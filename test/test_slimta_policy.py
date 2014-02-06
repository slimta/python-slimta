
import unittest

from assertions import *

from slimta.policy import QueuePolicy, RelayPolicy


class TestPolicy(unittest.TestCase):

    def test_queuepolicy_interface(self):
        qp = QueuePolicy()
        assert_raises(NotImplementedError, qp.apply, None)

    def test_relaypolicy_interface(self):
        rp = RelayPolicy()
        assert_raises(NotImplementedError, rp.apply, None)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
