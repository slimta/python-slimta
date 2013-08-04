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

.. _WSGI: http://wsgi.readthedocs.org/en/latest/
.. _file object: http://docs.python.org/2/library/stdtypes.html#file-objects

"""

from __future__ import absolute_import

import sys

from gevent.pywsgi import WSGIServer

from slimta import logging
from . import HttpError

__all__ = ['WsgiResponse', 'WsgiServer']

log = logging.getHttpLogger(__name__)


class WsgiResponse(HttpEror):
    """This exception can be explicitly raised to end the WSGI request and
    return the given response.

    :param status: The HTTP status string to return, e.g. ``200 OK``.
    :param headers: List of ``(name, value)`` header tuples to return.
    :param data: Optional iterable of raw data parts to return.

    """

    def __init__(self, status, headers=None, data=None):
        super(WsgiResponse, self).__init__(status)
        self.status = status
        self.headers = headers or []
        self.data = data or []


def _header_name_to_cgi(name):
    return 'HTTP_{0}'.format(name.upper().replace('-', '_'))


def _cgi_to_header_name(name):
    parts = name.split('_')
    return '-'.join([part.capitalize() for part in parts[1:]])


class WsgiServer(object):
    """Implements the base class for a WSGI server that logs its requests and
    responses and can easily be deployed as a functioning HTTP server.

    Instances of this class can be used as applications in WSGI server engines,
    or :meth:`.build_server` can be used.

    """

    split_pattern = re.compile(r'\s*[,;]\s*')

    #: List of header names that should be expected in client requests. If this
    #: list is left empty, all headers passed in by the client are passed in to
    #: :meth:`.handle`.
    expected_headers = []

    def __init__(self):
        super(WsgiServer, self).__init__()

    def handle(self, method, path, headers, data_fp):
        """Override in sub-classes to handle a request and provide a response.
        These requests and responses are automatically logged by
        :class:`slimta.logging.http`.

        This function should raise :exc:`WsgiResponse` to return a response to
        the request. If the exception is not raised, ``200 OK`` is returned by
        default.

        :param method: This is the HTTP verb given in the request.
        :param path: This is the selector path given in the request.
        :param headers: This is a dictionary of headers given in the request,
                        using standard header hyphens and capitalization (e.g.
                        ``X-Example-Header``. The values are flattened into a
                        single string, CGI-style.
                        
                        If :attr:`.expected_headers` is set, the keys in this
                        dictionary will be the headers given in that list, with
                        ``None`` as the value if the header was not provided in
                        the request.
        :param data_fp: This is a `file object`_ that will read the raw request
                        data, if desired.
        :raises: :exc:`WsgiResponse`

        """
        raise NotImplementedError()

    def build_server(self, listener, pool=None, tls=None):
        """Constructs and returns a WSGI server engine, configured to use the
        current object as its application.

        :param listener: Usually a ``(ip, port)`` tuple defining the interface
                         and port upon which to listen for connections.
        :param pool: If given, defines a specific :class:`gevent.pool.Pool` to
                     use for new greenlets.
        :param tls: Optional dictionary of TLS settings passed directly as
                    keyword arguments to :class:`gevent.ssl.SSLSocket`.
        :rtype: :class:`gevent.pywsgi.WSGIServer`

        """
        spawn = pool or 'default'
        tls = tls or {}
        return WSGIServer(listener, self, log=sys.stdout, spawn=spawn, **tls)

    def __call__(self, environ, start_response):
        log.wsgi_request(environ)
        method = environ['REQUEST_METHOD'].upper()
        path = environ.get('PATH_INFO', '')
        headers = self._load_headers(environ)
        data_fp = environ.get('wsgi.input')
        try:
            self.handle(method, path, headers, data_fp)
            status = '200 OK'
            headers = []
            data = []
        except WsgiResponse as res:
            status = res.status
            headers = res.headers
            data = res.data
        log.wsgi_response(environ, status, headers)
        return data

    def _load_headers(self, environ):
        ret = {'Content-Length': environ.get('CONTENT_LENGTH'),
               'Content-Type': environ.get('CONTENT_TYPE')}
        if self.expected_headers:
            for name in self.expected_headers:
                cgi_name = _header_name_to_cgi(name)
                ret[name] = environ.get(cgi_name)
        else:
            for key, value in environ.iteritems():
                if key.startswith('HTTP_'):
                    name = _cgi_to_header_name(key)
                    ret[name] = value
        return ret


# vim:et:fdm=marker:sts=4:sw=4:ts=4
