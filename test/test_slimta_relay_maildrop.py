
import unittest

from mox import MoxTestBase, IsA
from gevent import Timeout
import gevent_subprocess

from slimta.relay.maildrop import MaildropRelay
from slimta.relay import TransientRelayError, PermanentRelayError
from slimta.envelope import Envelope


class TestMaildropRelay(MoxTestBase):

    def test_exec_maildrop(self):
        pmock = self.mox.CreateMock(gevent_subprocess.Popen)
        self.mox.StubOutWithMock(gevent_subprocess, 'Popen')
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse('From: sender@example.com\r\n\r\ntest test\r\n')
        gevent_subprocess.Popen(['maildrop', '-f', 'sender@example.com'],
                                stdin=gevent_subprocess.PIPE,
                                stdout=gevent_subprocess.PIPE,
                                stderr=gevent_subprocess.PIPE).AndReturn(pmock)
        pmock.communicate('From: sender@example.com\r\n\r\ntest test\r\n').AndReturn(('', ''))
        pmock.pid = -1
        pmock.returncode = 0
        self.mox.ReplayAll()
        m = MaildropRelay()
        status, msg = m._exec_maildrop(env)
        self.assertEqual(0, status)
        self.assertEqual(None, msg)

    def test_exec_maildrop_error(self):
        pmock = self.mox.CreateMock(gevent_subprocess.Popen)
        self.mox.StubOutWithMock(gevent_subprocess, 'Popen')
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse('From: sender@example.com\r\n\r\ntest test\r\n')
        gevent_subprocess.Popen(['maildrop', '-f', 'sender@example.com'],
                                stdin=gevent_subprocess.PIPE,
                                stdout=gevent_subprocess.PIPE,
                                stderr=gevent_subprocess.PIPE).AndReturn(pmock)
        pmock.communicate('From: sender@example.com\r\n\r\ntest test\r\n').AndReturn(('', 'maildrop: error msg'))
        pmock.pid = -1
        pmock.returncode = MaildropRelay.EX_TEMPFAIL
        self.mox.ReplayAll()
        m = MaildropRelay()
        status, msg = m._exec_maildrop(env)
        self.assertEqual(MaildropRelay.EX_TEMPFAIL, status)
        self.assertEqual('error msg', msg)

    def test_attempt(self):
        env = Envelope()
        m = MaildropRelay()
        self.mox.StubOutWithMock(m, '_exec_maildrop')
        m._exec_maildrop(env).AndReturn((0, None))
        self.mox.ReplayAll()
        m.attempt(env, 0)

    def test_attempt_transientfail(self):
        env = Envelope()
        m = MaildropRelay()
        self.mox.StubOutWithMock(m, '_exec_maildrop')
        m._exec_maildrop(env).AndReturn((MaildropRelay.EX_TEMPFAIL, 'transient failure'))
        self.mox.ReplayAll()
        with self.assertRaises(TransientRelayError):
            m.attempt(env, 0)

    def test_attempt_timeout(self):
        env = Envelope()
        m = MaildropRelay()
        self.mox.StubOutWithMock(m, '_exec_maildrop')
        m._exec_maildrop(env).AndRaise(Timeout)
        self.mox.ReplayAll()
        with self.assertRaises(TransientRelayError):
            m.attempt(env, 0)

    def test_attempt_permanentfail(self):
        env = Envelope()
        m = MaildropRelay()
        self.mox.StubOutWithMock(m, '_exec_maildrop')
        m._exec_maildrop(env).AndReturn((13, 'permanent failure'))
        self.mox.ReplayAll()
        with self.assertRaises(PermanentRelayError):
            m.attempt(env, 0)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
