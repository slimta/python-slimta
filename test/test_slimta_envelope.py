
import unittest
from email.message import Message

from slimta.envelope import Envelope
from slimta.bounce import Bounce
from slimta.smtp.reply import Reply


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

        self.assertEqual('', bounce.sender)
        self.assertEqual(['sender@example.com'], bounce.recipients)
        self.assertEqual('550', bounce.headers['X-Reply-Code'])
        self.assertEqual('5.0.0 Rejected', bounce.headers['X-Reply-Message'])
        self.assertEqual('sender@example.com', bounce.headers['X-Orig-Sender'])
        self.assertEqual("""\
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

        self.assertEqual('', bounce.sender)
        self.assertEqual(['sender@example.com'], bounce.recipients)
        self.assertEqual('550', bounce.headers['X-Reply-Code'])
        self.assertEqual('5.0.0 Rejected', bounce.headers['X-Reply-Message'])
        self.assertEqual('sender@example.com', bounce.headers['X-Orig-Sender'])
        self.assertEqual("""\
From: sender@example.com\r
To: rcpt1@example.com\r
To: rcpt2@example.com\r
\r
\r
EOM\r
""", bounce.message)

# vim:et:fdm=marker:sts=4:sw=4:ts=4
