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

"""This module provides classes to check DNSBLs_ for IP addresses or hosts.
These lists can be hugely helpful and inexpensive ways of filtering spam.

.. _DNSBLs: http://en.wikipedia.org/wiki/DNSBL

"""

from __future__ import absolute_import

from functools import wraps

import gevent
from gevent.pool import Pool, Group
from pycares.errno import ARES_ENOTFOUND

from slimta import logging
from slimta.util.dns import DNSResolver, DNSError

__all__ = ['DnsBlocklist', 'DnsBlocklistGroup', 'check_dnsbl']


class DnsBlocklist(object):
    """Class to check one DNSBL. This object provides ``__contains__`` and
    ``__getitem__`` protocols, so it supports simpler usage::

        if '123.4.56.7' in dnsbl:
            reason = dnsbl['123.4.56.7']

    .. note::

       Because ``__getitem__`` simply calls :meth:`.get_reason()`, it
       will never raise a :class:`KeyError` and should only be used after using
       :meth:`.get()` or ``__contains__``.

    :param address: The DNSBL domain name.

    """

    def __init__(self, address):
        self.address = address

    def _build_query(self, ip):
        one, two, three, four = ip.split('.', 3)
        return '.'.join([four, three, two, one, self.address])

    def __contains__(self, ip):
        return self.get(ip, timeout=10.0)

    def __getitem__(self, ip):
        return self.get_reason(ip, timeout=10.0)

    def get(self, ip, timeout=None, strict=False):
        """Checks this DNSBL for the given IP address. This method does not
        check the answer, only that the response was not ``NXDOMAIN``.

        :param ip: The IP address string to check.
        :param timeout: A timeout in seconds before ``False`` is returned.
        :param strict: If ``True``, DNS exceptions that are not ``NXDOMAIN``
                       (including timeouts) will also  result in a ``True``
                       return value.
        :returns: ``True`` if the DNSBL had an entry for the given IP address,
                  ``False`` otherwise.

        """
        with gevent.Timeout(timeout, None):
            query = self._build_query(ip)
            try:
                DNSResolver.query(query, 'A').get()
            except DNSError as exc:
                if exc.errno == ARES_ENOTFOUND:
                    return False
                logging.log_exception(__name__, query=query)
                return not strict
            else:
                return True
        return strict

    def get_reason(self, ip, timeout=None):
        """Gets the TXT record for the IP address on this DNSBL. This is
        usually a reason for why the IP address matched. As such, this function
        should only be called after :meth:`.get()` returns ``True``.

        :param ip: The IP address to get a match reason for.
        :param timeout: A timeout in seconds before giving up.
        :returns: A string with the reason, or ``None``.

        """
        with gevent.Timeout(timeout, None):
            query = self._build_query(ip)
            try:
                answers = DNSResolver.query(query, 'TXT').get()
            except DNSError:
                pass
            else:
                if answers:
                    for rdata in answers:
                        return rdata.text


class DnsBlocklistGroup(object):
    """Allows a group of DNSBLs to be queried simultaneously."""

    def __init__(self, pool=None):
        self.dnsbls = []
        if isinstance(pool, Pool):
            self.pool = pool
        elif pool is None:
            self.pool = gevent
        else:
            self.pool = Pool(pool)

    def add_dnsbl(self, address):
        """Adds a DNSBL domain name to the list of DNSBLs to check.

        :param address: The DNSBL domain name.

        """
        self.dnsbls.append(DnsBlocklist(address))

    def _run_dnsbl_get(self, matches, dnsbl, ip):
        if dnsbl.get(ip):
            matches.add(dnsbl.address)

    def _run_dnsbl_get_reason(self, reasons, dnsbl, ip):
        reasons[dnsbl.address] = dnsbl.get_reason(ip)

    def __contains__(self, ip):
        return bool(self.get(ip, timeout=10.0))

    def get(self, ip, timeout=None):
        """Queries all DNSBLs in the group for matches.

        :param ip: The IP address to check for.
        :param timeout: Timeout in seconds before canceling remaining queries.
        :returns: A :class:`set()` containing the DNSBL domain names that
                  matched a record for the IP address.

        """
        matches = set()
        group = Group()
        with gevent.Timeout(timeout, None):
            for dnsbl in self.dnsbls:
                thread = self.pool.spawn(self._run_dnsbl_get,
                                         matches, dnsbl, ip)
                group.add(thread)
            group.join()
        group.kill()
        return matches

    def get_reasons(self, matches, ip, timeout=None):
        """Gets the reasons for each matching DNSBL for the IP address.

        :param matches: The DNSBL matches, as returned by :meth:`.get()`.
        :param ip: The IP address to get reasons for.
        :param timeout: Timeout in seconds before canceling remaining queries.
        :returns: A :class:`dict()` keyed by the DNSBL domain names from
                  the ``matches`` argument with the values being the reasons
                  each DNSBL matched or ``None``.

        """
        reasons = dict.fromkeys(matches)
        group = Group()
        with gevent.Timeout(timeout, None):
            for dnsbl in self.dnsbls:
                if dnsbl.address in matches:
                    thread = self.pool.spawn(self._run_dnsbl_get_reason,
                                             reasons, dnsbl, ip)
                    group.add(thread)
            group.join()
        group.kill()
        return reasons


def check_dnsbl(address, match_code='550', match_message='5.7.1 Access denied',
                timeout=10.0):
    """Decorator for :class:`~slimta.edge.smtp.SmtpValidators` methods that are
    given a |Reply| object. It will check the current SMTP session's connecting
    IP address against the DNSBL provided at domain name ``address``. If the IP
    matches, set the reply and do not call the validator method.

    :param address: :class:`DnsBlocklist` object, :class:`DnsBlocklistGroup`
                    object, or DNSBL domain name string.
    :param match_code: When the connecting IP address matches, set the |Reply|
                       code to this string.
    :param match_message: When the connecting IP address matches, set the
                          |Reply| message to this string.
    :param timeout: Timeout in seconds before giving up the check.

    """
    if not isinstance(address, DnsBlocklist) and \
       not isinstance(address, DnsBlocklistGroup):
        address = DnsBlocklist(address)

    def new_decorator(f):
        @wraps(f)
        def new_f(self, reply, *args, **kwargs):
            ip = self.session.address[0] or ''
            try:
                ret = address.get(ip, timeout=timeout)
            except ValueError:
                ret = None
            if ret:
                reply.code = match_code
                reply.message = match_message
            else:
                return f(self, reply, *args, **kwargs)
        return new_f
    return new_decorator


# vim:et:fdm=marker:sts=4:sw=4:ts=4
