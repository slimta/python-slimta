
import re

from mox3.mox import MoxTestBase, IsA, Func
from six.moves import cPickle

from slimta.envelope import Envelope
from slimta.cloudstorage.rackspace import RackspaceCloudAuth, \
        RackspaceCloudFiles


def _is_files_path(path):
    match = re.match('^/v1/test/[a-f0-9]{8}-?[a-f0-9]{4}-?4[a-f0-9]{3}-?[89ab][a-f0-9]{3}-?[a-f0-9]{12}$', path)
    return match


class TestRackspaceCloudFiles(MoxTestBase):

    def setUp(self):
        super(TestRackspaceCloudFiles, self).setUp()
        self.auth = self.mox.CreateMock(RackspaceCloudAuth)
        self.auth.token_id = 'tokenid'
        self.auth.files_endpoint = 'http://files/v1'
        self.env = Envelope('sender@example.com', ['rcpt@example.com'])
        self.pickled_env = cPickle.dumps(self.env, cPickle.HIGHEST_PROTOCOL)

    def test_write_message(self):
        files = RackspaceCloudFiles(self.auth, container='test')
        conn = self.mox.CreateMockAnything()
        res = self.mox.CreateMockAnything()
        self.mox.StubOutWithMock(files, 'get_connection')
        files.get_connection(IsA(tuple), {}).AndReturn(conn)
        conn.putrequest('PUT', Func(_is_files_path))
        conn.putheader('Host', 'files')
        conn.putheader('Content-Type', 'application/octet-stream')
        conn.putheader('Content-Length', str(len(self.pickled_env)))
        conn.putheader('X-Object-Meta-Timestamp', '1234.0')
        conn.putheader('X-Auth-Token', 'tokenid')
        conn.endheaders(self.pickled_env)
        conn.getresponse().AndReturn(res)
        res.status = 201
        res.reason = 'Created'
        res.getheaders().AndReturn([])
        self.mox.ReplayAll()
        self.assertTrue(files.write_message(self.env, 1234.0))

    def test_set_message_meta(self):
        files = RackspaceCloudFiles(self.auth, container='test')
        conn = self.mox.CreateMockAnything()
        res = self.mox.CreateMockAnything()
        self.mox.StubOutWithMock(files, 'get_connection')
        files.get_connection(IsA(tuple), {}).AndReturn(conn)
        conn.putrequest('POST', '/v1/test/4321')
        conn.putheader('Host', 'files')
        conn.putheader('X-Auth-Token', 'tokenid')
        conn.putheader('X-Object-Meta-Timestamp', '1234.0')
        conn.putheader('X-Object-Meta-Attempts', '3')
        conn.endheaders()
        conn.getresponse().AndReturn(res)
        res.status = 202
        res.reason = 'Accepted'
        res.getheaders().AndReturn([])
        self.mox.ReplayAll()
        files.set_message_meta('4321', 1234.0, 3)

    def test_delete_message(self):
        files = RackspaceCloudFiles(self.auth, container='test')
        conn = self.mox.CreateMockAnything()
        res = self.mox.CreateMockAnything()
        self.mox.StubOutWithMock(files, 'get_connection')
        files.get_connection(IsA(tuple), {}).AndReturn(conn)
        conn.putrequest('DELETE', '/v1/test/4321')
        conn.putheader('Host', 'files')
        conn.putheader('X-Auth-Token', 'tokenid')
        conn.endheaders()
        conn.getresponse().AndReturn(res)
        res.status = 204
        res.reason = 'No Content'
        res.getheaders().AndReturn([])
        self.mox.ReplayAll()
        files.delete_message('4321')

    def test_get_message(self):
        files = RackspaceCloudFiles(self.auth, container='test')
        conn = self.mox.CreateMockAnything()
        res = self.mox.CreateMockAnything()
        self.mox.StubOutWithMock(files, 'get_connection')
        files.get_connection(IsA(tuple), {}).AndReturn(conn)
        conn.putrequest('GET', '/v1/test/4321')
        conn.putheader('Host', 'files')
        conn.putheader('X-Auth-Token', 'tokenid')
        conn.endheaders()
        conn.getresponse().AndReturn(res)
        res.status = 200
        res.reason = 'OK'
        res.getheaders().AndReturn([])
        res.read().AndReturn(self.pickled_env)
        res.getheader('X-Object-Meta-Timestamp').AndReturn('1234.0')
        res.getheader('X-Object-Meta-Attempts', None).AndReturn('3')
        res.getheader('X-Object-Meta-Delivered-Rcpts', None).AndReturn('[1, 2]')
        self.mox.ReplayAll()
        env, meta = files.get_message('4321')
        self.assertTrue(isinstance(env, Envelope))
        self.assertEqual('sender@example.com', env.sender)
        self.assertEqual(['rcpt@example.com'], env.recipients)
        self.assertEqual(1234.0, meta['timestamp'])
        self.assertEqual(3, meta['attempts'])
        self.assertEqual([1, 2], meta['delivered_indexes'])

    def test_get_message_meta(self):
        files = RackspaceCloudFiles(self.auth, container='test')
        conn = self.mox.CreateMockAnything()
        res = self.mox.CreateMockAnything()
        self.mox.StubOutWithMock(files, 'get_connection')
        files.get_connection(IsA(tuple), {}).AndReturn(conn)
        conn.putrequest('HEAD', '/v1/test/4321')
        conn.putheader('Host', 'files')
        conn.putheader('X-Auth-Token', 'tokenid')
        conn.endheaders()
        conn.getresponse().AndReturn(res)
        res.status = 200
        res.reason = 'OK'
        res.getheaders().AndReturn([])
        res.getheader('X-Object-Meta-Timestamp').AndReturn('1234.0')
        res.getheader('X-Object-Meta-Attempts', None).AndReturn('3')
        res.getheader('X-Object-Meta-Delivered-Rcpts', None).AndReturn(None)
        self.mox.ReplayAll()
        meta = files.get_message_meta('4321')
        self.assertEqual(1234.0, meta['timestamp'])
        self.assertEqual(3, meta['attempts'])
        self.assertFalse('delivered_indexes' in meta)

    def test_list_messages_page(self):
        files = RackspaceCloudFiles(self.auth, container='test', prefix='test-')
        conn = self.mox.CreateMockAnything()
        res = self.mox.CreateMockAnything()
        self.mox.StubOutWithMock(files, 'get_connection')
        files.get_connection(IsA(tuple), {}).AndReturn(conn)
        conn.putrequest('GET', '/v1/test?limit=1000&marker=marker')
        conn.putheader('Host', 'files')
        conn.putheader('X-Auth-Token', 'tokenid')
        conn.endheaders()
        conn.getresponse().AndReturn(res)
        res.status = 200
        res.reason = 'OK'
        res.getheaders().AndReturn([])
        res.read().AndReturn('test-one\ntest-two\ntest-three\nfour')
        self.mox.ReplayAll()
        lines, marker = files._list_messages_page('marker')
        self.assertEqual(['test-one', 'test-two', 'test-three'], lines)

    def test_list_messages(self):
        files = RackspaceCloudFiles(self.auth, container='test')
        self.mox.StubOutWithMock(files, '_list_messages_page')
        self.mox.StubOutWithMock(files, 'get_message_meta')
        files._list_messages_page(None).AndReturn((['one', 'two'], 'two'))
        files._list_messages_page('two').AndReturn(([], None))
        files.get_message_meta('one').AndReturn((1234.0, 0))
        files.get_message_meta('two').AndReturn((5678.0, 0))
        self.mox.ReplayAll()
        results = list(files.list_messages())
        self.assertEqual([(1234.0, 'one'), (5678.0, 'two')], results)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
