import email.utils

import unittest2 as unittest
from mox3.mox import MoxTestBase, IsA
from gevent.ssl import SSLSocket
from pysasl import SASLAuth

from slimta.smtp.io import IO
from slimta.smtp.auth import AuthSession, ServerAuthError, \
                             InvalidMechanismError, AuthenticationCanceled


class TestSmtpAuth(unittest.TestCase, MoxTestBase):

    def setUp(self):
        super(TestSmtpAuth, self).setUp()
        self.sock = self.mox.CreateMock(SSLSocket)
        self.sock.fileno = lambda: -1
        self.sock.getpeername = lambda: ('test', 0)
        self.io = IO(self.sock)
        self.make_msgid = email.utils.make_msgid = lambda: '<test@example.com>'

    def test_bytes(self):
        auth = AuthSession(SASLAuth(), self.io)
        self.assertEqual('CRAM-MD5 LOGIN PLAIN', str(auth))

    def test_invalid_mechanism(self):
        auth = AuthSession(SASLAuth(), self.io)
        with self.assertRaises(InvalidMechanismError):
            auth.server_attempt(b'TEST')
        with self.assertRaises(InvalidMechanismError):
            auth.server_attempt(b'B@D')

    def test_plain_noarg(self):
        self.sock.sendall(b'334 \r\n')
        self.sock.recv(IsA(int)).AndReturn(b'dGVzdHppZAB0ZXN0dXNlcgB0ZXN0cGFzc3dvcmQ=\r\n')
        self.mox.ReplayAll()
        auth = AuthSession(SASLAuth(), self.io)
        result = auth.server_attempt(b'PLAIN')
        self.assertEqual(u'testuser', result.authcid)
        self.assertEqual(u'testpassword', result.secret)
        self.assertEqual(u'testzid', result.authzid)

    def test_plain(self):
        self.mox.ReplayAll()
        auth = AuthSession(SASLAuth(), self.io)
        result = auth.server_attempt(b'PLAIN dGVzdHppZAB0ZXN0dXNlcgB0ZXN0cGFzc3dvcmQ=')
        self.assertEqual(u'testuser', result.authcid)
        self.assertEqual(u'testpassword', result.secret)
        self.assertEqual(u'testzid', result.authzid)

    def test_plain_canceled(self):
        self.sock.sendall(b'334 \r\n')
        self.sock.recv(IsA(int)).AndReturn(b'*\r\n')
        self.mox.ReplayAll()
        auth = AuthSession(SASLAuth(), self.io)
        with self.assertRaises(AuthenticationCanceled):
            auth.server_attempt(b'PLAIN')
        with self.assertRaises(AuthenticationCanceled):
            auth.server_attempt(b'PLAIN *')

    def test_login_noarg(self):
        self.sock.sendall(b'334 VXNlcm5hbWU6\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'dGVzdHVzZXI=\r\n')
        self.sock.sendall(b'334 UGFzc3dvcmQ6\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'dGVzdHBhc3N3b3Jk\r\n')
        self.mox.ReplayAll()
        auth = AuthSession(SASLAuth(), self.io)
        result = auth.server_attempt(b'LOGIN')
        self.assertEqual(u'testuser', result.authcid)
        self.assertEqual(u'testpassword', result.secret)
        self.assertEqual(None, result.authzid)

    def test_login(self):
        self.sock.sendall(b'334 UGFzc3dvcmQ6\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'dGVzdHBhc3N3b3Jk\r\n')
        self.mox.ReplayAll()
        auth = AuthSession(SASLAuth(), self.io)
        result = auth.server_attempt(b'LOGIN dGVzdHVzZXI=')
        self.assertEqual(u'testuser', result.authcid)
        self.assertEqual(u'testpassword', result.secret)
        self.assertEqual(None, result.authzid)

    def test_crammd5(self):
        self.sock.sendall(b'334 PHRlc3RAZXhhbXBsZS5jb20+\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'dGVzdHVzZXIgNDkzMzA1OGU2ZjgyOTRkZTE0NDJkMTYxOTI3ZGI5NDQ=\r\n')
        self.mox.ReplayAll()
        auth = AuthSession(SASLAuth(), self.io)
        result = auth.server_attempt(b'CRAM-MD5')
        self.assertEqual(u'testuser', result.authcid)
        self.assertTrue(result.check_secret(u'testpassword'))
        self.assertFalse(result.check_secret(u'testwrong'))
        self.assertEqual(None, result.authzid)

    def test_crammd5_malformed(self):
        self.sock.sendall(b'334 PHRlc3RAZXhhbXBsZS5jb20+\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'bWFsZm9ybWVk\r\n')
        self.mox.ReplayAll()
        auth = AuthSession(SASLAuth(), self.io)
        with self.assertRaises(ServerAuthError):
            auth.server_attempt(b'CRAM-MD5')

    def test_client_bad_mech(self):
        self.sock.sendall(b'AUTH LOGIN\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'535 Nope!\r\n')
        self.mox.ReplayAll()
        auth = AuthSession(SASLAuth(), self.io)
        reply = auth.client_attempt(u'test@example.com', u'asdf',
                                    None, b'LOGIN')
        self.assertEqual('535', reply.code)
        self.assertEqual('5.0.0 Nope!', reply.message)

    def test_client_plain(self):
        self.sock.sendall(b'AUTH PLAIN amtsAHRlc3RAZXhhbXBsZS5jb20AYXNkZg==\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'235 Ok\r\n')
        self.mox.ReplayAll()
        auth = AuthSession(SASLAuth(), self.io)
        reply = auth.client_attempt(u'test@example.com', u'asdf', u'jkl',
                                    b'PLAIN')
        self.assertEqual('235', reply.code)
        self.assertEqual('2.0.0 Ok', reply.message)

    def test_client_login(self):
        self.sock.sendall(b'AUTH LOGIN\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'334 VXNlcm5hbWU6\r\n')
        self.sock.sendall(b'dGVzdEBleGFtcGxlLmNvbQ==\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'334 UGFzc3dvcmQ6\r\n')
        self.sock.sendall(b'YXNkZg==\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'235 Ok\r\n')
        self.mox.ReplayAll()
        auth = AuthSession(SASLAuth(), self.io)
        reply = auth.client_attempt(u'test@example.com', u'asdf',
                                    None, b'LOGIN')
        self.assertEqual('235', reply.code)
        self.assertEqual('2.0.0 Ok', reply.message)

    def test_client_login_bad_username(self):
        self.sock.sendall(b'AUTH LOGIN\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'334 VXNlcm5hbWU6\r\n')
        self.sock.sendall(b'dGVzdEBleGFtcGxlLmNvbQ==\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'535 Nope!\r\n')
        self.mox.ReplayAll()
        auth = AuthSession(SASLAuth(), self.io)
        reply = auth.client_attempt(u'test@example.com', u'asdf',
                                    None, b'LOGIN')
        self.assertEqual('535', reply.code)
        self.assertEqual('5.0.0 Nope!', reply.message)

    def test_client_crammd5(self):
        self.sock.sendall(b'AUTH CRAM-MD5\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'334 dGVzdCBjaGFsbGVuZ2U=\r\n')
        self.sock.sendall(b'dGVzdEBleGFtcGxlLmNvbSA1Yzk1OTBjZGE3ZTgxMDY5Mzk2ZjhiYjlkMzU1MzE1Yg==\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'235 Ok\r\n')
        self.mox.ReplayAll()
        auth = AuthSession(SASLAuth(), self.io)
        reply = auth.client_attempt(u'test@example.com', u'asdf',
                                    None, b'CRAM-MD5')
        self.assertEqual('235', reply.code)
        self.assertEqual('2.0.0 Ok', reply.message)

    def test_client_xoauth2(self):
        self.sock.sendall(b'AUTH XOAUTH2 dXNlcj10ZXN0QGV4YW1wbGUuY29tAWF1dGg9QmVhcmVyYXNkZgEB\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'235 Ok\r\n')
        self.mox.ReplayAll()
        auth = AuthSession(SASLAuth(), self.io)
        reply = auth.client_attempt(u'test@example.com', u'asdf',
                                    None, b'XOAUTH2')
        self.assertEqual('235', reply.code)
        self.assertEqual('2.0.0 Ok', reply.message)

    def test_client_xoauth2_error(self):
        self.sock.sendall(b'AUTH XOAUTH2 dXNlcj10ZXN0QGV4YW1wbGUuY29tAWF1dGg9QmVhcmVyYXNkZgEB\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'334 eyJzdGF0dXMiOiI0MDEiLCJzY2hlbWVzIjoiYmVhcmVyIG1hYyIsInNjb3BlIjoiaHR0cHM6Ly9tYWlsLmdvb2dsZS5jb20vIn0K\r\n')
        self.sock.sendall(b'\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'535 Nope!\r\n')
        self.mox.ReplayAll()
        auth = AuthSession(SASLAuth(), self.io)
        reply = auth.client_attempt(u'test@example.com', u'asdf',
                                    None, b'XOAUTH2')
        self.assertEqual('535', reply.code)
        self.assertEqual('5.0.0 Nope!', reply.message)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
