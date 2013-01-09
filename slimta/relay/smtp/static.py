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

"""Implements a pool of connections to a single destination. If an existing
connection is available, it is re-used by subsequent connections until it times
out.

"""

from gevent.queue import PriorityQueue
from gevent.event import AsyncResult

from slimta.relay import Relay

__all__ = ['StaticSmtpRelay']


class StaticSmtpRelay(Relay):
    """Manages the relaying of messages to a specific ``host:port``. Connections
    may be recycled when possible, to send multiple messages over a single
    channel.

    :param host: Host string to connect to.
    :param port: Port to connect to.
    :param pool_size: At most this many simultaneous connections will be open to
                      the destination. If this limit is reached and no
                      connections are idle, new attempts will block.
    :param tls: Optional dictionary of TLS settings passed directly as
                keyword arguments to :class:`gevent.ssl.SSLSocket`.
    :param tls_required: If given and True, it should be considered a delivery
                         failure if TLS cannot be negotiated by the client.
    :param connect_timeout: Timeout in seconds to wait for a client connection
                            to be successful before issuing a transient failure.
    :param command_timeout: Timeout in seconds to wait for a reply to each SMTP
                            command before issuing a transient failure.
    :param data_timeout: Timeout in seconds to wait for a reply to message data
                         before issuing a transient failure.
    :param idle_timeout: Timeout in seconds after a message is delivered before
                         a QUIT command is sent and the connection terminated.
                         If another message should be delivered before this
                         timeout expires, the connection will be re-used. By
                         default, QUIT is sent immediately and connections are
                         never re-used.


    """

    def __init__(self, host, port=25, pool_size=None, client_class=None,
                       **client_kwargs):
        super(StaticSmtpRelay, self).__init__()
        if client_class:
            self.client_class = client_class
        else:
            from slimta.relay.smtp.client import SmtpRelayClient
            self.client_class = SmtpRelayClient
        self.host = host
        self.port = port
        self.queue = PriorityQueue()
        self.pool = set()
        self.pool_size = pool_size
        self.client_kwargs = client_kwargs

    def _remove_client(self, client):
        self.pool.remove(client)
        if not self.queue.empty() and not self.pool:
            self._add_client()

    def _add_client(self):
        client = self.client_class((self.host, self.port), self.queue,
                                   **self.client_kwargs)
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
