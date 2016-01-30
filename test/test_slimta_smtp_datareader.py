import unittest2 as unittest
from mox3.mox import MoxTestBase, IsA
from gevent.socket import socket

from slimta.smtp.datareader import DataReader
from slimta.smtp.io import IO
from slimta.smtp import ConnectionLost, MessageTooBig


class TestSmtpDataReader(unittest.TestCase, MoxTestBase):

    def setUp(self):
        super(TestSmtpDataReader, self).setUp()
        self.sock = self.mox.CreateMock(socket)
        self.sock.fileno = lambda: -1

    def test_append_line(self):
        dr = DataReader(None)
        dr._append_line(b'asdf')
        dr._append_line(b'jkl\r\n')
        dr.i += 1
        dr._append_line(b'qwerty')
        self.assertEqual([b'asdfjkl\r\n', b'qwerty'], dr.lines)

    def test_from_recv_buffer(self):
        io = IO(None)
        io.recv_buffer = b'test\r\ndata'
        dr = DataReader(io)
        dr.from_recv_buffer()
        self.assertEqual([b'test\r\n', b'data'], dr.lines)

    def test_handle_finished_line_EOD(self):
        dr = DataReader(None)
        dr.lines = [b'.\r\n']
        dr.handle_finished_line()
        self.assertEqual(0, dr.EOD)

    def test_handle_finished_line_initial_period(self):
        dr = DataReader(None)
        dr.lines = [b'..stuff\r\n']
        dr.handle_finished_line()
        self.assertEqual(b'.stuff\r\n', dr.lines[0])

    def test_add_lines(self):
        dr = DataReader(None)
        dr.add_lines(b'\r\ntwo\r\n.three\r\nfour')
        self.assertEqual([b'\r\n', b'two\r\n', b'three\r\n', b'four'], dr.lines)
        self.assertEqual(3, dr.i)
        self.assertEqual(None, dr.EOD)

    def test_recv_piece(self):
        self.sock.recv(IsA(int)).AndReturn(b'one\r\ntwo')
        self.sock.recv(IsA(int)).AndReturn(b'\r\nthree\r\n.\r\nstuff\r\n')
        self.mox.ReplayAll()
        dr = DataReader(IO(self.sock))
        self.assertTrue(dr.recv_piece())
        self.assertFalse(dr.recv_piece())
        self.assertEqual([b'one\r\n', b'two\r\n', b'three\r\n',
                          b'.\r\n', b'stuff\r\n', b''], dr.lines)
        self.assertEqual(3, dr.EOD)
        self.assertEqual(5, dr.i)

    def test_recv_piece_already_eod(self):
        dr = DataReader(None)
        dr.EOD = 2
        self.assertFalse(dr.recv_piece())

    def test_recv_piece_connectionlost(self):
        self.sock.recv(IsA(int)).AndReturn(b'')
        self.mox.ReplayAll()
        dr = DataReader(IO(self.sock))
        self.assertRaises(ConnectionLost, dr.recv_piece)

    def test_recv_piece_messagetoobig(self):
        self.sock.recv(IsA(int)).AndReturn(b'1234567890')
        self.mox.ReplayAll()
        dr = DataReader(IO(self.sock), 9)
        self.assertRaises(MessageTooBig, dr.recv_piece)

    def test_return_all(self):
        io = IO(None)
        dr = DataReader(io)
        dr.lines = [b'one\r\n', b'two\r\n', b'.\r\n', b'three\r\n']
        dr.EOD = 2
        self.assertEqual(b'one\r\ntwo\r\n', dr.return_all())
        self.assertEqual(b'three\r\n', io.recv_buffer)

    def test_recv(self):
        self.sock.recv(IsA(int)).AndReturn(b'\r\nthree\r\n')
        self.sock.recv(IsA(int)).AndReturn(b'.\r\nstuff\r\n')
        self.mox.ReplayAll()
        io = IO(self.sock)
        io.recv_buffer = b'one\r\ntwo'
        dr = DataReader(io)
        self.assertEqual(b'one\r\ntwo\r\nthree\r\n', dr.recv())


# vim:et:fdm=marker:sts=4:sw=4:ts=4
