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

"""Implements slimta lookup against a series of regular expressions."""

from __future__ import absolute_import

import re

from . import LookupBase

__all__ = ['RegexLookup']


class RegexLookup(LookupBase):
    """Instantiate this class without any mappings. This object may be used as
    a slimta lookup interface.

    :param str_template: This template string is used to determine the string
                         to match against the regular expressions. The
                         :py:meth:`str.format` method is called with keyword
                         arguments, given the keyword arguments passed in to
                         :meth:`.lookup`.
    :type str_template: str

    """

    def __init__(self, str_template):
        super(RegexLookup, self).__init__()
        self.str_template = str_template
        self.regexes = []

    def add_regex(self, pattern, value):
        """Adds a regular expression with the associated value.

        :param pattern: Pattern to check the lookup string against.
        :type pattern: :py:obj:`str` or :class:`re.RegexObject`
        :param value: The value to return on successful lookup.

        """
        self.regexes.append((re.compile(pattern), value))

    def lookup(self, **kwargs):
        ret = None
        try:
            lookup_str = self.str_template.format(**kwargs)
        except KeyError:
            pass
        else:
            for regex, value in self.regexes:
                match = regex.match(lookup_str)
                if match:
                    ret = value
                    break
        self.log(__name__, kwargs, ret)
        return ret


# vim:et:fdm=marker:sts=4:sw=4:ts=4
