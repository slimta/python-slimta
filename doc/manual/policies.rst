
.. include:: /global.rst

.. _cr.yp.to: http://cr.yp.to/immhf/envelope.html#received
.. _SpamAssassin: http://spamassassin.apache.org/

Policy Implementation
=====================

Many policies in |slimta| will be applied directly before queuing the message.
These are called queue policies, and they are especially useful because they
are executed **once** for every message and the results are persistently
stored.  Spam filtering is an example of a great queue policy, because it is
expensive and the results can be stored in the |Envelope| object as an
attribute or header.

Other policies in |slimta| will be applied directly before each delivery
attempt, called relay policies. A great example of a relay policy would be
recipient forwarding looked up from a database; you would want to make sure the
latest forwarding rules are applied on each delivery attempt, to not use a
stale rule. At the moment, no relay policies are included with |slimta|.

.. _policy-add-date-header:

``Date`` Header
"""""""""""""""

Addition of a ``Date:`` header is a necessary policy for most MTAs, when the
original message lacks one. The header generally uses local time-zones written
as acronyms, for better human-readability.

The ``Date:`` header addition is a queue policy, given by the
:class:`~slimta.policy.headers.AddDateHeader` class::

    from slimta.policy.headers import AddDateHeader
    queue.add_policy(AddDateHeader())

.. _policy-add-message-id-header:

``Message-Id`` Header
"""""""""""""""""""""

A ``Message-Id:`` header should be added by the first *MTA* receiving the
message from the client, if not by the client itself. The header should not be
overridden by any subsequent MTA handling the message. A ``Message-Id`` will
look similar to an email address: left- and right-parts separated by an ``@``
with the whole thing surrounded by ``<`` and ``>``. The right-part of the ID
is usually the FQDN of the MTA that first received the message. The left-part
should be a string that tries to uniquely identify the message from all the
other messages the MTA has or will handle. This uniqueness is usually attained
by concatenating a randomly-generated UUID to a timestamp.

The ``Message-Id:`` header addition is a queue policy, given by the
:class:`~slimta.policy.headers.AddMessageIdHeader` class::

    from slimta.policy.headers import AddMessageIdHeader
    queue.add_policy(AddMessageIdHeader())

.. _policy-add-received-header:

``Received`` Header
"""""""""""""""""""

The ``Received:`` header is the most unique and complicated header of those that
MTAs should add to a message. The header should be pre-pended to every message,
so that the order that each MTA handled the message is preserved. The header
does not have a strict, RFC-mandated format, but `cr.yp.to`_ has a good
recommendation that fits what *most* good MTAs will do, and |slimta| attempts to
follow.

The ``Received:`` header addition is a queue policy, given by the
:class:`~slimta.policy.headers.AddReceivedHeader` class::

    from slimta.policy.headers import AddReceivedHeader
    queue.add_policy(AddReceivedHeader())

.. _policy-forwarding:

Recipient Forwarding
""""""""""""""""""""

Forwarding policies range from quite simple to exorbitantly complex. The
:class:`~slimta.policy.forward.Forward` policy included with |slimta| can only
handle *static* rules (e.g. not queried from a database) using regular
expression-based substitution.

Because the mappings are static and thus will never become stale like a database
lookup might, this is implemented as a queue policy, given by the
:class:`~slimta.policy.forward.Forward` class::

    from slimta.policy.forward import Forward
    
    fwd = Forward()
    fwd.add_mapping(r'(ian|icg)@example.com', 'admin@example.com')
    queue.add_policy(fwd)

.. _policy-spamassassin:

SpamAssassin
""""""""""""

The included spam filtering mechanism uses SpamAssassin_ by making a socket
connection to a ``spamd`` server. When used as a policy, the message is scanned
and a ``X-Spam-Status:`` header is added to the message with either ``"YES"`` or
``"NO"`` indicating spamminess. If spammy, another header ``X-Spam-Symbols:`` is
also added with the symbols used in the match.

SpamAssassin is an expensive operation, so it is implemented as a queue policy,
given by the :class:`~slimta.policy.spamassassin.SpamAssassin` class::

    from slimta.policy.spamassassin import SpamAssassin
    queue.add_policy(SpamAssassin())

