
from mox3.mox import MoxTestBase, IsA
from gevent import socket

from slimta.util.proxyproto import ProxyProtocol, \
    ProxyProtocolV1, ProxyProtocolV2


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


class PPV1Edge(ProxyProtocolV1, SomeEdgeServer):
    pass


class PPV2Edge(ProxyProtocolV2, SomeEdgeServer):
    pass


class PPEdge(ProxyProtocol, SomeEdgeServer):
    pass


class TestProxyProtocol(MoxTestBase):
    def setUp(self):
        super(TestProxyProtocol, self).setUp()
        self.pp = ProxyProtocol()

    def test_read_pp_initial(self):
        def _get_side_effect(data):
            def _side_effect(view, length):
                view[0:len(data)] = data
            return _side_effect

        sock = self.mox.CreateMock(socket.socket)
        sock.recv_into(IsA(memoryview), 8).WithSideEffects(_get_side_effect(b'abcdefg')).AndReturn(7)
        sock.recv_into(IsA(memoryview), 1).WithSideEffects(_get_side_effect(b'h')).AndReturn(1)
        self.mox.ReplayAll()
        line = self.pp._ProxyProtocol__read_pp_initial(sock)
        self.assertEqual(b'abcdefgh', line)

    def test_handle_pp_v1(self):
        sock = self.mox.CreateMock(socket.socket)
        sock.fileno = lambda: -1
        pp = PPEdge(self, sock, 13)
        self.mox.StubOutWithMock(ProxyProtocol, '_ProxyProtocol__read_pp_initial')
        self.mox.StubOutWithMock(ProxyProtocolV1, 'process_pp_v1')
        pp._ProxyProtocol__read_pp_initial(sock).AndReturn(b'PROXY ')
        ProxyProtocolV1.process_pp_v1(sock, b'PROXY ').AndReturn((13, 14))
        self.mox.ReplayAll()
        pp.handle(sock, None)
        self.assertTrue(pp.handle_called)

    def test_handle_pp_v2(self):
        sock = self.mox.CreateMock(socket.socket)
        sock.fileno = lambda: -1
        pp = PPEdge(self, sock, 13)
        self.mox.StubOutWithMock(ProxyProtocol, '_ProxyProtocol__read_pp_initial')
        self.mox.StubOutWithMock(ProxyProtocolV2, 'process_pp_v2')
        pp._ProxyProtocol__read_pp_initial(sock).AndReturn(b'\r\n\r\n\x00\r\nQ')
        ProxyProtocolV2.process_pp_v2(sock, b'\r\n\r\n\x00\r\nQ').AndReturn((13, 14))
        self.mox.ReplayAll()
        pp.handle(sock, None)
        self.assertTrue(pp.handle_called)

    def test_handle_error(self):
        sock = self.mox.CreateMock(socket.socket)
        sock.fileno = lambda: -1
        pp = PPEdge(self, sock, (None, None))
        self.mox.StubOutWithMock(ProxyProtocol, '_ProxyProtocol__read_pp_initial')
        pp._ProxyProtocol__read_pp_initial(sock).AndRaise(AssertionError)
        self.mox.ReplayAll()
        pp.handle(sock, None)
        self.assertTrue(pp.handle_called)


class TestProxyProtocolV1(MoxTestBase):

    def setUp(self):
        super(TestProxyProtocolV1, self).setUp()
        self.pp = ProxyProtocolV1()

    def test_read_pp_line(self):
        def _get_side_effect(data):
            def _side_effect(view, length):
                view[0:len(data)] = data
            return _side_effect

        sock = self.mox.CreateMock(socket.socket)
        sock.recv_into(IsA(memoryview), 7).WithSideEffects(_get_side_effect(b'bcde')).AndReturn(4)
        sock.recv_into(IsA(memoryview), 3).WithSideEffects(_get_side_effect(b'fgh')).AndReturn(3)
        sock.recv_into(IsA(memoryview), 2).WithSideEffects(_get_side_effect(b'ij')).AndReturn(2)
        sock.recv_into(IsA(memoryview), 2).WithSideEffects(_get_side_effect(b'k\r')).AndReturn(2)
        sock.recv_into(IsA(memoryview), 1).WithSideEffects(_get_side_effect(b'\n')).AndReturn(1)
        self.mox.ReplayAll()
        line = self.pp._ProxyProtocolV1__read_pp_line(sock, b'a')
        self.assertEqual(b'abcdefghijk\r\n', line)

    def test_read_pp_line_eof(self):
        sock = self.mox.CreateMock(socket.socket)
        sock.recv_into(IsA(memoryview), 2).AndReturn(0)
        self.mox.ReplayAll()
        with self.assertRaises(AssertionError):
            self.pp._ProxyProtocolV1__read_pp_line(sock, b'')

    def test_read_pp_line_long(self):
        sock = self.mox.CreateMock(socket.socket)
        sock.recv_into(IsA(memoryview), 8).AndReturn(8)
        for i in range(49):
            sock.recv_into(IsA(memoryview), 2).AndReturn(2)
        sock.recv_into(IsA(memoryview), 1).AndReturn(1)
        self.mox.ReplayAll()
        line = self.pp._ProxyProtocolV1__read_pp_line(sock, b'')
        self.assertEqual(b'\x00'*107, line)

    def test_handle(self):
        sock = self.mox.CreateMock(socket.socket)
        sock.fileno = lambda: -1
        pp = PPV1Edge(self, sock, 13)
        self.mox.StubOutWithMock(ProxyProtocolV1, '_ProxyProtocolV1__read_pp_line')
        self.mox.StubOutWithMock(ProxyProtocolV1, 'parse_pp_line')
        pp._ProxyProtocolV1__read_pp_line(sock, b'').AndReturn(b'the line')
        pp.parse_pp_line(b'the line').AndReturn((13, 14))
        self.mox.ReplayAll()
        pp.handle(sock, None)
        self.assertTrue(pp.handle_called)

    def test_handle_error(self):
        sock = self.mox.CreateMock(socket.socket)
        sock.fileno = lambda: -1
        pp = PPV1Edge(self, sock, (None, None))
        self.mox.StubOutWithMock(ProxyProtocolV1, '_ProxyProtocolV1__read_pp_line')
        pp._ProxyProtocolV1__read_pp_line(sock, b'').AndRaise(AssertionError)
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


class TestProxyProtocolV2(MoxTestBase):

    def setUp(self):
        super(TestProxyProtocolV2, self).setUp()
        self.pp = ProxyProtocolV2()

    def test_read_pp_data(self):
        def _get_side_effect(data):
            def _side_effect(view, length):
                view[0:len(data)] = data
            return _side_effect

        sock = self.mox.CreateMock(socket.socket)
        sock.recv_into(IsA(memoryview), 14).WithSideEffects(_get_side_effect(b'cdefghij')).AndReturn(8)
        sock.recv_into(IsA(memoryview), 6).WithSideEffects(_get_side_effect(b'klmnop')).AndReturn(6)
        self.mox.ReplayAll()
        data = self.pp._ProxyProtocolV2__read_pp_data(sock, 16, b'ab')
        self.assertEqual(b'abcdefghijklmnop', data)

    def test_parse_pp_data(self):
        data = bytearray(b'\r\n\r\n\x00\r\nQUIT\n\x21\x21\xf0\xf0')
        cmd, fam, proto, addr_len = self.pp._ProxyProtocolV2__parse_pp_data(data)
        self.assertEqual('proxy', cmd)
        self.assertEqual(socket.AF_INET6, fam)
        self.assertEqual(socket.SOCK_STREAM, proto)
        self.assertEqual(61680, addr_len)

    def test_parse_pp_addresses(self):
        data = bytearray(b'\x00\x00\x00\x00\x7f\x00\x00\x01\x00\x00\x19\x00')
        src_addr, dst_addr = self.pp._ProxyProtocolV2__parse_pp_addresses(socket.AF_INET, data)
        self.assertEqual(('0.0.0.0', 0), src_addr)
        self.assertEqual(('127.0.0.1', 25), dst_addr)
        data = bytearray((b'\x00'*15 + b'\x01')*2 + b'\x00\x00\x19\x00')
        src_addr, dst_addr = self.pp._ProxyProtocolV2__parse_pp_addresses(socket.AF_INET6, data)
        self.assertEqual(('::1', 0), src_addr)
        self.assertEqual(('::1', 25), dst_addr)
        data = bytearray(b'abc' + b'\x00'*105 + b'def' + b'\x00'*105)
        src_addr, dst_addr = self.pp._ProxyProtocolV2__parse_pp_addresses(socket.AF_UNIX, data)
        self.assertEqual(b'abc', src_addr)
        self.assertEqual(b'def', dst_addr)

    def test_process_pp_v2(self):
        sock = self.mox.CreateMock(socket.socket)
        self.mox.StubOutWithMock(ProxyProtocolV2, '_ProxyProtocolV2__read_pp_data')
        self.mox.StubOutWithMock(ProxyProtocolV2, '_ProxyProtocolV2__parse_pp_data')
        self.mox.StubOutWithMock(ProxyProtocolV2, '_ProxyProtocolV2__parse_pp_addresses')
        ProxyProtocolV2._ProxyProtocolV2__read_pp_data(sock, 16, b'init').AndReturn(b'data1')
        ProxyProtocolV2._ProxyProtocolV2__parse_pp_data(b'data1').AndReturn((1, 2, 3, 4))
        ProxyProtocolV2._ProxyProtocolV2__read_pp_data(sock, 4, b'').AndReturn(b'data2')
        ProxyProtocolV2._ProxyProtocolV2__parse_pp_addresses(2, b'data2').AndReturn((13, 14))
        self.mox.ReplayAll()
        src_addr, dst_addr = ProxyProtocolV2.process_pp_v2(sock, b'init')
        self.assertEqual(13, src_addr)
        self.assertEqual(14, dst_addr)

    def test_handle(self):
        sock = self.mox.CreateMock(socket.socket)
        sock.fileno = lambda: -1
        pp = PPV2Edge(self, sock, 13)
        self.mox.StubOutWithMock(ProxyProtocolV2, 'process_pp_v2')
        ProxyProtocolV2.process_pp_v2(sock, b'').AndReturn((13, 14))
        self.mox.ReplayAll()
        pp.handle(sock, None)
        self.assertTrue(pp.handle_called)

    def test_handle_error(self):
        sock = self.mox.CreateMock(socket.socket)
        sock.fileno = lambda: -1
        pp = PPV2Edge(self, sock, (None, None))
        self.mox.StubOutWithMock(ProxyProtocolV2, 'process_pp_v2')
        ProxyProtocolV2.process_pp_v2(sock, b'').AndRaise(AssertionError)
        self.mox.ReplayAll()
        pp.handle(sock, None)
        self.assertTrue(pp.handle_called)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
