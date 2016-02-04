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

"""This module makes compatibility between Python 2 and Python 3 a little more
convenient. It's intended to avoid dependence on the ``six`` library.

"""

from __future__ import absolute_import

import sys

try:
    from urllib import parse as urlparse_mod
    from http import client as httplib_mod
    import reprlib as reprlib_mod
except ImportError:
    import urlparse as urlparse_mod
    import httplib as httplib_mod
    import repr as reprlib_mod

__all__ = ['PY3', 'PY2']

#: True if the interpreter is Python 3.x, False otherwise.
PY3 = (sys.version_info[0] == 3)

#: True if the interpreter is Python 2.x, False otherwise.
PY2 = (sys.version_info[0] == 2)

#: The ``urlparse`` module on Python 2, ``urllib.parse`` on Python 3.
urlparse = urlparse_mod

#: The ``httplib`` module on Python 2, ``http.client`` on Python 3. In Python
#: 2, the deprecated ``strict`` parameter is set to True.
httplib = httplib_mod

#: The ``repr`` module on Python 2, ``reprlib`` on Python 3.
reprlib = reprlib_mod


if sys.version_info < (3, 4):  # pragma: no cover
    orig_HTTPConnection = httplib_mod.HTTPConnection
    orig_HTTPSConnection = httplib_mod.HTTPSConnection

    class _StrictHTTPConnection(orig_HTTPConnection):

        _init_args = ('host', 'port', 'timeout', 'source_address')

        def __init__(self, *args, **kwargs):
            for i, arg in enumerate(args):
                kwargs.setdefault(self._init_args[i], arg)
            kwargs['strict'] = True
            orig_HTTPConnection.__init__(self, **kwargs)

    class _StrictHTTPSConnection(orig_HTTPSConnection):

        _init_args = ('host', 'port', 'key_file', 'cert_file', 'timeout',
                      'source_address', 'context')

        def __init__(self, *args, **kwargs):
            for i, arg in enumerate(args):
                kwargs.setdefault(self._init_args[i], arg)
            kwargs['strict'] = True
            orig_HTTPSConnection.__init__(self, **kwargs)

    httplib.HTTPConnection = _StrictHTTPConnection
    httplib.HTTPSConnection = _StrictHTTPSConnection


# vim:et:fdm=marker:sts=4:sw=4:ts=4
