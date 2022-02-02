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

"""Package containing a module for the different cloud service providers along
with any necessary helper modules.

.. _S3: http://aws.amazon.com/s3/
.. _SQS: http://aws.amazon.com/sqs/

"""

from __future__ import absolute_import

from slimta.queue import QueueError, QueueStorage
from slimta import logging

__all__ = ['CloudStorageError', 'CloudStorage']

log = logging.getQueueStorageLogger(__name__)


class CloudStorageError(QueueError):
    """Base exception for all exceptions in the package.

    """
    pass


class CloudStorage(QueueStorage):
    """This class implements a :class:`~slimta.queue.QueueStorage` backend that
    uses cloud services to store messages. It coordinates the storage of
    messages and metadata (using `S3`_) with the optional message queue
    mechanisms (using `SQS`_) that can alert other *slimta* processes that a
    new message is available in the object store.

    :param object_store: The object used as the backend for storing message
                         contents and metadata in the cloud. Currently this can
                         be an instance of
                         :class:`~aws.SimpleStorageService`.
    :param message_queue: The optional object used
                          as the backend for alerting other processes that a
                          new message is in the object store. Currently this
                          can be an instance of
                          :class:`~aws.SimpleQueueService`.

    """

    def __init__(self, object_store, message_queue=None):
        super(CloudStorage, self).__init__()
        self.obj_store = object_store
        self.msg_queue = message_queue

    def write(self, envelope, timestamp):
        storage_id = self.obj_store.write_message(envelope, timestamp)
        if self.msg_queue:
            try:
                self.msg_queue.queue_message(storage_id, timestamp)
            except Exception:
                logging.log_exception(__name__)
        log.write(storage_id, envelope)
        return storage_id

    def set_timestamp(self, id, timestamp):
        self.obj_store.set_message_meta(id, timestamp=timestamp)
        log.update_meta(id, timestamp=timestamp)

    def increment_attempts(self, id):
        meta = self.obj_store.get_message_meta(id)
        new_attempts = meta['attempts'] + 1
        self.obj_store.set_message_meta(id, attempts=new_attempts)
        log.update_meta(id, attempts=new_attempts)
        return new_attempts

    def set_recipients_delivered(self, id, rcpt_indexes):
        meta = self.obj_store.get_message_meta(id)
        current = meta.get('delivered_indexes', [])
        new = current + rcpt_indexes
        self.obj_store.set_message_meta(id, delivered_indexes=new)
        log.update_meta(id, delivered_indexes=rcpt_indexes)

    def load(self):
        return self.obj_store.list_messages()

    def get(self, id):
        envelope, meta = self.obj_store.get_message(id)
        delivered_rcpts = meta.get('delivered_indexes', [])
        self._remove_delivered_rcpts(envelope, delivered_rcpts)
        return envelope, meta.get('attempts', 0)

    def remove(self, id):
        self.obj_store.delete_message(id)
        log.remove(id)

    def wait(self):
        if self.msg_queue:
            for timestamp, storage_id, message_id in self.msg_queue.poll():
                yield (timestamp, storage_id)
                self.msg_queue.delete(message_id)
            self.msg_queue.sleep()
        else:
            raise NotImplementedError()


# vim:et:fdm=marker:sts=4:sw=4:ts=4
