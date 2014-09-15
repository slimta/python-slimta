
from assertions import *

from mox import MoxTestBase, IsA
from gevent.socket import socket

from slimta.smtp.io import IO
from slimta.smtp.auth import Auth, AuthSession, CredentialsInvalidError, \
                             ServerAuthError, InvalidMechanismError, \
                             AuthenticationCanceled
from slimta.smtp.auth.standard import *
from slimta.smtp.auth.oauth import OAuth2


class StaticCramMd5(CramMd5):

    def _build_initial_challenge(self):
        return '<test@example.com>'


class FakeAuth(Auth):

    def verify_secret(self, cid, secret, zid=None):
        if cid != 'testuser' or secret != 'testpassword':
            raise CredentialsInvalidError()
        if zid is not None and zid != 'testzid':
            raise CredentialsInvalidError()
        return 'testidentity'

    def get_secret(self, cid, zid=None):
        if cid != 'testuser':
            raise CredentialsInvalidError()
        if zid is not None and zid != 'testzid':
            raise CredentialsInvalidError()
        return 'testpassword', 'testidentity'

    def get_available_mechanisms(self, encrypted):
        return [Plain, Login, StaticCramMd5]


class FakeAuthNoSecure(Auth):

    def get_available_mechanisms(self, encrypted):
        if encrypted:
            return [Plain, Login]
        else:
            return []


class FakeAuthWithGetSecret(Auth):

    def get_secret(self, *args):
        raise CredentialsInvalidError()


class FakeSession(object):

    def __init__(self, encrypted):
        self.encrypted = encrypted


class TestSmtpAuth(MoxTestBase):

    def setUp(self):
        super(TestSmtpAuth, self).setUp()
        self.sock = self.mox.CreateMock(socket)
        self.sock.fileno = lambda: -1

    def test_get_available_mechanisms(self):
        auth = Auth()
        assert_equal([CramMd5], auth.get_available_mechanisms())
        assert_equal([CramMd5, Plain, Login],
                     auth.get_available_mechanisms(True))

    def test_str(self):
        auth = AuthSession(FakeAuthWithGetSecret(), FakeSession(False))
        assert_equal('CRAM-MD5', str(auth))
        auth = AuthSession(Auth(), FakeSession(True))
        assert_equal('PLAIN LOGIN', str(auth))

    def test_str_no_secure_mechanisms(self):
        auth = AuthSession(FakeAuthNoSecure(), FakeSession(True))
        assert_equal('PLAIN LOGIN', str(auth))
        auth = AuthSession(FakeAuthNoSecure(), FakeSession(False))
        with assert_raises(ValueError):
            str(auth)

    def test_unimplemented_means_invalid(self):
        auth = FakeAuthWithGetSecret()
        with assert_raises(CredentialsInvalidError):
            auth.verify_secret('user', 'pass')
        with assert_raises(CredentialsInvalidError):
            auth.get_secret('user')

    def test_invalid_mechanism(self):
        auth = AuthSession(FakeAuth(), FakeSession(True))
        with assert_raises(InvalidMechanismError):
            auth.server_attempt(None, 'TEST')
        with assert_raises(InvalidMechanismError):
            auth.server_attempt(None, 'B@D')

    def test_plain_noarg(self):
        self.sock.sendall('334 \r\n')
        self.sock.recv(IsA(int)).AndReturn('dGVzdHppZAB0ZXN0dXNlcgB0ZXN0cGFzc3dvcmQ=\r\n')
        self.mox.ReplayAll()
        io = IO(self.sock)
        auth = AuthSession(FakeAuth(), FakeSession(True))
        identity = auth.server_attempt(io, 'PLAIN')
        assert_equal('testidentity', identity)

    def test_plain(self):
        self.mox.ReplayAll()
        io = IO(self.sock)
        auth = AuthSession(FakeAuth(), FakeSession(True))
        identity = auth.server_attempt(io, 'PLAIN dGVzdHppZAB0ZXN0dXNlcgB0ZXN0cGFzc3dvcmQ=')
        assert_equal('testidentity', identity)

    def test_plain_badcreds(self):
        self.mox.ReplayAll()
        io = IO(self.sock)
        auth = AuthSession(FakeAuth(), FakeSession(True))
        with assert_raises(CredentialsInvalidError):
            auth.server_attempt(io, 'PLAIN dGVzdHppZAB0ZXN0dXNlcgBiYWRwYXNzd29yZA==')
        with assert_raises(ServerAuthError):
            auth.server_attempt(io, 'PLAIN dGVzdGluZw==')

    def test_plain_canceled(self):
        self.sock.sendall('334 \r\n')
        self.sock.recv(IsA(int)).AndReturn('*\r\n')
        self.mox.ReplayAll()
        io = IO(self.sock)
        auth = AuthSession(FakeAuth(), FakeSession(True))
        with assert_raises(AuthenticationCanceled):
            auth.server_attempt(io, 'PLAIN')
        with assert_raises(AuthenticationCanceled):
            auth.server_attempt(io, 'PLAIN *')

    def test_login_noarg(self):
        self.sock.sendall('334 VXNlcm5hbWU6\r\n')
        self.sock.recv(IsA(int)).AndReturn('dGVzdHVzZXI=\r\n')
        self.sock.sendall('334 UGFzc3dvcmQ6\r\n')
        self.sock.recv(IsA(int)).AndReturn('dGVzdHBhc3N3b3Jk\r\n')
        self.mox.ReplayAll()
        io = IO(self.sock)
        auth = AuthSession(FakeAuth(), FakeSession(True))
        identity = auth.server_attempt(io, 'LOGIN')
        assert_equal('testidentity', identity)

    def test_login(self):
        self.sock.sendall('334 UGFzc3dvcmQ6\r\n')
        self.sock.recv(IsA(int)).AndReturn('dGVzdHBhc3N3b3Jk\r\n')
        self.mox.ReplayAll()
        io = IO(self.sock)
        auth = AuthSession(FakeAuth(), FakeSession(True))
        identity = auth.server_attempt(io, 'LOGIN dGVzdHVzZXI=')
        assert_equal('testidentity', identity)

    def test_crammd5(self):
        self.sock.sendall('334 PHRlc3RAZXhhbXBsZS5jb20+\r\n')
        self.sock.recv(IsA(int)).AndReturn('dGVzdHVzZXIgNDkzMzA1OGU2ZjgyOTRkZTE0NDJkMTYxOTI3ZGI5NDQ=\r\n')
        self.mox.ReplayAll()
        io = IO(self.sock)
        auth = AuthSession(FakeAuth(), FakeSession(True))
        identity = auth.server_attempt(io, 'CRAM-MD5 dGVzdHVzZXI=')
        assert_equal('testidentity', identity)

    def test_crammd5_badcreds(self):
        self.sock.sendall('334 PHRlc3RAZXhhbXBsZS5jb20+\r\n')
        self.sock.recv(IsA(int)).AndReturn('dGVzdHVzZXIgMTIzNDU2Nzg5MA==\r\n')
        self.mox.ReplayAll()
        io = IO(self.sock)
        auth = AuthSession(FakeAuth(), FakeSession(True))
        with assert_raises(CredentialsInvalidError):
            auth.server_attempt(io, 'CRAM-MD5 dGVzdHVzZXI=')

    def test_crammd5_malformed(self):
        self.sock.sendall('334 PHRlc3RAZXhhbXBsZS5jb20+\r\n')
        self.sock.recv(IsA(int)).AndReturn('bWFsZm9ybWVk\r\n')
        self.mox.ReplayAll()
        io = IO(self.sock)
        auth = AuthSession(FakeAuth(), FakeSession(True))
        with assert_raises(ServerAuthError):
            auth.server_attempt(io, 'CRAM-MD5 dGVzdHVzZXI=')

    def test_client_plain(self):
        self.sock.sendall('AUTH PLAIN amtsAHRlc3RAZXhhbXBsZS5jb20AYXNkZg==\r\n')
        self.sock.recv(IsA(int)).AndReturn('235 Ok\r\n')
        self.mox.ReplayAll()
        io = IO(self.sock)
        reply = Plain.client_attempt(io, 'test@example.com', 'asdf', 'jkl')
        assert_equal('235', reply.code)
        assert_equal('2.0.0 Ok', reply.message)

    def test_client_login(self):
        self.sock.sendall('AUTH LOGIN\r\n')
        self.sock.recv(IsA(int)).AndReturn('334 VXNlcm5hbWU6\r\n')
        self.sock.sendall('dGVzdEBleGFtcGxlLmNvbQ==\r\n')
        self.sock.recv(IsA(int)).AndReturn('334 UGFzc3dvcmQ6\r\n')
        self.sock.sendall('YXNkZg==\r\n')
        self.sock.recv(IsA(int)).AndReturn('235 Ok\r\n')
        self.mox.ReplayAll()
        io = IO(self.sock)
        reply = Login.client_attempt(io, 'test@example.com', 'asdf', None)
        assert_equal('235', reply.code)
        assert_equal('2.0.0 Ok', reply.message)

    def test_client_login_bad_mech(self):
        self.sock.sendall('AUTH LOGIN\r\n')
        self.sock.recv(IsA(int)).AndReturn('535 Nope!\r\n')
        self.mox.ReplayAll()
        io = IO(self.sock)
        reply = Login.client_attempt(io, 'test@example.com', 'asdf', None)
        assert_equal('535', reply.code)
        assert_equal('5.0.0 Nope!', reply.message)

    def test_client_login_bad_username(self):
        self.sock.sendall('AUTH LOGIN\r\n')
        self.sock.recv(IsA(int)).AndReturn('334 VXNlcm5hbWU6\r\n')
        self.sock.sendall('dGVzdEBleGFtcGxlLmNvbQ==\r\n')
        self.sock.recv(IsA(int)).AndReturn('535 Nope!\r\n')
        self.mox.ReplayAll()
        io = IO(self.sock)
        reply = Login.client_attempt(io, 'test@example.com', 'asdf', None)
        assert_equal('535', reply.code)
        assert_equal('5.0.0 Nope!', reply.message)

    def test_client_crammd5(self):
        self.sock.sendall('AUTH CRAM-MD5\r\n')
        self.sock.recv(IsA(int)).AndReturn('334 dGVzdCBjaGFsbGVuZ2U=\r\n')
        self.sock.sendall('dGVzdEBleGFtcGxlLmNvbSA1Yzk1OTBjZGE3ZTgxMDY5Mzk2ZjhiYjlkMzU1MzE1Yg==\r\n')
        self.sock.recv(IsA(int)).AndReturn('235 Ok\r\n')
        self.mox.ReplayAll()
        io = IO(self.sock)
        reply = CramMd5.client_attempt(io, 'test@example.com', 'asdf', None)
        assert_equal('235', reply.code)
        assert_equal('2.0.0 Ok', reply.message)

    def test_client_crammd5_bad_mech(self):
        self.sock.sendall('AUTH CRAM-MD5\r\n')
        self.sock.recv(IsA(int)).AndReturn('535 Nope!\r\n')
        self.mox.ReplayAll()
        io = IO(self.sock)
        reply = CramMd5.client_attempt(io, 'test@example.com', 'asdf', None)
        assert_equal('535', reply.code)
        assert_equal('5.0.0 Nope!', reply.message)

    def test_client_xoauth2(self):
        self.sock.sendall('AUTH XOAUTH2 dXNlcj10ZXN0QGV4YW1wbGUuY29tAWF1dGg9QmVhcmVyYXNkZgEB\r\n')
        self.sock.recv(IsA(int)).AndReturn('235 Ok\r\n')
        self.mox.ReplayAll()
        io = IO(self.sock)
        reply = OAuth2.client_attempt(io, 'test@example.com', 'asdf', None)
        assert_equal('235', reply.code)
        assert_equal('2.0.0 Ok', reply.message)

    def test_client_xoauth2_error(self):
        self.sock.sendall('AUTH XOAUTH2 dXNlcj10ZXN0QGV4YW1wbGUuY29tAWF1dGg9QmVhcmVyYXNkZgEB\r\n')
        self.sock.recv(IsA(int)).AndReturn('334 eyJzdGF0dXMiOiI0MDEiLCJzY2hlbWVzIjoiYmVhcmVyIG1hYyIsInNjb3BlIjoiaHR0cHM6Ly9tYWlsLmdvb2dsZS5jb20vIn0K\r\n')
        self.sock.sendall('\r\n')
        self.sock.recv(IsA(int)).AndReturn('535 Nope!\r\n')
        self.mox.ReplayAll()
        io = IO(self.sock)
        reply = OAuth2.client_attempt(io, 'test@example.com', 'asdf', None)
        assert_equal('535', reply.code)
        assert_equal('5.0.0 Nope!', reply.message)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
