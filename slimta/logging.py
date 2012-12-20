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

"""Utilities to make logging consistent and easy in :mod:`slimta` packages."""

from __future__ import absolute_import

import logging
from pprint import pformat

__all__ = ['getSocketLogger']


def getSocketLogger(name):
    """Wraps the result of :func:python:`logging.getLogger()` in a
    :class:`SocketLogger` object to provide limited and consistent logging
    output for socket operations.

    :param name: ``name`` as passed in to :func:python:`logging.getLogger()`.
    :rtype: :class:`SocketLogger`

    """
    logger = logging.getLogger(name)
    return SocketLogger(logger)


class SocketLogger(object):
    """Provides a limited set of log methods that :mod:`slimta` packages may
    use. This prevents free-form logs from mixing in with standard, machine-
    parseable logs.

    :param log: :class:python:`logging.Logger` object to log through.

    """

    def __init__(self, log):
        self.log = log

    def _stringify_address(self, address):
        if isinstance(address, tuple):
            return '{0}:{1!s}'.format(*address)
        return address

    def send(self, socket, data):
        """Logs a socket :meth:`~socket.socket.send()` operation along with the
        peer the socket is connected to.

        :param socket: The socket that has sent data.
        :param data: The data that was sent.

        """
        fd = socket.fileno()
        msg = 'fd:{0}:send {1}'.format(fd, pformat(data))
        self.log.debug(msg)

    def recv(self, socket, data):
        """Logs a socket :meth:`~socket.socket.recv()` operation along with the
        peer the socket is connected to.

        :param socket: The socket that has received data.
        :param data: The data that was received.

        """
        fd = socket.fileno()
        msg = 'fd:{0}:recv {1}'.format(fd, pformat(data))
        self.log.debug(msg)

    def accept(self, server, client, address=None):
        """Logs a socket :meth:`~socket.socket.accept()` operation along with
        the server that received it and the peer that initiated it.

        :param server: The server socket that received the connection.
        :param client: The client socket that was accepted.
        :param address: If known, the peer address of the client socket.

        """
        server_fd = server.fileno()
        client_fd = client.fileno()
        client_peer = self._stringify_address(address or client.getpeername())
        msg = 'fd:{0}:accept {1} {2}'.format(server_fd, client_fd, client_peer)
        self.log.debug(msg)

    def connect(self, socket, address=None):
        """Logs a socket :meth:`~socket.socket.connect()` operation along with
        the peer the socket is connected to. Logged at the ``DEBUG`` level.

        :param socket: The socket that was connected.
        :param address: If known, the peer address the socket connected to.

        """
        fd = socket.fileno()
        peer = self._stringify_address(address or socket.getpeername())
        msg = 'fd:{0}:connect {1}'.format(fd, peer)
        self.log.debug(msg)

    def close(self, socket):
        """Logs a socket :meth:`~socket.socket.close()` operation along with
        the peer the socket was connected to. Logged at the ``DEBUG`` level.

        :param socket: The socket that was closed.

        """
        fd = socket.fileno()
        msg = 'fd:{0}:close'.format(fd)
        self.log.debug(msg)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
