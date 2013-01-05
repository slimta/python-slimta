
import unittest

from mox import MoxTestBase, IsA
import dns.resolver

from slimta.relay.smtp.mx import MxSmtpRelay, MxRecord, NoDomainError
from slimta.relay.smtp.static import StaticSmtpRelay
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


class TestMxSmtpRelay(MoxTestBase):

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
        self.mox.StubOutWithMock(dns.resolver, 'query')
        dns.resolver.query('example.com', 'MX').AndReturn(mx_ret)
        mx.new_static_relay('mx1.example.com', 25).AndReturn(static)
        static.attempt(env, 0)
        mx.new_static_relay('mx2.example.com', 25).AndReturn(static)
        static.attempt(env, 1)
        self.mox.ReplayAll()
        mx.attempt(env, 0)
        mx.attempt(env, 1)

    def test_attempt_expiredmx(self):
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        mx_ret = FakeMxAnswer(True, [(10, 'mx2.example.com'),
                                     (5, 'mx1.example.com')])
        mx = MxSmtpRelay()
        static = self.mox.CreateMock(StaticSmtpRelay)
        self.mox.StubOutWithMock(mx, 'new_static_relay')
        self.mox.StubOutWithMock(dns.resolver, 'query')
        dns.resolver.query('example.com', 'MX').AndReturn(mx_ret)
        mx.new_static_relay('mx1.example.com', 25).AndReturn(static)
        static.attempt(env, 0)
        dns.resolver.query('example.com', 'MX').AndReturn(mx_ret)
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


# vim:et:fdm=marker:sts=4:sw=4:ts=4
