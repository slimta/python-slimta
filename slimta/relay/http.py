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

import re
import urlparse
from httplib import HTTPConnection
from base64 import b64encode

import gevent
from gevent import socket
from gevent.ssl import SSLSocket
from gevent.queue import PriorityQueue, Empty
from gevent.event import AsyncResult

from slimta import logging
from slimta.smtp.reply import Reply
from . import Relay, PermanentRelayError, TransientRelayError
from .smtp import SmtpRelayError

__all__ = ['HttpRelay']

log = logging.getHttpLogger(__name__)


class GeventHTTPConnection(HTTPConnection):
    # This class attempts to avoid the complete re-implementation of httplib
    # that comes included with gevent.

    def connect(self):
        self.sock = socket.create_connection((self.host,self.port),
                                             self.timeout, self.source_address)
        if self._tunnel_host:
            self._tunnel()


class GeventHTTPSConnection(HTTPConnection):
    # This class makes HTTPS connections more robust and capable of certificate
    # verification that the standard httplib library is incapable of doing.

    def __init__(self, *args, **kwargs):
        self.tls = kwargs.pop('tls', None)
        super(GeventHTTPSConnection, self).__init__(*args, **kwargs)

    def connect(self):
        sock = socket.create_connection((self.host,self.port),
                                        self.timeout, self.source_address)
        self.sock = SSLSocket(sock, **self.tls)
        self.sock.do_handshake()
        if self._tunnel_host:
            self._tunnel()

    def close(self):
        if self.sock:
            try:
                self.sock.unwrap()
            except socket.error as (errno, message):
                if errno != 0:
                    raise
        super(GeventHTTPSConnection, self).close()


class HttpWorker(gevent.Greenlet):

    reply_code_pattern = re.compile(r'^\s*(\d\d\d)\s*;')
    reply_param_pattern = re.compile(r'\s(\w+)\s*=\s*"(.*?)"')

    def __init__(self, relay):
        super(HttpWorker, self).__init__()
        self.idle = True
        self.conn = None
        self.url = urlparse.urlsplit(relay.url, 'http')
        self.relay = relay

    def _wait_for_request(self):
        queue = self.relay.queue
        idle_timeout = self.relay.idle_timeout
        self.idle = True
        try:
            n, result, envelope = queue.get(timeout=idle_timeout)
        except Empty:
            if self.conn:
                self.conn.close()
            return
        if result and envelope:
            self.idle = False
            self._handle_request(result, envelope)

    def _build_headers(self, envelope, msg_headers, msg_body):
        content_length = len(msg_headers) + len(msg_body)
        headers = [('Content-Length', content_length),
                   ('Content-Type', 'message/rfc822'),
                   (self.relay.ehlo_header, self.relay.ehlo_as),
                   (self.relay.sender_header, b64encode(envelope.sender))]
        for rcpt in envelope.recipients:
            headers.append((self.relay.rcpt_header, b64encode(rcpt)))
        return headers

    def _handle_request(self, result, envelope):
        if not self.conn:
            self._make_connection()
        with gevent.Timeout(self.relay.timeout):
            msg_headers, msg_body = envelope.flatten()
            headers = self._build_headers(envelope, msg_headers, msg_body)
            log.request(self.conn, 'POST', self.url.path, headers)
            self.conn.putrequest('POST', self.url.path)
            for name, value in headers:
                self.conn.putheader(name, value)
            self.conn.endheaders(msg_headers)
            self.conn.send(msg_body)
            self._process_response(self.conn.getresponse(), result)

    def _parse_smtp_reply_header(self, http_res):
        raw_reply = http_res.getheader('X-Smtp-Reply', '')
        match = re.match(self.reply_code_pattern, raw_reply)
        if not match:
            return None
        code = match.group(1)
        message = ''
        command = None
        for match in re.finditer(self.reply_param_pattern, raw_reply):
            if match.group(1).lower() == 'message':
                message = match.group(2)
            elif match.group(1).lower() == 'command':
                command = match.group(2)
        return Reply(code, message, command)

    def _process_response(self, http_res, result):
        status = '{0!s} {1}'.format(http_res.status, http_res.reason)
        smtp_reply = self._parse_smtp_reply_header(http_res)
        log.response(self.conn, status, http_res.getheaders())
        if status.startswith('2'):
            result.set(True)
            return
        if smtp_reply:
            exc = SmtpRelayError.factory(smtp_reply)
        elif status.startswith('4'):
            exc = PermanentRelayError(http_res.reason)
        else:
            exc = TransientRelayError(http_res.reason)
        result.set_exception(exc)

    def _make_connection(self):
        host = self.url.netloc or 'localhost'
        host = host.rsplit(':', 1)[0]
        port = self.url.port
        if self.relay.tls:
            self.conn = GeventHTTPSConnection(host, port, strict=True,
                                              **self.relay.tls)
        else:
            self.conn = GeventHTTPConnection(host, port, strict=True)
        self.conn.set_debuglevel(1)

    def _run(self):
        try:
            while True:
                self._wait_for_request()
                if not self.relay.idle_timeout:
                    break
        except gevent.Timeout:
            pass
        finally:
            if self.conn:
                self.conn.close()


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

    :param url: URL string to make requests against. This string is parsed with
                :py:func:`urlparse.urlsplit` with ``'http'`` as the default
                scheme.
    :param pool_size: At most this many simultaneous connections will be open to
                      the destination. If this limit is reached and no
                      connections are idle, new attempts will block.
    :param tls: Dictionary of TLS settings passed directly as keyword arguments
                to :class:`gevent.ssl.SSLSocket`. This parameter is optional
                unless ``https:`` is given in ``url``.
    :param ehlo_as: The string to send as the EHLO string in a header. Defaults
                    to the FQDN of the system.
    :param timeout: This is the maximum time in seconds to wait for the entire
                    session: connection, request, and response. If ``None``,
                    there is no timeout.
    :param idle_timeout: Timeout in seconds that a connection is held open
                         waiting for another delivery request to process. By
                         default, connections are closed immediately and not
                         reused.

    """

    #: The header name used to send the base64-encoded sender address.
    sender_header = 'X-Envelope-Sender'

    #: The header name used to send each base64-encoded recipient address.
    recipient_header = 'X-Envelope-Recipient'

    #: The header name used to send the EHLO string.
    ehlo_header = 'X-Ehlo'

    def __init__(self, url, pool_size=None, tls=None, ehlo_as=None,
                 timeout=None, idle_timeout=None):
        super(HttpRelay, self).__init__()
        self.url = url
        self.queue = PriorityQueue()
        self.pool = set()
        self.pool_size = pool_size
        self.tls = tls
        self.ehlo_as = ehlo_as or socket.getfqdn()
        self.timeout = timeout
        self.idle_timeout = idle_timeout

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
