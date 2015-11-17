# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import unittest2 as unittest

from base64 import b64encode
from email.message import Message

import six

from slimta.envelope import Envelope
from slimta.bounce import Bounce
from slimta.smtp.reply import Reply
from slimta.util.encoders import encode_base64



class TestEnvelope(unittest.TestCase):

    def test_copy(self):
        env1 = Envelope('sender@example.com', ['rcpt1@example.com'])
        env1.parse(b"""\
From: sender@example.com\r
To: rcpt1@example.com\r
\r
test test\r
""")
        env2 = env1.copy()
        env2.recipients.append('rcpt2@example.com')
        env2.headers['To'] = 'rcpt2@example.com'
        self.assertEqual('sender@example.com', env1.sender)
        self.assertEqual(['rcpt1@example.com'], env1.recipients)
        self.assertEqual(['rcpt1@example.com'], env1.headers.get_all('To'))
        self.assertEqual('sender@example.com', env2.sender)
        self.assertEqual(['rcpt1@example.com', 'rcpt2@example.com'], env2.recipients)
        self.assertEqual(['rcpt1@example.com', 'rcpt2@example.com'], env2.headers.get_all('To'))

    def test_repr(self):
        env = Envelope('sender@example.com')
        s = repr(env)
        self.assertRegexpMatches(s, r"<Envelope at 0x[a-fA-F0-9]+, sender=u?'sender@example.com'>")

    def test_flatten(self):
        headers = Message()
        headers['From'] = 'sender@example.com'
        headers['To'] = 'rcpt1@example.com'
        headers['To'] = 'rcpt2@example.com'
        body = b'test test\r\n'
        env = Envelope(headers=headers, message=body)
        header_str = '\r\n'.join(['From: sender@example.com',
                                  'To: rcpt1@example.com',
                                  'To: rcpt2@example.com',
                                  '', ''])
        ret_headers, ret_body = env.flatten()
        self.assertEqual(header_str, ret_headers)
        self.assertEqual(body, ret_body)

    def test_encode_7bit(self):
        headers = Message()
        headers['From'] = 'sender@example.com'
        headers['To'] = 'rcpt@example.com'
        body = ''.join([six.unichr(i) for i in range(129, 256)]).encode('utf-8')
        env = Envelope(headers=headers, message=body)
        header_str = '\r\n'.join(['From: sender@example.com',
                                  'To: rcpt@example.com',
                                  '', ''])
        with self.assertRaises(UnicodeError):
            env.encode_7bit()

    def test_encode_7bit_encoding(self):
        headers = Message()
        headers['From'] = 'sender@example.com'
        headers['To'] = 'rcpt@example.com'
        body = bytes(bytearray(range(129, 256)))
        env = Envelope(headers=headers, message=body)
        header_str = '\r\n'.join(['From: sender@example.com',
                                  'To: rcpt@example.com',
                                  'Content-Transfer-Encoding: base64',
                                  '', ''])
        body_str = b'gYKDhIWGh4iJiouMjY6PkJGSk5SVlpeYmZqbnJ2en6ChoqOkpaanqKmqq6ytrq+wsbKztLW2t7i5\nuru8vb6/wMHCw8TFxsfIycrLzM3Oz9DR0tPU1dbX2Nna29zd3t/g4eLj5OXm5+jp6uvs7e7v8PHy\n8/T19vf4+fr7/P3+/w=='
        if six.PY3:
            body_str = body_str + b'\n'
        env.encode_7bit(encoder=encode_base64)
        ret_headers, ret_body = env.flatten()
        self.assertEqual(header_str, ret_headers)
        self.assertEqual(body_str, ret_body)

    def test_parse(self):
        env = Envelope()
        env.parse(b"""\
From: sender@example.com
To: rcpt1@example.com
To: rcpt2@example.com

test test\r
""")
        self.assertEqual('sender@example.com', env.headers['from'])
        self.assertEqual(['rcpt1@example.com', 'rcpt2@example.com'],
                         env.headers.get_all('To'))
        self.assertEqual(b'test test\r\n', env.message)

    def test_parse_onlyheaders(self):
        env = Envelope()
        env.parse(b"""\
From: sender@example.com
Subject: important things
""")
        self.assertEqual('sender@example.com', env.headers['from'])
        self.assertEqual('important things', env.headers['subject'])
        self.assertEqual(b'', env.message)

    def test_parse_nonascii_headers(self):
        env = Envelope()
        env.parse(b"""Subject: \xc3\xa9\xc3\xa9\n""")
        self.assertEqual('éé', env.headers['subject'])

    def test_parse_onlybody(self):
        env = Envelope()
        env.parse(b"""\
important things
""")
        self.assertEqual(b'important things\n', env.message)

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
        # email.generators.Generator.flatten behaviour differs from py2 to py3
        if six.PY2:
            self.assertEqual(b'test test\r\n', env.message)
        elif six.PY3:
            self.assertEqual(b'test test\n', env.message)

    def test_bounce(self):
        env = Envelope('sender@example.com', ['rcpt1@example.com',
                                              'rcpt2@example.com'])
        env.parse(b"""\
From: sender@example.com
To: rcpt1@example.com
To: rcpt2@example.com

test test\r
""")
        reply = Reply('550', '5.0.0 Rejected')

        Bounce.header_template = """\
X-Reply-Code: {code}
X-Reply-Message: {message}
X-Orig-Sender: {sender}

"""
        Bounce.footer_template = """\

EOM
"""
        bounce = Bounce(env, reply)

        self.assertEqual('', bounce.sender)
        self.assertEqual(['sender@example.com'], bounce.recipients)
        self.assertEqual('550', bounce.headers['X-Reply-Code'])
        self.assertEqual('5.0.0 Rejected', bounce.headers['X-Reply-Message'])
        self.assertEqual('sender@example.com', bounce.headers['X-Orig-Sender'])
        self.assertEqual(b"""\
From: sender@example.com\r
To: rcpt1@example.com\r
To: rcpt2@example.com\r
\r
test test\r

EOM
""", bounce.message)

    def test_bounce_headersonly(self):
        env = Envelope('sender@example.com', ['rcpt1@example.com',
                                              'rcpt2@example.com'])
        env.parse(b"""\
From: sender@example.com
To: rcpt1@example.com
To: rcpt2@example.com

test test\r
""")
        reply = Reply('550', '5.0.0 Rejected')

        Bounce.header_template = """\
X-Reply-Code: {code}
X-Reply-Message: {message}
X-Orig-Sender: {sender}

"""
        Bounce.footer_template = """\
\r
EOM\r
"""
        bounce = Bounce(env, reply, headers_only=True)

        self.assertEqual('', bounce.sender)
        self.assertEqual(['sender@example.com'], bounce.recipients)
        self.assertEqual('550', bounce.headers['X-Reply-Code'])
        self.assertEqual('5.0.0 Rejected', bounce.headers['X-Reply-Message'])
        self.assertEqual('sender@example.com', bounce.headers['X-Orig-Sender'])
        self.assertEqual(b"""\
From: sender@example.com\r
To: rcpt1@example.com\r
To: rcpt2@example.com\r
\r
\r
EOM\r
""", bounce.message)

# vim:et:fdm=marker:sts=4:sw=4:ts=4
