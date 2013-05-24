
.. include:: /global.rst

Configuring the Queues
======================

With the mail queue being the heart of an MTA, the ``queue`` section of
``slimta.conf`` is both important and highly customizable. It also introduces
the possibility of using the ``slimta-worker`` executable for some queue types.
In the ``queue`` section, each key provides an arbitrary, free-form name for
the queue. The sub-section for each key has two required settings:

* ``type``: String, required

  Defines the type of queue. A known type must be given or an error will be
  thrown. The other keys in this mapping depend on the value of ``type``.

* ``relay``: String, required

  Delivery attempts of messages in the queue are passed to this relay. The value
  is a name, which must correspond to a key in the top-level ``relay`` section.

Queue Policy Settings
"""""""""""""""""""""

On entry into the queue, there are several :doc:`policies` that can be applied
to a message. To configure them, there is an additional, optional key available
in a ``queue`` sub-section:

* ``policies``: List

  Each entry in this list is a dictionary with a ``type`` field. Check out the
  :doc:`policies` page for more information about each type:

  * ``add_date_header``: Adds the ``Date:`` header to the message.
  * ``add_message_id_header``: Adds the ``Message-Id:`` header to the message.
  * ``add_received_header``: Adds a ``Received:`` header to the message.
  * ``recipient_split``: Forks the message so that for each recipient there is
    a deep copy of the original message.
  * ``recipient_domain_split``: Forks the message so that for each unique domain
    in the message recipients there is a deep copy of the original message with
    the recipients for that domain.
  * ``forward``: Rewrites recipients using regular expressions. Along with the
    ``type`` key, there is a ``mapping`` key which is a dictionary of
    replacement rules where each key is a regular expression pattern and the
    value is string to replace the pattern match with.
  * ``spamassassin``: Queries a SpamAssassin server to check if the message is
    considered spam, adding headers to the message with the results.

Delivery Retry Behavior
"""""""""""""""""""""""

Additionally, every ``queue`` type (*except* for ``"custom"`` and ``"proxy"``)
honors the ability to configure message retrying with the following
configuration settings:

* ``retry``: Dictionary

  If this dictionary is *not* given, messages are never retried. This dictionary
  has two keys, ``delay`` and ``maximum``:

  * ``delay``: String
  
    Defines an mathematic expression whose result is used as the number of
    seconds to delay between each delivery attempt of a message.  The string
    allows arithmetic operators and the use of any functions in the :mod:`math`
    module (without the ``math.`` prefix). The variable ``x`` may be used in the
    expression, and will be replaced with the number of delivery attempts the
    message has undergone.

    For example, passing the string ``"300*x"`` will start the delay at five
    minutes, and increase the delay by an additional five minutes for each
    attempt on the message.

    The default value of this setting is ``"300"``, which results in messages
    being retried every five minutes until the maximum number of attempts has
    been reached.

  * ``maximum``: Integer

    Defines the maximum number of retries before a message is failed. If this
    value is not given, messages are never retried.

``memory`` Queues
"""""""""""""""""

With this queue type, all queued messages and their metadata reside in memory.
While this is fast and easy to setup, it is *not* safe for production usage, and
can easily result in loss of mail. The ``"memory"`` queue type does not have any
additional settings.

``disk`` Queues
"""""""""""""""

With this queue type, messages and their metadata are spooled to disk before
acceptance. This queue type requires three directories, which are configured
with the following keys:

* ``tmp_dir``: String

  This directory is used as scratch space so that files can be created and
  written before being moved to their final destination. This allows for the use
  of the atomic :func:`os.rename` operation, to help prevent data corruption. By
  default, the OS-specific temporary directory is used.

* ``envelope_dir``: String, required

  In this directory, the message contents and envelope information are written
  to files that use the ``.env`` suffix in a Python :mod:`pickle` format.

* ``meta_dir``: String, required

  In this directory, the message metadata is kept in files that end in
  ``.meta``. This information is primarily related to the delivery of the
  message, including how many attempts it has undergone, and is kept separately
  so that it can be written to often.

``proxy`` Queues
""""""""""""""""

The ``"proxy"`` queue type is not a queue at all, but rather a method of
bypassing the queue step and immediately attempting message delivery. If
delivery fails, the client gets immediate feedback from the edge service. There
are no additional configuration settings for this queue type.

``celery`` Queues
"""""""""""""""""

.. _Celery Project: http://celeryproject.org/
.. _Celery Configuration: http://docs.celeryproject.org/en/latest/configuration.html

The ``"celery"`` queue type takes advantage of the `Celery Project`_ to offload
most queuing logic. Essentially, on reception, a message is written to a
broker such as RabbitMQ or Redis, and the client is immediately notified that
the message was accepted. A separate process is configured to pull messages from
the broker when they are ready for delivery.

Unlike other queue types, the ``"celery"`` queue type requires you to run
a separate process alongside ``slimta``::

    $ slimta
    $ slimta-worker

However, as long as these two processes are configured the same and consume the
same broker service, you now have the advantage of being able to receive
messages (with an edge service) and delivery them (with a relay service) on two
totally different machines.

No additional config settings are necessary inside the ``"celery"`` queue sub-
section. However, there is a required, top-level section that is shared among
all ``"celery"`` queues:

* ``celery_app``: Dictionary

  This section contains all the key-value pairs normally placed in a
  ``celeryconfig.py`` module. For example, to specify the broker and backend
  URLs::

    celery_app: {
      BROKER_URL: 'redis://'
      BACKEND_URL: 'redis://'
    }

``custom`` Queues
"""""""""""""""""

Only one additional key is required by the ``"custom"`` queue type:

* ``factory``: String, required

  This is a string of the form ``package.module:symbol``. The package and
  module portion are imported with :func:`importlib.import_module`, and then
  the symbol is fetched from the loaded module with :func:`getattr()`.

  The result of loading the symbol must be a function that takes two arguments,
  the options object (that contains the ``type``, ``relay``, and ``factory``
  keys as well as any others as necessary) and the |Relay| object that the queue
  should use for message delivery::

    def queue_factory(options, relay):
        if 'foo' in options:
            return FooQueue(options.stuff, relay)
        else:
            return BarQueue(options.baz, relay)

