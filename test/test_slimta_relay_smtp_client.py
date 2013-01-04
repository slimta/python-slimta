
import unittest

from mox import MoxTestBase, IsA
from gevent.socket import socket
from gevent.queue import Queue

from slimta.relay import TransientRelayError, PermanentRelayError
from slimta.relay.smtp.client import SmtpRelayClient
from slimta.envelope import Envelope


class TestSmtpRelayClient(MoxTestBase):

    def setUp(self):
        super(TestSmtpRelayClient, self).setUp()
        self.sock = self.mox.CreateMock(socket)
        self.sock.fileno = lambda: -1
        self.queue = self.mox.CreateMock(Queue)
        self.tls_args = {'test': 'test'}

    def _socket_creator(self, address):
        return self.sock

    def test_connect(self):
        self.mox.ReplayAll()
        client = SmtpRelayClient(None, self.queue, socket_creator=self._socket_creator)
        client._connect()

    def test_banner(self):
        self.sock.recv(IsA(int)).AndReturn('220 Welcome\r\n')
        self.sock.recv(IsA(int)).AndReturn('420 Not Welcome\r\n')
        self.mox.ReplayAll()
        client = SmtpRelayClient(None, self.queue, socket_creator=self._socket_creator)
        client._connect()
        client._banner()
        with self.assertRaises(TransientRelayError):
            client._banner()

    def test_ehlo(self):
        self.sock.sendall('EHLO test\r\n')
        self.sock.recv(IsA(int)).AndReturn('250-Hello\r\n250 TEST\r\n')
        self.sock.sendall('EHLO test\r\n')
        self.sock.recv(IsA(int)).AndReturn('420 Goodbye\r\n')
        self.mox.ReplayAll()
        client = SmtpRelayClient(None, self.queue, socket_creator=self._socket_creator, ehlo_as='test')
        client._connect()
        client._ehlo()
        with self.assertRaises(TransientRelayError):
            client._ehlo()

    def test_starttls(self):
        sock = self.mox.CreateMockAnything()
        sock.fileno = lambda: -1
        def socket_creator(address):
            return sock
        sock.sendall('STARTTLS\r\n')
        sock.recv(IsA(int)).AndReturn('220 Go ahead\r\n')
        sock.tls_wrapper(sock, self.tls_args).AndReturn(sock)
        sock.sendall('STARTTLS\r\n')
        sock.recv(IsA(int)).AndReturn('420 Stop\r\n')
        self.mox.ReplayAll()
        client = SmtpRelayClient(None, self.queue, socket_creator=socket_creator, tls=self.tls_args, tls_wrapper=sock.tls_wrapper, tls_required=True)
        client._connect()
        client._starttls()
        with self.assertRaises(TransientRelayError):
            client._starttls()

    def test_handshake_tls_immediately(self):
        sock = self.mox.CreateMockAnything()
        sock.fileno = lambda: -1
        def socket_creator(address):
            return sock
        sock.tls_wrapper(sock, self.tls_args).AndReturn(sock)
        sock.recv(IsA(int)).AndReturn('220 Welcome\r\n')
        sock.sendall('EHLO test\r\n')
        sock.recv(IsA(int)).AndReturn('250 Hello\r\n')
        self.mox.ReplayAll()
        client = SmtpRelayClient(None, self.queue, socket_creator=socket_creator, tls=self.tls_args, tls_wrapper=sock.tls_wrapper, tls_immediately=True, ehlo_as='test')
        client._connect()
        client._handshake()

    def test_handshake_starttls(self):
        sock = self.mox.CreateMockAnything()
        sock.fileno = lambda: -1
        def socket_creator(address):
            return sock
        sock.recv(IsA(int)).AndReturn('220 Welcome\r\n')
        sock.sendall('EHLO test\r\n')
        sock.recv(IsA(int)).AndReturn('250 Hello\r\n')
        sock.sendall('STARTTLS\r\n')
        sock.recv(IsA(int)).AndReturn('220 Go ahead\r\n')
        sock.tls_wrapper(sock, self.tls_args).AndReturn(sock)
        sock.sendall('EHLO test\r\n')
        sock.recv(IsA(int)).AndReturn('250 Hello\r\n')
        self.mox.ReplayAll()
        client = SmtpRelayClient(None, self.queue, socket_creator=socket_creator, tls=self.tls_args, tls_wrapper=sock.tls_wrapper, ehlo_as='test')
        client._connect()
        client._handshake()

    def test_rset(self):
        self.sock.sendall('RSET\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 Ok\r\n')
        self.mox.ReplayAll()
        client = SmtpRelayClient(None, self.queue, socket_creator=self._socket_creator)
        client._connect()
        client._rset()

    def test_mailfrom(self):
        self.sock.sendall('MAIL FROM:<sender>\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 Ok\r\n')
        self.sock.sendall('MAIL FROM:<sender>\r\n')
        self.sock.recv(IsA(int)).AndReturn('550 Not Ok\r\n')
        self.mox.ReplayAll()
        client = SmtpRelayClient(None, self.queue, socket_creator=self._socket_creator)
        client._connect()
        client._mailfrom('sender')
        with self.assertRaises(PermanentRelayError):
            client._mailfrom('sender')

    def test_rcptto(self):
        self.sock.sendall('RCPT TO:<recipient>\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 Ok\r\n')
        self.sock.sendall('RCPT TO:<recipient>\r\n')
        self.sock.recv(IsA(int)).AndReturn('550 Not Ok\r\n')
        self.mox.ReplayAll()
        client = SmtpRelayClient(None, self.queue, socket_creator=self._socket_creator)
        client._connect()
        client._rcptto('recipient')
        with self.assertRaises(PermanentRelayError):
            client._rcptto('recipient')


# vim:et:fdm=marker:sts=4:sw=4:ts=4
