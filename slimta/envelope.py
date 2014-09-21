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
import cStringIO
from email.message import Message
from email.generator import Generator
from email.parser import Parser, FeedParser

__all__ = ['Envelope']

_HEADER_BOUNDARY = re.compile(r'\r?\n\s*?\n')
_LINE_BREAK = re.compile(r'\r?\n')


class Envelope(object):
    """Class containing message data and metadata. This class acts like an
    envelope with the sending address, recipient(s), and the actual message.

    :param sender: The address that sent the message.
    :param recipients: List of addresses to receive the message.
    :param headers: The message headers.
    :type headers: :class:`email.message.Message`
    :param message: String containing the message contents after the headers.

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

        #: String of message data, not including headers.
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

        :returns: Tuple of two strings: ``(header_data, message_data)``

        """
        outfp = cStringIO.StringIO()
        Generator(outfp).flatten(self.headers, False)
        header_data = re.sub(_LINE_BREAK, '\r\n', outfp.getvalue())
        return header_data, self.message

    def _encode_parts(self, header_data, msg_data, encoder):
        """Encodes any MIME part in the current message that is 8-bit."""
        self.headers = None
        self.message = None

        parser = FeedParser()
        parser.feed(header_data)
        parser.feed(msg_data)
        msg = parser.close()

        for part in msg.walk():
            if not part.is_multipart():
                payload = part.get_payload()
                try:
                    payload.encode('ascii')
                except UnicodeDecodeError:
                    del part['Content-Transfer-Encoding']
                    encoder(part)

        self.parse(msg)

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
        header_data, msg_data = self.flatten()
        try:
            msg_data.encode('ascii')
        except UnicodeDecodeError:
            if not encoder:
                raise
            self._encode_parts(header_data, msg_data, encoder)

    def parse(self, data):
        """Parses the given string or :class:`~email.message.Message` to
        populate the :attr:`headers` and :attr:`message` attributes.

        :param data: The complete message, headers and message body.
        :type data: :py:obj:`str` or :class:`~email.message.Message`

        """
        if isinstance(data, Message):
            outfp = cStringIO.StringIO()
            Generator(outfp).flatten(data, False)
            data = outfp.getvalue()
        match = re.search(_HEADER_BOUNDARY, data)
        if not match:
            header_data = data
            payload = ''
        else:
            header_data = data[:match.end(0)]
            payload = data[match.end(0):]
        self.headers = Parser().parsestr(header_data, True)
        self.message = self.headers.get_payload() + payload
        self.headers.set_payload('')

    def __repr__(self):
        template = '<Envelope at {0}, sender={1!r}>'
        return template.format(hex(id(self)), self.sender)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
