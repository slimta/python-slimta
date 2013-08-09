
.. include:: /global.rst

Mail Delivery Agent
===================

*Note:* This example requires the ``python-slimta-piperelay`` package.

Step 1: Create the Relay
------------------------

To get started, we create a |Relay| object. This is first because |Edge| depends
on |Queue| and |Queue| depends on |Relay|. For this example, we'll be using
:class:`~slimta.piperelay.MaildropRelay`, though you could just as easily
substitute one of the other classes in :mod:`slimta.piperelay`::

    from slimta.piperelay import MaildropRelay

    relay = MaildropRelay(timeout=10.0)

The result is a variable ``relay`` that can be passed in to the |Queue|
constructor. The ``relay`` will produce transient errors if the command takes
too long to reply. An unhandled exception will be raised if the ``maildrop``
command does not exist in the system path.

Step 2: Create the Queue
------------------------

Now that we have a |Relay|, we can create the |QueueStorage| and |Queue|
objects. The simplest |QueueStorage| sub-class is
:class:`~slimta.queue.dict.DictStorage`, which stores message contents and meta
in :class:`dict` objects. However, this can be made persistent using
:mod:`shelve`::

    import shelve
    from slimta.queue.dict import DictStorage

    env_db = shelve.open('envelope.db')
    meta_db = shelve.open('meta.db')
    storage = DictStorage(env_db, meta_db)

The resulting ``storage`` variable along with ``relay`` from *Step 1* can create
our |Queue|::

    from slimta.queue import Queue

    queue = Queue(storage, relay)
    queue.start()

Because queue objects inherit :class:`gevent.Greenlet`, they must call their
``.start()`` method to function properly.

Step 3: Add Queue Policies
--------------------------

Now that we have our |Queue|, we will most likely want to add various
|QueuePolicy| and |RelayPolicy| rules to affect behavior. MDAs should add
various headers, such as ``Date`` and ``Received``, for example::

    from slimta.policy.headers import *

    queue.add_prequeue_policy(AddDateHeader())
    queue.add_prequeue_policy(AddMessageIdHeader())
    queue.add_prequeue_policy(AddReceivedHeader())

Because an MDA configuration typically receives mail from the outside world, it
is likely you will want to scan this mail from spam. The
:class:`~slimta.policy.spamassassin.SpamAssassin` policy will add
the ``X-Spam-Status`` set to ``YES`` or ``NO`` for each message, which can be
used by maildrop to filter to a spam quarantine::

    from slimta.policy.spamassassin import SpamAssassin

    queue.add_prequeue_policy(SpamAssassin())

As with MSA configurations, MDAs will often find the
:class:`~slimta.policy.forward.Forward` policy useful as well.

Step 4: Create the Edge
-----------------------

The |Edge| is how messages are injected into the system from mail clients, and
now that we have a |Queue| object, we can create one. The most common |Edge|
for an MDA will obviously be :class:`~slimta.edge.smtp.SmtpEdge`, but you could
also create an edge service that receives messages by HTTP or even from the
filesystem. Most MDAs will use :class:`~slimta.edge.smtp.SmtpEdge` on the
RFC-specified port 25.

Creating an |Edge| can be very simple if you are not worried about how messages
are received or from whom::

    from slimta.edge.smtp import SmtpEdge

    tls_args = {'keyfile': '/path/to/key.pem', 'certfile': '/path/to/cert.pem'}
    edge = SmtpEdge(('', 25), queue, tls=tls_args)
    edge.start()

This will receive any messages from any sender intended for any recipient and
send it to the |Queue|. For an MDA however, we only want to accept emails sent
to recipients we host. To do this, we will sub-class
:class:`~slimta.edge.smtp.SmtpValidators` and restrict the addresses allowed by
the ``RCPT TO:<...>`` command::

    from slimta.edge.smtp import SmtpValidators

    class MyValidators(SmtpValidators):
        def handle_rcpt(self, reply, recipient):
            try:
                localpart, domain = recipient.rsplit('@', 1)
            except ValueError:
                reply.code = '550'
                reply.message = '5.7.1 <{0}> Not a valid address'
                return
            if domain.lower() != 'slimta.org':
                reply.code = '550'
                reply.message = '5.7.1 <{0}> Not authenticated'
                return

    # Your edge creation line would now look like...
    edge = SmtpEdge(('', 25), queue, tls=tls_args, validator_class=MyValidators)
    edge.start()

Your SMTP server will now reject a client's ``RCPT TO:<...>`` command if the
address is not on the ``slimta.org`` domain.

Step 5: Daemonizing
-------------------

You probably don't want to keep a terminal open the entire time your MTA is
running. There are some daemonization tools in the :mod:`slimta.system` module.
Their usage is relatively simple::

    import gevent
    from slimta import system

    gevent.sleep(0.5)
    system.drop_privileges('smtp-user', 'smtp-user')
    system.redirect_stdio()  # Redirects all streams to /dev/null by default.
    system.daemonize()

The :func:`~slimta.system.drop_privileges()` command is only necessary if you
ran your MTA as ``root``, which is necessary to create servers listening on
privileged ports such as 25, 587 or 465.

The :func:`gevent.sleep()` call is not always necessary, but sometimes gevent
will not have opened the ports by the time you drop privileges and then it will
fail, so calling a short sleep will make sure everything is ready.

Step 6: Profit
--------------

Once you have all your pieces together, you can simply let the system function::

    try:
        edge.get()
    except KeyboardInterrupt:
        pass

