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

"""Utilities to make logging consistent and easy for any any subprocess
operations.

"""

from __future__ import absolute_import

from functools import partial
from pprint import pformat

__all__ = ['SubprocessLogger']


class SubprocessLogger(object):
    """Provides a limited set of log methods that :mod:`slimta` packages may
    use. This prevents free-form logs from mixing in with standard, machine-
    parseable logs.

    :param log: :py:class:`logging.Logger` object to log through.

    """

    def __init__(self, log):
        from slimta.logging import logline
        self.log = partial(logline, log.debug, 'pid')

    def popen(self, process, args):
        self.log(process.pid, 'popen', args=args)

    def stdio(self, process, stdin, stdout, stderr):
        self.log(process.pid, 'stdio',
                 stdin=stdin,
                 stdout=stdout,
                 stderr=stderr)

    def exit(self, process):
        self.log(process.pid, 'exit', returncode=process.returncode)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
