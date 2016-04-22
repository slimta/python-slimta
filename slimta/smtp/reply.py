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

"""Package defining the class containing a standard SMTP reply made up of a
code and a message, as well as a few pre-defined standard replies.

.. _ENHANCEDSTATUSCODES: http://tools.ietf.org/html/rfc2034

"""

from __future__ import absolute_import

import re

from slimta.util import pycompat

__all__ = ['Reply', 'unknown_command', 'unknown_parameter', 'bad_sequence',
                    'bad_arguments', 'timed_out', 'unhandled_error',
                    'connection_failed', 'tls_failure', 'invalid_credentials']

message_esc_pattern = re.compile(r'^([245]\.\d\d?\d?\.\d\d?\d?)\s+')
esc_pattern = re.compile(r'^([245])\.(\d\d?\d?)\.(\d\d?\d?)$')
code_pattern = re.compile(r'^[12345]\d\d$')


class Reply(object):
    """Defines a standard SMTP reply, which can be made up of a code, an
    intelligent ENHANCEDSTATUSCODES_ string, and a free-form message. This
    object may or may not be immediately populated with real data.

    :param code: The three-digit SMTP code.
    :param message: Message part of the reply, possibly prefixed with an
                    ENHANCEDSTATUSCODES_ string.
    :param command: The command that is waiting for the reply, typically for
                    logging or debugging.
    :param address: Information about the remote host that gave the reply, see
                    :py:mod:`socket` for details.

    """

    def __init__(self, code=None, message=None, command=None, address=None):
        self.command = command
        self.address = address

        #: Holds the reply code, which can only be set to a string containing
        #: three digits.
        self.code = code

        #: Holds the ENHANCEDSTATUSCODES_ string. This property is usually set
        #: automatically by the ``message`` property.
        self.enhanced_status_code = None

        #: Gets and sets the reply message. If you set this property with an
        #: ENHANCEDSTATUSCODES_ string prefixed, that string will be pulled out
        #: and set in the ``enhanced_status_code``.
        self.message = message

        #: Boolean defining whether a newline should be sent before the reply,
        #: which is useful for asynchronous replies such as timeouts.
        self.newline_first = False

    def __eq__(self, other):
        if not hasattr(other, 'code') or not hasattr(other, 'message'):
            return NotImplemented
        return self.code == other.code and self.message == other.message

    def __repr__(self):
        """Converts the reply into a string that shows appropriate internals of
        the object.

        :rtype: str

        """
        return '<Reply code={0!r} message={1!r}>'.format(self.code,
                                                         self.message)

    def __str__(self):
        """Converts the reply into a single string.

        :returns: The code, ENHANCEDSTATUSCODES_ string, and the message,
                  separated by spaces.
        :rtype: str

        """
        return '{0} {1}'.format(self.code, self.message)

    def __bytes__(self):
        """Converts the reply into a single bytestring.

        :returns: The code, ENHANCEDSTATUSCODES_ string, and the message,
                  separated by spaces.
        :rtype: :py:obj:`bytes`

        """
        return b' '.join((self.code.encode('ascii'),
                          self.message.encode('utf-8')))

    def __bool__(self):
        """Defines the truth-testing operation for |Reply| objects. This will
        evaluate ``True`` if the object value set to its ``code`` attribute
        other than ``None``. This is useful for checking replies that may be
        buffered and not yet populatd..

        :rtype: True or False

        """
        return self.code is not None

    # Python 2 compat.
    if pycompat.PY2:
        __nonzero__ = __bool__
        __unicode__ = __str__
        __str__ = __bytes__

    def copy(self, reply):
        """Direct-copies the given reply code and message into the current
        object. This is generally useful for sending pre-defined responses.

        :param reply: A :class:`Reply` object to copy.

        """
        self._code = reply._code
        self._message = reply._message
        self._esc = reply._esc
        return self

    def recv(self, io):
        """Populates the object with the code and message received from the
        session.

        :param io: :class:`IO` object to use to receive the reply.

        """
        self.code, self.message = io.recv_reply()
        self.address = io.address

    def send(self, io, flush=False):
        """Sends the reply to the session.

        :param io: :class:`IO` object to use to send the reply.
        :param flush: If ``True``, flush the send buffer after sending.

        """
        if self.newline_first:
            io.buffered_send(b'\r\n')
        io.send_reply(self)
        if flush:
            io.flush_send()

    def is_error(self):
        """Checks if the SMTP reply indicates an error, which will be True if
        the code begins with a ``4`` or ``5``.

        :rtype: True or False

        """
        return self.code[0] in ('4', '5')

    @property
    def code(self):
        return self._code

    @code.setter
    def code(self, value):
        if value:
            match = code_pattern.match(value)
            if match:
                self._code = value
            else:
                raise ValueError('Invalid SMTP reply code', value)
        else:
            self._code = value

    @property
    def message(self):
        esc = self.enhanced_status_code
        msg = self._message
        if esc and msg:
            return ' '.join((esc, msg))
        else:
            return msg

    @message.setter
    def message(self, value):
        if value:
            match = message_esc_pattern.match(value)
            if match:
                self._message = value[match.end(0):]
                self.enhanced_status_code = match.group(1)
                return
        self._message = value
        if self._esc:
            self._esc = None

    @property
    def enhanced_status_code(self):
        code_0 = self._code and self._code[0]
        if code_0 in ('2', '4', '5'):
            if self._esc:
                return '.'.join((code_0, self._esc[1], self._esc[2]))
            elif self._esc is False:
                return None
            else:
                return '.'.join((code_0, '0', '0'))

    @enhanced_status_code.setter
    def enhanced_status_code(self, value):
        if value:
            match = esc_pattern.match(value)
            if match:
                self._esc = match.groups()
            else:
                raise ValueError('Invalid ENHANCEDSTATUSCODES string', value)
        else:
            self._esc = value

    @property
    def raw_message(self):
        return self._message


#: Reply sent when an unknown SMTP command is received by a server.
unknown_command = Reply('500', '5.5.2 Syntax error, command unrecognized')

#: Reply sent when a parameter is sent that is not supported.
unknown_parameter = Reply('504', '5.5.4 Command parameter not implemented')

#: Reply sent when commands are sent out of standard SMTP sequence.
bad_sequence = Reply('503', '5.5.1 Bad sequence of commands')

#: Reply sent when an expected parameter is invalid.
bad_arguments = Reply('501', '5.5.4 Syntax error in parameters or arguments')

#: Reply sent when an unhandled exception is raised in a command handler.
unhandled_error = Reply('421', '4.3.0 Unhandled system error')

#: Reply sent when a TLS negotiation error occurs.
tls_failure = Reply('421', '4.7.0 TLS negotiation failed')

#: Reply sent when a connection fails unexpectedly.
connection_failed = Reply('451', '4.3.0 Connection failed')

#: Reply sent when the server times out waiting for data from the client.
timed_out = Reply('421', '4.4.2 Connection timed out')
timed_out.newline_first = True

#: Reply sent when an authentication attempt resulted in invalid credentials.
invalid_credentials = Reply(
    '535', '5.7.8 Authentication credentials invalid')


# vim:et:fdm=marker:sts=4:sw=4:ts=4
