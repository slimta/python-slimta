
import unittest

from mox import MoxTestBase, IsA
from gevent import socket, ssl

from slimta.http import HTTPConnection, HTTPSConnection, get_connection


class TestHTTPConnection(MoxTestBase):

    def test_connect(self):
        self.mox.StubOutWithMock(socket, 'create_connection')
        socket.create_connection(('testhost', 8025), 7, 8).AndReturn(9)
        self.mox.ReplayAll()
        conn = HTTPConnection('testhost', 8025, True, 7, 8)
        conn.connect()
        self.assertEqual(9, conn.sock)


class TestHTTPSConnection(MoxTestBase):

    def test_connect(self):
        self.mox.StubOutWithMock(socket, 'create_connection')
        self.mox.StubOutWithMock(ssl, 'SSLSocket')
        sslsock = self.mox.CreateMockAnything()
        socket.create_connection(('testhost', 8025), 7, 8).AndReturn(9)
        ssl.SSLSocket(9, var='val').AndReturn(sslsock)
        sslsock.do_handshake()
        self.mox.ReplayAll()
        conn = HTTPSConnection('testhost', 8025, {'var': 'val'}, True, 7, 8)
        conn.connect()
        self.assertEqual(sslsock, conn.sock)

    def test_close(self):
        conn = HTTPSConnection('testhost', 8025, {'var': 'val'}, True, 7, 8)
        conn.sock = self.mox.CreateMockAnything()
        conn.sock.unwrap()
        conn.sock.close()
        self.mox.ReplayAll()
        conn.close()


class TestGetConnection(MoxTestBase):

    def test_get_connection(self):
        conn = get_connection('http://localhost')
        self.assertIsInstance(conn, HTTPConnection)
        conn = get_connection('https://localhost')
        self.assertIsInstance(conn, HTTPSConnection)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
