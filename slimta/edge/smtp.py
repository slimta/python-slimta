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

"""Implements an |Edge| that receives messages with the SMTP protocol.
Attempts to follow the SMTP server RFCs.

"""

import time
import email.parser

import gevent
from gevent.server import StreamServer
from gevent.socket import gethostname

from slimta.envelope import Envelope
from slimta.edge import Edge
from slimta.smtp.server import Server
from slimta.smtp.reply import unknown_command, bad_sequence
from slimta.smtp import MessageTooBig

__all__ = ['SmtpEdge']


class Handlers(object):

    def __init__(self, address, validators, handoff):
        self.protocol = 'SMTP'
        self.security = 'none'
        self.address = address
        self.validators = validators
        self.handoff = handoff

        self.envelope = None
        self.ehlo_as = None
        self.authed = None

    def _call_validator(self, command, *args):
        method = 'handle_'+command
        if hasattr(self.validators, method):
            getattr(self.validators, method)(*args)

    def _modify_protocol_string(self, change):
        old = self.protocol
        if old == 'SMTP' and change == 'EHLO':
            self.protocol = 'ESMTP'
        elif old == 'SMTP' and change == 'STARTTLS':
            self.protocol = 'SMTPS'
        elif old == 'SMTPS' and change == 'EHLO':
            self.protocol = 'ESMTPS'
        elif old == 'ESMTP' and change == 'STARTTLS':
            self.protocol = 'ESMTPS'
        elif old == 'ESMTP' and change == 'AUTH':
            self.protocol = 'ESMTPA'
        elif old == 'ESMTPA' and change == 'STARTTLS':
            self.protocol = 'ESMTPSA'
        elif old == 'ESMTPS' and change == 'AUTH':
            self.protocol = 'ESMTPSA'

    def BANNER(self, reply):
        self._call_validator('banner', reply, self.address)

    def EHLO(self, reply, ehlo_as):
        self._call_validator('ehlo', reply, ehlo_as)
        self._modify_protocol_string('EHLO')
        if reply.code == '250':
            self.ehlo_as = ehlo_as
            self.envelope = None

    def HELO(self, reply, helo_as):
        self._call_validator('helo', reply, ehlo_as)
        if reply.code == '250':
            self.ehlo_as = ehlo_as
            self.envelope = None

    def TLSHANDSHAKE(self, reply, extensions):
        self._call_validator('tls', reply)
        self._modify_protocol_string('STARTTLS')
        self.security = 'TLS'

    def AUTH(self, reply, server):
        if 'AUTH' not in server.extensions:
            reply.copy(unknown_command)
            return
        if not self.ehlo_as or self.authed or server.have_mailfrom:
            reply.copy(bad_sequence)
            return

        reply.code = '235'
        reply.message = '2.7.0 Authentication successful'

    def RSET(self, reply):
        self.envelope = None

    def MAIL(self, reply, address):
        self._call_validator('mail', reply, address)
        if reply.code == '250':
            self.envelope = Envelope(sender=address)

    def RCPT(self, reply, address):
        self._call_validator('rcpt', reply, address)
        if reply.code == '250':
            self.envelope.recipients.append(address)

    def DATA(self, reply):
        self._call_validator('data', reply)

    def HAVE_DATA(self, reply, data, err):
        if isinstance(err, MessageTooBig):
            reply.code == '552'
            reply.message = '5.3.4 Message exceeded size limit'
            return
        elif err:
            raise err

        self.envelope.edge_hostname = gethostname()
        self.envelope.timestamp = time.time()
        self.envelope.message = message = email.parser.Parser().parsestr(data)

        if 'from' not in message:
            message['from'] = self.envelope.sender

        if self.handoff:
            self.handoff(self.envelope, reply)
        else:
            reply.code = '250'
            reply.message = '2.6.0 Message discarded'

        self.envelope = None


class SmtpEdge(Edge):
    """Class that uses :mod:`slimta.smtp.server` to implement an edge
    service to receive messages.

    The ``validators`` argument is an object that may implement some or
    all of the following functions. Leaving the `reply` argument
    untouched will return the default, successful reply from the
    command.
    
    * ``handle_banner(reply, address)``: Validate connecting address before
      sending the SMTP banner.
    * ``handle_ehlo(reply, ehlo_as)``: Validate the EHLO string.
    * ``handle_helo(reply, helo_as)``: Validate the HELO string.
    * ``handle_mail(reply, sender)``: Validate the sender address.
    * ``handle_rcpt(reply, recipient)``: Validate one recipient address.
    * ``handle_data(reply)``: Any remaining validation before accepting data.
    * ``handle_rset(reply)``: Called before replying to an RSET command.
    * ``handle_tls()``: Called after a successful TLS handshake. This may be at
      the beginning of the session or after a `STARTTLS` command.

    :param listener: ``(ip, port)`` tuple to listen on, as described in |Edge|.
    :param handoff: Called with new messages, as described in |Edge|.
    :param pool: Optional greenlet pool, as described in |Edge|.
    :param validators: Object with ``handle_xxxx()`` methods as described.
    :param command_timeout: Seconds before the connection times out waiting
                            for a command.
    :param data_timeout: Seconds before the connection times out while
                         receiving data. This is a cumulative timeout that
                         is not tricked by the client sending data.

    """

    def __init__(self, listener, handoff, pool=None, validators=None,
                                 command_timeout=None, data_timeout=None):
        super(SmtpEdge, self).__init__(listener, handoff, pool)
        self.command_timeout = command_timeout
        self.data_timeout = data_timeout
        self.validators = validators

    def _handle(self, socket, address):
        try:
            handlers = Handlers(address, self.validators, self.handoff)
            smtp_server = Server(socket, handlers,
                                 command_timeout=self.command_timeout,
                                 data_timeout=self.data_timeout)
            smtp_server.handle()
        finally:
            socket.close()


# vim:et:fdm=marker:sts=4:sw=4:ts=4
