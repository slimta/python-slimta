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

"""Package providing an alternative to the standard |Queue| class, such that
messages are not written to storage but instead immediately relayed. An |Edge|
service will have to wait for a message to finish relaying before its reply can
be issued.

"""

from __future__ import absolute_import

import uuid

from slimta.relay import RelayError
from . import QueueError


class ProxyQueue(object):
    """Class implementing the same interface as |Queue|, but proxies a message
    to a |Relay| service instead of storing and trying/retrying delivery.

    :param relay: |Relay| object used to attempt message deliveries.

    """

    def __init__(self, relay):
        self.relay = relay

    def add_policy(self, *args):
        msg = 'ProxyQueue objects do not support add_policy()'
        raise NotImplementedError(msg)

    def start(self):
        # No-op, because this class does not inherit from Greenlet. Provided
        # for backwards compatibility with the standard Queue class.
        pass

    def kill(self):
        # No-op, because this class does not inherit from Greenlet. Provided
        # for backwards compatibility with the standard Queue class.
        pass

    def flush(self):
        # No-op, because this class does not maintain an actual queue. Provided
        # for backwards compatibility with the standard Queue class.
        pass

    def enqueue(self, envelope):
        try:
            self.relay._attempt(envelope, 0)
        except RelayError as e:
            return [(envelope, e)]
        else:
            return [(envelope, uuid.uuid4().hex)]


# vim:et:fdm=marker:sts=4:sw=4:ts=4
