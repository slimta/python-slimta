
import unittest2 as unittest
from mox import MoxTestBase, IsA

from slimta.relay.smtp.static import StaticSmtpRelay
from slimta.relay.smtp.client import SmtpRelayClient


class TestStaticSmtpRelay(unittest.TestCase, MoxTestBase):

    def test_add_client(self):
        static = StaticSmtpRelay('testhost')
        ret = static.add_client()
        self.assertIsInstance(ret, SmtpRelayClient)

    def test_add_client_custom(self):
        def fake_class(addr, queue, **kwargs):
            self.assertEqual(('testhost', 25), addr)
            return 'success'
        static = StaticSmtpRelay('testhost', client_class=fake_class)
        self.assertEqual('success', static.add_client())


# vim:et:fdm=marker:sts=4:sw=4:ts=4
