import time

import unittest2 as unittest
from mox3.mox import MoxTestBase

from slimta.edge import Edge, EdgeServer


class TestEdge(unittest.TestCase, MoxTestBase):

    def test_handoff(self):
        self.mox.StubOutWithMock(time, 'time')
        env = self.mox.CreateMockAnything()
        queue = self.mox.CreateMockAnything()
        time.time().AndReturn(12345)
        queue.enqueue(env).AndReturn('asdf')
        self.mox.ReplayAll()
        edge = Edge(queue, 'test.example.com')
        self.assertEqual('asdf', edge.handoff(env))
        self.assertEqual('test.example.com', env.receiver)
        self.assertEqual(12345, env.timestamp)

    def test_handoff_error(self):
        env = self.mox.CreateMockAnything()
        queue = self.mox.CreateMockAnything()
        queue.enqueue(env).AndRaise(RuntimeError)
        self.mox.ReplayAll()
        edge = Edge(queue)
        with self.assertRaises(RuntimeError):
            edge.handoff(env)

    def test_kill(self):
        queue = self.mox.CreateMockAnything()
        self.mox.ReplayAll()
        edge = Edge(queue)
        edge.kill()


class TestEdgeServer(unittest.TestCase, MoxTestBase):

    def test_edge_interface(self):
        edge = EdgeServer(('127.0.0.1', 0), None)
        with self.assertRaises(NotImplementedError):
            edge.handle(None, None)

    def test_handle(self):
        queue = self.mox.CreateMockAnything()
        sock = self.mox.CreateMockAnything()
        edge = EdgeServer(('127.0.0.1', 0), queue)
        self.mox.StubOutWithMock(edge, 'handle')
        sock.fileno().AndReturn(15)
        edge.handle(sock, 'test address')
        self.mox.ReplayAll()
        try:
            edge.server.pre_start()
        except AttributeError:
            edge.server.init_socket()
        edge._handle(sock, 'test address')

    def test_handle_error(self):
        queue = self.mox.CreateMockAnything()
        sock = self.mox.CreateMockAnything()
        edge = EdgeServer(('127.0.0.1', 0), queue)
        self.mox.StubOutWithMock(edge, 'handle')
        sock.fileno().AndReturn(15)
        edge.handle(sock, 5).AndRaise(RuntimeError)
        self.mox.ReplayAll()
        try:
            edge.server.pre_start()
        except AttributeError:
            edge.server.init_socket()
        with self.assertRaises(RuntimeError):
            edge._handle(sock, 5)

    def test_kill(self):
        edge = EdgeServer(('127.0.0.1', 0), None)
        self.mox.StubOutWithMock(edge.server, 'stop')
        edge.server.stop()
        self.mox.ReplayAll()
        edge.kill()

    def test_run(self):
        edge = EdgeServer(('127.0.0.1', 0), None)
        self.mox.StubOutWithMock(edge.server, 'start')
        self.mox.StubOutWithMock(edge.server, 'serve_forever')
        edge.server.start()
        edge.server.serve_forever()
        self.mox.ReplayAll()
        edge._run()


# vim:et:fdm=marker:sts=4:sw=4:ts=4
