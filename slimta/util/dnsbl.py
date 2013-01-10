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

__all__ = ['DnsBlackholeList']

import gevent
import dns.resolver
from dns.exception import DNSException
from gevent.pool import Pool
from gevent.event import Event


class DnsBlackholeList(object):
    """Class to check one DNSBL. This object also supports the membership test
    protocol, so it would support a check like ``'127.0.0.1' in dnsbl``.

    :param address: The DNSBL domain name.

    """
    
    def __init__(self, address):
        self.address = address

    def _reverse_ip_octets(self, ip):
        return four, three, two, one

    def _build_query(self, ip):
        one, two, three, four = ip.split('.', 3)
        return '.'.join([four, three, two, one, self.address])

    def __contains__(self, ip):
        try:
            return self.get(ip, timeout=10.0)
        except gevent.Timeout:
            return False

    def get(self, ip, timeout=None):
        """Checks this DNSBL for the given IP address. This method does not
        check the answer, only that the response was not ``NXDOMAIN``.

        :param ip: The IP address string to check.
        :param timeout: A timeout in seconds before ``False`` is returned.
        :returns: ``True`` if the query succeeded and the result was not
                  ``NXDOMAIN``, ``False`` otherwise.

        """
        with gevent.Timeout(timeout, None):
            query = self._build_query(ip)
            try:
                answers = dns.resolver.query(query, 'A')
            except dns.resolver.NXDOMAIN:
                return False
            else:
                return True
        return False

    def get_reason(self, ip, timeout=None):
        """Gets the TXT record for the IP address on this DNSBL. This is usually
        a reason for why the IP address matched. As such, this function should
        only be called after :meth:`.get()` returns ``True``.

        :param ip: The IP address to get a match reason for.
        :param timeout: A timeout in seconds before giving up.
        :returns: A string with the reason, or ``None``.

        """
        with gevent.Timeout(timeout):
            query = self._build_query(ip)
            try:
                answers = dns.resolver.query(query, 'TXT')
            except DNSException:
                pass
            else:
                for txt in answers:
                    return str(txt)


class DnsBLGroup(object):
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
        self.dnsbls.append(DnsBlackholeList(address))

    def _run_dnsbl_get(self, matches, dnsbl, ip):
        if dnsbl.get(ip):
            matches.add(dnsbl.address)

    def _run_dnsbl_get_reason(self, matches, dnsbl, ip):
        reasons[dnsbl.address] = dnsbl.get_reason(ip)

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

    def get_reason(self, matches, ip, timeout=None):
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


# vim:et:fdm=marker:sts=4:sw=4:ts=4
