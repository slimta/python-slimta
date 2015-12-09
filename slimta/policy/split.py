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

"""Implements a policy to break down envelopes with multiple recipients into
logical groups. This is useful for relayers that may not handle multi-recipient
messages well, such as :class:`~slimta.relay.smtp.mx.MxSmtpRelay`.

"""

from __future__ import absolute_import

from collections import OrderedDict

from . import QueuePolicy

__all__ = ['RecipientSplit', 'RecipientDomainSplit']


class RecipientSplit(QueuePolicy):
    """If a given |Envelope| has more than one recipient, this policy splits
    it, generating a list of new :class:`Envelope` object copies where each has
    only one recipient. Each new object has its own copy of
    :attr:`~slimta.envelope.Envelope.headers`, but other attributes may be
    shared between each new instance.

    """

    def apply(self, envelope):
        if len(envelope.recipients) <= 1:
            return
        ret = []
        for rcpt in envelope.recipients:
            new_env = envelope.copy([rcpt])
            ret.append(new_env)
        return ret


class RecipientDomainSplit(QueuePolicy):
    """If a given |Envelope| recipients of more than one unique domain (case-
    insensitive), this policy splits it generating a list of new
    :class:`Envelope` object copies where each has only one recipient. Each new
    object has its own copy of :attr:`~slimta.envelope.Envelope.headers`, but
    other attributes may be shared between each new instance.

    Any recipient in the original |Envelope| that does not have a domain (and
    thus is not a valid email address) will be given an |Envelope| of its own.

    """

    def _get_domain(self, rcpt):
        localpart, domain = rcpt.rsplit('@', 1)
        if not domain:
            raise ValueError(rcpt)
        return domain.lower()

    def _get_domain_groups(self, recipients):
        groups = OrderedDict()
        bad_rcpts = []
        for rcpt in recipients:
            try:
                domain = self._get_domain(rcpt)
            except ValueError:
                bad_rcpts.append(rcpt)
            else:
                groups.setdefault(domain, []).append(rcpt)
        return groups, bad_rcpts

    def _append_envelope_copy(self, envelope, copies, rcpts):
        new_env = envelope.copy(rcpts)
        copies.append(new_env)

    def apply(self, envelope):
        groups, bad_rcpts = self._get_domain_groups(envelope.recipients)
        if len(groups)+len(bad_rcpts) <= 1:
            return
        ret = []
        for domain, rcpts in groups.items():
            self._append_envelope_copy(envelope, ret, rcpts)
        for bad_rcpt in bad_rcpts:
            self._append_envelope_copy(envelope, ret, [bad_rcpt])
        return ret


# vim:et:fdm=marker:sts=4:sw=4:ts=4
