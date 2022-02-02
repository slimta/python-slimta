
from redis import StrictRedis
from mox import MoxTestBase, IsA

from slimta.lookup.drivers.redis import RedisLookup


class TestRedisLookup(MoxTestBase):

    def setUp(self):
        super(TestRedisLookup, self).setUp()
        self.drv = RedisLookup('test {a} {b}')
        self.drv.redis = self.mox.CreateMock(StrictRedis)
        self.drv_hash = RedisLookup('test {a} {b}', use_hash=True)
        self.drv_hash.redis = self.mox.CreateMock(StrictRedis)

    def test_lookup_miss(self):
        self.drv.redis.get('test one two').AndReturn(None)
        self.mox.ReplayAll()
        self.assertEqual(None, self.drv.lookup(a='one', b='two'))

    def test_lookup_hit(self):
        self.drv.redis.get('test one two').AndReturn('{"test": "pass"}')
        self.mox.ReplayAll()
        expected = {"test": "pass"}
        self.assertEqual(expected, self.drv.lookup(a='one', b='two'))

    def test_hash_lookup_miss(self):
        self.drv_hash.redis.hgetall('test one two').AndReturn(None)
        self.mox.ReplayAll()
        self.assertEqual(None, self.drv_hash.lookup(a='one', b='two'))

    def test_hash_lookup_hit(self):
        self.drv_hash.redis.hgetall('test one two').AndReturn({'test': 'pass'})
        self.mox.ReplayAll()
        expected = {"test": "pass"}
        self.assertEqual(expected, self.drv_hash.lookup(a='one', b='two'))


# vim:et:fdm=marker:sts=4:sw=4:ts=4
