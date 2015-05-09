
import unittest2 as unittest

from slimta.policy.split import RecipientSplit, RecipientDomainSplit
from slimta.envelope import Envelope


class TestPoliySplit(unittest.TestCase):

    def test_recipientsplit_apply(self):
        env = Envelope('sender@example.com', ['rcpt1@example.com',
                                              'rcpt2@example.com'])
        env.parse("""\
From: sender@example.com
To: rcpt1@example.com
To: rcpt2@example.com

test test\r
""")
        policy = RecipientSplit()
        env1, env2 = policy.apply(env)

        self.assertEqual('sender@example.com', env1.sender)
        self.assertEqual(['rcpt1@example.com'], env1.recipients)
        self.assertEqual('sender@example.com', env1.headers['from'])
        self.assertEqual(['rcpt1@example.com', 'rcpt2@example.com'],
                         env1.headers.get_all('To'))
        self.assertEqual('test test\r\n', env1.message)

        self.assertEqual('sender@example.com', env2.sender)
        self.assertEqual(['rcpt2@example.com'], env2.recipients)
        self.assertEqual('sender@example.com', env2.headers['from'])
        self.assertEqual(['rcpt1@example.com', 'rcpt2@example.com'],
                         env2.headers.get_all('To'))
        self.assertEqual('test test\r\n', env2.message)

    def test_recipientsplit_apply_onercpt(self):
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        policy = RecipientSplit()
        self.assertFalse(policy.apply(env))

    def test_recipientdomainsplit_get_domain(self):
        policy = RecipientDomainSplit()
        self.assertEqual('example.com', policy._get_domain('rcpt@example.com'))
        self.assertEqual('example.com', policy._get_domain('rcpt@Example.com'))
        self.assertRaises(ValueError, policy._get_domain, 'rcpt@')
        self.assertRaises(ValueError, policy._get_domain, 'rcpt')

    def test_recipientdomainsplit_get_domain_groups(self):
        policy = RecipientDomainSplit()
        groups, bad_rcpts = policy._get_domain_groups(['rcpt@example.com'])
        self.assertEqual({'example.com': ['rcpt@example.com']}, groups)
        self.assertEqual([], bad_rcpts)
        groups, bad_rcpts = policy._get_domain_groups(['rcpt1@example.com', 'rcpt2@Example.com'])
        self.assertEqual({'example.com': ['rcpt1@example.com', 'rcpt2@Example.com']}, groups)
        self.assertEqual([], bad_rcpts)
        groups, bad_rcpts = policy._get_domain_groups(['rcpt1@example.com', 'rcpt2@Example.com', 'rcpt@test.com'])
        self.assertEqual({'example.com': ['rcpt1@example.com', 'rcpt2@Example.com'],
                          'test.com': ['rcpt@test.com']}, groups)
        self.assertEqual([], bad_rcpts)
        groups, bad_rcpts = policy._get_domain_groups(['rcpt@example.com', 'rcpt'])
        self.assertEqual({'example.com': ['rcpt@example.com']}, groups)
        self.assertEqual(['rcpt'], bad_rcpts)

    def test_recipientdomainsplit_apply(self):
        env = Envelope('sender@example.com', ['rcpt1@example.com',
                                              'rcpt2@example.com',
                                              'rcpt@test.com'])
        env.parse("""\r\ntest test\r\n""")
        policy = RecipientDomainSplit()
        env1, env2 = policy.apply(env)

        self.assertEqual('sender@example.com', env1.sender)
        self.assertEqual(['rcpt1@example.com', 'rcpt2@example.com'], env1.recipients)
        self.assertEqual('test test\r\n', env1.message)

        self.assertEqual('sender@example.com', env2.sender)
        self.assertEqual(['rcpt@test.com'], env2.recipients)
        self.assertEqual('test test\r\n', env2.message)

    def test_recipientdomainsplit_apply_allbadrcpts(self):
        env = Envelope('sender@example.com', ['rcpt1', 'rcpt2@'])
        env.parse("""\r\ntest test\r\n""")
        policy = RecipientDomainSplit()
        env1, env2 = policy.apply(env)

        self.assertEqual('sender@example.com', env1.sender)
        self.assertEqual(['rcpt1'], env1.recipients)
        self.assertEqual('test test\r\n', env1.message)

        self.assertEqual('sender@example.com', env2.sender)
        self.assertEqual(['rcpt2@'], env2.recipients)
        self.assertEqual('test test\r\n', env2.message)

    def test_recipientdomainsplit_apply_onedomain(self):
        env = Envelope('sender@example.com', ['rcpt1@example.com',
                                              'rcpt2@example.com'])
        env.parse('')
        policy = RecipientDomainSplit()
        self.assertFalse(policy.apply(env))


# vim:et:fdm=marker:sts=4:sw=4:ts=4
