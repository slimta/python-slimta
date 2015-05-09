
import unittest2 as unittest

import gevent
from mox import MoxTestBase, IgnoreArg
from dns.resolver import NXDOMAIN
from dns.exception import DNSException
from dns.exception import SyntaxError as DnsSyntaxError

from slimta.util import dns_resolver
from slimta.util.ptrlookup import PtrLookup


class TestPtrLookup(unittest.TestCase, MoxTestBase):

    def test_from_getpeername(self):
        sock = self.mox.CreateMockAnything()
        sock.getpeername().AndReturn(('127.0.0.1', 0))
        self.mox.ReplayAll()
        ptr, port = PtrLookup.from_getpeername(sock)
        self.assertEqual(0, port)
        self.assertIsInstance(ptr, PtrLookup)
        self.assertEqual('127.0.0.1', ptr.ip)

    def test_from_getsockname(self):
        sock = self.mox.CreateMockAnything()
        sock.getsockname().AndReturn(('127.0.0.1', 0))
        self.mox.ReplayAll()
        ptr, port = PtrLookup.from_getsockname(sock)
        self.assertEqual(0, port)
        self.assertIsInstance(ptr, PtrLookup)
        self.assertEqual('127.0.0.1', ptr.ip)

    def test_run_nxdomain(self):
        self.mox.StubOutWithMock(dns_resolver, 'query')
        dns_resolver.query(IgnoreArg(), 'PTR').AndRaise(NXDOMAIN)
        self.mox.ReplayAll()
        ptr = PtrLookup('127.0.0.1')
        self.assertIsInstance(ptr, gevent.Greenlet)
        self.assertIsNone(ptr._run())

    def test_run_dnsexception(self):
        self.mox.StubOutWithMock(dns_resolver, 'query')
        dns_resolver.query(IgnoreArg(), 'PTR').AndRaise(DNSException)
        self.mox.ReplayAll()
        ptr = PtrLookup('127.0.0.1')
        self.assertIsInstance(ptr, gevent.Greenlet)
        self.assertIsNone(ptr._run())

    def test_run_dnssyntaxerror(self):
        self.mox.StubOutWithMock(dns_resolver, 'query')
        self.mox.ReplayAll()
        ptr = PtrLookup('abcd')
        self.assertIsInstance(ptr, gevent.Greenlet)
        self.assertIsNone(ptr._run())

    def test_finish(self):
        self.mox.StubOutWithMock(dns_resolver, 'query')
        dns_resolver.query(IgnoreArg(), 'PTR').AndReturn(['example.com'])
        self.mox.ReplayAll()
        ptr = PtrLookup('127.0.0.1')
        ptr.start()
        self.assertEqual('example.com', ptr.finish(runtime=1.0))

    def test_finish_timeout(self):
        self.mox.StubOutWithMock(dns_resolver, 'query')
        def long_sleep(*args):
            gevent.sleep(1.0)
        dns_resolver.query(IgnoreArg(), 'PTR').WithSideEffects(long_sleep)
        self.mox.ReplayAll()
        ptr = PtrLookup('127.0.0.1')
        ptr.start()
        self.assertIsNone(ptr.finish(runtime=0.0))


# vim:et:fdm=marker:sts=4:sw=4:ts=4
