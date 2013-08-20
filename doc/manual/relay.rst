
.. include:: /global.rst

.. _courier-maildrop: http://www.courier-mta.org/maildrop/
.. _dovecot-lda: http://wiki.dovecot.org/LDA
.. _pipe daemon: http://www.postfix.org/pipe.8.html
.. _Smart-Hosting: http://en.wikipedia.org/wiki/Smart_host

Relay Services
==============

Relay services are given an existing message and attempt to delivery it to the
message's next destination. In a traditional MTA, this next destination will be
looked up by the recipient's domain MX record and delivery is done with SMTP.
In other cases, such as when acting as an *MDA*, |slimta| is the final
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

Email messages destined for a recipient address hosted elsewhere on the
Internet are relayed by querying the recipient domain's MX records. The result
is a prioritized list of hostnames that should be considered the next hop for
the message. The highest priority (given by the lowest MX preference number)
hostname is tried first, and lower priority hostnames should be tried
subsequently. MX relaying always uses port 25.

MX relaying can be done with the :class:`~slimta.relay.smtp.mx.MxSmtpRelay`
class, which will automatically cache MX records until their TTL and will
keep a :class:`~slimta.relay.smtp.static.StaticSmtpRelay` object for each
destination, so that connections are re-used::

    from slimta.relay.smtp.mx import MxSmtpRelay
    relay = MxSmtpRelay()

Recipient domains can be configured to ignore MX records and permanently
deliver to a certain hostname using the
:meth:`~slimta.relay.smtp.mx.MxSmtpRelay.force_mx` method::

    relay.force_mx('example.com', 'smarthost.example.com')

.. _relay-http:

HTTP Relaying
"""""""""""""

Similar to the :ref:`HTTP Edge <edge-http>`, HTTP can be used to relay messages
as the data payload of a request. The EHLO, sender, and recipients information
usually transferred in the SMTP request are sent as headers in the request.
Refer to the :mod:`slimta.relay.http` module for more information on how this
request is constructed.

If the remote host is an :ref:`HTTP Edge <edge-http>`, the response to the
request will most likely have an ``X-Smtp-Reply`` header that is used as the
message delivery |Reply| when returning to the queue. If the response does not
have this header, then :class:`~slimta.relay.PermanentRelayError` is raised for
``4XX`` codes and :class:`~slimta.relay.TransientRelayError` is raised for
``5XX`` codes.

HTTP relays are set up by creating a :class:`~slimta.relay.http.HttpRelay`
object::

    from slimta.relay.http import HttpRelay
    relay = HttpRelay('http://example.com:8025/messages/')

.. _relay-maildrop:

External Process Relaying
"""""""""""""""""""""""""

When |slimta| is configured to be the final destination for the email message,
it can stream a message to an external process to locally deliver the message.
This is how applications like `courier-maildrop`_ and `dovecot-lda`_ are given
messages. This method is modeled off the `pipe daemon`_ from postfix.  This
type of relay is provided in the :mod:`slimta.piperelay` module. Here's an
example of delivery to the ``maildrop`` command::

    from slimta.piperelay import MaildropRelay
    relay = MaildropRelay(timeout=10.0)

The :mod:`slimta.piperelay` module is packaged separately as an extension as
described in :ref:`External Process Delivery <pipe-relay>`. 

