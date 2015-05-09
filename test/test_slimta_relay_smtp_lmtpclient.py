
from email.encoders import encode_base64

import unittest2 as unittest
from mox import MoxTestBase, IsA
from gevent import Timeout
from gevent.socket import socket, error as socket_error
from gevent.event import AsyncResult

from slimta.util.deque import BlockingDeque
from slimta.smtp import ConnectionLost, SmtpError
from slimta.relay import TransientRelayError, PermanentRelayError
from slimta.relay.smtp.lmtpclient import LmtpRelayClient
from slimta.envelope import Envelope


class TestLmtpRelayClient(unittest.TestCase, MoxTestBase):

    def setUp(self):
        super(TestLmtpRelayClient, self).setUp()
        self.sock = self.mox.CreateMock(socket)
        self.sock.fileno = lambda: -1
        self.queue = self.mox.CreateMock(BlockingDeque)
        self.tls_args = {'test': 'test'}

    def _socket_creator(self, address):
        return self.sock

    def test_lhlo(self):
        self.sock.sendall('LHLO test\r\n')
        self.sock.recv(IsA(int)).AndReturn('250-Hello\r\n250 TEST\r\n')
        self.sock.sendall('LHLO test\r\n')
        self.sock.recv(IsA(int)).AndReturn('420 Goodbye\r\n')
        self.mox.ReplayAll()
        client = LmtpRelayClient(None, self.queue, socket_creator=self._socket_creator, ehlo_as='test')
        client._connect()
        client._ehlo()
        with self.assertRaises(TransientRelayError):
            client._ehlo()

    def test_deliver(self):
        result = self.mox.CreateMock(AsyncResult)
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse('From: sender@example.com\r\n\r\ntest test \x81\r\n')
        self.sock.sendall('LHLO test\r\n')
        self.sock.recv(IsA(int)).AndReturn('250-Hello\r\n250 8BITMIME\r\n')
        self.sock.sendall('MAIL FROM:<sender@example.com>\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 Ok\r\n')
        self.sock.sendall('RCPT TO:<rcpt@example.com>\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 Ok\r\n')
        self.sock.sendall('DATA\r\n')
        self.sock.recv(IsA(int)).AndReturn('354 Go ahead\r\n')
        self.sock.sendall('From: sender@example.com\r\n\r\ntest test \x81\r\n.\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 Ok\r\n')
        result.set([None])
        self.mox.ReplayAll()
        client = LmtpRelayClient(None, self.queue, socket_creator=self._socket_creator, ehlo_as='test')
        client._connect()
        client._ehlo()
        client._deliver(result, env)

    def test_deliver_badpipeline(self):
        result = self.mox.CreateMock(AsyncResult)
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse('From: sender@example.com\r\n\r\ntest test\r\n')
        self.sock.sendall('LHLO test\r\n')
        self.sock.recv(IsA(int)).AndReturn('250-Hello\r\n250 PIPELINING\r\n')
        self.sock.sendall('MAIL FROM:<sender@example.com>\r\nRCPT TO:<rcpt@example.com>\r\nDATA\r\n')
        self.sock.recv(IsA(int)).AndReturn('550 Not ok\r\n250 Ok\r\n354 Go ahead\r\n')
        result.set_exception(IsA(PermanentRelayError))
        self.sock.sendall('.\r\nRSET\r\n')
        self.sock.recv(IsA(int)).AndReturn('550 Yikes\r\n250 Ok\r\n')
        self.mox.ReplayAll()
        client = LmtpRelayClient(None, self.queue, socket_creator=self._socket_creator, ehlo_as='test')
        client._connect()
        client._ehlo()
        client._deliver(result, env)

    def test_deliver_multircpt(self):
        result = self.mox.CreateMock(AsyncResult)
        env = Envelope('sender@example.com', ['rcpt1@example.com', 'rcpt2@example.com', 'rcpt3@example.com'])
        env.parse('From: sender@example.com\r\n\r\ntest test\r\n')
        self.sock.sendall('LHLO test\r\n')
        self.sock.recv(IsA(int)).AndReturn('250-Hello\r\n250 PIPELINING\r\n')
        self.sock.sendall('MAIL FROM:<sender@example.com>\r\nRCPT TO:<rcpt1@example.com>\r\nRCPT TO:<rcpt2@example.com>\r\nRCPT TO:<rcpt3@example.com>\r\nDATA\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 Ok\r\n250 Ok\r\n550 Nope\r\n250 Ok\r\n354 Go ahead\r\n')
        self.sock.sendall('From: sender@example.com\r\n\r\ntest test\r\n.\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 Ok\r\n450 Yikes\r\n')
        result.set([None, IsA(PermanentRelayError), IsA(TransientRelayError)])
        self.sock.sendall('RSET\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 Ok\r\n')
        self.mox.ReplayAll()
        client = LmtpRelayClient(None, self.queue, socket_creator=self._socket_creator, ehlo_as='test')
        client._connect()
        client._ehlo()
        client._deliver(result, env)

    def test_deliver_badrcpts(self):
        result = self.mox.CreateMock(AsyncResult)
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse('From: sender@example.com\r\n\r\ntest test\r\n')
        self.sock.sendall('LHLO test\r\n')
        self.sock.recv(IsA(int)).AndReturn('250-Hello\r\n250 PIPELINING\r\n')
        self.sock.sendall('MAIL FROM:<sender@example.com>\r\nRCPT TO:<rcpt@example.com>\r\nDATA\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 Ok\r\n550 Not ok\r\n354 Go ahead\r\n')
        self.sock.sendall('.\r\nRSET\r\n')
        self.sock.recv(IsA(int)).AndReturn('550 Yikes\r\n250 Ok\r\n')
        result.set_exception(IsA(PermanentRelayError))
        self.mox.ReplayAll()
        client = LmtpRelayClient(None, self.queue, socket_creator=self._socket_creator, ehlo_as='test')
        client._connect()
        client._ehlo()
        client._deliver(result, env)

    def test_deliver_rset_exception(self):
        result = self.mox.CreateMock(AsyncResult)
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse('From: sender@example.com\r\n\r\ntest test\r\n')
        self.sock.sendall('LHLO test\r\n')
        self.sock.recv(IsA(int)).AndReturn('250-Hello\r\n250 PIPELINING\r\n')
        self.sock.sendall('MAIL FROM:<sender@example.com>\r\nRCPT TO:<rcpt@example.com>\r\nDATA\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 Ok\r\n250 Ok\r\n450 No!\r\n')
        result.set_exception(IsA(TransientRelayError))
        self.sock.sendall('RSET\r\n')
        self.sock.recv(IsA(int)).AndRaise(ConnectionLost)
        self.mox.ReplayAll()
        client = LmtpRelayClient(None, self.queue, socket_creator=self._socket_creator, ehlo_as='test')
        client._connect()
        client._ehlo()
        with self.assertRaises(ConnectionLost):
            client._deliver(result, env)

    def test_deliver_conversion(self):
        result = self.mox.CreateMock(AsyncResult)
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse('From: sender@example.com\r\n\r\ntest test \x81\r\n')
        self.sock.sendall('LHLO test\r\n')
        self.sock.recv(IsA(int)).AndReturn('250-Hello\r\n250 PIPELINING\r\n')
        self.sock.sendall('MAIL FROM:<sender@example.com>\r\nRCPT TO:<rcpt@example.com>\r\nDATA\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 Ok\r\n250 Ok\r\n354 Go ahead\r\n')
        self.sock.sendall('From: sender@example.com\r\nContent-Transfer-Encoding: base64\r\n\r\ndGVzdCB0ZXN0IIENCg==\n\r\n.\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 Ok\r\n')
        result.set([None])
        self.mox.ReplayAll()
        client = LmtpRelayClient(None, self.queue, socket_creator=self._socket_creator, ehlo_as='test', binary_encoder=encode_base64)
        client._connect()
        client._ehlo()
        client._deliver(result, env)

    def test_deliver_conversion_failure(self):
        result = self.mox.CreateMock(AsyncResult)
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse('From: sender@example.com\r\n\r\ntest test \x81\r\n')
        self.sock.sendall('LHLO test\r\n')
        self.sock.recv(IsA(int)).AndReturn('250-Hello\r\n250 PIPELINING\r\n')
        self.sock.sendall('RSET\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 Ok\r\n')
        result.set_exception(IsA(PermanentRelayError))
        self.mox.ReplayAll()
        client = LmtpRelayClient(None, self.queue, socket_creator=self._socket_creator, ehlo_as='test')
        client._connect()
        client._ehlo()
        client._deliver(result, env)

    def test_disconnect(self):
        self.sock.sendall('QUIT\r\n')
        self.sock.recv(IsA(int)).AndReturn('221 Goodbye\r\n')
        self.sock.close()
        self.mox.ReplayAll()
        client = LmtpRelayClient(None, self.queue, socket_creator=self._socket_creator, ehlo_as='test')
        client._connect()
        client._disconnect()

    def test_disconnect_failure(self):
        self.sock.sendall('QUIT\r\n')
        self.sock.recv(IsA(int)).AndRaise(socket_error(None, None))
        self.sock.close()
        self.mox.ReplayAll()
        client = LmtpRelayClient(None, self.queue, socket_creator=self._socket_creator, ehlo_as='test')
        client._connect()
        client._disconnect()


# vim:et:fdm=marker:sts=4:sw=4:ts=4
