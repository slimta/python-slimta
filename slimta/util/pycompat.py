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
from functools import partial

__all__ = ['PY3', 'PY2', 'map', 'urlparse', 'httplib', 'reprlib',
           'parser_class', 'generator_class']

#: True if the interpreter is Python 3.x, False otherwise.
PY3 = (sys.version_info[0] == 3)

#: True if the interpreter is Python 2.x, False otherwise.
PY2 = (sys.version_info[0] == 2)

if PY3:
    map_func = map

    from urllib import parse as urlparse_mod
    from http import client as httplib_mod
    import reprlib as reprlib_mod

    from email.generator import BytesGenerator
    from email.parser import BytesParser
    from email.policy import SMTP
    parser = partial(BytesParser, policy=SMTP)
    generator = partial(BytesGenerator, policy=SMTP)
else:
    from itertools import imap
    map_func = imap

    import urlparse as urlparse_mod
    import httplib as httplib_mod
    import repr as reprlib_mod

    from email.generator import Generator
    from email.parser import Parser
    parser = Parser
    generator = Generator

#: The ``itertools.imap`` function on Python 2, ``map`` on Python 3.
map = map_func

#: The ``urlparse`` module on Python 2, ``urllib.parse`` on Python 3.
urlparse = urlparse_mod

#: The ``httplib`` module on Python 2, ``http.client`` on Python 3. In Python
#: 2, the deprecated ``strict`` parameter is set to True.
httplib = httplib_mod

#: The ``repr`` module on Python 2, ``reprlib`` on Python 3.
reprlib = reprlib_mod

#: An ``email.parser.Parser`` instance on Python 2, an
#: ``email.parser.BytesParser`` instance on Python 3.
parser_class = parser

#: An ``email.generator.Generator`` instance on Python 2, an
#: ``email.generator.BytesGenerator`` instance on Python 3.
generator_class = generator


# vim:et:fdm=marker:sts=4:sw=4:ts=4
