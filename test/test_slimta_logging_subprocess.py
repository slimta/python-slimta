
import unittest2 as unittest

from testfixtures import log_capture

from slimta.logging import getSubprocessLogger


class FakeSubprocess(object):

    def __init__(self, pid, returncode):
        self.pid = pid
        self.returncode = returncode


class TestSocketLogger(unittest.TestCase):

    def setUp(self):
        self.log = getSubprocessLogger('test')

    @log_capture()
    def test_popen(self, l):
        p = FakeSubprocess(320, 0)
        self.log.popen(p, ['one', 'two'])
        l.check(('test', 'DEBUG', 'pid:320:popen args=[\'one\', \'two\']'))

    @log_capture()
    def test_stdio(self, l):
        p = FakeSubprocess(828, 0)
        self.log.stdio(p, 'one', 'two', '')
        l.check(('test', 'DEBUG', 'pid:828:stdio stderr=\'\' stdin=\'one\' stdout=\'two\''))

    @log_capture()
    def test_exit(self, l):
        p = FakeSubprocess(299, 13)
        self.log.exit(p)
        l.check(('test', 'DEBUG', 'pid:299:exit returncode=13'))


# vim:et:fdm=marker:sts=4:sw=4:ts=4
