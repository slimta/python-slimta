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

"""

"""

from __future__ import absolute_import

from gevent import Greenlet, Timeout
from gevent.event import AsyncResult

from slimta.util.deque import BlockingDeque
from . import Relay

__all__ = ['RelayPool', 'RelayPoolClient']


class RelayPool(Relay):
    """Base class that inherits |Relay| to add the ability to create bounded,
    cached pools of outbound clients. It maintains a queue of messages to be
    delivered such that idle clients in the pool pick them up.

    :param pool_size: At most this many simultaneous connections will be open
                      to a destination. If this limit is reached and no
                      connections are idle, new attempts will block.

    """

    def __init__(self, pool_size=None):
        super(RelayPool, self).__init__()
        self.pool = set()
        self.pool_size = pool_size

        #: This attribute holds the queue object for providing delivery
        #: requests to idle clients in the pool.
        self.queue = BlockingDeque()

    def kill(self):
        for client in self.pool:
            client.kill()

    def _remove_client(self, client):
        self.pool.remove(client)
        if len(self.queue) > 0 and not self.pool:
            self._add_client()

    def _add_client(self):
        client = self.add_client()
        client.queue = self.queue
        client.start()
        client.link(self._remove_client)
        self.pool.add(client)

    def _check_idle(self):
        for client in self.pool:
            if client.idle:
                return
        if not self.pool_size or len(self.pool) < self.pool_size:
            self._add_client()

    def add_client(self):
        """Sub-classes must override this method to create and return a new
        :class:`RelayPoolClient` object that will poll for delivery requests.

        :rtype: :class:`RelayPoolClient`

        """
        raise NotImplementedError()

    def attempt(self, envelope, attempts):
        self._check_idle()
        result = AsyncResult()
        self.queue.append((result, envelope))
        return result.get()


class RelayPoolClient(Greenlet):
    """Base class for implementing clients for handling delivery requests in a
    :class:`RelayPool`.

    :param queue: The queue on which delivery requests will be received.
    :param idle_timeout: If the client can handle multiple, pipelined delivery
                         requests, this is the timeout in seconds that a client
                         will wait for subsequent requests.

    """

    def __init__(self, queue, idle_timeout=None):
        super(RelayPoolClient, self).__init__()
        self.idle = False
        self.queue = queue

        #: This attribute holds the idle timeout for handling multiple delivery
        #: requests on the client.
        self.idle_timeout = idle_timeout

    def poll(self):
        """This method can be used by clients to receive new delivery requests
        from the client pool. This method will block until a delivery request
        is received.

        :returns: A tuple containing the :class:`~gevent.event.AsyncResult` and
                  the :class:`~slimta.envelope.Envelope` that make up a
                  delivery request. If no delivery requests are received before
                  the :attr:`idle_timeout` timeout, ``(None, None)`` is
                  returned.

        """
        self.idle = True
        try:
            with Timeout(self.idle_timeout, False):
                return self.queue.popleft()
            return None, None
        finally:
            self.idle = False

    def _run(self):
        """This method must be overriden by sub-classes to handle processing of
        delivery requests. It should call :meth:`poll` when it is ready for new
        delivery requests. The result of the delivery attempt should be written
        to the :class:`~gevent.event.AsyncResult` object provided in the
        request.

        """
        raise NotImplementedError()


# vim:et:fdm=marker:sts=4:sw=4:ts=4
