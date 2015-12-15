# Copyright (c) 2015 Ian C. Good
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

"""Package providing support for the `PROXY protocol`_ on various edge
services.

.. _PROXY protocol: http://www.haproxy.org/download/1.5/doc/proxy-protocol.txt

"""

from __future__ import absolute_import

from gevent import socket

from slimta.logging import getSocketLogger

__all__ = ['ProxyProtocolV1']

log = getSocketLogger(__name__)


class ProxyProtocolV1(object):
    """Implements version 1 of the proxy protocol, to avoid losing information
    about the original connection when routing traffic through a proxy. This
    process involves an extra line sent by the client at the beginning of every
    cconnection.

    Mix-in before an implementation of :class:`~slimta.edge.EdgeServer` to
    expect every connection to begin with a proxy protocol header. The
    ``address`` argument passed in to the
    :meth:`~slimta.edge.EdgeServer.handle` method will contain information
    about the original connection source, before proxying.

    """

    #: The source address returned if UNKNOWN is given in the proxy protocol
    #: header.
    unknown_pp_source_address = (None, None)

    #: The destination address returned if UNKNOWN is given in the proxy
    #: protocol header.
    unknown_pp_dest_address = (None, None)

    #: The source address returned if there was a parsing error or EOF while
    #: reading the proxy protocol header.
    invalid_pp_source_address = (None, None)

    #: The destination address returned if there was a parsing error or EOF
    #: while reading the proxy protocol header.
    invalid_pp_dest_address = (None, None)

    def __read_pp_line(self, sock):
        buf = bytearray(107)
        read = memoryview(buf)[0:0].tobytes()
        while len(read) < len(buf):
            where = memoryview(buf)[len(read):]
            try_read = min(len(where), 1 if read.endswith(b'\r') else 2)
            read_n = sock.recv_into(where, try_read)
            assert read_n, 'Received EOF during proxy protocol header'
            read = memoryview(buf)[0:len(read)+read_n].tobytes()
            if read.endswith(b'\r\n'):
                break
        return read

    def parse_pp_line(self, line):
        """Given a bytestring containing a single line ending in CRLF, parse
        into two source and destination address tuples of the form
        ``(ip, port)`` and return them.

        :param line: Bytestring ending in CRLF
        :returns: Two tuples for source and destination addresses, as might be
                  returned by :py:func:`~socket.getpeername` and
                  :py:func:`~socket.getsockname`.

        """
        assert line.startswith(b'PROXY ') and line.endswith(b'\r\n'), \
            "String must start with 'PROXY' and end with CRLF"
        line = line[6:-2]
        parts = line.split(b' ')
        if parts[0] == b'UNKNOWN':
            return self.unknown_pp_source_address, self.unknown_pp_dest_address
        family = self.__get_pp_family(parts[0])
        assert len(parts) == 5, \
            'Invalid proxy protocol header format'
        source_addr = (self.__get_pp_ip(family, parts[1], 'source'),
                       self.__get_pp_port(parts[3], 'source'))
        dest_addr = (self.__get_pp_ip(family, parts[2], 'destination'),
                     self.__get_pp_port(parts[4], 'destination'))
        return source_addr, dest_addr

    def __get_pp_family(self, family_string):
        if family_string == b'TCP4':
            return socket.AF_INET
        elif family_string == b'TCP6':
            return socket.AF_INET6
        else:
            raise AssertionError('Invalid proxy protocol address family')

    def __get_pp_ip(self, addr_family, ip_string, which):
        try:
            packed = socket.inet_pton(addr_family, ip_string.decode('ascii'))
            return socket.inet_ntop(addr_family, packed)
        except (UnicodeDecodeError, socket.error):
            msg = 'Invalid proxy protocol {0} IP format'.format(which)
            raise AssertionError(msg)

    def __get_pp_port(self, port_string, which):
        try:
            port_num = int(port_string)
        except ValueError:
            msg = 'Invalid proxy protocol {0} port format'.format(which)
            raise AssertionError(msg)
        assert port_num >= 0 and port_num <= 65535, \
            'Proxy protocol {0} port out of range'.format(which)
        return port_num

    def handle(self, sock, addr):
        """Intercepts calls to :meth:`~slimta.edge.EdgeServer.handle`, reads
        the proxy protocol header, and then resumes the original call.

        """
        try:
            line = self.__read_pp_line(sock)
            log.recv(sock, line)
            src_addr, _ = self.parse_pp_line(line)
        except AssertionError as exc:
            log.proxyproto_invalid(sock, exc)
            src_addr = self.invalid_pp_source_address
        else:
            log.proxyproto_success(sock, src_addr)
        return super(ProxyProtocolV1, self).handle(sock, src_addr)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
