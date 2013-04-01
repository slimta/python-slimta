
import unittest

from mox import MoxTestBase, IsA, IgnoreArg
from celery import Celery

from slimta.celeryqueue import CeleryQueue
from slimta.relay import Relay, TransientRelayError, PermanentRelayError
from slimta.policy import QueuePolicy
from slimta.envelope import Envelope
from slimta.smtp.reply import Reply


class TestCeleryQueue(MoxTestBase):

    def setUp(self):
        super(TestCeleryQueue, self).setUp()
        self.relay = self.mox.CreateMock(Relay)
        self.celery = self.mox.CreateMock(Celery)
        self.env = Envelope('sender@example.com', ['rcpt@example.com'])
        self.bounce = Envelope('', ['sender@example.com'])

    def test_policies(self):
        self.celery.task(IgnoreArg())
        p1 = self.mox.CreateMock(QueuePolicy)
        p2 = self.mox.CreateMock(QueuePolicy)
        p1.apply(self.env)
        p2.apply(self.env)
        self.mox.ReplayAll()
        queue = CeleryQueue(self.celery, self.relay)
        queue.add_policy(p1)
        queue.add_policy(p2)
        self.assertRaises(TypeError, queue.add_policy, None)
        queue._run_policies(self.env)

    def test_flush_notimplemented(self):
        self.celery.task(IgnoreArg())
        self.mox.ReplayAll()
        queue = CeleryQueue(self.celery, self.relay)
        with self.assertRaises(NotImplementedError):
            queue.flush()

    def test_enqueue(self):
        task = self.mox.CreateMockAnything()
        subtask = self.mox.CreateMockAnything()
        result = self.mox.CreateMockAnything()
        result.id = '12345'
        self.celery.task(IgnoreArg()).AndReturn(task)
        task.s(self.env, 0).AndReturn(subtask)
        subtask.apply_async().AndReturn(result)
        self.mox.ReplayAll()
        queue = CeleryQueue(self.celery, self.relay)
        self.assertEqual([(self.env, '12345')], queue.enqueue(self.env))

    def test_attempt_delivery(self):
        self.celery.task(IgnoreArg())
        self.relay.attempt(self.env, 0)
        self.mox.ReplayAll()
        queue = CeleryQueue(self.celery, self.relay)
        queue.attempt_delivery(self.env, 0)

    def test_attempt_delivery_suffix(self):
        task_func = self.mox.CreateMockAnything()
        self.celery.task(name='attempt_delivery_test').AndReturn(task_func)
        task_func.__call__(IgnoreArg())
        self.relay.attempt(self.env, 0)
        self.mox.ReplayAll()
        queue = CeleryQueue(self.celery, self.relay, 'test')
        queue.attempt_delivery(self.env, 0)

    def test_attempt_delivery_transientrelayerror(self):
        task = self.mox.CreateMockAnything()
        subtask = self.mox.CreateMockAnything()
        result = self.mox.CreateMockAnything()
        result.id = '12345'
        self.relay.attempt(self.env, 0).AndRaise(TransientRelayError('transient', Reply('450', 'transient error')))
        self.celery.task(IgnoreArg()).AndReturn(task)
        task.s(self.env, 1).AndReturn(subtask)
        subtask.set(countdown=60)
        subtask.apply_async().AndReturn(result)
        self.mox.ReplayAll()
        def backoff(envelope, attempts):
            self.assertEqual(self.env, envelope)
            self.assertEqual(1, attempts)
            return 60
        queue = CeleryQueue(self.celery, self.relay, backoff=backoff)
        queue.attempt_delivery(self.env, 0)

    def test_attempt_delivery_permanentrelayerror(self):
        task = self.mox.CreateMockAnything()
        subtask = self.mox.CreateMockAnything()
        result = self.mox.CreateMockAnything()
        result.id = '12345'
        self.relay.attempt(self.env, 0).AndRaise(PermanentRelayError('permanent', Reply('550', 'permanent error')))
        self.celery.task(IgnoreArg()).AndReturn(task)
        task.s(self.bounce, 0).AndReturn(subtask)
        subtask.apply_async().AndReturn(result)
        self.mox.ReplayAll()
        def return_bounce(envelope, reply):
            self.assertEqual(self.env, envelope)
            return self.bounce
        queue = CeleryQueue(self.celery, self.relay, bounce_factory=return_bounce)
        queue.attempt_delivery(self.env, 0)

    def test_attempt_delivery_transientrelayerror_no_retry(self):
        task = self.mox.CreateMockAnything()
        subtask = self.mox.CreateMockAnything()
        result = self.mox.CreateMockAnything()
        result.id = '12345'
        self.relay.attempt(self.env, 0).AndRaise(TransientRelayError('transient', Reply('450', 'transient error')))
        self.celery.task(IgnoreArg()).AndReturn(task)
        task.s(self.bounce, 0).AndReturn(subtask)
        subtask.apply_async().AndReturn(result)
        self.mox.ReplayAll()
        def return_bounce(envelope, reply):
            self.assertEqual(self.env, envelope)
            return self.bounce
        def no_retry(envelope, attempts):
            self.assertEqual(self.env, envelope)
            self.assertEqual(1, attempts)
            return None
        queue = CeleryQueue(self.celery, self.relay, backoff=no_retry, bounce_factory=return_bounce)
        queue.attempt_delivery(self.env, 0)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
