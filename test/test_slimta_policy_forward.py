
import unittest2 as unittest

from slimta.policy.forward import Forward
from slimta.envelope import Envelope


class TestPolicyForward(unittest.TestCase):

    def test_no_mappings(self):
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        fwd = Forward()
        fwd.apply(env)
        self.assertEqual('sender@example.com', env.sender)
        self.assertEqual(['rcpt@example.com'], env.recipients)

    def test_no_matches(self):
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        fwd = Forward()
        fwd.add_mapping(r'nomatch', 'test')
        fwd.apply(env)
        self.assertEqual('sender@example.com', env.sender)
        self.assertEqual(['rcpt@example.com'], env.recipients)

    def test_simple(self):
        env = Envelope('sender@example.com', ['rcpt@example.com',
                                              'test@test.com'])
        fwd = Forward()
        fwd.add_mapping(r'^rcpt', 'test')
        fwd.add_mapping(r'test\.com$', 'example.com')
        fwd.apply(env)
        self.assertEqual('sender@example.com', env.sender)
        self.assertEqual(['test@example.com',
                          'test@example.com'], env.recipients)

    def test_shortcircuit(self):
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        fwd = Forward()
        fwd.add_mapping(r'^rcpt', 'test')
        fwd.add_mapping(r'^example', 'testdomain')
        fwd.apply(env)
        self.assertEqual('sender@example.com', env.sender)
        self.assertEqual(['test@example.com'], env.recipients)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
