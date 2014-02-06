
from assertions import *

from mox import MoxTestBase, IsA
from gevent.socket import socket

from slimta.smtp.io import IO
from slimta.smtp import BadReply, ConnectionLost
from slimta.smtp.reply import Reply


class TestSmtpIO(MoxTestBase):

    def setUp(self):
        super(TestSmtpIO, self).setUp()
        self.sock = self.mox.CreateMock(socket)
        self.sock.fileno = lambda: -1

    def test_buffered_recv(self):
        self.sock.recv(IsA(int)).AndReturn('some data')
        self.mox.ReplayAll()
        io = IO(self.sock)
        io.buffered_recv()
        assert_equal('some data', io.recv_buffer)

    def test_buffered_recv_connectionlost(self):
        self.sock.recv(IsA(int)).AndReturn('')
        self.mox.ReplayAll()
        io = IO(self.sock)
        assert_raises(ConnectionLost, io.buffered_recv)

    def test_buffered_send(self):
        self.mox.ReplayAll()
        io = IO(self.sock)
        io.buffered_send('some data')
        assert_equal('some data', io.send_buffer.getvalue())

    def test_flush_send(self):
        self.sock.sendall('some data')
        self.mox.ReplayAll()
        io = IO(self.sock)
        io.buffered_send('some data')
        io.flush_send()

    def test_flush_send_empty(self):
        self.mox.ReplayAll()
        io = IO(self.sock)
        io.flush_send()

    def test_recv_reply(self):
        self.sock.recv(IsA(int)).AndReturn('250 Ok\r\n')
        self.mox.ReplayAll()
        io = IO(self.sock)
        code, message = io.recv_reply()
        assert_equal('250', code)
        assert_equal('Ok', message)

    def test_recv_reply_multipart(self):
        self.sock.recv(IsA(int)).AndReturn('250 ')
        self.sock.recv(IsA(int)).AndReturn('Ok\r\n')
        self.mox.ReplayAll()
        io = IO(self.sock)
        code, message = io.recv_reply()
        assert_equal('250', code)
        assert_equal('Ok', message)

    def test_recv_reply_multiline(self):
        self.sock.recv(IsA(int)).AndReturn('250-One\r\n250 Two\r\n')
        self.mox.ReplayAll()
        io = IO(self.sock)
        code, message = io.recv_reply()
        assert_equal('250', code)
        assert_equal('One\r\nTwo', message)

    def test_recv_reply_bad_code(self):
        self.sock.recv(IsA(int)).AndReturn('bad\r\n')
        self.mox.ReplayAll()
        io = IO(self.sock)
        assert_raises(BadReply, io.recv_reply)

    def test_recv_reply_bad_multiline(self):
        self.sock.recv(IsA(int)).AndReturn('250-One\r\n500 Two\r\n')
        self.mox.ReplayAll()
        io = IO(self.sock)
        assert_raises(BadReply, io.recv_reply)

    def test_recv_line(self):
        self.sock.recv(IsA(int)).AndReturn('one')
        self.sock.recv(IsA(int)).AndReturn('\r\ntwo')
        self.mox.ReplayAll()
        io = IO(self.sock)
        line = io.recv_line()
        assert_equal('one', line)
        assert_equal('two', io.recv_buffer)

    def test_recv_command(self):
        self.sock.recv(IsA(int)).AndReturn('CMD\r\n')
        self.mox.ReplayAll()
        io = IO(self.sock)
        command, arg = io.recv_command()
        assert_equal('CMD', command)
        assert_equal(None, arg)

    def test_recv_command_arg(self):
        self.sock.recv(IsA(int)).AndReturn('cmd arg \r\n')
        self.mox.ReplayAll()
        io = IO(self.sock)
        command, arg = io.recv_command()
        assert_equal('CMD', command)
        assert_equal('arg', arg)

    def test_recv_command_bad(self):
        self.sock.recv(IsA(int)).AndReturn('cmd123r\n')
        self.mox.ReplayAll()
        io = IO(self.sock)
        command, arg = io.recv_command()
        assert_equal(None, command)
        assert_equal(None, arg)

    def test_send_reply(self):
        self.mox.ReplayAll()
        io = IO(self.sock)
        io.send_reply(Reply('100', 'Ok'))
        assert_equal('100 Ok\r\n', io.send_buffer.getvalue())

    def test_send_reply_multiline(self):
        self.mox.ReplayAll()
        io = IO(self.sock)
        io.send_reply(Reply('100', 'One\r\nTwo'))
        assert_equal('100-One\r\n100 Two\r\n', io.send_buffer.getvalue())

    def test_send_command(self):
        self.mox.ReplayAll()
        io = IO(self.sock)
        io.send_command('CMD')
        assert_equal('CMD\r\n', io.send_buffer.getvalue())


# vim:et:fdm=marker:sts=4:sw=4:ts=4
