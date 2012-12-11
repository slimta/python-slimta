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

__all__ = ['Edge']


class Edge(gevent.Greenlet):
    """This class implements a :class:`~gevent.Greenlet` serving a
    :class:`~gevent.server.StreamServer` until killed. Connections are accepted
    on the socket and passed to :meth:`._handle()`, which should be overriden
    by implementers of this base class.

    :param listener: Usually a (ip, port) tuple defining the interface and
                     port upon which to listen for connections.
    :param handoff: Should be called by :meth:`_handle()` when a new message
                    is received, passed in an :class:`Envelope` containing
                    the message and a :class:`Reply` for changing the reply
                    to the message.
    :param pool: If given, defines a specific :class:`gevent.pool.Pool` to
                 use for new greenlets.

    """

    def __init__(self, listener, handoff, pool=None):
        super(Edge, self).__init__()
        spawn = pool or 'default'
        self.server = StreamServer(listener, self._handle, spawn=spawn)
        self.handoff = handoff

    def _handle(self, socket, address):
        """Override this function to receive messages on the socket and call
        `self.handoff()`.

        :param socket: The socket for the connected client.
        :param address: The address of the connected client.

        :raises: :class:`NotImplemented`

        """
        raise NotImplemented()

    def _run(self):
        self.server.start()
        self.server.serve_forever()


# vim:et:fdm=marker:sts=4:sw=4:ts=4
