
from assertions import *

import gevent
from mox import MoxTestBase, IgnoreArg
from dns.resolver import NXDOMAIN
from dns.exception import DNSException
from dns.exception import SyntaxError as DnsSyntaxError

from slimta.util import dns_resolver
from slimta.util.ptrlookup import PtrLookup


class TestPtrLookup(MoxTestBase):

    def test_from_getpeername(self):
        sock = self.mox.CreateMockAnything()
        sock.getpeername().AndReturn(('127.0.0.1', 0))
        self.mox.ReplayAll()
        ptr, port = PtrLookup.from_getpeername(sock)
        assert_equal(0, port)
        assert_is_instance(ptr, PtrLookup)
        assert_equal('127.0.0.1', ptr.ip)

    def test_from_getsockname(self):
        sock = self.mox.CreateMockAnything()
        sock.getsockname().AndReturn(('127.0.0.1', 0))
        self.mox.ReplayAll()
        ptr, port = PtrLookup.from_getsockname(sock)
        assert_equal(0, port)
        assert_is_instance(ptr, PtrLookup)
        assert_equal('127.0.0.1', ptr.ip)

    def test_run_nxdomain(self):
        self.mox.StubOutWithMock(dns_resolver, 'query')
        dns_resolver.query(IgnoreArg(), 'PTR').AndRaise(NXDOMAIN)
        self.mox.ReplayAll()
        ptr = PtrLookup('127.0.0.1')
        assert_is_instance(ptr, gevent.Greenlet)
        assert_is_none(ptr._run())

    def test_run_dnsexception(self):
        self.mox.StubOutWithMock(dns_resolver, 'query')
        dns_resolver.query(IgnoreArg(), 'PTR').AndRaise(DNSException)
        self.mox.ReplayAll()
        ptr = PtrLookup('127.0.0.1')
        assert_is_instance(ptr, gevent.Greenlet)
        assert_is_none(ptr._run())

    def test_run_dnssyntaxerror(self):
        self.mox.StubOutWithMock(dns_resolver, 'query')
        self.mox.ReplayAll()
        ptr = PtrLookup('abcd')
        assert_is_instance(ptr, gevent.Greenlet)
        assert_is_none(ptr._run())

    def test_finish(self):
        self.mox.StubOutWithMock(dns_resolver, 'query')
        dns_resolver.query(IgnoreArg(), 'PTR').AndReturn(['example.com'])
        self.mox.ReplayAll()
        ptr = PtrLookup('127.0.0.1')
        ptr.start()
        assert_equal('example.com', ptr.finish(runtime=1.0))

    def test_finish_timeout(self):
        self.mox.StubOutWithMock(dns_resolver, 'query')
        def long_sleep(*args):
            gevent.sleep(1.0)
        dns_resolver.query(IgnoreArg(), 'PTR').WithSideEffects(long_sleep)
        self.mox.ReplayAll()
        ptr = PtrLookup('127.0.0.1')
        ptr.start()
        assert_is_none(ptr.finish(runtime=0.0))


# vim:et:fdm=marker:sts=4:sw=4:ts=4
