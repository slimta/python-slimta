
.. include:: /global.rst

Configuring the Relays
======================

The last major section in ``slimta.conf`` is ``relay``, where you set up the
|Relay| options for outbound message delivery. In the ``relay`` section, each
key  provides an arbitrary, free-form name for the relay, and the value is a
mapping with one required key:

* ``type``: String

  Defines the type of relay. A known type must be given or an error will be
  thrown. The other keys in this mapping depend on the value of ``type``.


``mx`` and ``static`` Relays
""""""""""""""""""""""""""""

.. _MSA: http://en.wikipedia.org/wiki/Mail_submission_agent

When configuring an `MSA`_, you generally want to accept all mail from
authorized senders for delivery to the intended target. The fundamental design
of email uses DNS MX records to allow domains to advertize the servers that will
accept mail on its behalf. Other times, you might want to delivery *all* mail to
a particular host, perhaps for spam or abuse prevention. Using the ``"mx"`` and
``"static"`` relay types provide this behavior.

Using the ``"mx"`` type produces an :class:`~slimta.relay.smtp.mx.MxSmtpRelay`
and the ``"static"`` type produces a
:class:`~slimta.relay.smtp.static.StaticSmtpRelay`. Both share several config
options that can customize their behavior:

* ``connect_timeout``: Integer

  Defines the time, in seconds, that the relay will allow for connection before
  failing. The default is 30 seconds.

* ``command_timeout``: Integer

  Defines the time, in seconds, that the relay will wait for a response to each
  SMTP command before failing and disconnecting. The default is 30 seconds.

* ``data_timeout``: Integer

  Defines the time, in seconds, that the relay will wait for message data to be
  accepted. This delay may be longer than most other commands, as the remote
  host will likely need time to spool the message. The default is 60 seconds.

* ``idle_timeout``: Integer

  Unlike the other timeouts, this is the amount of time an outbound connection
  is left open *after* a message has been delivered. If a new message is to be
  delivered to the same host, the connection can be recycled. The default is
  10 seconds.

* ``concurrent_connections``: Integer

  The maximum number of simultaneous connections to any given remote host. If
  this limit is reached, delivery of messages to that host will block until a
  space is freed. The default is 5 connections.

* ``ehlo_as``: String

  This string is used as the ``EHLO``/``HELO`` string when handshaking with
  remote hosts. This setting should *never* be an IP address, ``"localhost"``,
  or ``"localdomain"``, as many email services will block these and list your
  IP on DNS blocklists. By default, the FQDN of the local machine is used.

* ``tls``: Dictionary

  This mapping, which takes the same keys as the keyword parameters to
  :func:`~ssl.wrap_socket`, both enables and configures TLS encryption on this
  SMTP relay. By default, TLS is not enabled.

There are some additional options that apply *only* to ``"static"`` relay types.
These options specify the permanent delivery address for all mail, and are as
follows:

* ``host``: String, required

  The host name or IP address of the destination for outbound mail delivery on
  the ``"static"`` relay type.

* ``port``: Integer

  The port number to connect to on the destination server for outbound mail
  delivery on the ``"static"`` relay type.

``pipe`` Relays
"""""""""""""""

.. _pipe: http://www.postfix.org/pipe.8.html

The ``"pipe"`` relay type mimcs the postfix pipe_ daemon, which is a useful
delivery mechanism for handing off a message to an external process by piping
the message data to the process's *stdin* stream. This relay type has the
following configuration keys:

* ``args``: List

  These are the arguments for the subprocess, similar to the ``args`` parameter
  to the :py:class:`~subprocess.Popen` constructor. This list may contain
  several macros, see the :class:`~slimta.piperelay.PipeRelay` class constructor
  for more information.

* ``error_pattern``: String

  This string defines a regular expression that parses an error message from the
  subprocess's *stdout* or *stderr*, whichever matches.

``maildrop`` Relays
"""""""""""""""""""

.. _courier maildrop: http://www.courier-mta.org/maildrop/

The ``"maildrop"`` relay type enables message delivery to the local machine,
using the `courier maildrop`_ application. The behavior of this relay is mostly
configured externally using ``.mailfilter`` files, though it allows for one
configuration key:

* ``path``: String

  The path to the ``maildrop`` executable. By default, the ``$PATH`` environment
  variable is searched.

``dovecot`` Relays
""""""""""""""""""

.. _LDA: http://wiki.dovecot.org/LDA
.. _dovecot: http://www.dovecot.org/

The ``"dovecot"`` relay type enables message delivery to the local machine,
using the LDA_ agent included with dovecot_. The behavior of this relay is
mostly configured within dovecot using Sieve or similar, though it allows for
one configuration key:

* ``path``: String

  The path to the ``dovecot-lda`` executable. By default, the ``$PATH``
  environment variable is searched.

``http`` Relays
"""""""""""""""

The ``"http"`` relay type uses request headers to specify the information
about the session and envelope normally given in SMTP commands, and the
response code and headers to determine whether delivery was successful, or if
it permanently or transiently failed.

* ``url``: String

  The URL string to POST messages to. This string determines the hostname,
  port, and path for the request. The ``http:`` or ``https:`` scheme is ignored
  in favor of the ``tls`` option below.

* ``ehlo_as``: String

  Optional string passed as the ``X-Ehlo`` header in the request. If not given,
  the system FQDN is used.

* ``timeout``: Number

  Timeout in seconds for the entire request and response, including connection
  time, before the delivery attempt transiently fails. Default is 60 seconds.

* ``idle_timeout``: Number

  If given, connections are left open after a response is received, and another
  delivery is attempted before this timeout, the connection is recycled. By
  default, connections are closed immediately.

* ``tls``: Dictionary

  This mapping, which takes the same keys as the keyword parameters to
  :func:`~ssl.wrap_socket`, both enables and configures TLS encryption on this
  HTTP relay. This means the server must be configured for HTTPS. By default,
  TLS is not enabled.

``blackhole`` Relays
""""""""""""""""""""

This relay type considers every message delivered to it a successful delivery,
but will take no actual action. This is really only useful for testing. No
additional options are associated with this relay type.

``custom`` Relays
"""""""""""""""""

Only one additional key is required by the ``"custom"`` relay type:

* ``factory``: String, required

  This is a string of the form ``package.module:symbol``. The package and
  module portion are imported with :func:`importlib.import_module`, and then
  the symbol is fetched from the loaded module with :func:`getattr()`.

  The result of loading the symbol must be a function that takes one argument,
  the options object (that contains the ``type`` and ``factory`` keys as well
  as any others as necessary)::

    def relay_factory(options):
        if 'foo' in options:
            return FooRelay(options.stuff)
        else:
            return BarRelay(options.baz)

