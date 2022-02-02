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

from collections import OrderedDict
from functools import partial

import pycares
import pycares.errno
import gevent
from gevent import select
from gevent.event import AsyncResult  # type: ignore

from slimta import logging

__all__ = ['DNSError', 'DNSResolver']


class DNSError(Exception):
    """Exception raised with DNS resolution failed. The exception message will
    contain more information.

    .. attribute:: errno

       The error number, as per :mod:`pycares.errno`.

    """

    def __init__(self, errno):
        str_error = pycares.errno.strerror(errno)
        if isinstance(str_error, bytes):
            str_error = str_error.decode('utf-8')
        msg = '{0} [{1}]'.format(str_error, pycares.errno.errorcode[errno])
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
    def _distinct(cls, read_fds, write_fds):
        seen = set()
        for fd in read_fds:
            if fd not in seen:
                yield fd
                seen.add(fd)
        for fd in write_fds:
            if fd not in seen:
                yield fd
                seen.add(fd)

    @classmethod
    def _register_fds(cls, poll, prev_fds_map):
        assert cls._channel is not None
        # we must mimic the behavior of pycares sock_state_cb to maintain
        # compatibility with custom DNSResolver.channel objects.
        fds_map = OrderedDict()
        _read_fds, _write_fds = cls._channel.getsock()
        read_fds = set(_read_fds)
        write_fds = set(_write_fds)
        for fd in cls._distinct(_read_fds, _write_fds):
            event = 0
            if fd in read_fds:
                event |= select.POLLIN
            if fd in write_fds:
                event |= select.POLLOUT
            fds_map[fd] = event
            prev_event = prev_fds_map.pop(fd, 0)
            if event != prev_event:
                poll.register(fd, event)
        for fd in prev_fds_map:
            poll.unregister(fd)
        return fds_map

    @classmethod
    def _wait_channel(cls):
        assert cls._channel is not None
        poll = select.poll()
        fds_map = OrderedDict()
        try:
            while True:
                fds_map = cls._register_fds(poll, fds_map)
                if not fds_map:
                    break
                timeout = cls._channel.timeout()
                if not timeout:
                    cls._channel.process_fd(pycares.ARES_SOCKET_BAD,
                                            pycares.ARES_SOCKET_BAD)
                    continue
                for fd, event in poll.poll(timeout):
                    if event & (select.POLLIN | select.POLLPRI):
                        cls._channel.process_fd(fd, pycares.ARES_SOCKET_BAD)
                    if event & select.POLLOUT:
                        cls._channel.process_fd(pycares.ARES_SOCKET_BAD, fd)
        except Exception:
            logging.log_exception(__name__)
            cls._channel.cancel()
            cls._channel = None
            raise
        finally:
            cls._thread = None


# vim:et:fdm=marker:sts=4:sw=4:ts=4
