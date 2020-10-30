# Copyright (c) 2014 Ian C. Good
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

"""Provides an implementation of the |QueuePolicy| interface that enforces
policies specified in a slimta lookup record.

Currently the following record keys are implemented:

``alias``
  Rewrites the envelope, replacing occurrences of the looked up address with
  the contents of this field.

``add_headers``
  If the contents of this field are a JSON-decodable dictionary, the keys and
  values are prepended to the message as new headers. Existing headers are left
  untouched.

"""

from __future__ import absolute_import

import json

from slimta.policy import QueuePolicy

__all__ = ['LookupPolicy']


class LookupPolicy(QueuePolicy):
    """Instances of this class may be configured to run before a message is
    queued using :meth:`slimta.queue.Queue.add_policy`.

    :param lookup: The slimta lookup driver, implementing the
                   :class:`~slimta.lookup.drivers.LookupBase` interface.
    :param on_sender: If ``True``, the envelope sender is looked up and has
                       policies applied.
    :type on_sender: bool
    :param on_rcpts: If ``True``, the envelope recipients are looked up, each
                     one applying any policies found in the record.
    :type on_rcpts: bool

    """

    def __init__(self, lookup, on_sender=False, on_rcpts=True):
        super(LookupPolicy, self).__init__()
        self.lookup = lookup
        self.on_sender = on_sender
        self.on_rcpts = on_rcpts

    def _add_headers(self, envelope, headers_raw):
        try:
            headers = json.loads(headers_raw)
        except ValueError:
            return
        for key, val in headers.items():
            envelope.prepend_header(key, val)

    def _verp_enc(self, address, on_domain):
        localpart, _, domain = address.rpartition('@')
        if localpart:
            return '{0!s}={1!s}@{2!s}'.format(localpart, domain, on_domain)
        else:
            return '{0!s}@{1!s}'.format(domain, on_domain)

    def _get_alias(self, address, alias):
        localpart, _, domain = address.rpartition('@')
        alias = alias.format(localpart=localpart, domain=domain)
        if '@' in alias:
            return alias
        else:
            if localpart:
                return '{0!s}@{1!s}'.format(localpart, alias)
            else:
                return alias

    def apply(self, envelope):
        if self.on_sender:
            ret = self.lookup.lookup_address(envelope.sender) or {}
            if 'verp' in ret:
                envelope.sender = self._verp_enc(envelope.sender, ret['verp'])
            if 'alias' in ret:
                envelope.sender = self._get_alias(
                        envelope.sender, ret['alias'])
            if 'add_headers' in ret:
                self._add_headers(envelope, ret['add_headers'])
        if self.on_rcpts:
            for i, rcpt in enumerate(envelope.recipients):
                ret = self.lookup.lookup_address(rcpt) or {}
                if 'verp' in ret:
                    envelope.recipients[i] = self._verp_enc(rcpt, ret['verp'])
                if 'alias' in ret:
                    envelope.recipients[i] = self._get_alias(
                            rcpt, ret['alias'])
                if 'add_headers' in ret:
                    self._add_headers(envelope, ret['add_headers'])


# vim:et:fdm=marker:sts=4:sw=4:ts=4
