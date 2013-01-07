
import unittest

import gevent
from gevent import Greenlet

from slimta.relay.smtp.static import StaticSmtpRelay
from slimta.envelope import Envelope


class FakeClient(Greenlet):

    def __init__(self, address, queue, **kwargs):
        super(FakeClient, self).__init__()
        self.queue = queue
        self.idle = True

    def _run(self):
        ret = self.queue.get(timeout=1)
        if isinstance(ret, tuple):
            priority, result, envelope = ret
            result.set('test')


class TestStaticSmtpRelay(unittest.TestCase):

    def test_add_remove_client(self):
        static = StaticSmtpRelay(None, client_class=FakeClient)
        static.queue.put(True)
        static._add_client()
        for client in static.pool:
            client.join()
        gevent.sleep(0)
        self.assertFalse(static.pool)

    def test_add_remove_client_morequeued(self):
        static = StaticSmtpRelay(None, client_class=FakeClient)
        static.queue.put(True)
        static.queue.put(True)
        static._add_client()
        for client in static.pool:
            client.join()
        self.assertTrue(static.pool)
        for client in static.pool:
            client.join()
        gevent.sleep(0)
        self.assertFalse(static.pool)

    def test_attempt(self):
        env = Envelope()
        static = StaticSmtpRelay(None, client_class=FakeClient)
        ret = static.attempt(env, 0)
        self.assertEqual('test', ret)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
