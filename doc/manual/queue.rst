
.. include:: /global.rst

Queue Services
==============

When a client sends an email, that email may go through several email servers
before arriving at its final destination. Each server is designed to take
responsibility for delivering the message to the next one, retrying if
necessary. Once a server has taken responsibility for a message, the connecting
client (or server) may disconnect.

The *queue* service is responsible for making sure email messages are stored
persistently somewhere (in case of catastrophic failure) and that delivery is
tried and retried with due diligence.

Persistent Storage
""""""""""""""""""

A storage mechanism should store the entirety of an |Envelope| object, such that
it can be recreated on restart. Along with the envelope, queue services must
also keep track of when a message's next delivery attempt should be and how many
attempts a message has undergone. In essence, a queue's storage mechanism allows
|slimta| to be stopped and restarted without losing state.

In-Memory
'''''''''

The :class:`~slimta.queue.dict.DictStorage` class is a simple storage mechanism
that, by itself, *does not* provide on-disk persistence. By default, it creates
two dicts in memory for queue data, but passing in :mod:`shelve` objects will
allow basic persistence. Be aware, however, that :mod:`shelve` may not handle
system or process failure and could leave corruption.

The :class:`~slimta.queue.dict.DictStorage` class is very useful for development
and testing, but probably should be avoided for live systems.

Local Disk
''''''''''

The :class:`~slimta.diskstorage.DiskStorage` class stores queue data
persistently on disk, using two files for each queued message. Files are never
created or edited in-place, but are instead created as new files in a scratch
directory and atomically moved into place. Asynchronous disk I/O is used in an
effort to prevent blocking the process and stopping network I/O.

:class:`~slimta.diskstorage.DiskStorage` is likely the current best mechanism
for live mail systems. Install it with::

    pip install python-slimta-diskstorage

Redis
'''''

The future plan is to have a |QueueStorage| implementation which uses redis_ as
the back-end. This will essentially "out-source" the difficult problem of
balancing and disconnecting storage and processing.

Delivery Attempts
"""""""""""""""""

Delivery attempts for a queue are performed with the |Relay| object passed in to
the |Queue| constructor. The delivery attempt will ultimately produce a |Reply|
object indicating its success or failure. If delivery was successful, the queue
will remove the message from persistent storage.

If delivery failed permanently, with a ``5xx`` code or too many ``4xx`` codes,
a |Bounce| envelope is created from the original message, which is delivered
back to the original message sender. The original message is removed from
storage and not retried.

If delivery failed transiently, with a ``4xx`` code (which usually includes
connectivity issues), the message is left in storage and a new delivery attempt
is scheduled in the future. The time between delivery attempts is managed by the
``backoff`` function passed in to the |Queue| constructor. If this ``backoff``
function returns ``None``, the message is permanently failed.

Here is an example ``backoff`` function that makes 5 delivery attempts with an
exponentially increasing backoff time::

    def exponential_backoff(envelope, attempts):
        if attempts <= 5:
            return 12.0 * (5.0 ** attempts)
        return None

