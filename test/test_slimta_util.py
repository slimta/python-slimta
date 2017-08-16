import unittest
from mox3.mox import MoxTestBase, IgnoreArg
from gevent import socket

from slimta import util


class TestIPv4SocketCreator(MoxTestBase):

    def setUp(self):
        super(TestIPv4SocketCreator, self).setUp()
        self.mox.StubOutWithMock(socket, 'create_connection')
        self.mox.StubOutWithMock(socket, 'getaddrinfo')
        self.socket_creator = util.build_ipv4_socket_creator([25])

    def test_other_port(self):
        socket.create_connection(('host', 443), 'timeout', 'source').AndReturn('socket')
        self.mox.ReplayAll()
        ret = self.socket_creator(('host', 443), 'timeout', 'source')
        self.assertEqual('socket', ret)

    def test_successful(self):
        socket.getaddrinfo('host', 25, socket.AF_INET).AndReturn([(None, None, None, None, 'sockaddr')])
        socket.create_connection('sockaddr', IgnoreArg(), IgnoreArg()).AndReturn('socket')
        self.mox.ReplayAll()
        ret = self.socket_creator(('host', 25), 'timeout', 'source')
        self.assertEqual('socket', ret)

    def test_error(self):
        socket.getaddrinfo('host', 25, socket.AF_INET).AndReturn([(None, None, None, None, 'sockaddr')])
        socket.create_connection('sockaddr', IgnoreArg(), IgnoreArg()).AndRaise(socket.error('error'))
        self.mox.ReplayAll()
        with self.assertRaises(socket.error):
            self.socket_creator(('host', 25), 'timeout', 'source')

    def test_no_addresses(self):
        socket.getaddrinfo('host', 25, socket.AF_INET).AndReturn([])
        self.mox.ReplayAll()
        with self.assertRaises(socket.error):
            self.socket_creator(('host', 25), 'timeout', 'source')


class TestCreateListeners(MoxTestBase):

    def setUp(self):
        super(TestCreateListeners, self).setUp()
        self.mox.StubOutWithMock(socket, 'getaddrinfo')
        self.mox.StubOutWithMock(socket, 'socket')
        self.sock = self.mox.CreateMockAnything()

    def test_unix_socket(self):
        socket.socket(socket.AF_UNIX, socket.SOCK_STREAM, socket.IPPROTO_IP).AndReturn(self.sock)
        self.sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setblocking(0)
        self.sock.bind('/path/to/sock')
        self.sock.listen(socket.SOMAXCONN)
        self.mox.ReplayAll()
        listeners = util.create_listeners('/path/to/sock', socket.AF_UNIX)
        self.assertEqual([self.sock], listeners)

    def test_valueerror(self):
        self.mox.ReplayAll()
        with self.assertRaises(ValueError):
            util.create_listeners('bad')

    def test_successful(self):
        socket.getaddrinfo('host', 25, socket.AF_UNSPEC, socket.SOCK_STREAM, socket.IPPROTO_IP, socket.AI_PASSIVE).AndReturn([(11, 12, 13, None, 'sockaddr')])
        socket.socket(11, 12, 13).AndReturn(self.sock)
        self.sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setblocking(0)
        self.sock.bind('sockaddr')
        self.sock.listen(socket.SOMAXCONN)
        self.mox.ReplayAll()
        listeners = util.create_listeners(('host', 25))
        self.assertEqual([self.sock], listeners)

    def test_socket_error(self):
        socket.getaddrinfo('host', 25, socket.AF_UNSPEC, socket.SOCK_STREAM, socket.IPPROTO_IP, socket.AI_PASSIVE).AndReturn([(11, 12, 13, None, 'sockaddr')])
        socket.socket(11, 12, 13).AndRaise(socket.error)
        self.mox.ReplayAll()
        with self.assertRaises(socket.error):
            util.create_listeners(('host', 25))


# vim:et:fdm=marker:sts=4:sw=4:ts=4
