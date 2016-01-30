import unittest2 as unittest

import gevent
from gevent import socket
from mox3.mox import MoxTestBase

from slimta.util.ptrlookup import PtrLookup


class TestPtrLookup(unittest.TestCase, MoxTestBase):

    def test_from_getpeername(self):
        sock = self.mox.CreateMockAnything()
        sock.getpeername().AndReturn(('127.0.0.1', 0))
        self.mox.ReplayAll()
        ptr, port = PtrLookup.from_getpeername(sock)
        self.assertEqual(0, port)
        self.assertIsInstance(ptr, PtrLookup)
        self.assertEqual('127.0.0.1', ptr.ip)

    def test_from_getsockname(self):
        sock = self.mox.CreateMockAnything()
        sock.getsockname().AndReturn(('127.0.0.1', 0))
        self.mox.ReplayAll()
        ptr, port = PtrLookup.from_getsockname(sock)
        self.assertEqual(0, port)
        self.assertIsInstance(ptr, PtrLookup)
        self.assertEqual('127.0.0.1', ptr.ip)

    def test_run_no_result(self):
        self.mox.StubOutWithMock(socket, 'gethostbyaddr')
        socket.gethostbyaddr('127.0.0.1').AndRaise(socket.herror)
        self.mox.ReplayAll()
        ptr = PtrLookup('127.0.0.1')
        self.assertIsInstance(ptr, gevent.Greenlet)
        self.assertIsNone(ptr._run())

    def test_run_bad_ip(self):
        self.mox.ReplayAll()
        ptr = PtrLookup('abcd')
        self.assertIsInstance(ptr, gevent.Greenlet)
        self.assertIsNone(ptr._run())

    def test_run_greenletexit(self):
        self.mox.StubOutWithMock(socket, 'gethostbyaddr')
        socket.gethostbyaddr('127.0.0.1').AndRaise(gevent.GreenletExit)
        self.mox.ReplayAll()
        ptr = PtrLookup('abcd')
        self.assertIsInstance(ptr, gevent.Greenlet)
        self.assertIsNone(ptr._run())

    def test_finish(self):
        self.mox.StubOutWithMock(socket, 'gethostbyaddr')
        socket.gethostbyaddr('127.0.0.1').AndReturn(
            ('example.com', None, None))
        self.mox.ReplayAll()
        ptr = PtrLookup('127.0.0.1')
        ptr.start()
        self.assertEqual('example.com', ptr.finish(runtime=1.0))

    def test_finish_timeout(self):
        def long_sleep(*args):
            gevent.sleep(1.0)

        self.mox.StubOutWithMock(socket, 'gethostbyaddr')
        socket.gethostbyaddr('127.0.0.1').WithSideEffects(long_sleep)
        self.mox.ReplayAll()
        ptr = PtrLookup('127.0.0.1')
        ptr.start()
        self.assertIsNone(ptr.finish(runtime=0.001))


# vim:et:fdm=marker:sts=4:sw=4:ts=4
