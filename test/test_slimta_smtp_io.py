
import unittest

from slimta.smtp.io import IO
from slimta.smtp import BadReply, ConnectionLost
from slimta.smtp.reply import Reply

from mock.socket import MockSocket


class TestSmtpIO(unittest.TestCase):

    def test_buffered_recv(self):
        sock = MockSocket([('recv', 'some data')])
        io = IO(sock)
        io.buffered_recv()
        self.assertEqual('some data', io.recv_buffer)
        sock.assert_done(self)

    def test_buffered_recv_connectionlost(self):
        sock = MockSocket([('recv', '')])
        io = IO(sock)
        self.assertRaises(ConnectionLost, io.buffered_recv)
        sock.assert_done(self)

    def test_buffered_send(self):
        sock = MockSocket([])
        io = IO(sock)
        io.buffered_send('some data')
        self.assertEqual('some data', io.send_buffer.getvalue())
        sock.assert_done(self)

    def test_flush_send(self):
        sock = MockSocket([('send', 'some data')])
        io = IO(sock)
        io.buffered_send('some data')
        io.flush_send()
        sock.assert_done(self)

    def test_flush_send_empty(self):
        sock = MockSocket([])
        io = IO(sock)
        io.flush_send()
        sock.assert_done(self)

    def test_recv_reply(self):
        sock = MockSocket([('recv', '250 Ok\r\n')])
        io = IO(sock)
        code, message = io.recv_reply()
        self.assertEqual('250', code)
        self.assertEqual('Ok', message)
        sock.assert_done(self)

    def test_recv_reply_multipart(self):
        sock = MockSocket([('recv', '250 '), ('recv', 'Ok\r\n')])
        io = IO(sock)
        code, message = io.recv_reply()
        self.assertEqual('250', code)
        self.assertEqual('Ok', message)
        sock.assert_done(self)

    def test_recv_reply_multiline(self):
        sock = MockSocket([('recv', '250-One\r\n250 Two\r\n')])
        io = IO(sock)
        code, message = io.recv_reply()
        self.assertEqual('250', code)
        self.assertEqual('One\r\nTwo', message)
        sock.assert_done(self)

    def test_recv_reply_bad_code(self):
        sock = MockSocket([('recv', 'bad\r\n')])
        io = IO(sock)
        self.assertRaises(BadReply, io.recv_reply)
        sock.assert_done(self)

    def test_recv_reply_bad_multiline(self):
        sock = MockSocket([('recv', '250-One\r\n500 Two\r\n')])
        io = IO(sock)
        self.assertRaises(BadReply, io.recv_reply)
        sock.assert_done(self)

    def test_recv_line(self):
        sock = MockSocket([('recv', 'one'), ('recv', '\r\ntwo')])
        io = IO(sock)
        line = io.recv_line()
        self.assertEqual('one', line)
        self.assertEqual('two', io.recv_buffer)
        sock.assert_done(self)

    def test_recv_command(self):
        sock = MockSocket([('recv', 'CMD\r\n')])
        io = IO(sock)
        command, arg = io.recv_command()
        self.assertEqual('CMD', command)
        self.assertEqual(None, arg)
        sock.assert_done(self)

    def test_recv_command_arg(self):
        sock = MockSocket([('recv', 'cmd arg \r\n')])
        io = IO(sock)
        command, arg = io.recv_command()
        self.assertEqual('CMD', command)
        self.assertEqual('arg', arg)
        sock.assert_done(self)

    def test_recv_command_bad(self):
        sock = MockSocket([('recv', 'cmd123\r\n')])
        io = IO(sock)
        command, arg = io.recv_command()
        self.assertEqual(None, command)
        self.assertEqual(None, arg)
        sock.assert_done(self)

    def test_send_reply(self):
        io = IO(MockSocket([]))
        io.send_reply(Reply('100', 'Ok'))
        self.assertEqual('100 Ok\r\n', io.send_buffer.getvalue())

    def test_send_reply_multiline(self):
        io = IO(MockSocket([]))
        io.send_reply(Reply('100', 'One\r\nTwo'))
        self.assertEqual('100-One\r\n100 Two\r\n', io.send_buffer.getvalue())

    def test_send_command(self):
        io = IO(MockSocket([]))
        io.send_command('CMD')
        self.assertEqual('CMD\r\n', io.send_buffer.getvalue())


# vim:et:fdm=marker:sts=4:sw=4:ts=4
