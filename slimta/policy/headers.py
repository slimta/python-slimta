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

"""Module containing several |Policy| implementations for handling the standard
RFC headers.

"""

import uuid
from time import strftime, gmtime
from math import floor

from slimta.policy import Policy

__all__ = ['AddDateHeader', 'AddMessageIdHeader', 'AddReceivedHeader']


class AddDateHeader(Policy):
    """Checks for the existence of the RFC-specified ``Date`` header, adding it
    if it does not exist.

    """

    def __init__(self):
        pass

    def build_date(self, time):
        """Returns a date string in the format desired for the header. This
        method can be overridden to control the format.

        :param time: Timestamp (as returned by :func:`time.time()`) to convert
                     into date string.
        :returns: Date string for the header.

        """
        return strftime('%a, %d %b %Y %T %z', time)

    def apply(self, envelope):
        if 'date' not in envelope.headers:
            envelope.headers['Date'] = self.build_date(envelope.timestamp)


class AddMessageIdHeader(Policy):
    """Checks for the existence of the RFC-specified ``Message-Id`` header,
    adding it if it does not exist.

    :param hostname: The hostname to use in the generated headers.

    """

    def __init__(self, hostname):
        self.hostname = hostname

    def apply(self, envelope):
        if 'message-id' not in envelope.headers:
            mid = '<{0}.{1}@{2}>'.format(uuid.uuid4().hex,
                                         floor(envelope.timestamp),
                                         self.hostname)
            envelope.headers['Message-Id'] = mid


class AddReceivedHeader(Policy):
    """Adds the RFC-specified ``Received`` header to the message. This header
    should be added for every hop from a message's origination to its
    destination.

    The format of this header is unusual, here is a good description:
    http://cr.yp.to/immhf/envelope.html

    """

    def __init__(self, date_format='%a, %d %b %Y %H:%M:%S +0000', use_utc=True):
        self.date_format = date_format
        self.use_utc = use_utc

    def _build_from_section(self, envelope, parts):
        template = 'from {0} ({1} [{2}]{3})'
        parts.append(template.format())

    def _build_by_section(self, envelope, parts):
        template = 'by {0} (slimta {1})'
        parts.append(template.format(envelope.receiver, 'x.x.x'))

    def _build_with_section(self, envelope, parts):
        template = 'with {0}'
        parts.append(template.format())

    def _build_id_section(self, envelope, parts):
        template = 'id {0}'
        parts.append(template.format())

    def _build_for_section(self, envelope, parts):
        template = 'for <{0}>'
        rcpts = '>,<'.join(envelope.recipients)
        parts.append(template.format(rcpts))

    def apply(self, envelope):
        parts = []
        self._build_from_section(envelope, parts)
        self._build_by_section(envelope, parts)
        self._build_with_section(envelope, parts)
        self._build_id_section(envelope, parts)
        self._build_for_section(envelope, parts)

        t = gmtime(envelope.timestamp) if self.use_utc else envelope.timestamp
        date = strftime(self.date_format, t)

        data = ' '.join(parts) + '; ' + date
        envelope.headers['Received'] = data


# vim:et:fdm=marker:sts=4:sw=4:ts=4
