
import unittest
from StringIO import StringIO
from base64 import b64encode

from mox import MoxTestBase, IsA, IgnoreArg
import gevent
from dns import resolver
from dns.exception import DNSException

from slimta.edge.wsgi import WsgiEdge
from slimta.envelope import Envelope
from slimta.queue import QueueError
from slimta.smtp.reply import Reply


class TestEdgeWsgi(MoxTestBase):

    def setUp(self):
        super(TestEdgeWsgi, self).setUp()
        self.start_response = self.mox.CreateMockAnything()
        self.queue = self.mox.CreateMockAnything()
        self.environ = {'REQUEST_METHOD': 'POST',
                        'HTTP_X_ENVELOPE_SENDER': b64encode('sender@example.com'),
                        'HTTP_X_ENVELOPE_RECIPIENT': '{0}, {1}'.format(b64encode('rcpt1@example.com'), b64encode('rcpt2@example.com')),
                        'wsgi.input': StringIO('')}
        self.mox.StubOutWithMock(resolver, 'query')

    def test_ptr_lookup(self):
        environ = self.environ.copy()
        environ['REMOTE_ADDR'] = '1.2.3.4'
        resolver.query(IgnoreArg(), 'PTR').AndRaise(DNSException)
        resolver.query(IgnoreArg(), 'PTR').AndReturn(['example.com'])
        self.mox.ReplayAll()
        w = WsgiEdge(None)
        w._ptr_lookup(environ)
        self.assertNotIn('slimta.reverse_address', environ)
        w._ptr_lookup(environ)
        self.assertEqual('example.com', environ['slimta.reverse_address'])

    def test_invalid_path(self):
        environ = self.environ.copy()
        valid_paths = r'/good'
        environ['PATH_INFO'] = '/bad'
        self.start_response.__call__('404 Not Found', IsA(list))
        self.mox.ReplayAll()
        w = WsgiEdge(self.queue, uri_pattern=valid_paths)
        self.assertEqual([], w(environ, self.start_response))

    def test_invalid_method(self):
        environ = self.environ.copy()
        environ['REQUEST_METHOD'] = 'PUT'
        self.start_response.__call__('405 Method Not Allowed', IsA(list))
        self.mox.ReplayAll()
        w = WsgiEdge(self.queue)
        self.assertEqual([], w(environ, self.start_response))

    def test_invalid_content_type(self):
        environ = self.environ.copy()
        environ['CONTENT_TYPE'] = 'text/plain'
        self.start_response.__call__('415 Unsupported Media Type', IsA(list))
        self.mox.ReplayAll()
        w = WsgiEdge(self.queue)
        self.assertEqual([], w(environ, self.start_response))

    def test_unexpected_exception(self):
        environ = self.environ.copy()
        environ['wsgi.input'] = None
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


# vim:et:fdm=marker:sts=4:sw=4:ts=4
