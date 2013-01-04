
import unittest
from email.message import Message

from slimta.envelope import Envelope


class TestEnvelope(unittest.TestCase):

    def test_flatten(self):
        headers = Message()
        headers['From'] = 'sender@example.com'
        headers['To'] = 'rcpt1@example.com'
        headers['To'] = 'rcpt2@example.com'
        body = 'test test\r\n'
        env = Envelope(headers=headers, message=body)
        header_str = '\r\n'.join(['From: sender@example.com',
                                  'To: rcpt1@example.com',
                                  'To: rcpt2@example.com',
                                  '', ''])
        ret_headers, ret_body = env.flatten()
        self.assertEqual(header_str, ret_headers)
        self.assertEqual(body, ret_body)

    def test_parse(self):
        env = Envelope()
        env.parse("""\
From: sender@example.com
To: rcpt1@example.com
To: rcpt2@example.com

test test\r
""")
        self.assertEqual('sender@example.com', env.headers['from'])
        self.assertEqual(['rcpt1@example.com', 'rcpt2@example.com'],
                         env.headers.get_all('To'))
        self.assertEquals('test test\r\n', env.message)

    def test_parse_onlyheaders(self):
        env = Envelope()
        env.parse("""\
From: sender@example.com
Subject: important things
""")
        self.assertEqual('sender@example.com', env.headers['from'])
        self.assertEqual('important things', env.headers['subject'])
        self.assertEqual('', env.message)

    def test_split(self):
        env = Envelope('sender@example.com', ['rcpt1@example.com',
                                              'rcpt2@example.com'])
        env.parse("""\
From: sender@example.com
To: rcpt1@example.com
To: rcpt2@example.com

test test\r
""")
        env1, env2 = env.split()

        self.assertEqual('sender@example.com', env1.sender)
        self.assertEqual(['rcpt1@example.com'], env1.recipients)
        self.assertEqual('sender@example.com', env1.headers['from'])
        self.assertEqual(['rcpt1@example.com', 'rcpt2@example.com'],
                         env1.headers.get_all('To'))
        self.assertEquals('test test\r\n', env1.message)

        self.assertEqual('sender@example.com', env2.sender)
        self.assertEqual(['rcpt2@example.com'], env2.recipients)
        self.assertEqual('sender@example.com', env2.headers['from'])
        self.assertEqual(['rcpt1@example.com', 'rcpt2@example.com'],
                         env2.headers.get_all('To'))
        self.assertEquals('test test\r\n', env2.message)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
