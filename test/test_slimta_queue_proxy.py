
import unittest2 as unittest
from mox import MoxTestBase, IsA

from slimta.queue.proxy import ProxyQueue
from slimta.smtp.reply import Reply
from slimta.relay import Relay, TransientRelayError, PermanentRelayError
from slimta.envelope import Envelope


class TestProxyQueue(unittest.TestCase, MoxTestBase):

    def setUp(self):
        super(TestProxyQueue, self).setUp()
        self.relay = self.mox.CreateMock(Relay)
        self.env = Envelope('sender@example.com', ['rcpt@example.com'])

    def test_enqueue(self):
        self.relay._attempt(self.env, 0)
        self.mox.ReplayAll()
        q = ProxyQueue(self.relay)
        ret = q.enqueue(self.env)
        self.assertEqual(1, len(ret))
        self.assertEqual(2, len(ret[0]))
        self.assertEqual(self.env, ret[0][0])
        self.assertRegexpMatches(ret[0][1], r'[0-9a-fA-F]{32}')

    def test_enqueue_relayerror(self):
        err = PermanentRelayError('msg failure', Reply('550', 'Not Ok'))
        self.relay._attempt(self.env, 0).AndRaise(err)
        self.mox.ReplayAll()
        q = ProxyQueue(self.relay)
        ret = q.enqueue(self.env)
        self.assertEqual(1, len(ret))
        self.assertEqual(2, len(ret[0]))
        self.assertEqual(self.env, ret[0][0])
        self.assertEqual(err, ret[0][1])

    def test_start_noop(self):
        self.mox.ReplayAll()
        q = ProxyQueue(self.relay)
        q.start()

    def test_kill_noop(self):
        self.mox.ReplayAll()
        q = ProxyQueue(self.relay)
        q.kill()

    def test_flush_noop(self):
        self.mox.ReplayAll()
        q = ProxyQueue(self.relay)
        q.flush()

    def test_add_policy_error(self):
        self.mox.ReplayAll()
        q = ProxyQueue(self.relay)
        with self.assertRaises(NotImplementedError):
            q.add_policy('test')


# vim:et:fdm=marker:sts=4:sw=4:ts=4
