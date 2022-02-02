
from mox import MoxTestBase, IsA

from slimta.envelope import Envelope
from slimta.lookup.policy import LookupPolicy
from slimta.lookup.drivers.dict import DictLookup


class TestDictLookup(MoxTestBase):

    def setUp(self):
        super(TestDictLookup, self).setUp()
        self.data = {}
        self.address_policy = LookupPolicy(DictLookup(self.data, '{address}'), True, True)
        self.domain_policy = LookupPolicy(DictLookup(self.data, '{domain}'), True, True)

    def test_verp(self):
        self.data['sender@example.com'] = {'verp': 'verp.com'}
        self.data['rcpt2@example.com'] = {'verp': 'verp.com'}
        env = Envelope('sender@example.com', ['rcpt1@example.com', 'rcpt2@example.com'])
        self.address_policy.apply(env)
        self.assertEquals('sender=example.com@verp.com', env.sender)
        self.assertEquals(['rcpt1@example.com', 'rcpt2=example.com@verp.com'], env.recipients)

    def test_alias(self):
        self.data['sender@example.com'] = {'alias': 'sender@other.com'}
        self.data['rcpt2@example.com'] = {'alias': 'other.com'}
        env = Envelope('sender@example.com', ['rcpt1@example.com', 'rcpt2@example.com'])
        self.address_policy.apply(env)
        self.assertEquals('sender@other.com', env.sender)
        self.assertEquals(['rcpt1@example.com', 'rcpt2@other.com'], env.recipients)

    def test_alias_domain(self):
        self.data['example.com'] = {'alias': 'other.com'}
        env = Envelope('sender@example.com', ['rcpt1@example.com', 'rcpt2@example.com'])
        self.domain_policy.apply(env)
        self.assertEquals('sender@other.com', env.sender)
        self.assertEquals(['rcpt1@other.com', 'rcpt2@other.com'], env.recipients)

    def test_alias_rewrite(self):
        self.data['sender@example.com'] = {'alias': 'test+{localpart}@other.com'}
        self.data['rcpt2@example.com'] = {'alias': 'test@{domain}'}
        env = Envelope('sender@example.com', ['rcpt1@example.com', 'rcpt2@example.com'])
        self.address_policy.apply(env)
        self.assertEquals('test+sender@other.com', env.sender)
        self.assertEquals(['rcpt1@example.com', 'test@example.com'], env.recipients)

    def test_alias_domain_rewrite(self):
        self.data['example.com'] = {'alias': 'test+{localpart}@other.com'}
        env = Envelope('sender@example.com', ['rcpt1@example.com', 'rcpt2@example.com'])
        self.domain_policy.apply(env)
        self.assertEquals('test+sender@other.com', env.sender)
        self.assertEquals(['test+rcpt1@other.com', 'test+rcpt2@other.com'], env.recipients)

    def test_add_headers(self):
        self.data['sender@example.com'] = {'add_headers': '{"X-Test-A": "one"}'}
        self.data['rcpt2@example.com'] = {'add_headers': '{"X-Test-B": "two"}'}
        env = Envelope('sender@example.com', ['rcpt1@example.com', 'rcpt2@example.com'])
        env.parse(b"""\n\n""")
        self.address_policy.apply(env)
        self.assertEquals('one', env.headers['x-test-a'])
        self.assertEquals('two', env.headers['x-test-b'])

# vim:et:fdm=marker:sts=4:sw=4:ts=4:tw=0
