
import unittest

from testfixtures import log_capture

from slimta.logging import getHttpLogger


class TestHttpLogger(unittest.TestCase):

    def setUp(self):
        self.log = getHttpLogger('test')
        self.environ = {'var': 'val'}

    @log_capture()
    def test_request(self, l):
        self.log.request(self.environ)
        l.check(('test', 'DEBUG', 'http:{0}:request environ={{\'var\': \'val\'}}'.format(id(self.environ))))

    @log_capture()
    def test_response(self, l):
        self.log.response(self.environ, '200 OK', [('Header', 'Value')])
        l.check(('test', 'DEBUG', 'http:{0}:response headers=[(\'Header\', \'Value\')] status=\'200 OK\''.format(id(self.environ))))


# vim:et:fdm=marker:sts=4:sw=4:ts=4
