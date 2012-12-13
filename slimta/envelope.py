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

"""Module defining :class:`Envelope` for holding message data along with
metadata.

"""

__all__ = ['Envelope']


class Envelope(object):
    """Class containing message data and metadata. This class acts like an
    envelope with the sending address, recipient(s), and the actual message.

    :param sender: The address that sent the message.
    :param recipients: List of addresses to receive the message.
    :param message: :class:`email.message.Message` object containing message
                    contents and headers.

    """

    def __init__(self, sender=None, recipients=None, message=None):
        #: Sending address of the message.
        self.sender = sender

        #: List of recipient addresses of the message.
        self.recipients = recipients or []

        #: :class:`email.message.Message` object with message headers and data.
        self.message = message

        #: Hostname of the :mod:`slimta` server that received the message. 
        self.receiver = None

        #: Timestamp when the message was received.
        self.timestamp = None


# vim:et:fdm=marker:sts=4:sw=4:ts=4
