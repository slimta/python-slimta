
import unittest

from assertions import *

import gevent

from slimta.relay.pool import RelayPool, RelayPoolClient
from slimta.envelope import Envelope


class TestPool(RelayPool):

    def add_client(self):
        return TestClient(self.queue)


class TestClient(RelayPoolClient):

    def _run(self):
        ret = self.poll()
        if isinstance(ret, tuple):
            result, envelope = ret
            result.set('test')


class TestRelayPool(unittest.TestCase):

    def test_add_remove_client(self):
        pool = TestPool()
        pool.queue.append(True)
        pool._add_client()
        pool_copy = pool.pool.copy()
        for client in pool_copy:
            client.join()
        gevent.sleep(0)
        assert_false(pool.pool)

    def test_add_remove_client_morequeued(self):
        pool = TestPool()
        pool.queue.append(True)
        pool.queue.append(True)
        pool._add_client()
        pool_copy = pool.pool.copy()
        for client in pool_copy:
            client.join()
        assert_true(pool.pool)
        pool_copy = pool.pool.copy()
        for client in pool_copy:
            client.join()
        gevent.sleep(0)
        assert_false(pool.pool)

    def test_attempt(self):
        env = Envelope()
        pool = TestPool()
        ret = pool.attempt(env, 0)
        assert_equal('test', ret)

    def test_kill(self):
        pool = RelayPool()
        pool.pool.add(RelayPoolClient(None))
        pool.pool.add(RelayPoolClient(None))
        pool.pool.add(RelayPoolClient(None))
        for client in pool.pool:
            assert_false(client.ready())
        pool.kill()
        for client in pool.pool:
            assert_true(client.ready())


# vim:et:fdm=marker:sts=4:sw=4:ts=4
