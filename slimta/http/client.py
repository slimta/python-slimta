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

"""

"""

from __future__ import absolute_import

import re
import urlparse
from httplib import HTTPConnection
from base64 import b64encode

import gevent
from gevent import socket, ssl

from slimta import logging

__all__ = ['get_connection']

log = logging.getHttpLogger(__name__)


class GeventHTTPConnection(HTTPConnection):
    # This class attempts to avoid the complete re-implementation of httplib
    # that comes included with gevent.

    def connect(self):
        self.sock = socket.create_connection((self.host,self.port),
                                             self.timeout, self.source_address)
        if self._tunnel_host:
            self._tunnel()


class GeventHTTPSConnection(HTTPConnection):
    # This class makes HTTPS connections more robust and capable of certificate
    # verification that the standard httplib library is incapable of doing.

    def __init__(self, *args, **kwargs):
        self.tls = kwargs.pop('tls', None)
        HTTPConnection.__init__(self, *args, **kwargs)

    def connect(self):
        sock = socket.create_connection((self.host,self.port),
                                        self.timeout, self.source_address)
        self.sock = ssl.SSLSocket(sock, **self.tls)
        self.sock.do_handshake()
        if self._tunnel_host:
            self._tunnel()

    def close(self):
        if self.sock:
            try:
                self.sock.unwrap()
            except socket.error as (errno, message):
                if errno != 0:
                    raise
        HTTPConnection.close(self)


class HttpClient(object):
    """This class will open connections, submit requests, and receive responses
    using the HTTP or HTTPS protocols, based on the URL passed in.

    :param url: URL string to be parsed with :py:func:`urlparse.urlsplit` with
                the default scheme string ``'http'``. Any extra path or query
                string in the URL is ignored.

    """

    def __init__(self, url):
        super(HttpClient, self).__init__()
        self.url = urlparse.urlsplit(url, 'http')

    def _get_connection(self):
        host = self.url.netloc or 'localhost'
        host = host.rsplit(':', 1)[0]
        port = self.url.port
        if self.url.scheme.lower() == 'https':
            conn = GeventHTTPSConnection(host, port, strict=True,
                                         **self.relay.tls)
        else:
            conn = GeventHTTPConnection(host, port, strict=True)
        return conn

    def send(self, method, path, headers, data_parts):
        """Constructs and sends an HTTP request.

        :param method: The method string, e.g. ``'POST'``.
        :param path: The selector path string.
        :param headers: List of ``(name, value)`` header tuples.
        :param data_parts: Iterable of raw data parts to send with the request.

        """
        if not self.conn:
            self.conn = self._get_connection()
        log.request(self.conn, method, path, headers)
        self.conn.putrequest(method, path)
        for name, value in headers:
            self.conn.putheader(name, value)
        data_iter = iter(data_parts)
        self.conn.endheaders(next(data_iter, None))
        for part in data_iter:
            self.conn.send(part)

    def recv(self):
        """Receives and parses the response from the previous HTTP request.

        :returns: Tuple of three items, the status line, a list of header
                  tuples, and the raw :class:`~httplib.HTTPResponse` object to
                  read the response data from.

        """
        response = self.conn.getresponse()
        status = '{0!s} {1}'.format(response.status, response.reason)
        headers = response.getheaders()
        log.response(self.conn, status, headers)
        return status, headers, response

    def close(self):
        """Ends the connection and closes the socket. Subsequent calls to
        :meth:`.send` will open a new connection."""
        self.conn.close()
        self.conn = None


# vim:et:fdm=marker:sts=4:sw=4:ts=4
