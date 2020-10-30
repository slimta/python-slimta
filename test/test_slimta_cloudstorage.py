
from mox3.mox import MoxTestBase, IsA

from slimta.queue import QueueError
from slimta.envelope import Envelope
from slimta.cloudstorage import CloudStorage, CloudStorageError


class TestCloudStorage(MoxTestBase):

    def setUp(self):
        super(TestCloudStorage, self).setUp()
        self.obj_store = self.mox.CreateMockAnything()
        self.msg_queue = self.mox.CreateMockAnything()

    def test_exception_inheritance(self):
        self.assertTrue(isinstance(CloudStorageError(), QueueError))

    def test_write(self):
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        self.obj_store.write_message(env, 1234.0).AndReturn('testid')
        self.msg_queue.queue_message('testid', 1234.0)
        self.mox.ReplayAll()
        storage = CloudStorage(self.obj_store, self.msg_queue)
        self.assertEqual('testid', storage.write(env, 1234.0))

    def test_write_msg_queue_exception(self):
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        self.obj_store.write_message(env, 1234.0).AndReturn('testid')
        self.msg_queue.queue_message('testid', 1234.0).AndRaise(Exception)
        self.mox.ReplayAll()
        storage = CloudStorage(self.obj_store, self.msg_queue)
        self.assertEqual('testid', storage.write(env, 1234.0))

    def test_write_no_msg_queue(self):
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        self.obj_store.write_message(env, 1234.0).AndReturn('testid')
        self.mox.ReplayAll()
        storage = CloudStorage(self.obj_store)
        self.assertEqual('testid', storage.write(env, 1234.0))

    def test_set_timestamp(self):
        self.obj_store.set_message_meta('testid', timestamp=1234.0)
        self.mox.ReplayAll()
        storage = CloudStorage(self.obj_store, self.msg_queue)
        storage.set_timestamp('testid', 1234.0)

    def test_increment_attempts(self):
        self.obj_store.get_message_meta('testid').AndReturn(
            {'attempts': 3})
        self.obj_store.set_message_meta('testid', attempts=4)
        self.mox.ReplayAll()
        storage = CloudStorage(self.obj_store, self.msg_queue)
        self.assertEqual(4, storage.increment_attempts('testid'))

    def test_load(self):
        self.obj_store.list_messages().AndReturn(['1', '2', '3'])
        self.mox.ReplayAll()
        storage = CloudStorage(self.obj_store, self.msg_queue)
        self.assertEqual(['1', '2', '3'], storage.load())

    def test_get(self):
        env = Envelope('sender@example.com', ['rcpt1@example.com',
                                              'rcpt2@example.com'])
        self.obj_store.get_message('testid').AndReturn(
            (env, {'attempts': 3,
                   'delivered_indexes': [0]}))
        self.mox.ReplayAll()
        storage = CloudStorage(self.obj_store, self.msg_queue)
        env, attempts = storage.get('testid')
        self.assertEqual('sender@example.com', env.sender)
        self.assertEqual(['rcpt2@example.com'], env.recipients)
        self.assertEqual(3, attempts)

    def test_remove(self):
        self.obj_store.delete_message('testid')
        self.mox.ReplayAll()
        storage = CloudStorage(self.obj_store, self.msg_queue)
        storage.remove('testid')

    def test_wait(self):
        self.msg_queue.poll().AndReturn([(1234.0, 'storeid1', 'msgid1'), (5678.0, 'storeid2', 'msgid2')])
        self.msg_queue.delete('msgid1')
        self.msg_queue.delete('msgid2')
        self.msg_queue.sleep()
        self.mox.ReplayAll()
        storage = CloudStorage(self.obj_store, self.msg_queue)
        self.assertEqual([(1234.0, 'storeid1'), (5678.0, 'storeid2')], list(storage.wait()))

    def test_wait_no_msg_queue(self):
        self.mox.ReplayAll()
        storage = CloudStorage(self.obj_store)
        self.assertRaises(NotImplementedError, list, storage.wait())


# vim:et:fdm=marker:sts=4:sw=4:ts=4
