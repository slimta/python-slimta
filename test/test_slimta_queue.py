
import unittest

from mox import MoxTestBase, IsA
import gevent
from gevent.pool import Pool

from slimta.queue import Queue, QueueStorage
from slimta.smtp.reply import Reply
from slimta.relay import Relay, TransientRelayError, PermanentRelayError
from slimta.policy import Policy
from slimta.envelope import Envelope


class TestQueue(MoxTestBase):

    def setUp(self):
        super(TestQueue, self).setUp()
        self.relay = self.mox.CreateMock(Relay)
        self.store = self.mox.CreateMock(QueueStorage)
        self.env = Envelope('sender@example.com', ['rcpt@example.com'])

    def test_prequeue_policies(self):
        p1 = self.mox.CreateMock(Policy)
        p2 = self.mox.CreateMock(Policy)
        p1.apply(self.env)
        p2.apply(self.env)
        self.mox.ReplayAll()
        queue = Queue(self.store, self.relay)
        queue.add_prequeue_policy(p1)
        queue.add_prequeue_policy(p2)
        queue._run_prequeue_policies(self.env)

    def test_postqueue_policies(self):
        p1 = self.mox.CreateMock(Policy)
        p2 = self.mox.CreateMock(Policy)
        p2.apply(self.env)
        p1.apply(self.env)
        self.mox.ReplayAll()
        queue = Queue(self.store, self.relay)
        queue.add_postqueue_policy(p2)
        queue.add_postqueue_policy(p1)
        queue._run_postqueue_policies(self.env)

    def test_add_queued(self):
        queue = Queue(self.store, self.relay)
        queue._add_queued((10, 'one'))
        queue._add_queued((5, 'two'))
        queue._add_queued((7, 'three'))
        self.assertEqual([(5, 'two'), (7, 'three'), (10, 'one')], queue.queued)
        self.assertTrue(queue.wake.isSet())

    def test_load_all(self):
        self.store.load().AndReturn([(3, 'one'), (5, 'two'), (1, 'three')])
        self.mox.ReplayAll()
        queue = Queue(self.store, self.relay)
        queue._load_all()
        self.assertEqual([(1, 'three'), (3, 'one'), (5, 'two')], queue.queued)
        self.assertTrue(queue.wake.isSet())

    def test_load_all_empty(self):
        self.store.load().AndReturn([])
        self.mox.ReplayAll()
        queue = Queue(self.store, self.relay)
        queue._load_all()
        self.assertEqual([], queue.queued)
        self.assertFalse(queue.wake.isSet())

    def test_enqueue_wait(self):
        self.store.write(self.env, IsA(float)).AndReturn('1234')
        self.relay.attempt(self.env, 0)
        self.store.remove('1234')
        self.mox.ReplayAll()
        queue = Queue(self.store, self.relay, relay_pool=5)
        queue.enqueue(self.env)
        queue.relay_pool.join()

    def test_enqueue_wait_transientfail(self):
        self.store.write(self.env, IsA(float)).AndReturn('1234')
        self.relay.attempt(self.env, 0).AndRaise(TransientRelayError('transient', Reply('450', 'transient')))
        self.store.increment_attempts('1234')
        self.store.set_timestamp('1234', IsA(float))
        self.mox.ReplayAll()
        def backoff(envelope, attempts):
            return 0
        queue = Queue(self.store, self.relay, backoff=backoff, relay_pool=5)
        queue.enqueue(self.env)
        queue.relay_pool.join()

    def test_enqueue_wait_transientfail_noretry(self):
        self.store.write(self.env, IsA(float)).AndReturn('1234')
        self.relay.attempt(self.env, 0).AndRaise(TransientRelayError('transient', Reply('450', 'transient')))
        self.store.increment_attempts('1234')
        self.store.remove('1234')
        self.mox.ReplayAll()
        def no_bounce(envelope, reply):
            return None
        queue = Queue(self.store, self.relay, bounce_factory=no_bounce, relay_pool=5)
        queue.enqueue(self.env)
        queue.relay_pool.join()

    def test_enqueue_wait_permanentfail(self):
        self.store.write(self.env, IsA(float)).AndReturn('1234')
        self.relay.attempt(self.env, 0).AndRaise(PermanentRelayError('permanent', Reply('550', 'permanent')))
        self.store.remove('1234')
        self.mox.ReplayAll()
        def no_bounce(envelope, reply):
            return None
        queue = Queue(self.store, self.relay, bounce_factory=no_bounce, relay_pool=5)
        queue.enqueue(self.env)
        queue.relay_pool.join()

    def test_check_ready(self):
        self.store.get('1234').AndReturn((self.env, 0))
        self.relay.attempt(self.env, 0)
        self.store.remove('1234')
        self.mox.ReplayAll()
        queue = Queue(self.store, self.relay, store_pool=Pool(5))
        queue._add_queued((10, '1234'))
        queue._check_ready(20)
        queue.store_pool.join()

    def test_check_ready_empty(self):
        self.mox.ReplayAll()
        queue = Queue(self.store, self.relay, store_pool=5)
        queue._add_queued((20, '1234'))
        queue._check_ready(10)
        queue.store_pool.join()

    def test_wait_ready_nonequeued(self):
        queue = Queue(self.store, self.relay)
        def wait_func():
            queue._wait_ready(20)
        thread = gevent.spawn(wait_func)
        gevent.sleep(0)
        self.assertFalse(thread.ready())
        queue._add_queued((10, '1234'))
        gevent.sleep(0)
        self.assertTrue(thread.ready())

    def test_wait_ready_noneready(self):
        queue = Queue(self.store, self.relay)
        queue._add_queued((20, '1234'))
        queue.wake.clear()
        def wait_func():
            queue._wait_ready(10)
        thread = gevent.spawn(wait_func)
        gevent.sleep(0)
        self.assertFalse(thread.ready())
        queue._add_queued((5, '1234'))
        gevent.sleep(0)
        self.assertTrue(thread.ready())

    def test_wait_ready_nowait(self):
        queue = Queue(self.store, self.relay)
        queue._add_queued((10, '1234'))
        with gevent.Timeout(1.0):
            queue._wait_ready(20)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
