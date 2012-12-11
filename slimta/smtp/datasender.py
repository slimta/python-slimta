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

import re

__all__ = ['DataSender']


class DataSender(object):

    def __init__(self, data):
        self.data = data
        self.data_len = len(data)
        if self.data_len == 0 or data[-1] == '\n':
            self.end_marker = '.\r\n'
        else:
            self.end_marker = '\r\n.\r\n'

    def _process(self):
        done = False
        data = self.data
        data_len = self.data_len
        i = 0
        if data_len > 0 and data[0] == '.':
            yield '.'
        while not done:
            if i >= data_len:
                done = True
                yield self.end_marker
            else:
                index = data.find('\n.', i)
                if index == -1:
                    yield data if i == 0 else data[i:]
                    i = data_len
                else:
                    yield data[i:index+2]
                    yield '.'
                    i = index+2

    def __iter__(self):
        return self._process()

    def send(self, io):
        for piece in self:
            io.buffered_send(piece)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
