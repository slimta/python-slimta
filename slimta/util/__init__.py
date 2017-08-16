# Copyright (c) 2016 Ian C. Good
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

"""Package containing a variety of useful modules utilities that didn't really
belong anywhere else.

"""

from __future__ import absolute_import

from gevent import socket

__all__ = ['build_ipv4_socket_creator', 'create_connection_ipv4']


def build_ipv4_socket_creator(only_ports=None):
    """Returns a function that will act like
    :py:func:`socket.create_connection` but only using IPv4 addresses. This
    function can be used as the ``socket_creator`` argument to some classes
    like :class:`~slimta.relay.smtp.mx.MxSmtpRelay`.

    :param only_ports: If given, can be a list to limit which ports are
                       restricted to IPv4. Connections to all other ports may
                       be IPv6.

    """
    def socket_creator(*args, **kwargs):
        return create_connection_ipv4(*args, only_ports=only_ports, **kwargs)
    return socket_creator


def create_connection_ipv4(address, timeout=None, source_address=None,
                           only_ports=None):
    """Attempts to mimick to :py:func:`socket.create_connection`, but
    connections are only made to IPv4 addresses.

    :param only_ports: If given, can be a list to limit which ports are
                       restricted to IPv4. Connections to all other ports may
                       be IPv6.

    """
    host, port = address
    if only_ports and port not in only_ports:
        return socket.create_connection(address, timeout, source_address)
    last_exc = None
    for res in socket.getaddrinfo(host, port, socket.AF_INET):
        _, _, _, _, sockaddr = res
        try:
            return socket.create_connection(sockaddr,  timeout, source_address)
        except socket.error as exc:
            last_exc = exc
    if last_exc is not None:
        raise last_exc
    else:
        raise socket.error('getaddrinfo returns an empty list')


def create_listeners(address,
                     family=socket.AF_UNSPEC,
                     socktype=socket.SOCK_STREAM,
                     proto=socket.IPPROTO_IP):
    """Uses :func:`socket.getaddrinfo` to create listening sockets for
    available socket parameters. For example, giving *address* as
    ``('localhost', 80)`` on a system with IPv6 would return one socket bound
    to ``127.0.0.1`` and one bound to ``::1`.

    May also be used for ``socket.AF_UNIX`` with a file path to produce a
    single unix domain socket listening on that path.

    :param address: A ``(host, port)`` tuple to listen on.
    :param family: the socket family, default ``AF_UNSPEC``.
    :param socktype: the socket type, default ``SOCK_STREAM``.
    :param proto: the socket protocol, default ``IPPROTO_IP``.

    """
    if family == socket.AF_UNIX:
        sock = socket.socket(family, socktype, proto)
        _init_socket(sock, address)
        return [sock]
    elif not isinstance(address, tuple) or len(address) != 2:
        raise ValueError(address)
    flags = socket.AI_PASSIVE
    host, port = address
    listeners = []
    last_exc = None
    for res in socket.getaddrinfo(host, port, family, socktype, proto, flags):
        fam, typ, prt, _, sockaddr = res
        try:
            sock = socket.socket(fam, typ, prt)
            _init_socket(sock, sockaddr)
        except socket.error as exc:
            last_exc = exc
        else:
            listeners.append(sock)
    if last_exc and not listeners:
        raise last_exc
    return listeners


def _init_socket(sock, sockaddr):
    try:
        sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
    except socket.error as exc:
        pass
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    except socket.error as exc:
        pass
    sock.setblocking(0)
    sock.bind(sockaddr)
    if sock.type != socket.SOCK_DGRAM:
        sock.listen(socket.SOMAXCONN)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
