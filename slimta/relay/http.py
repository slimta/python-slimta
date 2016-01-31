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
from socket import getfqdn
from base64 import b64encode

import gevent

from slimta import logging
from slimta.smtp.reply import Reply
from slimta.http import get_connection
from slimta.util import validate_tls
from slimta.util.pycompat import urlparse
from . import PermanentRelayError, TransientRelayError
from .pool import RelayPool, RelayPoolClient
from .smtp import SmtpRelayError

__all__ = ['HttpRelay']

log = logging.getHttpLogger(__name__)


class HttpRelayClient(RelayPoolClient):

    reply_code_pattern = re.compile(r'^\s*(\d\d\d)\s*;')
    reply_param_pattern = re.compile(r'\s(\w+)\s*=\s*"(.*?)"')

    def __init__(self, relay):
        super(HttpRelayClient, self).__init__(relay.queue, relay.idle_timeout)
        self.conn = None
        self.ehlo_as = None
        self.url = relay.url
        self.relay = relay

    def _wait_for_request(self):
        result, envelope = self.poll()
        if result and envelope:
            self.idle = False
            self._handle_request(result, envelope)
        else:
            if self.conn:
                self.conn.close()
                self.conn = None

    def _b64encode(self, what):
        return b64encode(what.encode('utf-8')).decode('ascii')

    def _build_headers(self, envelope, msg_headers, msg_body):
        content_length = str(len(msg_headers) + len(msg_body))
        headers = [('Content-Length', content_length),
                   ('Content-Type', 'message/rfc822'),
                   (self.relay.ehlo_header, self.ehlo_as),
                   (self.relay.sender_header,
                    self._b64encode(envelope.sender))]
        for rcpt in envelope.recipients:
            headers.append((self.relay.recipient_header,
                            self._b64encode(rcpt)))
        return headers

    def _new_conn(self):
        self.conn = get_connection(self.url, self.relay.tls)
        try:
            self.ehlo_as = self.relay.ehlo_as()
        except TypeError:
            self.ehlo_as = self.relay.ehlo_as

    def _handle_request(self, result, envelope):
        method = self.relay.http_verb
        if not self.conn:
            self._new_conn()
        with gevent.Timeout(self.relay.timeout):
            msg_headers, msg_body = envelope.flatten()
            headers = self._build_headers(envelope, msg_headers, msg_body)
            log.request(self.conn, method, self.url.path, headers)
            self.conn.putrequest(method, self.url.path)
            for name, value in headers:
                self.conn.putheader(name.encode('iso-8859-1'),
                                    value.encode('iso-8859-1'))
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
            result.set(smtp_reply)
        else:
            if smtp_reply:
                exc = SmtpRelayError.factory(smtp_reply)
            elif status.startswith('4'):
                exc = PermanentRelayError(http_res.reason)
            else:
                exc = TransientRelayError(http_res.reason)
            result.set_exception(exc)

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


class HttpRelay(RelayPool):
    """Implements a |Relay| that attempts to deliver mail with an HTTP or HTTPS
    request. This request contains all the information that would usually go
    through an SMTP session as headers: the EHLO string, envelope sender and
    recipients.

    A ``200 OK`` (or similar) response from the server will inform the caller
    that the message was successfully delivered. In other cases, the class
    makes its best guess about whether to raise a
    :class:`~slimta.relay.PermanentRelayError` or
    :class:`~slimta.relay.TransientRelayError`. If the server's response
    includes a ``X-Smtp-Reply`` header, it will be used. This header looks
    like::

        X-Smtp-Reply: 550; message="5.0.0 Some error message"

    :param url: URL string to make requests against. This string is parsed with
                :py:func:`urlparse.urlsplit` with ``'http'`` as the default
                scheme.
    :param pool_size: At most this many simultaneous connections will be open
                      to the destination. If this limit is reached and no
                      connections are idle, new attempts will block.
    :param tls: Dictionary of TLS settings passed directly as keyword arguments
                to :class:`gevent.ssl.SSLSocket`. This parameter is optional
                unless ``https:`` is given in ``url``.
    :param ehlo_as: The string to send as the EHLO string in a header. Defaults
                    to the FQDN of the system. This may also be given as a
                    function that will be executed with no arguments at the
                    beginning of each connection.
    :param timeout: This is the maximum time in seconds to wait for the entire
                    session: connection, request, and response. If ``None``,
                    there is no timeout.
    :param idle_timeout: Timeout in seconds that a connection is held open
                         waiting for another delivery request to process. By
                         default, connections are closed immediately and not
                         reused.

    """

    #: The HTTP verb to use with the requests.
    http_verb = 'POST'

    #: The header name used to send the base64-encoded sender address.
    sender_header = 'X-Envelope-Sender'

    #: The header name used to send each base64-encoded recipient address.
    recipient_header = 'X-Envelope-Recipient'

    #: The header name used to send the EHLO string.
    ehlo_header = 'X-Ehlo'

    def __init__(self, url, pool_size=None, tls=None, ehlo_as=None,
                 timeout=None, idle_timeout=None):
        super(HttpRelay, self).__init__(pool_size)
        self.url = urlparse.urlsplit(url, 'http')
        self.tls = validate_tls(tls)
        self.ehlo_as = ehlo_as or getfqdn()
        self.timeout = timeout
        self.idle_timeout = idle_timeout

    def add_client(self):
        return HttpRelayClient(self)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
