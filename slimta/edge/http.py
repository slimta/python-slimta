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

import re
from base64 import b64decode

import gevent
from gevent.pywsgi import WSGIServer
from gevent import monkey; monkey.patch_all()
from dns import resolver, reversename
from dns.exception import DNSException

from slimta import logging
from slimta.envelope import Envelope
from slimta.queue import QueueError
from slimta.relay import RelayError
from . import Edge

__all__ = ['HttpEdge']

log = logging.getWSGILogger(__name__)



class HttpEdge(Edge, gevent.Greenlet):
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
    :param tls: Optional dictionary of TLS settings passed directly as
                keyword arguments to :class:`gevent.ssl.SSLSocket`.

    """

    split_pattern = re.compile(r'\s*[,;]\s*')

    def __init__(self, listener, queue, pool=None, hostname=None, tls=None):
        super(HttpEdge, self).__init__(queue, hostname)
        spawn = pool or 'default'
        self.tls = tls or {}
        self.server = WSGIServer(listener, self._handle, **self.tls)

    def _log_request(self, environ):
        pass

    def _handle(self, environ, start_response):
        self._trigger_ptr_lookup(environ)
        log.request(environ)
        env = self._get_envelope(environ)
        self._add_envelope_extras(environ, env)
        status, headers, data = self._enqueue_envelope(env)
        log.response(environ, status, headers)
        start_response(status, headers)
        return data

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
        return b64decode(environ.get('HTTP_X_ENVELOPE_SENDER', ''))

    def _get_recipients(self, environ):
        rcpts_raw = environ.get('HTTP_X_ENVELOPE_RECIPIENT', '')
        rcpts_split = self.split_pattern.split(rcpts_raw)
        return [b64decode(rcpt_b64) for rcpt_b64 in rcpts_split]

    def _get_envelope(self, environ):
        sender = self._get_sender(environ)
        recipients = self._get_recipients(environ)
        env = Envelope(sender, recipients)

        content_length = int(environ.get('CONTENT_LENGTH', 0))
        data = environ['wsgi.input'].read(content_length)
        env.parse(data)
        return env

    def _add_envelope_extras(self, environ, env):
        env.client['ip'] = environ.get('REMOTE_ADDR', '0.0.0.0')
        env.client['host'] = environ.get('slimta.reverse_address', None)
        env.client['name'] = environ['HTTP_X_EHLO']
        env.client['protocol'] = 'HTTPS' if self.tls else 'HTTP'
        environ['slimta.ptr_lookup_thread'].kill(block=False)

    def _enqueue_envelope(self, env):
        results = self.handoff(env)
        return '200 OK', [], []

    def _run(self):
        return self.server.serve_forever()


# vim:et:fdm=marker:sts=4:sw=4:ts=4
