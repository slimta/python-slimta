import unittest2 as unittest
from mox3.mox import MoxTestBase, IgnoreArg
from gevent import socket

from slimta import util


class TestIPv4SocketCreator(MoxTestBase):

    def setUp(self):
        super(TestIPv4SocketCreator, self).setUp()
        self.mox.StubOutWithMock(socket, 'create_connection')
        self.mox.StubOutWithMock(socket, 'getaddrinfo')
        self.getaddrinfo = self.mox.CreateMock(socket.getaddrinfo)
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


# vim:et:fdm=marker:sts=4:sw=4:ts=4
