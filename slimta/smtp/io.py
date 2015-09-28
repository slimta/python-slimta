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

from __future__ import absolute_import

import re
import cStringIO
from socket import error as socket_error
from errno import ECONNRESET, EPIPE

from gevent.ssl import SSLSocket, SSLError
from gevent import socket

from slimta import logging
from . import ConnectionLost, BadReply
from .reply import Reply

__all__ = ['IO']

line_pattern = re.compile(r'(.*?)\r?\n')
reply_line_pattern = re.compile(r'((\d\d\d)([ \t-])(.*?))\r?\n')
command_pattern = re.compile(r'^([a-zA-Z]+)\s*$')
command_arg_pattern = re.compile(r'^([a-zA-Z]+)\s+(.+?)\s*$')

log = logging.getSocketLogger(__name__)


class IO(object):

    def __init__(self, socket, tls_wrapper=None):
        self.socket = socket
        if tls_wrapper:
            self._tls_wrapper = tls_wrapper

        self.send_buffer = cStringIO.StringIO()
        self.recv_buffer = ''

    @property
    def encrypted(self):
        return isinstance(self.socket, SSLSocket)

    def close(self):
        log.close(self.socket)
        if self.encrypted:
            try:
                self.socket.unwrap()
            except socket_error as (errno, message):
                if errno not in (0, EPIPE, ECONNRESET):
                    raise
        self.socket.close()

    def raw_send(self, data):
        try:
            self.socket.sendall(data)
        except socket_error as (errno, message):
            if errno == ECONNRESET:
                raise ConnectionLost()
            raise
        log.send(self.socket, data)

    def raw_recv(self):
        try:
            data = self.socket.recv(4096)
        except socket_error as (errno, message):
            if errno == ECONNRESET:
                raise ConnectionLost()
            raise
        log.recv(self.socket, data)
        if data == '':
            raise ConnectionLost()
        return data

    def _tls_wrapper(self, socket, tls):
        sslsock = SSLSocket(socket, **tls)
        sslsock.do_handshake()
        return sslsock

    def encrypt_socket(self, tls):
        log.encrypt(self.socket, tls)
        try:
            self.socket = self._tls_wrapper(self.socket, tls)
            return True
        except SSLError:
            return False

    def buffered_recv(self):
        received = self.raw_recv()
        self.recv_buffer += received

    def buffered_send(self, data):
        self.send_buffer.write(data)

    def flush_send(self):
        send = self.send_buffer.getvalue()
        if send == '':
            return
        self.raw_send(send)
        self.send_buffer = cStringIO.StringIO()

    def recv_reply(self):
        code = None
        message_lines = []
        incomplete = True
        input = self.recv_buffer

        while incomplete:
            start_i = 0
            while start_i is not None:
                match = reply_line_pattern.match(input, start_i)
                if match:
                    if code and code != match.group(2):
                        raise BadReply(match.group(1))
                    code = match.group(2)
                    message_lines.append(match.group(4))
                    self.recv_buffer = input[match.end(0):]

                    if match.group(3) != '-':
                        incomplete = False
                        start_i = None
                    else:
                        start_i = match.end(0)
                else:
                    match = line_pattern.match(input, start_i)
                    if match:
                        self.recv_buffer = input[match.end(0):]
                        message_lines.append(match.group(1))
                        raise BadReply('\r\n'.join(message_lines))
                    else:
                        start_i = None

            if incomplete:
                self.buffered_recv()
                input = self.recv_buffer

        return code, '\r\n'.join(message_lines)

    def recv_line(self):
        while True:
            input = self.recv_buffer
            match = line_pattern.match(input)
            if match:
                self.recv_buffer = input[match.end(0):]
                return match.group(1)
            self.buffered_recv()

    def recv_command(self):
        line = self.recv_line()
        match = command_pattern.match(line)
        if match:
            return match.group(1).upper(), None
        match = command_arg_pattern.match(line)
        if match:
            return match.group(1).upper(), match.group(2)
        return None, None

    def send_reply(self, reply):
        code, message = reply.code, reply.message
        lines = []
        message = message+'\r\n'
        for match in line_pattern.finditer(message):
            lines.append(match.group(1))

        to_send = cStringIO.StringIO()
        for line in lines[:-1]:
            to_send.write(''.join((code, '-', line, '\r\n')))
        to_send.write(''.join((code, ' ', lines[-1], '\r\n')))
        return self.buffered_send(to_send.getvalue())

    def send_command(self, command):
        return self.buffered_send(command+'\r\n')


# vim:et:fdm=marker:sts=4:sw=4:ts=4
