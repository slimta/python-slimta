import sys
from functools import wraps

import unittest2 as unittest
from mox3.mox import MoxTestBase, IsA
import gevent
from gevent.pool import Pool
from gevent.event import AsyncResult

from slimta.queue import Queue, QueueStorage
from slimta.smtp.reply import Reply
from slimta.relay import Relay, TransientRelayError, PermanentRelayError
from slimta.policy import QueuePolicy
from slimta.envelope import Envelope


def _redirect_stderr(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        print('NOTE: stderr is redirected to stdout for this test.')
        old_stderr = sys.stderr
        sys.stderr = sys.stdout
        try:
            return f(*args, **kwargs)
        finally:
            sys.stderr = old_stderr
    return wrapper


class TestQueue(unittest.TestCase, MoxTestBase):

    def setUp(self):
        super(TestQueue, self).setUp()
        self.relay = self.mox.CreateMock(Relay)
        self.store = self.mox.CreateMock(QueueStorage)
        self.env = Envelope('sender@example.com', ['rcpt@example.com'])

    def test_queuestorage_interface(self):
        qs = QueueStorage()
        self.assertRaises(NotImplementedError, qs.write, self.env, 1234567890)
        self.assertRaises(NotImplementedError, qs.set_timestamp, '1234', 1234567890)
        self.assertRaises(NotImplementedError, qs.increment_attempts, '1234')
        self.assertRaises(NotImplementedError, qs.set_recipients_delivered, '1234', [])
        self.assertRaises(NotImplementedError, qs.load)
        self.assertRaises(NotImplementedError, qs.get, '1234')
        self.assertRaises(NotImplementedError, qs.remove, '1234')
        self.assertRaises(NotImplementedError, qs.wait)
        self.assertRaises(NotImplementedError, qs.get_info)

    def test_policies(self):
        p1 = self.mox.CreateMock(QueuePolicy)
        p2 = self.mox.CreateMock(QueuePolicy)
        p1.apply(self.env)
        p2.apply(self.env)
        self.mox.ReplayAll()
        queue = Queue(self.store, self.relay)
        queue.add_policy(p1)
        queue.add_policy(p2)
        self.assertRaises(TypeError, queue.add_policy, None)
        queue._run_policies(self.env)

    def test_add_queued(self):
        queue = Queue(self.store, self.relay)
        queue._add_queued((10, 'one'))
        queue._add_queued((5, 'two'))
        queue._add_queued((99, 'one'))
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
        self.relay._attempt(self.env, 0)
        self.store.remove('1234')
        self.mox.ReplayAll()
        queue = Queue(self.store, self.relay, relay_pool=5)
        self.assertEqual([(self.env, '1234')], queue.enqueue(self.env))
        queue.relay_pool.join()

    def test_enqueue_wait_norelay(self):
        self.store.write(self.env, IsA(float)).AndReturn('1234')
        self.mox.ReplayAll()
        queue = Queue(self.store, relay_pool=5)
        self.assertEqual([(self.env, '1234')], queue.enqueue(self.env))
        queue.relay_pool.join()

    def test_enqueue_wait_splitpolicy(self):
        splitpolicy1 = self.mox.CreateMock(QueuePolicy)
        splitpolicy2 = self.mox.CreateMock(QueuePolicy)
        regpolicy = self.mox.CreateMock(QueuePolicy)
        env1 = Envelope('sender1@example.com', ['rcpt1@example.com'])
        env2 = Envelope('sender2@example.com', ['rcpt2@example.com'])
        env3 = Envelope('sender3@example.com', ['rcpt3@example.com'])
        splitpolicy1.apply(self.env).AndReturn([env1, env2])
        regpolicy.apply(env1)
        splitpolicy2.apply(env1)
        regpolicy.apply(env2)
        splitpolicy2.apply(env2).AndReturn([env2, env3])
        self.store.write(env1, IsA(float)).AndReturn('1234')
        self.store.write(env2, IsA(float)).AndReturn('5678')
        self.store.write(env3, IsA(float)).AndReturn('90AB')
        self.relay._attempt(env1, 0).InAnyOrder('relay')
        self.relay._attempt(env2, 0).InAnyOrder('relay')
        self.relay._attempt(env3, 0).InAnyOrder('relay')
        self.store.remove('1234').InAnyOrder('relay')
        self.store.remove('5678').InAnyOrder('relay')
        self.store.remove('90AB').InAnyOrder('relay')
        self.mox.ReplayAll()
        queue = Queue(self.store, self.relay, relay_pool=5)
        queue.add_policy(splitpolicy1)
        queue.add_policy(regpolicy)
        queue.add_policy(splitpolicy2)
        self.assertEqual([(env1, '1234'), (env2, '5678'), (env3, '90AB')],
                         queue.enqueue(self.env))
        queue.relay_pool.join()

    def test_enqueue_randomfail(self):
        self.store.write(self.env, IsA(float)).AndRaise(gevent.GreenletExit)
        self.mox.ReplayAll()
        queue = Queue(self.store, self.relay, relay_pool=5)
        self.assertRaises(gevent.GreenletExit, queue.enqueue, self.env)

    def test_enqueue_wait_transientfail(self):
        self.store.write(self.env, IsA(float)).AndReturn('1234')
        self.relay._attempt(self.env, 0).AndRaise(TransientRelayError('transient', Reply('450', 'transient')))
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
        self.relay._attempt(self.env, 0).AndRaise(TransientRelayError('transient', Reply('450', 'transient')))
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
        self.relay._attempt(self.env, 0).AndRaise(PermanentRelayError('permanent', Reply('550', 'permanent')))
        self.store.remove('1234')
        self.mox.ReplayAll()
        def no_bounce(envelope, reply):
            return None
        queue = Queue(self.store, self.relay, bounce_factory=no_bounce, relay_pool=5)
        queue.enqueue(self.env)
        queue.relay_pool.join()

    @_redirect_stderr
    def test_enqueue_wait_unhandledfail(self):
        self.store.write(self.env, IsA(float)).AndReturn('1234')
        self.relay._attempt(self.env, 0).AndRaise(Exception('unhandled error'))
        self.store.increment_attempts('1234')
        self.store.set_timestamp('1234', IsA(float))
        self.mox.ReplayAll()
        def backoff(envelope, attempts):
            return 0
        queue = Queue(self.store, self.relay, backoff=backoff, relay_pool=5)
        queue.enqueue(self.env)
        queue.relay_pool.join()

    def test_enqueue_wait_partial_relay(self):
        env = Envelope('sender@example.com', ['rcpt1@example.com',
                                              'rcpt2@example.com',
                                              'rcpt3@example.com'])
        self.store.write(env, IsA(float)).AndReturn('1234')
        self.relay._attempt(env, 0).AndReturn(
            {'rcpt1@example.com': None,
             'rcpt2@example.com': TransientRelayError('transient', Reply('450', 'transient')),
             'rcpt3@example.com': PermanentRelayError('permanent', Reply('550', 'permanent'))})
        self.store.increment_attempts('1234')
        self.store.set_timestamp('1234', IsA(float))
        self.store.set_recipients_delivered('1234', set([0, 2]))
        self.mox.ReplayAll()
        def backoff(envelope, attempts):
            return 0
        def no_bounce(envelope, reply):
            return None
        queue = Queue(self.store, self.relay, backoff=backoff, bounce_factory=no_bounce, relay_pool=5)
        queue.enqueue(env)
        queue.relay_pool.join()

    def test_enqueue_wait_partial_relay_expired(self):
        env = Envelope('sender@example.com', ['rcpt1@example.com',
                                              'rcpt2@example.com',
                                              'rcpt3@example.com'])
        bounce_mock = self.mox.CreateMockAnything()
        bounce_mock(IsA(Envelope), IsA(Reply)).AndReturn(None)
        bounce_mock(IsA(Envelope), IsA(Reply)).AndReturn(None)
        self.store.write(env, IsA(float)).AndReturn('1234')
        self.relay._attempt(env, 0).AndReturn(
            {'rcpt1@example.com': TransientRelayError('transient', Reply('450', 'transient 1')),
             'rcpt2@example.com': TransientRelayError('transient', Reply('450', 'transient 1')),
             'rcpt3@example.com': TransientRelayError('transient', Reply('450', 'transient 2'))})
        self.store.increment_attempts('1234')
        self.store.remove('1234')
        self.mox.ReplayAll()
        queue = Queue(self.store, self.relay, bounce_factory=bounce_mock, relay_pool=5)
        queue.enqueue(env)
        queue.relay_pool.join()

    def test_check_ready(self):
        self.store.get('1234').AndReturn((self.env, 0))
        self.relay._attempt(self.env, 0)
        self.store.remove('1234')
        self.mox.ReplayAll()
        queue = Queue(self.store, self.relay, store_pool=Pool(5))
        queue._add_queued((10, '1234'))
        queue._check_ready(20)
        queue.store_pool.join()

    def test_check_ready_missing(self):
        self.store.get('1234').AndRaise(KeyError)
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

    def test_wait_store(self):
        queue = Queue(self.store, self.relay, relay_pool=5)
        queue.wake = self.mox.CreateMock(AsyncResult)
        self.store.wait().AndReturn([(1234567890, '1234')])
        queue.wake.set()
        self.store.wait().AndReturn([])
        self.store.wait().AndReturn([(2345678901, '5678')])
        queue.wake.set()
        self.store.wait().AndRaise(NotImplementedError)
        self.mox.ReplayAll()
        queue._wait_store()

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
        queue._add_queued((5, '5678'))
        gevent.sleep(0)
        self.assertTrue(thread.ready())

    def test_wait_ready_nowait(self):
        queue = Queue(self.store, self.relay)
        queue._add_queued((10, '1234'))
        with gevent.Timeout(1.0):
            queue._wait_ready(20)

    def test_flush(self):
        self.store.get('three').AndReturn((self.env, 1))
        self.store.get('two').AndReturn((self.env, 2))
        self.store.get('one').AndReturn((self.env, 3))
        self.relay._attempt(self.env, 1)
        self.store.remove('three')
        self.relay._attempt(self.env, 2)
        self.store.remove('two')
        self.relay._attempt(self.env, 3)
        self.store.remove('one')
        self.mox.ReplayAll()
        queue = Queue(self.store, self.relay, store_pool=5, relay_pool=5)
        queue._add_queued((float('inf'), 'one'))
        queue._add_queued((0, 'two'))
        queue._add_queued((float('-inf'), 'three'))
        queue.flush()
        queue.store_pool.join()
        queue.relay_pool.join()

    def test_kill(self):
        self.mox.ReplayAll()
        queue = Queue(self.store, self.relay)
        self.assertFalse(queue.ready())
        queue.kill()
        self.assertTrue(queue.ready())


# vim:et:fdm=marker:sts=4:sw=4:ts=4
