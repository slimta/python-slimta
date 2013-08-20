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

"""This module provides a basis for implementing WSGI_ applications that are
automatically logged with :mod:`slimta.logging.http`.

.. _WSGI: http://wsgi.readthedocs.org/en/latest/
.. _variables: http://www.python.org/dev/peps/pep-0333/#environ-variables

"""

from __future__ import absolute_import

import sys

from gevent.pywsgi import WSGIServer as GeventWSGIServer

from slimta import logging

__all__ = ['WsgiServer']

log = logging.getHttpLogger(__name__)


class WsgiServer(object):
    """Implements the base class for a WSGI server that logs its requests and
    responses and can easily be deployed as a functioning HTTP server.

    Instances of this class can be used as applications in WSGI server engines,
    or :meth:`.build_server` can be used.

    """

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
        return GeventWSGIServer(listener, self, log=sys.stdout, spawn=spawn,
                                **tls)

    def handle(self, environ, start_response):
        """Overridden by sub-classes to handle WSGI requests and generate a
        response. This method should be used as if it were the WSGI application
        function.

        :param environ: The WSGI environment variables_.
        :param start_response: Call this function to initiate the WSGI
                               response.
        :returns: An iterable of raw data parts to return with the response.

        """
        raise NotImplementedError()

    def __call__(self, environ, start_response):
        """When this object is used as a WSGI application, this method logs the
        request and ensures that the response will be logged as well. The
        request is then proxied to :meth:`.handle` for processing.

        """
        log.wsgi_request(environ)

        def logged_start_response(status, headers, *args, **kwargs):
            log.wsgi_response(environ, status, headers)
            return start_response(status, headers, *args, **kwargs)
        return self.handle(environ, logged_start_response)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
