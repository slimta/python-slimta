
import unittest

from assertions import *

from slimta.smtp.datasender import DataSender


class TestSmtpDataSender(unittest.TestCase):

    def test_empty_data(self):
        ret = ''.join(DataSender(''))
        assert_equal('.\r\n', ret)

    def test_newline(self):
        ret = ''.join(DataSender('\r\n'))
        assert_equal('\r\n.\r\n', ret)

    def test_one_line(self):
        ret = ''.join(DataSender('one'))
        assert_equal('one\r\n.\r\n', ret)

    def test_multi_line(self):
        ret = ''.join(DataSender('one\r\ntwo'))
        assert_equal('one\r\ntwo\r\n.\r\n', ret)

    def test_eod(self):
        ret = ''.join(DataSender('.\r\n'))
        assert_equal('..\r\n.\r\n', ret)

    def test_period_escape(self):
        ret = ''.join(DataSender('.one\r\n..two\r\n'))
        assert_equal('..one\r\n...two\r\n.\r\n', ret)

# vim:et:fdm=marker:sts=4:sw=4:ts=4
