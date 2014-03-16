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

"""Package defining a common interface upon which a message can be received on
a listening socket under various protocols.

"""

from __future__ import absolute_import

import time
from socket import getfqdn

import gevent
from gevent.server import StreamServer
from gevent.ssl import SSLSocket

from slimta import logging

__all__ = ['Edge', 'EdgeServer']

log = logging.getSocketLogger(__name__)


class Edge(object):
    """This class should be used as the base for all *edge* services. Most will
    directly inherit :class:`EdgeServer` and thus indirectly inherit
    :class:`Edge`.

    :param queue: |Queue| (Or |Queue|-like) object that will take
                  responsibility for delivery of messages received by the
                  :class:`Edge`.
    :param hostname: String identifying the local machine, stamped to each
                     received message in its
                     :attr:`~slimta.envelope.Envelope.receiver` attribute for
                     use in headers and bounce messages. By default, the return
                     value of :func:`~gevent.socket.getfqdn()` is used.

    """

    def __init__(self, queue, hostname=None):
        super(Edge, self).__init__()
        self.queue = queue
        self.hostname = hostname or getfqdn()

    def handoff(self, envelope):
        """This method may be called manually or by whatever mechanism a
        sub-class uses to receive new |Envelope| messages from a client.
        Because a |QueuePolicy| may generate new |Envelope| objects, this
        method returns a list of tuples, ``(envelope, result)`` where
        ``result`` is either an ID string or a
        :class:`~slimta.queue.QueueError`. The edge service can then use this
        information to report back success or failure to the client.

        :param envelope: |Envelope| containing the received message.
        :returns: List of tuples containing each |Envelope| and its
                  corresponding ID string or :class:`~slimta.queue.QueueError`.

        """
        envelope.receiver = self.hostname
        envelope.timestamp = time.time()

        try:
            return self.queue.enqueue(envelope)
        except Exception:
            logging.log_exception(__name__)
            raise

    def kill(self):
        """.. versionadded:: 0.3.15

        This method is used by |Edge| and |Edge|-like objects to properly end
        associated services (such as running :class:`~gevent.Greenlet` threads)
        and close resources.

        """
        pass


class EdgeServer(Edge, gevent.Greenlet):
    """This class implements a :class:`~gevent.Greenlet` serving a
    :class:`~gevent.server.StreamServer` until killed. Connections are accepted
    on the socket and passed to :meth:`.handle()`, which should be overriden
    by implementers of this base class. The socket will be closed
    automatically.

    :param queue: |Queue| object used by :meth:`.handoff()` to ensure the
                  envelope is properly queued before acknowledged by the edge
                  service.
    :param listener: Usually a ``(ip, port)`` tuple defining the interface and
                     port upon which to listen for connections. See
                     the ``listener`` parameter to
                     :class:`~gevent.baseserver.BaseServer` for more
                     information.
    :param pool: If given, defines a specific :class:`gevent.pool.Pool` to
                 use for new greenlets.
    :param hostname: String identifying the local machine. See |Edge| for more
                     details.

    """

    def __init__(self, listener, queue, pool=None, hostname=None):
        super(EdgeServer, self).__init__(queue, hostname)
        spawn = pool or 'default'
        self.server = StreamServer(listener, self._handle, spawn=spawn)

    def _handle(self, socket, address):
        log.accept(self.server.socket, socket, address)
        try:
            self.handle(socket, address)
        except Exception:
            logging.log_exception(__name__)
            raise

    def handle(self, socket, address):
        """Override this function to receive messages on the socket and call
        :meth:`.handoff()` with each received |Envelope| object.

        :param socket: The socket for the connected client.
        :param address: The address of the connected client.

        :raises: :py:exc:`NotImplementedError`

        """
        raise NotImplementedError()

    def kill(self):
        self.server.stop()

    def _run(self):
        self.server.start()
        self.server.serve_forever()


# vim:et:fdm=marker:sts=4:sw=4:ts=4
