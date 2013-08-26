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

"""Reads message contents from an SMTP client. This task requires special
consideration because of the SMTP RFC requirements that message data be ended
with a line with a single ``.``. Also, lines that begin with ``.`` but contain
other data should have the prefixed ``.`` removed.

"""

from __future__ import absolute_import

import re
import cStringIO
from pprint import pformat

from . import ConnectionLost, MessageTooBig

__all__ = ['DataReader']

fullline_pattern = re.compile(r'.*\n')
eod_pattern = re.compile(r'^\.\s*?\n$')
endl_pattern = re.compile(r'\r?\n$')


class DataReader(object):
    """Class that reads message data until the End-Of-Data marker, or until a
    certain number of bytes have been read.

    :param io: |IO| object to read message data from.
    :param max_size: If given, causes :class:`slimta.smtp.MessageTooBig` to be
                     raised if too many bytes have been read.

    """

    def __init__(self, io, max_size=None):
        self.io = io
        self.size = 0
        self.max_size = max_size

        self.EOD = None
        self.lines = ['']
        self.i = 0

    def _append_line(self, line):
        if len(self.lines) <= self.i:
            self.lines.append(line)
        else:
            self.lines[self.i] += line

    def from_recv_buffer(self):
        self.add_lines(self.io.recv_buffer)
        self.io.recv_buffer = ''

    def handle_finished_line(self):
        i = self.i
        line = self.lines[i]

        # Move internal trackers ahead.
        self.i += 1

        # Only handle lines within the data.
        if not self.EOD:
            # Check for the End-Of-Data marker.
            if eod_pattern.match(line):
                self.EOD = i

            # Remove an initial period on non-EOD lines as per RFC 821 4.5.2.
            elif line[0] == '.':
                line = line[1:]
                self.lines[i] = line

    def add_lines(self, piece):
        last = 0
        for match in fullline_pattern.finditer(piece):
            last = match.end(0)
            self._append_line(match.group(0))
            self.handle_finished_line()
        after_match = piece[last:]
        self._append_line(after_match)

    def recv_piece(self):
        if self.EOD is not None:
            return False

        piece = self.io.raw_recv()
        if piece == '':
            raise ConnectionLost()

        self.size += len(piece)
        if self.max_size and self.size > self.max_size:
            self.EOD = self.i
            raise MessageTooBig()

        self.add_lines(piece)
        return not self.EOD

    def return_all(self):
        data_lines = self.lines[:self.EOD]
        after_data_lines = self.lines[self.EOD+1:]

        # Save the extra lines back on the recv_buffer.
        self.io.recv_buffer = ''.join(after_data_lines)

        # Return the data as one big string
        return ''.join(data_lines)

    def recv(self):
        """Receives all message data from the session.

        :rtype: str

        """
        self.from_recv_buffer()
        while self.recv_piece():
            pass
        return self.return_all()


# vim:et:fdm=marker:sts=4:sw=4:ts=4
