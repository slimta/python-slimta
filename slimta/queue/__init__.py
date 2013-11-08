# Copyright (c) 2012 Ian C. Good
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

"""Package defining common functionality for SMTP queuing. According to the
SMTP RFCs, a server must persistently store a message before telling the client
it accepts the message. Rather than being a traditional queue data structure,
SMTP queues will retry messages after certain periods of time.

"""

from __future__ import absolute_import

import time
import bisect
from itertools import imap, izip, repeat, chain

import gevent
from gevent import Greenlet
from gevent.event import Event
from gevent.coros import Semaphore
from gevent.pool import Pool

from slimta.logging import log_exception
from slimta.core import SlimtaError
from slimta.relay import PermanentRelayError, TransientRelayError
from slimta.smtp.reply import Reply
from slimta.bounce import Bounce
from slimta.policy import QueuePolicy

__all__ = ['QueueError', 'Queue', 'QueueStorage']


class QueueError(SlimtaError):
    """Base exception for errors in the queue package."""
    pass


class QueueStorage(object):
    """Base class to show the interface that classes must implement to be a
    storage mechanism for :class:`Queue`.

    """
    def __init__(self):
        pass

    def write(self, envelope, timestamp):
        """Writes the given envelope to storage, along with the timestamp of
        its next delivery attempt. The number of delivery attempts asociated
        with the message should start at zero.

        :param envelope: |Envelope| object to write.
        :param timestamp: Timestamp of message's next delivery attempt.
        :returns: Unique identifier string for the message in queue.
        :raises: :class:`QueueError`

        """
        raise NotImplementedError()

    def set_timestamp(self, id, timestamp):
        """Sets a new timestamp for the message's next delivery attempt.

        :param id: The unique identifier string for the message.
        :param timestamp: The new delivery attempt timestamp.
        :raises: :class:`QueueError`

        """
        raise NotImplementedError()

    def increment_attempts(self, id):
        """Increments the number of delivery attempts associated with the
        message.

        :param id: The unique identifier string for the message.
        :returns: The new number of message delivery attempts.
        :raises: :class:`QueueError`

        """
        raise NotImplementedError()

    def load(self):
        """Loads all queued messages from the storage engine, such that the
        :class:`Queue` can be aware of all upcoming delivery attempts.

        :returns: Iterable that yields tuples of the form ``(timestamp, id)``
                  for each message in storage.
        :raises: :class:`QueueError`

        """
        raise NotImplementedError()

    def get(self, id):
        """Returns the |Envelope| object associated with the given unique
        identifier sring.

        :param id: The unique identifier string of the requested |Envelope|.
        :returns: Tuple with the |Envelope| object and number of attempts.
        :raises: :class:`KeyError`, :class:`QueueError`

        """
        raise NotImplementedError()

    def remove(self, id):
        """Removes the |Envelope| associated with the given unique identifier
        string from queue storage. This is typically used when the message has
        been successfully delivered or delivery has permanently failed.

        :param id: The unique identifier string of the |Envelope| to remove.
        :raises: :class:`QueueError`

        """
        raise NotImplementedError()

    def wait(self):
        """If messages are not being delivered from the same process in which
        they were received, the storage mechanism needs a way to wait until it
        is notified that a new message has been stored.

        :returns: An iterable or generator producing tuples with the timestamp
                  and unique identifier string of a new message in storage. When
                  the iterable or generator is exhausted, :meth:`.wait` is
                  simply called again.

        """
        raise NotImplementedError()


class Queue(Greenlet):
    """Manages the queue of |Envelope| objects waiting for delivery. This is
    not a standard FIFO queue, a message's place in the queue depends entirely
    on the timestamp of its next delivery attempt.

    :param store: Object implementing :class:`QueueStorage`.
    :param relay: |Relay| object used to attempt message deliveries. If this
                  is not given, no deliveries will be attempted on received
                  messages.
    :param backoff: Function that, given an |Envelope| and number of delivery
                    attempts, will return the number of seconds before the next
                    attempt. If it returns ``None``, the message will be
                    permanently failed. The default backoff function simply
                    returns ``None`` and messages are never retried.
    :param bounce_factory: Function that produces a |Bounce| object given the
                           same parameters as the |Bounce| constructor. If the
                           function returns ``None``, no bounce is delivered.
                           By default, a new |Bounce| is created in every case.
    :param store_pool: Number of simultaneous operations performable against
                       the ``store`` object. Default is unlimited.
    :param relay_pool: Number of simultaneous operations performable against
                       the ``relay`` object. Default is unlimited.

    """

    def __init__(self, store, relay=None, backoff=None, bounce_factory=None,
                 store_pool=None, relay_pool=None):
        super(Queue, self).__init__()
        self.store = store
        self.relay = relay
        self.backoff = backoff or self._default_backoff
        self.bounce_factory = bounce_factory or Bounce
        self.wake = Event()
        self.queued = []
        self.active_ids = set()
        self.queued_ids = set()
        self.queued_lock = Semaphore(1)
        self.queue_policies = []
        self._use_pool('store_pool', store_pool)
        self._use_pool('relay_pool', relay_pool)

    def add_policy(self, policy):
        """Adds a |QueuePolicy| to be executed before messages are persisted
        to storage.

        :param policy: |QueuePolicy| object to execute.

        """
        if isinstance(policy, QueuePolicy):
            self.queue_policies.append(policy)
        else:
            raise TypeError('Argument not a QueuePolicy.')

    @staticmethod
    def _default_backoff(envelope, attempts):
        pass

    def _run_policies(self, envelope):
        results = [envelope]

        def recurse(current, i):
            try:
                policy = self.queue_policies[i]
            except IndexError:
                return
            ret = policy.apply(current)
            if ret:
                results.remove(current)
                results.extend(ret)
                for env in ret:
                    recurse(env, i+1)
            else:
                recurse(current, i+1)
        recurse(envelope, 0)
        return results

    def _use_pool(self, attr, pool):
        if pool is None:
            pass
        elif isinstance(pool, Pool):
            setattr(self, attr, pool)
        else:
            setattr(self, attr, Pool(pool))

    def _pool_run(self, which, func, *args, **kwargs):
        pool = getattr(self, which+'_pool', None)
        if pool:
            ret = pool.spawn(func, *args, **kwargs)
            return ret.get()
        else:
            return func(*args, **kwargs)

    def _pool_imap(self, which, func, *iterables):
        pool = getattr(self, which+'_pool', gevent)
        threads = imap(pool.spawn, repeat(func), *iterables)
        ret = []
        for thread in threads:
            thread.join()
            ret.append(thread.exception or thread.value)
        return ret

    def _pool_spawn(self, which, func, *args, **kwargs):
        pool = getattr(self, which+'_pool', gevent)
        return pool.spawn(func, *args, **kwargs)

    def _add_queued(self, entry):
        timestamp, id = entry
        if id not in self.queued_ids | self.active_ids:
            bisect.insort(self.queued, entry)
            self.queued_ids.add(id)
            self.wake.set()

    def enqueue(self, envelope):
        """Drops a new message in the queue for delivery. The first delivery
        attempt is made immediately (depending on relay pool availability).
        This method is not typically called directly, |Edge| objects use it
        when they receive new messages.

        :param envelope: |Envelope| object to enqueue.
        :returns: Zipped list of envelopes and their respective queue IDs (or
                  thrown :exc:`QueueError` objects).

        """
        now = time.time()
        envelopes = self._run_policies(envelope)
        ids = self._pool_imap('store', self.store.write, envelopes,
                              repeat(now))
        results = zip(envelopes, ids)
        for env, id in results:
            if not isinstance(id, BaseException):
                if self.relay:
                    self.active_ids.add(id)
                    self._pool_spawn('relay', self._attempt, id, env, 0)
            elif not isinstance(id, QueueError):
                raise id  # Re-raise exceptions that are not QueueError.
        return results

    def _load_all(self):
        for entry in self.store.load():
            self._add_queued(entry)

    def _remove(self, id):
        self.store.remove(id)
        self.queued_ids.discard(id)
        self.active_ids.discard(id)

    def _bounce(self, envelope, reply):
        bounce = self.bounce_factory(envelope, reply)
        if bounce:
            return self.enqueue(bounce)

    def _perm_fail(self, id, envelope, reply):
        self._pool_spawn('store', self._remove, id)
        if envelope.sender:  # Can't bounce to null-sender.
            self._pool_spawn('bounce', self._bounce, envelope, reply)

    def _retry_later(self, id, envelope, reply):
        attempts = self.store.increment_attempts(id)
        wait = self.backoff(envelope, attempts)
        if wait is None:
            reply.message += ' (Too many retries)'
            self._perm_fail(id, envelope, reply)
        else:
            when = time.time() + wait
            self.store.set_timestamp(id, when)
            self.active_ids.discard(id)
            self._add_queued((when, id))

    def _attempt(self, id, envelope, attempts):
        try:
            self.relay._attempt(envelope, attempts)
        except TransientRelayError as e:
            self._pool_spawn('store', self._retry_later, id, envelope, e.reply)
        except PermanentRelayError as e:
            self._perm_fail(id, envelope, e.reply)
        except Exception as e:
            log_exception(__name__)
            reply = Reply('450', '4.0.0 Unhandled delivery error: '+str(e))
            self._pool_spawn('store', self._retry_later, id, envelope, reply)
            raise
        else:
            self._pool_spawn('store', self._remove, id)

    def _dequeue(self, id):
        try:
            envelope, attempts = self.store.get(id)
        except KeyError:
            return
        self.active_ids.add(id)
        self._pool_spawn('relay', self._attempt, id, envelope, attempts)

    def _check_ready(self, now):
        last_i = 0
        for i, entry in enumerate(self.queued):
            timestamp, id = entry
            if now >= timestamp:
                self._pool_spawn('store', self._dequeue, id)
                last_i = i+1
            else:
                break
        if last_i > 0:
            self.queued = self.queued[last_i:]
            self.queued_ids = set([id for timestamp, id in self.queued])

    def _wait_store(self):
        while True:
            try:
                for entry in self.store.wait():
                    self._add_queued(entry)
            except NotImplementedError:
                return

    def _wait_ready(self, now):
        try:
            first = self.queued[0]
        except IndexError:
            self.wake.wait()
            self.wake.clear()
            return
        first_timestamp = first[0]
        if first_timestamp > now:
            self.wake.wait(first_timestamp-now)
            self.wake.clear()

    def flush(self):
        """Attempts to immediately flush all messages waiting in the queue,
        regardless of their retry timers.

        ***Note:*** This can be a very expensive operation, use with care.

        """
        self.wake.set()
        self.wake.clear()
        self.queued_lock.acquire()
        try:
            for entry in self.queued:
                self._pool_spawn('store', self._dequeue, entry[1])
            self.queued = []
        finally:
            self.queued_lock.release()

    def kill(self):
        """This method is used by |Queue| and |Queue|-like objects to properly
        end any associated services (such as running :class:`~gevent.Greenlet`
        threads) and close resources.

        """
        super(Queue, self).kill()

    def _run(self):
        if not self.relay:
            return
        self._pool_spawn('store', self._load_all)
        self._pool_spawn('store', self._wait_store)
        while True:
            self.queued_lock.acquire()
            try:
                now = time.time()
                self._check_ready(now)
                self._wait_ready(now)
            finally:
                self.queued_lock.release()


# vim:et:fdm=marker:sts=4:sw=4:ts=4
