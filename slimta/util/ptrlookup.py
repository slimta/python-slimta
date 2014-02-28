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

""".. versionadded:: 0.3.21

When a client connects to the server, it is useful to know who they claim to
be. One such method is looking up the PTR records for the client's IP address
in DNS. If it exists, a PTR record will map an IP address to an arbitrary
hostname.

However, it is not usually desired to slow down a client's request just because
their PTR record lookup has not yet finished. This module implements a
:class:`~gevent.Greenlet` thread that will look up a client's PTR record will
its request is being processed. If the request finishes before the PTR record
lookup, the lookup is stopped

"""

from __future__ import absolute_import

import time

import gevent
from dns import reversename
from dns.resolver import NXDOMAIN
from dns.exception import SyntaxError as DnsSyntaxError

from slimta.util import dns_resolver
from slimta import logging

__all__ = ['PtrLookup']


class PtrLookup(gevent.Greenlet):
    """Asynchronously looks up the PTR record of an IP address, implemented as
    a :class:`~gevent.Greenlet` thread.

    :param ip: The IP address to query.

    """

    def __init__(self, ip):
        super(PtrLookup, self).__init__()
        self.ip = ip
        self.start_time = None

    @classmethod
    def from_getpeername(cls, socket):
        """Creates a :class:`PtrLookup` object based on the IP address of the
        socket's remote address, using :py:meth:`~socket.socket.getpeername`.

        :param socket: The :py:class:`~socket.socket` object to use.
        :returns: A tuple containing the new :class:`PtrLookup` object and the
                  port number from :py:meth:`~socket.socket.getpeername`.

        """
        ip, port = socket.getpeername()
        return cls(ip), port

    @classmethod
    def from_getsockname(cls, socket):
        """Creates a :class:`PtrLookup` object based on the IP address of the
        socket's local address, using :py:meth:`~socket.socket.getsockname`.

        :param socket: The :py:class:`~socket.socket` object to use.
        :returns: A tuple containing the new :class:`PtrLookup` object and the
                  port number from :py:meth:`~socket.socket.getsockname`.

        """
        ip, port = socket.getsockname()
        return cls(ip), port

    def start(self):
        """Starts the PTR lookup thread.

        .. seealso:: :meth:`gevent.Greenlet.start`

        """
        self.start_time = time.time()
        super(PtrLookup, self).start()

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

    def finish(self, runtime=None):
        """Attempts to get the results of the PTR lookup. If the results are
        not available, ``None`` is returned instead.

        When this method returns, the :class:`~gevent.Greenlet` executing the
        lookup is killed.

        :param runtime: If this many seconds have not passed since the lookup
                        started, the method call blocks the remaining time. For
                        example, if 3.5 seconds have elapsed since calling
                        :meth:`.start` and you pass in ``5.0``, this method
                        will wait at most 1.5 seconds for the results to come
                        in.
        :type runtime: float
        :returns: The PTR lookup results (a hostname string) or ``None``.

        """
        try:
            if runtime is None:
                result = self.get(block=False)
            else:
                timeout = time.time() - self.start_time
                result = self.get(block=True, timeout=timeout)
        except gevent.Timeout:
            result = None
        self.kill(block=False)
        return result


# vim:et:fdm=marker:sts=4:sw=4:ts=4
