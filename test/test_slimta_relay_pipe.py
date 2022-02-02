import unittest
from mox import MoxTestBase
from gevent import Timeout
from gevent import subprocess

from slimta.relay.pipe import PipeRelay, MaildropRelay, DovecotLdaRelay
from slimta.relay import TransientRelayError, PermanentRelayError
from slimta.envelope import Envelope


class TestPipeRelay(MoxTestBase, unittest.TestCase):

    def _mock_popen(self, rcpt, returncode, stdout):
        pmock = self.mox.CreateMockAnything()
        subprocess.Popen(['relaytest', '-f', 'sender@example.com', rcpt],
                         stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE).AndReturn(pmock)
        pmock.communicate(b'From: sender@example.com\r\n\r\ntest test\r\n').AndReturn((stdout, ''))
        pmock.pid = -1
        pmock.returncode = returncode
        return pmock

    def test_attempt(self):
        self.mox.StubOutWithMock(subprocess, 'Popen')
        env = Envelope('sender@example.com', ['rcpt1@example.com', 'rcpt2@example.com', 'rcpt3@example.com', 'rcpt4@example.com', 'rcpt5@example.com'])
        env.parse(b'From: sender@example.com\r\n\r\ntest test\r\n')
        self._mock_popen('rcpt1@example.com', 0, '')
        self._mock_popen('rcpt2@example.com', 1337, 'transient')
        self._mock_popen('rcpt3@example.com', 1337, '5.0.0 permanent')
        self._mock_popen('rcpt4@example.com', 1337, b'5.0.0 permanent')
        subprocess.Popen(['relaytest', '-f', 'sender@example.com', 'rcpt5@example.com'],
                         stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE).AndRaise(Timeout)
        self.mox.ReplayAll()
        m = PipeRelay(['relaytest', '-f', '{sender}', '{recipient}'])
        results = m.attempt(env, 0)
        self.assertEqual(5, len(results))
        self.assertEqual(None, results['rcpt1@example.com'])
        self.assertIsInstance(results['rcpt2@example.com'], TransientRelayError)
        self.assertEqual('transient', str(results['rcpt2@example.com']))
        self.assertEqual('450', results['rcpt2@example.com'].reply.code)
        self.assertIsInstance(results['rcpt3@example.com'], PermanentRelayError)
        self.assertEqual('5.0.0 permanent', str(results['rcpt3@example.com']))
        self.assertEqual('550', results['rcpt3@example.com'].reply.code)
        self.assertIsInstance(results['rcpt4@example.com'], PermanentRelayError)
        self.assertEqual('5.0.0 permanent', str(results['rcpt4@example.com']))
        self.assertEqual('550', results['rcpt4@example.com'].reply.code)
        self.assertIsInstance(results['rcpt5@example.com'], TransientRelayError)
        self.assertEqual('Delivery timed out', str(results['rcpt5@example.com']))
        self.assertEqual('450', results['rcpt5@example.com'].reply.code)


class TestMaildropRelay(MoxTestBase, unittest.TestCase):

    def test_attempt(self):
        self.mox.StubOutWithMock(subprocess, 'Popen')
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse(b'From: sender@example.com\r\n\r\ntest test\r\n')
        pmock = self.mox.CreateMockAnything()
        subprocess.Popen(['maildrop', '-f', 'sender@example.com'],
                         stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE).AndReturn(pmock)
        pmock.communicate(b'From: sender@example.com\r\n\r\ntest test\r\n').AndReturn(('', ''))
        pmock.pid = -1
        pmock.returncode = 0
        self.mox.ReplayAll()
        m = MaildropRelay()
        result = m.attempt(env, 0)
        self.assertEqual(None, result)

    def test_attempt_timeout(self):
        self.mox.StubOutWithMock(subprocess, 'Popen')
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse(b'From: sender@example.com\r\n\r\ntest test\r\n')
        subprocess.Popen(['maildrop', '-f', 'sender@example.com'],
                         stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE).AndRaise(Timeout)
        self.mox.ReplayAll()
        m = MaildropRelay()
        with self.assertRaises(TransientRelayError):
            m.attempt(env, 0)

    def test_extra_args(self):
        m = MaildropRelay(extra_args=['-t', 'test'])
        self.assertEquals(['-t', 'test'], m.args[-2:])

    def test_raise_error(self):
        m = MaildropRelay()
        with self.assertRaises(TransientRelayError):
            m.raise_error(m.EX_TEMPFAIL, 'message', '')
        with self.assertRaises(PermanentRelayError):
            m.raise_error(13, 'message', '')


class TestDovecotLdaRelay(MoxTestBase, unittest.TestCase):

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
