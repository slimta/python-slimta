
import unittest

from slimta.smtp.io import IO
from slimta.smtp.auth import Auth, CredentialsInvalidError, ServerAuthError, \
                             InvalidMechanismError, AuthenticationCanceled
from slimta.smtp.auth.mechanisms import *

from mock.socket import MockSocket


class StaticCramMd5(CramMd5):

    def _build_initial_challenge(self):
        return '<test@example.com>'


class FakeAuth(Auth):

    def verify_secret(self, cid, secret, zid=None):
        if cid != 'testuser' or secret != 'testpassword':
            raise CredentialsInvalidError()
        if zid is not None and zid != 'testzid':
            raise CredentialsInvalidError()

    def get_secret(self, cid, zid=None):
        if cid != 'testuser':
            raise CredentialsInvalidError()
        if zid is not None and zid != 'testzid':
            raise CredentialsInvalidError()
        return 'testpassword', None

    def get_available_mechanisms(self, encrypted=False):
        return [Plain, Login, StaticCramMd5]


class FakeSession(object):

    def __init__(self, encrypted):
        self.encrypted = encrypted


class TestSmtpAuth(unittest.TestCase):

    def test_get_available_mechanisms(self):
        auth = Auth(None)
        self.assertEqual([CramMd5], auth.get_available_mechanisms())
        self.assertEqual([Plain, Login, CramMd5],
                         auth.get_available_mechanisms(True))

    def test_str(self):
        auth = Auth(FakeSession(False))
        self.assertEqual('CRAM-MD5', str(auth))
        auth = Auth(FakeSession(True))
        self.assertEqual('PLAIN LOGIN CRAM-MD5', str(auth))

    def test_unimplemented_means_invalid(self):
        auth = Auth(None)
        with self.assertRaises(CredentialsInvalidError):
            auth.verify_secret('user', 'pass')
        with self.assertRaises(CredentialsInvalidError):
            auth.get_secret('user')

    def test_invalid_mechanism(self):
        auth = FakeAuth(FakeSession(True))
        with self.assertRaises(InvalidMechanismError):
            auth.server_attempt(None, 'TEST')
        with self.assertRaises(InvalidMechanismError):
            auth.server_attempt(None, 'B@D')

    def test_plain_noarg(self):
        sock = MockSocket([('send', '334 \r\n'),
                           ('recv', 'dGVzdHppZAB0ZXN0dXNlcgB0ZXN0cGFzc3dvcmQ=\r\n')])
        io = IO(sock)
        auth = FakeAuth(FakeSession(True))
        auth.server_attempt(io, 'PLAIN')
        sock.assert_done(self)

    def test_plain(self):
        sock = MockSocket([])
        io = IO(sock)
        auth = FakeAuth(FakeSession(True))
        auth.server_attempt(io, 'PLAIN dGVzdHppZAB0ZXN0dXNlcgB0ZXN0cGFzc3dvcmQ=')
        sock.assert_done(self)

    def test_plain_badcreds(self):
        sock = MockSocket([])
        io = IO(sock)
        auth = FakeAuth(FakeSession(True))
        with self.assertRaises(CredentialsInvalidError):
            auth.server_attempt(io, 'PLAIN dGVzdHppZAB0ZXN0dXNlcgBiYWRwYXNzd29yZA==')
        with self.assertRaises(ServerAuthError):
            auth.server_attempt(io, 'PLAIN dGVzdGluZw==')
        sock.assert_done(self)

    def test_plain_canceled(self):
        sock = MockSocket([('send', '334 \r\n'),
                           ('recv', '*\r\n')])
        io = IO(sock)
        auth = FakeAuth(FakeSession(True))
        with self.assertRaises(AuthenticationCanceled):
            auth.server_attempt(io, 'PLAIN')
        sock.assert_done(self)
        with self.assertRaises(AuthenticationCanceled):
            auth.server_attempt(io, 'PLAIN *')

    def test_login_noarg(self):
        sock = MockSocket([('send', '334 VXNlcm5hbWU6\r\n'),
                           ('recv', 'dGVzdHVzZXI=\r\n'),
                           ('send', '334 UGFzc3dvcmQ6\r\n'),
                           ('recv', 'dGVzdHBhc3N3b3Jk\r\n')])
        io = IO(sock)
        auth = FakeAuth(FakeSession(True))
        auth.server_attempt(io, 'LOGIN')
        sock.assert_done(self)

    def test_login(self):
        sock = MockSocket([('send', '334 UGFzc3dvcmQ6\r\n'),
                           ('recv', 'dGVzdHBhc3N3b3Jk\r\n')])
        io = IO(sock)
        auth = FakeAuth(FakeSession(True))
        auth.server_attempt(io, 'LOGIN dGVzdHVzZXI=')
        sock.assert_done(self)

    def test_crammd5(self):
        sock = MockSocket([('send', '334 PHRlc3RAZXhhbXBsZS5jb20+\r\n'),
                           ('recv', 'dGVzdHVzZXIgNDkzMzA1OGU2ZjgyOTRkZTE0NDJkMTYxOTI3ZGI5NDQ=\r\n')])
        io = IO(sock)
        auth = FakeAuth(FakeSession(True))
        auth.server_attempt(io, 'CRAM-MD5 dGVzdHVzZXI=')
        sock.assert_done(self)

    def test_crammd5_badcreds(self):
        sock = MockSocket([('send', '334 PHRlc3RAZXhhbXBsZS5jb20+\r\n'),
                           ('recv', 'dGVzdHVzZXIgMTIzNDU2Nzg5MA==\r\n')])
        io = IO(sock)
        auth = FakeAuth(FakeSession(True))
        with self.assertRaises(CredentialsInvalidError):
            auth.server_attempt(io, 'CRAM-MD5 dGVzdHVzZXI=')
        sock.assert_done(self)

    def test_crammd5_malformed(self):
        sock = MockSocket([('send', '334 PHRlc3RAZXhhbXBsZS5jb20+\r\n'),
                           ('recv', 'bWFsZm9ybWVk\r\n')])
        io = IO(sock)
        auth = FakeAuth(FakeSession(True))
        with self.assertRaises(ServerAuthError):
            auth.server_attempt(io, 'CRAM-MD5 dGVzdHVzZXI=')
        sock.assert_done(self)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
