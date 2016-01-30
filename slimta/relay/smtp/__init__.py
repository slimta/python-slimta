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

"""Package implementing the ability to route messages to their next hop
with the standard SMTP protocol. Moving messages from hop top hop with
SMTP is the foundation of how email works. Picking the next hop is
typically done with MX records in DNS, but often configurations will
involve local static routing.

"""

from __future__ import absolute_import

from .. import RelayError, TransientRelayError, PermanentRelayError

__all__ = ['SmtpRelayError']


class SmtpRelayError(RelayError):

    def __init__(self, type, reply):
        command = reply.command or b'[unknown command]'
        msg = '{0} failure on {1}: {2}'.format(
            type, command.decode('ascii'), str(reply))
        super(SmtpRelayError, self).__init__(msg, reply)

    @staticmethod
    def factory(reply):
        if reply.code[0] == '5':
            return SmtpPermanentRelayError(reply)
        else:
            return SmtpTransientRelayError(reply)


class SmtpTransientRelayError(SmtpRelayError, TransientRelayError):

    def __init__(self, reply):
        super(SmtpTransientRelayError, self).__init__('Transient', reply)


class SmtpPermanentRelayError(SmtpRelayError, PermanentRelayError):

    def __init__(self, reply):
        super(SmtpPermanentRelayError, self).__init__('Permanent', reply)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
