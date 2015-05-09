
import unittest2 as unittest
from mox import MoxTestBase, IsA
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
        dr._append_line('asdf')
        dr._append_line('jkl\r\n')
        dr.i += 1
        dr._append_line('qwerty')
        self.assertEqual(['asdfjkl\r\n', 'qwerty'], dr.lines)

    def test_from_recv_buffer(self):
        io = IO(None)
        io.recv_buffer = 'test\r\ndata'
        dr = DataReader(io)
        dr.from_recv_buffer()
        self.assertEqual(['test\r\n', 'data'], dr.lines)

    def test_handle_finished_line_EOD(self):
        dr = DataReader(None)
        dr.lines = ['.\r\n']
        dr.handle_finished_line()
        self.assertEqual(0, dr.EOD)

    def test_handle_finished_line_initial_period(self):
        dr = DataReader(None)
        dr.lines = ['..stuff\r\n']
        dr.handle_finished_line()
        self.assertEqual('.stuff\r\n', dr.lines[0])

    def test_add_lines(self):
        dr = DataReader(None)
        dr.add_lines('\r\ntwo\r\n.three\r\nfour')
        self.assertEqual(['\r\n', 'two\r\n', 'three\r\n', 'four'], dr.lines)
        self.assertEqual(3, dr.i)
        self.assertEqual(None, dr.EOD)

    def test_recv_piece(self):
        self.sock.recv(IsA(int)).AndReturn('one\r\ntwo')
        self.sock.recv(IsA(int)).AndReturn('\r\nthree\r\n.\r\nstuff\r\n')
        self.mox.ReplayAll()
        dr = DataReader(IO(self.sock))
        self.assertTrue(dr.recv_piece())
        self.assertFalse(dr.recv_piece())
        self.assertEqual(['one\r\n', 'two\r\n', 'three\r\n',
                          '.\r\n', 'stuff\r\n', ''], dr.lines)
        self.assertEqual(3, dr.EOD)
        self.assertEqual(5, dr.i)

    def test_recv_piece_already_eod(self):
        dr = DataReader(None)
        dr.EOD = 2
        self.assertFalse(dr.recv_piece())

    def test_recv_piece_connectionlost(self):
        self.sock.recv(IsA(int)).AndReturn('')
        self.mox.ReplayAll()
        dr = DataReader(IO(self.sock))
        self.assertRaises(ConnectionLost, dr.recv_piece)

    def test_recv_piece_messagetoobig(self):
        self.sock.recv(IsA(int)).AndReturn('1234567890')
        self.mox.ReplayAll()
        dr = DataReader(IO(self.sock), 9)
        self.assertRaises(MessageTooBig, dr.recv_piece)

    def test_return_all(self):
        io = IO(None)
        dr = DataReader(io)
        dr.lines = ['one\r\n', 'two\r\n', '.\r\n', 'three\r\n']
        dr.EOD = 2
        self.assertEqual('one\r\ntwo\r\n', dr.return_all())
        self.assertEqual('three\r\n', io.recv_buffer)

    def test_recv(self):
        self.sock.recv(IsA(int)).AndReturn('\r\nthree\r\n')
        self.sock.recv(IsA(int)).AndReturn('.\r\nstuff\r\n')
        self.mox.ReplayAll()
        io = IO(self.sock)
        io.recv_buffer = 'one\r\ntwo'
        dr = DataReader(io)
        self.assertEqual('one\r\ntwo\r\nthree\r\n', dr.recv())


# vim:et:fdm=marker:sts=4:sw=4:ts=4
