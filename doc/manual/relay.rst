
.. include:: /global.rst

Relay Services
==============

Delivery attempts in *slimta* are done by *relay* services. A delivery attempt
can be made using any medium, but are typically one of two methods. *MSAs* and
intermediate *MTAs* use SMTP to deliver to the "next-hop" *MTA*. *MDAs* are the
final destination of messages and will *relay* to long-term storage for the user
to receive with POP3 or IMAP.

Email delivery works by always relaying email messages from towards hosts that
will know more about how to deliver it. That implies that every host has *some*
logic on how it wants to move an email from point A to point B. This is called
*routing* logic, and will depend completely on the environment. Most *MTAs* that
are relaying messages will use *MX* record lookup on the domain of the recipient
to find an SMTP "next-hop". Internal *MTAs* may have custom routing logic like
delivering messages to the appropriate internal datacenter where the recipient's
mailbox is hosted.

Relaying Manager
""""""""""""""""

*Edge* services are relatively simple, they can all receive messages and they
can all deliver them using a client :doc:`bus <bus>` to a *queue* service.
Relaying is a little more complicated, as a single request from a server bus
could contain messages destined for different relayers. As such, a relaying
manager is necessary to be aware of all the different relayers and send messages
to them appropriately.

Creating a relaying manager is simple::

   local relay_server, relay_client = slimta.bus.new_local()

   local relay = slimta.relay.new(relay_server)

Once you have your :mod:`~slimta.relay` object, you can use its
:func:`~slimta.relay.add_relayer()` method to make the manager aware of a
particular relayer. There is no limitation to the kinds of relayers you can
attach to a manager; you could have several different :ref:`SMTP relayers
<relay-smtp>` with different behaviors added under different names.

Routing logic can specify a relayer with which message should be delivered like
so::

   local message = get_some_message_object()
   message.envelope.dest_relayer = "SMTP"

Which would specify that the message should be delivered using whichever relayer
was attached to the relaying manager using ``"SMTP"`` as its name.

.. _relay-smtp:

SMTP Relayers
"""""""""""""

Using SMTP to move a message to its "next-hop" is the standard (and only) method
when delivering a message to an address that your system does not host. SMTP
relaying by an *MTA* should not use authentication, but may (and should) try to
secure the connection with *TLS*.

Creating a :mod:`~slimta.relay.smtp` relayer is simple::

   local smtp = slimta.relay.smtp.new()

   relay:add_relayer("SMTP", smtp)

Or, you could be more specific and say your hostname is ``"server.example.com"``
and you only want to use IPv6 connections::

   local smtp = slimta.relay.smtp.new("server.example.com", "AF_INET6")

Alternatively, the string sent with the ``EHLO`` command to remote servers can
be dynamic. If you pass a function in to the constructor or use
:func:`~slimta.relay.smtp.set_ehlo_as()` with a function, that function will be
called for every session to generate an EHLO string. The argument to that
function will be an opaque session object with three useful attributes:
``messages``, ``host``, and ``port``. The ``messages`` attribute is a table
array of :mod:`~slimta.message` objects to be relayed on the session, ``host``
is a string hostname, and ``port`` is the port number.

Outbound encryption is generally desired, as well. As the client, encryption
opens up the possibility of server certificate validation, to be sure the server
is who it says it is. Enable encryption on outbound connections with
:func:`~slimta.relay.smtp.use_security()`::

   local ssl = ratchet.ssl.new(ratchet.ssl.TLSv1_client)
   ssl:load_certs(nil, "/path/to/certs/")

   smtp:use_security("starttls", ssl)

See `SSL_CTX_load_verify_locations`_ **CApath** argument for details on how to
use certificate paths properly.

.. _relay-maildrop:

Maildrop Relayers
"""""""""""""""""

As a proof-of-concept for delivering locally (and thus using *slimta* as an
*MDA*), the :mod:`~slimta.relay.maildrop` module provides a relayer that calls
the ``maildrop`` command (provided by `Courier`_) to deliver the message to a
Maildir::

   local maildrop = slimta.relay.maildrop.new(nil, 60.0)

   relay:add_relayer("maildrop", maildrop)

When a message is relayed through this relayer, a new process is started of the
form ``maildrop -f <sender>`` where ``<sender>`` is the sender address from the
message envelope. The raw message is written to process's stdin, and
any error messages are read from stderr. The process's exit code defines whether
or not the relayer was successful.

Keep in mind, you must configure maildrop to deliver with a ``.mailfilter`` file
or equivalent.

.. _SSL_CTX_load_verify_locations: http://www.openssl.org/docs/ssl/SSL_CTX_load_verify_locations.html
.. _Courier: http://www.courier-mta.org/maildrop/

