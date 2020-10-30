
import json

from mox3.mox import MoxTestBase, IsA
from six.moves import cPickle
import gevent

from boto.s3.bucket import Bucket
from boto.s3.key import Key
from boto.sqs.queue import Queue
from boto.sqs.message import Message

from slimta.envelope import Envelope
from slimta.cloudstorage.aws import SimpleStorageService, SimpleQueueService


class TestSimpleStorageService(MoxTestBase):

    def setUp(self):
        super(TestSimpleStorageService, self).setUp()
        self.bucket = self.mox.CreateMock(Bucket)
        self.key = self.mox.CreateMock(Key)
        self.s3 = SimpleStorageService(self.bucket, prefix='test-')
        self.s3.Key = self.mox.CreateMockAnything()
        self.env = Envelope('sender@example.com', ['rcpt@example.com'])
        self.pickled_env = cPickle.dumps(self.env, cPickle.HIGHEST_PROTOCOL)

    def test_write_message(self):
        self.s3.Key.__call__(self.bucket).AndReturn(self.key)
        self.key.set_metadata('timestamp', '1234.0')
        self.key.set_metadata('attempts', '')
        self.key.set_metadata('delivered_indexes', '')
        self.key.set_contents_from_string(self.pickled_env)
        self.mox.ReplayAll()
        self.s3.write_message(self.env, 1234.0)
        self.assertTrue(isinstance(self.key.key, str))
        self.assertTrue(self.key.key.startswith('test-'))

    def test_set_message_meta(self):
        self.bucket.get_key('storeid').AndReturn(self.key)
        self.key.set_metadata('timestamp', '5678.0')
        self.key.set_metadata('attempts', '3')
        self.mox.ReplayAll()
        self.s3.set_message_meta('storeid', 5678.0, 3)

    def test_delete_message(self):
        self.bucket.get_key('storeid').AndReturn(self.key)
        self.key.delete()
        self.mox.ReplayAll()
        self.s3.delete_message('storeid')

    def test_get_message(self):
        self.bucket.get_key('storeid').AndReturn(self.key)
        self.key.get_contents_as_string().AndReturn(self.pickled_env)
        self.key.get_metadata('timestamp').AndReturn('4321.0')
        self.key.get_metadata('attempts').AndReturn('5')
        self.key.get_metadata('delivered_indexes').AndReturn('')
        self.mox.ReplayAll()
        env, meta = self.s3.get_message('storeid')
        self.assertEqual('sender@example.com', env.sender)
        self.assertEqual(['rcpt@example.com'], env.recipients)
        self.assertEqual(4321.0, meta['timestamp'])
        self.assertEqual(5, meta['attempts'])
        self.assertFalse('delivered_indexes' in meta)

    def test_get_message_meta(self):
        self.bucket.get_key('storeid').AndReturn(self.key)
        self.key.get_metadata('timestamp').AndReturn('4321.0')
        self.key.get_metadata('attempts').AndReturn('5')
        self.key.get_metadata('delivered_indexes').AndReturn('[1, 2]')
        self.mox.ReplayAll()
        meta = self.s3.get_message_meta('storeid')
        self.assertEqual(4321.0, meta['timestamp'])
        self.assertEqual(5, meta['attempts'])
        self.assertEqual([1, 2], meta['delivered_indexes'])

    def test_list_messages(self):
        self.mox.StubOutWithMock(self.s3, 'get_message_meta')
        self.bucket.list('test-').AndReturn(['test-storeid1', 'test-storeid2'])
        self.s3.get_message_meta('test-storeid1').AndReturn((1234.0, 1))
        self.s3.get_message_meta('test-storeid2').AndReturn((5678.0, 2))
        self.mox.ReplayAll()
        ret = list(self.s3.list_messages())
        self.assertEqual([(1234.0, 'test-storeid1'), (5678.0, 'test-storeid2')], ret)


class TestSimpleQueueService(MoxTestBase):

    def setUp(self):
        super(TestSimpleQueueService, self).setUp()
        self.queue = self.mox.CreateMock(Queue)
        self.sqs = SimpleQueueService(self.queue)

    def test_queue_message(self):
        self.sqs.Message = self.mox.CreateMockAnything()
        msg = self.mox.CreateMock(Message)
        self.sqs.Message.__call__().AndReturn(msg)
        msg.set_body(json.dumps({'timestamp': 1234.0, 'storage_id': 'storeid'}))
        self.queue.write(msg).AndReturn(False)
        self.queue.write(msg).AndReturn(True)
        self.mox.ReplayAll()
        self.sqs.queue_message('storeid', 1234.0)

    def test_poll(self):
        msg1 = self.mox.CreateMock(Message)
        msg2 = self.mox.CreateMock(Message)
        self.queue.get_messages().AndReturn([msg1, msg2])
        msg1.get_body().AndReturn('{"timestamp": 1234.0, "storage_id": "storeid1"}')
        msg2.get_body().AndReturn('{"timestamp": 5678.0, "storage_id": "storeid2"}')
        self.mox.ReplayAll()
        ret = list(self.sqs.poll())
        self.assertEqual([(1234.0, 'storeid1', msg1), (5678.0, 'storeid2', msg2)], ret)

    def test_sleep(self):
        self.mox.StubOutWithMock(gevent, 'sleep')
        gevent.sleep(13.0)
        self.mox.ReplayAll()
        sqs = SimpleQueueService(None, poll_pause=13.0)
        sqs.sleep()

    def test_delete(self):
        msg = self.mox.CreateMock(Message)
        self.queue.delete_message(msg)
        self.mox.ReplayAll()
        self.sqs.delete(msg)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
