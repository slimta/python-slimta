
import unittest

from slimta.smtp.server import Server
from slimta.smtp import ConnectionLost

from mock.socket import MockSocket


class TestSmtpServer(unittest.TestCase):

    def setUp(self):
        self.tls_args = {'server_side': True}

    def test_starttls_extension(self):
        s = Server(None, None)
        self.assertFalse('STARTTLS' in s.extensions)
        s = Server(None, None, tls=self.tls_args, tls_immediately=False)
        self.assertTrue('STARTTLS' in s.extensions)
        s = Server(None, None, tls=self.tls_args, tls_immediately=True)
        self.assertFalse('STARTTLS' in s.extensions)

    def test_recv_command(self):
        sock = MockSocket([('recv', 'cmd ARG\r\n')])
        s = Server(sock, None)
        cmd, arg = s._recv_command()
        self.assertEqual('CMD', cmd)
        self.assertEqual('ARG', arg)
        sock.assert_done(self)

    def test_get_message_data(self):
        expected_reply = '250 2.6.0 Message Accepted for Delivery\r\n'
        sock = MockSocket([('recv', 'one\r\n'), ('recv', '.\r\n'),
                           ('send', expected_reply)])
        s = Server(sock, None)
        s._get_message_data()
        self.assertFalse(s.have_mailfrom)
        self.assertFalse(s.have_rcptto)

    def test_call_custom_handler(self):
        class TestHandler(object):
            def TEST(self, arg):
                return arg.lower()
        s = Server(None, TestHandler())
        self.assertEqual('stuff', s._call_custom_handler('TEST', 'STUFF'))

    def test_banner_quit(self):
        sock = MockSocket([('send', '220 ESMTP server\r\n'),
                           ('recv', 'QUIT\r\n'),
                           ('send', '221 2.0.0 Bye\r\n')])
        s = Server(sock, None)
        s.handle()
        sock.assert_done(self)

    def test_unhandled_error(self):
        class TestHandler(object):
            def BANNER(self, reply):
                raise Exception('test')
        sock = MockSocket([('send', '421 4.3.0 Unhandled system error\r\n')])
        s = Server(sock, TestHandler())
        with self.assertRaises(Exception) as cm:
            s.handle()
        self.assertEqual(('test', ), cm.exception.args)
        sock.assert_done(self)

    def test_tls_immediately(self):
        sock = MockSocket([('encrypt', self.tls_args),
                           ('send', '220 ESMTP server\r\n'),
                           ('recv', 'QUIT\r\n'),
                           ('send', '221 2.0.0 Bye\r\n')])
        s = Server(sock, None, tls=self.tls_args, tls_immediately=True,
                               tls_wrapper=sock.tls_wrapper)
        s.handle()
        sock.assert_done(self)

    def test_ehlo(self):
        sock = MockSocket([('send', '220 ESMTP server\r\n'),
                           ('recv', 'EHLO there\r\n'),
                           ('send', '250-Hello there\r\n250 TEST\r\n'),
                           ('recv', 'QUIT\r\n'),
                           ('send', '221 2.0.0 Bye\r\n')])
        s = Server(sock, None)
        s.extensions.reset()
        s.extensions.add('TEST')
        s.handle()
        self.assertEqual('there', s.ehlo_as)
        sock.assert_done(self)

    def test_helo(self):
        sock = MockSocket([('send', '220 ESMTP server\r\n'),
                           ('recv', 'HELO there\r\n'),
                           ('send', '250 Hello there\r\n'),
                           ('recv', 'QUIT\r\n'),
                           ('send', '221 2.0.0 Bye\r\n')])
        s = Server(sock, None)
        s.handle()
        self.assertEqual('there', s.ehlo_as)
        sock.assert_done(self)

    def test_starttls(self):
        sock = MockSocket([('send', '220 ESMTP server\r\n'),
                           ('recv', 'EHLO there\r\n'),
                           ('send', '250-Hello there\r\n250 STARTTLS\r\n'),
                           ('recv', 'STARTTLS\r\n'),
                           ('send', '220 2.7.0 Go ahead\r\n'),
                           ('encrypt', self.tls_args),
                           ('recv', 'QUIT\r\n'),
                           ('send', '221 2.0.0 Bye\r\n')])
        s = Server(sock, None, tls=self.tls_args, tls_wrapper=sock.tls_wrapper)
        s.extensions.reset()
        s.extensions.add('STARTTLS')
        s.handle()
        self.assertEqual(None, s.ehlo_as)
        sock.assert_done(self)

    def test_starttls_bad(self):
        sock = MockSocket([('send', '220 ESMTP server\r\n'),
                           ('recv', 'STARTTLS\r\n'),
                           ('send', '503 5.5.1 Bad sequence of commands\r\n'),
                           ('recv', 'STARTTLS badarg\r\n'),
                           ('send', '501 5.5.4 Syntax error in parameters or arguments\r\n'),
                           ('recv', 'QUIT\r\n'),
                           ('send', '221 2.0.0 Bye\r\n')])
        s = Server(sock, None, tls=self.tls_args)
        s.extensions.reset()
        s.extensions.add('STARTTLS')
        s.handle()
        self.assertEqual(None, s.ehlo_as)
        sock.assert_done(self)

    def test_mailfrom(self):
        sock = MockSocket([('send', '220 ESMTP server\r\n'),
                           ('recv', 'HELO there\r\n'),
                           ('send', '250 Hello there\r\n'),
                           ('recv', 'MAIL FROM:<test">"addr>\r\n'),
                           ('send', '250 2.1.0 Sender <test">"addr> Ok\r\n'),
                           ('recv', 'QUIT\r\n'),
                           ('send', '221 2.0.0 Bye\r\n')])
        s = Server(sock, None)
        s.handle()
        self.assertTrue(s.have_mailfrom)
        sock.assert_done(self)

    def test_mailfrom_bad(self):
        sock = MockSocket([('send', '220 ESMTP server\r\n'),
                           ('recv', 'MAIL FROM:<test>\r\n'),
                           ('send', '503 5.5.1 Bad sequence of commands\r\n'),
                           ('recv', 'HELO there\r\n'),
                           ('send', '250 Hello there\r\n'),
                           ('recv', 'MAIL FROM:<test1> SIZE=5\r\n'),
                           ('send', '504 5.5.4 Command parameter not implemented\r\n'),
                           ('recv', 'MAIL FRM:<addr>\r\n'),
                           ('send', '501 5.5.4 Syntax error in parameters or arguments\r\n'),
                           ('recv', 'MAIL FROM:<addr\r\n'),
                           ('send', '501 5.5.4 Syntax error in parameters or arguments\r\n'),
                           ('recv', 'MAIL FROM:<test1>\r\n'),
                           ('send', '250 2.1.0 Sender <test1> Ok\r\n'),
                           ('recv', 'MAIL FROM:<test2>\r\n'),
                           ('send', '503 5.5.1 Bad sequence of commands\r\n'),
                           ('recv', 'QUIT\r\n'),
                           ('send', '221 2.0.0 Bye\r\n')])
        s = Server(sock, None)
        s.handle()
        self.assertTrue(s.have_mailfrom)
        sock.assert_done(self)

    def test_mailfrom_send_extension(self):
        sock = MockSocket([('send', '220 ESMTP server\r\n'),
                           ('recv', 'EHLO there\r\n'),
                           ('send', '250-Hello there\r\n250 SIZE 10\r\n'),
                           ('recv', 'MAIL FROM:<test1> SIZE=ASDF\r\n'),
                           ('send', '501 5.5.4 Syntax error in parameters or arguments\r\n'),
                           ('recv', 'MAIL FROM:<test1> SIZE=20\r\n'),
                           ('send', '552 5.3.4 Message size exceeds 10 limit\r\n'),
                           ('recv', 'MAIL FROM:<test1> SIZE=5\r\n'),
                           ('send', '250 2.1.0 Sender <test1> Ok\r\n'),
                           ('recv', 'QUIT\r\n'),
                           ('send', '221 2.0.0 Bye\r\n')])
        s = Server(sock, None)
        s.extensions.reset()
        s.extensions.add('SIZE', 10)
        s.handle()
        self.assertTrue(s.have_mailfrom)
        sock.assert_done(self)

    def test_rcptto(self):
        sock = MockSocket([('send', '220 ESMTP server\r\n'),
                           ('recv', 'RCPT TO:<test">"addr>\r\n'),
                           ('send', '250 2.1.5 Recipient <test">"addr> Ok\r\n'),
                           ('recv', 'RCPT TO:<test2>\r\n'),
                           ('send', '250 2.1.5 Recipient <test2> Ok\r\n'),
                           ('recv', 'QUIT\r\n'),
                           ('send', '221 2.0.0 Bye\r\n')])
        s = Server(sock, None)
        s.ehlo_as = 'test'
        s.have_mailfrom = True
        s.handle()
        self.assertTrue(s.have_rcptto)
        sock.assert_done(self)

    def test_rcptto_bad(self):
        sock = MockSocket([('send', '220 ESMTP server\r\n'),
                           ('recv', 'RCPT TO:<test>\r\n'),
                           ('send', '503 5.5.1 Bad sequence of commands\r\n'),
                           ('recv', 'HELO there\r\n'),
                           ('send', '250 Hello there\r\n'),
                           ('recv', 'RCPT TO:<test>\r\n'),
                           ('send', '503 5.5.1 Bad sequence of commands\r\n'),
                           ('recv', 'MAIL FROM:<test1>\r\n'),
                           ('send', '250 2.1.0 Sender <test1> Ok\r\n'),
                           ('recv', 'RCPT T:<test1>\r\n'),
                           ('send', '501 5.5.4 Syntax error in parameters or arguments\r\n'),
                           ('recv', 'RCPT TO:<test1\r\n'),
                           ('send', '501 5.5.4 Syntax error in parameters or arguments\r\n'),
                           ('recv', 'QUIT\r\n'),
                           ('send', '221 2.0.0 Bye\r\n')])
        s = Server(sock, None)
        s.handle()
        self.assertFalse(s.have_rcptto)
        sock.assert_done(self)

    def test_data(self):
        sock = MockSocket([('send', '220 ESMTP server\r\n'),
                           ('recv', 'DATA\r\n'),
                           ('send', '354 Start mail input; end with <CRLF>.<CRLF>\r\n'),
                           ('recv', '.\r\nQUIT\r\n'),
                           ('send', '250 2.6.0 Message Accepted for Delivery\r\n'),
                           ('send', '221 2.0.0 Bye\r\n')])
        s = Server(sock, None)
        s.ehlo_as = 'test'
        s.have_mailfrom = True
        s.have_rcptto = True
        s.handle()
        sock.assert_done(self)

    def test_data_bad(self):
        sock = MockSocket([('send', '220 ESMTP server\r\n'),
                           ('recv', 'DATA arg\r\n'),
                           ('send', '501 5.5.4 Syntax error in parameters or arguments\r\n'),
                           ('recv', 'DATA\r\n'),
                           ('send', '503 5.5.1 Bad sequence of commands\r\n'),
                           ('recv', 'QUIT\r\n'),
                           ('send', '221 2.0.0 Bye\r\n')])
        s = Server(sock, None)
        s.ehlo_as = 'test'
        s.have_mailfrom = True
        s.handle()
        sock.assert_done(self)

    def test_data_connectionlost(self):
        sock = MockSocket([('send', '220 ESMTP server\r\n'),
                           ('recv', 'DATA\r\n'),
                           ('send', '354 Start mail input; end with <CRLF>.<CRLF>\r\n'),
                           ('recv', '')])
        s = Server(sock, None)
        s.ehlo_as = 'test'
        s.have_mailfrom = True
        s.have_rcptto = True
        self.assertRaises(ConnectionLost, s.handle)
        sock.assert_done(self)

    def test_noop(self):
        sock = MockSocket([('send', '220 ESMTP server\r\n'),
                           ('recv', 'NOOP\r\n'),
                           ('send', '250 2.0.0 Ok\r\n'),
                           ('recv', 'QUIT\r\n'),
                           ('send', '221 2.0.0 Bye\r\n')])
        s = Server(sock, None)
        s.handle()
        sock.assert_done(self)

    def test_rset(self):
        class TestHandlers(object):
            server = None
            def NOOP(self2, reply):
                self.assertEqual('test', self2.server.ehlo_as)
                self.assertFalse(self2.server.have_mailfrom)
                self.assertFalse(self2.server.have_rcptto)
        sock = MockSocket([('send', '220 ESMTP server\r\n'),
                           ('recv', 'RSET arg\r\n'),
                           ('send', '501 5.5.4 Syntax error in parameters or arguments\r\n'),
                           ('recv', 'RSET\r\n'),
                           ('send', '250 2.0.0 Ok\r\n'),
                           ('recv', 'NOOP\r\n'),
                           ('send', '250 2.0.0 Ok\r\n'),
                           ('recv', 'QUIT\r\n'),
                           ('send', '221 2.0.0 Bye\r\n')])
        h = TestHandlers()
        s = h.server = Server(sock, h)
        s.ehlo_as = 'test'
        s.have_mailfrom = True
        s.have_rcptto = True
        s.handle()
        sock.assert_done(self)

    def test_quit_bad(self):
        sock = MockSocket([('send', '220 ESMTP server\r\n'),
                           ('recv', 'QUIT arg\r\n'),
                           ('send', '501 5.5.4 Syntax error in parameters or arguments\r\n'),
                           ('recv', 'QUIT\r\n'),
                           ('send', '221 2.0.0 Bye\r\n')])
        s = Server(sock, None)
        s.handle()
        sock.assert_done(self)

    def test_custom_command(self):
        class TestHandlers(object):
            def TEST(self2, reply, arg, server):
                self.assertTrue(server.have_mailfrom)
                reply.code = '250'
                reply.message = 'Doing '+arg
        sock = MockSocket([('send', '220 ESMTP server\r\n'),
                           ('recv', 'TEST stuff\r\n'),
                           ('send', '250 2.0.0 Doing stuff\r\n'),
                           ('recv', 'QUIT\r\n'),
                           ('send', '221 2.0.0 Bye\r\n')])
        s = Server(sock, TestHandlers())
        s.have_mailfrom = True
        s.handle()
        sock.assert_done(self)

    def test_bad_commands(self):
        sock = MockSocket([('send', '220 ESMTP server\r\n'),
                           ('recv', '\r\n'),
                           ('send', '500 5.5.2 Syntax error, command unrecognized\r\n'),
                           ('recv', 'BADCMD\r\n'),
                           ('send', '500 5.5.2 Syntax error, command unrecognized\r\n'),
                           ('recv', 'STARTTLS\r\n'),
                           ('send', '500 5.5.2 Syntax error, command unrecognized\r\n'),
                           ('recv', 'AUTH\r\n'),
                           ('send', '500 5.5.2 Syntax error, command unrecognized\r\n'),
                           ('recv', 'QUIT\r\n'),
                           ('send', '221 2.0.0 Bye\r\n')])
        s = Server(sock, None)
        s.handle()
        sock.assert_done(self)



# vim:et:fdm=marker:sts=4:sw=4:ts=4
