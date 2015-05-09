
import unittest2 as unittest

from slimta.relay.blackhole import BlackholeRelay
from slimta.envelope import Envelope
from slimta.policy import RelayPolicy


class TestBlackholeRelay(unittest.TestCase):

    def test_attempt(self):
        env = Envelope()
        blackhole = BlackholeRelay()
        ret = blackhole.attempt(env, 0)
        self.assertEqual('250', ret.code)

    def test_attempt_policies(self):
        class BadPolicy(RelayPolicy):
            def apply(self, env):
                raise Exception('that\'s bad policy!')
        env = Envelope()
        blackhole = BlackholeRelay()
        blackhole.add_policy(BadPolicy())
        ret = blackhole._attempt(env, 0)
        self.assertEqual('250', ret.code)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
