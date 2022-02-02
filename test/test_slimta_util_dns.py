
from mox import MoxTestBase, IgnoreArg

import pycares
import pycares.errno
import gevent
from gevent import select
from gevent.event import AsyncResult

from slimta.util.dns import DNSResolver, DNSError


class TestDNS(MoxTestBase):

    def test_get_query_type(self):
        self.assertEqual(pycares.QUERY_TYPE_MX,
                         DNSResolver._get_query_type('MX'))
        self.assertEqual(13, DNSResolver._get_query_type(13))

    def test_result_cb(self):
        result = AsyncResult()
        DNSResolver._result_cb(result, 13, None)
        self.assertEqual(13, result.get())

    def test_result_cb_error(self):
        result = AsyncResult()
        DNSResolver._result_cb(result, 13, pycares.errno.ARES_ENOTFOUND)
        with self.assertRaises(DNSError) as cm:
            result.get()
        self.assertEqual('Domain name not found [ARES_ENOTFOUND]',
                         str(cm.exception))

    def test_query(self):
        channel = self.mox.CreateMock(pycares.Channel)
        self.mox.StubOutWithMock(pycares, 'Channel')
        self.mox.StubOutWithMock(gevent, 'spawn')
        pycares.Channel().AndReturn(channel)
        channel.query('example.com', 13, IgnoreArg())
        gevent.spawn(IgnoreArg())
        self.mox.ReplayAll()
        DNSResolver.query('example.com', 13)

    def test_wait_channel(self):
        DNSResolver._channel = channel = self.mox.CreateMockAnything()
        poll = self.mox.CreateMockAnything()
        self.mox.StubOutWithMock(select, 'poll')
        select.poll().AndReturn(poll)
        channel.getsock().AndReturn(([1, 2], [2, 3]))
        channel.timeout().AndReturn(1.0)
        poll.register(1, select.POLLIN)
        poll.register(2, select.POLLIN | select.POLLOUT)
        poll.register(3, select.POLLOUT)
        poll.poll(1.0).AndReturn([(1, select.POLLIN), (3, select.POLLOUT)])
        channel.process_fd(1, pycares.ARES_SOCKET_BAD)
        channel.process_fd(pycares.ARES_SOCKET_BAD, 3)
        channel.getsock().AndReturn(([1, 3], [4]))
        channel.timeout().AndReturn(1.0)
        poll.register(3, select.POLLIN)
        poll.register(4, select.POLLOUT)
        poll.unregister(2)
        poll.poll(1.0).AndReturn([])
        channel.getsock().AndReturn(([1, 3], [4]))
        channel.timeout().AndReturn(None)
        channel.process_fd(pycares.ARES_SOCKET_BAD, pycares.ARES_SOCKET_BAD)
        channel.getsock().AndReturn(([], []))
        poll.unregister(1)
        poll.unregister(3)
        poll.unregister(4)
        self.mox.ReplayAll()
        DNSResolver._wait_channel()

    def test_wait_channel_error(self):
        DNSResolver._channel = channel = self.mox.CreateMockAnything()
        poll = self.mox.CreateMockAnything()
        self.mox.StubOutWithMock(select, 'poll')
        select.poll().AndReturn(poll)
        channel.getsock().AndReturn(([1], []))
        channel.timeout().AndReturn(1.0)
        poll.register(1, select.POLLIN).AndReturn(None)
        poll.poll(1.0).AndRaise(ValueError(13))
        channel.cancel()
        self.mox.ReplayAll()
        with self.assertRaises(ValueError):
            DNSResolver._wait_channel()
        self.assertIsNone(DNSResolver._channel)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
