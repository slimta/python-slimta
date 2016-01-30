import unittest2 as unittest
import re

from slimta.queue.dict import DictStorage
from slimta.envelope import Envelope


class TestDictStorage(unittest.TestCase):

    id_pattern = re.compile(r'[0-9a-fA-F]{32}')

    def setUp(self):
        self.env = {}
        self.meta = {}
        self.dict = DictStorage(self.env, self.meta)

    def _write_test_envelope(self, rcpts=None):
        env = Envelope('sender@example.com', rcpts or ['rcpt@example.com'])
        env.timestamp = 9876543210
        id = self.dict.write(env, 1234567890)
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
        self.dict.set_timestamp(id, 1111)
        self.assertEqual(env, self.env[id])
        self.assertEqual(1111, self.meta[id]['timestamp'])

    def test_increment_attempts(self):
        id, env = self._write_test_envelope()
        self.assertEqual(1, self.dict.increment_attempts(id))
        self.assertEqual(2, self.dict.increment_attempts(id))
        self.assertEqual(env, self.env[id])
        self.assertEqual(2, self.meta[id]['attempts'])

    def test_set_recipients_delivered(self):
        id, env = self._write_test_envelope(['one', 'two', 'three'])
        self.dict.set_recipients_delivered(id, [1])
        self.assertEqual(['one', 'three'], env.recipients)
        self.dict.set_recipients_delivered(id, [0, 1])
        self.assertEqual([], env.recipients)

    def test_load(self):
        queued = [self._write_test_envelope(),
                  self._write_test_envelope()]
        loaded = [info for info in self.dict.load()]
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
        self.dict.increment_attempts(id)
        get_env, get_attempts = self.dict.get(id)
        self.assertEqual(env, get_env)
        self.assertEqual(1, get_attempts)

    def test_remove(self):
        id, env = self._write_test_envelope()
        self.dict.remove(id)
        id, env = self._write_test_envelope()
        del self.env[id]
        self.dict.remove(id)
        id, env = self._write_test_envelope()
        del self.meta[id]
        self.dict.remove(id)

    def test_get_info(self):
        id1, _ = self._write_test_envelope()
        id2, _ = self._write_test_envelope()
        id3, _ = self._write_test_envelope()
        self.dict.remove(id2)
        info = self.dict.get_info()
        self.assertEqual(2, info['size'])
        self.assertEqual(2, info['meta_size'])


# vim:et:fdm=marker:sts=4:sw=4:ts=4
