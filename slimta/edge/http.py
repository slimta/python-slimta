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

"""Implements an |Edge| that receives messages with the HTTP protocol.

"""

from __future__ import absolute_import

import gevent
from gevent.pywsgi import WSGIServer
from gevent import monkey; monkey.patch_all()
from dns import resolver, reversename
from dns.exception import DNSException

from slimta import logging
from . import Edge

__all__ = ['EdgeHTTPServer']

log = logging.getSocketLogger(__name__)


class EdgeHTTPServer(Edge, gevent.Greenlet):
    """This class implements a :class:`~gevent.pywsgi.WSGIServer` that receives
    messages over HTTP or HTTPS.

    :param listener: Usually a ``(ip, port)`` tuple defining the interface and
                     port upon which to listen for connections.
    :param queue: |Queue| object used by :meth:`.handoff()` to ensure the
                  envelope is properly queued before acknowledged by the edge
                  service.
    :param pool: If given, defines a specific :class:`gevent.pool.Pool` to
                 use for new greenlets.
    :param hostname: String identifying the local machine. See |Edge| for more
                     details.

    """

    def __init__(self, listener, queue, pool=None, hostname=None):
        super(EdgeHTTPServer, self).__init__(queue, hostname)
        spawn = pool or 'default'


# vim:et:fdm=marker:sts=4:sw=4:ts=4
