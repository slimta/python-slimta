
from assertions import *

from mox import MoxTestBase, IsA
from gevent.socket import socket

from slimta.smtp.client import Client, LmtpClient
from slimta.smtp.reply import Reply
from slimta.smtp.auth.standard import Plain


class TestSmtpClient(MoxTestBase):

    def setUp(self):
        super(TestSmtpClient, self).setUp()
        self.sock = self.mox.CreateMock(socket)
        self.sock.fileno = lambda: -1
        self.tls_args = {'test': 'test'}

    def test_get_reply(self):
        self.sock.recv(IsA(int)).AndReturn('421 Test\r\n')
        self.mox.ReplayAll()
        client = Client(self.sock)
        reply = client.get_reply('[TEST]')
        assert_equal('421', reply.code)
        assert_equal('4.0.0 Test', reply.message)
        assert_equal('[TEST]', reply.command)

    def test_get_banner(self):
        self.sock.recv(IsA(int)).AndReturn('220 Go\r\n')
        self.mox.ReplayAll()
        client = Client(self.sock)
        reply = client.get_banner()
        assert_equal('220', reply.code)
        assert_equal('Go', reply.message)
        assert_equal('[BANNER]', reply.command)

    def test_custom_command(self):
        self.sock.sendall('cmd arg\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 Ok\r\n')
        self.mox.ReplayAll()
        client = Client(self.sock)
        reply = client.custom_command('cmd', 'arg')
        assert_equal('250', reply.code)
        assert_equal('2.0.0 Ok', reply.message)
        assert_equal('CMD', reply.command)

    def test_ehlo(self):
        self.sock.sendall('EHLO there\r\n')
        self.sock.recv(IsA(int)).AndReturn('250-Hello there\r\n250-TEST arg\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 EXTEN\r\n')
        self.mox.ReplayAll()
        client = Client(self.sock)
        reply = client.ehlo('there')
        assert_equal('250', reply.code)
        assert_equal('Hello there', reply.message)
        assert_equal('EHLO', reply.command)
        assert_true('TEST' in client.extensions)
        assert_true('EXTEN' in client.extensions)
        assert_equal('arg', client.extensions.getparam('TEST'))

    def test_helo(self):
        self.sock.sendall('HELO there\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 Hello\r\n')
        self.mox.ReplayAll()
        client = Client(self.sock)
        reply = client.helo('there')
        assert_equal('250', reply.code)
        assert_equal('Hello', reply.message)
        assert_equal('HELO', reply.command)

    def test_starttls(self):
        sock = self.mox.CreateMockAnything()
        sock.fileno = lambda: -1
        sock.sendall('STARTTLS\r\n')
        sock.recv(IsA(int)).AndReturn('220 Go ahead\r\n')
        sock.tls_wrapper(sock, self.tls_args).AndReturn(sock)
        self.mox.ReplayAll()
        client = Client(sock, tls_wrapper=sock.tls_wrapper)
        reply = client.starttls(self.tls_args)
        assert_equal('220', reply.code)
        assert_equal('2.0.0 Go ahead', reply.message)
        assert_equal('STARTTLS', reply.command)

    def test_starttls_noencrypt(self):
        self.sock.sendall('STARTTLS\r\n')
        self.sock.recv(IsA(int)).AndReturn('420 Nope\r\n')
        self.mox.ReplayAll()
        client = Client(self.sock)
        reply = client.starttls({})
        assert_equal('420', reply.code)
        assert_equal('4.0.0 Nope', reply.message)
        assert_equal('STARTTLS', reply.command)

    def test_auth(self):
        self.sock.sendall('AUTH PLAIN AHRlc3RAZXhhbXBsZS5jb20AYXNkZg==\r\n')
        self.sock.recv(IsA(int)).AndReturn('235 Ok\r\n')
        self.mox.ReplayAll()
        client = Client(self.sock)
        client.extensions.add('AUTH', 'PLAIN')
        reply = client.auth('test@example.com', 'asdf')
        assert_equal('235', reply.code)
        assert_equal('2.0.0 Ok', reply.message)
        assert_equal('AUTH', reply.command)

    def test_auth_force_mechanism(self):
        self.sock.sendall('AUTH PLAIN AHRlc3RAZXhhbXBsZS5jb20AYXNkZg==\r\n')
        self.sock.recv(IsA(int)).AndReturn('535 Nope!\r\n')
        self.mox.ReplayAll()
        client = Client(self.sock)
        reply = client.auth('test@example.com', 'asdf', mechanism=Plain)
        assert_equal('535', reply.code)
        assert_equal('5.0.0 Nope!', reply.message)
        assert_equal('AUTH', reply.command)

    def test_mailfrom(self):
        self.sock.sendall('MAIL FROM:<test>\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 2.0.0 Ok\r\n')
        self.mox.ReplayAll()
        client = Client(self.sock)
        reply = client.mailfrom('test')
        assert_equal('250', reply.code)
        assert_equal('2.0.0 Ok', reply.message)
        assert_equal('MAIL', reply.command)

    def test_mailfrom_pipelining(self):
        self.sock.sendall('MAIL FROM:<test>\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 2.0.0 Ok\r\n')
        self.mox.ReplayAll()
        client = Client(self.sock)
        client.extensions.add('PIPELINING')
        reply = client.mailfrom('test')
        assert_equal(None, reply.code)
        assert_equal(None, reply.message)
        assert_equal('MAIL', reply.command)
        client._flush_pipeline()
        assert_equal('250', reply.code)
        assert_equal('2.0.0 Ok', reply.message)

    def test_mailfrom_size(self):
        self.sock.sendall('MAIL FROM:<test> SIZE=10\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 2.0.0 Ok\r\n')
        self.mox.ReplayAll()
        client = Client(self.sock)
        client.extensions.add('SIZE', 100)
        reply = client.mailfrom('test', 10)
        assert_equal('250', reply.code)
        assert_equal('2.0.0 Ok', reply.message)
        assert_equal('MAIL', reply.command)

    def test_rcptto(self):
        self.sock.sendall('RCPT TO:<test>\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 2.0.0 Ok\r\n')
        self.mox.ReplayAll()
        client = Client(self.sock)
        reply = client.rcptto('test')
        assert_equal('250', reply.code)
        assert_equal('2.0.0 Ok', reply.message)
        assert_equal('RCPT', reply.command)

    def test_rcptto_pipelining(self):
        self.sock.sendall('RCPT TO:<test>\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 2.0.0 Ok\r\n')
        self.mox.ReplayAll()
        client = Client(self.sock)
        client.extensions.add('PIPELINING')
        reply = client.rcptto('test')
        assert_equal(None, reply.code)
        assert_equal(None, reply.message)
        assert_equal('RCPT', reply.command)
        client._flush_pipeline()
        assert_equal('250', reply.code)
        assert_equal('2.0.0 Ok', reply.message)

    def test_data(self):
        self.sock.sendall('DATA\r\n')
        self.sock.recv(IsA(int)).AndReturn('354 Go ahead\r\n')
        self.mox.ReplayAll()
        client = Client(self.sock)
        reply = client.data()
        assert_equal('354', reply.code)
        assert_equal('Go ahead', reply.message)
        assert_equal('DATA', reply.command)

    def test_send_empty_data(self):
        self.sock.sendall('.\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 2.0.0 Done\r\n')
        self.mox.ReplayAll()
        client = Client(self.sock)
        reply = client.send_empty_data()
        assert_equal('250', reply.code)
        assert_equal('2.0.0 Done', reply.message)
        assert_equal('[SEND_DATA]', reply.command)

    def test_send_data(self):
        self.sock.sendall('One\r\nTwo\r\n..Three\r\n.\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 2.0.0 Done\r\n')
        self.mox.ReplayAll()
        client = Client(self.sock)
        reply = client.send_data('One\r\nTwo\r\n.Three')
        assert_equal('250', reply.code)
        assert_equal('2.0.0 Done', reply.message)
        assert_equal('[SEND_DATA]', reply.command)

    def test_rset(self):
        self.sock.sendall('RSET\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 Ok\r\n')
        self.mox.ReplayAll()
        client = Client(self.sock)
        reply = client.rset()
        assert_equal('250', reply.code)
        assert_equal('2.0.0 Ok', reply.message)
        assert_equal('RSET', reply.command)

    def test_quit(self):
        self.sock.sendall('QUIT\r\n')
        self.sock.recv(IsA(int)).AndReturn('221 Bye\r\n')
        self.mox.ReplayAll()
        client = Client(self.sock)
        reply = client.quit()
        assert_equal('221', reply.code)
        assert_equal('2.0.0 Bye', reply.message)
        assert_equal('QUIT', reply.command)


class TestLmtpClient(MoxTestBase):

    def setUp(self):
        super(TestLmtpClient, self).setUp()
        self.sock = self.mox.CreateMock(socket)
        self.sock.fileno = lambda: -1
        self.tls_args = {'test': 'test'}

    def test_ehlo_invalid(self):
        client = LmtpClient(self.sock)
        assert_raises(NotImplementedError, client.ehlo, 'there')

    def test_helo_invalid(self):
        client = LmtpClient(self.sock)
        assert_raises(NotImplementedError, client.helo, 'there')

    def test_lhlo(self):
        self.sock.sendall('LHLO there\r\n')
        self.sock.recv(IsA(int)).AndReturn('250-Hello there\r\n250-TEST arg\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 EXTEN\r\n')
        self.mox.ReplayAll()
        client = LmtpClient(self.sock)
        reply = client.lhlo('there')
        assert_equal('250', reply.code)
        assert_equal('Hello there', reply.message)
        assert_equal('LHLO', reply.command)
        assert_true('TEST' in client.extensions)
        assert_true('EXTEN' in client.extensions)
        assert_equal('arg', client.extensions.getparam('TEST'))

    def test_rcptto(self):
        self.sock.sendall('RCPT TO:<test>\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 2.0.0 Ok\r\n')
        self.mox.ReplayAll()
        client = LmtpClient(self.sock)
        reply = client.rcptto('test')
        assert_equal('250', reply.code)
        assert_equal('2.0.0 Ok', reply.message)
        assert_equal('RCPT', reply.command)
        assert_equal([('test', reply)], client.rcpttos)

    def test_rset(self):
        self.sock.sendall('RSET\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 Ok\r\n')
        self.mox.ReplayAll()
        client = LmtpClient(self.sock)
        client.rcpttos = 'testing'
        reply = client.rset()
        assert_equal('250', reply.code)
        assert_equal('2.0.0 Ok', reply.message)
        assert_equal('RSET', reply.command)
        assert_equal([], client.rcpttos)

    def test_send_data(self):
        self.sock.sendall('One\r\nTwo\r\n..Three\r\n.\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 2.0.0 Ok\r\n'
                                           '550 5.0.0 Not Ok\r\n')
        self.mox.ReplayAll()
        client = LmtpClient(self.sock)
        client.rcpttos = [('test1', Reply('250')),
                          ('test2', Reply('250')),
                          ('test3', Reply('550'))]
        replies = client.send_data('One\r\nTwo\r\n.Three')
        assert_equal(2, len(replies))
        assert_equal('test1', replies[0][0])
        assert_equal('250', replies[0][1].code)
        assert_equal('2.0.0 Ok', replies[0][1].message)
        assert_equal('[SEND_DATA]', replies[0][1].command)
        assert_equal('test2', replies[1][0])
        assert_equal('550', replies[1][1].code)
        assert_equal('5.0.0 Not Ok', replies[1][1].message)
        assert_equal('[SEND_DATA]', replies[1][1].command)

    def test_send_empty_data(self):
        self.sock.sendall('.\r\n')
        self.sock.recv(IsA(int)).AndReturn('250 2.0.0 Ok\r\n'
                                           '550 5.0.0 Not Ok\r\n')
        self.mox.ReplayAll()
        client = LmtpClient(self.sock)
        client.rcpttos = [('test1', Reply('250')),
                          ('test2', Reply('250')),
                          ('test3', Reply('550'))]
        replies = client.send_empty_data()
        assert_equal(2, len(replies))
        assert_equal('test1', replies[0][0])
        assert_equal('250', replies[0][1].code)
        assert_equal('2.0.0 Ok', replies[0][1].message)
        assert_equal('[SEND_DATA]', replies[0][1].command)
        assert_equal('test2', replies[1][0])
        assert_equal('550', replies[1][1].code)
        assert_equal('5.0.0 Not Ok', replies[1][1].message)
        assert_equal('[SEND_DATA]', replies[1][1].command)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
