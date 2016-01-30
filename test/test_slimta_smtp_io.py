import unittest2 as unittest
from mox3.mox import MoxTestBase, IsA
from gevent.socket import socket

from slimta.smtp.io import IO
from slimta.smtp import BadReply, ConnectionLost
from slimta.smtp.reply import Reply


class TestSmtpIO(unittest.TestCase, MoxTestBase):

    def setUp(self):
        super(TestSmtpIO, self).setUp()
        self.sock = self.mox.CreateMock(socket)
        self.sock.fileno = lambda: -1

    def test_buffered_recv(self):
        self.sock.recv(IsA(int)).AndReturn(b'some data')
        self.mox.ReplayAll()
        io = IO(self.sock)
        io.buffered_recv()
        self.assertEqual(b'some data', io.recv_buffer)

    def test_buffered_recv_connectionlost(self):
        self.sock.recv(IsA(int)).AndReturn(b'')
        self.mox.ReplayAll()
        io = IO(self.sock)
        self.assertRaises(ConnectionLost, io.buffered_recv)

    def test_buffered_send(self):
        self.mox.ReplayAll()
        io = IO(self.sock)
        io.buffered_send(b'some data')
        self.assertEqual(b'some data', io.send_buffer.getvalue())

    def test_flush_send(self):
        self.sock.sendall(b'some data')
        self.mox.ReplayAll()
        io = IO(self.sock)
        io.buffered_send(b'some data')
        io.flush_send()

    def test_flush_send_empty(self):
        self.mox.ReplayAll()
        io = IO(self.sock)
        io.flush_send()

    def test_recv_reply(self):
        self.sock.recv(IsA(int)).AndReturn(b'250 Ok\r\n')
        self.mox.ReplayAll()
        io = IO(self.sock)
        code, message = io.recv_reply()
        self.assertEqual('250', code)
        self.assertEqual('Ok', message)

    def test_recv_utf8(self):
        self.sock.recv(IsA(int)).AndReturn(b'250 \xc3\xbf\r\n')
        self.mox.ReplayAll()
        io = IO(self.sock)
        code, message = io.recv_reply()
        self.assertEqual('250', code)
        self.assertEqual(u'\xff', message)

    def test_recv_nonutf8(self):
        self.sock.recv(IsA(int)).AndReturn(b'250 \xff\r\n')
        self.mox.ReplayAll()
        io = IO(self.sock)
        self.assertRaises(BadReply, io.recv_reply)

    def test_recv_reply_multipart(self):
        self.sock.recv(IsA(int)).AndReturn(b'250 ')
        self.sock.recv(IsA(int)).AndReturn(b'Ok\r\n')
        self.mox.ReplayAll()
        io = IO(self.sock)
        code, message = io.recv_reply()
        self.assertEqual('250', code)
        self.assertEqual('Ok', message)

    def test_recv_reply_multiline(self):
        self.sock.recv(IsA(int)).AndReturn(b'250-One\r\n250 Two\r\n')
        self.mox.ReplayAll()
        io = IO(self.sock)
        code, message = io.recv_reply()
        self.assertEqual('250', code)
        self.assertEqual('One\r\nTwo', message)

    def test_recv_reply_bad_code(self):
        self.sock.recv(IsA(int)).AndReturn(b'bad\r\n')
        self.mox.ReplayAll()
        io = IO(self.sock)
        self.assertRaises(BadReply, io.recv_reply)

    def test_recv_reply_bad_multiline(self):
        self.sock.recv(IsA(int)).AndReturn(b'250-One\r\n500 Two\r\n')
        self.mox.ReplayAll()
        io = IO(self.sock)
        self.assertRaises(BadReply, io.recv_reply)

    def test_recv_line(self):
        self.sock.recv(IsA(int)).AndReturn(b'one')
        self.sock.recv(IsA(int)).AndReturn(b'\r\ntwo')
        self.mox.ReplayAll()
        io = IO(self.sock)
        line = io.recv_line()
        self.assertEqual(b'one', line)
        self.assertEqual(b'two', io.recv_buffer)

    def test_recv_command(self):
        self.sock.recv(IsA(int)).AndReturn(b'CMD\r\n')
        self.mox.ReplayAll()
        io = IO(self.sock)
        command, arg = io.recv_command()
        self.assertEqual(b'CMD', command)
        self.assertEqual(None, arg)

    def test_recv_command_arg(self):
        self.sock.recv(IsA(int)).AndReturn(b'cmd arg \r\n')
        self.mox.ReplayAll()
        io = IO(self.sock)
        command, arg = io.recv_command()
        self.assertEqual(b'CMD', command)
        self.assertEqual(b'arg', arg)

    def test_recv_command_bad(self):
        self.sock.recv(IsA(int)).AndReturn(b'cmd123r\n')
        self.mox.ReplayAll()
        io = IO(self.sock)
        command, arg = io.recv_command()
        self.assertEqual(None, command)
        self.assertEqual(None, arg)

    def test_recv_command_nonutf8(self):
        self.sock.recv(IsA(int)).AndReturn(b'cmd\xffr\n')
        self.mox.ReplayAll()
        io = IO(self.sock)
        command, arg = io.recv_command()
        self.assertEqual(None, command)
        self.assertEqual(None, arg)

    def test_send_reply(self):
        self.mox.ReplayAll()
        io = IO(self.sock)
        io.send_reply(Reply('100', 'Ok'))
        self.assertEqual(b'100 Ok\r\n', io.send_buffer.getvalue())

    def test_send_reply_nonascii(self):
        self.mox.ReplayAll()
        io = IO(self.sock)
        io.send_reply(Reply('100', u'Ok\xff'))
        self.assertEqual(b'100 Ok\xc3\xbf\r\n', io.send_buffer.getvalue())

    def test_send_reply_multiline(self):
        self.mox.ReplayAll()
        io = IO(self.sock)
        io.send_reply(Reply('100', 'One\r\nTwo'))
        self.assertEqual(b'100-One\r\n100 Two\r\n', io.send_buffer.getvalue())

    def test_send_command(self):
        self.mox.ReplayAll()
        io = IO(self.sock)
        io.send_command(b'CMD')
        self.assertEqual(b'CMD\r\n', io.send_buffer.getvalue())

    def test_send_command_nonascii(self):
        self.mox.ReplayAll()
        io = IO(self.sock)
        io.send_command(b'CMD\xff')
        self.assertEqual(b'CMD\xff\r\n', io.send_buffer.getvalue())


# vim:et:fdm=marker:sts=4:sw=4:ts=4
