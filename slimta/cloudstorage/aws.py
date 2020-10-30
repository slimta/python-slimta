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

"""This module defines the queue storage mechanism specific to the `Amazon Web
Services`_ hosting service. It requires an account as well as the `Simple
Storage Service (S3)`_ and optionally the `Simple Queue Service (SQS)`_
services.

For each queued message, the contents and metadata of the message are written
to *S3*. Upon success, a reference to the S3 object is injected into *SQS* as a
new message.

The *SQS* service is only necessary for alerting separate *slimta* processes
that a new message has been queued. If reception and relaying are happening in
the same process, *SQS* is unnecessary.

**NOTE:** This module uses the `boto`_ library to communicate with *AWS*. To
avoid performance issues, you must use gevent `monkey patching`_ before using
it!

::

    from gevent import monkey; monkey.patch_all()

    s3_conn = boto.connect_s3()
    s3_bucket = s3_conn.get_bucket('slimta-queue')
    s3 = SimpleStorageService(s3_bucket)

    sqs_conn = boto.sqs.connect_to_region('us-west-2')
    sqs_queue = sqs_conn.create_queue('slimta-queue')
    sqs = SimpleQueueService(sqs_queue)

    queue_storage = CloudStorage(s3, sqs)

.. _Amazon Web Services: http://aws.amazon.com/
.. _Simple Storage Service (S3): http://aws.amazon.com/s3/
.. _Simple Queue Service (SQS): http://aws.amazon.com/sqs/
.. _boto: http://boto.readthedocs.org/en/latest/
.. _monkey patching: http://gevent.org/intro.html#monkey-patching

"""

from __future__ import absolute_import

import uuid
import json

from six.moves import cPickle

import gevent
from boto.s3.key import Key
from boto.sqs.message import Message

__all__ = ['SimpleStorageService', 'SimpleQueueService']


class SimpleStorageService(object):
    """Instances of this class may be passed in to the
    :class:`~slimta.cloudstorage.CloudStorage` constructor for the ``storage``
    parameter to use *S3* as the storage backend.

    Keys added to the bucket are generated with ``prefix + str(uuid.uuid4())``.

    :param bucket: The S3 bucket object in which all message contents and
                   metadata will be written. Each created S3 object will use a
                   :py:mod:`uuid` string as its key.
    :type bucket: :class:`boto.s3.bucket.Bucket`
    :param timeout: Timeout, in seconds, before requests to *S3* will fail and
                    raise an exception.
    :param prefix: The string prefixed to every key added to the bucket.

    """

    def __init__(self, bucket, timeout=None, prefix=''):
        super(SimpleStorageService, self).__init__()
        self.bucket = bucket
        self.timeout = timeout
        self.prefix = prefix
        self.Key = Key

    def _get_key(self, id):
        key = self.bucket.get_key(id)
        if not key:
            raise KeyError(id)
        return key

    def write_message(self, envelope, timestamp):
        key = self.Key(self.bucket)
        key.key = self.prefix+str(uuid.uuid4())
        envelope_raw = cPickle.dumps(envelope, cPickle.HIGHEST_PROTOCOL)
        with gevent.Timeout(self.timeout):
            key.set_metadata('timestamp', json.dumps(timestamp))
            key.set_metadata('attempts', '')
            key.set_metadata('delivered_indexes', '')
            key.set_contents_from_string(envelope_raw)
        return key.key

    def set_message_meta(self, id, timestamp=None, attempts=None,
                         delivered_indexes=None):
        key = self._get_key(id)
        with gevent.Timeout(self.timeout):
            if timestamp is not None:
                key.set_metadata('timestamp', json.dumps(timestamp))
            if attempts is not None:
                key.set_metadata('attempts', json.dumps(attempts))
            if delivered_indexes is not None:
                key.set_metadata('delivered_indexes',
                                 json.dumps(delivered_indexes))

    def delete_message(self, id):
        key = self._get_key(id)
        with gevent.Timeout(self.timeout):
            key.delete()

    def get_message(self, id):
        key = self._get_key(id)
        with gevent.Timeout(self.timeout):
            envelope_raw = key.get_contents_as_string()
            timestamp_raw = key.get_metadata('timestamp')
            attempts_raw = key.get_metadata('attempts')
            delivered_raw = key.get_metadata('delivered_indexes')
        envelope = cPickle.loads(envelope_raw)
        meta = {'timestamp': json.loads(timestamp_raw)}
        if attempts_raw:
            meta['attempts'] = json.loads(attempts_raw)
        if delivered_raw:
            meta['delivered_indexes'] = json.loads(delivered_raw)
        return envelope, meta

    def get_message_meta(self, id):
        key = self._get_key(id)
        with gevent.Timeout(self.timeout):
            timestamp_raw = key.get_metadata('timestamp')
            attempts_raw = key.get_metadata('attempts')
            delivered_raw = key.get_metadata('delivered_indexes')
        meta = {'timestamp': json.loads(timestamp_raw)}
        if attempts_raw:
            meta['attempts'] = json.loads(attempts_raw)
        if delivered_raw:
            meta['delivered_indexes'] = json.loads(delivered_raw)
        return meta

    def list_messages(self):
        with gevent.Timeout(self.timeout):
            ids = list(self.bucket.list(self.prefix))
        for id in ids:
            timestamp, attempts = self.get_message_meta(id)
            yield (timestamp, id)


class SimpleQueueService(object):
    """Instances of this class may be passed in to the
    :class:`~slimta.cloudstorage.CloudStorage` constructor for the
    ``message_queue`` parameter to use *SQS* as the message queue backend to
    alert other processes that a new message was stored.

    :param queue: The SQS queue object in which each new message corresponds to
                  a new object in storage.
    :type queue: :class:`boto.sqs.queue.Queue`
    :param timeout: Timeout, in seconds, before requests to *S3* will fail and
                    raise an exception.
    :param poll_pause: The time, in seconds, to idle between attempts to poll
                       the queue for new messages.

    """

    def __init__(self, queue, timeout=None, poll_pause=1.0):
        super(SimpleQueueService, self).__init__()
        self.queue = queue
        self.timeout = timeout
        self.poll_pause = poll_pause
        self.Message = Message

    def queue_message(self, storage_id, timestamp):
        msg = self.Message()
        payload = {'timestamp': timestamp, 'storage_id': storage_id}
        msg.set_body(json.dumps(payload))
        with gevent.Timeout(self.timeout):
            while not self.queue.write(msg):
                pass

    def poll(self):
        with gevent.Timeout(self.timeout):
            messages = self.queue.get_messages()
        for msg in messages:
            payload = json.loads(msg.get_body())
            yield (payload['timestamp'], payload['storage_id'], msg)

    def sleep(self):
        gevent.sleep(self.poll_pause)

    def delete(self, msg):
        with gevent.Timeout(self.timeout):
            self.queue.delete_message(msg)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
