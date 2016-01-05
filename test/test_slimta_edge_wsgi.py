
from io import BytesIO

from mox3.mox import MoxTestBase, IsA

from slimta.edge.wsgi import WsgiEdge, WsgiValidators
from slimta.envelope import Envelope
from slimta.queue import QueueError


class TestEdgeWsgi(MoxTestBase):

    def setUp(self):
        super(TestEdgeWsgi, self).setUp()
        self.start_response = self.mox.CreateMockAnything()
        self.queue = self.mox.CreateMockAnything()
        self.environ = {'REQUEST_METHOD': 'POST',
                        'HTTP_X_EHLO': 'test',
                        'HTTP_X_ENVELOPE_SENDER': 'c2VuZGVyQGV4YW1wbGUuY29t',
                        'HTTP_X_ENVELOPE_RECIPIENT': 'cmNwdDFAZXhhbXBsZS5jb20=, cmNwdDJAZXhhbXBsZS5jb20=',
                        'HTTP_X_CUSTOM_HEADER': 'custom test',
                        'wsgi.input': BytesIO(b'')}

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
        self.start_response.__call__('204 No Content', IsA(list))
        self.mox.ReplayAll()
        w = WsgiEdge(self.queue)
        self.assertEqual([], w(self.environ, self.start_response))

    def test_queueerror(self):
        self.queue.enqueue(IsA(Envelope)).AndReturn([(Envelope(), QueueError())])
        self.start_response.__call__('503 Service Unavailable', IsA(list))
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
        w._run_validators(self.environ)
        self.assertEqual(31, self.validated)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
