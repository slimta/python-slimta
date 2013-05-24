
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

Additionally, every ``queue`` type *except* for ``"custom"`` honors the
following settings:

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

``disk`` Queues
"""""""""""""""

``proxy`` Queues
""""""""""""""""

``celery`` Queues
"""""""""""""""""

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

