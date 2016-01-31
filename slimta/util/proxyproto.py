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

import struct

from gevent import socket

from slimta.logging import getSocketLogger

__all__ = ['ProxyProtocol', 'ProxyProtocolV1', 'ProxyProtocolV2']

log = getSocketLogger(__name__)

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


class LocalConnection(Exception):
    # Used to indicate that the parsed proxy protocol header is for a "local"
    # connection, and should not be proxied.
    pass


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

    @classmethod
    def __read_pp_line(cls, sock, initial):
        buf = bytearray(107)
        buf[0:len(initial)] = initial
        read = initial
        while len(read) < 8:
            where = memoryview(buf)[len(read):]
            read_n = sock.recv_into(where, 8-len(read))
            assert read_n, 'Received EOF during proxy protocol header'
            read = memoryview(buf)[0:len(read)+read_n].tobytes()
        while len(read) < len(buf):
            where = memoryview(buf)[len(read):]
            try_read = min(len(where), 1 if read.endswith(b'\r') else 2)
            read_n = sock.recv_into(where, try_read)
            assert read_n, 'Received EOF during proxy protocol header'
            read = memoryview(buf)[0:len(read)+read_n].tobytes()
            if read.endswith(b'\r\n'):
                break
        return read

    @classmethod
    def parse_pp_line(cls, line):
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
            return unknown_pp_source_address, unknown_pp_dest_address
        family = cls.__get_pp_family(parts[0])
        assert len(parts) == 5, \
            'Invalid proxy protocol header format'
        source_addr = (cls.__get_pp_ip(family, parts[1], 'source'),
                       cls.__get_pp_port(parts[3], 'source'))
        dest_addr = (cls.__get_pp_ip(family, parts[2], 'destination'),
                     cls.__get_pp_port(parts[4], 'destination'))
        return source_addr, dest_addr

    @classmethod
    def __get_pp_family(cls, family_string):
        if family_string == b'TCP4':
            return socket.AF_INET
        elif family_string == b'TCP6':
            return socket.AF_INET6
        else:
            raise AssertionError('Invalid proxy protocol address family')

    @classmethod
    def __get_pp_ip(cls, addr_family, ip_string, which):
        try:
            packed = socket.inet_pton(addr_family, ip_string.decode('ascii'))
            return socket.inet_ntop(addr_family, packed)
        except (UnicodeDecodeError, socket.error):
            msg = 'Invalid proxy protocol {0} IP format'.format(which)
            raise AssertionError(msg)

    @classmethod
    def __get_pp_port(cls, port_string, which):
        try:
            port_num = int(port_string)
        except ValueError:
            msg = 'Invalid proxy protocol {0} port format'.format(which)
            raise AssertionError(msg)
        assert port_num >= 0 and port_num <= 65535, \
            'Proxy protocol {0} port out of range'.format(which)
        return port_num

    @classmethod
    def process_pp_v1(cls, sock, initial):
        line = cls.__read_pp_line(sock, initial)
        log.recv(sock, line)
        return cls.parse_pp_line(line)

    def handle(self, sock, addr):
        """Intercepts calls to :meth:`~slimta.edge.EdgeServer.handle`, reads
        the proxy protocol header, and then resumes the original call.

        """
        try:
            src_addr, _ = self.process_pp_v1(sock, b'')
        except AssertionError as exc:
            log.proxyproto_invalid(sock, exc)
            src_addr = invalid_pp_source_address
        else:
            log.proxyproto_success(sock, src_addr)
        return super(ProxyProtocolV1, self).handle(sock, src_addr)


class ProxyProtocolV2(object):
    """Implements version 2 of the proxy protocol, to avoid losing information
    about the original connection when routing traffic through a proxy. This
    version is binary, and may be more efficient than version 1.

    Mix-in before an implementation of :class:`~slimta.edge.EdgeServer` to
    expect every connection to begin with a proxy protocol header. The
    ``address`` argument passed in to the
    :meth:`~slimta.edge.EdgeServer.handle` method will contain information
    about the original connection source, before proxying.

    """

    __commands = {0x00: 'local',
                  0x01: 'proxy'}
    __families = {0x10: socket.AF_INET,
                  0x20: socket.AF_INET6,
                  0x30: socket.AF_UNIX}
    __protocols = {0x01: socket.SOCK_STREAM,
                   0x02: socket.SOCK_DGRAM}

    @classmethod
    def __read_pp_data(cls, sock, length, initial):
        buf = bytearray(length)
        buf[0:len(initial)] = initial
        read = initial
        while len(read) < len(buf):
            where = memoryview(buf)[len(read):]
            read_n = sock.recv_into(where, len(buf)-len(read))
            assert read_n, 'Received EOF during proxy protocol header'
            read = memoryview(buf)[0:len(read)+read_n].tobytes()
        return bytearray(read)

    @classmethod
    def __parse_pp_data(cls, data):
        assert data[0:12] == b'\r\n\r\n\x00\r\nQUIT\n', \
            'Invalid proxy protocol v2 signature'
        assert data[13] & 0xf0 == 0x20, 'Invalid proxy protocol version'
        command = cls.__commands.get(data[12] & 0x0f)
        family = cls.__families.get(data[13] & 0xf0)
        protocol = cls.__protocols.get(data[13] & 0x0f)
        addr_len = struct.unpack('<H', data[14:16])[0]
        return command, family, protocol, addr_len

    @classmethod
    def __parse_pp_addresses(cls, family, addr_data):
        if family == socket.AF_INET:
            src_ip, dst_ip, src_port, dst_port = \
                struct.unpack('<4s4sHH', addr_data)
            src_addr = (socket.inet_ntop(family, src_ip), src_port)
            dst_addr = (socket.inet_ntop(family, dst_ip), dst_port)
            return src_addr, dst_addr
        elif family == socket.AF_INET6:
            src_ip, dst_ip, src_port, dst_port = \
                struct.unpack('<16s16sHH', addr_data)
            src_addr = (socket.inet_ntop(family, src_ip), src_port)
            dst_addr = (socket.inet_ntop(family, dst_ip), dst_port)
            return src_addr, dst_addr
        elif family == socket.AF_UNIX:
            src_addr, dst_addr = struct.unpack('<108s108s', addr_data)
            return src_addr.rstrip(b'\x00'), dst_addr.rstrip(b'\x00')
        else:
            return unknown_pp_source_address,  unknown_pp_dest_address

    @classmethod
    def process_pp_v2(cls, sock, initial):
        try:
            data = cls.__read_pp_data(sock, 16, initial)
            cmd, family, _, addr_len = cls.__parse_pp_data(data)
            addr_data = cls.__read_pp_data(sock, addr_len, b'')
            ret = cls.__parse_pp_addresses(family, addr_data)
            if cmd == 'local':
                raise LocalConnection()
            return ret
        except struct.error:
            raise AssertionError('Invalid proxy protocol data')

    def handle(self, sock, addr):
        """Intercepts calls to :meth:`~slimta.edge.EdgeServer.handle`, reads
        the proxy protocol header, and then resumes the original call.

        """
        try:
            src_addr, _ = self.process_pp_v2(sock, b'')
        except LocalConnection:
            log.proxyproto_local(sock)
            return
        except AssertionError as exc:
            log.proxyproto_invalid(sock, exc)
            src_addr = invalid_pp_source_address
        else:
            log.proxyproto_success(sock, src_addr)
        return super(ProxyProtocolV2, self).handle(sock, src_addr)


class ProxyProtocol(object):
    """Reads the first 8 bytes from the socket to determine which version of
    the proxy protocol is active before handing processing off to either
    :class:`ProxyProtocolV1` or :class:`ProxyProtocolV2`.

    Mix-in before an implementation of :class:`~slimta.edge.EdgeServer` to
    expect every connection to begin with a proxy protocol header. The
    ``address`` argument passed in to the
    :meth:`~slimta.edge.EdgeServer.handle` method will contain information
    about the original connection source, before proxying.

    """

    @classmethod
    def __read_pp_initial(cls, sock):
        buf = bytearray(8)
        read = b''
        while len(read) < len(buf):
            where = memoryview(buf)[len(read):]
            read_n = sock.recv_into(where, 8-len(read))
            assert read_n, 'Received EOF during proxy protocol header'
            read = memoryview(buf)[0:len(read)+read_n].tobytes()
        return read

    def handle(self, sock, addr):
        """Intercepts calls to :meth:`~slimta.edge.EdgeServer.handle`, reads
        the proxy protocol header, and then resumes the original call.

        """
        try:
            initial = self.__read_pp_initial(sock)
            if initial.startswith(b'PROXY '):
                src_addr, _ = ProxyProtocolV1.process_pp_v1(sock, initial)
            elif initial == b'\r\n\r\n\x00\r\nQ':
                src_addr, _ = ProxyProtocolV2.process_pp_v2(sock, initial)
            else:
                raise AssertionError('Invalid proxy protocol signature')
        except LocalConnection:
            log.proxyproto_local(sock)
            return
        except AssertionError as exc:
            log.proxyproto_invalid(sock, exc)
            src_addr = invalid_pp_source_address
        else:
            log.proxyproto_success(sock, src_addr)
        return super(ProxyProtocol, self).handle(sock, src_addr)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
