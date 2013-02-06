
import os
import unittest
import re
from tempfile import mkdtemp
from shutil import rmtree

from slimta.queue.disk import DiskStorage
from slimta.envelope import Envelope


class TestdiskStorage(unittest.TestCase):

    id_pattern = re.compile(r'[0-9a-fA-F]{32}')

    def setUp(self):
        self.env_dir = mkdtemp()
        self.meta_dir = mkdtemp()
        self.tmp_dir = mkdtemp()
        self.disk = DiskStorage(self.env_dir, self.meta_dir, self.tmp_dir)

    def tearDown(self):
        rmtree(self.env_dir, True)
        rmtree(self.meta_dir, True)
        rmtree(self.tmp_dir, True)

    def _assert_empty_dir(self, path):
        filelist = os.listdir(path)
        self.assertFalse(filelist)

    def _write_test_envelope(self, rcpts=None):
        env = Envelope('sender@example.com', rcpts or ['rcpt@example.com'])
        env.timestamp = 9876543210
        id = self.disk.write(env, 1234567890)
        return id, env

    def test_write(self):
        id, env = self._write_test_envelope()
        self.assertTrue(self.id_pattern.match(id))
        self.assertEqual(env, self.env[id])
        self.assertEqual(1234567890, self.meta[id]['timestamp'])
        self.assertEqual(0, self.meta[id]['attempts'])
        self.assertEqual('sender@example.com', self.env[id].sender)
        self.assertEqual(['rcpt@example.com'], self.env[id].recipients)
        self.assertEqual(9876543210, self.env[id].timestamp)

    def test_set_timestamp(self):
        id, env = self._write_test_envelope()
        self.disk.set_timestamp(id, 1111)
        self.assertEqual(env, self.env[id])
        self.assertEqual(1111, self.meta[id]['timestamp'])

    def test_increment_attempts(self):
        id, env = self._write_test_envelope()
        self.assertEqual(1, self.disk.increment_attempts(id))
        self.assertEqual(2, self.disk.increment_attempts(id))
        self.assertEqual(env, self.env[id])
        self.assertEqual(2, self.meta[id]['attempts'])

    def test_load(self):
        queued = [self._write_test_envelope(),
                  self._write_test_envelope()]
        loaded = [info for info in self.disk.load()]
        self.assertEqual(len(queued), len(loaded))
        for timestamp, loaded_id in loaded:
            for queued_id, env in queued:
                if loaded_id == queued_id:
                    self.assertEqual(env, self.env[loaded_id])
                    self.assertEqual(timestamp, self.meta[queued_id]['timestamp'])
                    break
            else:
                raise ValueError('Queued does not match loaded')

    def test_get(self):
        id, env = self._write_test_envelope()
        self.disk.increment_attempts(id)
        get_env, get_attempts = self.disk.get(id)
        self.assertEqual(env, get_env)
        self.assertEqual(1, get_attempts)

    def test_remove(self):
        id, env = self._write_test_envelope()
        self.disk.remove(id)
        id, env = self._write_test_envelope()
        del self.env[id]
        self.disk.remove(id)
        id, env = self._write_test_envelope()
        del self.meta[id]
        self.disk.remove(id)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
