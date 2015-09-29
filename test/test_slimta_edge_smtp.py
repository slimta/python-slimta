
import unittest2 as unittest
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


class TestEdgeSmtp(unittest.TestCase, MoxTestBase):

    def test_call_validator(self):
        mock = self.mox.CreateMockAnything()
        mock.__call__(IsA(SmtpSession)).AndReturn(mock)
        mock.handle_test('arg')
        self.mox.ReplayAll()
        h = SmtpSession(None, mock, None)
        h._call_validator('test', 'arg')

    def test_protocol_attribute(self):
        h = SmtpSession(None, None, None)
        self.assertEqual('SMTP', h.protocol)
        h.extended_smtp = True
        self.assertEqual('ESMTP', h.protocol)
        h.security = 'TLS'
        self.assertEqual('ESMTPS', h.protocol)
        h.auth = 'test'
        self.assertEqual('ESMTPSA', h.protocol)

    def test_simple_handshake(self):
        mock = self.mox.CreateMockAnything()
        mock.__call__(IsA(SmtpSession)).AndReturn(mock)
        mock.handle_banner(IsA(Reply), ('127.0.0.1', 0))
        mock.handle_helo(IsA(Reply), 'there')
        self.mox.ReplayAll()
        h = SmtpSession(('127.0.0.1', 0), mock, None)
        h.BANNER_(Reply('220'))
        h.HELO(Reply('250'), 'there')
        self.assertEqual('there', h.ehlo_as)
        self.assertFalse(h.extended_smtp)

    def test_extended_handshake(self):
        creds = self.mox.CreateMockAnything()
        creds.authcid = 'testuser'
        creds.authzid = 'testzid'
        mock = self.mox.CreateMockAnything()
        mock.__call__(IsA(SmtpSession)).AndReturn(mock)
        mock.handle_banner(IsA(Reply), ('127.0.0.1', 0))
        mock.handle_ehlo(IsA(Reply), 'there')
        mock.handle_tls()
        mock.handle_auth(IsA(Reply), creds)
        self.mox.ReplayAll()
        h = SmtpSession(('127.0.0.1', 0), mock, None)
        h.BANNER_(Reply('220'))
        h.EHLO(Reply('250'), 'there')
        h.TLSHANDSHAKE()
        h.AUTH(Reply('235'), creds)
        self.assertEqual('there', h.ehlo_as)
        self.assertTrue(h.extended_smtp)
        self.assertEqual('TLS', h.security)
        self.assertEqual('testuser', h.auth)
        self.assertEqual('ESMTPSA', h.protocol)

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
        self.assertEqual('sender@example.com', h.envelope.sender)
        self.assertEqual(['rcpt@example.com'], h.envelope.recipients)
        h.DATA(Reply('550'))
        h.RSET(Reply('250'))
        self.assertFalse(h.envelope)

    def test_have_data_errors(self):
        h = SmtpSession(None, None, None)
        reply = Reply('250')
        h.HAVE_DATA(reply, None, MessageTooBig())
        self.assertEqual('552', reply.code)
        with self.assertRaises(ValueError):
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
        self.assertEqual('250', reply.code)
        self.assertEqual('2.6.0 Message accepted for delivery', reply.message)

    def test_have_data_queueerror(self):
        env = Envelope()
        handoff = self.mox.CreateMockAnything()
        handoff(env).AndReturn([(env, QueueError())])
        self.mox.ReplayAll()
        h = SmtpSession(('127.0.0.1', 0), None, handoff)
        h.envelope = env
        reply = Reply('250')
        h.HAVE_DATA(reply, '', None)
        self.assertEqual('550', reply.code)
        self.assertEqual('5.6.0 Error queuing message', reply.message)

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
