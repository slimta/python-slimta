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

"""Package implementing the :mod:`slimta.queue` system on disk.

"""

import os
import uuid
import os.path
import cPickle

from pyaio.gevent import aioFile

from slimta.queue import QueueStorage 
from slimta import logging

__all__ = ['DiskStorage']

log = logging.getQueueStorageLogger(__name__)


class aioFileWithReadline(aioFile):

    def read(self, *args, **kwargs):
        return str(super(aioFileWithReadline, self).read(*args, **kwargs))

    def readline(self, size=None):
        linebuf = bytearray()
        print 'ohi'
        while True:
            piece = super(aioFileWithReadline, self).read(64)
            if piece is None:
                return str(linebuf)
            endl_index = piece.find('\n')
            if endl_index == -1:
                linebuf.extend(piece)
            else:
                piece_view = memoryview(piece)
                linebuf.extend(piece_view[0:endl_index+1])
                if endl_index+1 < len(piece):
                    leftover = piece_view[endl_index+1:]
                    self._read_buf[0:0] = leftover
                    self._offset -= len(leftover)
                    self._eof = False
                return str(linebuf)


class DiskOps(object):

    def __init__(self, env_dir, meta_dir, tmp_dir):
        self.env_dir = env_dir
        self.meta_dir = meta_dir
        self.tmp_dir = tmp_dir

    def check_exists(self, id):
        path = os.path.join(self.env_dir, id)
        return os.path.lexists(path)

    def write_env(self, id, envelope):
        tmp_path = os.path.join(self.tmp_dir, id)
        final_path = os.path.join(self.env_dir, id)
        with aioFileWithReadline(tmp_path, 'w') as f:
            cPickle.dump(envelope, f)
        os.rename(tmp_path, final_path)

    def write_meta(self, id, meta):
        tmp_path = os.path.join(self.tmp_dir, id+'.meta')
        final_path = os.path.join(self.meta_dir, id+'.meta')
        with aioFileWithReadline(tmp_path, 'w') as f:
            cPickle.dump(meta, f)
        os.rename(tmp_path, final_path)

    def read_meta(self, id):
        path = os.path.join(self.meta_dir, id+'.meta')
        with aioFileWithReadline(path, 'r') as f:
            return cPickle.load(f)

    def read_env(self, id):
        path = os.path.join(self.env_dir, id)
        with aioFileWithReadline(path, 'r') as f:
            return cPickle.load(f)

    def get_ids(self):
        return os.listdir(self.env_dir)

    def delete_env(self, id):
        env_path = os.path.join(self.env_dir, id)
        try:
            os.remove(env_path)
        except OSError:
            pass

    def delete_meta(self, id):
        meta_path = os.path.join(self.meta_dir, id+'.meta')
        try:
            os.remove(meta_path)
        except OSError:
            pass


class DiskStorage(QueueStorage):
    """Stores |Envelope| and queue metadata in two files on disk.

    :param env_dir: Directory where queue envelope files are stored. These
                    files may be large and will not be modified after initial
                    writing.
    :param meta_dir: Directory where queue meta files are stored. These files
                     will be small and volatile.
    :param tmp_dir: Directory that may be used as scratch space. New files are
                    written here and then moved to their final destination.

    """

    def __init__(self, env_dir, meta_dir, tmp_dir='/tmp'):
        super(DiskStorage, self).__init__()
        self.ops = DiskOps(env_dir, meta_dir, tmp_dir)

    def write(self, envelope, timestamp):
        meta = {'timestamp': timestamp, 'attempts': 0}
        while True:
            id = uuid.uuid4().hex
            if not self.ops.check_exists(id):
                self.ops.write_env(id, envelope)
                self.ops.write_meta(id, meta)
                log.write(id, envelope)
                return id

    def set_timestamp(self, id, timestamp):
        meta = self.ops.read_meta(id)
        meta['timestamp'] = timestamp
        self.ops.write_meta(id, meta)
        log.update_meta(id, timestamp=timestamp)

    def increment_attempts(self, id):
        meta = self.ops.read_meta(id)
        new_attempts = meta['attempts'] + 1
        meta['attempts'] = new_attempts
        self.ops.write_meta(id, meta)
        log.update_meta(id, attempts=new_attempts)
        return new_attempts

    def load(self):
        for id in self.ops.get_ids():
            meta = self.ops.read_meta(id)
            yield (meta['timestamp'], id)

    def get(self, id):
        meta = self.ops.read_meta(id)
        env = self.ops.read_env(id)
        return env, meta['attempts']

    def remove(self, id):
        self.ops.delete_env(id)
        self.ops.delete_meta(id)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
