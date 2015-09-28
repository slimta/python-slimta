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

"""Package defining a generic SMTP server class that can be used on a
pre-connected socket. This works by calling optionally-defined callbacks in
certain situations (typically when a client sends various commands).

"""

from __future__ import absolute_import

import re

from gevent.ssl import SSLError
from gevent.socket import timeout as socket_timeout
from gevent import Timeout
from pysasl import SASLAuth

from . import SmtpError, ConnectionLost
from .datareader import DataReader
from .io import IO
from .extensions import Extensions
from .auth import ServerAuthError, AuthSession
from .reply import *

__all__ = ['Server']

from_pattern = re.compile(r'^[fF][rR][oO][mM]:\s*<')
to_pattern = re.compile(r'^[tT][oO]:\s*<')
param_keyword_pattern = re.compile(r'\b([a-zA-Z0-9][a-zA-Z0-9-]*)')
param_value_pattern = re.compile(r'\=([\x21-\x3C\x3E-\x7F]+)')


def find_outside_quotes(haystack, needle, start_i=0, quotes='"'):
    quoted = None
    h_len = len(haystack)
    n_len = len(needle)
    for i in xrange(start_i, h_len-n_len+1):
        if not quoted:
            if haystack[i:i+n_len] == needle:
                return i
            for quote in quotes:
                if haystack[i] == quote:
                    quoted = quote
                    break
        elif haystack[i] == quoted:
                quoted = None
    return -1


class Server(object):
    """Class that implements an SMTP server given a connected socket. This
    object has an ``extensions`` attribute that is an |Extensions| object that
    contains the SMTP extensions the server supports.

    :param socket: Connected socket for the session.
    :type socket: :class:`gevent.socket.socket`
    :param handlers: Object with methods that will be called when
                     corresponding SMTP commands are received. These methods
                     can modify the |Reply| before the command response is
                     sent.
    :param auth: If True, enable authentication with default mechanisms. May
                 also be given as a list of SASL mechanism names to support,
                 e.g. ``['PLAIN', 'LOGIN', 'CRAM-MD5']``.
    :param tls: Optional dictionary of TLS settings passed directly as
                keyword arguments to :class:`gevent.ssl.SSLSocket`.
    :param tls_immediately: If True, the socket will be encrypted
                            immediately.
    :param tls_wrapper: Optional function that takes a socket and the ``tls``
                        dictionary, creates a new encrypted socket, performs
                        the TLS handshake, and returns it. The default uses
                        :class:`~gevent.ssl.SSLSocket`.
    :type tls_immediately: True or False
    :param command_timeout: Optional timeout waiting for a command to be
                            sent from the client.
    :param data_timeout: Optional timeout waiting for data to be sent from
                         the client.

    """

    def __init__(self, socket, handlers, auth=False,
                 tls=None, tls_immediately=False, tls_wrapper=None,
                 command_timeout=None, data_timeout=None):
        self.handlers = handlers
        self.extensions = Extensions()

        self.io = IO(socket, tls_wrapper)

        self.have_mailfrom = None
        self.have_rcptto = None
        self.ehlo_as = None
        self.authed = False

        self.extensions.add('8BITMIME')
        self.extensions.add('PIPELINING')
        self.extensions.add('ENHANCEDSTATUSCODES')
        if tls and not tls_immediately:
            self.extensions.add('STARTTLS')
        if auth:
            if isinstance(auth, list):
                auth_obj = SASLAuth(auth)
            else:
                auth_obj = SASLAuth()
            auth_session = AuthSession(auth_obj, self.io)
            self.extensions.add('AUTH', auth_session)

        if tls:
            self.tls = tls.copy()
            self.tls.setdefault('server_side', True)
        else:
            self.tls = None
        self.tls_immediately = tls_immediately

        self.command_timeout = command_timeout
        self.data_timeout = data_timeout or command_timeout

    @property
    def encrypted(self):
        """True if the session transport is encrypted, False otherwise."""
        return self.io.encrypted

    def _recv_command(self):
        with Timeout(self.command_timeout):
            return self.io.recv_command()

    def _get_message_data(self):
        max_size = self.extensions.getparam('SIZE', filter=int)
        reader = DataReader(self.io, max_size)

        err = None
        with Timeout(self.data_timeout):
            try:
                data = reader.recv()
            except ConnectionLost:
                raise
            except SmtpError as e:
                data = None
                err = e

        reply = Reply('250', '2.6.0 Message Accepted for Delivery')
        self._call_custom_handler('HAVE_DATA', reply, data, err)

        self.io.send_reply(reply)
        self.io.flush_send()

        self.have_mailfrom = None
        self.have_rcptto = None

    def _encrypt_session(self):
        if not self.io.encrypt_socket(self.tls):
            return False
        self._call_custom_handler('TLSHANDSHAKE')
        return True

    def _handle_command(self, which, arg):
        method = '_command_'+which
        if hasattr(self, method):
            return getattr(self, method)(arg)
        else:
            return self._command_custom(which, arg)

    def _call_custom_handler(self, which, *args):
        if hasattr(self.handlers, which):
            return getattr(self.handlers, which)(*args)

    def handle(self):
        """Runs through the SMTP session, receiving commands, calling handlers,
        and sending responses.

        :raises: :class:`~slimta.smtp.ConnectionLost` or unhandled exceptions.

        """
        if self.tls and self.tls_immediately:
            if not self._encrypt_session():
                tls_failure.send(self.io, flush=True)
                return

        command, arg = 'BANNER_', None
        while True:
            try:
                try:
                    if command:
                        self._handle_command(command, arg)
                    else:
                        unknown_command.send(self.io)
                except StopIteration:
                    break
                except ConnectionLost:
                    raise
                except Exception as e:
                    unhandled_error.send(self.io)
                    raise
                finally:
                    self.io.flush_send()

                command, arg = self._recv_command()
            except Timeout:
                timed_out.send(self.io)
                self.io.flush_send()
                raise ConnectionLost()

    def _gather_params(self, remaining):
        params = {}
        pos = 0
        while True:
            match = param_keyword_pattern.search(remaining, pos)
            if not match:
                break
            param_keyword = match.group(1).upper()
            pos = match.end(0)
            value_match = param_value_pattern.match(remaining, pos)
            if value_match:
                param_value = value_match.group(1)
                params[param_keyword] = param_value
                pos = value_match.end(0)
            else:
                params[param_keyword] = True
        return params

    def _command_BANNER_(self, arg):
        reply = Reply('220', 'ESMTP server')
        reply.enhanced_status_code = False
        self._call_custom_handler('BANNER_', reply)

        reply.send(self.io)

        if reply.code != '220':
            self._call_custom_handler('CLOSE')
            raise StopIteration()

    def _command_EHLO(self, ehlo_as):
        reply = Reply('250', 'Hello {0}'.format(ehlo_as))
        reply.enhanced_status_code = False
        self._call_custom_handler('EHLO', reply, ehlo_as)

        # Add extension list to message, if successful.
        if reply.code == '250':
            reply.message = self.extensions.build_string(reply.message)

            self.have_mailfrom = None
            self.have_rcptto = None
            self.ehlo_as = ehlo_as

        reply.send(self.io)

    def _command_HELO(self, ehlo_as):
        reply = Reply('250', 'Hello {0}'.format(ehlo_as))
        reply.enhanced_status_code = False
        self._call_custom_handler('HELO', reply, ehlo_as)

        if reply.code == '250':
            self.have_mailfrom = None
            self.have_rcptto = None
            self.ehlo_as = ehlo_as
            self.extensions.reset()

        reply.send(self.io)

    def _command_STARTTLS(self, arg):
        if 'STARTTLS' not in self.extensions:
            unknown_command.send(self.io)
            return

        if arg:
            bad_arguments.send(self.io)
            return

        if not self.ehlo_as:
            bad_sequence.send(self.io)
            return

        reply = Reply('220', '2.7.0 Go ahead')
        self._call_custom_handler('STARTTLS', reply, self.extensions)

        reply.send(self.io, flush=True)

        if reply.code == '220':
            if not self._encrypt_session():
                tls_failure.send(self.io)
                raise StopIteration()
            self.ehlo_as = None
            self.extensions.drop('STARTTLS')

    def _command_AUTH(self, arg):
        if 'AUTH' not in self.extensions:
            unknown_command.send(self.io)
            return
        if not self.ehlo_as or self.authed or self.have_mailfrom:
            bad_sequence.send(self.io)
            return
        auth = self.extensions.getparam('AUTH')

        try:
            result = auth.server_attempt(arg)
        except ValueError:
            bad_arguments.send(self.io)
            return
        except ServerAuthError as e:
            e.reply.send(self.io)
            return

        reply = Reply('235', '2.7.0 Authentication successful')
        self._call_custom_handler('AUTH', reply, result)
        reply.send(self.io)

        if reply.code == '235':
            self.authed = True

    def _command_MAIL(self, arg):
        match = from_pattern.match(arg)
        if not match:
            bad_arguments.send(self.io)
            return

        start = match.end(0)
        end = find_outside_quotes(arg, '>', start)
        if end == -1:
            bad_arguments.send(self.io)
            return
        address = arg[start:end]

        if not self.ehlo_as:
            bad_sequence.send(self.io)
            return

        if self.have_mailfrom:
            bad_sequence.send(self.io)
            return

        params = self._gather_params(arg[end+1:])

        if 'SIZE' in params:
            try:
                size = int(params['SIZE'])
            except ValueError:
                bad_arguments.send(self.io)
                return
            max_size = self.extensions.getparam('SIZE', filter=int)
            if max_size is not None:
                if size > max_size:
                    m = '5.3.4 Message size exceeds {0} limit'.format(max_size)
                    Reply('552', m).send(self.io)
                    return
            else:
                unknown_parameter.send(self.io)
                return

        reply = Reply('250', '2.1.0 Sender <{0}> Ok'.format(address))
        self._call_custom_handler('MAIL', reply, address, params)

        reply.send(self.io)

        self.have_mailfrom = self.have_mailfrom or (reply.code == '250')

    def _command_RCPT(self, arg):
        match = to_pattern.match(arg)
        if not match:
            bad_arguments.send(self.io)
            return

        start = match.end(0)
        end = find_outside_quotes(arg, '>', start)
        if end == -1:
            bad_arguments.send(self.io)
            return
        address = arg[start:end]

        if not self.have_mailfrom:
            bad_sequence.send(self.io)
            return

        params = self._gather_params(arg[end+1:])

        reply = Reply('250', '2.1.5 Recipient <{0}> Ok'.format(address))
        self._call_custom_handler('RCPT', reply, address, params)

        reply.send(self.io)

        self.have_rcptto = self.have_rcptto or (reply.code == '250')

    def _command_DATA(self, arg):
        if arg:
            bad_arguments.send(self.io)
            return

        if not self.have_mailfrom or not self.have_rcptto:
            bad_sequence.send(self.io)
            return

        reply = Reply('354', 'Start mail input; end with <CRLF>.<CRLF>')
        self._call_custom_handler('DATA', reply)

        reply.send(self.io)
        self.io.flush_send()

        if reply.code == '354':
            self._get_message_data()

    def _command_RSET(self, arg):
        if arg:
            bad_arguments.send(self.io)
            return

        reply = Reply('250', 'Ok')
        self._call_custom_handler('RSET', reply)

        if reply.code == '250':
            self.have_mailfrom = None
            self.have_rcptto = None

        reply.send(self.io)

    def _command_NOOP(self, arg):
        reply = Reply('250', 'Ok')
        self._call_custom_handler('NOOP', reply)

        reply.send(self.io)

    def _command_QUIT(self, arg):
        if arg:
            bad_arguments.send(self.io)
            return

        reply = Reply('221', 'Bye')
        self._call_custom_handler('QUIT', reply)

        reply.send(self.io)

        if reply.code == '221':
            self._call_custom_handler('CLOSE')
            raise StopIteration()

    def _command_custom(self, command, arg):
        reply = Reply()
        reply.copy(unknown_command)
        self._call_custom_handler(command, reply, arg, self)

        reply.send(self.io)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
