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

from __future__ import absolute_import

from collections import deque

from gevent.lock import Semaphore

__all__ = ['BlockingDeque']


class BlockingDeque(deque):

    def __init__(self, *args, **kwargs):
        super(BlockingDeque, self).__init__(*args, **kwargs)
        self.sema = Semaphore(len(self))

    def append(self, *args, **kwargs):
        ret = super(BlockingDeque, self).append(*args, **kwargs)
        self.sema.release()
        return ret

    def appendleft(self, *args, **kwargs):
        ret = super(BlockingDeque, self).appendleft(*args, **kwargs)
        self.sema.release()
        return ret

    def clear(self, *args, **kwargs):
        ret = super(BlockingDeque, self).clear(*args, **kwargs)
        while not self.sema.locked():
            self.sema.acquire(blocking=False)
        return ret

    def extend(self, *args, **kwargs):
        pre_n = len(self)
        ret = super(BlockingDeque, self).extend(*args, **kwargs)
        post_n = len(self)
        for i in xrange(pre_n, post_n):
            self.sema.release()
        return ret

    def extendleft(self, *args, **kwargs):
        pre_n = len(self)
        ret = super(BlockingDeque, self).extendleft(*args, **kwargs)
        post_n = len(self)
        for i in xrange(pre_n, post_n):
            self.sema.release()
        return ret

    def pop(self, *args, **kwargs):
        self.sema.acquire()
        return super(BlockingDeque, self).pop(*args, **kwargs)

    def popleft(self, *args, **kwargs):
        self.sema.acquire()
        return super(BlockingDeque, self).popleft(*args, **kwargs)

    def remove(self, *args, **kwargs):
        ret = super(BlockingDeque, self).remove(*args, **kwargs)
        self.sema.acquire()
        return ret


# vim:et:fdm=marker:sts=4:sw=4:ts=4
