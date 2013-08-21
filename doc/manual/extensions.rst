
.. include:: /global.rst

.. _gevent_subprocess: https://github.com/bombela/gevent_subprocess
.. _courier-maildrop: http://www.courier-mta.org/maildrop/
.. _dovecot-deliver: http://wiki.dovecot.org/LDA
.. _pyaio: https://github.com/felipecruz/pyaio
.. _redis: http://redis.io/
.. _redis-py: https://github.com/andymccurdy/redis-py
.. _ESPs: http://en.wikipedia.org/wiki/E-mail_service_provider
.. _spam-filled world: http://www.maawg.org/email_metrics_report
.. _Celery Distributed Task Queue: http://www.celeryproject.org/
.. _SPF: http://en.wikipedia.org/wiki/Sender_Policy_Framework

Extensions
==========

In an effort to keep a small number of dependencies and avoid a reputation for
"bloating", several desirable features are included as extensions installed
separately. These extensions, and where and how to use them, are discussed
here.

.. _pipe-relay:

External Process Delivery
"""""""""""""""""""""""""

This simple extension uses the `gevent_subprocess`_ library to initiate local
delivery an external process. This simple mechanism is then used to support
delivery to applications such as `courier-maildrop`_ and `dovecot-deliver`_.

Installation of this extension is as simple as::

    $ pip install python-slimta-piperelay

Take `courier-maildrop`_ as an example. With a normal system configuration, the
following should be plenty to create a :class:`~slimta.piperelay.MaildropRelay`
instance::

    from slimta.piperelay import MaildropRelay

    relay = MaildropRelay()

For more information, the :doc:`mda` tutorial and :mod:`~slimta.piperelay`
module documentation may be useful.

.. _disk-storage:

Disk Storage
""""""""""""

In the fashion of traditional MTAs, the :mod:`~slimta.diskstorage` extension
writes |Envelope| data and queue metadata directly to disk to configurable
directories. This extension relies on `pyaio`_ to asynchronously write and read
files on disk.

To ensure file creation and modification is atomic, files are
first written to a scratch directory and then :func:`os.rename` moves them to
their final destination. For this reason, it is important that the scratch
directory (``tmp_dir`` argument in the constructor) reside on the same
filesystem as the envelope and meta directories (``env_dir`` and ``meta_dir``
arguments, respectively).

The files created in the envelope directory will be identified by a
:func:`~uuid.uuid4` :attr:`hexadecimal string <uuid.UUID.hex>` appended with
the suffix ``.env``. The files created in the meta directory will be identified
by the same uuid string as its corresponding envelope file, but with the suffix
``.meta``. The envelope and meta directories can be the same, but two
:class:`~slimta.diskstorage.DiskStorage` should not share directories.

To install this extension::

    $ pip install python-slimta-diskstorage

And to initialize a new :class:`~slimta.diskstorage.DiskStorage`::

    from slimta.diskstorage import DiskStorage

    queue_dir = '/var/spool/slimta/queue'
    queue = DiskStorage(queue_dir, queue_dir)

.. _redis-storage:

Redis Storage
"""""""""""""

Taking advantage of the advanced data structures and ease of use of the redis_
database, the :mod:`~slimta.redisstorage` extension simply creates a hash key
for each queued message, containing its delivery metadata and a pickled version
of the |Envelope|.

The keys created in redis will look like the following::

    redis 127.0.0.1:6379> KEYS *
    1) "slimta:28195d3b0a5847f9853e5b0173c85151"
    2) "slimta:5ebb94976cd94b418d6063a2ca4cbf8f"
    3) "slimta:d33879cf66244472b983770ba762e07b"
    redis 127.0.0.1:6379> 

Each key is a hash that will look something like::

    redis 127.0.0.1:6379> HGETALL slimta:d33879cf66244472b983770ba762e07b 
    1) "attempts"
    2) "2"
    3) "timestamp"
    4) "1377121655"
    5) "envelope"
    6) "..."
    redis 127.0.0.1:6379> 

On startup, the |Queue| will scan the keyspace (using the customizable prefix
``slimta:``) and populate the queue with existing messages for delivery.

To install this extension::

    $ pip install python-slimta-redisstorage

And to initialize a new :class:`~slimta.redisstorage.RedisStorage`::

    from slimta.redisstorage import RedisStorage

    store = RedisStorage('redis.example.com')

.. _celery-queue:

Celery Distributed Queuing
""""""""""""""""""""""""""

Why It's Better
'''''''''''''''

One of the original inspirations for |slimta| was splitting apart the "big 3"
components of an MTA in such a way that different server clusters could be
responsible for each component. These "big 3" components are called the *edge*,
the *queue*, and the *relay* in this library.

One of the largest and most complicated pieces of logic in modern-day `ESPs`_
is anti-abuse. It is reasonable to assume that simply handling inbound traffic
from a `spam-filled world`_ is more than enough for a server cluster to be
responsible for. The server running the *edge* service should be able to simply
hand off a received message for delivery to the *queue* running on another
machine.

Despite the name, a *queue* in the MTA sense is not a simple FIFO we learned
about in our Computer Science course. It is responsible at a minimum for:

* Receiving new messages from the *edge* and persistently storing them.
* Requesting delivery from the *relay* service.
* Delaying message delivery retry after transient failures.
* Reporting permanent delivery failure back to the sender with a bounce
  message.

If you're familiar with the `Celery Distributed Task Queue`_, it fits the bill
perfectly.

Setting It Up
'''''''''''''

Celery will actually take care of managing the *relay* and *queue* services,
when all is said and done. The message broker and results backend of Celery
act as the *queue*, and the task workers act as the *relay*.

In a new file (I called mine ``mytasks.py``), set up your ``celery`` object::

    from celery import Celery

    celery = Celery('mytasks', broker='redis://localhost/0',
                               backend='redis://localhost/0')

We'll also set up our |Relay| object now::

    from slimta.relay.smtp.mx import MxSmtpRelay

    relay = MxSmtpRelay()

Next, create a new :class:`~slimta.celeryqueue.CeleryQueue` using both of these
objects::

    from slimta.celeryqueue import CeleryQueue

    queue = CeleryQueue(celery, relay)

Simply creating a :class:`~slimta.celeryqueue.CeleryQueue` instance will
register a new celery task called ``attempt_delivery``. Each delivery attempt
and retry will call this task, including delivery of bounce messages.

Now, back inside your |slimta| application code, you can import ``queue``
from this file, add your policies, and create your |Edge|::

    from mytasks import queue
    from slimta.policy.headers import *
    from slimta.edge.smtp import SmtpEdge

    queue.add_policy(AddDateHeader())
    queue.add_policy(AddMessageIdHeader())
    queue.add_policy(AddReceivedHeader())

    edge = SmtpEdge(('', 25), queue)
    edge.start()

Finally, in a new terminal start your task worker, using :mod:`gevent` as the
worker thread pool::

    $ celery worker -A mytasks -l debug -P gevent

Now you are all set up with a distributed Celery queue! You're now free to
scale your *edge* by adding more machines running |SmtpEdge| to the a ``queue``
with the same backend and broker. You're now free to scale your *queue* by
scaling your backend and broker (might be easier with RabbitMQ than Redis).
And finally, you're free to scale your *relay* by adding machines designated as
Celery task workers. Go nuts!

.. _enforce-spf:

Sender Policy Framework (SPF)
"""""""""""""""""""""""""""""

SPF_ is a tool that, at its most basic, allows domains to explicitly list the
outbound hosts/IPs from which they are legitimately sending mail. Domains may
set DNS records of special formats that email receivers query and compare
against the information they know about the sending client.

To set it up, you need to create rules for the different types of results. You
do this by creating a :class:`~slimta.spf.EnforceSpf` object and calling
:meth:`~slimta.spf.EnforceSpf.set_enforcement` for each different results you
want to act upon. These results are:

* `none <http://tools.ietf.org/html/rfc4408#section-2.5.1>`_
* `neutral <http://tools.ietf.org/html/rfc4408#section-2.5.2>`_
* `pass <http://tools.ietf.org/html/rfc4408#section-2.5.3>`_
* `fail <http://tools.ietf.org/html/rfc4408#section-2.5.4>`_
* `softfail <http://tools.ietf.org/html/rfc4408#section-2.5.5>`_
* `temperror <http://tools.ietf.org/html/rfc4408#section-2.5.6>`_
* `permerror <http://tools.ietf.org/html/rfc4408#section-2.5.7>`_

So we create our rules::

    spf = EnforceSpf()
    spf.set_enforcement('fail', match_message='5.7.1 Access denied: {reason}')
    spf.set_enforcement('softfail', match_code='250', match_message='2.0.0 Ok; {reason}')

And then in our :class:`~slimta.edge.smtp.SmtpValidators` class, use the
:meth:`~slimta.spf.EnforceSpf.check` decorator::

    @spf.check
    def validate_mail(self, reply, sender):
        pass

