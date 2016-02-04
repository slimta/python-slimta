import unittest2 as unittest

import sys
from email.message import Message
from email.encoders import encode_base64
from email.header import Header

from slimta.envelope import Envelope


class TestEnvelope(unittest.TestCase):

    def test_copy(self):
        env1 = Envelope('sender@example.com', ['rcpt1@example.com'])
        env1.parse(b"""\
From: sender@example.com
To: rcpt1@example.com

test test
""".replace(b'\n', b'\r\n'))
        env2 = env1.copy(env1.recipients + ['rcpt2@example.com'])
        env2.headers.replace_header('To', 'rcpt1@example.com, rcpt2@example.com')
        self.assertEqual('sender@example.com', env1.sender)
        self.assertEqual(['rcpt1@example.com'], env1.recipients)
        self.assertEqual(['rcpt1@example.com'], env1.headers.get_all('To'))
        self.assertEqual('sender@example.com', env2.sender)
        self.assertEqual(['rcpt1@example.com', 'rcpt2@example.com'], env2.recipients)
        self.assertEqual(['rcpt1@example.com, rcpt2@example.com'], env2.headers.get_all('To'))

    def test_repr(self):
        env = Envelope('sender@example.com')
        s = repr(env)
        self.assertRegexpMatches(s, r"<Envelope at 0x[a-fA-F0-9]+, sender=b?'sender@example.com'>")

    def test_flatten(self):
        header_str = b"""\
From: sender@example.com
To: rcpt1@example.com
To: rcpt2@example.com

""".replace(b'\n', b'\r\n')
        body_str = b'test test\r\n'
        env = Envelope()
        env.parse(header_str + body_str)
        ret_headers, ret_body = env.flatten()
        self.assertEqual(header_str, ret_headers)
        self.assertEqual(body_str, ret_body)

    def test_encode_7bit(self):
        headers = Message()
        headers['From'] = 'sender@example.com'
        headers['To'] = 'rcpt@example.com'
        body = bytes(bytearray(range(129, 256)))
        env = Envelope(headers=headers, message=body)
        with self.assertRaises(UnicodeError):
            env.encode_7bit()

    def test_encode_7bit_encoding(self):
        headers = Message()
        headers['From'] = 'sender@example.com'
        headers['To'] = 'rcpt@example.com'
        body = bytes(bytearray(range(129, 256)))
        env = Envelope(headers=headers, message=body)
        header_str = b"""\
From: sender@example.com
To: rcpt@example.com
Content-Transfer-Encoding: base64

""".replace(b'\n', b'\r\n')
        body_str = b'gYKDhIWGh4iJiouMjY6PkJGSk5SVlpeYmZqbnJ2en6ChoqOkpaanqKmqq6ytrq+wsbKztLW2t7i5\r\nuru8vb6/wMHCw8TFxsfIycrLzM3Oz9DR0tPU1dbX2Nna29zd3t/g4eLj5OXm5+jp6uvs7e7v8PHy\r\n8/T19vf4+fr7/P3+/w=='
        env.encode_7bit(encoder=encode_base64)
        ret_headers, ret_body = env.flatten()
        self.assertEqual(header_str, ret_headers)
        self.assertEqual(body_str, ret_body.rstrip())

    def test_parse(self):
        env = Envelope()
        env.parse(b"""\
From: sender@example.com
To: rcpt1@example.com
To: rcpt2@example.com

test test
""".replace(b'\n', b'\r\n'))
        self.assertEqual('sender@example.com', env.headers['from'])
        self.assertEqual(['rcpt1@example.com', 'rcpt2@example.com'],
                         env.headers.get_all('To'))
        self.assertEqual(b'test test\r\n', env.message)

    def test_parse_onlyheaders(self):
        env = Envelope()
        env.parse(b"""\
From: sender@example.com
Subject: important things
""".replace(b'\n', b'\r\n'))
        self.assertEqual('sender@example.com', env.headers['from'])
        self.assertEqual('important things', env.headers['subject'])
        self.assertEqual(b'', env.message)

    @unittest.skipIf(sys.version_info[0:2] == (3, 3), 'Broken on Python 3.3')
    def test_parse_nonascii_headers(self):
        env = Envelope()
        env.parse(b'Subject: \xc3\xa9\xc3\xa9\n')
        try:
            self.assertEqual(b'\xc3\xa9\xc3\xa9', env.headers['subject'].encode())
        except UnicodeDecodeError:
            self.assertEqual(b'\xc3\xa9\xc3\xa9', env.headers['subject'])

    def test_parse_onlybody(self):
        env = Envelope()
        env.parse(b"""\
important things
""".replace(b'\n', b'\r\n'))
        self.assertEqual(b'important things\r\n', env.message)

    def test_parse_message_object(self):
        msg = Message()
        msg['From'] = 'sender@example.com'
        msg['To'] = 'rcpt1@example.com'
        msg['To'] = 'rcpt2@example.com'
        msg.set_payload(b'test test\r\n')
        env = Envelope()
        env.parse_msg(msg)
        self.assertEqual('sender@example.com', env.headers['from'])
        self.assertEqual(['rcpt1@example.com', 'rcpt2@example.com'], env.headers.get_all('to'))
        self.assertEqual(b'test test\r\n', env.message)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
