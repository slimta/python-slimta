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

from slimta.smtp.client import LmtpClient
from .client import SmtpRelayClient

__all__ = ['LmtpRelayClient']


class LmtpRelayClient(SmtpRelayClient):

    _client_class = LmtpClient

    def __init__(self, address, queue, socket_creator=None, ehlo_as=None,
                 tls=None, tls_immediately=False,
                 tls_required=False, tls_wrapper=None,
                 connect_timeout=10.0, command_timeout=10.0,
                 data_timeout=None, idle_timeout=None,
                 credentials=None, binary_encoder=None):
        super(SmtpRelayClient, self).__init__(queue, idle_timeout)
        self.address = address
        if socket_creator:
            self._socket_creator = socket_creator
        self.socket = None
        self.client = None
        self.ehlo_as = ehlo_as or hostname
        self.tls = tls
        self.tls_immediately = tls_immediately
        self.tls_required = tls_required
        self.tls_wrapper = tls_wrapper
        self.connect_timeout = connect_timeout
        self.command_timeout = command_timeout
        self.data_timeout = data_timeout or command_timeout
        self.credentials = credentials
        self.binary_encoder = binary_encoder

    def _ehlo(self):
        with Timeout(self.command_timeout):
            lhlo = self.client.lhlo(self.ehlo_as)
        if lhlo.is_error():
            raise SmtpRelayError.factory(lhlo)

    def _send_message_data(self, envelope):
        header_data, message_data = envelope.flatten()
        with Timeout(self.data_timeout):
            send_data = self.client.send_data(header_data, message_data)
        self.client._flush_pipeline()
        if send_data.is_error():
            raise SmtpRelayError.factory(send_data)
        return send_data

    def _run(self):
        result, envelope = self.poll()
        if not result:
            return
        try:
            self._connect()
            self._handshake()
            while result:
                if self._check_server_timeout():
                    self.queue.appendleft((result, envelope))
                    break
                if self._send_envelope(result, envelope):
                    result.set(True)
                if self.idle_timeout is None:
                    break
                result, envelope = self.poll()
        except SmtpRelayError as e:
            result.set_exception(e)
        except SmtpError as e:
            if not result.ready():
                reply = Reply('421', '4.3.0 {0!s}'.format(e))
                relay_error = SmtpRelayError.factory(reply)
                result.set_exception(relay_error)
        except Timeout:
            if not result.ready():
                relay_error = SmtpRelayError.factory(timed_out)
                result.set_exception(relay_error)
        except Exception as e:
            if not result.ready():
                result.set_exception(e)
            raise
        finally:
            self._disconnect()


# vim:et:fdm=marker:sts=4:sw=4:ts=4
