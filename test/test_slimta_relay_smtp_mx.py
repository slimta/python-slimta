
import unittest2 as unittest
from mox import MoxTestBase, IsA
import dns.resolver
from dns.exception import Timeout as DNSTimeout

from slimta.relay import TransientRelayError, PermanentRelayError
from slimta.relay.smtp.mx import MxSmtpRelay, MxRecord, NoDomainError
from slimta.relay.smtp.static import StaticSmtpRelay
from slimta.util import dns_resolver
from slimta.envelope import Envelope


class FakeMxAnswer(object):

    def __init__(self, expired, rdata):
        class FakeMxRdata(object):
            def __init__(self, preference, exchange):
                self.preference = preference
                self.exchange = exchange
        self.expiration = float('-inf') if expired else float('inf')
        self.rdata = [FakeMxRdata(*rr) for rr in rdata]

    def __iter__(self):
        return iter(self.rdata)


class FakeAAnswer(object):

    def __init__(self, expired, rdata):
        class FakeARdata(object):
            def __init__(self, address):
                self.address = address
        self.expiration = float('-inf') if expired else float('inf')
        self.rdata = [FakeARdata(*rr) for rr in rdata]

    def __iter__(self):
        return iter(self.rdata)


class TestMxSmtpRelay(unittest.TestCase, MoxTestBase):

    def test_get_rcpt_domain(self):
        env = Envelope('sender@example.com', ['rcpt@Example.com'])
        mx = MxSmtpRelay()
        self.assertEqual('example.com', mx._get_rcpt_domain(env))

    def test_get_rcpt_domain_error(self):
        env = Envelope('sender@example.com', ['badrcpt'])
        mx = MxSmtpRelay()
        self.assertRaises(NoDomainError, mx._get_rcpt_domain, env)

    def test_choose_mx(self):
        records = [(1, 1), (2, 2), (3, 3), (4, 4), (5, 5)]
        mx = MxSmtpRelay()
        self.assertEqual(1, mx.choose_mx(records, 0))
        self.assertEqual(5, mx.choose_mx(records, 4))
        self.assertEqual(1, mx.choose_mx(records, 5))
        self.assertEqual(3, mx.choose_mx(records, 7))
        self.assertEqual(2, mx.choose_mx(records, 1821))

    def test_attempt(self):
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        mx_ret = FakeMxAnswer(False, [(5, 'mx1.example.com'),
                                      (10, 'mx2.example.com')])
        mx = MxSmtpRelay()
        static = self.mox.CreateMock(StaticSmtpRelay)
        self.mox.StubOutWithMock(mx, 'new_static_relay')
        self.mox.StubOutWithMock(dns_resolver, 'query')
        dns_resolver.query('example.com', 'MX').AndReturn(mx_ret)
        mx.new_static_relay('mx1.example.com', 25).AndReturn(static)
        static.attempt(env, 0)
        mx.new_static_relay('mx2.example.com', 25).AndReturn(static)
        static.attempt(env, 1)
        self.mox.ReplayAll()
        mx.attempt(env, 0)
        mx.attempt(env, 1)

    def test_attempt_no_mx(self):
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        a_ret = FakeAAnswer(False, [('1.2.3.4', )])
        mx = MxSmtpRelay()
        static = self.mox.CreateMock(StaticSmtpRelay)
        self.mox.StubOutWithMock(mx, 'new_static_relay')
        self.mox.StubOutWithMock(dns_resolver, 'query')
        dns_resolver.query('example.com', 'MX').AndRaise(dns.resolver.NXDOMAIN)
        dns_resolver.query('example.com', 'A').AndReturn(a_ret)
        mx.new_static_relay('1.2.3.4', 25).AndReturn(static)
        static.attempt(env, 0)
        self.mox.ReplayAll()
        mx.attempt(env, 0)

    def test_attempt_no_records(self):
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        mx = MxSmtpRelay()
        static = self.mox.CreateMock(StaticSmtpRelay)
        self.mox.StubOutWithMock(mx, 'new_static_relay')
        self.mox.StubOutWithMock(dns_resolver, 'query')
        dns_resolver.query('example.com', 'MX').AndRaise(dns.resolver.NXDOMAIN)
        dns_resolver.query('example.com', 'A').AndRaise(dns.resolver.NXDOMAIN)
        self.mox.ReplayAll()
        with self.assertRaises(PermanentRelayError):
            mx.attempt(env, 0)

    def test_attempt_expiredmx(self):
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        mx_ret = FakeMxAnswer(True, [(10, 'mx2.example.com'),
                                     (5, 'mx1.example.com')])
        mx = MxSmtpRelay()
        static = self.mox.CreateMock(StaticSmtpRelay)
        self.mox.StubOutWithMock(mx, 'new_static_relay')
        self.mox.StubOutWithMock(dns_resolver, 'query')
        dns_resolver.query('example.com', 'MX').AndReturn(mx_ret)
        mx.new_static_relay('mx1.example.com', 25).AndReturn(static)
        static.attempt(env, 0)
        dns_resolver.query('example.com', 'MX').AndReturn(mx_ret)
        mx.new_static_relay('mx2.example.com', 25).AndReturn(static)
        static.attempt(env, 1)
        self.mox.ReplayAll()
        mx.attempt(env, 0)
        mx.attempt(env, 1)

    def test_attempt_force_mx(self):
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        mx = MxSmtpRelay()
        static = self.mox.CreateMock(StaticSmtpRelay)
        self.mox.StubOutWithMock(mx, 'new_static_relay')
        mx.new_static_relay('mail.example.com', 25).AndReturn(static)
        static.attempt(env, 0)
        static.attempt(env, 1)
        self.mox.ReplayAll()
        mx.force_mx('example.com', 'mail.example.com')
        mx.attempt(env, 0)
        mx.attempt(env, 1)

    def test_attempt_no_answer(self):
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        mx = MxSmtpRelay()
        self.mox.StubOutWithMock(mx, 'new_static_relay')
        self.mox.StubOutWithMock(dns_resolver, 'query')
        dns_resolver.query('example.com', 'MX').AndRaise(dns.resolver.NoAnswer)
        dns_resolver.query('example.com', 'A').AndRaise(dns.resolver.NoAnswer)
        self.mox.ReplayAll()
        with self.assertRaises(PermanentRelayError):
            mx.attempt(env, 0)

    def test_attempt_no_answer(self):
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        mx = MxSmtpRelay()
        self.mox.StubOutWithMock(mx, 'new_static_relay')
        self.mox.StubOutWithMock(dns_resolver, 'query')
        dns_resolver.query('example.com', 'MX').AndRaise(DNSTimeout)
        self.mox.ReplayAll()
        with self.assertRaises(TransientRelayError):
            mx.attempt(env, 0)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
