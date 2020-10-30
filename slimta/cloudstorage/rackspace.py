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

"""This module defines the queue storage mechanism specific to the `Rackspace
Cloud`_ hosting service. It requires an account as well as the `Cloud Files`_
and optionally the `Cloud Queues`_ services.

For each queued message, the contents and metadata of the message are written
to *Cloud Files*. Upon success, a reference to the message is injected into
*Cloud Queues* as a new message.

The *Cloud Queues* service is only necessary for alerting separate *slimta*
processes that a new message has been queued. If reception and relaying are
happening in the same process, *Cloud Queues* is unnecessary.

::

    auth = RackspaceCloudAuth({'username': 'slimta', 'api_key': 'xxxxxx'},
                              region='IAD')
    cloud_files = RackspaceCloudFiles(auth)
    cloud_queues = RackspaceCloudQueues(auth)

    storage = CloudStorage(cloud_files, cloud_queues)

.. _Rackspace Cloud: http://www.rackspace.com/cloud/
.. _Cloud Files: http://www.rackspace.com/cloud/files/
.. _Cloud Queues: http://www.rackspace.com/cloud/queues/

"""

from __future__ import absolute_import

import uuid
import json
from socket import getfqdn
from functools import partial

from six.moves import cPickle
from six.moves.urllib.parse import urlsplit, urljoin, urlencode

import gevent

from slimta.http import get_connection
from slimta import logging
from . import CloudStorageError

__all__ = ['RackspaceError', 'RackspaceCloudAuth', 'RackspaceCloudFiles',
           'RackspaceCloudQueues']

log = logging.getHttpLogger(__name__)

_DEFAULT_AUTH_ENDPOINT = 'https://identity.api.rackspacecloud.com/v2.0/'
_DEFAULT_CLIENT_ID = str(uuid.uuid5(uuid.NAMESPACE_DNS, getfqdn()))

_TIMESTAMP_HDR = 'X-Object-Meta-Timestamp'
_ATTEMPTS_HDR = 'X-Object-Meta-Attempts'
_DELIVERED_RCPTS_HDR = 'X-Object-Meta-Delivered-Rcpts'


class RackspaceError(CloudStorageError):
    """Thrown when an unexpected status has been returned from a Rackspace
    Cloud API request and the engine does not know how to continue.

    """

    def __init__(self, response):
        status = '{0!s} {1}'.format(response.status, response.reason)
        msg = 'Received {0!r} from the API.'.format(status)
        super(RackspaceError, self).__init__(msg)

        #: The :class:`~httplib.HTTPResponse` object that triggered the
        #: exception.
        self.response = response


class RackspaceCloudAuth(object):
    """This class implements and manages the creation of authentication tokens
    when :class:`RackspaceCloudFiles` or :class:`RackspaceCloudQueues` objects
    require them.

    :param credentials: This dictionary defines how credentials are sent to the
                        Auth API.

                        If the ``function`` key is defined, it must be a
                        callable that takes no arguments and returns a tuple.
                        The tuple must contain a token string, a Cloud Files
                        service endpoint, and a Cloud Queues service endpoint.

                        Otherwise, this dictionary must have a ``username`` key
                        whose value is the Rackspace Cloud username string.

                        The ``password`` key may be used to fetch tokens using
                        the account's password. Alternatively, the ``api_key``
                        key may be used to fetch tokens using the account's API
                        key. With ``username``, either ``password`` or
                        ``api_key`` must be given.

                        Optionally, ``tenant_id`` may also be provided for
                        situations where it is necessary for authentication.
    :type credentials: dict
    :param endpoint: If given, this is the Rackspace Cloud Auth endpoint to hit
                     when creating tokens.
    :param region: When discovering API endpoints from the service catalog,
                   this is the endpoint region to use, e.g. ``IAD`` or ``HKG``.
                   If not given, the first region returned is used.
    :param timeout: Timeout, in seconds, for requests to the Cloud Auth API to
                    create a new token for the session.
    :param tls: Optional dictionary of TLS settings passed directly as keyword
                arguments to :class:`gevent.ssl.SSLSocket`. This is only used
                for URLs with the ``https`` scheme.

    """

    def __init__(self, credentials, endpoint=_DEFAULT_AUTH_ENDPOINT,
                 region=None, timeout=None, tls=None):
        super(RackspaceCloudAuth, self).__init__()
        self.get_connection = get_connection
        self.timeout = timeout
        self.region = region
        self.tls = tls or {}
        self.token_func = None
        self._token_id = None

        if 'function' in credentials:
            self.token_func = credentials['function']
        elif 'username' in credentials:
            username = credentials['username']
            tenant_id = credentials.get('tenant_id')
            if 'password' in credentials:
                password = credentials['password']
                self.token_func = partial(self._get_token_password,
                                          endpoint,
                                          username, password, tenant_id)
            elif 'api_key' in credentials:
                api_key = credentials['api_key']
                self.token_func = partial(self._get_token_api_key,
                                          endpoint,
                                          username, api_key, tenant_id)
        if not self.token_func:
            msg = 'Required keys not found in credentials dictionary.'
            raise KeyError(msg)

        #: The current Cloud Queues API endpoint in use by the mechanism. This
        #: should be populated automatically on authentication.
        self.queues_endpoint = None

        #: The current Cloud Files API endpoint in use by the mechanism. This
        #: should be populated automatically on authentication.
        self.files_endpoint = None

    def _get_token(self, url, payload):
        full_url = urljoin(url+'/', 'tokens')
        parsed_url = urlsplit(full_url, 'http')
        conn = self.get_connection(parsed_url, self.tls)
        json_payload = json.dumps(payload, sort_keys=True)
        headers = [('Host', parsed_url.hostname),
                   ('Content-Type', 'application/json'),
                   ('Content-Length', str(len(json_payload))),
                   ('Accept', 'application/json')]
        with gevent.Timeout(self.timeout):
            log.request(conn, 'POST', parsed_url.path, headers)
            conn.putrequest('POST', parsed_url.path)
            for name, value in headers:
                conn.putheader(name, value)
            conn.endheaders(json_payload)
            res = conn.getresponse()
            status = '{0!s} {1}'.format(res.status, res.reason)
            log.response(conn, status, res.getheaders())
            return self._get_token_response(res)

    def _get_token_response(self, response):
        if response.status != 200:
            raise RackspaceError(response)
        payload = json.load(response)
        token_id = payload['access']['token']['id']
        files_endpoint = None
        queues_endpoint = None
        for service in payload['access']['serviceCatalog']:
            if service['type'] == 'object-store':
                for endpoint in service['endpoints']:
                    if not self.region or endpoint['region'] == self.region:
                        files_endpoint = endpoint['publicURL']
                        break
            if service['type'] == 'rax:queues':
                for endpoint in service['endpoints']:
                    if not self.region or endpoint['region'] == self.region:
                        queues_endpoint = endpoint['publicURL']
                        break
        return token_id, files_endpoint, queues_endpoint

    def _get_token_password(self, url, username, password, tenant_id):
        payload = {'auth': {'passwordCredentials': {'username': username,
                                                    'password': password}}}
        if tenant_id:
            payload['auth']['tenantId'] = tenant_id
        return self._get_token(url, payload)

    def _get_token_api_key(self, url, username, api_key, tenant_id):
        payload = {'auth': {'RAX-KSKEY:apiKeyCredentials':
                            {'username': username, 'apiKey': api_key}}}
        if tenant_id:
            payload['auth']['tenantId'] = tenant_id
        return self._get_token(url, payload)

    @property
    def token_id(self):
        """The current token in use by the mechanism.

        """
        if not self._token_id:
            self.create_token()
        return self._token_id

    def create_token(self):
        """Creates a new token for use in future requests to Rackspace Cloud
        services. This method is called automatically in most cases. The new
        token is stored in the :attr:`.token_id` attribute.

        """
        self._token_id, self.files_endpoint, self.queues_endpoint = \
            self.token_func()


class RackspaceCloudFiles(object):
    """Instances of this class may be passed in to the
    :class:`~slimta.cloudstorage.CloudStorage` constructor for the ``storage``
    parameter to use `Cloud Files`_ as the storage backend.

    Keys added to the container are generated with
    ``prefix + str(uuid.uuid4())``.

    :param auth: The :class:`RackspaceCloudAuth` object used to manage tokens
                 this service.
    :param container: The Cloud Files container name to use. The files in this
                      container will be named with random UUID strings.
    :param timeout: Timeout, in seconds, for all requests to the Cloud Files
                    API to return before an exception is thrown.
    :param tls: Optional dictionary of TLS settings passed directly as keyword
                arguments to :class:`gevent.ssl.SSLSocket`. This is only used
                for URLs with the ``https`` scheme.
    :param prefix: The string prefixed to every key added to the bucket.

    """

    def __init__(self, auth, container='slimta-queue', timeout=None, tls=None,
                 prefix=''):
        super(RackspaceCloudFiles, self).__init__()
        self.get_connection = get_connection
        self.auth = auth
        self.container = container
        self.timeout = timeout
        self.prefix = prefix
        self.tls = tls or {}

    def _get_files_url(self, files_id=None):
        url = urljoin(self.auth.files_endpoint+'/', self.container)
        if files_id:
            url = urljoin(url+'/', files_id)
        return url

    def write_message(self, envelope, timestamp, retry=False):
        envelope_raw = cPickle.dumps(envelope, cPickle.HIGHEST_PROTOCOL)
        files_id = self.prefix + str(uuid.uuid4())
        url = self._get_files_url(files_id)
        parsed_url = urlsplit(str(url), 'http')
        conn = self.get_connection(parsed_url, self.tls)
        headers = [('Host', parsed_url.hostname),
                   ('Content-Type', 'application/octet-stream'),
                   ('Content-Length', str(len(envelope_raw))),
                   (_TIMESTAMP_HDR, json.dumps(timestamp)),
                   ('X-Auth-Token', self.auth.token_id)]
        with gevent.Timeout(self.timeout):
            log.request(conn, 'PUT', parsed_url.path, headers)
            conn.putrequest('PUT', parsed_url.path)
            for name, value in headers:
                conn.putheader(name, value)
            conn.endheaders(envelope_raw)
            res = conn.getresponse()
            status = '{0!s} {1}'.format(res.status, res.reason)
            log.response(conn, status, res.getheaders())
        if res.status == 401 and not retry:
            self.auth.create_token()
            return self.write_message(envelope, timestamp, retry=True)
        elif res.status != 201:
            raise RackspaceError(res)
        return files_id

    def _write_message_meta(self, files_id, meta_headers, retry=False):
        url = self._get_files_url(files_id)
        parsed_url = urlsplit(url, 'http')
        conn = self.get_connection(parsed_url, self.tls)
        headers = [('Host', parsed_url.hostname),
                   ('X-Auth-Token', self.auth.token_id)] + meta_headers
        with gevent.Timeout(self.timeout):
            log.request(conn, 'POST', parsed_url.path, headers)
            conn.putrequest('POST', parsed_url.path)
            for name, value in headers:
                conn.putheader(name, value)
            conn.endheaders()
            res = conn.getresponse()
            status = '{0!s} {1}'.format(res.status, res.reason)
            log.response(conn, status, res.getheaders())
        if res.status == 401 and not retry:
            self.auth.create_token()
            return self._write_message_meta(files_id, meta_headers, retry=True)
        elif res.status != 202:
            raise RackspaceError(res)

    def set_message_meta(self, files_id, timestamp=None, attempts=None,
                         delivered_indexes=None):
        meta_headers = []
        if timestamp is not None:
            timestamp_raw = json.dumps(timestamp)
            meta_headers.append((_TIMESTAMP_HDR, timestamp_raw))
        if attempts is not None:
            attempts_raw = json.dumps(attempts)
            meta_headers.append((_ATTEMPTS_HDR, attempts_raw))
        if delivered_indexes is not None:
            delivered_raw = json.dumps(delivered_indexes)
            meta_headers.append((_DELIVERED_RCPTS_HDR, delivered_raw))
        return self._write_message_meta(files_id, meta_headers)

    def delete_message(self, files_id, retry=False):
        url = self._get_files_url(files_id)
        parsed_url = urlsplit(url, 'http')
        conn = self.get_connection(parsed_url, self.tls)
        headers = [('Host', parsed_url.hostname),
                   ('X-Auth-Token', self.auth.token_id)]
        with gevent.Timeout(self.timeout):
            log.request(conn, 'DELETE', parsed_url.path, headers)
            conn.putrequest('DELETE', parsed_url.path)
            for name, value in headers:
                conn.putheader(name, value)
            conn.endheaders()
            res = conn.getresponse()
            status = '{0!s} {1}'.format(res.status, res.reason)
            log.response(conn, status, res.getheaders())
        if res.status == 401 and not retry:
            return self.delete_message(files_id, retry=True)
        elif res.status != 204:
            raise RackspaceError(res)

    def get_message(self, files_id, only_meta=False, retry=False):
        url = self._get_files_url(files_id)
        parsed_url = urlsplit(url, 'http')
        conn = self.get_connection(parsed_url, self.tls)
        headers = [('Host', parsed_url.hostname),
                   ('X-Auth-Token', self.auth.token_id)]
        method = 'HEAD' if only_meta else 'GET'
        with gevent.Timeout(self.timeout):
            log.request(conn, method, parsed_url.path, headers)
            conn.putrequest(method, parsed_url.path)
            for name, value in headers:
                conn.putheader(name, value)
            conn.endheaders()
            res = conn.getresponse()
            status = '{0!s} {1}'.format(res.status, res.reason)
            log.response(conn, status, res.getheaders())
            data = None if only_meta else res.read()
        if res.status == 401 and not retry:
            self.auth.create_token()
            return self.get_message(files_id, only_meta, retry=True)
        if res.status == 404:
            raise KeyError(files_id)
        elif res.status != 200:
            raise RackspaceError(res)
        timestamp_raw = res.getheader(_TIMESTAMP_HDR)
        attempts_raw = res.getheader(_ATTEMPTS_HDR, None)
        delivered_raw = res.getheader(_DELIVERED_RCPTS_HDR, None)
        meta = {'timestamp': json.loads(timestamp_raw)}
        if attempts_raw:
            meta['attempts'] = json.loads(attempts_raw)
        if delivered_raw:
            meta['delivered_indexes'] = json.loads(delivered_raw)
        if only_meta:
            return meta
        else:
            envelope = cPickle.loads(data)
            return envelope, meta

    def get_message_meta(self, files_id):
        return self.get_message(files_id, only_meta=True)

    def _list_messages_page(self, marker, retry=False):
        url = self._get_files_url()
        parsed_url = urlsplit(url, 'http')
        conn = self.get_connection(parsed_url, self.tls)
        headers = [('Host', parsed_url.hostname),
                   ('X-Auth-Token', self.auth.token_id)]
        query = urlencode({'limit': '1000'})
        if marker:
            query += '&{0}'.format(urlencode({'marker': marker}))
        selector = '{0}?{1}'.format(parsed_url.path, query)
        with gevent.Timeout(self.timeout):
            log.request(conn, 'GET', selector, headers)
            conn.putrequest('GET', selector)
            for name, value in headers:
                conn.putheader(name, value)
            conn.endheaders()
            res = conn.getresponse()
            status = '{0!s} {1}'.format(res.status, res.reason)
            log.response(conn, status, res.getheaders())
            data = res.read()
        if res.status == 401 and not retry:
            self.auth.create_token()
            return self._list_messages_page(marker, retry=True)
        if res.status == 200:
            lines = data.splitlines()
            return [line for line in lines
                    if line.startswith(self.prefix)], lines[-1]
        elif res.status == 204:
            return [], None
        else:
            raise RackspaceError(res)

    def list_messages(self):
        marker = None
        ids = []
        while True:
            ids_batch, marker = self._list_messages_page(marker)
            if not marker:
                break
            ids.extend(ids_batch)
        for id in ids:
            timestamp, attempts = self.get_message_meta(id)
            yield timestamp, id


class RackspaceCloudQueues(object):
    """Instances of this class may be passed in to the
    :class:`~slimta.cloudstorage.CloudStorage` constructor for the
    ``message_queue`` parameter to use `Cloud Queues`_ as the message queue
    backend to alert other processes that a new message was stored.

    :param auth: The :class:`RackspaceCloudAuth` object used to manage tokens
                 this service.
    :param queue_name: The Cloud Files queue name to use.
    :param client_id: The ``Client-ID`` header passed in with all Cloud Queues
                      requests. By default, this is generated using
                      :func:`~uuid.uuid5` in conjunction with
                      :func:`~socket.getfqdn` to be consistent across restarts.
    :param timeout: Timeout, in seconds, for all requests to the Cloud Queues
                    API.
    :param poll_pause: The time, in seconds, to idle between attempts to poll
                       the queue for new messages.
    :param tls: Optional dictionary of TLS settings passed directly as keyword
                arguments to :class:`gevent.ssl.SSLSocket`. This is only used
                for URLs with the ``https`` scheme.

    """

    def __init__(self, auth, queue_name='slimta-queue', client_id=None,
                 timeout=None, poll_pause=1.0, tls=None):
        super(RackspaceCloudQueues, self).__init__()
        self.get_connection = get_connection
        self.auth = auth
        self.queue_name = queue_name
        self.client_id = client_id or _DEFAULT_CLIENT_ID
        self.timeout = timeout
        self.poll_pause = poll_pause
        self.tls = tls or {}

    def queue_message(self, storage_id, timestamp, retry=False):
        url = urljoin(self.auth.queues_endpoint+'/',
                      'queues/{0}/messages'.format(self.queue_name))
        parsed_url = urlsplit(url, 'http')
        conn = self.get_connection(parsed_url, self.tls)
        payload = [{'ttl': 86400,
                    'body': {'timestamp': timestamp,
                             'storage_id': storage_id}}]
        json_payload = json.dumps(payload, sort_keys=True)
        headers = [('Host', parsed_url.hostname),
                   ('Client-ID', self.client_id),
                   ('Content-Type', 'application/json'),
                   ('Content-Length', str(len(json_payload))),
                   ('Accept', 'application/json'),
                   ('X-Auth-Token', self.auth.token_id)]
        with gevent.Timeout(self.timeout):
            log.request(conn, 'POST', parsed_url.path, headers)
            conn.putrequest('POST', parsed_url.path)
            for name, value in headers:
                conn.putheader(name, value)
            conn.endheaders(json_payload)
            res = conn.getresponse()
            status = '{0!s} {1}'.format(res.status, res.reason)
            log.response(conn, status, res.getheaders())
        if res.status == 401 and not retry:
            self.auth.create_token()
            return self.queue_message(storage_id, timestamp, retry=True)
        elif res.status != 201:
            raise RackspaceError(res)

    def _claim_queued_messages(self, retry=False):
        url = urljoin(self.auth.queues_endpoint+'/',
                      'queues/{0}/claims'.format(self.queue_name))
        parsed_url = urlsplit(url, 'http')
        conn = self.get_connection(parsed_url, self.tls)
        json_payload = '{"ttl": 3600, "grace": 3600}'
        headers = [('Host', parsed_url.hostname),
                   ('Client-ID', self.client_id),
                   ('Content-Type', 'application/json'),
                   ('Content-Length', str(len(json_payload))),
                   ('Accept', 'application/json'),
                   ('X-Auth-Token', self.auth.token_id)]
        with gevent.Timeout(self.timeout):
            log.request(conn, 'POST', parsed_url.path, headers)
            conn.putrequest('POST', parsed_url.path)
            for name, value in headers:
                conn.putheader(name, value)
            conn.endheaders(json_payload)
            res = conn.getresponse()
            status = '{0!s} {1}'.format(res.status, res.reason)
            log.response(conn, status, res.getheaders())
            data = res.read()
        if res.status == 401 and not retry:
            self.auth.create_token()
            return self._claim_queued_messages(retry=True)
        if res.status == 201:
            messages = json.loads(data)
            return [(msg['body'], msg['href']) for msg in messages]
        elif res.status == 204:
            return []
        else:
            raise RackspaceError(res)

    def poll(self):
        messages = self._claim_queued_messages()
        for body, href in messages:
            yield (body['timestamp'], body['storage_id'], href)

    def sleep(self):
        gevent.sleep(self.poll_pause)

    def delete(self, href, retry=False):
        url = self.auth.queues_endpoint
        parsed_url = urlsplit(url, 'http')
        conn = self.get_connection(parsed_url, self.tls)
        headers = [('Host', parsed_url.hostname),
                   ('Client-ID', self.client_id),
                   ('Content-Type', 'application/json'),
                   ('Accept', 'application/json'),
                   ('X-Auth-Token', self.auth.token_id)]
        with gevent.Timeout(self.timeout):
            log.request(conn, 'DELETE', href, headers)
            conn.putrequest('DELETE', href)
            for name, value in headers:
                conn.putheader(name, value)
            conn.endheaders()
            res = conn.getresponse()
            status = '{0!s} {1}'.format(res.status, res.reason)
            log.response(conn, status, res.getheaders())
        if res.status == 401 and not retry:
            self.auth.create_token()
            return self.delete(href, retry=True)
        elif res.status != 204:
            raise RackspaceError(res)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
