# Copyright (c) 2013 Ian C. Good
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

"""

"""

from __future__ import absolute_import

import gevent
from dns import reversename
from dns.resolver import NXDOMAIN
from dns.exception import SyntaxError as DnsSyntaxError

from slimta.util import dns_resolver
from slimta import logging

__all__ = ['PtrLookup']


class PtrLookup(gevent.Greenlet):
    """Asynchronously looks up the PTR record of an IP address.

    """

    def __init__(self, ip):
        super(PtrLookup, self).__init__()
        self.ip = ip

    @classmethod
    def from_getpeername(cls, socket):
        ip, port = socket.getpeername()
        return cls(ip), port

    @classmethod
    def from_getsockname(cls, socket):
        ip, port = socket.getsockname()
        return cls(ip), port

    def _run(self):
        try:
            ptraddr = reversename.from_address(self.ip)
            try:
                answers = dns_resolver.query(ptraddr, 'PTR')
            except NXDOMAIN:
                answers = []
            try:
                return str(answers[0])
            except IndexError:
                pass
        except (DnsSyntaxError, gevent.GreenletExit):
            pass
        except Exception:
            logging.log_exception(__name__, query=self.ip)

    def finish(self, block=False, timeout=None):
        try:
            result = self.get(block=block, timeout=timeout)
        except gevent.Timeout:
            result = None
        self.kill(block=False)
        return result


# vim:et:fdm=marker:sts=4:sw=4:ts=4
