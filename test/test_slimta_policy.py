
import unittest2 as unittest

from slimta.policy import QueuePolicy, RelayPolicy


class TestPolicy(unittest.TestCase):

    def test_queuepolicy_interface(self):
        qp = QueuePolicy()
        self.assertRaises(NotImplementedError, qp.apply, None)

    def test_relaypolicy_interface(self):
        rp = RelayPolicy()
        self.assertRaises(NotImplementedError, rp.apply, None)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
