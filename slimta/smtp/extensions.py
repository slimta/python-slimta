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

"""Manages the SMTP extensions offered by a server or available to a client."""

from __future__ import absolute_import

import re

__all__ = ['Extensions']

parse_pattern = re.compile(r'^\s*([a-zA-Z0-9][a-zA-Z0-9-]*)\s*(.*?)\s*$')
line_pattern = re.compile(r'(.*?)\r?\n')


class Extensions(object):
    """Class that simplifies the usage of SMTP extensions. Along with an
    extension, a simple string parameter can be stored if necessary.

    """

    def __init__(self):
        self.extensions = {}

    def reset(self):
        """Removes all known extensions."""
        self.extensions = {}

    def __contains__(self, ext):
        """Checks if the given extension is in the known extensions. This is
        especially useful for clients to check if a server offers a certain
        desired extension, e.g. ``if 'AUTH' in extensions:``.

        :param ext: The extension to check for, case-insensitive.
        :rtype: True or False

        """
        return ext.upper() in self.extensions

    def getparam(self, ext, filter=None):
        """Gets the parameter associated with an extension.

        :param ext: The extension to get the parameter for.
        :param filter: An optional filter function to modify the returned
                       parameter, if it exists, e.g. :func:`int()`.
        :returns: Returns None if the extension doesn't exist, the extension
                  doesn't have a parameter, or the filter function raises
                  :class:`ValueEror`.

        """
        try:
            param = self.extensions[ext.upper()]
        except KeyError:
            return None
        if filter:
            try:
                return filter(param)
            except ValueError:
                return None
        else:
            return param

    def add(self, ext, param=None):
        """Adds a new supported extension. This is useful for servers to
        advertise their offered extensions.

        :param ext: The extension name, which will be upper-cased.
        :param param: Optional parameter string associated with the extension.

        """
        self.extensions[ext.upper()] = param

    def drop(self, ext):
        """Drops the given extension, if it exists.

        :param ext: The extension name.
        :returns: True if the extension existed, False otherwise.

        """
        try:
            del self.extensions[ext.upper()]
            return True
        except KeyError:
            return False

    def parse_string(self, string):
        """Parses a string as returned by the EHLO command and adds all
        discovered extensions. This string should *not* have the response code
        prefixed to its lines.

        :param string: The string to parse.
        :returns: The first line of the string, which will be a free-form
                  message response to the EHLO command.

        """
        header = None
        string += '\r\n'
        for match in line_pattern.finditer(string):
            if not header:
                header = match.group(1)
            else:
                ext_match = parse_pattern.match(match.group(1))
                if ext_match:
                    arg = ext_match.group(2)
                    if arg:
                        self.add(ext_match.group(1), ext_match.group(2))
                    else:
                        self.add(ext_match.group(1))
        return header or string

    def build_string(self, header):
        """Converts the object into a string that can be sent with the response
        to a EHLO command, without the code prefixed to each line.

        :param header: The first line of the resulting string, which can be a
                       free-form message response for the EHLO command.
        :rtype: str

        """
        lines = [header]
        for k, v in self.extensions.iteritems():
            if v:
                try:
                    value_str = str(v)
                except ValueError:
                    pass
                else:
                    lines.append(' '.join((k, value_str)))
            else:
                lines.append(k)
        return '\r\n'.join(lines)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
