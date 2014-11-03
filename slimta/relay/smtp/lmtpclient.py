# Copyright (c) 2014 Ian C. Good
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

from socket import getfqdn

from gevent import Timeout

from slimta.smtp.client import LmtpClient
from .client import SmtpRelayClient
from . import SmtpRelayError

__all__ = ['LmtpRelayClient']

hostname = getfqdn()


class LmtpRelayClient(SmtpRelayClient):

    _client_class = LmtpClient

    def _ehlo(self):
        with Timeout(self.command_timeout):
            lhlo = self.client.lhlo(self.ehlo_as)
        if lhlo.is_error():
            raise SmtpRelayError.factory(lhlo)

    def _deliver(self, result, envelope):
        rcpt_results = [None] * len(envelope.recipients)
        try:
            self._handle_encoding(envelope)
            self._send_envelope(rcpt_results, envelope)
            data_results = self._send_message_data(envelope)
        except SmtpRelayError as e:
            result.set_exception(e)
            self._rset()
            return
        had_errors = False
        for rcpt, reply in data_results:
            if reply.is_error():
                i = envelope.recipients.index(rcpt)
                rcpt_results[i] = SmtpRelayError.factory(reply)
                had_errors = True
        result.set(rcpt_results)
        if had_errors:
            self._rset()


# vim:et:fdm=marker:sts=4:sw=4:ts=4
