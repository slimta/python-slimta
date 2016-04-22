from email.encoders import encode_base64

import unittest2 as unittest
from mox3.mox import MoxTestBase, IsA
from gevent import Timeout
from gevent.socket import socket, error as socket_error
from gevent.event import AsyncResult

from slimta.util import pycompat
from slimta.util.deque import BlockingDeque
from slimta.smtp import ConnectionLost, SmtpError
from slimta.smtp.reply import Reply
from slimta.relay import TransientRelayError, PermanentRelayError
from slimta.relay.smtp.client import SmtpRelayClient
from slimta.envelope import Envelope


class TestSmtpRelayClient(unittest.TestCase, MoxTestBase):

    def setUp(self):
        super(TestSmtpRelayClient, self).setUp()
        self.sock = self.mox.CreateMock(socket)
        self.sock.fileno = lambda: -1
        self.sock.getpeername = lambda: ('test', 0)
        self.queue = self.mox.CreateMock(BlockingDeque)
        self.tls_args = {'test': 'test'}

    def _socket_creator(self, address):
        return self.sock

    def test_connect(self):
        self.mox.ReplayAll()
        client = SmtpRelayClient('addr', self.queue, socket_creator=self._socket_creator)
        client._connect()

    def test_banner(self):
        self.sock.recv(IsA(int)).AndReturn(b'220 Welcome\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'420 Not Welcome\r\n')
        self.mox.ReplayAll()
        client = SmtpRelayClient('addr', self.queue, socket_creator=self._socket_creator)
        client._connect()
        client._banner()
        with self.assertRaises(TransientRelayError):
            client._banner()

    def test_ehlo(self):
        self.sock.sendall(b'EHLO there\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250-Hello\r\n250 TEST\r\n')
        self.sock.sendall(b'EHLO there\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'420 Goodbye\r\n')
        self.mox.ReplayAll()
        client = SmtpRelayClient('addr', self.queue, socket_creator=self._socket_creator, ehlo_as='there')
        client._connect()
        client._ehlo()
        with self.assertRaises(TransientRelayError):
            client._ehlo()

    def test_starttls(self):
        tls_wrapper = self.mox.CreateMockAnything()
        self.sock.sendall(b'STARTTLS\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'220 Go ahead\r\n')
        tls_wrapper(self.sock, self.tls_args).AndReturn(self.sock)
        self.sock.sendall(b'STARTTLS\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'420 Stop\r\n')
        self.mox.ReplayAll()
        client = SmtpRelayClient('addr', self.queue, socket_creator=self._socket_creator, tls=self.tls_args, tls_wrapper=tls_wrapper, tls_required=True)
        client._connect()
        client._starttls()
        with self.assertRaises(TransientRelayError):
            client._starttls()

    def test_handshake_tls_immediately(self):
        tls_wrapper = self.mox.CreateMockAnything()
        tls_wrapper(self.sock, self.tls_args).AndReturn(self.sock)
        self.sock.recv(IsA(int)).AndReturn(b'220 Welcome\r\n')
        self.sock.sendall(b'EHLO there\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250 Hello\r\n')
        self.mox.ReplayAll()
        client = SmtpRelayClient('addr', self.queue, socket_creator=self._socket_creator, tls=self.tls_args, tls_wrapper=tls_wrapper, tls_immediately=True, ehlo_as='there')
        client._connect()
        client._handshake()

    def test_handshake_starttls(self):
        tls_wrapper = self.mox.CreateMockAnything()
        self.sock.recv(IsA(int)).AndReturn(b'220 Welcome\r\n')
        self.sock.sendall(b'EHLO there\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250-Hello\r\n250 STARTTLS\r\n')
        self.sock.sendall(b'STARTTLS\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'220 Go ahead\r\n')
        tls_wrapper(self.sock, self.tls_args).AndReturn(self.sock)
        self.sock.sendall(b'EHLO there\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250 Hello\r\n')
        self.mox.ReplayAll()
        client = SmtpRelayClient('addr', self.queue, socket_creator=self._socket_creator, tls=self.tls_args, tls_wrapper=tls_wrapper, ehlo_as='there')
        client._connect()
        client._handshake()

    def test_handshake_authenticate(self):
        self.sock.recv(IsA(int)).AndReturn(b'220 Welcome\r\n')
        self.sock.sendall(b'EHLO there\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250-Hello\r\n250 AUTH PLAIN\r\n')
        self.sock.sendall(b'AUTH PLAIN AHRlc3RAZXhhbXBsZS5jb20AcGFzc3dk\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'235 Ok\r\n')
        self.mox.ReplayAll()
        client = SmtpRelayClient('addr', self.queue, socket_creator=self._socket_creator, credentials=('test@example.com', 'passwd'), ehlo_as='there')
        client._connect()
        client._handshake()

    def test_handshake_authenticate_callable(self):
        self.sock.recv(IsA(int)).AndReturn(b'220 Welcome\r\n')
        self.sock.sendall(b'EHLO there\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250-Hello\r\n250 AUTH PLAIN\r\n')
        self.sock.sendall(b'AUTH PLAIN AHRlc3RAZXhhbXBsZS5jb20AcGFzc3dk\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'235 Ok\r\n')
        self.mox.ReplayAll()
        def yield_creds():
            yield 'test@example.com'
            yield 'passwd'
        client = SmtpRelayClient('addr', self.queue, socket_creator=self._socket_creator, credentials=yield_creds, ehlo_as='there')
        client._connect()
        client._handshake()

    def test_rset(self):
        self.sock.sendall(b'RSET\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250 Ok\r\n')
        self.mox.ReplayAll()
        client = SmtpRelayClient('addr', self.queue, socket_creator=self._socket_creator)
        client._connect()
        client._rset()

    def test_handshake_authenticate_badcreds(self):
        self.sock.recv(IsA(int)).AndReturn(b'220 Welcome\r\n')
        self.sock.sendall(b'EHLO there\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250-Hello\r\n250 AUTH PLAIN\r\n')
        self.sock.sendall(b'AUTH PLAIN AHRlc3RAZXhhbXBsZS5jb20AcGFzc3dk\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'535 Nope!\r\n')
        self.mox.ReplayAll()
        client = SmtpRelayClient('addr', self.queue, socket_creator=self._socket_creator, credentials=('test@example.com', 'passwd'), ehlo_as='there')
        client._connect()
        with self.assertRaises(PermanentRelayError):
            client._handshake()

    def test_mailfrom(self):
        self.sock.sendall(b'MAIL FROM:<sender>\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250 Ok\r\n')
        self.sock.sendall(b'MAIL FROM:<sender>\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'550 Not Ok\r\n')
        self.mox.ReplayAll()
        client = SmtpRelayClient('addr', self.queue, socket_creator=self._socket_creator)
        client._connect()
        client._mailfrom('sender')
        with self.assertRaises(PermanentRelayError):
            client._mailfrom('sender')

    def test_rcptto(self):
        self.sock.sendall(b'RCPT TO:<recipient>\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250 Ok\r\n')
        self.mox.ReplayAll()
        client = SmtpRelayClient('addr', self.queue, socket_creator=self._socket_creator)
        client._connect()
        client._rcptto('recipient')

    def test_send_message_data(self):
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse(b'From: sender@example.com\r\n\r\ntest test\r\n')
        self.sock.sendall(b'From: sender@example.com\r\n\r\ntest test\r\n.\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250 Ok\r\n')
        self.sock.sendall(b'From: sender@example.com\r\n\r\ntest test\r\n.\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'550 Ok\r\n')
        self.mox.ReplayAll()
        client = SmtpRelayClient('addr', self.queue, socket_creator=self._socket_creator)
        client._connect()
        client._send_message_data(env)
        with self.assertRaises(PermanentRelayError):
            client._send_message_data(env)

    def test_deliver(self):
        result = AsyncResult()
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse(b'From: sender@example.com\r\n\r\ntest test \x81\r\n')
        self.sock.sendall(b'EHLO there\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250-Hello\r\n250 8BITMIME\r\n')
        self.sock.sendall(b'MAIL FROM:<sender@example.com>\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250 Ok\r\n')
        self.sock.sendall(b'RCPT TO:<rcpt@example.com>\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250 Ok\r\n')
        self.sock.sendall(b'DATA\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'354 Go ahead\r\n')
        self.sock.sendall(b'From: sender@example.com\r\n\r\ntest test \x81\r\n.\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250 Ok\r\n')
        self.mox.ReplayAll()
        client = SmtpRelayClient('addr', self.queue, socket_creator=self._socket_creator, ehlo_as='there')
        client._connect()
        client._ehlo()
        client._deliver(result, env)
        self.assertEqual({'rcpt@example.com': Reply('250', 'Ok')}, result.get_nowait())

    def test_deliver_badpipeline(self):
        result = AsyncResult()
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse(b'From: sender@example.com\r\n\r\ntest test\r\n')
        self.sock.sendall(b'EHLO there\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250-Hello\r\n250 PIPELINING\r\n')
        self.sock.sendall(b'MAIL FROM:<sender@example.com>\r\nRCPT TO:<rcpt@example.com>\r\nDATA\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'550 Not ok\r\n250 Ok\r\n354 Go ahead\r\n')
        self.sock.sendall(b'.\r\nRSET\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'550 Yikes\r\n250 Ok\r\n')
        self.mox.ReplayAll()
        client = SmtpRelayClient('addr', self.queue, socket_creator=self._socket_creator, ehlo_as='there')
        client._connect()
        client._ehlo()
        client._deliver(result, env)
        with self.assertRaises(PermanentRelayError):
            result.get_nowait()

    def test_deliver_baddata(self):
        result = AsyncResult()
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse(b'From: sender@example.com\r\n\r\ntest test\r\n')
        self.sock.sendall(b'EHLO there\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250-Hello\r\n250 PIPELINING\r\n')
        self.sock.sendall(b'MAIL FROM:<sender@example.com>\r\nRCPT TO:<rcpt@example.com>\r\nDATA\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250 Ok\r\n250 Ok\r\n354 Go ahead\r\n')
        self.sock.sendall(b'From: sender@example.com\r\n\r\ntest test\r\n.\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'450 Yikes\r\n')
        self.sock.sendall(b'RSET\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250 Ok\r\n')
        self.mox.ReplayAll()
        client = SmtpRelayClient('addr', self.queue, socket_creator=self._socket_creator, ehlo_as='there')
        client._connect()
        client._ehlo()
        client._deliver(result, env)
        with self.assertRaises(TransientRelayError):
            result.get_nowait()

    def test_deliver_badrcpts(self):
        result = AsyncResult()
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse(b'From: sender@example.com\r\n\r\ntest test\r\n')
        self.sock.sendall(b'EHLO there\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250-Hello\r\n250 PIPELINING\r\n')
        self.sock.sendall(b'MAIL FROM:<sender@example.com>\r\nRCPT TO:<rcpt@example.com>\r\nDATA\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250 Ok\r\n550 Not ok\r\n354 Go ahead\r\n')
        self.sock.sendall(b'.\r\nRSET\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'550 Yikes\r\n250 Ok\r\n')
        self.mox.ReplayAll()
        client = SmtpRelayClient('addr', self.queue, socket_creator=self._socket_creator, ehlo_as='there')
        client._connect()
        client._ehlo()
        client._deliver(result, env)
        with self.assertRaises(PermanentRelayError):
            result.get_nowait()

    def test_deliver_rset_exception(self):
        result = AsyncResult()
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse(b'From: sender@example.com\r\n\r\ntest test\r\n')
        self.sock.sendall(b'EHLO there\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250-Hello\r\n250 PIPELINING\r\n')
        self.sock.sendall(b'MAIL FROM:<sender@example.com>\r\nRCPT TO:<rcpt@example.com>\r\nDATA\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250 Ok\r\n250 Ok\r\n450 No!\r\n')
        self.sock.sendall(b'RSET\r\n')
        self.sock.recv(IsA(int)).AndRaise(ConnectionLost)
        self.mox.ReplayAll()
        client = SmtpRelayClient('addr', self.queue, socket_creator=self._socket_creator, ehlo_as='there')
        client._connect()
        client._ehlo()
        with self.assertRaises(ConnectionLost):
            client._deliver(result, env)
        with self.assertRaises(TransientRelayError):
            result.get_nowait()

    def test_deliver_conversion(self):
        result = AsyncResult()
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse(b'From: sender@example.com\r\n\r\ntest test \x81\r\n')
        self.sock.sendall(b'EHLO there\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250-Hello\r\n250 PIPELINING\r\n')
        self.sock.sendall(b'MAIL FROM:<sender@example.com>\r\nRCPT TO:<rcpt@example.com>\r\nDATA\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250 Ok\r\n250 Ok\r\n354 Go ahead\r\n')
        if pycompat.PY3:
            self.sock.sendall(b'From: sender@example.com\r\nContent-Transfer-Encoding: base64\r\n\r\ndGVzdCB0ZXN0IIEK\r\n.\r\n')
        else:
            self.sock.sendall(b'From: sender@example.com\r\nContent-Transfer-Encoding: base64\r\n\r\ndGVzdCB0ZXN0IIENCg==\r\n.\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250 Ok\r\n')
        self.mox.ReplayAll()
        client = SmtpRelayClient('addr', self.queue, socket_creator=self._socket_creator, ehlo_as='there', binary_encoder=encode_base64)
        client._connect()
        client._ehlo()
        client._deliver(result, env)
        self.assertEqual({'rcpt@example.com': Reply('250', 'Ok')}, result.get_nowait())

    def test_deliver_conversion_failure(self):
        result = AsyncResult()
        env = Envelope('bsender@example.com', ['rcpt@example.com'])
        env.parse(b'From: sender@example.com\r\n\r\ntest test \x81\r\n')
        self.sock.sendall(b'EHLO there\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250-Hello\r\n250 PIPELINING\r\n')
        self.sock.sendall(b'RSET\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250 Ok\r\n')
        self.mox.ReplayAll()
        client = SmtpRelayClient('addr', self.queue, socket_creator=self._socket_creator, ehlo_as='there')
        client._connect()
        client._ehlo()
        client._deliver(result, env)
        with self.assertRaises(PermanentRelayError):
            result.get_nowait()

    def test_disconnect(self):
        self.sock.sendall(b'QUIT\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'221 Goodbye\r\n')
        self.sock.close()
        self.mox.ReplayAll()
        client = SmtpRelayClient('addr', self.queue, socket_creator=self._socket_creator, ehlo_as='there')
        client._connect()
        client._disconnect()

    def test_disconnect_failure(self):
        self.sock.sendall(b'QUIT\r\n')
        self.sock.recv(IsA(int)).AndRaise(socket_error(None, None))
        self.sock.close()
        self.mox.ReplayAll()
        client = SmtpRelayClient('addr', self.queue, socket_creator=self._socket_creator, ehlo_as='there')
        client._connect()
        client._disconnect()

    def test_run(self):
        result = AsyncResult()
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse(b'From: sender@example.com\r\n\r\ntest test\r\n')
        queue = BlockingDeque()
        queue.append((result, env))
        self.sock.recv(IsA(int)).AndReturn(b'220 Welcome\r\n')
        self.sock.sendall(b'EHLO there\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250-Hello\r\n250 PIPELINING\r\n')
        self.sock.sendall(b'MAIL FROM:<sender@example.com>\r\nRCPT TO:<rcpt@example.com>\r\nDATA\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250 Ok\r\n250 Ok\r\n354 Go ahead\r\n')
        self.sock.sendall(b'From: sender@example.com\r\n\r\ntest test\r\n.\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250 Ok\r\n')
        self.sock.sendall(b'QUIT\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'221 Goodbye\r\n')
        self.sock.close()
        self.mox.ReplayAll()
        client = SmtpRelayClient('addr', queue, socket_creator=self._socket_creator, ehlo_as='there')
        client._run()
        self.assertEqual({'rcpt@example.com': Reply('250', 'Ok')}, result.get_nowait())

    def test_run_multiple(self):
        result1 = AsyncResult()
        result2 = AsyncResult()
        env1 = Envelope('sender1@example.com', ['rcpt1@example.com'])
        env1.parse(b'From: sender1@example.com\r\n\r\ntest test\r\n')
        env2 = Envelope('sender2@example.com', ['rcpt2@example.com'])
        env2.parse(b'From: sender2@example.com\r\n\r\ntest test\r\n')
        queue = BlockingDeque()
        queue.append((result1, env1))
        queue.append((result2, env2))
        self.sock.recv(IsA(int)).AndReturn(b'220 Welcome\r\n')
        self.sock.sendall(b'EHLO there\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250-Hello\r\n250 PIPELINING\r\n')
        self.sock.sendall(b'MAIL FROM:<sender1@example.com>\r\nRCPT TO:<rcpt1@example.com>\r\nDATA\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250 Ok\r\n250 Ok\r\n354 Go ahead\r\n')
        self.sock.sendall(b'From: sender1@example.com\r\n\r\ntest test\r\n.\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250 Ok\r\n')
        self.sock.sendall(b'MAIL FROM:<sender2@example.com>\r\nRCPT TO:<rcpt2@example.com>\r\nDATA\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250 Ok\r\n250 Ok\r\n354 Go ahead\r\n')
        self.sock.sendall(b'From: sender2@example.com\r\n\r\ntest test\r\n.\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250 Ok\r\n')
        self.sock.sendall(b'QUIT\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'221 Goodbye\r\n')
        self.sock.close()
        self.mox.ReplayAll()
        client = SmtpRelayClient('addr', queue, socket_creator=self._socket_creator, ehlo_as='there', idle_timeout=0.0)
        client._run()
        self.assertEqual({'rcpt1@example.com': Reply('250', 'Ok')}, result1.get_nowait())
        self.assertEqual({'rcpt2@example.com': Reply('250', 'Ok')}, result2.get_nowait())

    def test_run_random_exception(self):
        result = AsyncResult()
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse(b'From: sender@example.com\r\n\r\ntest test\r\n')
        queue = BlockingDeque()
        queue.append((result, env))
        self.sock.recv(IsA(int)).AndRaise(ValueError('test error'))
        self.sock.sendall(b'QUIT\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'221 Goodbye\r\n')
        self.sock.close()
        self.mox.ReplayAll()
        client = SmtpRelayClient('addr', queue, socket_creator=self._socket_creator, ehlo_as='there')
        with self.assertRaises(ValueError):
            client._run()
        with self.assertRaises(ValueError):
            result.get_nowait()

    def test_run_socket_error(self):
        result = AsyncResult()
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse(b'From: sender@example.com\r\n\r\ntest test\r\n')
        queue = BlockingDeque()
        queue.append((result, env))
        self.sock.recv(IsA(int)).AndRaise(socket_error(None, None))
        self.sock.sendall(b'QUIT\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'221 Goodbye\r\n')
        self.sock.close()
        self.mox.ReplayAll()
        client = SmtpRelayClient('addr', queue, socket_creator=self._socket_creator, ehlo_as='there')
        client._run()
        with self.assertRaises(TransientRelayError):
            result.get_nowait()

    def test_run_smtperror(self):
        result = AsyncResult()
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse(b'From: sender@example.com\r\n\r\ntest test\r\n')
        queue = BlockingDeque()
        queue.append((result, env))
        self.sock.recv(IsA(int)).AndRaise(SmtpError('test error'))
        self.sock.sendall(b'QUIT\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'221 Goodbye\r\n')
        self.sock.close()
        self.mox.ReplayAll()
        client = SmtpRelayClient('addr', queue, socket_creator=self._socket_creator, ehlo_as='there')
        client._run()
        with self.assertRaises(TransientRelayError):
            result.get_nowait()

    def test_run_timeout(self):
        result = AsyncResult()
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse(b'From: sender@example.com\r\n\r\ntest test\r\n')
        queue = BlockingDeque()
        queue.append((result, env))
        self.sock.recv(IsA(int)).AndRaise(Timeout(0.0))
        self.sock.sendall(b'QUIT\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'221 Goodbye\r\n')
        self.sock.close()
        self.mox.ReplayAll()
        client = SmtpRelayClient('addr', queue, socket_creator=self._socket_creator, ehlo_as='there')
        client._run()
        with self.assertRaises(TransientRelayError):
            result.get_nowait()

    def test_run_banner_failure(self):
        result = AsyncResult()
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse(b'From: sender@example.com\r\n\r\ntest test\r\n')
        queue = BlockingDeque()
        queue.append((result, env))
        self.sock.recv(IsA(int)).AndReturn(b'520 Not Welcome\r\n')
        self.sock.sendall(b'QUIT\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'221 Goodbye\r\n')
        self.sock.close()
        self.mox.ReplayAll()
        client = SmtpRelayClient('addr', queue, socket_creator=self._socket_creator, ehlo_as='there')
        client._run()
        with self.assertRaises(PermanentRelayError):
            result.get_nowait()

    def test_run_nomessages(self):
        queue = BlockingDeque()
        self.mox.ReplayAll()
        client = SmtpRelayClient('addr', queue, idle_timeout=0)
        client._run()


# vim:et:fdm=marker:sts=4:sw=4:ts=4
