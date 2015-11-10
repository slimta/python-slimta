from __future__ import unicode_literals
from base64 import b64encode

import unittest2 as unittest
from mox3.mox import MoxTestBase, IsA, IgnoreArg
import gevent
from dns.exception import DNSException
import six


from slimta.edge.wsgi import WsgiEdge, WsgiValidators
from slimta.util import dns_resolver
from slimta.envelope import Envelope
from slimta.queue import QueueError
from slimta.smtp.reply import Reply


class TestEdgeWsgi(unittest.TestCase, MoxTestBase):

    def setUp(self):
        super(TestEdgeWsgi, self).setUp()
        self.start_response = self.mox.CreateMockAnything()
        self.queue = self.mox.CreateMockAnything()
        self.environ = {
            b'REQUEST_METHOD': b'POST',
            b'HTTP_X_EHLO': b'test',
            b'HTTP_X_ENVELOPE_SENDER': b64encode(b'sender@example.com'),
            b'HTTP_X_ENVELOPE_RECIPIENT': '{0}, {1}'.format(
                b64encode(b'rcpt1@example.com').decode(),
                b64encode(b'rcpt2@example.com').decode()).encode('ascii'),
            b'HTTP_X_CUSTOM_HEADER': b'custom test',
            b'wsgi.input': six.BytesIO(b'')
        }

        self.unicode_environ = {
            'REQUEST_METHOD': 'POST',
            'HTTP_X_EHLO': 'test',
            'HTTP_X_ENVELOPE_SENDER': b64encode(b'sender@example.com').decode(),
            'HTTP_X_ENVELOPE_RECIPIENT': '{0}, {1}'.format(
                b64encode(b'rcpt1@example.com').decode(),
                b64encode(b'rcpt2@example.com').decode()),
            'HTTP_X_CUSTOM_HEADER': 'custom test',
            'wsgi.input': six.BytesIO(b'')
        }


    def test_ptr_lookup(self):
        environ = self.environ.copy()
        environ[b'REMOTE_ADDR'] = b'1.2.3.4'
        self.mox.StubOutWithMock(dns_resolver, 'query')
        dns_resolver.query(IgnoreArg(), 'PTR').AndRaise(DNSException)
        dns_resolver.query(IgnoreArg(), 'PTR').AndReturn(['example.com'])
        self.mox.ReplayAll()
        w = WsgiEdge(None)
        w._ptr_lookup(environ)
        self.assertNotIn('slimta.reverse_address', environ)
        w._ptr_lookup(environ)
        self.assertEqual('example.com', environ['slimta.reverse_address'])

    def test_invalid_path(self):
        environ = self.environ.copy()
        valid_paths = r'/good'
        environ[b'PATH_INFO'] = b'/bad'
        self.start_response.__call__('404 Not Found', IsA(list))
        self.mox.ReplayAll()
        w = WsgiEdge(self.queue, uri_pattern=valid_paths)
        self.assertEqual([], w(environ, self.start_response))

    def test_invalid_method(self):
        environ = self.environ.copy()
        environ[b'REQUEST_METHOD'] = b'PUT'
        self.start_response.__call__('405 Method Not Allowed', IsA(list))
        self.mox.ReplayAll()
        w = WsgiEdge(self.queue)
        self.assertEqual([], w(environ, self.start_response))

    def test_invalid_content_type(self):
        environ = self.environ.copy()
        environ[b'CONTENT_TYPE'] = b'text/plain'
        self.start_response.__call__('415 Unsupported Media Type', IsA(list))
        self.mox.ReplayAll()
        w = WsgiEdge(self.queue)
        self.assertEqual([], w(environ, self.start_response))

    def test_unexpected_exception(self):
        environ = self.environ.copy()
        environ[b'wsgi.input'] = None
        self.start_response.__call__('500 Internal Server Error', IsA(list))
        self.mox.ReplayAll()
        w = WsgiEdge(self.queue)
        self.assertEqual(["'NoneType' object has no attribute 'read'\n"], w(environ, self.start_response))

    def test_no_error(self):
        def verify_envelope(env):
            if not isinstance(env, Envelope):
                return False
            if 'sender@example.com' != env.sender:
                return False
            if 'rcpt1@example.com' != env.recipients[0]:
                return False
            if 'rcpt2@example.com' != env.recipients[1]:
                return False
            return True
        self.queue.enqueue(IsA(Envelope)).AndReturn([(Envelope(), 'testid')])
        self.start_response.__call__('200 OK', IsA(list))
        self.mox.ReplayAll()
        w = WsgiEdge(self.queue)
        self.assertEqual([], w(self.environ, self.start_response))

    def test_queueerror(self):
        self.queue.enqueue(IsA(Envelope)).AndReturn([(Envelope(), QueueError())])
        self.start_response.__call__('500 Internal Server Error', IsA(list))
        self.mox.ReplayAll()
        w = WsgiEdge(self.queue)
        self.assertEqual([], w(self.environ, self.start_response))

    def test_run_validators(self):
        self.validated = 0
        class Validators(WsgiValidators):
            custom_headers = ['X-Custom-Header']
            def validate_ehlo(self2, ehlo):
                self.assertEqual('test', ehlo)
                self.validated += 1
            def validate_sender(self2, sender):
                self.assertEqual('sender@example.com', sender)
                self.validated += 2
            def validate_recipient(self2, recipient):
                if recipient == 'rcpt1@example.com':
                    self.validated += 4
                elif recipient == 'rcpt2@example.com':
                    self.validated += 8
                else:
                    raise AssertionError('bad recipient: '+recipient)
            def validate_custom(self2, name, value):
                self.assertEqual('X-Custom-Header', name)
                self.assertEqual('custom test', value)
                self.validated += 16
        w = WsgiEdge(None, validator_class=Validators)
        w._run_validators(self.unicode_environ)
        self.assertEqual(31, self.validated)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
