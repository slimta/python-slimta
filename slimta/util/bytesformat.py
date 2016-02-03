# Copyright (c) 2016 Ian C. Good
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

"""Provides a class that is capable of basic bytestring templating, similar to
the :py:func:`str.format` method. This is needed in Python 3 before 3.5+, but
should work in all supported versions.

This class does the heavy lifting (a :py:func:`re.finditer` loop) during
construction, so it is optimal to instantiate it once and then re-use
:meth:`~BytesFormat.format`.

"""

from __future__ import absolute_import

import re

__all__ = ['BytesFormat']


class BytesFormat(object):
    """Wraps a bytestring in a class with a :meth:`.format` method similar to
    :py:func:`str.format`.

    During construction, the template string is scanned for matching ``{...}``
    pairs that contain only characters that match the ``\w`` regular
    expression.  In the :meth:`.format` method, these ``{...}`` are replaced
    with a matching argument's value, if an argument matches, or the action
    specified by ``mode`` happens when it does not match

    To match :meth:`.format` arguments, you may use a positional argument's
    number (e.g.  ``{0}``) or a keyword argument's key (e.g. ``{recipient}``).
    Additional formatting options are not supported.

    :param template: The template bytestring.
    :type template: :py:obj:`bytes`
    :param mode: If ``'ignore'``, any ``{...}`` that does not match a
                 :meth:`.format` argument is left in place as-is. If
                 ``'remove'``, these ``{...}`` are replaced with an empty
                 string. If ``'strict'``, these ``{...}`` will cause
                 :class:`KeyError` or :class:`IndexError` exceptions.

    """

    def __init__(self, template, mode='ignore'):
        super(BytesFormat, self).__init__()
        self.mode = mode
        self.template_parts = []
        self._parse_template(template)

    def _parse_template(self, template):
        last_end = 0
        for match in re.finditer(br'\{(\w+)\}', template):
            if match.start(0) > last_end:
                literal = template[last_end:match.start(0)]
                self.template_parts.append((0, literal))
            last_end = match.end(0)
            self.template_parts.append((1, match.group(1)))
        if len(template) > last_end:
            literal = template[last_end:]
            self.template_parts.append((0, literal))

    def _get_arg(self, value, args, kwargs):
        try:
            index = int(value)
        except ValueError:
            if isinstance(value, bytes):
                value = value.decode('ascii')
            return kwargs[value]
        else:
            return args[index]

    def _format(self, args, kwargs, mode=None):
        mode = mode or self.mode
        ret = []
        for type, value in self.template_parts:
            if type == 0:
                ret.append(value)
            elif type == 1:
                try:
                    result = self._get_arg(value, args, kwargs)
                except (KeyError, IndexError):
                    if mode == 'remove':
                        pass
                    elif mode == 'strict':
                        raise
                    else:
                        ret.append(b'{' + value + b'}')
                else:
                    try:
                        result = bytes(result)
                    except TypeError:
                        result = result.encode('utf-8')
                    ret.append(result)
        return b''.join(ret)

    def format(self, *args, **kwargs):
        """Substitutes in the given positional and keyword arguments into the
        original template string, replacing occurrences of ``{...}`` with the
        correct argument's value.

        :rtype: :py:obj:`bytes`

        """
        return self._format(args, kwargs)

    def __repr__(self):
        return repr(self._format([], {}, mode='ignore'))


# vim:et:fdm=marker:sts=4:sw=4:ts=4
