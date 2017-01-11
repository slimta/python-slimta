import unittest
from mox3.mox import MoxTestBase
from gevent import socket

from slimta.http import HTTPConnection, HTTPSConnection, get_connection


class TestHTTPConnection(MoxTestBase, unittest.TestCase):

    def test_init(self):
        conn = HTTPConnection('testhost', 8025, timeout=7)
        self.assertEqual(conn._create_connection, socket.create_connection)


class TestHTTPSConnection(MoxTestBase, unittest.TestCase):

    def test_close(self):
        conn = HTTPSConnection('testhost', 8025)
        conn.sock = self.mox.CreateMockAnything()
        conn.sock.unwrap()
        conn.sock.close()
        self.mox.ReplayAll()
        conn.close()


class TestGetConnection(MoxTestBase, unittest.TestCase):

    def test_get_connection(self):
        conn = get_connection('http://localhost')
        self.assertIsInstance(conn, HTTPConnection)
        conn = get_connection('https://localhost')
        self.assertIsInstance(conn, HTTPSConnection)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
