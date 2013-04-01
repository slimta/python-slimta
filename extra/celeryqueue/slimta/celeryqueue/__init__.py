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

"""Implements the |Queue| interface on top of `celery`_, a distributed task
queue system. When a message is enqueued, a delivery task is queued up in
celery. Celery workers will then pick up the task and attempt delivery, retrying
and bouncing in the same manner as |Queue|.

A :class:`celery.Celery` object must be given to :class:`CeleryQueue`, and a
task will be registered to attempt delivery of |Envelope| objects. It may be
desirable to configure celery workers to `use gevent`_, since ``slimta`` |Relay|
objects are expected to support it.

.. _celery: http://www.celeryproject.org/
.. _use gevent: http://docs.celeryproject.org/en/latest/configuration.html#celeryd-pool

"""

from celery.result import AsyncResult

from slimta.queue import QueueError
from slimta.relay import PermanentRelayError, TransientRelayError
from slimta.bounce import Bounce
from slimta.policy import QueuePolicy

__all__ = ['CeleryQueue']


class CeleryQueue(object):
    """Instantiates a new object that can be used wherever a |Queue| is
    expected.

    :param celery: :class:`celery.Celery` object to register delivery task with.
    :param relay: |Relay| instance to attempt delivery with.
    :param suffix: If given, the task registered in the :class:`~celery.Celery`
                   object will have its name suffixed wih an underscore and this
                   string.
    :param backoff: Function that, given an |Envelope| and number of delivery
                    attempts, will return the number of seconds before the next
                    attempt. If it returns ``None``, the message will be
                    permanently failed. The default backoff function simply
                    returns ``None`` and messages are never retried.
    :param bounce_factory: Function that produces a |Bounce| or |Envelope|
                           object given the same parameters as the |Bounce|
                           constructor. If the function returns ``None``, no
                           bounce is delivered.  By default, a new |Bounce| is
                           created in every case.

    """

    def __init__(self, celery, relay, suffix=None, backoff=None,
                       bounce_factory=None):
        if suffix:
            task_decorator = celery.task(name='attempt_delivery_'+suffix)
            self.attempt_task = task_decorator(self.attempt_delivery)
        else:
            self.attempt_task = celery.task(self.attempt_delivery)
        self.relay = relay
        self.bounce_factory = bounce_factory or Bounce
        self.backoff = backoff or self._default_backoff
        self.queue_policies = []

    def add_policy(self, policy):
        """Adds a |QueuePolicy| to be executed before messages are persisted
        to storage.

        :param policy: |QueuePolicy| object to execute.

        """
        if isinstance(policy, QueuePolicy):
            self.queue_policies.append(policy)
        else:
            raise TypeError('Argument not a QueuePolicy.')

    def flush(self):
        """The :meth:`~slimta.queue.Queue.flush` method from |Queue| is not
        available to :class:`CeleryQueue` objects.

        :raises: :class:`NotImplementedError`

        """
        raise NotImplementedError()

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

    def enqueue(self, envelope):
        envelopes = self._run_policies(envelope)
        ids = [self._initiate_attempt(env) for env in envelopes]
        results = zip(envelopes, ids)
        return results

    def _initiate_attempt(self, envelope, attempts=0, wait=None):
        attempt = self.attempt_task.s(envelope, attempts)
        if wait:
            attempt.set(countdown=wait)
        return attempt.apply_async().id

    def attempt_delivery(self, envelope, attempts):
        try:
            self.relay.attempt(envelope, attempts)
        except TransientRelayError, exc:
            wait = self.backoff(envelope, attempts+1)
            if wait:
                self._initiate_attempt(envelope, attempts+1, wait=wait)
            else:
                exc.reply.message += ' (Too many retries)'
                self.enqueue_bounce(envelope, exc.reply)
        except PermanentRelayError, exc:
            self.enqueue_bounce(envelope, exc.reply)

    def enqueue_bounce(self, envelope, reply):
        bounce = self.bounce_factory(envelope, reply)
        if bounce:
            self._initiate_attempt(bounce)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
