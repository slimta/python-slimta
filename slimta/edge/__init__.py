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

import gevent
from gevent.server import StreamServer
from gevent.ssl import SSLSocket

from slimta import logging

__all__ = ['Edge']

log = logging.getSocketLogger(__name__)


class Edge(gevent.Greenlet):
    """This class implements a :class:`~gevent.Greenlet` serving a
    :class:`~gevent.server.StreamServer` until killed. Connections are accepted
    on the socket and passed to :meth:`.handle()`, which should be overriden
    by implementers of this base class. The socket will be closed automatically.

    :param listener: Usually a (ip, port) tuple defining the interface and
                     port upon which to listen for connections.
    :param queue: |Queue| object used by :meth:`.handoff()` to ensure the
                  envelope is properly queued before acknowledged by the edge
                  service.
    :param pool: If given, defines a specific :class:`gevent.pool.Pool` to
                 use for new greenlets.

    """

    def __init__(self, listener, queue, pool=None):
        super(Edge, self).__init__()
        spawn = pool or 'default'
        self.server = StreamServer(listener, self._handle, spawn=spawn)
        self.queue = queue

    def handoff(self, envelope):
        """When :meth:`.handle()` finishes receiving a message, it should pass
        the new |Envelope| object to this method. Because a |QueuePolicy| may
        generate new |Envelope| objects, this method returns a list of tuples,
        ``(envelope, result)`` where ``result`` is either an ID string or a
        :class:`~slimta.queue.QueueError`. The edge service can then use this
        information to report back success or failure to the client.

        :param envelope: |Envelope| containing the received message.
        :returns: List of tuples containing each |Envelope| and its
                  corresponding ID string or :class:`~slimta.queue.QueueError`.

        """
        return self.queue.enqueue(envelope)

    def _handle(self, socket, address):
        log.accept(self.server.socket, socket, address)
        self.handle(socket, address)

    def handle(self, socket, address):
        """Override this function to receive messages on the socket and call
        :meth:`.handoff()` with each received |Envelope| object.

        :param socket: The socket for the connected client.
        :param address: The address of the connected client.

        :raises: :class:`NotImplementedError`

        """
        raise NotImplementedError()

    def _run(self):
        self.server.start()
        self.server.serve_forever()


# vim:et:fdm=marker:sts=4:sw=4:ts=4
