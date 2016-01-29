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

from __future__ import absolute_import, unicode_literals

import re
import copy
from email.message import Message
from email.generator import Generator

import six
from six.moves import cStringIO

try:
    from email.parser import BytesParser
    from email.generator import BytesGenerator
except ImportError:
    from email.generator import Generator as BytesGenerator

from slimta.util.typecheck import check_argtype
from slimta.util.encoders import utf8only_encode, utf8only_decode
from slimta.util.parser import Parser


__all__ = ['Envelope']

_HEADER_BOUNDARY = re.compile(br'\r?\n\s*?\n')
_LINE_BREAK = re.compile(r'\r?\n')


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

        #: String of message data, not including headers.
        check_argtype(message, bytes, 'message', or_none=True)
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
        outfp = cStringIO()
        Generator(outfp).flatten(self.headers, False)
        header_data = re.sub(_LINE_BREAK, '\r\n', outfp.getvalue())
        return header_data, self.message

    def _encode_parts(self, header_data, msg_data, encoder):
        """Encodes any MIME part in the current message that is 8-bit.

        :type header_data: :py:obj:`bytes`
        :type msg_data: :py:obj:`bytes`
        """
        self.headers = None
        self.message = None

        if six.PY3:
            msg = BytesParser().parsebytes(header_data+msg_data)

        else:
            msg = Parser().parsestr(header_data+msg_data)

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
        header_data, msg_data = self.flatten()
        # header data may contain ascii chars, even if RFCs disallow it
        # excepted with SMTPUTF8 extension. Some MTA work like that.
        encoded_header_data = utf8only_encode(header_data)
        try:
            msg_data.decode('ascii')
        except UnicodeError:
            if not encoder:
                raise
            self._encode_parts(encoded_header_data, msg_data, encoder)

    def parse_msg(self, msg):
        """Parses the given :class:`~email.message.Message` to
        populate the :attr:`headers` and :attr:`message` attributes.

        :param data: The complete message, headers and message body.
        :type data: :class:`~email.message.Message`

        """
        # Can't use non-six BytesIO here cause python2 BytesGenerator will fail
        # to decode headers
        outfp = six.BytesIO()
        BytesGenerator(outfp).flatten(msg, False)
        data = outfp.getvalue()

        if six.PY2:
            data = data.encode()

        self.parse(data)

    def parse(self, data):
        """Parses the given string to populate the :attr:`headers` and
        :attr:`message` attributes.

        :param data: The complete message, headers and message body.
        :type data: :py:obj:`bytes`

        """
        check_argtype(data, bytes, 'data')

        match = re.search(_HEADER_BOUNDARY, data)
        if not match:
            header_data = data
            payload = b''
        else:
            header_data = data[:match.end(0)]
            payload = data[match.end(0):]

        header_data_decoded = utf8only_decode(header_data)
        self.headers = Parser().parsestr(header_data_decoded, True)
        self.message = self.headers.get_payload().encode('ascii') + payload
        self.headers.set_payload('')

    def __repr__(self):
        template = '<Envelope at {0}, sender={1!r}>'
        return template.format(hex(id(self)), self.sender)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
