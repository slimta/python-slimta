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

__all__ = ['validate_tls', 'build_ipv4_socket_creator',
           'create_connection_ipv4']


def validate_tls(tls, **overrides):
    """Given a dictionary that could be used as keyword arguments to
    :class:`ssl.wrap_socket`, checks the existence of any certificate files.

    :param tls: Dictionary of TLS settings as might be passed in to an |Edge|
                constructor.
    :type tls: dict
    :param overrides: May be used to override any of the elements of the
                      ``tls`` dictionary.
    :type overrides: keyword arguments
    :returns: The new, validated ``tls`` dictionary.
    :raises: OSError

    """
    if tls is False:
        return tls
    elif tls is None or tls is True:
        return {}
    tls_copy = tls.copy()
    tls_copy.update(overrides)
    for arg in ('keyfile', 'certfile', 'ca_certs'):
        if arg in tls_copy:
            open(tls_copy[arg], 'r').close()
    return tls_copy


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


# vim:et:fdm=marker:sts=4:sw=4:ts=4
