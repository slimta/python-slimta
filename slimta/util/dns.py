# Copyright (c) 2015 Ian C. Good
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

"""This module implements DNS resolution with :mod:`pycares`.

"""

from __future__ import absolute_import

from functools import partial

import pycares
import pycares.errno
import gevent
from gevent import select
from gevent.event import AsyncResult

from slimta import logging

__all__ = ['DNSError', 'DNSResolver']


class DNSError(Exception):
    """Exception raised with DNS resolution failed. The exception message will
    contain more information.

    .. attribute:: errno

       The error number, as per :mod:`pycares.errno`.

    """

    def __init__(self, errno):
        msg = '{0} [{1}]'.format(pycares.errno.strerror(errno),
                                 pycares.errno.errorcode[errno])
        super(DNSError, self).__init__(msg)
        self.errno = errno


class DNSResolver(object):
    """Manages all the active DNS queries using a single, static
    :class:`pycares.Channel` object.

    .. attribute:: channel

       Before making any queries, this attribute may be set to override the
       default with a :class:`pycares.Channel` object that will manage all DNS
       queries.

    """

    channel = None
    _channel = None
    _thread = None

    @classmethod
    def query(cls, name, query_type):
        """Begin a DNS lookup. The result (or exception) will be in the
        returned :class:`~gevent.event.AsyncResult` when it is available.

        :param name: The DNS name to resolve.
        :type name: str
        :param query_type: The DNS query type, see
                           :meth:`pycares.Channel.query` for options. A string
                           may be given instead, e.g. ``'MX'``.
        :rtype: :class:`~gevent.event.AsyncResult`

        """
        result = AsyncResult()
        query_type = cls._get_query_type(query_type)
        cls._channel = cls._channel or cls.channel or pycares.Channel()
        cls._channel.query(name, query_type, partial(cls._result_cb, result))
        cls._thread = cls._thread or gevent.spawn(cls._wait_channel)
        return result

    @classmethod
    def _get_query_type(cls, query_type):
        if isinstance(query_type, str):
            type_attr = 'QUERY_TYPE_{0}'.format(query_type.upper())
            return getattr(pycares, type_attr)
        return query_type

    @classmethod
    def _result_cb(cls, result, answer, errno):
        if errno:
            exc = DNSError(errno)
            result.set_exception(exc)
        else:
            result.set(answer)

    @classmethod
    def _wait_channel(cls):
        try:
            while True:
                read_fds, write_fds = cls._channel.getsock()
                if not read_fds and not write_fds:
                    break
                timeout = cls._channel.timeout()
                if not timeout:
                    cls._channel.process_fd(pycares.ARES_SOCKET_BAD,
                                            pycares.ARES_SOCKET_BAD)
                    continue
                rlist, wlist, xlist = select.select(
                    read_fds, write_fds, [], timeout)
                for fd in rlist:
                    cls._channel.process_fd(fd, pycares.ARES_SOCKET_BAD)
                for fd in wlist:
                    cls._channel.process_fd(pycares.ARES_SOCKET_BAD, fd)
        except Exception:
            logging.log_exception(__name__)
            cls._channel.cancel()
            cls._channel = None
            raise
        finally:
            cls._thread = None


# vim:et:fdm=marker:sts=4:sw=4:ts=4
