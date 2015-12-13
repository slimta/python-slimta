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

"""Utilities to make logging consistent and easy for WSGI-style requests and
responses as well as more general HTTP logs.

"""

from __future__ import absolute_import

from functools import partial

__all__ = ['HttpLogger']


class HttpLogger(object):
    """Provides a limited set of log methods that :mod:`slimta` packages may
    use. This prevents free-form logs from mixing in with standard, machine-
    parseable logs.

    :param log: :py:class:`logging.Logger` object to log through.

    """

    def __init__(self, log):
        from slimta.logging import logline
        self.log = partial(logline, log.debug, 'http')

    def _get_method_from_environ(self, environ):
        return environ['REQUEST_METHOD'].upper()

    def _get_path_from_environ(self, environ):
        return environ.get('PATH_INFO', None)

    def _get_headers_from_environ(self, environ):
        ret = []
        for key, value in environ.items():
            if key == 'CONTENT_TYPE':
                ret.append(('Content-Type', value))
            elif key == 'CONTENT_LENGTH':
                ret.append(('Content-Length', value))
            elif key.startswith('HTTP_'):
                parts = key.split('_')
                name = '-'.join([part.capitalize() for part in parts[1:]])
                ret.append((name, value))
        return ret

    def wsgi_request(self, environ):
        """Logs a WSGI-style request. This method pulls the appropriate info
        from ``environ`` and passes it to :meth:`.request`.

        :param environ: The environment data.

        """
        method = self._get_method_from_environ(environ)
        path = self._get_path_from_environ(environ)
        headers = self._get_headers_from_environ(environ)
        self.request(environ, method, path, headers, is_client=False)

    def wsgi_response(self, environ, status, headers):
        """Logs a WSGI-style response. This method passes its given info along
        to :meth:`.response`.

        :param environ: The environment data.
        :param status: The status line given to the client, e.g.
                       ``404 Not Found``.
        :param headers: The headers returned in the response.

        """
        self.response(environ, status, headers, is_client=False)

    def request(self, conn, method, path, headers, is_client=True):
        """Logs an HTTP request.

        :param conn: The same object should be passed in this parameter to both
                     this method and to its corresponding :meth:`.response`.
                     There are no constraints on its type or value.
        :type conn: :py:class:`object`
        :param method: The request method string.
        :param path: The path string.
        :param headers: A list of ``(name, value)`` header tuples given in the
                        request.
        :param is_client: Whether or not the log line should be identified as a
                          client- or server-side request.
        :type is_client: :py:class:`bool`

        """
        type = 'client_request' if is_client else 'server_request'
        self.log(id(conn), type, method=method, path=path, headers=headers)

    def response(self, conn, status, headers, is_client=True):
        """Logs an HTTP response.

        :param conn: The same object should be passed in this parameter to both
                     this method and to its corresponding :meth:`.request`.
                     There are no constraints on its type or value.
        :type conn: :py:class:`object`
        :param status: The status string of the response, e.g. ``200 OK``.
        :param headers: A list of ``(name, value)`` header tuples given in the
                        response.
        :param is_client: Whether or not the log line should be identified as a
                          client- or server-side request.
        :type is_client: :py:class:`bool`

        """
        type = 'client_response' if is_client else 'server_response'
        self.log(id(conn), type, status=status, headers=headers)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
