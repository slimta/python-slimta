
from assertions import *

from mox import MoxTestBase, IsA, IgnoreArg
import gevent
from gevent.socket import create_connection
from dns.resolver import NXDOMAIN
from dns.exception import DNSException

from slimta.edge.smtp import SmtpEdge, SmtpSession
from slimta.util import dns_resolver
from slimta.envelope import Envelope
from slimta.queue import QueueError
from slimta.smtp.reply import Reply
from slimta.smtp import ConnectionLost, MessageTooBig
from slimta.smtp.client import Client


class TestEdgeSmtp(MoxTestBase):

    def test_call_validator(self):
        mock = self.mox.CreateMockAnything()
        mock.__call__(IsA(SmtpSession)).AndReturn(mock)
        mock.handle_test('arg')
        self.mox.ReplayAll()
        h = SmtpSession(None, mock, None)
        h._call_validator('test', 'arg')

    def test_protocol_attribute(self):
        h = SmtpSession(None, None, None)
        assert_equal('SMTP', h.protocol)
        h.extended_smtp = True
        assert_equal('ESMTP', h.protocol)
        h.security = 'TLS'
        assert_equal('ESMTPS', h.protocol)
        h.auth_result = 'test'
        assert_equal('ESMTPSA', h.protocol)

    def test_simple_handshake(self):
        mock = self.mox.CreateMockAnything()
        mock.__call__(IsA(SmtpSession)).AndReturn(mock)
        mock.handle_banner(IsA(Reply), ('127.0.0.1', 0))
        mock.handle_helo(IsA(Reply), 'there')
        self.mox.ReplayAll()
        h = SmtpSession(('127.0.0.1', 0), mock, None)
        h.BANNER_(Reply('220'))
        h.HELO(Reply('250'), 'there')
        assert_equal('there', h.ehlo_as)
        assert_false(h.extended_smtp)

    def test_extended_handshake(self):
        mock = self.mox.CreateMockAnything()
        mock.__call__(IsA(SmtpSession)).AndReturn(mock)
        mock.handle_banner(IsA(Reply), ('127.0.0.1', 0))
        mock.handle_ehlo(IsA(Reply), 'there')
        mock.handle_tls()
        self.mox.ReplayAll()
        h = SmtpSession(('127.0.0.1', 0), mock, None)
        h.BANNER_(Reply('220'))
        h.EHLO(Reply('250'), 'there')
        h.TLSHANDSHAKE()
        h.AUTH(Reply('250'), 'testauth')
        assert_equal('there', h.ehlo_as)
        assert_true(h.extended_smtp)
        assert_equal('TLS', h.security)
        assert_equal('testauth', h.auth_result)
        assert_equal('ESMTPSA', h.protocol)

    def test_mail_rcpt_data_rset(self):
        mock = self.mox.CreateMockAnything()
        mock.__call__(IsA(SmtpSession)).AndReturn(mock)
        mock.handle_mail(IsA(Reply), 'sender@example.com', {})
        mock.handle_rcpt(IsA(Reply), 'rcpt@example.com', {})
        mock.handle_data(IsA(Reply))
        self.mox.ReplayAll()
        h = SmtpSession(None, mock, None)
        h.MAIL(Reply('250'), 'sender@example.com', {})
        h.RCPT(Reply('250'), 'rcpt@example.com', {})
        assert_equal('sender@example.com', h.envelope.sender)
        assert_equal(['rcpt@example.com'], h.envelope.recipients)
        h.DATA(Reply('550'))
        h.RSET(Reply('250'))
        assert_false(h.envelope)

    def test_have_data_errors(self):
        h = SmtpSession(None, None, None)
        reply = Reply('250')
        h.HAVE_DATA(reply, None, MessageTooBig())
        assert_equal('552', reply.code)
        with assert_raises(ValueError):
            h.HAVE_DATA(reply, None, ValueError())

    def test_have_data(self):
        env = Envelope()
        handoff = self.mox.CreateMockAnything()
        handoff(env).AndReturn([(env, 'testid')])
        self.mox.ReplayAll()
        h = SmtpSession(('127.0.0.1', 0), None, handoff)
        h.envelope = env
        reply = Reply('250')
        h.HAVE_DATA(reply, '', None)
        assert_equal('250', reply.code)
        assert_equal('2.6.0 Message accepted for delivery', reply.message)

    def test_have_data_queueerror(self):
        env = Envelope()
        handoff = self.mox.CreateMockAnything()
        handoff(env).AndReturn([(env, QueueError())])
        self.mox.ReplayAll()
        h = SmtpSession(('127.0.0.1', 0), None, handoff)
        h.envelope = env
        reply = Reply('250')
        h.HAVE_DATA(reply, '', None)
        assert_equal('550', reply.code)
        assert_equal('5.6.0 Error queuing message', reply.message)

    def test_smtp_edge(self):
        queue = self.mox.CreateMockAnything()
        queue.enqueue(IsA(Envelope)).AndReturn([(Envelope(), 'testid')])
        self.mox.ReplayAll()
        server = SmtpEdge(('127.0.0.1', 0), queue)
        server.start()
        gevent.sleep(0)
        client_sock = create_connection(server.server.address)
        client = Client(client_sock)
        client.get_banner()
        client.ehlo('there')
        client.mailfrom('sender@example.com')
        client.rcptto('rcpt@example.com')
        client.data()
        client.send_empty_data()
        client.quit()
        client_sock.close()


# vim:et:fdm=marker:sts=4:sw=4:ts=4
