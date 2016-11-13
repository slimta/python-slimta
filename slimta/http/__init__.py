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

from socket import error as socket_error

from gevent import socket

from slimta.util.pycompat import httplib, urlparse

__all__ = ['HTTPConnection', 'HTTPSConnection', 'get_connection']


class HTTPConnection(httplib.HTTPConnection):
    """Modified version of the :py:class:`httplib.HTTPConnection` class that
    uses gevent sockets. This attempts to avoid the complete re-implementation
    that ships in :mod:`gevent.httplib`.

    """

    def __init__(self, host, port=None, *args, **kwargs):
        httplib.HTTPConnection.__init__(self, host, port, *args, **kwargs)
        self._create_connection = socket.create_connection


class HTTPSConnection(httplib.HTTPSConnection):
    """Modified version of the :py:class:`httplib.HTTPSConnection` class that
    uses gevent sockets.

    """

    def __init__(self, host, port=None, *args, **kwargs):
        httplib.HTTPSConnection.__init__(self, host, port, *args, **kwargs)
        self._create_connection = socket.create_connection

    def close(self):
        if self.sock:
            try:
                self.sock.unwrap()
            except socket_error as e:
                if e.errno != 0:
                    raise
        httplib.HTTPSConnection.close(self)


def get_connection(url, context=None):
    """This convenience functions returns a :class:`HTTPConnection` or
    :class:`HTTPSConnection` based on the information contained in URL.

    :param url: URL string to create a connection for. Alternatively, passing
                in the results of :py:func:`urlparse.urlsplit` works as well.
    :param context: Used to wrap sockets with SSL encryption, when the URL
                    scheme is ``https``.
    :type context: :py:class:`~ssl.SSLContext`

    """
    if isinstance(url, (str, bytes)):
        url = urlparse.urlsplit(url, 'http')
    host = url.netloc or 'localhost'

    if url.scheme == 'https':
        conn = HTTPSConnection(host, context=context)
    else:
        conn = HTTPConnection(host)
    return conn


# vim:et:fdm=marker:sts=4:sw=4:ts=4
