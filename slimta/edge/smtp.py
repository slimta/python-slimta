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

from slimta.envelope import Envelope
from slimta.smtp.server import Server
from slimta.smtp.reply import Reply
from slimta.smtp import ConnectionLost, MessageTooBig
from slimta.queue import QueueError
from slimta.relay import RelayError
from slimta.util.ptrlookup import PtrLookup
from . import EdgeServer

__all__ = ['SmtpEdge', 'SmtpValidators']


class SmtpValidators(object):
    """Base class for implementing SMTP command validators.

    Sub-classes may implement some or all of the following functions. Leaving
    the `reply` argument untouched will return the default, successful reply
    from the command. Setting the response code to ``421`` or ``221`` will
    close the connection.

    .. _RFC 2821 4.2: https://tools.ietf.org/html/rfc2821#section-4.2
    .. seealso:: `RFC 2821 4.2`_

    - ``handle_banner(reply, address)``: Validate connecting address before
      sending the SMTP banner.
    - ``handle_ehlo(reply, ehlo_as)``: Validate the EHLO string.
    - ``handle_helo(reply, helo_as)``: Validate the HELO string.
    - ``handle_auth(reply, creds)``: Validate an authentication attempt, given
      a :class:`~pysasl.AuthenticationCredentials` object.
    - ``handle_mail(reply, sender, params)``: Validate the sender address.
    - ``handle_rcpt(reply, recipient, params)``: Validate one recipient
      address.
    - ``handle_data(reply)``: Any remaining validation before receiving data.
    - ``handle_have_data(reply, data)``: Validate the received message data.
    - ``handle_queued(reply, results)``: Once the message has been queued,
      modify the returned |Reply| using the ``results`` from calling
      :meth:`~slimta.queue.Queue.enqueue`.
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
        #:  - ``auth``: A tuple of the form ``(authcid, authzid)`` if the
        #:              client has authenticated.
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
        self.auth = None

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
        if self.auth:
            proto += 'A'
        return proto

    def BANNER_(self, reply):
        self._ptr_lookup = PtrLookup(self.address[0])
        self._ptr_lookup.start()
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

    def AUTH(self, reply, creds):
        self._call_validator('auth', reply, creds)
        if reply.code == '235':
            self.auth = creds.authcid

    def RSET(self, reply):
        self.envelope = None

    def MAIL(self, reply, address, params):
        self._call_validator('mail', reply, address, params)
        if reply.code == '250':
            self.envelope = Envelope(sender=address)

    def RCPT(self, reply, address, params):
        self._call_validator('rcpt', reply, address, params)
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
        self.envelope.client['auth'] = self.auth

        self.envelope.parse(data)

        results = self.handoff(self.envelope)
        if isinstance(results[0][1], QueueError):
            default_reply = Reply('451', '4.3.0 Error queuing message')
            queue_reply = getattr(results[0][1], 'reply', default_reply)
            reply.copy(queue_reply)
        elif isinstance(results[0][1], RelayError):
            relay_reply = results[0][1].reply
            reply.copy(relay_reply)
        else:
            reply.message = '2.6.0 Message accepted for delivery'
        self._call_validator('queued', reply, results)

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
    :param auth: If True, enable authentication with default mechanisms. May
                 also be given as a list of SASL mechanism names to support,
                 e.g. ``['PLAIN', 'LOGIN', 'CRAM-MD5']``.
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
                 validator_class=None, auth=False,
                 tls=None, tls_immediately=False,
                 command_timeout=None, data_timeout=None,
                 hostname=None):
        super(SmtpEdge, self).__init__(listener, queue, pool, hostname)
        self.max_size = max_size
        self.command_timeout = command_timeout
        self.data_timeout = data_timeout
        self.validator_class = validator_class
        self.auth = auth
        self.tls = tls
        self.tls_immediately = tls_immediately

    def handle(self, socket, address):
        smtp_server = None
        try:
            handlers = SmtpSession(address, self.validator_class, self.handoff)
            smtp_server = Server(socket, handlers, self.auth,
                                 self.tls, self.tls_immediately,
                                 command_timeout=self.command_timeout,
                                 data_timeout=self.data_timeout)
            if self.max_size:
                smtp_server.extensions.add('SIZE', self.max_size)
            smtp_server.handle()
        except ConnectionLost:
            pass
        finally:
            if smtp_server:
                smtp_server.io.close()


# vim:et:fdm=marker:sts=4:sw=4:ts=4
