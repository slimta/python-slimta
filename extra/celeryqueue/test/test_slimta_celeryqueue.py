
import unittest

from mox import MoxTestBase, IsA


class TestCeleryQueue(MoxTestBase):

    def test_nothing(self):
        from nose.exc import SkipTest
        raise SkipTest()


# vim:et:fdm=marker:sts=4:sw=4:ts=4
