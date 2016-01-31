
import unittest2 as unittest

from slimta.smtp.datasender import DataSender


class TestSmtpDataSender(unittest.TestCase):

    def test_empty_data(self):
        ret = b''.join(DataSender(b''))
        self.assertEqual(b'.\r\n', ret)

    def test_newline(self):
        ret = b''.join(DataSender(b'\r\n'))
        self.assertEqual(b'\r\n.\r\n', ret)

    def test_one_line(self):
        ret = b''.join(DataSender(b'one'))
        self.assertEqual(b'one\r\n.\r\n', ret)

    def test_multi_line(self):
        ret = b''.join(DataSender(b'one\r\ntwo'))
        self.assertEqual(b'one\r\ntwo\r\n.\r\n', ret)

    def test_eod(self):
        ret = b''.join(DataSender(b'.\r\n'))
        self.assertEqual(b'..\r\n.\r\n', ret)

    def test_period_escape(self):
        ret = b''.join(DataSender(b'.one\r\n..two\r\n'))
        self.assertEqual(b'..one\r\n...two\r\n.\r\n', ret)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
