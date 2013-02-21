
.. include:: /global.rst

Envelope Objects
================

In |slimta|, an email message is thought of like a 'snail mail' envelope, it's
not just the message contents but also sending and receiving addresses and other
logistical information. An |Envelope| object represents all of this information.

The :attr:`~slimta.envelope.Envelope.sender` and
:attr:`~slimta.envelope.Envelope.recipients` attributes hold the sending address
of the message and the list of intended recipients. The
:class:`~slimta.policy.forward.Forward` policy can be useful to modify the
intended recipients of a message.

Headers and Contents
""""""""""""""""""""

The headers and body of the email contents are split up into the
:attr:`~slimta.envelope.Envelope.headers` and
:attr:`~slimta.envelope.Envelope.message` attributes. The ``headers`` attribute
is a :class:`email.message.Message` object and can be used to view, add, and
delete *headers only*, it does not contain the message payload as described by
:class:`~email.message.Message` documentation. The ``message`` attribute of the
|Envelope| object is Python string containing the contents of the message,
everything after the headers.

For delivery, |slimta| |Relay| transports will call
:meth:`~slimta.envelope.Envelope.flatten` to convert the ``headers`` (with any
modifications) and ``message`` into a single string. After flattening, the
message headers portion of the generated string is guaranteed to use ``\r\n``
line endings.

.. _envelope-bounces:

Non-Delivery Reports (Bounces)
""""""""""""""""""""""""""""""

Because a client that sent a message to an *edge* service will disconnect once
the message has been queued, there is no way of reporting to the client that the
message was delivered (successfully or unsuccessfully).

As such, the message sender should assume that a message was delivered
successfully unless told otherwise. If |slimta| failed to deliver a message,
either because of too many delivery attempts or a permanent error, it will
generate and deliver a *bounce* message back to the original sender address of
the message. From this *bounce* message, the sender should be able to tell which
message failed and why.

Generating Bounce Messages
''''''''''''''''''''''''''

|Bounce| objects are used to build *bounce* messages from the original
|Envelope| object and that message's |Reply| object.

The |Bounce| class allows for customization of the format of this bounce
message. The static class member :attr:`~slimta.bounce.Bounce.sender` is the
sender address to use. *Bounce* messages are not "from" anyone, and thus the
(RFC mandated) default is an empty string (``""``).

The |Bounce| class is a sub-class of |Envelope| and can thus be used wherever a
regular |Envelope| is required. The |Bounce| message is generated using the
original message's flattened message data surrounded by the header and footer
templates given in the |Bounce| class's static
:attr:`~slimta.bounce.Bounce.header_template` and
:attr:`~slimta.bounce.Bounce.footer_template` members. See the API documentation
of these attributes for information on how they work.

