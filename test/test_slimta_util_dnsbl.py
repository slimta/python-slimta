
import unittest2 as unittest

from mox import MoxTestBase, IsA
import gevent
from dns.resolver import NXDOMAIN

from slimta.util import dns_resolver
from slimta.util.dnsbl import DnsBlocklist, DnsBlocklistGroup, check_dnsbl
from slimta.smtp.reply import Reply


class TestDnsbl(unittest.TestCase, MoxTestBase):

    def setUp(self):
        super(TestDnsbl, self).setUp()
        self.mox.StubOutWithMock(dns_resolver, 'query')
        self.dnsbl = DnsBlocklist('test.example.com')

    def test_dnsblocklist_build_query(self):
        self.assertEqual('4.3.2.1.test.example.com', self.dnsbl._build_query('1.2.3.4'))

    def test_dnsblocklist_get(self):
        dns_resolver.query('4.3.2.1.test.example.com', 'A')
        dns_resolver.query('8.7.6.5.test.example.com', 'A').AndRaise(NXDOMAIN)
        self.mox.ReplayAll()
        self.assertTrue(self.dnsbl.get('1.2.3.4'))
        self.assertNotIn('5.6.7.8', self.dnsbl)

    def test_dnsblocklist_get_reason(self):
        dns_resolver.query('4.3.2.1.test.example.com', 'TXT')
        dns_resolver.query('4.3.2.1.test.example.com', 'TXT').AndReturn(['good reason'])
        dns_resolver.query('8.7.6.5.test.example.com', 'TXT').AndRaise(NXDOMAIN)
        self.mox.ReplayAll()
        self.assertEqual(None, self.dnsbl.get_reason('1.2.3.4'))
        self.assertEqual('good reason', self.dnsbl.get_reason('1.2.3.4'))
        self.assertEqual(None, self.dnsbl['5.6.7.8'])

    def test_dnsblocklistgroup_get(self):
        group = DnsBlocklistGroup()
        group.add_dnsbl('test1.example.com')
        group.add_dnsbl('test2.example.com')
        group.add_dnsbl('test3.example.com')
        dns_resolver.query('4.3.2.1.test1.example.com', 'A').InAnyOrder('one')
        dns_resolver.query('4.3.2.1.test2.example.com', 'A').InAnyOrder('one').AndRaise(NXDOMAIN)
        dns_resolver.query('4.3.2.1.test3.example.com', 'A').InAnyOrder('one')
        dns_resolver.query('8.7.6.5.test1.example.com', 'A').InAnyOrder('two').AndRaise(NXDOMAIN)
        dns_resolver.query('8.7.6.5.test2.example.com', 'A').InAnyOrder('two').AndRaise(NXDOMAIN)
        dns_resolver.query('8.7.6.5.test3.example.com', 'A').InAnyOrder('two').AndRaise(NXDOMAIN)
        self.mox.ReplayAll()
        self.assertEqual(set(['test1.example.com', 'test3.example.com']), group.get('1.2.3.4'))
        self.assertNotIn('5.6.7.8', group)

    def test_dnsblocklistgroup_get_reasons(self):
        group = DnsBlocklistGroup()
        group.add_dnsbl('test1.example.com')
        group.add_dnsbl('test2.example.com')
        group.add_dnsbl('test3.example.com')
        dns_resolver.query('4.3.2.1.test1.example.com', 'TXT').InAnyOrder().AndReturn(['reason one'])
        dns_resolver.query('4.3.2.1.test3.example.com', 'TXT').InAnyOrder()
        self.mox.ReplayAll()
        self.assertEqual({'test1.example.com': 'reason one', 'test3.example.com': None},
                         group.get_reasons(set(['test1.example.com', 'test3.example.com']), '1.2.3.4'))

    def test_check_dnsrbl(self):
        class TestSession(object):
            address = ('1.2.3.4', 56789)
        class TestValidators(object):
            def __init__(self):
                self.session = TestSession()
            @check_dnsbl('test.example.com')
            def validate_mail(self, reply, sender):
                assert False

        dns_resolver.query('4.3.2.1.test.example.com', 'A').AndRaise(NXDOMAIN)
        dns_resolver.query('4.3.2.1.test.example.com', 'A')
        self.mox.ReplayAll()
        validators = TestValidators()
        reply = Reply('250', '2.0.0 Ok')
        self.assertRaises(AssertionError, validators.validate_mail, reply, 'asdf')
        self.assertEqual('250', reply.code)
        self.assertEqual('2.0.0 Ok', reply.message)
        validators.validate_mail(reply, 'asdf')
        self.assertEqual('550', reply.code)
        self.assertEqual('5.7.1 Access denied', reply.message)



# vim:et:fdm=marker:sts=4:sw=4:ts=4
