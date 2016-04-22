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

from socket import getfqdn, error as socket_error
from functools import wraps

from gevent import Timeout
from gevent.socket import create_connection

from slimta.smtp import SmtpError
from slimta.smtp.reply import Reply, timed_out, connection_failed
from slimta.smtp.client import Client
from slimta import logging
from ..pool import RelayPoolClient
from . import SmtpRelayError

__all__ = ['SmtpRelayClient']

log = logging.getSocketLogger(__name__)
hostname = getfqdn()


def current_command(cmd):
    def deco(old_f):
        @wraps(old_f)
        def new_f(self, *args, **kwargs):
            prev = self.current_command
            self.current_command = cmd
            ret = old_f(self, *args, **kwargs)
            self.current_command = prev
            return ret
        return new_f
    return deco


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
        self.socket_creator = socket_creator or create_connection
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
        self.current_command = None

    @current_command(b'[CONNECT]')
    def _connect(self):
        with Timeout(self.connect_timeout):
            self.socket = self.socket_creator(self.address)
        log.connect(self.socket, self.address)
        self.client = self._client_class(self.socket, self.tls_wrapper,
                                         self.address)

    @current_command(b'[BANNER]')
    def _banner(self):
        with Timeout(self.command_timeout):
            banner = self.client.get_banner()
        if banner.is_error():
            raise SmtpRelayError.factory(banner)

    @current_command(b'EHLO')
    def _ehlo(self):
        try:
            ehlo_as = self.ehlo_as(self.address)
        except TypeError:
            ehlo_as = self.ehlo_as
        with Timeout(self.command_timeout):
            ehlo = self.client.ehlo(ehlo_as)
        if ehlo.is_error():
            raise SmtpRelayError.factory(ehlo)

    @current_command(b'STARTTLS')
    def _starttls(self):
        with Timeout(self.command_timeout):
            starttls = self.client.starttls(self.tls)
        if starttls.is_error() and self.tls_required:
            raise SmtpRelayError.factory(starttls)

    @current_command(b'AUTH')
    def _authenticate(self):
        try:
            credentials = self.credentials()
        except TypeError:
            credentials = self.credentials
        with Timeout(self.command_timeout):
            auth = self.client.auth(*credentials)
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

    @current_command(b'RSET')
    def _rset(self):
        with Timeout(self.command_timeout):
            self.client.rset()

    @current_command(b'MAIL')
    def _mailfrom(self, sender):
        with Timeout(self.command_timeout):
            mailfrom = self.client.mailfrom(sender)
        if mailfrom and mailfrom.is_error():
            raise SmtpRelayError.factory(mailfrom)
        return mailfrom

    @current_command(b'RCPT')
    def _rcptto(self, rcpt):
        with Timeout(self.command_timeout):
            return self.client.rcptto(rcpt)

    @current_command(b'DATA')
    def _data(self):
        with Timeout(self.command_timeout):
            return self.client.data()

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

    @current_command(b'[SEND_DATA]')
    def _send_empty_data(self):
        with Timeout(self.data_timeout):
            self.client.send_empty_data()

    @current_command(b'[SEND_DATA]')
    def _send_message_data(self, envelope):
        header_data, message_data = envelope.flatten()
        with Timeout(self.data_timeout):
            send_data = self.client.send_data(
                header_data, message_data)
        self.client._flush_pipeline()
        if isinstance(send_data, Reply) and send_data.is_error():
            raise SmtpRelayError.factory(send_data)
        return send_data

    def _handle_encoding(self, envelope):
        if '8BITMIME' not in self.client.extensions:
            try:
                envelope.encode_7bit(self.binary_encoder)
            except UnicodeError:
                reply = Reply('554', '5.6.3 Conversion not allowed',
                              command=b'[data conversion]',
                              address=self.address)
                raise SmtpRelayError.factory(reply)

    def _send_envelope(self, rcpt_results, envelope):
        data = None
        mailfrom = self._mailfrom(envelope.sender)
        rcpttos = [self._rcptto(rcpt) for rcpt in envelope.recipients]
        try:
            data = self._data()
            self._check_replies(mailfrom, rcpttos, data)
        except SmtpRelayError:
            if data and not data.is_error():
                self._send_empty_data()
            raise
        for i, rcpt_reply in enumerate(rcpttos):
            rcpt = envelope.recipients[i]
            if rcpt_reply.is_error():
                rcpt_results[rcpt] = SmtpRelayError.factory(rcpt_reply)

    def _deliver(self, result, envelope):
        rcpt_results = dict.fromkeys(envelope.recipients)
        try:
            self._handle_encoding(envelope)
            self._send_envelope(rcpt_results, envelope)
            msg_result = self._send_message_data(envelope)
        except SmtpRelayError as e:
            result.set_exception(e)
            self._rset()
        else:
            for key, value in rcpt_results.items():
                if value is None:
                    rcpt_results[key] = msg_result
            result.set(rcpt_results)

    def _check_server_timeout(self):
        try:
            if self.client.has_reply_waiting():
                with Timeout(self.command_timeout):
                    self.client.get_reply()
                return True
        except SmtpError:
            return True
        return False

    def _disconnect(self):
        try:
            with Timeout(self.command_timeout):
                self.client.quit()
        except (Timeout, Exception):
            pass
        finally:
            if self.client:
                self.client.io.close()

    def _get_error_reply(self, exc):
        try:
            if self.client.last_error.code == '421':
                return self.client.last_error
        except Exception:
            pass
        return Reply('421', '4.3.0 '+str(exc),
                     command=self.current_command, address=self.address)

    def _run(self):
        result, envelope = self.poll()
        if not result:
            return
        reraise = True
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
                reply = self._get_error_reply(e)
                relay_error = SmtpRelayError.factory(reply)
                result.set_exception(relay_error)
        except Timeout:
            if not result.ready():
                reply = Reply(command=self.current_command,
                              address=self.address).copy(timed_out)
                relay_error = SmtpRelayError.factory(reply)
                result.set_exception(relay_error)
        except socket_error as exc:
            log.error(self.socket, exc, self.address)
            if not result.ready():
                reply = Reply(command=self.current_command,
                              address=self.address).copy(connection_failed)
                relay_error = SmtpRelayError.factory(reply)
                result.set_exception(relay_error)
        except Exception as e:
            if not result.ready():
                result.set_exception(e)
            reraise = False
            raise
        finally:
            try:
                self._disconnect()
            except Exception:
                if reraise:
                    raise


# vim:et:fdm=marker:sts=4:sw=4:ts=4
