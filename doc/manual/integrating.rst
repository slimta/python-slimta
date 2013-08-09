
.. include:: /global.rst

Integrating Everything
======================

.. figure:: http://slimta.org/images/diagrams/reception-to-delivery.png
   :target: http://slimta.org/images/diagrams/reception-to-delivery.png
   :width: 100%
   :figwidth: 400px
   :align: right

   Diagram of an |Envelope| object's path from reception to delivery.

Piecing together the building blocks described in previous section is the last
crucial step in setting up your MTA. Nearly everything in |slimta| starts with
an |Edge| service which receives messages. They hand messages off to a |Queue|
service which talks to a |QueueStorage| object to persistently store messages.
The queue initiates delivery attempts with a |Relay| object.

Types of MTA Servers
--------------------

If you read the :doc:`terminology` page, there are `MTAs`_, `MDAs`_, `MSAs`_,
as well as other special configurations like `Smart hosts`_, `SMTP proxies`_,
or `Mail hubs`_. Depending on how you sub-class the different building blocks
of a |slimta| MTA, you can pretty much handle any of these configurations.

 * **MSA**: An MSA is all about taking a message from a mail client like
   Thunderbird and delivering it to its next hop on the Internet. Check out the
   :doc:`msa` page.

 * **MDA**: An MDA takes messages from the Internet and delivers them localy to
   something like `maildrop`_ or `dovecot`_. Check out the :doc:`mda` page.

 * **Smart Host**: A smart host takes messages and delivers them to a specific
   destination, rather then dynamically looking up the recipient's destination.
   Use a :class:`~slimta.relay.smtp.static.StaticSmtpRelay` object.

 * **SMTP proxy**: An SMTP proxy skips the |Queue| altogether, taking |Envelope|
   from the |Edge| and directly attempting delivery with a |Relay| and returning
   the success or failure back to the edge client. SMTP proxies are not yet
   supported by |slimta|, but they are on the radar.

 * **Mail Hubs**: A mail hub is a pretty generic term, but one particular use
   could be a dedicated spam scanner. It receives messages by any |Edge|, calls
   the :class:`~slimta.policy.spamassassin.SpamAssassin` policy, and delivers
   the result to another MTA with a
   :class:`~slimta.relay.smtp.static.StaticSmtpRelay` for further processing.

.. _MTAs: http://en.wikipedia.org/wiki/Message_transfer_agent
.. _MDAs: http://en.wikipedia.org/wiki/Mail_delivery_agent
.. _MSAs: http://en.wikipedia.org/wiki/Mail_submission_agent
.. _Smart hosts: http://en.wikipedia.org/wiki/Smart_host
.. _SMTP proxies: http://en.wikipedia.org/wiki/SMTP_proxy
.. _Mail hubs: http://en.wikipedia.org/wiki/E-mail_hub
.. _maildrop: http://www.courier-mta.org/maildrop/
.. _dovecot: http://wiki.dovecot.org/LDA

