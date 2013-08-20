# Copyright (c) 2013 Ian C. Good
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

"""Root package for |slimta| HTTP client and server libraries.

This package contains implementations of HTTP classes from :py:mod:`httplib`
using gevent sockets. These are provided to avoid the complete
re-implementation that ships in :mod:`gevent.httplib`, and to provide a more
similar interface to other slimta libraries that use SSL/TLS.

"""

from __future__ import absolute_import

from httplib import HTTPConnection

from gevent import socket, ssl

from slimta.core import SlimtaError

__all__ = ['HttpError', 'HTTPConnection', 'HTTPSConnection']


class HttpError(SlimtaError):
    """Base exception for all custom HTTP exceptions."""
    pass


class HTTPConnection(HTTPConnection):
    """Modified version of the :py:class:`httplib.HTTPConnection` class that
    uses gevent sockets. This attempts to avoid the complete re-implementation
    that ships in :mod:`gevent.httplib`.

    :param ...: Arguments as passed in to :py:class:`~httplib.HTTPConnection`.

    """

    def connect(self):
        self.sock = socket.create_connection((self.host, self.port),
                                             self.timeout, self.source_address)
        if self._tunnel_host:
            self._tunnel()


class HTTPSConnection(HTTPConnection):
    """Modified version of the :py:class:`httplib.HTTPSConnection` class that
    uses gevent sockets and the more functional ``tls`` parameter.

    :param ...: Arguments as passed in to :py:class:`~httplib.HTTPConnection`.
    :param tls: This keyword argument contains the keyword arguments passed
                into :class:`~gevent.ssl.SSLSocket` when the connection is
                encrypted.

    """

    def __init__(self, *args, **kwargs):
        self.tls = kwargs.pop('tls', None)
        HTTPConnection.__init__(self, *args, **kwargs)

    def connect(self):
        HTTPConnection.connect(self)
        self.sock = ssl.SSLSocket(self.sock, **self.tls)
        self.sock.do_handshake()

    def close(self):
        if self.sock:
            try:
                self.sock.unwrap()
            except socket.error as (errno, message):
                if errno != 0:
                    raise
        HTTPConnection.close(self)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
