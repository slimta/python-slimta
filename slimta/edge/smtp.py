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

from __future__ import absolute_import

import gevent
from gevent.server import StreamServer
from dns import reversename
from dns.resolver import NXDOMAIN

from slimta import logging
from slimta.envelope import Envelope
from slimta.smtp.server import Server
from slimta.smtp.reply import unknown_command, bad_sequence
from slimta.smtp import ConnectionLost, MessageTooBig
from slimta.queue import QueueError
from slimta.relay import RelayError
from slimta.util import dns_resolver
from . import EdgeServer

__all__ = ['SmtpEdge', 'SmtpValidators']


class SmtpValidators(object):
    """Base class for implementing SMTP command validators.

    Sub-classes may implement some or all of the following functions. Leaving
    the `reply` argument untouched will return the default, successful reply
    from the command.

    - ``handle_banner(reply, address)``: Validate connecting address before
      sending the SMTP banner.
    - ``handle_ehlo(reply, ehlo_as)``: Validate the EHLO string.
    - ``handle_helo(reply, helo_as)``: Validate the HELO string.
    - ``handle_mail(reply, sender, params)``: Validate the sender address.
    - ``handle_rcpt(reply, recipient, params)``: Validate one recipient address.
    - ``handle_data(reply)``: Any remaining validation before receiving data.
    - ``handle_have_data(reply, data)``: Validate the received message data.
    - ``handle_rset(reply)``: Called before replying to an RSET command.
    - ``handle_tls()``: Called after a successful TLS handshake. This may be at
      the beginning of the session or after a `STARTTLS` command.

    :param session: When sub-classes are instantiated, instances are passed
                    this object, stored and described in :attr:`session` below,
                    that have useful information about the current session.

    """

    def __init__(self, session):
        #: This instance attribute is an object that has its own set of
        #: attributes which may be useful in validation:
        #:
        #:  - ``address``: The address tuple of the connecting client.
        #:  - ``extended_smtp``: The client used EHLO instead of HELO.
        #:  - ``security``: Security of connection, ``None`` or ``'TLS'``.
        #:  - ``ehlo_as``: The EHLO or HELO string given by the client.
        #:  - ``auth_result``: The authentication result returned by |Auth|
        #:                     after successful authentication, or ``None`` if
        #:                     the client has not authenticated.
        #:  - ``envelope``: The |Envelope| being pieced together to send by the
        #:                  connecting client.
        self.session = session


class SmtpSession(object):

    def __init__(self, address, validator_class, handoff):
        self.extended_smtp = False
        self.security = None
        self.address = address
        self.reverse_address = None
        self.handoff = handoff
        self.validators = validator_class(self) if validator_class else None

        self.envelope = None
        self.ehlo_as = None
        self.auth_result = None

    def _call_validator(self, command, *args):
        method = 'handle_'+command
        if hasattr(self.validators, method):
            getattr(self.validators, method)(*args)

    @property
    def protocol(self):
        proto = 'SMTP'
        if self.extended_smtp:
            proto = 'ESMTP'
        if self.security == 'TLS':
            proto += 'S'
        if self.auth_result is not None:
            proto += 'A'
        return proto

    def _ptr_lookup(self):
        try:
            ptraddr = reversename.from_address(self.address[0])
            try:
                answers = dns_resolver.query(ptraddr, 'PTR')
            except NXDOMAIN:
                answers = []
            try:
                self.reverse_address = str(answers[0])
            except IndexError:
                pass
        except Exception:
            logging.log_exception(__name__, query=self.address[0])

    def _trigger_ptr_lookup(self):
        self._ptr_lookup_thread = gevent.spawn(self._ptr_lookup)

    def BANNER_(self, reply):
        self._trigger_ptr_lookup()
        self._call_validator('banner', reply, self.address)

    def EHLO(self, reply, ehlo_as):
        self._call_validator('ehlo', reply, ehlo_as)
        self.extended_smtp = True
        if reply.code == '250':
            self.ehlo_as = ehlo_as
            self.envelope = None

    def HELO(self, reply, helo_as):
        self._call_validator('helo', reply, helo_as)
        if reply.code == '250':
            self.ehlo_as = helo_as
            self.envelope = None

    def TLSHANDSHAKE(self):
        self._call_validator('tls')
        self.security = 'TLS'

    def AUTH(self, reply, result):
        self.auth_result = result

    def RSET(self, reply):
        self.envelope = None

    def MAIL(self, reply, address, params):
        try:
            self._call_validator('mail', reply, address, params)
        except TypeError:
            # XXX: Temporary for backwards-compatibility.
            self._call_validator('mail', reply, address)
        if reply.code == '250':
            self.envelope = Envelope(sender=address)

    def RCPT(self, reply, address, params):
        try:
            self._call_validator('rcpt', reply, address, params)
        except TypeError:
            # XXX: Temporary for backwards-compatibility.
            self._call_validator('rcpt', reply, address)
        if reply.code == '250':
            self.envelope.recipients.append(address)

    def DATA(self, reply):
        self._call_validator('data', reply)

    def HAVE_DATA(self, reply, data, err):
        if isinstance(err, MessageTooBig):
            reply.code = '552'
            reply.message = '5.3.4 Message exceeded size limit'
            return
        elif err:
            raise err

        self._call_validator('have_data', reply, data)
        if reply.code != '250':
            return

        self.envelope.client['ip'] = self.address[0]
        self.envelope.client['host'] = self.reverse_address
        self.envelope.client['name'] = self.ehlo_as
        self.envelope.client['protocol'] = self.protocol
        self.envelope.client['auth'] = self.auth_result
        if hasattr(self, '_ptr_lookup_thread'):
            self._ptr_lookup_thread.kill(block=False)

        self.envelope.parse(data)

        results = self.handoff(self.envelope)
        if isinstance(results[0][1], QueueError):
            reply.code = '550'
            reply.message = '5.6.0 Error queuing message'
        elif isinstance(results[0][1], RelayError):
            relay_reply = results[0][1].reply
            reply.copy(relay_reply)
        else:
            reply.message = '2.6.0 Message accepted for delivery'

        self.envelope = None


class SmtpEdge(EdgeServer):
    """Class that uses :mod:`slimta.smtp.server` to implement an edge
    service to receive messages.

    :param listener: ``(ip, port)`` tuple to listen on, as described in
                     |EdgeServer|.
    :param queue: |Queue| object for handing off messages, as described in
                  :meth:`~slimta.edge.Edge.handoff()`.
    :param pool: Optional greenlet pool, as described in |Edge|.
    :param max_size: Maximum size of incoming messages.
    :param validator_class: :class:`SmtpValidators` sub-class to validate
                            commands and alter replies.
    :param auth_class: Optional |Auth| sub-class to enable server
                       authentication.
    :param tls: Optional dictionary of TLS settings passed directly as
                keyword arguments to :class:`gevent.ssl.SSLSocket`.
    :param tls_immediately: If True, connections will be encrypted
                            immediately before the SMTP banner.
    :param command_timeout: Seconds before the connection times out waiting
                            for a command.
    :param data_timeout: Seconds before the connection times out while
                         receiving data. This is a cumulative timeout that
                         is not tricked by the client sending data.
    :param hostname: String identifying the local machine. See |Edge| for more
                     details.

    """

    def __init__(self, listener, queue, pool=None, max_size=None,
                 validator_class=None, auth_class=None,
                 tls=None, tls_immediately=False,
                 command_timeout=None, data_timeout=None,
                 hostname=None):
        super(SmtpEdge, self).__init__(listener, queue, pool, hostname)
        self.max_size = max_size
        self.command_timeout = command_timeout
        self.data_timeout = data_timeout
        self.validator_class = validator_class
        self.auth_class = auth_class
        self.tls = tls
        self.tls_immediately = tls_immediately

    def handle(self, socket, address):
        try:
            handlers = SmtpSession(address, self.validator_class, self.handoff)
            smtp_server = Server(socket, handlers, self.auth_class,
                                 self.tls, self.tls_immediately,
                                 command_timeout=self.command_timeout,
                                 data_timeout=self.data_timeout)
            if self.max_size:
                smtp_server.extensions.add('SIZE', self.max_size)
            smtp_server.handle()
        except ConnectionLost:
            pass
        finally:
            smtp_server.io.close()


# vim:et:fdm=marker:sts=4:sw=4:ts=4
