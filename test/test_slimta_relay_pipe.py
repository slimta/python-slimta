import unittest2 as unittest
from mox3.mox import MoxTestBase, IsA
from gevent import Timeout
from gevent import subprocess

from slimta.relay.pipe import PipeRelay, MaildropRelay, DovecotLdaRelay
from slimta.relay import TransientRelayError, PermanentRelayError
from slimta.envelope import Envelope


class TestPipeRelay(unittest.TestCase, MoxTestBase):

    def test_exec_process(self):
        pmock = self.mox.CreateMock(subprocess.Popen)
        self.mox.StubOutWithMock(subprocess, 'Popen')
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse(b'From: sender@example.com\r\n\r\ntest test\r\n')
        subprocess.Popen(['relaytest', '-f', 'sender@example.com'],
                         stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE).AndReturn(pmock)
        pmock.communicate(b'From: sender@example.com\r\n\r\ntest test\r\n').AndReturn(('testout', 'testerr'))
        pmock.pid = -1
        pmock.returncode = 0
        self.mox.ReplayAll()
        m = PipeRelay(['relaytest', '-f', '{sender}'])
        status, stdout, stderr = m._exec_process(env)
        self.assertEqual(0, status)
        self.assertEqual('testout', stdout)
        self.assertEqual('testerr', stderr)

    def test_exec_process_error(self):
        pmock = self.mox.CreateMock(subprocess.Popen)
        self.mox.StubOutWithMock(subprocess, 'Popen')
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse(b'From: sender@example.com\r\n\r\ntest test\r\n')
        subprocess.Popen(['relaytest', '-f', 'sender@example.com'],
                         stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE).AndReturn(pmock)
        pmock.communicate(b'From: sender@example.com\r\n\r\ntest test\r\n').AndReturn(('', ''))
        pmock.pid = -1
        pmock.returncode = 1337
        self.mox.ReplayAll()
        m = PipeRelay(['relaytest', '-f', '{sender}'])
        status, stdout, stderr = m._exec_process(env)
        self.assertEqual(1337, status)
        self.assertEqual('', stdout)
        self.assertEqual('', stderr)

    def test_attempt(self):
        env = Envelope()
        m = PipeRelay(['relaytest'])
        self.mox.StubOutWithMock(m, '_exec_process')
        m._exec_process(env).AndReturn((0, '', ''))
        self.mox.ReplayAll()
        m.attempt(env, 0)

    def test_attempt_transientfail(self):
        env = Envelope()
        m = PipeRelay(['relaytest'])
        self.mox.StubOutWithMock(m, '_exec_process')
        m._exec_process(env).AndReturn((1337, 'transient failure', ''))
        self.mox.ReplayAll()
        with self.assertRaises(TransientRelayError):
            m.attempt(env, 0)

    def test_attempt_timeout(self):
        env = Envelope()
        m = PipeRelay(['relaytest'])
        self.mox.StubOutWithMock(m, '_exec_process')
        m._exec_process(env).AndRaise(Timeout)
        self.mox.ReplayAll()
        with self.assertRaises(TransientRelayError):
            m.attempt(env, 0)

    def test_attempt_permanentfail(self):
        env = Envelope()
        m = PipeRelay(['relaytest'])
        self.mox.StubOutWithMock(m, '_exec_process')
        m._exec_process(env).AndReturn((13, '5.0.0 permanent failure', ''))
        self.mox.ReplayAll()
        with self.assertRaises(PermanentRelayError):
            m.attempt(env, 0)


class TestMaildropRelay(unittest.TestCase, MoxTestBase):

    def test_extra_args(self):
        m = MaildropRelay(extra_args=['-t', 'test'])
        self.assertEquals(['-t', 'test'], m.args[-2:])

    def test_raise_error(self):
        m = MaildropRelay()
        with self.assertRaises(TransientRelayError):
            m.raise_error(m.EX_TEMPFAIL, 'message', '')
        with self.assertRaises(PermanentRelayError):
            m.raise_error(13, 'message', '')


class TestDovecotLdaRelay(unittest.TestCase, MoxTestBase):

    def test_extra_args(self):
        m = DovecotLdaRelay(extra_args=['-t', 'test'])
        self.assertEquals(['-t', 'test'], m.args[-2:])

    def test_raise_error(self):
        m = DovecotLdaRelay()
        with self.assertRaises(TransientRelayError):
            m.raise_error(m.EX_TEMPFAIL, 'message', '')
        with self.assertRaises(PermanentRelayError):
            m.raise_error(13, 'message', '')


# vim:et:fdm=marker:sts=4:sw=4:ts=4
