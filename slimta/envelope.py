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

import re
import copy
import cStringIO
import email.generator
import email.parser

__all__ = ['Envelope']

header_boundary = re.compile(r'\r?\n\r?\n')


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

        #: Information about the client that sent the message. Utilized keys
        #: include:
        #:
        #: * ``ip``: The IP of the client.
        #: * ``host``: The reverse-lookup of the client IP.
        #: * ``name``: The client name, as given by its ``EHLO`` or alternative.
        #: * ``protocol``: The protocol used by the client, generally a variant
        #:                 of ``"SMTP"``.
        #: * ``auth``: The name the client successfully authenticated with, or
        #:             ``None``.
        self.client = {}

        #: Hostname of the :mod:`slimta` server that received the message. 
        self.receiver = None

        #: Timestamp when the message was received.
        self.timestamp = None

    def split(self):
        """Splits by recipient, returning a list of new :class:`Envelope`
        object copies where each has only one recipient. Each new object has
        its own copy of :attr:`headers`, but other attributes may be shared
        between each new instance.

        :returns: List of :class:`Envelope` objects, one for each recipient
                  in the :attr:`recipients` of the current :class:`Envelope`.

        """
        ret = []
        for rcpt in self.recipients:
            new_env = copy.copy(self)
            new_env.recipients = [rcpt]
            new_env.headers = copy.deepcopy(self.headers)
            ret.append(new_env)
        return ret

    def flatten(self):
        """Produces two strings representing the headers and message body.

        :returns: Tuple of two strings: ``(header_data, message_data)``

        """
        outfp = cStringIO.StringIO()
        email.generator.Generator(outfp).flatten(self.headers, False)
        header_data = outfp.getvalue().replace('\r', '').replace('\n', '\r\n')
        return header_data, self.message

    def parse(self, data):
        """Parses the given string to populate the :attr:`headers` and
        :attr:`message` attributes.

        :param data: The complete message, headers and message body.
        :type data: string

        """
        match = header_boundary.search(data)
        if not match:
            header_data = data
            payload = ''
        else:
            header_data = data[:match.end(0)]
            payload = data[match.end(0):]
        headers = email.parser.Parser().parsestr(header_data, True)
        self.headers = headers
        self.message = payload


# vim:et:fdm=marker:sts=4:sw=4:ts=4
