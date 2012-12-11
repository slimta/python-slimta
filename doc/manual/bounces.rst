
.. include:: /global.rst

Non-Delivery Reports (Bounces)
==============================

Because a client that sent a message to an *edge* service will disconnect once
the message has been queued, there is no way of reporting to the client that the
message was delivered (successfully or unsuccessfully).

As such, the message sender should assume that a message was delivered
successfully unless told otherwise. If *slimta* failed to deliver a message,
either because of too many delivery attempts or a permanent error, it will
generate and deliver a *bounce* message back to the original sender address of
the message. From this *bounce* message, the sender should be able to tell which
message failed and why.

Generating Bounce Messages
""""""""""""""""""""""""""

|Bounce| objects are used to build *bounce* messages from the original
|Envelope| object and that message's |Reply| object.

The |Bounce| module allows for customization of the format of this bounce
message.

The static class member ``sender`` is the sender address to use. *Bounce*
messages are not "from" anyone, and thus the (RFC mandated) default is ``""``.

The *bounce* :class:`~email.message.Message` object is generated using the
original message's flattened :class:`~email.message.Message` surrounded by the
header and footer templates given in the |Bounce| class's ``header_template``
and ``footer_template`` static members.

The header and footer templates can contain the following variables, which will
be replaced with the associated data, if available:

* ``$(boundary)`` -- A generated string useful as a MIME boundary.
* ``$(sender)`` -- The origin message's sender address.
* ``$(client_name)`` -- The reverse-lookup of the client's IP, rarely available.
* ``$(client_ip)`` -- The client IP address string.
* ``$(protocol)`` -- The protocol used to receive the message.
* ``$(code)`` -- The error code from delivery attempt(s).
* ``$(message)`` -- The error message from delivery attempt(s).

