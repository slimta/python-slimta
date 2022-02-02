
from mox import MoxTestBase, IsA

from slimta.lookup.drivers.dict import DictLookup


class TestDictLookup(MoxTestBase):

    def setUp(self):
        super(TestDictLookup, self).setUp()
        test = {'test one two': 1, 'test three four': 2}
        self.drv = DictLookup(test, 'test {a} {b}')

    def test_lookup_miss(self):
        self.assertEqual(None, self.drv.lookup(a='one', b='four'))
        self.assertEqual(None, self.drv.lookup(a='three', b='two'))

    def test_lookup_hit(self):
        self.assertEqual(1, self.drv.lookup(a='one', b='two'))
        self.assertEqual(2, self.drv.lookup(a='three', b='four'))

    def test_lookup_address(self):
        test = {'test one': 1, 'test two@example.com': 2}
        drv = DictLookup(test, 'test {address}')
        self.assertEqual(1, drv.lookup_address('one'))
        self.assertEqual(2, drv.lookup_address('two@example.com'))
        self.assertEqual(None, drv.lookup_address('three'))

    def test_lookup_address_domain(self):
        test = {'test one.com': 1}
        drv = DictLookup(test, 'test {domain}')
        self.assertEqual(1, drv.lookup_address('test@one.com'))
        self.assertEqual(None, drv.lookup_address('test@two.com'))


# vim:et:fdm=marker:sts=4:sw=4:ts=4
