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

"""Implements a simple forwarding policy, to transform or replace
recipients.

"""

from __future__ import absolute_import

import re

from . import QueuePolicy

__all__ = ['Forward']


class Forward(QueuePolicy):
    """Each |Envelope| recipient is run through :func:`re.sub()` to see if it
    is modified. If a recipient matches a mapping rule, no further mapping
    rules are processed. Mapping rules are checked in the order that they were
    added.

    """

    def __init__(self):
        self.mapping = []

    def add_mapping(self, pattern, repl, count=0):
        """Adds a mapping rule.

        :param pattern: Pattern to check recipient against.
        :type pattern: :py:obj:`str` or :class:`re.RegexObject`
        :param repl: Replacement for ``pattern`` matches, as described by
                     :func:`re.sub()`.
        :type repl: :py:obj:`str` or function
        :param count: Max number of replacements per recipient string.

        """
        self.mapping.append((re.compile(pattern), repl, count))

    def apply(self, envelope):
        n_rcpt = len(envelope.recipients)
        for i in range(n_rcpt):
            old_rcpt = envelope.recipients[i]
            for pattern, repl, count in self.mapping:
                new_rcpt, changes = re.subn(pattern, repl, old_rcpt, count)
                if new_rcpt and changes > 0:
                    envelope.recipients[i] = new_rcpt
                    break


# vim:et:fdm=marker:sts=4:sw=4:ts=4
