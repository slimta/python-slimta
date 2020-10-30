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

"""Implements slimta lookup against a standard Python dictionary-like object.
This object should be given pre-populated in the constructor, or be a proxy to
a persistent backend like :py:mod:`shelve`.

"""

from __future__ import absolute_import

from . import LookupBase

__all__ = ['DictLookup']


class DictLookup(LookupBase):
    """Instantiate this class with a Python dictionary-like object and it may
    be used as a slimta lookup interface.

    :param backend: The backend dictionary-like object that will be queried for
                    data lookups. The values in this mapping **must** also be
                    dictionary-like objects.
    :type backend: collections.Mapping
    :param key_template: This template string is used to determine the key
                         string to lookup. The :py:meth:`str.format` method is
                         called with keyword arguments, given the keyword
                         arguments passed in to :meth:`.lookup`.
    :type key_template: str

    """

    def __init__(self, backend, key_template):
        super(DictLookup, self).__init__()
        self.backend = backend
        self.key_template = key_template

    def lookup(self, **kwargs):
        key = self._format_key(self.key_template, kwargs)
        try:
            ret = self.backend[key]
        except KeyError:
            ret = None
        self.log(__name__, kwargs, ret)
        return ret


# vim:et:fdm=marker:sts=4:sw=4:ts=4
