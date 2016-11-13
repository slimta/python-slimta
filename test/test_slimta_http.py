import unittest2 as unittest
from mox3.mox import MoxTestBase
from gevent import socket, ssl

from slimta.http import HTTPConnection, HTTPSConnection, get_connection


class TestHTTPConnection(unittest.TestCase, MoxTestBase):

    def test_connect(self):
        self.mox.StubOutWithMock(socket, 'create_connection')
        socket.create_connection(('testhost', 8025), 7, None).AndReturn(9)
        self.mox.ReplayAll()
        conn = HTTPConnection('testhost', 8025, timeout=7)
        conn.connect()
        self.assertEqual(9, conn.sock)


class TestHTTPSConnection(unittest.TestCase, MoxTestBase):

    def test_close(self):
        conn = HTTPSConnection('testhost', 8025)
        conn.sock = self.mox.CreateMockAnything()
        conn.sock.unwrap()
        conn.sock.close()
        self.mox.ReplayAll()
        conn.close()


class TestGetConnection(unittest.TestCase, MoxTestBase):

    def test_get_connection(self):
        conn = get_connection('http://localhost')
        self.assertIsInstance(conn, HTTPConnection)
        conn = get_connection('https://localhost')
        self.assertIsInstance(conn, HTTPSConnection)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
