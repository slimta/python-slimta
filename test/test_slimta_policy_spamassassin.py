
import unittest2 as unittest

from mox3.mox import MoxTestBase
from gevent.socket import socket, SHUT_WR

from slimta.policy.spamassassin import SpamAssassin, SpamAssassinError
from slimta.envelope import Envelope


class TestSpamAssassin(unittest.TestCase, MoxTestBase):

    def setUp(self):
        super(TestSpamAssassin, self).setUp()
        self.sock = self.mox.CreateMock(socket)
        self.sock.fileno = lambda: -1
        self.sa = SpamAssassin(socket_creator=lambda _: self.sock)

    def test_send_request(self):
        self.sock.sendall(b"""\
SYMBOLS SPAMC/1.1
Content-Length: 23
User: slimta

testheaders
testbody
""".replace(b'\n', b'\r\n'))
        self.sock.shutdown(SHUT_WR)
        self.mox.ReplayAll()
        self.sa._send_request(self.sock, b'testheaders\r\n', b'testbody\r\n')

    def test_recv_response(self):
        self.sock.recv(4096).AndReturn(b"""\
SPAMD/1.1 0 EX_OK
Header-One: stuff
Spam: True with some info
Header-Two: other stuff

symbol:one, symbol$two, symbol_three
""")
        self.sock.recv(4096).AndReturn(b'')
        self.mox.ReplayAll()
        spammy, symbols = self.sa._recv_response(self.sock)
        self.assertTrue(spammy)
        self.assertEqual(['symbol:one', 'symbol$two', 'symbol_three'], symbols)

    def test_recv_response_bad_data(self):
        self.sock.recv(4096).AndReturn(b'')
        self.mox.ReplayAll()
        with self.assertRaises(SpamAssassinError):
            self.sa._recv_response(self.sock)

    def test_recv_response_bad_first_line(self):
        self.sock.recv(4096).AndReturn(b"""\
SPAMD/1.1 0 EX_NOT_OK

""")
        self.sock.recv(4096).AndReturn(b'')
        self.mox.ReplayAll()
        with self.assertRaises(SpamAssassinError):
            self.sa._recv_response(self.sock)

    def test_scan(self):
        self.mox.StubOutWithMock(self.sa, '_send_request')
        self.mox.StubOutWithMock(self.sa, '_recv_response')
        self.sa._send_request(self.sock, b'', b'my message data')
        self.sa._recv_response(self.sock).AndReturn((False, []))
        self.sock.close()
        self.mox.ReplayAll()
        self.assertEqual((False, []), self.sa.scan(b'my message data'))

    def test_apply(self):
        env = Envelope()
        env.parse(b"""X-Spam-Status: NO\r\n\r\n""")
        self.mox.StubOutWithMock(self.sa, 'scan')
        self.sa.scan(env).AndReturn((True, ['one', 'two']))
        self.mox.ReplayAll()
        self.sa.apply(env)
        self.assertEqual('YES', env.headers['X-Spam-Status'])
        self.assertEqual('one, two', env.headers['X-Spam-Symbols'])


# vim:et:fdm=marker:sts=4:sw=4:ts=4
