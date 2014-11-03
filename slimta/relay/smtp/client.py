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

import time
from socket import getfqdn, error as socket_error

import gevent
from gevent import Timeout, Greenlet
from gevent.socket import create_connection

from slimta.smtp import SmtpError
from slimta.smtp.reply import Reply, timed_out
from slimta.smtp.client import Client
from slimta import logging
from ..pool import RelayPoolClient
from . import SmtpRelayError

__all__ = ['SmtpRelayClient']

log = logging.getSocketLogger(__name__)
hostname = getfqdn()


class SmtpRelayClient(RelayPoolClient):

    _client_class = Client

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

    def _socket_creator(self, address):
        socket = create_connection(address)
        log.connect(socket, address)
        return socket

    def _connect(self):
        try:
            with Timeout(self.connect_timeout):
                self.socket = self._socket_creator(self.address)
        except socket_error as (err, msg):
            reply = Reply('451', '4.3.0 Connection failed')
            raise SmtpRelayError.factory(reply)
        self.client = self._client_class(self.socket, self.tls_wrapper)

    def _banner(self):
        with Timeout(self.command_timeout):
            banner = self.client.get_banner()
        if banner.is_error():
            raise SmtpRelayError.factory(banner)

    def _ehlo(self):
        with Timeout(self.command_timeout):
            ehlo = self.client.ehlo(self.ehlo_as)
        if ehlo.is_error():
            raise SmtpRelayError.factory(ehlo)

    def _starttls(self):
        with Timeout(self.command_timeout):
            starttls = self.client.starttls(self.tls)
        if starttls.is_error() and self.tls_required:
            raise SmtpRelayError.factory(starttls)

    def _authenticate(self):
        with Timeout(self.command_timeout):
            if callable(self.credentials):
                auth = self.client.auth(*self.credentials())
            else:
                auth = self.client.auth(*self.credentials)
        if auth.is_error():
            raise SmtpRelayError.factory(auth)

    def _handshake(self):
        if self.tls and self.tls_immediately:
            self.client.encrypt(self.tls)
        self._banner()
        self._ehlo()
        if self.tls and not self.tls_immediately:
            if self.tls_required or 'STARTTLS' in self.client.extensions:
                self._starttls()
                self._ehlo()
        if self.credentials:
            self._authenticate()

    def _rset(self):
        with Timeout(self.command_timeout):
            rset = self.client.rset()

    def _mailfrom(self, sender):
        with Timeout(self.command_timeout):
            mailfrom = self.client.mailfrom(sender)
        if mailfrom and mailfrom.is_error():
            raise SmtpRelayError.factory(mailfrom)
        return mailfrom

    def _rcptto(self, rcpt):
        with Timeout(self.command_timeout):
            return self.client.rcptto(rcpt)

    def _check_replies(self, mailfrom, rcpttos, data):
        if mailfrom.is_error():
            raise SmtpRelayError.factory(mailfrom)
        for rcptto in rcpttos:
            if not rcptto.is_error():
                break
        else:
            raise SmtpRelayError.factory(rcpttos[0])
        if data.is_error():
            raise SmtpRelayError.factory(data)

    def _send_message_data(self, envelope):
        header_data, message_data = envelope.flatten()
        with Timeout(self.data_timeout):
            send_data = self.client.send_data(header_data, message_data)
        self.client._flush_pipeline()
        if isinstance(send_data, Reply) and send_data.is_error():
            raise SmtpRelayError.factory(send_data)
        return send_data

    def _handle_encoding(self, envelope):
        if '8BITMIME' not in self.client.extensions:
            try:
                envelope.encode_7bit(self.binary_encoder)
            except UnicodeDecodeError:
                reply = Reply('554', '5.6.3 Conversion not allowed')
                raise SmtpRelayError.factory(reply)

    def _send_envelope(self, rcpt_results, envelope):
        data = None
        mailfrom = self._mailfrom(envelope.sender)
        rcpttos = [self._rcptto(rcpt) for rcpt in envelope.recipients]
        try:
            with Timeout(self.command_timeout):
                data = self.client.data()
            self._check_replies(mailfrom, rcpttos, data)
        except SmtpRelayError:
            if data and not data.is_error():
                with Timeout(self.data_timeout):
                    self.client.send_empty_data()
            raise
        for i, rcpt_reply in enumerate(rcpttos):
            if rcpt_reply.is_error():
                rcpt_results[i] =  SmtpRelayError.factory(rcpt_reply)

    def _deliver(self, result, envelope):
        rcpt_results = [None] * len(envelope.recipients)
        try:
            self._handle_encoding(envelope)
            self._send_envelope(rcpt_results, envelope)
            self._send_message_data(envelope)
        except SmtpRelayError as e:
            result.set_exception(e)
            self._rset()
        else:
            result.set(rcpt_results)

    def _check_server_timeout(self):
        if self.client.has_reply_waiting():
            with Timeout(self.command_timeout):
                timeout = self.client.get_reply()
            return True

    def _disconnect(self):
        try:
            with Timeout(self.command_timeout):
                self.client.quit()
        except (Timeout, Exception):
            pass
        finally:
            if self.client:
                self.client.io.close()

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
                self._deliver(result, envelope)
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
