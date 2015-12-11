from __future__ import unicode_literals

import unittest2 as unittest
import six

from testfixtures import log_capture

from slimta.logging import getHttpLogger


def native_dict(d):
    """ Converts dict keys/values to native strings

    (which is unicode for py3 and bytes for py2)

    """
    return {str(k): str(v) for k, v in d.items()}


class TestHttpLogger(unittest.TestCase):

    def setUp(self):
        self.log = getHttpLogger('test')
        self.environ = native_dict({
            'REQUEST_METHOD': 'GET',
            'PATH_INFO': '/test/stuff',
            'HTTP_HEADER': 'value'
        })
        self.conn = {}

    @log_capture()
    def test_wsgi_request(self, l):
        environ1 = native_dict({
            'REQUEST_METHOD': 'GET',
            'PATH_INFO': '/test/stuff',
            'CONTENT_LENGTH': 'value'
        })
        environ2 = native_dict({
            'REQUEST_METHOD': 'GET',
            'PATH_INFO': '/test/stuff',
            'CONTENT_TYPE': 'value'
        })
        environ3 = native_dict({
            'REQUEST_METHOD': 'GET',
            'PATH_INFO': '/test/stuff',
            'HTTP_X_HEADER_NAME': 'value'
        })
        self.log.wsgi_request(environ1)
        self.log.wsgi_request(environ2)
        self.log.wsgi_request(environ3)
        l.check((str('test'), str('DEBUG'), u'http:{0}:server_request headers=[(\'Content-Length\', \'value\')] method=\'GET\' path=\'/test/stuff\''.format(id(environ1))),
                    (str('test'), str('DEBUG'), u'http:{0}:server_request headers=[(\'Content-Type\', \'value\')] method=\'GET\' path=\'/test/stuff\''.format(id(environ2))),
                    (str('test'), str('DEBUG'), u'http:{0}:server_request headers=[(\'X-Header-Name\', \'value\')] method=\'GET\' path=\'/test/stuff\''.format(id(environ3))))

    @log_capture()
    def test_wsgi_response(self, l):
        environ = native_dict({
            'REQUEST_METHOD': 'GET',
            'PATH_INFO': '/test/stuff',
            'HTTP_HEADER': 'value'
        })
        self.log.wsgi_response(environ, '200 OK', [(b'Header', b'value')])
        if six.PY2:
            l.check((b'test', b'DEBUG', 'http:{0}:server_response headers=[(\'Header\', \'value\')] status=u\'200 OK\''.format(id(environ))))
        else:
            l.check(('test', 'DEBUG', 'http:{0}:server_response headers=[(b\'Header\', b\'value\')] status=\'200 OK\''.format(id(environ))))


    @log_capture()
    def test_request(self, l):
        self.log.request(self.conn, 'GET', '/test/stuff', [(b'Header', b'value')])
        if six.PY2:
            l.check(('test', 'DEBUG', 'http:{0}:client_request headers=[(\'Header\', \'value\')] method=u\'GET\' path=u\'/test/stuff\''.format(id(self.conn))))
        else:
            l.check(('test', 'DEBUG', 'http:{0}:client_request headers=[(b\'Header\', b\'value\')] method=\'GET\' path=\'/test/stuff\''.format(id(self.conn))))

    @log_capture()
    def test_response(self, l):
        self.log.response(self.conn, '200 OK', [(b'Header', b'value')])
        if six.PY2:
            l.check(('test', 'DEBUG', 'http:{0}:client_response headers=[(\'Header\', \'value\')] status=u\'200 OK\''.format(id(self.conn))))
        else:
            l.check(('test', 'DEBUG', 'http:{0}:client_response headers=[(b\'Header\', b\'value\')] status=\'200 OK\''.format(id(self.conn))))


# vim:et:fdm=marker:sts=4:sw=4:ts=4
