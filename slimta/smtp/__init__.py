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

"""Root package for :mod:`slimta` SMTP client and server libraries."""

from __future__ import absolute_import

from slimta.core import SlimtaError

__all__ = ['SmtpError',
           'ConnectionLost',
           'MessageTooBig',
           'BadReply']


class SmtpError(SlimtaError):
    """Base exception for all custom SMTP exceptions."""
    pass


class ConnectionLost(SmtpError):
    """Thrown when the socket is closed prematurely."""

    def __init__(self):
        msg = 'Connection was closed prematurely'
        super(ConnectionLost, self).__init__(msg)


class MessageTooBig(SmtpError):
    """Thrown when a message exceeds the maximum size given by the SMTP
    ``SIZE`` extension, if supported.

    """

    def __init__(self):
        msg = 'Message exceeded maximum allowed size'
        super(MessageTooBig, self).__init__(msg)


class BadReply(SmtpError):
    """Thrown when an SMTP server replies with a syntax-invalid code.

    :param data: The data that was expected to start with an SMTP code, made
                 available in the ``data`` attribute.

    """

    def __init__(self, data):
        super(BadReply, self).__init__('Bad SMTP reply from server.')
        self.data = data


# vim:et:fdm=marker:sts=4:sw=4:ts=4
