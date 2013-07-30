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

"""This module contains a |Relay| class that delivers mail using the HTTP or
HTTPS protocols. This is done in the same way that
:mod:`slimta.edge.wsgi` receives mail, making the two compatible
for exchanging mail.

"""

from __future__ import absolute_import

import gevent

from . import Relay

__all__ = ['HttpRelay']


class HttpWorker(gevent.Greenlet):

    def __init__(self, manager):
        super(HttpWorker, self).__init__()
        self.manager = manager
        self.idle = True
        self.conn = None

    def _run(self):
        pass


class HttpRelay(Relay):
    """Implements a |Relay| that attempts to deliver mail with an HTTP or HTTPS
    request. This request contains all the information that would usually go
    through an SMTP session as headers: the EHLO string, envelope sender and
    recipients.

    A ``200 OK`` (or similar) response from the server will inform the caller
    that the message was successfully delivered. In other cases, the class makes
    its best guess about whether to raise a
    :class:`~slimta.relay.PermanentRelayError` or
    :class:`~slimta.relay.TransientRelayError`. If the server's response
    includes a ``X-Smtp-Reply`` header, it will be used. This header looks
    like::

        X-Smtp-Reply: 550; message="5.0.0 Some error message"

    :param host: Host string to connect to. See ``host`` parameter of
                 :py:func:`~httplib.HTTPConnection` for details.
    :param port: Port to connect to. See ``port`` parameter of
                 :py:fun:`~httplib.HTTPConnection` for details.
    :param pool_size: At most this many simultaneous connections will be open to
                      the destination. If this limit is reached and no
                      connections are idle, new attempts will block.
    :param tls: Optional dictionary of TLS settings passed directly as
                keyword arguments to :class:`gevent.ssl.SSLSocket`.
    :param tls_required: If given and True, it should be considered a delivery
                         failure if TLS cannot be negotiated by the client.
    :param timeout: This is the maximum time in seconds to wait for the entire
                    session: connection, request, and response. If ``None``,
                    there is no timeout.

    """

    def __init__(self, host, port, pool_size=None, tls=None, tls_required=False,
                 timeout=None):
        super(HttpRelay, self).__init__()
        self.host = host
        self.port = port
        self.queue = PriorityQueue()
        self.pool = set()
        self.pool_size = pool_size
        self.tls = tls
        self.tls_required = tls_required

    def _remove_client(self, client):
        self.pool.remove(client)
        if not self.queue.empty() and not self.pool:
            self._add_client()

    def _add_client(self):
        client = HttpWorker(self)
        client.start()
        client.link(self._remove_client)
        self.pool.add(client)

    def _check_idle(self):
        for client in self.pool:
            if client.idle:
                return
        if not self.pool_size or len(self.pool) < self.pool_size:
            self._add_client()

    def attempt(self, envelope, attempts):
        self._check_idle()
        result = AsyncResult()
        self.queue.put((1, result, envelope))
        return result.get()


# vim:et:fdm=marker:sts=4:sw=4:ts=4
