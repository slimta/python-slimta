
from mox3.mox import MoxTestBase, IgnoreArg

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
        self.mox.StubOutWithMock(select, 'select')
        channel.getsock().AndReturn(('read', 'write'))
        channel.timeout().AndReturn(1.0)
        select.select('read', 'write', [], 1.0).AndReturn(
            ([1, 2, 3], [4, 5, 6], None))
        for fd in [1, 2, 3]:
            channel.process_fd(fd, pycares.ARES_SOCKET_BAD)
        for fd in [4, 5, 6]:
            channel.process_fd(pycares.ARES_SOCKET_BAD, fd)
        channel.getsock().AndReturn(('read', 'write'))
        channel.timeout().AndReturn(None)
        channel.process_fd(pycares.ARES_SOCKET_BAD, pycares.ARES_SOCKET_BAD)
        channel.getsock().AndReturn((None, None))
        self.mox.ReplayAll()
        DNSResolver._wait_channel()

    def test_wait_channel_error(self):
        DNSResolver._channel = channel = self.mox.CreateMockAnything()
        self.mox.StubOutWithMock(select, 'select')
        channel.getsock().AndReturn(('read', 'write'))
        channel.timeout().AndReturn(1.0)
        select.select('read', 'write', [], 1.0).AndRaise(ValueError(13))
        channel.cancel()
        self.mox.ReplayAll()
        with self.assertRaises(ValueError):
            DNSResolver._wait_channel()
        self.assertIsNone(DNSResolver._channel)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
