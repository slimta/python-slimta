import unittest2 as unittest

from slimta.envelope import Envelope
from slimta.bounce import Bounce
from slimta.smtp.reply import Reply


class TestBounce(unittest.TestCase):

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
From: sender@example.com
To: rcpt1@example.com
To: rcpt2@example.com

test test

EOM
""".replace(b'\n', b'\r\n'), bounce.message)

    def test_bounce_headersonly(self):
        env = Envelope('sender@example.com', ['rcpt1@example.com',
                                              'rcpt2@example.com'])
        env.parse(b"""\
From: sender@example.com
To: rcpt1@example.com
To: rcpt2@example.com

test test
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
        bounce = Bounce(env, reply, headers_only=True)

        self.assertEqual('', bounce.sender)
        self.assertEqual(['sender@example.com'], bounce.recipients)
        self.assertEqual('550', bounce.headers['X-Reply-Code'])
        self.assertEqual('5.0.0 Rejected', bounce.headers['X-Reply-Message'])
        self.assertEqual('sender@example.com', bounce.headers['X-Orig-Sender'])
        self.assertEqual(b"""\
From: sender@example.com
To: rcpt1@example.com
To: rcpt2@example.com


EOM
""".replace(b'\n', b'\r\n'), bounce.message)

# vim:et:fdm=marker:sts=4:sw=4:ts=4
