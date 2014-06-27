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

"""Implements an |Edge| that receives messages with the HTTP protocol. WSGI_ is
a Python specification for defining communication between web servers and the
application.

The resulting edge can be used by any HTTP client, like curl::

    $ curl -v -X POST -H 'Content-Type: message/rfc822' \\
           --data-binary @test.eml \\
           -H 'X-Envelope-Sender: c2VuZGVyQGV4YW1wbGUuY29t' \\
           -H 'X-Envelope-Recipient: cmVjaXBpZW50QGV4YW1wbGUuY29t' \\
           http://localhost:8080/
    * About to connect() to localhost port 8080 (#0)
    *   Trying 127.0.0.1...
    * Connected to localhost (127.0.0.1) port 8080 (#0)
    > POST / HTTP/1.1
    > User-Agent: curl/7.29.0
    > Host: localhost:8080
    > Accept: */*
    > Content-Type: message/rfc822
    > X-Envelope-Sender: c2VuZGVyQGV4YW1wbGUuY29t
    > X-Envelope-Recipient: cmVjaXBpZW50QGV4YW1wbGUuY29t
    > Content-Length: 99
    >
    * upload completely sent off: 99 out of 99 bytes
    < HTTP/1.1 200 OK
    < X-Smtp-Reply: 250; message="2.6.0 Message accepted for delivery"
    < Date: Mon, 29 Jul 2013 20:11:55 GMT
    < Content-Length: 0
    <
    * Connection #0 to host localhost left intact

.. _WSGI: http://wsgi.readthedocs.org/en/latest/
.. _variables: http://www.python.org/dev/peps/pep-0333/#environ-variables

"""

from __future__ import absolute_import

import sys
import re
from base64 import b64decode
from wsgiref.headers import Headers

import gevent
from gevent.pywsgi import WSGIServer
from dns import reversename
from dns.exception import DNSException

from slimta.logging import log_exception
from slimta.http.wsgi import WsgiServer
from slimta.envelope import Envelope
from slimta.smtp.reply import Reply
from slimta.queue import QueueError
from slimta.relay import RelayError
from slimta.util import dns_resolver
from . import Edge

__all__ = ['WsgiResponse', 'WsgiEdge', 'WsgiValidators']


class WsgiResponse(Exception):
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


class WsgiEdge(Edge, WsgiServer):
    """This class is intended to be instantiated and used as an app on top of a
    WSGI server engine such as :class:`gevent.pywsgi.WSGIServer`. It will only
    acccept ``POST`` requests that provide a ``message/rfc822`` payload.

    :param queue: |Queue| object used by :meth:`.handoff()` to ensure the
                  envelope is properly queued before acknowledged by the edge
                  service.
    :param hostname: String identifying the local machine. See |Edge| for more
                     details.
    :param validator_class: A class inherited from :class:`WsgiValidators`
                            whose methods will be executed on various request
                            headers to validate the request.
    :param uri_pattern: If given, only URI paths that match the given pattern
                        will be allowed.
    :type uri_pattern: :py:class:`~re.RegexObject` or :py:obj:`str`

    """

    split_pattern = re.compile(r'\s*[,;]\s*')

    #: The HTTP verb that clients will use with the requests. This may be
    #: changed with caution.
    http_verb = 'POST'

    #: The header name that clients will use to provide the envelope sender
    #: address.
    sender_header = 'X-Envelope-Sender'

    #: The header name that clients will use to provide the envelope recipient
    #: addresses. This header may be given multiple times, for each recipient.
    rcpt_header = 'X-Envelope-Recipient'

    #: The header name that clients will use to provide the EHLO identifier
    #: string, as in an SMTP session.
    ehlo_header = 'X-Ehlo'

    def __init__(self, queue, hostname=None, validator_class=None,
                 uri_pattern=None):
        super(WsgiEdge, self).__init__(queue, hostname)
        self.validator_class = validator_class
        if isinstance(uri_pattern, basestring):
            self.uri_pattern = re.compile(uri_pattern)
        else:
            self.uri_pattern = uri_pattern

    def __call__(self, environ, start_response):
        self._trigger_ptr_lookup(environ)
        try:
            self._validate_request(environ)
            env = self._get_envelope(environ)
            self._add_envelope_extras(environ, env)
            self._enqueue_envelope(env)
        except WsgiResponse as res:
            start_response(res.status, res.headers)
            return res.data
        except Exception as exc:
            log_exception(__name__)
            msg = '{0!s}\n'.format(exc)
            headers = [('Content-Length', len(msg)),
                       ('Content-Type', 'text/plain')]
            start_response('500 Internal Server Error', headers)
            return [msg]
        finally:
            environ['slimta.ptr_lookup_thread'].kill(block=False)

    def _validate_request(self, environ):
        if self.uri_pattern:
            path = environ.get('PATH_INFO', '')
            if not re.match(self.uri_pattern, path):
                raise WsgiResponse('404 Not Found')
        method = environ['REQUEST_METHOD'].upper()
        if method != self.http_verb:
            headers = [('Allow', self.http_verb)]
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
        try:
            ptraddr = reversename.from_address(ip)
            try:
                answers = dns_resolver.query(ptraddr, 'PTR')
            except NXDOMAIN:
                answers = []
            try:
                environ['slimta.reverse_address'] = str(answers[0])
            except IndexError:
                pass
        except Exception:
            log_exception(__name__, query=ip)

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
        the client in the ``X-Envelope-Recipient`` (or equivalent) headers.
        This method will be called for each occurence of the header.

        :param recipient: The decoded value of one recipient header.

        """
        pass

    def validate_custom(self, name, value):
        """Override this method to validate custom headers sent in by the
        client. This method will be called exactly once for each header listed
        in the :attr:`custom_headers` class attribute.

        :param name: The name of the header.
        :param value: The raw value of the header, or ``None`` if the client
                      did not provide the header.

        """
        pass


# vim:et:fdm=marker:sts=4:sw=4:ts=4
