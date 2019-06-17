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

"""Module containing several |QueuePolicy| implementations for handling the
standard RFC headers.

"""

from __future__ import absolute_import

import uuid
from time import strftime, gmtime, localtime
from math import floor
from socket import getfqdn
import logging

import slimta.logging
from slimta.core import __version__ as VERSION
from . import QueuePolicy
try:
    from dkim import dkim_sign, DKIMException
except ModuleNotFoundError:
    dkim_sign = None


__all__ = ['AddDateHeader', 'AddMessageIdHeader', 'AddReceivedHeader', 'AddDKIMHeader']


class AddDateHeader(QueuePolicy):
    """Checks for the existence of the RFC-specified ``Date`` header, adding it
    if it does not exist.

    """

    def __init__(self):
        pass

    def build_date(self, timestamp):
        """Returns a date string in the format desired for the header. This
        method can be overridden to control the format.

        :param timestamp: Timestamp (as returned by :func:`time.time()`) to
                          convert into date string.
        :returns: Date string for the header.

        """
        return strftime('%a, %d %b %Y %H:%M:%S %Z', localtime(timestamp))

    def apply(self, envelope):
        if 'date' not in envelope.headers:
            envelope.headers['Date'] = self.build_date(envelope.timestamp)


class AddMessageIdHeader(QueuePolicy):
    """Checks for the existence of the RFC-specified ``Message-Id`` header,
    adding it if it does not exist.

    :param hostname: The hostname to use in the generated headers. By default,
                     :func:`~gevent.socket.getfqdn()` is used.

    """

    def __init__(self, hostname=None):
        self.hostname = hostname or getfqdn()

    def apply(self, envelope):
        if 'message-id' not in envelope.headers:
            mid = '<{0}.{1:.0f}@{2}>'.format(uuid.uuid4().hex,
                                             floor(envelope.timestamp),
                                             self.hostname)
            envelope.headers['Message-Id'] = mid


class AddReceivedHeader(QueuePolicy):
    """Adds the RFC-specified ``Received`` header to the message. This header
    should be added for every hop from a message's origination to its
    destination.

    The format of this header is unusual, here is a good description:
    http://cr.yp.to/immhf/envelope.html

    """

    def __init__(self, date_format='%a, %d %b %Y %H:%M:%S +0000'):
        self.date_format = date_format

    def _build_from_section(self, envelope, parts):
        template = 'from {0} ({1} [{2}])'
        ehlo = envelope.client.get('name', None) or 'unknown'
        host = envelope.client.get('host', None) or 'unknown'
        ip = envelope.client.get('ip', None) or 'unknown'
        parts.append(template.format(ehlo, host, ip))

    def _build_by_section(self, envelope, parts):
        template = 'by {0} (slimta {1})'
        parts.append(template.format(envelope.receiver, VERSION))

    def _build_with_section(self, envelope, parts):
        template = 'with {0}'
        protocol = envelope.client.get('protocol', None)
        if protocol:
            parts.append(template.format(protocol))

    def _build_for_section(self, envelope, parts):
        template = 'for <{0}>'
        rcpts = '>,<'.join(envelope.recipients)
        parts.append(template.format(rcpts))

    def apply(self, envelope):
        parts = []
        self._build_from_section(envelope, parts)
        self._build_by_section(envelope, parts)
        self._build_with_section(envelope, parts)
        self._build_for_section(envelope, parts)

        t = gmtime(envelope.timestamp)
        date = strftime(self.date_format, t)

        data = ' '.join(parts) + '; ' + date

        envelope.prepend_header('Received', data)


class AddDKIMHeader(QueuePolicy):
    """Adds a Domain Key Identified Mail header
       will by default sign all the headers (except the ones marked
       as SHOULD NOT SIGN as stated in dkimpy doc)
       if this is not the last header added, the following ones
       will not be signed.
       :param dkim: Dict of dicts indexed by domain (example.com)
                    - privkey: private key: PEM file loaded in a string
                    - selector: selector setup in DNS for the domain
                    - signature_algorithm: (default rsa-sha256)
                    - include-headers: headers to sign (by default, all
                    except the ones marked as SHOULD NOT SIGN see
                    dkimpy doc)
       Refs:
       https://www.dkim.org
       https://gathman.org/pydkim/
       https://launchpad.net/dkimpy
    """

    def __init__(self, dkim):
        if not dkim_sign:
            raise ImportError('dkimpy is not installed')
        self.dkim = dkim
        self.logger = logging.getLogger(__name__)

    def apply(self, envelope):
        h, m = envelope.flatten()
        wm = h + m
        dom = envelope.sender
        if not '@' in dom:
            slimta.logging.logline(self.logger.error, __name__, id(self),
                    'DKIM: invalid sender', **dict(sender=envelope.sender) )
            return
        dom = dom.split('@')[1]
        if dom not in self.dkim:
            slimta.logging.logline(self.logger.debug, __name__, id(self),
                    "DKIM: domain :'" + dom + "' is not setup, ignore")
            return
        domk = self.dkim[dom]
        pk = domk['privkey'].encode('utf-8')
        sel = domk['selector'].encode('utf-8')
        algo = domk['signature_algorithm'] or 'rsa-sha256'
        algo = algo.encode('utf-8')
        flds = domk['include_headers']
        if flds: flds = [x.encode('utf-8') for x in flds]
        dom = dom.encode('utf-8')
        try:
            hd = dkim_sign(message=wm, selector=sel, domain=dom, privkey=pk,
                    signature_algorithm=algo, include_headers=flds)
        except DKIMException as e:
            slimta.logging.logline(self.logger.error, __name__, id(self),
                    'DKIM: exception:' + str(e),
                    **dict(sender=envelope.sender,domain=dom) )
            return
        data = hd.replace(b'\r\n',b'').decode('utf-8').split(':',1)[1]
        envelope.prepend_header('DKIM-Signature', data)  # RFC 6376 par. 5.6


# vim:et:fdm=marker:sts=4:sw=4:ts=4
