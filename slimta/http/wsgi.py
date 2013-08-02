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

.. _WSGI: http://wsgi.readthedocs.org/en/latest/

"""

from __future__ import absolute_import

import sys
import re
from base64 import b64decode
from wsgiref.headers import Headers

import gevent
from gevent.pywsgi import WSGIServer
from gevent import monkey; monkey.patch_all()
from dns import resolver, reversename
from dns.exception import DNSException

from slimta import logging
from slimta.envelope import Envelope
from slimta.smtp.reply import Reply
from slimta.queue import QueueError
from slimta.relay import RelayError
from . import HttpError

__all__ = []

log = logging.getHttpLogger(__name__)


class WsgiResponse(HttpError):
    """This exception can be explicitly raised to end the WSGI request and
    return the given response.

    :param status: The HTTP status string to return, e.g. ``200 OK``.
    :param headers: List of ``(name, value)`` header tuples to return.
    :param data: Optional raw data string to return.

    """

    def __init__(self, status, headers=None, data=None):
        super(WsgiResponse, self).__init__(status)
        self.status = status
        self.headers = headers or []
        self.data = data or []


def _header_name_to_cgi(name):
    return 'HTTP_{0}'.format(name.upper().replace('-', '_'))


def _build_http_response(smtp_reply):
    code = smtp_reply.code
    headers = []
    info = {'message': smtp_reply.message}
    if smtp_reply.command:
        info['command'] = smtp_reply.command
    Headers(headers).add_header('X-Smtp-Reply', code, **info)
    if code.startswith('2'):
        return WsgiResponse('200 OK', headers)
    elif code.startswith('4'):
        return WsgiResponse('503 Service Unavailable', headers)
    elif code == '535':
        return WsgiResponse('401 Unauthorized', headers)
    else:
        return WsgiResponse('500 Internal Server Error', headers)


class WsgiServer(object):
    """Implements the base class for a WSGI server that logs its requests and
    responses and can easily be deployed as a functioning HTTP server.

    """

    split_pattern = re.compile(r'\s*[,;]\s*')

    def __init__(self):
        super(WsgiServer, self).__init__()

    def build_server(self, listener, pool=None, tls=None):
        """Constructs and returns a WSGI server engine, configured to use the
        current object as its application.

        :param listener: Usually a ``(ip, port)`` tuple defining the interface
                         and port upon which to listen for connections.
        :param pool: If given, defines a specific :class:`gevent.pool.Pool` to
                     use for new greenlets.
        :param tls: Optional dictionary of TLS settings passed directly as
                    keyword arguments to :class:`gevent.ssl.SSLSocket`.
        :rtype: :class:`gevent.pywsgi.WSGIServer`

        """
        spawn = pool or 'default'
        tls = tls or {}
        return WSGIServer(listener, self, log=sys.stdout, **tls)

    def __call__(self, environ, start_response):
        log.wsgi_request(environ)
        def logged_start_response(status, headers, *args, **kwargs):
            log.wsgi_response(environ, status, headers)
            return start_resonse(status, headers, *args, **kwargs)
        pass

    def _validate_request(self, environ):
        if self.uri_pattern:
            path = environ.get('PATH_INFO', '')
            if not re.match(self.uri_pattern, path):
                raise WsgiResponse('404 Not Found')
        method = environ['REQUEST_METHOD'].upper()
        if method != 'POST':
            headers = [('Allow', 'POST')]
            raise WsgiResponse('405 Method Not Allowed', headers)
        ctype = environ.get('CONTENT_TYPE', 'message/rfc822')
        if ctype != 'message/rfc822':
            raise WsgiResponse('415 Unsupported Media Type')
        if self.validator_class:
            self._run_validators(environ)

    def _run_validators(self, environ):
        validators = self.validator_class(environ)
        validators.validate_ehlo(self._get_ehlo(environ))
        validators.validate_sender(self._get_sender(environ))
        recipients = self._get_recipients(environ)
        for rcpt in recipients:
            validators.validate_recipient(rcpt)
        for name in validators.custom_headers:
            cgi_name = _header_name_to_cgi(name)
            validators.validate_custom(name, environ.get(cgi_name))

    def _ptr_lookup(self, environ):
        ip = environ.get('REMOTE_ADDR', '0.0.0.0')
        ptraddr = reversename.from_address(ip)
        try:
            answers = resolver.query(ptraddr, 'PTR')
        except DNSException:
            answers = []
        try:
            environ['slimta.reverse_address'] = str(answers[0])
        except IndexError:
            pass

    def _trigger_ptr_lookup(self, environ):
        thread = gevent.spawn(self._ptr_lookup, environ)
        environ['slimta.ptr_lookup_thread'] = thread

    def _get_sender(self, environ):
        sender_header = _header_name_to_cgi(self.sender_header)
        return b64decode(environ.get(sender_header, ''))

    def _get_recipients(self, environ):
        rcpt_header = _header_name_to_cgi(self.rcpt_header)
        rcpts_raw = environ.get(rcpt_header, None)
        if not rcpts_raw:
            return []
        rcpts_split = self.split_pattern.split(rcpts_raw)
        return [b64decode(rcpt_b64) for rcpt_b64 in rcpts_split]

    def _get_ehlo(self, environ):
        ehlo_header = _header_name_to_cgi(self.ehlo_header)
        default = '[{0}]'.format(environ.get('REMOTE_ADDR', 'unknown'))
        return environ.get(ehlo_header, default)

    def _get_envelope(self, environ):
        sender = self._get_sender(environ)
        recipients = self._get_recipients(environ)
        env = Envelope(sender, recipients)

        content_length = int(environ.get('CONTENT_LENGTH', 0))
        data = environ['wsgi.input'].read(content_length)
        env.parse(data)
        return env

    def _add_envelope_extras(self, environ, env):
        env.client['ip'] = environ.get('REMOTE_ADDR', 'unknown')
        env.client['host'] = environ.get('slimta.reverse_address', None)
        env.client['name'] = self._get_ehlo(environ)
        env.client['protocol'] = environ.get('wsgi.url_scheme', 'http').upper()

    def _enqueue_envelope(self, env):
        results = self.handoff(env)
        if isinstance(results[0][1], QueueError):
            reply = Reply('550', '5.6.0 Error queuing message')
            raise _build_http_response(reply)
        elif isinstance(results[0][1], RelayError):
            relay_reply = results[0][1].reply
            raise _build_http_response(relay_reply)
        reply = Reply('250', '2.6.0 Message accepted for delivery')
        raise _build_http_response(reply)


class WsgiValidators(object):
    """Base class for implementing WSGI request validation. Instances will be
    created for each WSGI request.

    To terminate the current WSGI request with a response, raise the
    :exc:`WsgiResponse` exception from with the validator methods.

    :param environ: The environment variables_ for the current session.

    """

    #: A static list of headers that should be passed in to
    #: :meth:`validate_custom()`.
    custom_headers = []

    def __init__(self, environ):
        #: Stores the environment variables_ for the current session.
        self.environ = environ

    def validate_ehlo(self, ehlo):
        """Override this method to validate the EHLO string passed in by the
        client in the ``X-Ehlo`` (or equivalent) header.

        :param ehlo: The value of the EHLO header.

        """
        pass

    def validate_sender(self, sender):
        """Override this method to validate the sender address passed in by the
        client in the ``X-Envelope-Sender`` (or equivalent) header.

        :param sender: The decoded value of the sender header.

        """
        pass

    def validate_recipient(self, recipient):
        """Override this method to validate each recipient address passed in by
        the client in the ``X-Envelope-Recipient`` (or equivalent) headers. This
        method will be called for each occurence of the header.

        :param recipient: The decoded value of one recipient header.

        """
        pass

    def validate_custom(self, name, value):
        """Override this method to validate custom headers sent in by the
        client. This method will be called exactly once for each header listed
        in the :attr:`custom_headers` class attribute.

        :param name: The name of the header.
        :param value: The raw value of the header, or ``None`` if the client did
                      not provide the header.

        """
        pass


# vim:et:fdm=marker:sts=4:sw=4:ts=4
