
from mox3.mox import MoxTestBase, IsA
from gevent import socket

from slimta.util.proxyproto import ProxyProtocolV1


class SomeEdgeServer(object):

    def __init__(self, test, expected_sock, expected_addr):
        super(SomeEdgeServer, self).__init__()
        self.test = test
        self.expected_sock = expected_sock
        self.expected_addr = expected_addr
        self.handle_called = False

    def handle(self, sock, addr):
        self.test.assertEqual(self.expected_sock, sock)
        self.test.assertEqual(self.expected_addr, addr)
        self.handle_called = True


class PPEdgeServer(ProxyProtocolV1, SomeEdgeServer):
    pass


class TestProxyProtocolV1(MoxTestBase):

    def setUp(self):
        super(TestProxyProtocolV1, self).setUp()
        self.pp = ProxyProtocolV1()

    def test_read_pp_line(self):
        def _get_side_effect(data):
            def _side_effect(view, length):
                view[0:length] = data
            return _side_effect

        sock = self.mox.CreateMock(socket.socket)
        sock.recv_into(IsA(memoryview), 2).WithSideEffects(_get_side_effect(b'ab')).AndReturn(2)
        sock.recv_into(IsA(memoryview), 2).WithSideEffects(_get_side_effect(b'cd')).AndReturn(2)
        sock.recv_into(IsA(memoryview), 2).WithSideEffects(_get_side_effect(b'ef')).AndReturn(2)
        sock.recv_into(IsA(memoryview), 2).WithSideEffects(_get_side_effect(b'g\r')).AndReturn(2)
        sock.recv_into(IsA(memoryview), 1).WithSideEffects(_get_side_effect(b'\n')).AndReturn(1)
        self.mox.ReplayAll()
        line = self.pp._ProxyProtocolV1__read_pp_line(sock)
        self.assertEqual(b'abcdefg\r\n', line)

    def test_read_pp_line_eof(self):
        sock = self.mox.CreateMock(socket.socket)
        sock.recv_into(IsA(memoryview), 2).AndReturn(0)
        self.mox.ReplayAll()
        with self.assertRaises(AssertionError):
            self.pp._ProxyProtocolV1__read_pp_line(sock)

    def test_read_pp_line_long(self):
        sock = self.mox.CreateMock(socket.socket)
        for i in range(53):
            sock.recv_into(IsA(memoryview), 2).AndReturn(2)
        sock.recv_into(IsA(memoryview), 1).AndReturn(1)
        self.mox.ReplayAll()
        line = self.pp._ProxyProtocolV1__read_pp_line(sock)
        self.assertEqual(b'\x00'*107, line)

    def test_handle(self):
        sock = self.mox.CreateMock(socket.socket)
        sock.fileno = lambda: -1
        pp = PPEdgeServer(self, sock, 13)
        self.mox.StubOutWithMock(pp, '_ProxyProtocolV1__read_pp_line')
        self.mox.StubOutWithMock(pp, 'parse_pp_line')
        pp._ProxyProtocolV1__read_pp_line(sock).AndReturn(b'the line')
        pp.parse_pp_line(b'the line').AndReturn((13, 14))
        self.mox.ReplayAll()
        pp.handle(sock, None)
        self.assertTrue(pp.handle_called)

    def test_handle_error(self):
        sock = self.mox.CreateMock(socket.socket)
        sock.fileno = lambda: -1
        pp = PPEdgeServer(self, sock, (None, None))
        self.mox.StubOutWithMock(pp, '_ProxyProtocolV1__read_pp_line')
        pp._ProxyProtocolV1__read_pp_line(sock).AndRaise(AssertionError)
        self.mox.ReplayAll()
        pp.handle(sock, None)
        self.assertTrue(pp.handle_called)

    def test_parse_pp_line(self):
        f = self.pp.parse_pp_line
        self.assertEqual(((None, None), (None, None)),
                         f(b'PROXY UNKNOWN\r\n'))
        self.assertEqual((('127.0.0.1', 1234), ('0.0.0.0', 5678)),
                         f(b'PROXY TCP4 127.0.0.1 0.0.0.0 1234 5678\r\n'))
        self.assertEqual((('::1', 8765), ('::', 4321)),
                         f(b'PROXY TCP6 ::1 ::0 8765 4321\r\n'))

    def test_parse_pp_line_invalid(self):
        f = self.pp.parse_pp_line
        with self.assertRaises(AssertionError):
            f(b'NOPROXY UNKNOWN\r\n')
        with self.assertRaises(AssertionError):
            f(b'PROXY UNKNOWN')
        with self.assertRaises(AssertionError):
            f(b'PROXY TEST 0.0.0.0 0.0.0.0 0 0\r\n')
        with self.assertRaises(AssertionError):
            f(b'PROXY TCP4 ::0 ::0 0 0\r\n')
        with self.assertRaises(AssertionError):
            f(b'PROXY TCP6 0.0.0.0 0.0.0.0 0 0\r\n')
        with self.assertRaises(AssertionError):
            f(b'PROXY TCP4 0.0.0.0 0.0.0.0 abc def\r\n')
        with self.assertRaises(AssertionError):
            f(b'PROXY TCP4 0.0.0.0 0.0.0.0 100000 0\r\n')


# vim:et:fdm=marker:sts=4:sw=4:ts=4
