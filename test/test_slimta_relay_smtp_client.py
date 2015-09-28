
from email.encoders import encode_base64

import unittest2 as unittest
from mox import MoxTestBase, IsA
from gevent import Timeout
from gevent.socket import socket, error as socket_error
from gevent.event import AsyncResult
from pysasl.plain import PlainMechanism

from slimta.util.deque import BlockingDeque
from slimta.smtp import ConnectionLost, SmtpError
from slimta.relay import TransientRelayError, PermanentRelayError
from slimta.relay.smtp.client import SmtpRelayClient
from slimta.envelope import Envelope


class TestSmtpRelayClient(unittest.TestCase, MoxTestBase):

    def setUp(self):
        super(TestSmtpRelayClient, self).setUp()
        self.sock = self.mox.CreateMock(socket)
        self.sock.fileno = lambda: -1
        self.queue = self.mox.CreateMock(BlockingDeque)
        self.tls_args = {'test': 'test'}

    def _socket_creator(self, address):
        return self.sock

    def test_connect(self):
        self.mox.ReplayAll()
        client = SmtpRelayClient(None, self.queue, socket_creator=self._socket_creator)
        client._connect()

    def test_connect_failure(self):
        def socket_creator(address):
            raise socket_error(None, None)
        self.mox.ReplayAll()
        client = SmtpRelayClient(None, self.queue, socket_creator=socket_creator)
        with self.assertRaises(TransientRelayError):
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
        sock.recv(IsA(int)).AndReturn('250-Hello\r\n250 STARTTLS\r\n')
        sock.sendall('STARTTLS\r\n')
        sock.recv(IsA(int)).AndReturn('220 Go ahead\r\n')
        sock.tls_wrapper(sock, self.tls_args).AndReturn(sock)
        sock.sendall('EHLO test\r\n')
        sock.recv(IsA(int)).AndReturn('250 Hello\r\n')
        self.mox.ReplayAll()
        client = SmtpRelayClient(None, self.queue, socket_creator=socket_creator, tls=self.tls_args, tls_wrapper=sock.tls_wrapper, ehlo_as='test')
        client._connect()
        client._handshake()

    def test_handshake_authenticate(self):
        sock = self.mox.CreateMockAnything()
        sock.fileno = lambda: -1
        def socket_creator(address):
            return sock
        sock.recv(IsA(int)).AndReturn('220 Welcome\r\n')
        sock.sendall('EHLO test\r\n')
        sock.recv(IsA(int)).AndReturn('250-Hello\r\n250 AUTH PLAIN\r\n')
        sock.sendall('AUTH PLAIN AHRlc3RAZXhhbXBsZS5jb20AcGFzc3dk\r\n')
        sock.recv(IsA(int)).AndReturn('235 Ok\r\n')
        self.mox.ReplayAll()
        client = SmtpRelayClient(None, self.queue, socket_creator=socket_creator, credentials=('test@example.com', 'passwd'), ehlo_as='test')
        client._connect()
        client._handshake()

    def test_handshake_authenticate_callable(self):
        sock = self.mox.CreateMockAnything()
        sock.fileno = lambda: -1
        def socket_creator(address):
            return sock
        sock.recv(IsA(int)).AndReturn('220 Welcome\r\n')
        sock.sendall('EHLO test\r\n')
        sock.recv(IsA(int)).AndReturn('250-Hello\r\n250 AUTH PLAIN\r\n')
        sock.sendall('AUTH PLAIN AHRlc3RAZXhhbXBsZS5jb20AcGFzc3dk\r\n')
        sock.recv(IsA(int)).AndReturn('235 Ok\r\n')
        self.mox.ReplayAll()
        def yield_creds():
            yield 'test@example.com'
            yield 'passwd'
        client = SmtpRelayClient(None, self.queue, socket_creator=socket_creator, credentials=yield_creds, ehlo_as='test')
        client._connect()
        client._handshake()

    def test_rset(self):
        self.sock.sendall('RSET\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 Ok\r\n')
        self.mox.ReplayAll()
        client = SmtpRelayClient(None, self.queue, socket_creator=self._socket_creator)
        client._connect()
        client._rset()

    def test_handshake_authenticate_badcreds(self):
        sock = self.mox.CreateMockAnything()
        sock.fileno = lambda: -1
        def socket_creator(address):
            return sock
        sock.recv(IsA(int)).AndReturn('220 Welcome\r\n')
        sock.sendall('EHLO test\r\n')
        sock.recv(IsA(int)).AndReturn('250-Hello\r\n250 AUTH PLAIN\r\n')
        sock.sendall('AUTH PLAIN AHRlc3RAZXhhbXBsZS5jb20AcGFzc3dk\r\n')
        sock.recv(IsA(int)).AndReturn('535 Nope!\r\n')
        self.mox.ReplayAll()
        client = SmtpRelayClient(None, self.queue, socket_creator=socket_creator, credentials=('test@example.com', 'passwd'), ehlo_as='test')
        client._connect()
        with self.assertRaises(PermanentRelayError):
            client._handshake()

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
        self.mox.ReplayAll()
        client = SmtpRelayClient(None, self.queue, socket_creator=self._socket_creator)
        client._connect()
        client._rcptto('recipient')

    def test_send_message_data(self):
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse('From: sender@example.com\r\n\r\ntest test\r\n')
        self.sock.sendall('From: sender@example.com\r\n\r\ntest test\r\n.\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 Ok\r\n')
        self.sock.sendall('From: sender@example.com\r\n\r\ntest test\r\n.\r\n')
        self.sock.recv(IsA(int)).AndReturn('550 Ok\r\n')
        self.mox.ReplayAll()
        client = SmtpRelayClient(None, self.queue, socket_creator=self._socket_creator)
        client._connect()
        client._send_message_data(env)
        with self.assertRaises(PermanentRelayError):
            client._send_message_data(env)

    def test_deliver(self):
        result = self.mox.CreateMock(AsyncResult)
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse('From: sender@example.com\r\n\r\ntest test \x81\r\n')
        self.sock.sendall('EHLO test\r\n')
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
        client = SmtpRelayClient(None, self.queue, socket_creator=self._socket_creator, ehlo_as='test')
        client._connect()
        client._ehlo()
        client._deliver(result, env)

    def test_deliver_badpipeline(self):
        result = self.mox.CreateMock(AsyncResult)
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse('From: sender@example.com\r\n\r\ntest test\r\n')
        self.sock.sendall('EHLO test\r\n')
        self.sock.recv(IsA(int)).AndReturn('250-Hello\r\n250 PIPELINING\r\n')
        self.sock.sendall('MAIL FROM:<sender@example.com>\r\nRCPT TO:<rcpt@example.com>\r\nDATA\r\n')
        self.sock.recv(IsA(int)).AndReturn('550 Not ok\r\n250 Ok\r\n354 Go ahead\r\n')
        result.set_exception(IsA(PermanentRelayError))
        self.sock.sendall('.\r\nRSET\r\n')
        self.sock.recv(IsA(int)).AndReturn('550 Yikes\r\n250 Ok\r\n')
        self.mox.ReplayAll()
        client = SmtpRelayClient(None, self.queue, socket_creator=self._socket_creator, ehlo_as='test')
        client._connect()
        client._ehlo()
        client._deliver(result, env)

    def test_deliver_baddata(self):
        result = self.mox.CreateMock(AsyncResult)
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse('From: sender@example.com\r\n\r\ntest test\r\n')
        self.sock.sendall('EHLO test\r\n')
        self.sock.recv(IsA(int)).AndReturn('250-Hello\r\n250 PIPELINING\r\n')
        self.sock.sendall('MAIL FROM:<sender@example.com>\r\nRCPT TO:<rcpt@example.com>\r\nDATA\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 Ok\r\n250 Ok\r\n354 Go ahead\r\n')
        self.sock.sendall('From: sender@example.com\r\n\r\ntest test\r\n.\r\n')
        self.sock.recv(IsA(int)).AndReturn('450 Yikes\r\n')
        result.set_exception(IsA(TransientRelayError))
        self.sock.sendall('RSET\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 Ok\r\n')
        self.mox.ReplayAll()
        client = SmtpRelayClient(None, self.queue, socket_creator=self._socket_creator, ehlo_as='test')
        client._connect()
        client._ehlo()
        client._deliver(result, env)

    def test_deliver_badrcpts(self):
        result = self.mox.CreateMock(AsyncResult)
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse('From: sender@example.com\r\n\r\ntest test\r\n')
        self.sock.sendall('EHLO test\r\n')
        self.sock.recv(IsA(int)).AndReturn('250-Hello\r\n250 PIPELINING\r\n')
        self.sock.sendall('MAIL FROM:<sender@example.com>\r\nRCPT TO:<rcpt@example.com>\r\nDATA\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 Ok\r\n550 Not ok\r\n354 Go ahead\r\n')
        self.sock.sendall('.\r\nRSET\r\n')
        self.sock.recv(IsA(int)).AndReturn('550 Yikes\r\n250 Ok\r\n')
        result.set_exception(IsA(PermanentRelayError))
        self.mox.ReplayAll()
        client = SmtpRelayClient(None, self.queue, socket_creator=self._socket_creator, ehlo_as='test')
        client._connect()
        client._ehlo()
        client._deliver(result, env)

    def test_deliver_rset_exception(self):
        result = self.mox.CreateMock(AsyncResult)
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse('From: sender@example.com\r\n\r\ntest test\r\n')
        self.sock.sendall('EHLO test\r\n')
        self.sock.recv(IsA(int)).AndReturn('250-Hello\r\n250 PIPELINING\r\n')
        self.sock.sendall('MAIL FROM:<sender@example.com>\r\nRCPT TO:<rcpt@example.com>\r\nDATA\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 Ok\r\n250 Ok\r\n450 No!\r\n')
        result.set_exception(IsA(TransientRelayError))
        self.sock.sendall('RSET\r\n')
        self.sock.recv(IsA(int)).AndRaise(ConnectionLost)
        self.mox.ReplayAll()
        client = SmtpRelayClient(None, self.queue, socket_creator=self._socket_creator, ehlo_as='test')
        client._connect()
        client._ehlo()
        with self.assertRaises(ConnectionLost):
            client._deliver(result, env)

    def test_deliver_conversion(self):
        result = self.mox.CreateMock(AsyncResult)
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse('From: sender@example.com\r\n\r\ntest test \x81\r\n')
        self.sock.sendall('EHLO test\r\n')
        self.sock.recv(IsA(int)).AndReturn('250-Hello\r\n250 PIPELINING\r\n')
        self.sock.sendall('MAIL FROM:<sender@example.com>\r\nRCPT TO:<rcpt@example.com>\r\nDATA\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 Ok\r\n250 Ok\r\n354 Go ahead\r\n')
        self.sock.sendall('From: sender@example.com\r\nContent-Transfer-Encoding: base64\r\n\r\ndGVzdCB0ZXN0IIENCg==\n\r\n.\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 Ok\r\n')
        result.set([None])
        self.mox.ReplayAll()
        client = SmtpRelayClient(None, self.queue, socket_creator=self._socket_creator, ehlo_as='test', binary_encoder=encode_base64)
        client._connect()
        client._ehlo()
        client._deliver(result, env)

    def test_deliver_conversion_failure(self):
        result = self.mox.CreateMock(AsyncResult)
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse('From: sender@example.com\r\n\r\ntest test \x81\r\n')
        self.sock.sendall('EHLO test\r\n')
        self.sock.recv(IsA(int)).AndReturn('250-Hello\r\n250 PIPELINING\r\n')
        self.sock.sendall('RSET\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 Ok\r\n')
        result.set_exception(IsA(PermanentRelayError))
        self.mox.ReplayAll()
        client = SmtpRelayClient(None, self.queue, socket_creator=self._socket_creator, ehlo_as='test')
        client._connect()
        client._ehlo()
        client._deliver(result, env)

    def test_disconnect(self):
        self.sock.sendall('QUIT\r\n')
        self.sock.recv(IsA(int)).AndReturn('221 Goodbye\r\n')
        self.sock.close()
        self.mox.ReplayAll()
        client = SmtpRelayClient(None, self.queue, socket_creator=self._socket_creator, ehlo_as='test')
        client._connect()
        client._disconnect()

    def test_disconnect_failure(self):
        self.sock.sendall('QUIT\r\n')
        self.sock.recv(IsA(int)).AndRaise(socket_error(None, None))
        self.sock.close()
        self.mox.ReplayAll()
        client = SmtpRelayClient(None, self.queue, socket_creator=self._socket_creator, ehlo_as='test')
        client._connect()
        client._disconnect()

    def test_run(self):
        result = self.mox.CreateMock(AsyncResult)
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse('From: sender@example.com\r\n\r\ntest test\r\n')
        queue = BlockingDeque()
        queue.append((result, env))
        self.sock.recv(IsA(int)).AndReturn('220 Welcome\r\n')
        self.sock.sendall('EHLO test\r\n')
        self.sock.recv(IsA(int)).AndReturn('250-Hello\r\n250 PIPELINING\r\n')
        self.sock.sendall('MAIL FROM:<sender@example.com>\r\nRCPT TO:<rcpt@example.com>\r\nDATA\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 Ok\r\n250 Ok\r\n354 Go ahead\r\n')
        self.sock.sendall('From: sender@example.com\r\n\r\ntest test\r\n.\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 Ok\r\n')
        result.set([None])
        self.sock.sendall('QUIT\r\n')
        self.sock.recv(IsA(int)).AndReturn('221 Goodbye\r\n')
        self.sock.close()
        self.mox.ReplayAll()
        client = SmtpRelayClient(None, queue, socket_creator=self._socket_creator, ehlo_as='test')
        client._run()

    def test_run_multiple(self):
        result1 = self.mox.CreateMock(AsyncResult)
        result2 = self.mox.CreateMock(AsyncResult)
        env1 = Envelope('sender1@example.com', ['rcpt1@example.com'])
        env1.parse('From: sender1@example.com\r\n\r\ntest test\r\n')
        env2 = Envelope('sender2@example.com', ['rcpt2@example.com'])
        env2.parse('From: sender2@example.com\r\n\r\ntest test\r\n')
        queue = BlockingDeque()
        queue.append((result1, env1))
        queue.append((result2, env2))
        self.sock.recv(IsA(int)).AndReturn('220 Welcome\r\n')
        self.sock.sendall('EHLO test\r\n')
        self.sock.recv(IsA(int)).AndReturn('250-Hello\r\n250 PIPELINING\r\n')
        self.sock.sendall('MAIL FROM:<sender1@example.com>\r\nRCPT TO:<rcpt1@example.com>\r\nDATA\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 Ok\r\n250 Ok\r\n354 Go ahead\r\n')
        self.sock.sendall('From: sender1@example.com\r\n\r\ntest test\r\n.\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 Ok\r\n')
        result1.set([None])
        self.sock.sendall('MAIL FROM:<sender2@example.com>\r\nRCPT TO:<rcpt2@example.com>\r\nDATA\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 Ok\r\n250 Ok\r\n354 Go ahead\r\n')
        self.sock.sendall('From: sender2@example.com\r\n\r\ntest test\r\n.\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 Ok\r\n')
        result2.set([None])
        self.sock.sendall('QUIT\r\n')
        self.sock.recv(IsA(int)).AndReturn('221 Goodbye\r\n')
        self.sock.close()
        self.mox.ReplayAll()
        client = SmtpRelayClient(None, queue, socket_creator=self._socket_creator, ehlo_as='test', idle_timeout=0.0)
        client._run()

    def test_run_random_exception(self):
        result = self.mox.CreateMock(AsyncResult)
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse('From: sender@example.com\r\n\r\ntest test\r\n')
        queue = BlockingDeque()
        queue.append((result, env))
        self.sock.recv(IsA(int)).AndRaise(ValueError('test error'))
        result.ready().AndReturn(False)
        result.set_exception(IsA(ValueError))
        self.sock.sendall('QUIT\r\n')
        self.sock.recv(IsA(int)).AndReturn('221 Goodbye\r\n')
        self.sock.close()
        self.mox.ReplayAll()
        client = SmtpRelayClient(None, queue, socket_creator=self._socket_creator, ehlo_as='test')
        with self.assertRaises(ValueError):
            client._run()

    def test_run_smtperror(self):
        result = self.mox.CreateMock(AsyncResult)
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse('From: sender@example.com\r\n\r\ntest test\r\n')
        queue = BlockingDeque()
        queue.append((result, env))
        self.sock.recv(IsA(int)).AndRaise(SmtpError('test error'))
        result.ready().AndReturn(False)
        result.set_exception(IsA(TransientRelayError))
        self.sock.sendall('QUIT\r\n')
        self.sock.recv(IsA(int)).AndReturn('221 Goodbye\r\n')
        self.sock.close()
        self.mox.ReplayAll()
        client = SmtpRelayClient(None, queue, socket_creator=self._socket_creator, ehlo_as='test')
        client._run()

    def test_run_timeout(self):
        result = self.mox.CreateMock(AsyncResult)
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse('From: sender@example.com\r\n\r\ntest test\r\n')
        queue = BlockingDeque()
        queue.append((result, env))
        self.sock.recv(IsA(int)).AndRaise(Timeout(0.0))
        result.ready().AndReturn(False)
        result.set_exception(IsA(TransientRelayError))
        self.sock.sendall('QUIT\r\n')
        self.sock.recv(IsA(int)).AndReturn('221 Goodbye\r\n')
        self.sock.close()
        self.mox.ReplayAll()
        client = SmtpRelayClient(None, queue, socket_creator=self._socket_creator, ehlo_as='test')
        client._run()

    def test_run_banner_failure(self):
        result = self.mox.CreateMock(AsyncResult)
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse('From: sender@example.com\r\n\r\ntest test\r\n')
        queue = BlockingDeque()
        queue.append((result, env))
        self.sock.recv(IsA(int)).AndReturn('520 Not Welcome\r\n')
        result.set_exception(IsA(PermanentRelayError))
        self.sock.sendall('QUIT\r\n')
        self.sock.recv(IsA(int)).AndReturn('221 Goodbye\r\n')
        self.sock.close()
        self.mox.ReplayAll()
        client = SmtpRelayClient(None, queue, socket_creator=self._socket_creator, ehlo_as='test')
        client._run()

    def test_run_nomessages(self):
        queue = BlockingDeque()
        self.mox.ReplayAll()
        client = SmtpRelayClient(None, queue, idle_timeout=0)
        client._run()


# vim:et:fdm=marker:sts=4:sw=4:ts=4
