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

"""Package implementing the :mod:`slimta.queue` system on top of a
:func:`dict()` backend. This backend can be implemented as a :mod:`shelve` to
provide basic persistence.

"""

from __future__ import absolute_import

import uuid

from slimta import logging
from . import QueueStorage

__all__ = ['DictStorage']

log = logging.getQueueStorageLogger(__name__)


class DictStorage(QueueStorage):
    """Stores |Envelope| and queue metadata in two basic dictionary objects.

    :param envelope_db: The dictionary object to hold |Envelope| objects, keyed
                        by a unique string. Defaults to an empty :func:`dict`.
    :param meta_db: The dictionary object to hold envelope metadata, keyed by
                    the same string as ``envelope_db``. Defaults to an empty
                    :func:`dict`.

    """

    def __init__(self, envelope_db=None, meta_db=None):
        super(DictStorage, self).__init__()
        self.env_db = envelope_db if envelope_db is not None else {}
        self.meta_db = meta_db if meta_db is not None else {}

    def write(self, envelope, timestamp):
        while True:
            id = uuid.uuid4().hex
            if id not in self.env_db:
                self.env_db[id] = envelope
                self.meta_db[id] = {'timestamp': timestamp, 'attempts': 0}
                log.write(id, envelope)
                return id

    def set_timestamp(self, id, timestamp):
        meta = self.meta_db[id]
        meta['timestamp'] = timestamp
        self.meta_db[id] = meta
        log.update_meta(id, timestamp=timestamp)

    def increment_attempts(self, id):
        meta = self.meta_db[id]
        new_attempts = meta['attempts'] + 1
        meta['attempts'] = new_attempts
        self.meta_db[id] = meta
        log.update_meta(id, attempts=new_attempts)
        return new_attempts

    def set_recipients_delivered(self, id, rcpt_indexes):
        self._remove_delivered_rcpts(self.env_db[id], rcpt_indexes)
        log.update_meta(id, delivered_indexes=rcpt_indexes)

    def load(self):
        for key in self.meta_db.keys():
            meta = self.meta_db[key]
            yield (meta['timestamp'], key)

    def get(self, id):
        meta = self.meta_db[id]
        return self.env_db[id], meta['attempts']

    def remove(self, id):
        try:
            del self.meta_db[id]
        except KeyError:
            pass
        try:
            del self.env_db[id]
        except KeyError:
            pass
        log.remove(id)

    def get_info(self):
        return {'size': len(self.env_db),
                'meta_size': len(self.meta_db)}


# vim:et:fdm=marker:sts=4:sw=4:ts=4
