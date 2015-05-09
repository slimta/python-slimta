
import unittest2 as unittest

from slimta.smtp.datasender import DataSender


class TestSmtpDataSender(unittest.TestCase):

    def test_empty_data(self):
        ret = ''.join(DataSender(''))
        self.assertEqual('.\r\n', ret)

    def test_newline(self):
        ret = ''.join(DataSender('\r\n'))
        self.assertEqual('\r\n.\r\n', ret)

    def test_one_line(self):
        ret = ''.join(DataSender('one'))
        self.assertEqual('one\r\n.\r\n', ret)

    def test_multi_line(self):
        ret = ''.join(DataSender('one\r\ntwo'))
        self.assertEqual('one\r\ntwo\r\n.\r\n', ret)

    def test_eod(self):
        ret = ''.join(DataSender('.\r\n'))
        self.assertEqual('..\r\n.\r\n', ret)

    def test_period_escape(self):
        ret = ''.join(DataSender('.one\r\n..two\r\n'))
        self.assertEqual('..one\r\n...two\r\n.\r\n', ret)

# vim:et:fdm=marker:sts=4:sw=4:ts=4
