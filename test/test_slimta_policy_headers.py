import unittest2 as unittest

from slimta.policy.headers import AddDateHeader, AddMessageIdHeader, \
                                  AddReceivedHeader
from slimta.envelope import Envelope


class TestPolicyHeaders(unittest.TestCase):

    def test_add_date_header(self):
        env = Envelope()
        env.parse(b'')
        env.timestamp = 1234567890
        adh = AddDateHeader()
        self.assertEqual(None, env.headers['Date'])
        adh.apply(env)
        self.assertTrue(env.headers['Date'])

    def test_add_date_header_existing(self):
        env = Envelope()
        epoch = 'Thu, 01 Jan 1970 00:00:00 -0000'
        env.parse(b'Date: '+epoch.encode()+b'\r\n')
        adh = AddDateHeader()
        self.assertEqual(epoch, env.headers['Date'])
        adh.apply(env)
        self.assertEqual(epoch, env.headers['Date'])

    def test_add_message_id_header(self):
        env = Envelope()
        env.parse(b'')
        env.timestamp = 1234567890
        amih = AddMessageIdHeader('example.com')
        self.assertEqual(None, env.headers['Message-Id'])
        amih.apply(env)
        pattern = r'^<[0-9a-fA-F]{32}\.1234567890@example.com>$'
        self.assertRegexpMatches(env.headers['Message-Id'], pattern)

    def test_add_message_id_header_existing(self):
        env = Envelope()
        env.parse(b'Message-Id: testing\r\n')
        amih = AddMessageIdHeader()
        self.assertEqual('testing', env.headers['Message-Id'])
        amih.apply(env)
        self.assertEqual('testing', env.headers['Message-Id'])

    def test_add_received_header(self):
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse(b'From: test@example.com\r\n')
        env.timestamp = 1234567890
        env.client['name'] = 'mail.example.com'
        env.client['ip'] = '1.2.3.4'
        env.client['protocol'] = 'ESMTPS'
        env.receiver = 'test.com'
        arh = AddReceivedHeader()
        arh.apply(env)
        self.assertRegexpMatches(env.headers['Received'],
                r'from mail\.example\.com \(unknown \[1.2.3.4\]\) by test.com '
                r'\(slimta [^\)]+\) with ESMTPS for <rcpt@example.com>; ')

    def test_add_received_header_prepended(self):
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse(b'From: test@example.com\r\n')
        AddReceivedHeader().apply(env)
        self.assertEqual(['Received', 'From'], env.headers.keys())


# vim:et:fdm=marker:sts=4:sw=4:ts=4
