import unittest2 as unittest
from mox3.mox import MoxTestBase, IsA
from gevent.ssl import SSLSocket, SSLError
from pysasl import SASLAuth

from slimta.smtp.server import Server
from slimta.smtp.auth import AuthSession
from slimta.smtp import ConnectionLost


class TestSmtpServer(unittest.TestCase, MoxTestBase):

    def setUp(self):
        super(TestSmtpServer, self).setUp()
        self.sock = self.mox.CreateMock(SSLSocket)
        self.sock.fileno = lambda: -1
        self.tls_args = {'server_side': True}

    def test_starttls_extension(self):
        s = Server(None, None)
        self.assertFalse('STARTTLS' in s.extensions)
        s = Server(None, None, tls=self.tls_args, tls_immediately=False)
        self.assertTrue('STARTTLS' in s.extensions)
        s = Server(None, None, tls=self.tls_args, tls_immediately=True)
        self.assertFalse('STARTTLS' in s.extensions)

    def test_recv_command(self):
        self.sock.recv(IsA(int)).AndReturn(b'cmd ARG\r\n')
        self.mox.ReplayAll()
        s = Server(self.sock, None)
        cmd, arg = s._recv_command()
        self.assertEqual(b'CMD', cmd)
        self.assertEqual(b'ARG', arg)

    def test_get_message_data(self):
        expected_reply = b'250 2.6.0 Message accepted for delivery\r\n'
        self.sock.recv(IsA(int)).AndReturn(b'one\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'.\r\n')
        self.sock.sendall(expected_reply)
        self.mox.ReplayAll()
        s = Server(self.sock, None)
        s._get_message_data()
        self.assertFalse(s.have_mailfrom)
        self.assertFalse(s.have_rcptto)

    def test_call_custom_handler(self):
        class TestHandler(object):
            def TEST(self, arg):
                return arg.lower()
        s = Server(None, TestHandler())
        self.assertEqual(b'stuff', s._call_custom_handler('TEST', b'STUFF'))

    def test_banner_quit(self):
        self.sock.sendall(b'220 ESMTP server\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'QUIT\r\n')
        self.sock.sendall(b'221 2.0.0 Bye\r\n')
        self.mox.ReplayAll()
        s = Server(self.sock, None)
        s.handle()

    def test_unhandled_error(self):
        class TestHandler(object):
            def BANNER_(self, reply):
                raise Exception('test')
        self.sock.sendall(b'421 4.3.0 Unhandled system error\r\n')
        self.mox.ReplayAll()
        s = Server(self.sock, TestHandler())
        with self.assertRaises(Exception) as cm:
            s.handle()
        self.assertEqual(('test', ), cm.exception.args)

    def test_banner_command(self):
        self.sock.sendall(b'220 ESMTP server\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'BANNER\r\n')
        self.sock.sendall(b'500 5.5.2 Syntax error, command unrecognized\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'BANNER_\r\n')
        self.sock.sendall(b'500 5.5.2 Syntax error, command unrecognized\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'QUIT\r\n')
        self.sock.sendall(b'221 2.0.0 Bye\r\n')
        self.mox.ReplayAll()
        s = Server(self.sock, None)
        s.handle()

    def test_tls_immediately(self):
        sock = self.mox.CreateMockAnything()
        sock.fileno = lambda: -1
        sock.tls_wrapper(sock, self.tls_args).AndReturn(sock)
        sock.sendall(b'220 ESMTP server\r\n')
        sock.recv(IsA(int)).AndReturn(b'QUIT\r\n')
        sock.sendall(b'221 2.0.0 Bye\r\n')
        self.mox.ReplayAll()
        s = Server(sock, None, tls=self.tls_args, tls_immediately=True,
                   tls_wrapper=sock.tls_wrapper)
        s.handle()

    def test_tls_immediately_sslerror(self):
        sock = self.mox.CreateMockAnything()
        sock.fileno = lambda: -1
        sock.tls_wrapper(sock, self.tls_args).AndRaise(SSLError())
        sock.sendall(b'421 4.7.0 TLS negotiation failed\r\n')
        self.mox.ReplayAll()
        s = Server(sock, None, tls=self.tls_args, tls_immediately=True,
                   tls_wrapper=sock.tls_wrapper)
        s.handle()

    def test_ehlo(self):
        self.sock.sendall(b'220 ESMTP server\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'EHLO there\r\n')
        self.sock.sendall(b'250-Hello there\r\n250 TEST\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'QUIT\r\n')
        self.sock.sendall(b'221 2.0.0 Bye\r\n')
        self.mox.ReplayAll()
        s = Server(self.sock, None)
        s.extensions.reset()
        s.extensions.add('TEST')
        s.handle()
        self.assertEqual('there', s.ehlo_as)

    def test_helo(self):
        self.sock.sendall(b'220 ESMTP server\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'HELO there\r\n')
        self.sock.sendall(b'250 Hello there\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'QUIT\r\n')
        self.sock.sendall(b'221 2.0.0 Bye\r\n')
        self.mox.ReplayAll()
        s = Server(self.sock, None)
        s.handle()
        self.assertEqual('there', s.ehlo_as)

    def test_starttls(self):
        sock = self.mox.CreateMockAnything()
        sock.fileno = lambda: -1
        sock.sendall(b'220 ESMTP server\r\n')
        sock.recv(IsA(int)).AndReturn(b'EHLO there\r\n')
        sock.sendall(b'250-Hello there\r\n250 STARTTLS\r\n')
        sock.recv(IsA(int)).AndReturn(b'STARTTLS\r\n')
        sock.sendall(b'220 2.7.0 Go ahead\r\n')
        sock.tls_wrapper(sock, self.tls_args).AndReturn(sock)
        sock.recv(IsA(int)).AndReturn(b'QUIT\r\n')
        sock.sendall(b'221 2.0.0 Bye\r\n')
        self.mox.ReplayAll()
        s = Server(sock, None, tls=self.tls_args, tls_wrapper=sock.tls_wrapper)
        s.extensions.reset()
        s.extensions.add('STARTTLS')
        s.handle()
        self.assertEqual(None, s.ehlo_as)

    def test_starttls_bad(self):
        sock = self.mox.CreateMockAnything()
        sock.fileno = lambda: -1
        sock.sendall(b'220 ESMTP server\r\n')
        sock.recv(IsA(int)).AndReturn(b'STARTTLS\r\n')
        sock.sendall(b'503 5.5.1 Bad sequence of commands\r\n')
        sock.recv(IsA(int)).AndReturn(b'STARTTLS badarg\r\n')
        sock.sendall(b'501 5.5.4 Syntax error in parameters or arguments\r\n')
        sock.recv(IsA(int)).AndReturn(b'EHLO there\r\n')
        sock.sendall(b'250-Hello there\r\n250 STARTTLS\r\n')
        sock.recv(IsA(int)).AndReturn(b'STARTTLS\r\n')
        sock.sendall(b'220 2.7.0 Go ahead\r\n')
        sock.tls_wrapper(sock, self.tls_args).AndRaise(SSLError())
        sock.sendall(b'421 4.7.0 TLS negotiation failed\r\n')
        self.mox.ReplayAll()
        s = Server(sock, None, tls=self.tls_args, tls_wrapper=sock.tls_wrapper)
        s.extensions.reset()
        s.extensions.add('STARTTLS')
        s.handle()
        self.assertEqual('there', s.ehlo_as)

    def test_auth(self):
        self.sock.sendall(b'220 ESMTP server\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'EHLO there\r\n')
        self.sock.sendall(b'250-Hello there\r\n250 AUTH PLAIN\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'AUTH PLAIN dGVzdHppZAB0ZXN0dXNlcgB0ZXN0cGFzc3dvcmQ=\r\n')
        self.sock.sendall(b'235 2.7.0 Authentication successful\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'QUIT\r\n')
        self.sock.sendall(b'221 2.0.0 Bye\r\n')
        self.mox.ReplayAll()
        s = Server(self.sock, None)
        s.extensions.reset()
        s.extensions.add('AUTH', AuthSession(SASLAuth([b'PLAIN']), s.io))
        s.handle()
        self.assertTrue(s.authed)

    def test_mailfrom(self):
        self.sock.sendall(b'220 ESMTP server\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'HELO there\r\n')
        self.sock.sendall(b'250 Hello there\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'MAIL FROM:<test">"addr>\r\n')
        self.sock.sendall(b'250 2.1.0 Sender <test">"addr> Ok\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'QUIT\r\n')
        self.sock.sendall(b'221 2.0.0 Bye\r\n')
        self.mox.ReplayAll()
        s = Server(self.sock, None)
        s.handle()
        self.assertTrue(s.have_mailfrom)

    def test_mailfrom_bad(self):
        self.sock.sendall(b'220 ESMTP server\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'MAIL FROM:<test>\r\n')
        self.sock.sendall(b'503 5.5.1 Bad sequence of commands\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'HELO there\r\n')
        self.sock.sendall(b'250 Hello there\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'MAIL FROM:<test1> SIZE=5\r\n')
        self.sock.sendall(b'504 5.5.4 Command parameter not implemented\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'MAIL FRM:<addr>\r\n')
        self.sock.sendall(b'501 5.5.4 Syntax error in parameters or arguments\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'MAIL FROM:<addr\r\n')
        self.sock.sendall(b'501 5.5.4 Syntax error in parameters or arguments\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'MAIL FROM:<test1>\r\n')
        self.sock.sendall(b'250 2.1.0 Sender <test1> Ok\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'MAIL FROM:<test2>\r\n')
        self.sock.sendall(b'503 5.5.1 Bad sequence of commands\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'QUIT\r\n')
        self.sock.sendall(b'221 2.0.0 Bye\r\n')
        self.mox.ReplayAll()
        s = Server(self.sock, None)
        s.handle()
        self.assertTrue(s.have_mailfrom)

    def test_mailfrom_send_extension(self):
        self.sock.sendall(b'220 ESMTP server\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'EHLO there\r\n')
        self.sock.sendall(b'250-Hello there\r\n250 SIZE 10\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'MAIL FROM:<test1> SIZE=ASDF\r\n')
        self.sock.sendall(b'501 5.5.4 Syntax error in parameters or arguments\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'MAIL FROM:<test1> SIZE=20\r\n')
        self.sock.sendall(b'552 5.3.4 Message size exceeds 10 limit\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'MAIL FROM:<test1> SIZE=5\r\n')
        self.sock.sendall(b'250 2.1.0 Sender <test1> Ok\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'QUIT\r\n')
        self.sock.sendall(b'221 2.0.0 Bye\r\n')
        self.mox.ReplayAll()
        s = Server(self.sock, None)
        s.extensions.reset()
        s.extensions.add('SIZE', 10)
        s.handle()
        self.assertTrue(s.have_mailfrom)

    def test_rcptto(self):
        self.sock.sendall(b'220 ESMTP server\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'RCPT TO:<test">"addr>\r\n')
        self.sock.sendall(b'250 2.1.5 Recipient <test">"addr> Ok\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'RCPT TO:<test2>\r\n')
        self.sock.sendall(b'250 2.1.5 Recipient <test2> Ok\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'QUIT\r\n')
        self.sock.sendall(b'221 2.0.0 Bye\r\n')
        self.mox.ReplayAll()
        s = Server(self.sock, None)
        s.ehlo_as = b'test'
        s.have_mailfrom = True
        s.handle()
        self.assertTrue(s.have_rcptto)

    def test_rcptto_bad(self):
        self.sock.sendall(b'220 ESMTP server\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'RCPT TO:<test>\r\n')
        self.sock.sendall(b'503 5.5.1 Bad sequence of commands\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'HELO there\r\n')
        self.sock.sendall(b'250 Hello there\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'RCPT TO:<test>\r\n')
        self.sock.sendall(b'503 5.5.1 Bad sequence of commands\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'MAIL FROM:<test1>\r\n')
        self.sock.sendall(b'250 2.1.0 Sender <test1> Ok\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'RCPT T:<test1>\r\n')
        self.sock.sendall(b'501 5.5.4 Syntax error in parameters or arguments\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'RCPT TO:<test1\r\n')
        self.sock.sendall(b'501 5.5.4 Syntax error in parameters or arguments\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'QUIT\r\n')
        self.sock.sendall(b'221 2.0.0 Bye\r\n')
        self.mox.ReplayAll()
        s = Server(self.sock, None)
        s.handle()
        self.assertFalse(s.have_rcptto)

    def test_data(self):
        self.sock.sendall(b'220 ESMTP server\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'DATA\r\n')
        self.sock.sendall(b'354 Start mail input; end with <CRLF>.<CRLF>\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'.\r\nQUIT\r\n')
        self.sock.sendall(b'250 2.6.0 Message accepted for delivery\r\n')
        self.sock.sendall(b'221 2.0.0 Bye\r\n')
        self.mox.ReplayAll()
        s = Server(self.sock, None)
        s.ehlo_as = b'test'
        s.have_mailfrom = True
        s.have_rcptto = True
        s.handle()

    def test_data_bad(self):
        self.sock.sendall(b'220 ESMTP server\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'DATA arg\r\n')
        self.sock.sendall(b'501 5.5.4 Syntax error in parameters or arguments\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'DATA\r\n')
        self.sock.sendall(b'503 5.5.1 Bad sequence of commands\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'QUIT\r\n')
        self.sock.sendall(b'221 2.0.0 Bye\r\n')
        self.mox.ReplayAll()
        s = Server(self.sock, None)
        s.ehlo_as = b'test'
        s.have_mailfrom = True
        s.handle()

    def test_data_connectionlost(self):
        self.sock.sendall(b'220 ESMTP server\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'DATA\r\n')
        self.sock.sendall(b'354 Start mail input; end with <CRLF>.<CRLF>\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'')
        self.mox.ReplayAll()
        s = Server(self.sock, None)
        s.ehlo_as = b'test'
        s.have_mailfrom = True
        s.have_rcptto = True
        self.assertRaises(ConnectionLost, s.handle)

    def test_noop(self):
        self.sock.sendall(b'220 ESMTP server\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'NOOP\r\n')
        self.sock.sendall(b'250 2.0.0 Ok\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'QUIT\r\n')
        self.sock.sendall(b'221 2.0.0 Bye\r\n')
        self.mox.ReplayAll()
        s = Server(self.sock, None)
        s.handle()

    def test_rset(self):
        class TestHandlers(object):
            server = None
            def NOOP(self2, reply):
                self.assertEqual(b'test', self2.server.ehlo_as)
                self.assertFalse(self2.server.have_mailfrom)
                self.assertFalse(self2.server.have_rcptto)
        self.sock.sendall(b'220 ESMTP server\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'RSET arg\r\n')
        self.sock.sendall(b'501 5.5.4 Syntax error in parameters or arguments\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'RSET\r\n')
        self.sock.sendall(b'250 2.0.0 Ok\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'NOOP\r\n')
        self.sock.sendall(b'250 2.0.0 Ok\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'QUIT\r\n')
        self.sock.sendall(b'221 2.0.0 Bye\r\n')
        self.mox.ReplayAll()
        h = TestHandlers()
        s = h.server = Server(self.sock, h)
        s.ehlo_as = b'test'
        s.have_mailfrom = True
        s.have_rcptto = True
        s.handle()

    def test_quit_bad(self):
        self.sock.sendall(b'220 ESMTP server\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'QUIT arg\r\n')
        self.sock.sendall(b'501 5.5.4 Syntax error in parameters or arguments\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'QUIT\r\n')
        self.sock.sendall(b'221 2.0.0 Bye\r\n')
        self.mox.ReplayAll()
        s = Server(self.sock, None)
        s.handle()

    def test_custom_command(self):
        class TestHandlers(object):
            def TEST(self2, reply, arg, server):
                self.assertTrue(server.have_mailfrom)
                reply.code = '250'
                reply.message = 'Doing '+arg.decode()
        self.sock.sendall(b'220 ESMTP server\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'TEST stuff\r\n')
        self.sock.sendall(b'250 2.0.0 Doing stuff\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'QUIT\r\n')
        self.sock.sendall(b'221 2.0.0 Bye\r\n')
        self.mox.ReplayAll()
        s = Server(self.sock, TestHandlers())
        s.have_mailfrom = True
        s.handle()

    def test_bad_commands(self):
        self.sock.sendall(b'220 ESMTP server\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'\r\n')
        self.sock.sendall(b'500 5.5.2 Syntax error, command unrecognized\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'BADCMD\r\n')
        self.sock.sendall(b'500 5.5.2 Syntax error, command unrecognized\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'STARTTLS\r\n')
        self.sock.sendall(b'500 5.5.2 Syntax error, command unrecognized\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'AUTH\r\n')
        self.sock.sendall(b'500 5.5.2 Syntax error, command unrecognized\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'QUIT\r\n')
        self.sock.sendall(b'221 2.0.0 Bye\r\n')
        self.mox.ReplayAll()
        s = Server(self.sock, None)
        s.handle()

    def test_gather_params(self):
        s = Server(None, None)
        self.assertEqual({b'ONE': b'1'}, s._gather_params(b' ONE=1'))
        self.assertEqual({b'TWO': True}, s._gather_params(b'TWO'))
        self.assertEqual({b'THREE': b'foo', b'FOUR': b'bar'},
                         s._gather_params(b' THREE=foo FOUR=bar'))
        self.assertEqual({b'FIVE': True}, s._gather_params(b'five'))


# vim:et:fdm=marker:sts=4:sw=4:ts=4
