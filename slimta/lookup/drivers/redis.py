# Copyright (c) 2014 Ian C. Good
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

"""Implements slimta lookup against a redis data backend. By default, this
driver expects records to be JSON-encoded string_ values. It can be configured
to use the hash_ data structure instead, but it is less flexible.

.. _hash: http://redis.io/commands#hash
.. _string: http://redis.io/commands#string
.. _GET: http://redis.io/commands/get
.. _HGETALL: http://redis.io/commands/hgetall

"""

from __future__ import absolute_import

import json

import redis
from gevent import socket

from . import LookupBase

__all__ = ['RedisLookup']


class _GeventConnection(redis.Connection):

    def _connect(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.socket_timeout)
        sock.connect((self.host, self.port))
        return sock


class RedisLookup(LookupBase):
    """Implements the slimta lookup interface using the redis key-value storage
    as the backend layer.

    :param key_template: This template string is used to determine the key
                         string to lookup. :The :py:meth:`~str.format` method
                         is called with keyword arguments, given the keyword
                         arguments passed in to :meth:`.lookup`.
    :type key_template: str
    :param host: Hostname of the redis server to connect to.
    :param port: Port to connect to.
    :param db: Database number to create keys in.
    :param password: Optional password to authenticate with.
    :param socket_timeout: Timeout, in seconds, for socket operations. If the
                           timeout is hit, :py:exc:`socket.timeout` is raised.
                           ``None`` disables the timeout.
    :param use_hash: If ``True``, keys will be looked up as hashes with
                     HGETALL_ instead of as JSON-encoded strings. Hashes do not
                     allow for complex values in results, and cannot
                     distinguish missing records from empty records.

    """

    def __init__(self, key_template, host='localhost', port=6379, db=0,
                 password=None, socket_timeout=None, use_hash=False):
        super(RedisLookup, self).__init__()
        self.key_template = key_template
        pool = redis.ConnectionPool(connection_class=_GeventConnection,
                                    host=host, port=port, db=db,
                                    password=password,
                                    socket_timeout=socket_timeout)
        self.redis = redis.StrictRedis(connection_pool=pool)
        if use_hash:
            self._key_lookup = self._hash_lookup
        else:
            self._key_lookup = self._json_lookup

    def _json_lookup(self, key):
        value_raw = self.redis.get(key)
        if value_raw:
            return json.loads(value_raw)

    def _hash_lookup(self, key):
        return self.redis.hgetall(key)

    def lookup(self, **kwargs):
        key = self._format_key(self.key_template, kwargs)
        ret = self._key_lookup(key)
        self.log(__name__, kwargs, ret)
        return ret


# vim:et:fdm=marker:sts=4:sw=4:ts=4
