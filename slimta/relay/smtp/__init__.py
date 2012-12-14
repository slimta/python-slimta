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

"""Relays messages to a destination using the SMTP protocol. Moving messages
from hop top hop with SMTP is the foundation of how email works. Picking the
next hop is typically done with MX records in DNS, but often configurations will
involve local static routing.

"""

from gevent.queue import PriorityQueue
from gevent.event import AsyncResult
from gevent.coros import Semaphore, DummySemaphore

from slimta.relay import RelayError, TransientRelayError, PermanentRelayError

__all__ = ['SmtpRelayError']


class SmtpRelayError(RelayError):

    def __init__(self, type, reply):
        self.reply = reply
        msg = '{0} failure on {1}: {2}'.format(type, reply.command, str(reply))
        super(SmtpRelayError, self).__init__(msg)

    @staticmethod
    def factory(reply):
        if reply.code == '5':
            return SmtpPermanentRelayError(reply)
        else:
            return SmtpTransientRelayError(reply)


class SmtpTransientRelayError(SmtpRelayError, TransientRelayError):

    def __init__(self, reply):
        super(SmtpTransientRelayError, self).__init__('Transient', reply)


class SmtpPermanentRelayError(SmtpRelayError, PermanentRelayError):

    def __init__(self, reply):
        super(SmtpPermanentRelayError, self).__init__('Permanent', reply)


class StaticSmtpRelay(object):

    def __init__(self, host, port=25, pool_size=None, client_class=None):
        if client_class:
            self.client_class = client_class
        else:
            from slimta.relay.smtp.client import SmtpRelayClient
            self.client_class = SmtpRelayClient
        self.host = host
        self.port = port
        self.queue = PriorityQueue()
        self.limit = Semaphore(pool_size) if pool_size else DummySemaphore()
        self.pool = set()

    def _remove_client(self, client):
        self.pool.remove(client)
        self.limit.release()
        if not self.queue.empty() and not self.pool:
            self._add_client()

    def _add_client(self):
        self.limit.acquire()
        client = self.client_class((self.host, self.port), self.queue,
                                   idle_timeout=10)
        client.start()
        client.link(self._remove_client)
        self.pool.add(client)

    def _check_idle(self):
        if not self.limit.locked():
            for client in self.pool:
                if client.idle:
                    break
            else:
                    self._add_client()

    def attempt(self, envelope, attempts):
        self._check_idle()
        result = AsyncResult()
        self.queue.put((1, result, envelope))
        return result.get()


# vim:et:fdm=marker:sts=4:sw=4:ts=4
