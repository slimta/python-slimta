
import unittest

from assertions import *
from base64 import b64encode
from email.message import Message
from email.encoders import encode_base64

from slimta.envelope import Envelope
from slimta.bounce import Bounce
from slimta.smtp.reply import Reply


class TestEnvelope(unittest.TestCase):

    def test_copy(self):
        env1 = Envelope('sender@example.com', ['rcpt1@example.com'])
        env1.parse("""\
From: sender@example.com
To: rcpt1@example.com

test test
""".replace('\n', '\r\n'))
        env2 = env1.copy()
        env2.recipients.append('rcpt2@example.com')
        env2.headers['To'] = 'rcpt2@example.com'
        assert_equal('sender@example.com', env1.sender)
        assert_equal(['rcpt1@example.com'], env1.recipients)
        assert_equal(['rcpt1@example.com'], env1.headers.get_all('To'))
        assert_equal('sender@example.com', env2.sender)
        assert_equal(['rcpt1@example.com', 'rcpt2@example.com'], env2.recipients)
        assert_equal(['rcpt1@example.com', 'rcpt2@example.com'], env2.headers.get_all('To'))

    def test_repr(self):
        env = Envelope('sender@example.com')
        s = repr(env)
        assert_regexp_matches(s, r"<Envelope at 0x[a-fA-F0-9]+, sender='sender@example.com'>")

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
        assert_equal(header_str, ret_headers)
        assert_equal(body, ret_body)

    def test_encode_7bit(self):
        headers = Message()
        headers['From'] = 'sender@example.com'
        headers['To'] = 'rcpt@example.com'
        body = ''.join([chr(i) for i in range(129, 256)])
        env = Envelope(headers=headers, message=body)
        header_str = '\r\n'.join(['From: sender@example.com',
                                  'To: rcpt@example.com',
                                  '', ''])
        with assert_raises(UnicodeDecodeError):
            env.encode_7bit()

    def test_encode_7bit_encoding(self):
        headers = Message()
        headers['From'] = 'sender@example.com'
        headers['To'] = 'rcpt@example.com'
        body = ''.join([chr(i) for i in range(129, 256)])
        env = Envelope(headers=headers, message=body)
        header_str = '\r\n'.join(['From: sender@example.com',
                                  'To: rcpt@example.com',
                                  'Content-Transfer-Encoding: base64',
                                  '', ''])
        body_str = 'gYKDhIWGh4iJiouMjY6PkJGSk5SVlpeYmZqbnJ2en6ChoqOkpaanqKmqq6ytrq+wsbKztLW2t7i5\nuru8vb6/wMHCw8TFxsfIycrLzM3Oz9DR0tPU1dbX2Nna29zd3t/g4eLj5OXm5+jp6uvs7e7v8PHy\n8/T19vf4+fr7/P3+/w=='
        env.encode_7bit(encoder=encode_base64)
        ret_headers, ret_body = env.flatten()
        assert_equal(header_str, ret_headers)
        assert_equal(body_str, ret_body)

    def test_parse(self):
        env = Envelope()
        env.parse("""\
From: sender@example.com
To: rcpt1@example.com
To: rcpt2@example.com

test test\r
""")
        assert_equal('sender@example.com', env.headers['from'])
        assert_equal(['rcpt1@example.com', 'rcpt2@example.com'],
                         env.headers.get_all('To'))
        assert_equal('test test\r\n', env.message)

    def test_parse_onlyheaders(self):
        env = Envelope()
        env.parse("""\
From: sender@example.com
Subject: important things
""")
        assert_equal('sender@example.com', env.headers['from'])
        assert_equal('important things', env.headers['subject'])
        assert_equal('', env.message)

    def test_parse_onlybody(self):
        env = Envelope()
        env.parse("""\
important things
""")
        assert_equal('important things\n', env.message)

    def test_parse_message_object(self):
        data = Message()
        data['From'] = 'sender@example.com'
        data['To'] = 'rcpt1@example.com'
        data['To'] = 'rcpt2@example.com'
        data.set_payload('test test\r\n')
        env = Envelope()
        env.parse(data)
        assert_equal('sender@example.com', env.headers['from'])
        assert_equal(['rcpt1@example.com', 'rcpt2@example.com'], env.headers.get_all('to'))
        assert_equal('test test\r\n', env.message)

    def test_bounce(self):
        env = Envelope('sender@example.com', ['rcpt1@example.com',
                                              'rcpt2@example.com'])
        env.parse("""\
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

        assert_equal('', bounce.sender)
        assert_equal(['sender@example.com'], bounce.recipients)
        assert_equal('550', bounce.headers['X-Reply-Code'])
        assert_equal('5.0.0 Rejected', bounce.headers['X-Reply-Message'])
        assert_equal('sender@example.com', bounce.headers['X-Orig-Sender'])
        assert_equal("""\
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
        env.parse("""\
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

        assert_equal('', bounce.sender)
        assert_equal(['sender@example.com'], bounce.recipients)
        assert_equal('550', bounce.headers['X-Reply-Code'])
        assert_equal('5.0.0 Rejected', bounce.headers['X-Reply-Message'])
        assert_equal('sender@example.com', bounce.headers['X-Orig-Sender'])
        assert_equal("""\
From: sender@example.com\r
To: rcpt1@example.com\r
To: rcpt2@example.com\r
\r
\r
EOM\r
""", bounce.message)

# vim:et:fdm=marker:sts=4:sw=4:ts=4
