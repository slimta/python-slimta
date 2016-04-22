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

"""Utilities to make logging consistent and easy for any socket interaction."""

from __future__ import absolute_import

from functools import partial

from gevent.socket import SHUT_WR, SHUT_RD

__all__ = ['SocketLogger']


class SocketLogger(object):
    """Provides a limited set of log methods that :mod:`slimta` packages may
    use. This prevents free-form logs from mixing in with standard, machine-
    parseable logs.

    :param log: :py:class:`logging.Logger` object to log through.

    """

    def __init__(self, log):
        from slimta.logging import logline
        self.log = partial(logline, log.debug, 'fd')
        self.log_error = partial(logline, log.error, 'fd')

    def send(self, socket, data):
        """Logs a socket :meth:`~socket.socket.send()` operation along with the
        peer the socket is connected to.

        :param socket: The socket that has sent data.
        :param data: The data that was sent.

        """
        self.log(socket.fileno(), 'send', data=data)

    def recv(self, socket, data):
        """Logs a socket :meth:`~socket.socket.recv()` operation along with the
        peer the socket is connected to.

        :param socket: The socket that has received data.
        :param data: The data that was received.

        """
        self.log(socket.fileno(), 'recv', data=data)

    def accept(self, server, client, address=None):
        """Logs a socket :meth:`~socket.socket.accept()` operation along with
        the server that received it and the peer that initiated it.

        :param server: The server socket that received the connection.
        :param client: The client socket that was accepted.
        :param address: If known, the peer address of the client socket.

        """
        client_peer = address or client.getpeername()
        self.log(server.fileno(), 'accept',
                 clientfd=client.fileno(),
                 peer=client_peer)

    def connect(self, socket, address=None):
        """Logs a socket :meth:`~socket.socket.connect()` operation along with
        the peer the socket is connected to. Logged at the ``DEBUG`` level.

        :param socket: The socket that was connected.
        :param address: If known, the peer address the socket connected to.

        """
        peer = address or socket.getpeername()
        self.log(socket.fileno(), 'connect', peer=peer)

    def encrypt(self, socket, tls_args):
        """Logs a socket encryption operation along with the certificate and
        key files used and whether the socket is acting as the client or the
        server.

        :param socket: The socket that was shutdown.
        :param tls_args: Keyword rguments passed to the encryption operation.

        """
        keyfile = tls_args.get('keyfile', None)
        certfile = tls_args.get('certfile', None)
        server_side = tls_args.get('server_side', False)
        self.log(socket.fileno(), 'encrypt',
                 keyfile=keyfile,
                 certfile=certfile,
                 server_side=server_side)

    def shutdown(self, socket, how):
        """Logs a socket :meth:`~socket.socket.shutdown()` operation along
        with which part of the socket was shut down. Logged at the
        ``DEBUG`` level.

        :param socket: The socket that was shutdown.
        :param how: The ``how`` parameter, as passed to ``shutdown()``.

        """
        how_str = 'both'
        if how == SHUT_WR:
            how_str = 'write'
        elif how == SHUT_RD:
            how_str = 'read'
        self.log(socket.fileno(), 'shutdown', how=how_str)

    def close(self, socket):
        """Logs a socket :meth:`~socket.socket.close()` operation along with
        the peer the socket was connected to. Logged at the ``DEBUG`` level.

        :param socket: The socket that was closed.

        """
        self.log(socket.fileno(), 'close')

    def error(self, socket, exc, address=None):
        """Logs a :py:exc:`socket.error` exception. Logged at the ``ERROR``
        level and does not include a stack trace.

        :param socket: The socket that threw the error, if available.
        :param exc: The exception that was thrown.
        :param address: The remote address that threw the error, if available.

        """
        kwargs = {'message': str(exc), 'args': exc.args}
        fileno = 'none'
        if socket:
            fileno = socket.fileno()
        if address:
            kwargs['address'] = address
        self.log_error(fileno, 'error', **kwargs)

    def proxyproto_success(self, socket, src_addr):
        """Logs a successful proxy protocol header, with the new source address
        information. Logged at the ``DEBUG`` level.

        :param socket: The socket that received the header.
        :param src_addr: The new source address information.

        """
        self.log(socket.fileno(), 'ppsuccess', peer=src_addr)

    def proxyproto_invalid(self, socket, exc):
        """Logs an invalid proxy protocol header, with an exception provided by
        the :class:`~slimta.util.proxyproto.ProxyProtocol` class. Logged at the
        ``WARNING`` level.

        :param socket: The socket that failed the proxy protocol.
        :param exc: The exception generated during the failure.

        """
        self.log(socket.fileno(), 'ppinvalid', message=str(exc))

    def proxyproto_local(self, sock):
        """Logs a successful proxy protocol header that indicates a "local"
        connection from the proxy itself, to perform a health check.

        """
        self.log(sock.fileno(), 'pplocal')


# vim:et:fdm=marker:sts=4:sw=4:ts=4
