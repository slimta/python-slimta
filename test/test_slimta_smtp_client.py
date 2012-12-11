
import unittest

from slimta.smtp.client import Client

from mock.socket import MockSocket


class TestSmtpClient(unittest.TestCase):

    def test_get_banner(self):
        sock = MockSocket([('recv', '220 Go\r\n')])
        client = Client(sock)
        reply = client.get_banner()
        self.assertEqual('220', reply.code)
        self.assertEqual('Go', reply.message)
        self.assertEqual('[BANNER]', reply.command)
        sock.assert_done(self)

    def test_custom_command(self):
        sock = MockSocket([('send', 'cmd arg\r\n'),
                           ('recv', '250 Ok\r\n')])
        client = Client(sock)
        reply = client.custom_command('cmd', 'arg')
        self.assertEqual('250', reply.code)
        self.assertEqual('2.0.0 Ok', reply.message)
        self.assertEqual('CMD', reply.command)
        sock.assert_done(self)

    def test_ehlo(self):
        sock = MockSocket([('send', 'EHLO there\r\n'),
                           ('recv', '250-Hello there\r\n250-TEST arg\r\n'),
                           ('recv', '250 EXTEN\r\n')])
        client = Client(sock)
        reply = client.ehlo('there')
        self.assertEqual('250', reply.code)
        self.assertEqual('Hello there', reply.message)
        self.assertEqual('EHLO', reply.command)
        self.assertTrue('TEST' in client.extensions)
        self.assertTrue('EXTEN' in client.extensions)
        self.assertEqual('arg', client.extensions.getparam('TEST'))
        sock.assert_done(self)

    def test_helo(self):
        sock = MockSocket([('send', 'HELO there\r\n'),
                           ('recv', '250 Hello\r\n')])
        client = Client(sock)
        reply = client.helo('there')
        self.assertEqual('250', reply.code)
        self.assertEqual('Hello', reply.message)
        self.assertEqual('HELO', reply.command)
        sock.assert_done(self)

    def test_starttls_noencrypt(self):
        sock = MockSocket([('send', 'STARTTLS\r\n'),
                           ('recv', '420 Nope\r\n')])
        client = Client(sock)
        reply = client.starttls({})
        self.assertEqual('420', reply.code)
        self.assertEqual('4.0.0 Nope', reply.message)
        self.assertEqual('STARTTLS', reply.command)
        sock.assert_done(self)

    def test_mailfrom(self):
        sock = MockSocket([('send', 'MAIL FROM:<test>\r\n'),
                           ('recv', '250 2.0.0 Ok\r\n')])
        client = Client(sock)
        reply = client.mailfrom('test')
        self.assertEqual('250', reply.code)
        self.assertEqual('2.0.0 Ok', reply.message)
        self.assertEqual('MAIL', reply.command)
        sock.assert_done(self)

    def test_mailfrom_pipelining(self):
        sock = MockSocket([('send', 'MAIL FROM:<test>\r\n'),
                           ('recv', '250 2.0.0 Ok\r\n')])
        client = Client(sock)
        client.extensions.add('PIPELINING')
        reply = client.mailfrom('test')
        self.assertEqual(None, reply.code)
        self.assertEqual(None, reply.message)
        self.assertEqual('MAIL', reply.command)
        client._flush_pipeline()
        self.assertEqual('250', reply.code)
        self.assertEqual('2.0.0 Ok', reply.message)
        sock.assert_done(self)

    def test_mailfrom_size(self):
        sock = MockSocket([('send', 'MAIL FROM:<test> SIZE=10\r\n'),
                           ('recv', '250 2.0.0 Ok\r\n')])
        client = Client(sock)
        client.extensions.add('SIZE', 100)
        reply = client.mailfrom('test', 10)
        self.assertEqual('250', reply.code)
        self.assertEqual('2.0.0 Ok', reply.message)
        self.assertEqual('MAIL', reply.command)
        sock.assert_done(self)

    def test_rcptto(self):
        sock = MockSocket([('send', 'RCPT TO:<test>\r\n'),
                           ('recv', '250 2.0.0 Ok\r\n')])
        client = Client(sock)
        reply = client.rcptto('test')
        self.assertEqual('250', reply.code)
        self.assertEqual('2.0.0 Ok', reply.message)
        self.assertEqual('RCPT', reply.command)
        sock.assert_done(self)

    def test_rcptto_pipelining(self):
        sock = MockSocket([('send', 'RCPT TO:<test>\r\n'),
                           ('recv', '250 2.0.0 Ok\r\n')])
        client = Client(sock)
        client.extensions.add('PIPELINING')
        reply = client.rcptto('test')
        self.assertEqual(None, reply.code)
        self.assertEqual(None, reply.message)
        self.assertEqual('RCPT', reply.command)
        client._flush_pipeline()
        self.assertEqual('250', reply.code)
        self.assertEqual('2.0.0 Ok', reply.message)
        sock.assert_done(self)

    def test_data(self):
        sock = MockSocket([('send', 'DATA\r\n'),
                           ('recv', '354 Go ahead\r\n')])
        client = Client(sock)
        reply = client.data()
        self.assertEqual('354', reply.code)
        self.assertEqual('Go ahead', reply.message)
        self.assertEqual('DATA', reply.command)
        sock.assert_done(self)

    def test_send_empty_data(self):
        sock = MockSocket([('send', '.\r\n'),
                           ('recv', '250 2.0.0 Done\r\n')])
        client = Client(sock)
        reply = client.send_empty_data()
        self.assertEqual('250', reply.code)
        self.assertEqual('2.0.0 Done', reply.message)
        self.assertEqual('[SEND_DATA]', reply.command)
        sock.assert_done(self)

    def test_send_data(self):
        sock = MockSocket([('send', 'One\r\nTwo\r\n..Three\r\n.\r\n'),
                           ('recv', '250 2.0.0 Done\r\n')])
        client = Client(sock)
        reply = client.send_data('One\r\nTwo\r\n.Three')
        self.assertEqual('250', reply.code)
        self.assertEqual('2.0.0 Done', reply.message)
        self.assertEqual('[SEND_DATA]', reply.command)
        sock.assert_done(self)

    def test_rset(self):
        sock = MockSocket([('send', 'RSET\r\n'),
                           ('recv', '250 Ok\r\n')])
        client = Client(sock)
        reply = client.rset()
        self.assertEqual('250', reply.code)
        self.assertEqual('2.0.0 Ok', reply.message)
        self.assertEqual('RSET', reply.command)
        sock.assert_done(self)

    def test_quit(self):
        sock = MockSocket([('send', 'QUIT\r\n'),
                           ('recv', '221 Bye\r\n')])
        client = Client(sock)
        reply = client.quit()
        self.assertEqual('221', reply.code)
        self.assertEqual('2.0.0 Bye', reply.message)
        self.assertEqual('QUIT', reply.command)
        sock.assert_done(self)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
