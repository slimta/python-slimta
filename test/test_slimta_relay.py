
import unittest2 as unittest
from mox import MoxTestBase, IsA

from slimta.relay import Relay, PermanentRelayError, TransientRelayError
from slimta.policy import RelayPolicy
from slimta.envelope import Envelope


class TestRelay(unittest.TestCase, MoxTestBase):

    def test_default_replies(self):
        perm = PermanentRelayError('test msg')
        transient = TransientRelayError('test msg')
        self.assertEqual('550 5.0.0 test msg', str(perm.reply))
        self.assertEqual('450 4.0.0 test msg', str(transient.reply))

    def test_policies(self):
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        p1 = self.mox.CreateMock(RelayPolicy)
        p2 = self.mox.CreateMock(RelayPolicy)
        p1.apply(env)
        p2.apply(env)
        self.mox.ReplayAll()
        relay = Relay()
        relay.add_policy(p1)
        relay.add_policy(p2)
        self.assertRaises(TypeError, relay.add_policy, None)
        relay._run_policies(env)

    def test_private_attempt(self):
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        relay = Relay()
        self.mox.StubOutWithMock(relay, '_run_policies')
        self.mox.StubOutWithMock(relay, 'attempt')
        relay._run_policies(env)
        relay.attempt(env, 0)
        self.mox.ReplayAll()
        relay._attempt(env, 0)

    def test_public_attempt(self):
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        relay = Relay()
        self.assertRaises(NotImplementedError, relay.attempt, env, 0)

    def test_kill(self):
        relay = Relay()
        relay.kill()  # no-op!


# vim:et:fdm=marker:sts=4:sw=4:ts=4
