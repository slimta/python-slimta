
import unittest2 as unittest
from mox import MoxTestBase, IsA
import gevent
from gevent.pywsgi import WSGIServer as GeventWSGIServer

from slimta.http.wsgi import WsgiServer, log


class TestWsgiServer(unittest.TestCase, MoxTestBase):

    def test_build_server(self):
        w = WsgiServer()
        server = w.build_server(('0.0.0.0', 0))
        self.assertIsInstance(server, GeventWSGIServer)

    def test_handle_unimplemented(self):
        w = WsgiServer()
        with self.assertRaises(NotImplementedError):
            w.handle(None, None)

    def test_call(self):
        class FakeWsgiServer(WsgiServer):
            def handle(self, environ, start_response):
                start_response('200 Test', 13)
                return ['test']
        w = FakeWsgiServer()
        environ = {}
        start_response = self.mox.CreateMockAnything()
        self.mox.StubOutWithMock(log, 'wsgi_request')
        self.mox.StubOutWithMock(log, 'wsgi_response')
        log.wsgi_request(environ)
        start_response('200 Test', 13)
        log.wsgi_response(environ, '200 Test', 13)
        self.mox.ReplayAll()
        self.assertEqual(['test'], w(environ, start_response))


# vim:et:fdm=marker:sts=4:sw=4:ts=4
