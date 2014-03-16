
from assertions import *

from mox import MoxTestBase, IsA

from slimta.relay.smtp.static import StaticSmtpRelay
from slimta.relay.smtp.client import SmtpRelayClient


class TestStaticSmtpRelay(MoxTestBase):

    def test_add_client(self):
        static = StaticSmtpRelay('testhost')
        ret = static.add_client()
        assert_is_instance(ret, SmtpRelayClient)

    def test_add_client_custom(self):
        def fake_class(addr, queue, **kwargs):
            assert_equal(('testhost', 25), addr)
            return 'success'
        static = StaticSmtpRelay('testhost', client_class=fake_class)
        assert_equal('success', static.add_client())


# vim:et:fdm=marker:sts=4:sw=4:ts=4
