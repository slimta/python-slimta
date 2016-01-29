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

from itertools import chain

__all__ = ['DataSender']


class DataSender(object):
    """Class that writes multi-line message data, taking care of dot marker
    """
    def __init__(self, *parts):
        self.parts = parts
        self._calc_end_marker()

    def _calc_last_two(self):
        ret = b''
        for part in reversed(self.parts):
            ret = part[-2:] + ret
            if len(ret) >= 2:
                ret = ret[-2:]
                break
        return ret

    def _calc_end_marker(self):
        last_two = self._calc_last_two()
        if not last_two or last_two == b'\r\n':
            self.end_marker = b'.\r\n'
        else:
            self.end_marker = b'\r\n.\r\n'

    def _process_part(self, part):
        """
        :type part: bytes
        """
        part_len = len(part)
        i = 0
        if part_len > 0 and part[0:1] == b'.':
            yield b'.'
        while i < part_len:
            index = part.find(b'\n.', i)
            if index == -1:
                yield part if i == 0 else part[i:]
                i = part_len
            else:
                yield part[i:index+2]
                yield b'.'
                i = index+2

    def __iter__(self):
        iterables = [self._process_part(part) for part in self.parts]
        iterables.append((self.end_marker, ))
        return chain.from_iterable(iterables)

    def send(self, io):
        for piece in self:
            io.buffered_send(piece)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
