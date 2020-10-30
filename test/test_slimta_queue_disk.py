
import pytest
_ = pytest.importorskip('pyaio')

import os
import unittest
import re
from tempfile import mkdtemp
from shutil import rmtree

from slimta.diskstorage import DiskStorage
from slimta.envelope import Envelope


class TestDiskStorage(unittest.TestCase):

    id_pattern = re.compile(r'[0-9a-fA-F]{32}')

    def setUp(self):
        self.env_dir = mkdtemp()
        self.meta_dir = mkdtemp()
        self.tmp_dir = mkdtemp()
        self.disk = DiskStorage(self.env_dir, self.meta_dir, self.tmp_dir)

    def tearDown(self):
        rmtree(self.env_dir)
        rmtree(self.meta_dir)
        rmtree(self.tmp_dir)

    def _write_test_envelope(self, rcpts=None):
        env = Envelope('sender@example.com', rcpts or ['rcpt@example.com'])
        env.timestamp = 9876543210
        id = self.disk.write(env, 1234567890)
        return id, env

    def test_tmp_cleanup(self):
        id, env = self._write_test_envelope()
        self.assertEqual([], os.listdir(self.tmp_dir))

    def test_write(self):
        id, env = self._write_test_envelope()

        written_env = self.disk.ops.read_env(id)
        written_meta = self.disk.ops.read_meta(id)
        self.assertTrue(self.id_pattern.match(id))
        self.assertEqual(vars(env), vars(written_env))
        self.assertEqual(1234567890, written_meta['timestamp'])
        self.assertEqual(0, written_meta['attempts'])
        self.assertEqual('sender@example.com', written_env.sender)
        self.assertEqual(['rcpt@example.com'], written_env.recipients)
        self.assertEqual(9876543210, written_env.timestamp)

    def test_set_timestamp(self):
        id, env = self._write_test_envelope()
        self.disk.set_timestamp(id, 1111)

        written_env = self.disk.ops.read_env(id)
        written_meta = self.disk.ops.read_meta(id)
        self.assertEqual(vars(env), vars(written_env))
        self.assertEqual(1111, written_meta['timestamp'])

    def test_increment_attempts(self):
        id, env = self._write_test_envelope()
        self.assertEqual(1, self.disk.increment_attempts(id))
        self.assertEqual(2, self.disk.increment_attempts(id))

        written_env = self.disk.ops.read_env(id)
        written_meta = self.disk.ops.read_meta(id)
        self.assertEqual(vars(env), vars(written_env))
        self.assertEqual(2, written_meta['attempts'])

    def test_set_recipients_delivered(self):
        id, env = self._write_test_envelope()
        self.disk.set_recipients_delivered(id, [1])
        self.disk.set_recipients_delivered(id, [3])

        written_env = self.disk.ops.read_env(id)
        written_meta = self.disk.ops.read_meta(id)
        self.assertEqual(vars(env), vars(written_env))
        self.assertEqual([1, 3], written_meta['delivered_indexes'])

    def test_load(self):
        queued = [self._write_test_envelope(),
                  self._write_test_envelope()]
        loaded = [info for info in self.disk.load()]
        self.assertEqual(len(queued), len(loaded))
        for timestamp, loaded_id in loaded:
            for queued_id, env in queued:
                if loaded_id == queued_id:
                    written_env = self.disk.ops.read_env(loaded_id)
                    written_meta = self.disk.ops.read_meta(loaded_id)
                    self.assertEqual(vars(env), vars(written_env))
                    self.assertEqual(timestamp, written_meta['timestamp'])
                    break
            else:
                raise ValueError('Queued does not match loaded')

    def test_get(self):
        id, env = self._write_test_envelope(['rcpt1@example.com',
                                             'rcpt2@example.com'])
        self.disk.increment_attempts(id)
        self.disk.set_recipients_delivered(id, [0])
        get_env, get_attempts = self.disk.get(id)
        self.assertEqual('sender@example.com', get_env.sender)
        self.assertEqual(['rcpt2@example.com'], get_env.recipients)
        self.assertEqual(1, get_attempts)

    def test_remove(self):
        id, env = self._write_test_envelope()
        self.disk.remove(id)
        id, env = self._write_test_envelope()
        self.disk.ops.delete_env(id)
        self.disk.remove(id)
        id, env = self._write_test_envelope()
        self.disk.ops.delete_meta(id)
        self.disk.remove(id)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
