
from mox import MoxTestBase

from slimta.lookup.drivers.regex import RegexLookup


class TestRegexLookup(MoxTestBase):

    def setUp(self):
        super(TestRegexLookup, self).setUp()
        self.drv = RegexLookup('test {a} {b}')
        self.drv.add_regex(r'^test [0-9]+ [a-zA-Z]+$', 1)
        self.drv.add_regex(r'^test [a-zA-Z]+ [0-9]+$', 2)

    def test_lookup_miss(self):
        self.assertEqual(None, self.drv.lookup(a='abc', b='def'))
        self.assertEqual(None, self.drv.lookup(a='123', b='456'))

    def test_lookup_hit(self):
        self.assertEqual(1, self.drv.lookup(a='123', b='abc'))
        self.assertEqual(2, self.drv.lookup(a='def', b='456'))

    def test_lookup_address(self):
        drv = RegexLookup('test {address}')
        drv.add_regex(r'^test one$', 1)
        drv.add_regex(r'^test two@example.com$', 2)
        self.assertEqual(1, drv.lookup_address('one'))
        self.assertEqual(2, drv.lookup_address('two@example.com'))
        self.assertEqual(None, drv.lookup_address('three'))

    def test_lookup_address_domain(self):
        drv = RegexLookup('test {domain}')
        drv.add_regex(r'^test one.com$', 1)
        self.assertEqual(1, drv.lookup_address('test@one.com'))
        self.assertEqual(None, drv.lookup_address('test@two.com'))


# vim:et:fdm=marker:sts=4:sw=4:ts=4
