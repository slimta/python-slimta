
import unittest2 as unittest

from mox import MoxTestBase, IsA
from gevent.lock import Semaphore

from slimta.util.deque import BlockingDeque


class TestBlockingDeque(unittest.TestCase, MoxTestBase):

    def setUp(self):
        super(TestBlockingDeque, self).setUp()
        self.deque = BlockingDeque()
        self.deque.sema = self.mox.CreateMock(Semaphore)

    def test_append(self):
        self.deque.sema.release()
        self.mox.ReplayAll()
        self.deque.append(True)

    def test_appendleft(self):
        self.deque.sema.release()
        self.mox.ReplayAll()
        self.deque.appendleft(True)

    def test_clear(self):
        for i in range(3):
            self.deque.sema.release()
        for i in range(3):
            self.deque.sema.locked().AndReturn(False)
            self.deque.sema.acquire(blocking=False)
        self.deque.sema.locked().AndReturn(True)
        self.mox.ReplayAll()
        self.deque.append(True)
        self.deque.append(True)
        self.deque.append(True)
        self.deque.clear()

    def test_extend(self):
        self.deque.sema.release()
        self.deque.sema.release()
        self.deque.sema.release()
        self.mox.ReplayAll()
        self.deque.extend([1, 2, 3])

    def test_extendleft(self):
        self.deque.sema.release()
        self.deque.sema.release()
        self.deque.sema.release()
        self.mox.ReplayAll()
        self.deque.extendleft([1, 2, 3])

    def test_pop(self):
        self.deque.sema.release()
        self.deque.sema.release()
        self.deque.sema.acquire()
        self.mox.ReplayAll()
        self.deque.append(4)
        self.deque.append(5)
        self.assertEqual(5, self.deque.pop())

    def test_popleft(self):
        self.deque.sema.release()
        self.deque.sema.release()
        self.deque.sema.acquire()
        self.mox.ReplayAll()
        self.deque.append(4)
        self.deque.append(5)
        self.assertEqual(4, self.deque.popleft())

    def test_remove(self):
        self.deque.sema.release()
        self.deque.sema.release()
        self.deque.sema.acquire()
        self.mox.ReplayAll()
        self.deque.append(4)
        self.deque.append(5)
        self.deque.remove(4)

    def test_remove_notfound(self):
        self.deque.sema.release()
        self.deque.sema.release()
        self.mox.ReplayAll()
        self.deque.append(4)
        self.deque.append(5)
        with self.assertRaises(ValueError):
            self.deque.remove(6)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
