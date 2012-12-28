
.. include:: /global.rst

Edge Services
=============

The term *edge* is not necessarily common among other *MTAs*. It was adapted
loosely by *slimta* from the `Edge Transport Server Role`_ in Microsoft
Exchange, but the name is about where the similarities end.

In *slimta*, an edge service are those that are listening for new messages
entering the system. The protocol does not matter, an edge service produces an
|Envelope| object and hands it off to the next stage of delivery.

Edge services (usually) send their requests to and receive their responses from
a *queue* service. That means the response delivered to the client does not
signify whether the message was successfully delivered, but rather that the
*queue* service has taken responsibility for its delivery. An edge service
**may** be configured to deliver directly to a relay service, creating a form
of email message proxy.

.. _edge-smtp:

SMTP Edge Services
""""""""""""""""""

Traditionally, email *MTAs* receive messages from other *MTAs* or user email
clients using the SMTP protocol (`RFC 5321`_, `RFC 2821`_, `RFC 821`_). An SMTP
session delivering a message from a client to a server might look like this,
with server (edge) replies back to the client emphasized:

.. parsed-literal::

   *220 slimta.org ESMTP Mail Gateway*
   EHLO client.example.com
   *250-Hello client.example.com*
   *250-8BITMIME*
   *250-PIPELINING*
   *250-STARTTLS*
   *250 ENHANCEDSTATUSCODES*
   MAIL FROM:<sender@client.example.com>
   *250 2.1.0 <sender@client.example.com> Ok*
   RCPT TO:<recipient@server.example.com>
   *250 2.1.5 <recipient@server.example.com> Ok*
   DATA
   *354 Start mail input; end with <CRLF>.<CRLF>*
   ... email data ...
   .
   *250 2.6.0 Message queued as e64820855322425486542d1bd59ba6cd*
   QUIT
   *221 2.0.0 Bye*

SMTP edge services are somewhat unique in that they control not just the receipt
of and response to the message, but also a lot of interim requests. A server may
respond negatively to any command sent to it by the client, and often, crucial
policies are implemented that way. For example, if you are sure you don't want
to accept messages from a certain IP (e.g. known spammers) you would want to
limit the amount of memory and CPU cycles they consume by rejecting before the
before ``DATA``.

Creating SMTP Edge Objects
''''''''''''''''''''''''''

::

   from slimta.edge.smtp import SmtpEdge

   smtp = SmtpEdge(('', 25), queue)
   smtp.start()

.. _Edge Transport Server Role: http://technet.microsoft.com/en-us/library/bb124701.aspx
.. _RFC 5321: http://tools.ietf.org/html/rfc5321
.. _RFC 2821: http://tools.ietf.org/html/rfc2821
.. _RFC 821: http://tools.ietf.org/html/rfc821

