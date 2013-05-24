
.. include:: /global.rst

Configuring the Edges
=====================

The next big section in ``slimta.conf`` is ``edge``, which allows you to setup
as many different inbound edge listeners as you need. In the ``edge`` section,
each key provides an arbitrary, free-form name for the edge, and the value is
a mapping with two required keys:

* ``type``: String

  Defines the type of edge. A known type must be given or an error will be
  thrown. The other keys in this mapping depend on the value of ``type``.

* ``queue``: String

  When messages are received by this edge listener, they are passed to this
  queue. The value of this queue is a name, which must correspond to a key in
  the top-level ``queue`` section.

``smtp`` Edges
""""""""""""""

SMTP Edges produce an |SmtpEdge| object from the extra keys given in the edge
sub-section. These keys are:

* ``listener``: Dictionary

  This mapping defines how to open the listening socket. It takes two keys,
  ``interface`` and ``port``. By default, these are ``'127.0.0.1'`` and
  ``25``, respectively.

* ``hostname``: String

  This is the string presented as the machine's hostname in the SMTP banner
  message. By default, this will be the machine's FQDN.

* ``max_size``: Integer

  This is the maximum allowed size, in bytes, of incoming messages on this SMTP
  edge. Larger messages are rejected. By default, there is no size limit.

* ``tls``: Dictionary

  This mapping, which takes the same keys as the keyword parameters to
  :func:`~ssl.wrap_socket`, both enables and configures TLS encryption on this
  SMTP edge. By default, TLS is not enabled.

* ``tls_immediately``: Boolean

  Defines whether or not TLS should handshake immediately on connection, or if
  a socket is only encrypted if the user runs ``STARTTLS``. By default, sessions
  are only encrypted on ``STARTTLS``.

* ``rules``: Dictionary

  This sub-section gives extra configurability in the internals of the SMTP
  edge. It has its own set of keys, all of which are optional:

  * ``banner``: String

    This string is presented to connecting clients as the SMTP banner message.
    It can contain ``{fqdn}`` or ``{hostname}`` to substitute in the respective
    information about the local machine. By default, a generic banner message is
    used.

  * ``dnsbl``: String

    Specifies a server that will be queried as a DNS blocklist. If a connecting
    client "hits" on the DNS blocklist, it is rejected outright. By default, no
    DNS blocklists are checked.

  * ``reject_spf``: List

    Specifies a list of SPF result types that are rejected in an SMTP session.
    Valid strings in the list are: ``pass``, ``permerror``, ``fail``,
    ``temperror``, ``softfail``, ``none``, and ``neutral``. By default, no SPF
    results are rejected.

  * ``only_senders``: List

    Only the email addresses in this list will be accepted when given in the
    ``MAIL FROM:<>`` command from a client. By default, all senders are
    accepted.

  * ``only_recipients``: List

    Only the email addresses in this list will be acceped when given in the
    ``RCPT TO:<>`` commands from the client. By default, all recipients are
    accepted.

  * ``require_credentials``: Dictionary

    If this option is given, clients are required to authenticate before mail
    can be accepted. The keys and values in this dictionary are the usernames
    and passwords, respectively, of the valid authentication credentials.

``custom`` Edges
""""""""""""""""

Only one additional key is required by the ``"custom"`` edge type:

* ``factory``: String, required

  This is a string of the form ``package.module:symbol``. The package and
  module portion are imported with :func:`importlib.import_module`, and then
  the symbol is fetched from the loaded module with :func:`getattr()`.

  The result of loading the symbol must be a function that takes two arguments,
  the options object (that contains the ``type``, ``queue``, and ``factory``
  keys as well as any others as necessary) and the |Queue| object that the edge
  should delivery received messages to::

    def edge_factory(options, queue):
        if 'foo' in options:
            return FooEdge(options.stuff, queue)
        else:
            return BarEdge(options.baz, queue)

