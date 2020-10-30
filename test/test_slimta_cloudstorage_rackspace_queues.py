
import json

import gevent
from mox3.mox import MoxTestBase, IsA, Func

from slimta.cloudstorage.rackspace import RackspaceCloudAuth, \
        RackspaceCloudQueues


class TestRackspaceCloudQueues(MoxTestBase):

    def setUp(self):
        super(TestRackspaceCloudQueues, self).setUp()
        self.auth = self.mox.CreateMock(RackspaceCloudAuth)
        self.auth.token_id = 'tokenid'
        self.auth.queues_endpoint = 'http://queues/v1'

    def test_queue_message(self):
        queues = RackspaceCloudQueues(self.auth, queue_name='test', client_id='test')
        conn = self.mox.CreateMockAnything()
        res = self.mox.CreateMockAnything()
        self.mox.StubOutWithMock(queues, 'get_connection')
        queues.get_connection(IsA(tuple), {}).AndReturn(conn)
        json_payload = json.dumps([{'ttl': 86400, 'body': {'timestamp': 1234.0, 'storage_id': 'asdf'}}], sort_keys=True)
        conn.putrequest('POST', '/v1/queues/test/messages')
        conn.putheader('Host', 'queues')
        conn.putheader('Client-ID', 'test')
        conn.putheader('Content-Type', 'application/json')
        conn.putheader('Content-Length', str(len(json_payload)))
        conn.putheader('Accept', 'application/json')
        conn.putheader('X-Auth-Token', 'tokenid')
        conn.endheaders(json_payload)
        conn.getresponse().AndReturn(res)
        res.status = 201
        res.reason = 'Created'
        res.getheaders().AndReturn([])
        self.mox.ReplayAll()
        queues.queue_message('asdf', 1234.0)

    def test_poll(self):
        queues = RackspaceCloudQueues(self.auth, queue_name='test', client_id='test')
        conn = self.mox.CreateMockAnything()
        res = self.mox.CreateMockAnything()
        self.mox.StubOutWithMock(queues, 'get_connection')
        queues.get_connection(IsA(tuple), {}).AndReturn(conn)
        json_payload = '{"ttl": 3600, "grace": 3600}'
        conn.putrequest('POST', '/v1/queues/test/claims')
        conn.putheader('Host', 'queues')
        conn.putheader('Client-ID', 'test')
        conn.putheader('Content-Type', 'application/json')
        conn.putheader('Content-Length', str(len(json_payload)))
        conn.putheader('Accept', 'application/json')
        conn.putheader('X-Auth-Token', 'tokenid')
        conn.endheaders(json_payload)
        conn.getresponse().AndReturn(res)
        res.status = 201
        res.reason = 'Created'
        res.getheaders().AndReturn([])
        res.read().AndReturn("""[{"body": {"timestamp": 1234.0, "storage_id": "storeid1"}, "href": "msgid1"},
            {"body": {"timestamp": 5678.0, "storage_id": "storeid2"}, "href": "msgid2"}]""")
        self.mox.ReplayAll()
        results = list(queues.poll())
        self.assertEqual([(1234.0, 'storeid1', 'msgid1'), (5678.0, 'storeid2', 'msgid2')], results)

    def test_sleep(self):
        queues = RackspaceCloudQueues(self.auth, poll_pause=1337.0)
        self.mox.StubOutWithMock(gevent, 'sleep')
        gevent.sleep(1337.0)
        self.mox.ReplayAll()
        queues.sleep()

    def test_delete(self):
        queues = RackspaceCloudQueues(self.auth, client_id='test')
        conn = self.mox.CreateMockAnything()
        res = self.mox.CreateMockAnything()
        self.mox.StubOutWithMock(queues, 'get_connection')
        queues.get_connection(IsA(tuple), {}).AndReturn(conn)
        conn.putrequest('DELETE', '/path/to/msg')
        conn.putheader('Host', 'queues')
        conn.putheader('Client-ID', 'test')
        conn.putheader('Content-Type', 'application/json')
        conn.putheader('Accept', 'application/json')
        conn.putheader('X-Auth-Token', 'tokenid')
        conn.endheaders()
        conn.getresponse().AndReturn(res)
        res.status = 204
        res.reason = 'No Content'
        res.getheaders().AndReturn([])
        self.mox.ReplayAll()
        queues.delete('/path/to/msg')


# vim:et:fdm=marker:sts=4:sw=4:ts=4
