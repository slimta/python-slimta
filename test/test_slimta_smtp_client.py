import unittest2 as unittest
from mox3.mox import MoxTestBase, IsA
from gevent.socket import socket

from slimta.smtp.client import Client, LmtpClient
from slimta.smtp.reply import Reply


class TestSmtpClient(unittest.TestCase, MoxTestBase):

    def setUp(self):
        super(TestSmtpClient, self).setUp()
        self.sock = self.mox.CreateMock(socket)
        self.sock.fileno = lambda: -1
        self.sock.getpeername = lambda: ('test', 0)
        self.tls_args = {'test': 'test'}

    def test_get_reply(self):
        self.sock.recv(IsA(int)).AndReturn(b'421 Test\r\n')
        self.mox.ReplayAll()
        client = Client(self.sock)
        reply = client.get_reply(b'[TEST]')
        self.assertEqual('421', reply.code)
        self.assertEqual('4.0.0 Test', reply.message)
        self.assertEqual(b'[TEST]', reply.command)

    def test_get_banner(self):
        self.sock.recv(IsA(int)).AndReturn(b'220 Go\r\n')
        self.mox.ReplayAll()
        client = Client(self.sock)
        reply = client.get_banner()
        self.assertEqual('220', reply.code)
        self.assertEqual('Go', reply.message)
        self.assertEqual(b'[BANNER]', reply.command)

    def test_custom_command(self):
        self.sock.sendall(b'cmd arg\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250 Ok\r\n')
        self.mox.ReplayAll()
        client = Client(self.sock)
        reply = client.custom_command(b'cmd', b'arg')
        self.assertEqual('250', reply.code)
        self.assertEqual('2.0.0 Ok', reply.message)
        self.assertEqual(b'CMD', reply.command)

    def test_ehlo(self):
        self.sock.sendall(b'EHLO there\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250-Hello there\r\n250-TEST arg\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250 EXTEN\r\n')
        self.mox.ReplayAll()
        client = Client(self.sock)
        reply = client.ehlo('there')
        self.assertEqual('250', reply.code)
        self.assertEqual('Hello there', reply.message)
        self.assertEqual(b'EHLO', reply.command)
        self.assertTrue('TEST' in client.extensions)
        self.assertTrue('EXTEN' in client.extensions)
        self.assertEqual('arg', client.extensions.getparam('TEST'))

    def test_helo(self):
        self.sock.sendall(b'HELO there\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250 Hello\r\n')
        self.mox.ReplayAll()
        client = Client(self.sock)
        reply = client.helo('there')
        self.assertEqual('250', reply.code)
        self.assertEqual('Hello', reply.message)
        self.assertEqual(b'HELO', reply.command)

    def test_starttls(self):
        sock = self.mox.CreateMockAnything()
        sock.fileno = lambda: -1
        sock.getpeername = lambda: ('test', 0)
        sock.sendall(b'STARTTLS\r\n')
        sock.recv(IsA(int)).AndReturn(b'220 Go ahead\r\n')
        sock.tls_wrapper(sock, self.tls_args).AndReturn(sock)
        self.mox.ReplayAll()
        client = Client(sock, tls_wrapper=sock.tls_wrapper)
        reply = client.starttls(self.tls_args)
        self.assertEqual('220', reply.code)
        self.assertEqual('2.0.0 Go ahead', reply.message)
        self.assertEqual(b'STARTTLS', reply.command)

    def test_starttls_noencrypt(self):
        self.sock.sendall(b'STARTTLS\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'420 Nope\r\n')
        self.mox.ReplayAll()
        client = Client(self.sock)
        reply = client.starttls({})
        self.assertEqual('420', reply.code)
        self.assertEqual('4.0.0 Nope', reply.message)
        self.assertEqual(b'STARTTLS', reply.command)

    def test_auth(self):
        self.sock.sendall(b'AUTH PLAIN AHRlc3RAZXhhbXBsZS5jb20AYXNkZg==\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'235 Ok\r\n')
        self.mox.ReplayAll()
        client = Client(self.sock)
        client.extensions.add('AUTH', b'PLAIN')
        reply = client.auth('test@example.com', 'asdf')
        self.assertEqual('235', reply.code)
        self.assertEqual('2.0.0 Ok', reply.message)
        self.assertEqual(b'AUTH', reply.command)

    def test_auth_force_mechanism(self):
        self.sock.sendall(b'AUTH PLAIN AHRlc3RAZXhhbXBsZS5jb20AYXNkZg==\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'535 Nope!\r\n')
        self.mox.ReplayAll()
        client = Client(self.sock)
        reply = client.auth('test@example.com', 'asdf', mechanism=b'PLAIN')
        self.assertEqual('535', reply.code)
        self.assertEqual('5.0.0 Nope!', reply.message)
        self.assertEqual(b'AUTH', reply.command)

    def test_mailfrom(self):
        self.sock.sendall(b'MAIL FROM:<test>\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250 2.0.0 Ok\r\n')
        self.mox.ReplayAll()
        client = Client(self.sock)
        reply = client.mailfrom('test')
        self.assertEqual('250', reply.code)
        self.assertEqual('2.0.0 Ok', reply.message)
        self.assertEqual(b'MAIL', reply.command)

    def test_mailfrom_pipelining(self):
        self.sock.sendall(b'MAIL FROM:<test>\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250 2.0.0 Ok\r\n')
        self.mox.ReplayAll()
        client = Client(self.sock)
        client.extensions.add('PIPELINING')
        reply = client.mailfrom('test')
        self.assertEqual(None, reply.code)
        self.assertEqual(None, reply.message)
        self.assertEqual(b'MAIL', reply.command)
        client._flush_pipeline()
        self.assertEqual('250', reply.code)
        self.assertEqual('2.0.0 Ok', reply.message)

    def test_mailfrom_size(self):
        self.sock.sendall(b'MAIL FROM:<test> SIZE=10\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250 2.0.0 Ok\r\n')
        self.mox.ReplayAll()
        client = Client(self.sock)
        client.extensions.add('SIZE', 100)
        reply = client.mailfrom('test', 10)
        self.assertEqual('250', reply.code)
        self.assertEqual('2.0.0 Ok', reply.message)
        self.assertEqual(b'MAIL', reply.command)

    def test_rcptto(self):
        self.sock.sendall(b'RCPT TO:<test>\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250 2.0.0 Ok\r\n')
        self.mox.ReplayAll()
        client = Client(self.sock)
        reply = client.rcptto('test')
        self.assertEqual('250', reply.code)
        self.assertEqual('2.0.0 Ok', reply.message)
        self.assertEqual(b'RCPT', reply.command)

    def test_rcptto_pipelining(self):
        self.sock.sendall(b'RCPT TO:<test>\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250 2.0.0 Ok\r\n')
        self.mox.ReplayAll()
        client = Client(self.sock)
        client.extensions.add('PIPELINING')
        reply = client.rcptto('test')
        self.assertEqual(None, reply.code)
        self.assertEqual(None, reply.message)
        self.assertEqual(b'RCPT', reply.command)
        client._flush_pipeline()
        self.assertEqual('250', reply.code)
        self.assertEqual('2.0.0 Ok', reply.message)

    def test_data(self):
        self.sock.sendall(b'DATA\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'354 Go ahead\r\n')
        self.mox.ReplayAll()
        client = Client(self.sock)
        reply = client.data()
        self.assertEqual('354', reply.code)
        self.assertEqual('Go ahead', reply.message)
        self.assertEqual(b'DATA', reply.command)

    def test_send_empty_data(self):
        self.sock.sendall(b'.\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250 2.0.0 Done\r\n')
        self.mox.ReplayAll()
        client = Client(self.sock)
        reply = client.send_empty_data()
        self.assertEqual('250', reply.code)
        self.assertEqual('2.0.0 Done', reply.message)
        self.assertEqual(b'[SEND_DATA]', reply.command)

    def test_send_data(self):
        self.sock.sendall(b'One\r\nTwo\r\n..Three\r\n.\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250 2.0.0 Done\r\n')
        self.mox.ReplayAll()
        client = Client(self.sock)
        reply = client.send_data(b'One\r\nTwo\r\n.Three')
        self.assertEqual('250', reply.code)
        self.assertEqual('2.0.0 Done', reply.message)
        self.assertEqual(b'[SEND_DATA]', reply.command)

    def test_rset(self):
        self.sock.sendall(b'RSET\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250 Ok\r\n')
        self.mox.ReplayAll()
        client = Client(self.sock)
        reply = client.rset()
        self.assertEqual('250', reply.code)
        self.assertEqual('2.0.0 Ok', reply.message)
        self.assertEqual(b'RSET', reply.command)

    def test_quit(self):
        self.sock.sendall(b'QUIT\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'221 Bye\r\n')
        self.mox.ReplayAll()
        client = Client(self.sock)
        reply = client.quit()
        self.assertEqual('221', reply.code)
        self.assertEqual('2.0.0 Bye', reply.message)
        self.assertEqual(b'QUIT', reply.command)


class TestLmtpClient(unittest.TestCase, MoxTestBase):

    def setUp(self):
        super(TestLmtpClient, self).setUp()
        self.sock = self.mox.CreateMock(socket)
        self.sock.fileno = lambda: -1
        self.sock.getpeername = lambda: ('test', 0)
        self.tls_args = {'test': 'test'}

    def test_ehlo_invalid(self):
        client = LmtpClient(self.sock)
        self.assertRaises(NotImplementedError, client.ehlo, 'there')

    def test_helo_invalid(self):
        client = LmtpClient(self.sock)
        self.assertRaises(NotImplementedError, client.helo, 'there')

    def test_lhlo(self):
        self.sock.sendall(b'LHLO there\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250-Hello there\r\n250-TEST arg\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250 EXTEN\r\n')
        self.mox.ReplayAll()
        client = LmtpClient(self.sock)
        reply = client.lhlo('there')
        self.assertEqual('250', reply.code)
        self.assertEqual('Hello there', reply.message)
        self.assertEqual(b'LHLO', reply.command)
        self.assertTrue('TEST' in client.extensions)
        self.assertTrue('EXTEN' in client.extensions)
        self.assertEqual('arg', client.extensions.getparam('TEST'))

    def test_rcptto(self):
        self.sock.sendall(b'RCPT TO:<test>\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250 2.0.0 Ok\r\n')
        self.mox.ReplayAll()
        client = LmtpClient(self.sock)
        reply = client.rcptto('test')
        self.assertEqual('250', reply.code)
        self.assertEqual('2.0.0 Ok', reply.message)
        self.assertEqual(b'RCPT', reply.command)
        self.assertEqual([('test', reply)], client.rcpttos)

    def test_rset(self):
        self.sock.sendall(b'RSET\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250 Ok\r\n')
        self.mox.ReplayAll()
        client = LmtpClient(self.sock)
        client.rcpttos = 'testing'
        reply = client.rset()
        self.assertEqual('250', reply.code)
        self.assertEqual('2.0.0 Ok', reply.message)
        self.assertEqual(b'RSET', reply.command)
        self.assertEqual([], client.rcpttos)

    def test_send_data(self):
        self.sock.sendall(b'One\r\nTwo\r\n..Three\r\n.\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250 2.0.0 Ok\r\n'
                                           b'550 5.0.0 Not Ok\r\n')
        self.mox.ReplayAll()
        client = LmtpClient(self.sock)
        client.rcpttos = [('test1', Reply('250')),
                          ('test2', Reply('250')),
                          ('test3', Reply('550'))]
        replies = client.send_data(b'One\r\nTwo\r\n.Three')
        self.assertEqual(2, len(replies))
        self.assertEqual('test1', replies[0][0])
        self.assertEqual('250', replies[0][1].code)
        self.assertEqual('2.0.0 Ok', replies[0][1].message)
        self.assertEqual(b'[SEND_DATA]', replies[0][1].command)
        self.assertEqual('test2', replies[1][0])
        self.assertEqual('550', replies[1][1].code)
        self.assertEqual('5.0.0 Not Ok', replies[1][1].message)
        self.assertEqual(b'[SEND_DATA]', replies[1][1].command)

    def test_send_empty_data(self):
        self.sock.sendall(b'.\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'250 2.0.0 Ok\r\n'
                                           b'550 5.0.0 Not Ok\r\n')
        self.mox.ReplayAll()
        client = LmtpClient(self.sock)
        client.rcpttos = [('test1', Reply('250')),
                          ('test2', Reply('250')),
                          ('test3', Reply('550'))]
        replies = client.send_empty_data()
        self.assertEqual(2, len(replies))
        self.assertEqual('test1', replies[0][0])
        self.assertEqual('250', replies[0][1].code)
        self.assertEqual('2.0.0 Ok', replies[0][1].message)
        self.assertEqual(b'[SEND_DATA]', replies[0][1].command)
        self.assertEqual('test2', replies[1][0])
        self.assertEqual('550', replies[1][1].code)
        self.assertEqual('5.0.0 Not Ok', replies[1][1].message)
        self.assertEqual(b'[SEND_DATA]', replies[1][1].command)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
