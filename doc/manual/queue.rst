
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
*slimta* to be stopped and restarted without losing state.

The :class:`~slimta.queue.dict.DictStorage` class is a simple storage mechanism
that, by itself, *does not* provide on-disk persistence. It should be used in
conjunction with :mod:`shelve` dict-like objects for persistence.

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

