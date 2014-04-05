
import unittest

from assertions import *

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

        assert_equal('sender@example.com', env1.sender)
        assert_equal(['rcpt1@example.com'], env1.recipients)
        assert_equal('sender@example.com', env1.headers['from'])
        assert_equal(['rcpt1@example.com', 'rcpt2@example.com'],
                         env1.headers.get_all('To'))
        assert_equal('test test\r\n', env1.message)

        assert_equal('sender@example.com', env2.sender)
        assert_equal(['rcpt2@example.com'], env2.recipients)
        assert_equal('sender@example.com', env2.headers['from'])
        assert_equal(['rcpt1@example.com', 'rcpt2@example.com'],
                         env2.headers.get_all('To'))
        assert_equal('test test\r\n', env2.message)

    def test_recipientsplit_apply_onercpt(self):
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        policy = RecipientSplit()
        assert_false(policy.apply(env))

    def test_recipientdomainsplit_get_domain(self):
        policy = RecipientDomainSplit()
        assert_equal('example.com', policy._get_domain('rcpt@example.com'))
        assert_equal('example.com', policy._get_domain('rcpt@Example.com'))
        assert_raises(ValueError, policy._get_domain, 'rcpt@')
        assert_raises(ValueError, policy._get_domain, 'rcpt')

    def test_recipientdomainsplit_get_domain_groups(self):
        policy = RecipientDomainSplit()
        groups, bad_rcpts = policy._get_domain_groups(['rcpt@example.com'])
        assert_equal({'example.com': ['rcpt@example.com']}, groups)
        assert_equal([], bad_rcpts)
        groups, bad_rcpts = policy._get_domain_groups(['rcpt1@example.com', 'rcpt2@Example.com'])
        assert_equal({'example.com': ['rcpt1@example.com', 'rcpt2@Example.com']}, groups)
        assert_equal([], bad_rcpts)
        groups, bad_rcpts = policy._get_domain_groups(['rcpt1@example.com', 'rcpt2@Example.com', 'rcpt@test.com'])
        assert_equal({'example.com': ['rcpt1@example.com', 'rcpt2@Example.com'],
                          'test.com': ['rcpt@test.com']}, groups)
        assert_equal([], bad_rcpts)
        groups, bad_rcpts = policy._get_domain_groups(['rcpt@example.com', 'rcpt'])
        assert_equal({'example.com': ['rcpt@example.com']}, groups)
        assert_equal(['rcpt'], bad_rcpts)

    def test_recipientdomainsplit_apply(self):
        env = Envelope('sender@example.com', ['rcpt1@example.com',
                                              'rcpt2@example.com',
                                              'rcpt@test.com'])
        env.parse("""\r\ntest test\r\n""")
        policy = RecipientDomainSplit()
        env1, env2 = policy.apply(env)

        assert_equal('sender@example.com', env1.sender)
        assert_equal(['rcpt1@example.com', 'rcpt2@example.com'], env1.recipients)
        assert_equal('test test\r\n', env1.message)

        assert_equal('sender@example.com', env2.sender)
        assert_equal(['rcpt@test.com'], env2.recipients)
        assert_equal('test test\r\n', env2.message)

    def test_recipientdomainsplit_apply_allbadrcpts(self):
        env = Envelope('sender@example.com', ['rcpt1', 'rcpt2@'])
        env.parse("""\r\ntest test\r\n""")
        policy = RecipientDomainSplit()
        env1, env2 = policy.apply(env)

        assert_equal('sender@example.com', env1.sender)
        assert_equal(['rcpt1'], env1.recipients)
        assert_equal('test test\r\n', env1.message)

        assert_equal('sender@example.com', env2.sender)
        assert_equal(['rcpt2@'], env2.recipients)
        assert_equal('test test\r\n', env2.message)

    def test_recipientdomainsplit_apply_onedomain(self):
        env = Envelope('sender@example.com', ['rcpt1@example.com',
                                              'rcpt2@example.com'])
        env.parse('')
        policy = RecipientDomainSplit()
        assert_false(policy.apply(env))


# vim:et:fdm=marker:sts=4:sw=4:ts=4
