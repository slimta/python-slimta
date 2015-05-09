
import unittest2 as unittest
import uuid

from testfixtures import log_capture

from slimta.logging import getQueueStorageLogger
from slimta.envelope import Envelope


class TestSocketLogger(unittest.TestCase):

    def setUp(self):
        self.log = getQueueStorageLogger('test')

    @log_capture()
    def test_write(self, l):
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        self.log.write('123abc', env)
        l.check(('test', 'DEBUG', 'queue:123abc:write recipients=[\'rcpt@example.com\'] sender=\'sender@example.com\''))

    @log_capture()
    def test_update_meta(self, l):
        self.log.update_meta('1234', timestamp=12345)
        l.check(('test', 'DEBUG', 'queue:1234:meta timestamp=12345'))

    @log_capture()
    def test_remove(self, l):
        id = uuid.uuid4().hex
        self.log.remove(id)
        l.check(('test', 'DEBUG', 'queue:{0}:remove'.format(id)))


# vim:et:fdm=marker:sts=4:sw=4:ts=4
