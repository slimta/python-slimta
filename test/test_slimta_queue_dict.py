
import unittest
import re

from assertions import *

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
        assert_true(self.id_pattern.match(id))
        assert_equal(env, self.env[id])
        assert_equal(1234567890, self.meta[id]['timestamp'])
        assert_equal(0, self.meta[id]['attempts'])
        assert_equal('sender@example.com', self.env[id].sender)
        assert_equal(['rcpt@example.com'], self.env[id].recipients)
        assert_equal(9876543210, self.env[id].timestamp)

    def test_set_timestamp(self):
        id, env = self._write_test_envelope()
        self.dict.set_timestamp(id, 1111)
        assert_equal(env, self.env[id])
        assert_equal(1111, self.meta[id]['timestamp'])

    def test_increment_attempts(self):
        id, env = self._write_test_envelope()
        assert_equal(1, self.dict.increment_attempts(id))
        assert_equal(2, self.dict.increment_attempts(id))
        assert_equal(env, self.env[id])
        assert_equal(2, self.meta[id]['attempts'])

    def test_set_recipients_delivered(self):
        id, env = self._write_test_envelope(['one', 'two', 'three'])
        self.dict.set_recipients_delivered(id, [1])
        assert_equal(['one', 'three'], env.recipients)
        self.dict.set_recipients_delivered(id, [0, 1])
        assert_equal([], env.recipients)

    def test_load(self):
        queued = [self._write_test_envelope(),
                  self._write_test_envelope()]
        loaded = [info for info in self.dict.load()]
        assert_equal(len(queued), len(loaded))
        for timestamp, loaded_id in loaded:
            for queued_id, env in queued:
                if loaded_id == queued_id:
                    assert_equal(env, self.env[loaded_id])
                    assert_equal(timestamp, self.meta[queued_id]['timestamp'])
                    break
            else:
                raise ValueError('Queued does not match loaded')

    def test_get(self):
        id, env = self._write_test_envelope()
        self.dict.increment_attempts(id)
        get_env, get_attempts = self.dict.get(id)
        assert_equal(env, get_env)
        assert_equal(1, get_attempts)

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
        assert_equal(2, info['size'])
        assert_equal(2, info['meta_size'])


# vim:et:fdm=marker:sts=4:sw=4:ts=4
