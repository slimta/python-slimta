
.. include:: /global.rst

.. _courier-maildrop: http://www.courier-mta.org/maildrop/
.. _Smart-Hosting: http://en.wikipedia.org/wiki/Smart_host

Relay Services
==============

Relay services are given an existing message and attempt to delivery it to the
message's next destination. In a traditional MTA, this next destination will be
looked up by the recipient's domain MX record and delivery is done with SMTP.
In other cases, such as when acting as an *MDA*, *slimta* is the final
destination and delivery occurs locally with something like courier-maildrop_.

In any case, the relay will report either its attempt was a success or whether
failure was permanent or transient.

.. _relay-smtp-smarthost:

SMTP Smart-Host Relaying
""""""""""""""""""""""""

A very common type of relaying is sending all mail through to a single
destination. This could be a local mail server that delivers all mail to its
ISP mail servers, or it could be useful for a "front-line" of email servers
whose sole purpose is spam scanning before handing off for real processing and
routing. This static delivery is generally called `Smart-Hosting`_

Smart-Host relaying can be done with the
:class:`~slimta.relay.smtp.static.StaticSmtpRelay` class, which will maintain
a pool of connections to the destination that will be re-used if idle. For
example, to ensure no more than one open connection to a destination is open at
once::

    from slimta.relay.smtp.static import StaticSmtpRelay
    relay = StaticSmtpRelay('smarthost.example.com', pool_size=1)

.. _relay-smtp-mx:

SMTP MX Relaying
""""""""""""""""

Email messages destined for a recipient address hosted elsewhere on the Internet
are relayed by querying the recipient domain's MX records. The result is a
prioritized list of hostnames that should be considered the next hop for the
message. The highest priority (given by the lowest MX preference number)
hostname is tried first, and lower priority hostnames should be tried
subsequently. MX relaying always uses port 25.

MX relaying can be done with the :class:`~slimta.relay.smtp.mx.MxSmtpRelay`
class, which will automatically cache MX records until their TTL and will
keep a :class:`~slimta.relay.smtp.static.StaticSmtpRelay` object for each
destination, so that connections are re-used::

    from slimta.relay.smtp.mx import MxSmtpRelay
    relay = MxSmtpRelay()

Recipient domains can be configured to ignore MX records and permanently deliver
to a certain hostname using the
:meth:`~slimta.relay.smtp.mx.MxSmtpRelay.force_mx` method::

    relay.force_mx('example.com', 'smarthost.example.com')

.. _relay-maildrop:

Courier Maildrop Relaying
"""""""""""""""""""""""""

When *slimta* is configured to be the final destination for the email message,
it can use the ``maildrop`` command provided by courier-maildrop_ to deliver
messages locally. This relay is provided by the
:class:`~slimta.relay.maildrop.MaildropRelay` class::

    from slimta.relay.maildrop import MaildropRelay
    relay = MaildropRelay(timeout=10.0)

