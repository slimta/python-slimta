# Copyright (c) 2012 Ian C. Good
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

"""Package implementing the :mod:`~slimta.queue` storage system using redis_.

.. _redis: http://redis.io/

"""

from __future__ import absolute_import

import uuid
import time
import pickle

import redis
from gevent import socket

from slimta.queue import QueueStorage
from slimta import logging

__all__ = ['RedisStorage']

log = logging.getQueueStorageLogger(__name__)


class GeventConnection(redis.Connection):

    def _connect(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.socket_timeout)
        sock.connect((self.host, self.port))
        return sock


class RedisStorage(QueueStorage):
    """|QueueStorage| mechanism that stores |Envelope| and queue metadata in
    redis hashes.

    :param host: Hostname of the redis server to connect to.
    :param port: Port to connect to.
    :param db: Database number to create keys in.
    :param password: Optional password to authenticate with.
    :param socket_timeout: Timeout, in seconds, for socket operations. If the
                           timeout is hit, :py:exc:`socket.timeout` is raised.
                           ``None`` disables the timeout.
    :param prefix: Any key created is prefixed with this string.
    :type prefix: str

    """

    def __init__(self, host='localhost', port=6379, db=0, password=None,
                 socket_timeout=None, prefix='slimta:'):
        super(RedisStorage, self).__init__()
        pool = redis.ConnectionPool(connection_class=GeventConnection,
                                    host=host, port=port, db=db,
                                    password=password,
                                    socket_timeout=socket_timeout)
        self.redis = redis.StrictRedis(connection_pool=pool)
        self.prefix = prefix
        self.queue_key = '{0}queue'.format(prefix)

    def _get_key(self, id):
        if isinstance(id, bytes):
            id = id.decode('ascii')
        return self.prefix + id

    def write(self, envelope, timestamp):
        envelope_raw = pickle.dumps(envelope, pickle.HIGHEST_PROTOCOL)
        while True:
            id = uuid.uuid4().hex
            key = self._get_key(id)
            if self.redis.hsetnx(key, 'envelope', envelope_raw):
                queue_raw = pickle.dumps((timestamp, id),
                                         pickle.HIGHEST_PROTOCOL)
                pipe = self.redis.pipeline()
                pipe.hmset(key, {'timestamp': timestamp,
                                 'attempts': 0})
                pipe.rpush(self.queue_key, queue_raw)
                pipe.execute()
                log.write(id, envelope)
                return id

    def set_timestamp(self, id, timestamp):
        self.redis.hset(self._get_key(id), 'timestamp', timestamp)
        log.update_meta(id, timestamp=timestamp)

    def increment_attempts(self, id):
        new_attempts = self.redis.hincrby(self._get_key(id), 'attempts', 1)
        log.update_meta(id, attempts=new_attempts)
        return new_attempts

    def set_recipients_delivered(self, id, rcpt_indexes):
        current = self.redis.hget(self._get_key(id), 'delivered_indexes')
        new_indexes = rcpt_indexes
        if current:
            new_indexes = pickle.loads(current) + rcpt_indexes
        self.redis.hset(self._get_key(id), 'delivered_indexes',
                        pickle.dumps(new_indexes, pickle.HIGHEST_PROTOCOL))
        log.update_meta(id, delivered_indexes=rcpt_indexes)

    def load(self):
        for key in self.redis.keys(self.prefix+'*'):
            if key != self.queue_key:
                id = key[len(self.prefix):]
                timestamp = self.redis.hget(key, 'timestamp') or time.time()
                yield float(timestamp), id

    def get(self, id):
        envelope_raw, attempts, delivered_indexes_raw = \
            self.redis.hmget(self._get_key(id), 'envelope', 'attempts',
                             'delivered_indexes')
        if not envelope_raw:
            raise KeyError(id)
        envelope = pickle.loads(envelope_raw)
        del envelope_raw
        if delivered_indexes_raw:
            delivered_indexes = pickle.loads(delivered_indexes_raw)
            self._remove_delivered_rcpts(envelope, delivered_indexes)
        return envelope, int(attempts or 0)

    def remove(self, id):
        self.redis.delete(self._get_key(id))
        log.remove(id)

    def wait(self):
        ret = self.redis.blpop([self.queue_key], 0)
        if ret:
            return [pickle.loads(ret[1])]
        return []


# vim:et:fdm=marker:sts=4:sw=4:ts=4
