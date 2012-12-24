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

"""Package providing a mocked socket interface, such that it will raise an
exception if data is sent or received out of an expected ordering.

"""

from pprint import pformat

__all__ = ['MockSocket']


class SequenceError(Exception):
    """Raised when the mock socket expected data to be sent to it and instead
    data was requested of it, or the mock socket expected to send data and
    instead data was sent to it.

    :param expected: The command the mock socket expected.
    :param command: The command the mock socket was given.
    :param data: If the command was ``send``, this is the associated data.

    """

    def __init__(self, expected, command, data=None):
        message = 'Received {0} when {1} was expected [{2}]'.format(\
                command, expected, pformat(data))
        super(SequenceError, self).__init__(message)
        self.expected = expected
        self.command = command
        self.data = data


class ExpectationError(Exception):
    """Raised when data that the mock socket expected to receive was different
    from what it actually received.

    :param expected: What the mock expected.
    :type expected: string
    :param received: What the mock received.
    :type received: string

    """

    def __init__(self, expected, received):
        message = 'Expectation failed: [{0}] != [{1}]'.format(\
                pformat(expected), pformat(received))
        super(ExpectationError, self).__init__(message)
        self.expected = expected
        self.received = received


class MockSocket(object):
    """Mocks a socket such that the data sent back-and-forth can be scripted and
    if the actual transaction does not match the script an error is thrown.

    :param script: List of tuples, such that the first item in the tuple is
                   either 'send' or 'recv' and the second item in the tuple is
                   the data.

    """

    def __init__(self, script):
        self.script = script
        self.i = 0

    def fileno(self):
        return -1

    def tls_wrapper(self, socket, tls):
        expected_command, expected_data = self.script[self.i]
        if expected_command != 'encrypt':
            raise SequenceError(expected_command, 'encrypt', tls)
        if tls != expected_data:
            raise ExpectationError(expected_data, tls)
        self.i += 1
        return socket

    def send(self, data):
        expected_command, expected_data = self.script[self.i]
        if expected_command != 'send':
            raise SequenceError(expected_command, 'send', data)
        if data != expected_data:
            raise ExpectationError(expected_data, data)
        self.i += 1

    def sendall(self, data):
        return self.send(data)

    def recv(self, s=None):
        expected_command, requested_data = self.script[self.i]
        if expected_command != 'recv':
            raise SequenceError(expected_command, 'recv')
        self.i += 1
        return requested_data

    def close(self):
        expected_command = self.script[self.i][0]
        if expected_command != 'close':
            raise SequenceError(expected_command, 'close')
        self.i += 1

    def assert_done(self, test):
        test.assertRaises(IndexError, self.script.__getitem__, self.i)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
