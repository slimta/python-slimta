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

"""Module defining :class:`Envelope` for holding message data along with
metadata.

"""

from __future__ import absolute_import

import re
import copy
from io import BytesIO

try:
    from email.parser import BytesParser
    from email.generator import BytesGenerator
    from email.policy import SMTP
except ImportError:
    from email.parser import Parser
    from email.generator import Generator

from slimta.util import pycompat

__all__ = ['Envelope']

_HEADER_BOUNDARY = re.compile(br'\r?\n\s*?\n')
_LINE_BREAK = re.compile(br'\r?\n')


class Envelope(object):
    """Class containing message data and metadata. This class acts like an
    envelope with the sending address, recipient(s), and the actual message.

    :param sender: The address that sent the message.
    :param recipients: List of addresses to receive the message.
    :param headers: The message headers.
    :type headers: :class:`email.message.Message`
    :param message: String containing the message contents after the headers.
    :type message: :py:obj:`bytes`

    """

    def __init__(self, sender=None, recipients=None,
                 headers=None, message=None):
        #: Sending address of the message.
        self.sender = sender

        #: List of recipient addresses of the message.
        self.recipients = recipients or []

        #: :class:`email.message.Message` object for accessing and modifying
        #: message headers.
        self.headers = headers

        #: Bytestring of message data, not including headers.
        self.message = message

        #: Dictionary of information about the client that sent the message.
        #: Utilized keys include:
        #:
        #: - ``ip``: The IP of the client.
        #: - ``host``: The reverse-lookup of the client IP.
        #: - ``name``: The client name, as given by its ``EHLO`` or
        #:             alternative.
        #: - ``protocol``: The protocol used by the client, generally a variant
        #:                 of ``"SMTP"``.
        #: - ``auth``: The name the client successfully authenticated with, or
        #:             ``None``.
        self.client = {}

        #: Hostname of the :mod:`slimta` server that received the message.
        self.receiver = None

        #: Timestamp when the message was received.
        self.timestamp = None

    def _parse_data(self, data, *extra):
        if pycompat.PY3:
            return BytesParser(policy=SMTP).parse(BytesIO(data), *extra)
        else:
            return Parser().parse(BytesIO(data), *extra)

    def _msg_generator(self, msg):
        outfp = BytesIO()
        if pycompat.PY3:
            BytesGenerator(outfp, policy=SMTP).flatten(msg, False)
            return outfp.getvalue()
        else:
            Generator(outfp).flatten(msg, False)
            return re.sub(_LINE_BREAK, b'\r\n', outfp.getvalue())

    def _merge_payloads(self, headers, payload):
        if headers.get_payload():
            new_msg = copy.deepcopy(headers)
            headers.set_payload('')
            for header in new_msg.keys():
                del new_msg[header]
            return self._msg_generator(new_msg).lstrip(b'\r\n') + payload
        else:
            return payload

    def prepend_header(self, name, value):
        """This method allows prepending a header to the message. The
        :attr:`.headers` object does not directly support header prepending
        because the Python implementation only provides appending.

        """
        self.headers._headers.insert(0, (name, value))

    def copy(self, new_rcpts=None):
        """Builds and returns an exact copy if the current object. This method
        uses a deep-copying so internal datastructures are not shared.

        :param new_rcpts: If given, overwrite the :attr:`.recipients` list with
                          this value inthe new object.
        :returns: An exact, deep copy of the current object.

        """
        new_env = copy.deepcopy(self)
        if new_rcpts:
            new_env.recipients = new_rcpts
        return new_env

    def flatten(self):
        """Produces two strings representing the headers and message body.

        :returns: Tuple of two bytestrings: ``(header_data, message_data)``

        """
        header_data = self._msg_generator(self.headers)
        return header_data, self.message

    def _encode_parts(self, encoder):
        header_data, msg_data = self.flatten()
        msg = self._parse_data(header_data + msg_data)

        for part in msg.walk():
            if not part.is_multipart():
                payload = part.get_payload()
                try:
                    payload.encode('ascii')
                except UnicodeError:
                    del part['Content-Transfer-Encoding']
                    encoder(part)

        self.parse_msg(msg)

    def encode_7bit(self, encoder=None):
        """.. versionadded:: 0.3.12

        Forces the message into 7-bit encoding such that it can be sent to SMTP
        servers that do not support the ``8BITMIME`` extension.

        If the ``encoder`` function is not given, this function is relatively
        cheap and will just check the message body for 8-bit characters
        (raising :py:exc:`UnicodeDecodeError` if any are found).  Otherwise,
        this method can be very expensive. It will parse the entire message
        into MIME parts in order to encode parts that are not 7-bit.

        :param encoder: Optional function from :mod:`email.encoders` used to
                        encode MIME parts that are not 7-bit.
        :raises: UnicodeDecodeError

        """
        try:
            self.message.decode('ascii')
        except UnicodeDecodeError:
            if not encoder:
                raise
            self._encode_parts(encoder)

    def parse_msg(self, msg):
        """Parses the given :class:`~email.message.Message` to
        populate the :attr:`headers` and :attr:`message` attributes.

        :param data: The complete message, headers and message body.
        :type data: :class:`~email.message.Message`

        """
        self.parse(self._msg_generator(msg))

    def parse(self, data):
        """Parses the given string to populate the :attr:`headers` and
        :attr:`message` attributes.

        :param data: The complete message, headers and message body.
        :type data: :py:obj:`bytes`

        """
        match = re.search(_HEADER_BOUNDARY, data)
        if not match:
            header_data = data
            payload = b''
        else:
            header_data = data[:match.end(0)]
            payload = data[match.end(0):]

        self.headers = self._parse_data(header_data, True)
        self.message = self._merge_payloads(self.headers, payload)

    def __repr__(self):
        template = '<Envelope at {0}, sender={1!r}>'
        return template.format(hex(id(self)), self.sender)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
