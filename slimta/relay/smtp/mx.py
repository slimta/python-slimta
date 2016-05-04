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

"""Implements an algorithm to query and pick an MX record to delivery a
message.  The MX record is calculated by pulling the domain-name from the
recipient's email address (or first recipient, if multiple) and querying DNS
for the domain MX email routing records. If multiple records exist, the pick is
made by using the number of delivery attempts to cycle through the options.

"""

from __future__ import absolute_import

import time

from pycares.errno import ARES_ENOTFOUND, ARES_ENODATA

from slimta import logging
from slimta.smtp.reply import Reply
from slimta.util import validate_tls
from slimta.util.dns import DNSResolver, DNSError
from .. import TransientRelayError, PermanentRelayError, Relay
from .static import StaticSmtpRelay

__all__ = ['MxSmtpRelay']


class NoDomainError(PermanentRelayError):
    """Thrown by :class:`MxSmtpRelay` delivery attempts when the recipient
    address is not a valid email address. A valid email address shall have
    exactly one un-quoted ``@`` character dividing localpart and domain.

    :param recipient: The invalid recipient address that generated the error,
                      also stored as the ``recipient`` attribute of the raised
                      exception.

    """
    def __init__(self, recipient):
        msg = 'Recipient address has no domain: '+recipient
        reply = Reply('550', '5.1.5 '+msg, command='RCPT')
        super(NoDomainError, self).__init__(msg, reply)
        self.recipient = recipient


class MxRecord(object):

    def __init__(self, domain):
        self.domain = domain
        self._records = None
        self._expiration = 0

    def get(self):
        if self.expired:
            self._records, self._expiration = self._resolve()
        if not self._records:
            msg = 'No usable DNS records found: '+self.domain
            raise ValueError(msg)
        return self._records

    def _resolve_a(self):
        answer = DNSResolver.query(self.domain, 'A').get()
        expiration = 0
        now = time.time()
        ret = []
        for rdata in answer:
            ret.append((0, str(rdata.host)))
            expiration = max(expiration, now + rdata.ttl)
        return ret, expiration

    def _resolve_mx(self):
        answer = DNSResolver.query(self.domain, 'MX').get()
        expiration = 0
        now = time.time()
        ret = []
        for rdata in answer:
            for i, rec in enumerate(ret):
                if rec[0] > rdata.priority:
                    ret.insert(i, (rdata.priority, str(rdata.host)))
                    break
            else:
                ret.append((rdata.priority, str(rdata.host)))
            expiration = max(expiration, now + rdata.ttl)
        return ret, expiration

    def _resolve(self):
        non_fatal_errors = (ARES_ENOTFOUND, ARES_ENODATA)
        try:
            return self._resolve_mx()
        except DNSError as exc:
            if exc.errno in non_fatal_errors:
                try:
                    return self._resolve_a()
                except DNSError as exc:
                    if exc.errno in non_fatal_errors:
                        return None, 0
                    raise
            raise

    @property
    def expired(self):
        return not self._expiration or time.time() >= self._expiration


class MxSmtpRelay(Relay):
    """Delivers messages based on the MX records of their recipients. Keeps an
    expiring cache of resolved MX records to prevent DNS overuse, and uses a
    :class:`~slimta.relay.smtp.static.StaticSmtpRelay` object for each
    destination to recycle and limit connections.

    All arguments are optional.

    :param tls: Optional dictionary of TLS settings passed directly as
                keyword arguments to :class:`gevent.ssl.SSLSocket`.
    :param tls_required: If given and True, it should be considered a delivery
                         failure if TLS cannot be negotiated by the client.
    :param connect_timeout: Timeout in seconds to wait for a client connection
                            to be successful before issuing a transient
                            failure.
    :param command_timeout: Timeout in seconds to wait for a reply to each SMTP
                            command before issuing a transient failure.
    :param data_timeout: Timeout in seconds to wait for a reply to message data
                         before issuing a transient failure.
    :param idle_timeout: Timeout in seconds after a message is delivered before
                         a QUIT command is sent and the connection terminated.
                         If another message should be delivered before this
                         timeout expires, the connection will be re-used. By
                         default, QUIT is sent immediately and connections are
                         never re-used.
    :param socket_creator: Optional function to use instead of
                           :py:func:`~socket.create_connection` for creating
                           sockets.
    :param ehlo_as: The string to send as the EHLO or HELO string. Defaults to
                    the FQDN of the system. This may also be given as a
                    function that will be executed with the destination address
                    at the beginning of each connection.
    :param binary_encoder: Optional function from :mod:`email.encoders` used as
                           an argument to
                           :meth:`~slimta.envelope.Envelope.encode_7bit` when
                           conversion is necessary for the remote server.

    """

    def __init__(self, tls=None, **client_kwargs):
        super(MxSmtpRelay, self).__init__()
        self._mx_records = {}
        self._force_mx = {}
        self._relayers = {}
        self._client_kwargs = client_kwargs
        self._client_kwargs['tls'] = validate_tls(tls)

    def _get_rcpt_domain(self, envelope):
        rcpt = envelope.recipients[0]
        try:
            localpart, domain = rcpt.rsplit('@', 1)
            return domain.lower()
        except ValueError:
            raise NoDomainError(rcpt)

    def new_static_relay(self, destination, port):
        """Return a new :class:`~slimta.relay.smtp.static.StaticSmtpRelay`
        object for the given destination. This method can be overriden to
        provide extra arguments, such as limiting the number of concurrent
        connections.

        :param destination: The hostname to relay to.
        :param port: The delivery port on the destination.

        """
        return StaticSmtpRelay(destination, port=port, **self._client_kwargs)

    def choose_mx(self, records, attempts):
        """Chooses a record based on the number of delivery attempts on the
        message. As provided, this method cycle through the records trying
        each one once, but this method can be overriden.

        :param records: List of tuples ``(pref, host)`` sorted by preference.
        :param attempts: The number of delivery attempts this message has
                         undergone.
        :returns: The ``host`` that was picked from the list.
        :rtype: str

        """
        i = attempts % len(records)
        return records[i][1]

    def force_mx(self, domain, destination, port=25):
        """Do not do MX record lookups for the given ``domain``, instead always
        use ``destination`` for delivery.

        :param domain: Domain to force.
        :param destination: Destination hostname.
        :param port: Port number on the destination.

        """
        self._force_mx[domain.lower()] = (destination, port)

    def attempt(self, envelope, attempts):
        domain = self._get_rcpt_domain(envelope)
        if domain in self._force_mx:
            dest, port = self._force_mx[domain]
        else:
            record = self._mx_records.setdefault(domain, MxRecord(domain))
            try:
                dest = self.choose_mx(record.get(), attempts)
            except ValueError as exc:
                msg = str(exc)
                reply = Reply('550', '5.1.2 '+msg)
                raise PermanentRelayError(msg, reply)
            except DNSError:
                logging.log_exception(__name__)
                msg = 'DNS lookup failed'
                reply = Reply('451', '4.4.3 '+msg)
                raise TransientRelayError(msg, reply)
            port = 25
        try:
            relayer = self._relayers[(dest, port)]
        except KeyError:
            relayer = self.new_static_relay(dest, port)
            self._relayers[(dest, port)] = relayer
        return relayer.attempt(envelope, attempts)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
