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

"""Package containing a |QueuePolicy| for connecting to ``spamd``
(SpamAssassin) and checking if a message is spammy. If used as a
|QueuePolicy|, the header ``X-Spam-Status`` will be ``YES`` if spammy (with
matched symbols in ``X-Spam-Symbols``).

"""

from __future__ import absolute_import

import re
from io import BytesIO

from gevent import Timeout
from gevent.socket import create_connection, SHUT_WR

from slimta import logging
from slimta.envelope import Envelope
from . import PolicyError, QueuePolicy

__all__ = ['SpamAssassinError', 'SpamAssassin']

log = logging.getSocketLogger(__name__)

first_line_pattern = re.compile(br'^SPAMD/[^ ]+ 0 EX_OK$')
spammy_pattern = re.compile(br'^Spam: ([^ ]+)', re.MULTILINE)
divider_pattern = re.compile(br'^(.*?)\r?\n(.*?)\r?\n\r?\n', re.DOTALL)
symbols_pattern = re.compile(br'[^\s,]+')


class SpamAssassinError(PolicyError):
    """This exception occurs when malformed or error data was received
    from the SpamAssassin server. This means the server is broken or
    misconfigured, it does not imply the message is spammy or clean.

    """

    def __init__(self):
        msg = 'Error scanning message'
        super(SpamAssassinError, self).__init__(msg)


class SpamAssassin(QueuePolicy):
    """Queries ``spamd`` to check if a given message is spammy.

    :param address: Address tuple of the spamd server, defaults to
                    ``('localhost', 783)``.
    :param timeout: Timeout to use while waiting for spamd response.

    """

    SPAMC_USER = b'slimta'
    SPAMC_PROTOCOL_VER = b'1.1'

    def __init__(self, address=None, timeout=None, socket_creator=None):
        self.address = address or ('127.0.0.1', 783)
        self.timeout = timeout
        self._socket_creator = socket_creator or create_connection

    def _build_request_str(self, header_data, message_data):
        reqfp = BytesIO()
        data_len = str(len(header_data) + len(message_data)).encode()
        reqfp.write(b'SYMBOLS SPAMC/' + self.SPAMC_PROTOCOL_VER + b'\r\n')
        reqfp.write(b'Content-Length: ' + data_len + b'\r\n')
        reqfp.write(b'User: ' + self.SPAMC_USER + b'\r\n\r\n')
        reqfp.write(header_data)
        reqfp.write(message_data)
        return reqfp.getvalue()

    def _send_request(self, socket, header_data, message_data):
        request_str = self._build_request_str(header_data, message_data)
        socket.sendall(request_str)
        log.send(socket, request_str)
        socket.shutdown(SHUT_WR)
        log.shutdown(socket, SHUT_WR)

    def _recv_all(self, socket):
        resfp = BytesIO()
        with Timeout(self.timeout):
            while True:
                data = socket.recv(4096)
                log.recv(socket, data)
                if data == b'':
                    break
                resfp.write(data)
        response = resfp.getvalue()
        match = divider_pattern.match(response)
        if not match:
            raise SpamAssassinError()
        first_line = match.group(1)
        headers = match.group(2)
        after = response[match.end(0):]
        return first_line, headers, after

    def _recv_response(self, socket):
        first_line, headers, body = self._recv_all(socket)
        symbols = [s.decode('ascii') for s in symbols_pattern.findall(body)]
        match = first_line_pattern.match(first_line)
        if not match:
            raise SpamAssassinError()
        spammy = False
        match = spammy_pattern.search(headers)
        if match and match.group(1) == b'True':
            spammy = True
        return spammy, symbols

    def scan(self, message):
        """Convenience method that scans a message and returns the results,
        without adding the spam headers.

        :param message: Message to scan.
        :type message: :py:obj:`bytes` or :class:`~slimta.envelope.Envelope`
        :returns: Tuple of a spammy boolean followed by a list of the symbols
                  matched in the scan.

        """

        if isinstance(message, Envelope):
            header_data, message_data = message.flatten()
        else:
            header_data = b''
            message_data = message
        socket = None
        try:
            socket = self._socket_creator(self.address)
            log.connect(socket, self.address)
            self._send_request(socket, header_data, message_data)
            return self._recv_response(socket)
        finally:
            if socket:
                log.close(socket)
                socket.close()

    def apply(self, envelope):
        spammy, symbols = self.scan(envelope)
        del envelope.headers['X-Spam-Status']
        if spammy:
            envelope.headers['X-Spam-Status'] = 'YES'
            envelope.headers['X-Spam-Symbols'] = ', '.join(symbols)
        else:
            envelope.headers['X-Spam-Status'] = 'NO'


# vim:et:fdm=marker:sts=4:sw=4:ts=4
