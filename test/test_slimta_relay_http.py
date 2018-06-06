import unittest
from mox3.mox import MoxTestBase, IsA
from gevent.event import AsyncResult
from gevent import Timeout

from slimta.envelope import Envelope
from slimta.util.deque import BlockingDeque
from slimta.util.pycompat import urlparse
from slimta.smtp.reply import Reply
from slimta.relay import PermanentRelayError, TransientRelayError
from slimta.relay.http import HttpRelay, HttpRelayClient


class TestHttpRelay(MoxTestBase, unittest.TestCase):

    def test_add_client(self):
        static = HttpRelay('http://testurl')
        ret = static.add_client()
        self.assertIsInstance(ret, HttpRelayClient)


class TestHttpRelayClient(MoxTestBase, unittest.TestCase):

    def setUp(self):
        super(TestHttpRelayClient, self).setUp()
        self.queue = self.mox.CreateMock(BlockingDeque)
        class FakeRelay(object):
            queue = self.queue
            idle_timeout = None
            url = urlparse.urlsplit('http://testurl:8025/path/info')
            tls = None
            http_verb = 'POST'
            sender_header = 'X-Envelope-Sender'
            recipient_header = 'X-Envelope-Recipient'
            ehlo_header = 'X-Ehlo'
            ehlo_as = 'test'
            timeout = 10.0
            idle_timeout = 10.0
        self.client = HttpRelayClient(FakeRelay())
        self.result = self.mox.CreateMockAnything()
        self.env = Envelope('sender@example.com', ['rcpt1@example.com', 'rcpt2@example.com'])
        self.env.parse(b'Header: value\r\n\r\ntest message\r\n')

    def test_wait_for_request(self):
        self.mox.StubOutWithMock(self.client, '_handle_request')
        self.queue.popleft().AndReturn((5, 10))
        self.client._handle_request(5, 10)
        self.mox.ReplayAll()
        self.client._wait_for_request()

    def test_wait_for_request_timeout(self):
        self.mox.StubOutWithMock(self.client, '_handle_request')
        self.client.conn = self.mox.CreateMockAnything()
        self.queue.popleft().AndReturn((None, None))
        self.client.conn.close()
        self.mox.ReplayAll()
        self.client._wait_for_request()

    def test_handle_request(self):
        self.mox.StubOutWithMock(self.client, '_process_response')
        conn = self.client.conn = self.mox.CreateMockAnything()
        self.client.ehlo_as = 'test'
        conn.putrequest('POST', '/path/info')
        conn.putheader(b'Content-Length', b'31')
        conn.putheader(b'Content-Type', b'message/rfc822')
        conn.putheader(b'X-Ehlo', b'test')
        conn.putheader(b'X-Envelope-Sender', b'c2VuZGVyQGV4YW1wbGUuY29t')
        conn.putheader(b'X-Envelope-Recipient', b'cmNwdDFAZXhhbXBsZS5jb20=')
        conn.putheader(b'X-Envelope-Recipient', b'cmNwdDJAZXhhbXBsZS5jb20=')
        conn.endheaders(b'Header: value\r\n\r\n')
        conn.send(b'test message\r\n')
        conn.getresponse().AndReturn(13)
        self.client._process_response(13, 21)
        self.mox.ReplayAll()
        self.client._handle_request(21, self.env)

    def test_parse_smtp_reply_header(self):
        http_res = self.mox.CreateMockAnything()
        http_res.getheader('X-Smtp-Reply', '').AndReturn('250; message="2.0.0 Ok"')
        http_res.getheader('X-Smtp-Reply', '').AndReturn('550; message="5.0.0 Nope" command="smtpcmd"')
        http_res.getheader('X-Smtp-Reply', '').AndReturn('asdf')
        self.mox.ReplayAll()
        reply1 = self.client._parse_smtp_reply_header(http_res)
        self.assertEqual('250', reply1.code)
        self.assertEqual('2.0.0 Ok', reply1.message)
        self.assertEqual(None, reply1.command)
        reply2 = self.client._parse_smtp_reply_header(http_res)
        self.assertEqual('550', reply2.code)
        self.assertEqual('5.0.0 Nope', reply2.message)
        self.assertEqual('smtpcmd', reply2.command)
        reply3 = self.client._parse_smtp_reply_header(http_res)
        self.assertEqual(None, reply3)

    def test_process_response_200(self):
        http_res = self.mox.CreateMockAnything()
        http_res.status = '200'
        http_res.reason = 'OK'
        http_res.getheader('X-Smtp-Reply', '').AndReturn('250; message="2.0.0 Ok"')
        http_res.getheaders()
        self.result.set(Reply('250', '2.0.0 Ok'))
        self.mox.ReplayAll()
        self.client._process_response(http_res, self.result)

    def test_process_response_400_with_smtp_reply(self):
        http_res = self.mox.CreateMockAnything()
        http_res.status = '400'
        http_res.reason = 'Bad Request'
        http_res.getheader('X-Smtp-Reply', '').AndReturn('550; message="5.0.0 Nope"')
        http_res.getheaders()
        self.result.set_exception(IsA(PermanentRelayError))
        self.mox.ReplayAll()
        self.client._process_response(http_res, self.result)

    def test_process_response_400(self):
        http_res = self.mox.CreateMockAnything()
        http_res.status = '400'
        http_res.reason = 'Bad Request'
        http_res.getheader('X-Smtp-Reply', '').AndReturn('')
        http_res.getheaders()
        self.result.set_exception(IsA(PermanentRelayError))
        self.mox.ReplayAll()
        self.client._process_response(http_res, self.result)

    def test_process_response_500(self):
        http_res = self.mox.CreateMockAnything()
        http_res.status = '500'
        http_res.reason = 'Internal Server Error'
        http_res.getheader('X-Smtp-Reply', '').AndReturn('')
        http_res.getheaders()
        self.result.set_exception(IsA(TransientRelayError))
        self.mox.ReplayAll()
        self.client._process_response(http_res, self.result)

    def test_run(self):
        self.mox.StubOutWithMock(self.client, '_wait_for_request')
        self.client.conn = self.mox.CreateMockAnything()
        self.client._wait_for_request()
        self.client._wait_for_request().AndRaise(Timeout)
        self.client.conn.close()
        self.mox.ReplayAll()
        self.client._run()


# vim:et:fdm=marker:sts=4:sw=4:ts=4
