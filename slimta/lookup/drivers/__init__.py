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

"""This package contains several implementations of the slimta lookup
mechanism, which provides a simple interface to control actions and policies
with external lookups. Under normal circumstances, slimta lookup drivers do
not modify their backend data source.

"""

from __future__ import absolute_import

import logging

from ...logging.log import logline

__all__ = ['LookupBase']


class LookupBase(object):
    """Inherit this class to implement a slimta lookup driver. Only the
    :meth:`.lookup` method must be overridden.

    """

    def _format_key(self, key_template, kwargs):
        kwargs = kwargs.copy()
        while True:
            try:
                return key_template.format(**kwargs)
            except KeyError as exc:
                key = exc.args[0]
                kwargs[key] = '{'+key+'}'

    def lookup(self, **kwargs):
        """The keyword arguments will be used by the lookup driver to return a
        dictionary-like object that will be used to affect actions or policy.
        For some drivers, these keywords may be used with a template to produce
        a lookup key. For SQL-style drivers, they might be used in a ``WHERE``
        clause of a ``SELECT`` query.

        :param kwargs: Used by the driver to lookup records.
        :type kwargs: keyword arguments
        :returns: A dictionary if a record was found, ``None`` otherwise.

        """
        raise NotImplementedError()

    def lookup_address(self, address, **extra):
        """A convenience method where the given address is passed in as the
        ``address`` keyword to :meth:`.lookup`. If the address has domain part,
        it is substringed and passed in as the ``domain`` keyword a well.

        :param address: An address to lookup, either as the full address or as
                        its domain part.
        :type address: str
        :param extra: Additional keyword arguments to pass in to
                      :meth:`.lookup`.
        :type extra: keyword arguments

        """
        if '@' in address:
            domain = address.rsplit('@', 1)[1]
            return self.lookup(address=address, domain=domain, **extra)
        return self.lookup(address=address, **extra)

    def log(self, name, kwargs, ret):
        """Implementing drivers should call this method to log the lookup
        transaction.

        :param name: The module name, e.g. ``__name__``.
        :type name: str
        :param kwargs: The keyword arguments given to :meth:`.lookup`.
        :type kwargs: dict
        :param ret: The return value of the lookup, e.g. a dictionary or
                    ``None``.

        """
        logger = logging.getLogger(name)
        operation = 'notfound' if ret is None else 'found'
        logline(logger.debug, 'lookup', id(self), operation, **kwargs)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
