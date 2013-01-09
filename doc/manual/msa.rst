
.. include:: /global.rst

Mail Submission Agent
=====================

Step 1: Create the Relay
------------------------

To get started, we create a |Relay| object. This is first because |Edge| depends
on |Queue| and |Queue| depends on |Relay|::

    from slimta.relay.smtp.mx import MxSmtpRelay

    tls_args = {'keyfile': '/path/to/key.pem', 'certfile': '/path/to/cert.pem'}
    relay = MxSmtpRelay(tls=tls_args, connect_timeout=20, command_timeout=10,
                                      data_timeout=20, idle_timeout=30)

The result is a variable ``relay`` that can be passed in to the |Queue|
constructor. The ``relay`` will be capable of opportunistic TLS and will produce
transient errors if remote servers take too long to reply.

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
|QueuePolicy| and |RelayPolicy| rules to affect behavior. MSAs should add
various headers, such as ``Date`` and ``Received``, for example::

    from slimta.policy.headers import *

    queue.add_prequeue_policy(AddDateHeader())
    queue.add_prequeue_policy(AddMessageIdHeader())
    queue.add_prequeue_policy(AddReceivedHeader())

Because our |Relay| above was :class:`~slimta.relay.smtp.mx.MxSmtpRelay`, we
should also use the :class:`~slimta.policy.split.RecipientDomainSplit` policy.
This makes sure that we relay each recipient to its correct domain MX record,
since an |Envelope| can have many recipients of many different domains::

    from slimta.policy.split import RecipientDomainSplit

    queue.add_prequeue_policy(RecipientDomainSplit())

Most MSAs trust that their clients aren't going to be sending spam, so we'll
leave discussion of the :class:`~slimta.policy.spamassassin.SpamAssassin`
policy for the :doc:`mda` section. The :class:`~slimta.policy.forward.Forward`
policy may prove useful in some MSA configurations.

Step 4: Create the Edge
-----------------------

The |Edge| is how messages are injected into the system from mail clients, and
now that we have a |Queue| object, we can create one. The most common |Edge|
for an MSA will obviously be :class:`~slimta.edge.smtp.SmtpEdge`, but you could
also create an edge service that receives messages by HTTP or even from the
filesystem. An :class:`~slimta.edge.smtp.SmtpEdge` should be created for the
RFC-specified port 587 and the deprecated SSL-only port 465.

Creating an |Edge| can be very simple if you are not worried about how messages
are received or from whom::

    from slimta.edge.smtp import SmtpEdge

    tls_args = {'keyfile': '/path/to/key.pem', 'certfile': '/path/to/cert.pem'}
    edge = SmtpEdge(('', 587), queue, tls=tls_args)
    edge.start()

This will receive any messages from any sender and send it to the |Queue|. In
our examples, because we chose an :class:`~slimta.relay.smtp.mx.MxSmtpRelay`,
this would also mean our MSA would be an `Open Relay`_. **This is BAD!** We
should add some sort of authentication::

    from slimta.smtp.auth import Auth, CredentialsInvalidError

    class MyAuth(Auth):
        def verify_secret(self, username, password, identity=None):
            if username != 'testuser' or password != 'testpassword':
                raise CredentialsInvalidError()
            return 'testuser'
        def get_secret(self, username, identity=None):
            if username == 'testuser':
                return 'testpassword', 'testuser'
            raise CredentialsInvalidError()

    # Your edge creation line would now look like...
    edge = SmtpEdge(('', 587), queue, auth_class=MyAuth, tls=tls_args)
    edge.start()

Now, that will *allow* clients to authenticate, but it will not stop them from
sending messages if they haven't authenticated. For that, we need to add an
:class:`~slimta.edge.smtp.SmtpValidators`::

    from slimta.edge.smtp import SmtpValidators

    class MyValidators(SmtpValidators):
        def handle_mail(self, reply, sender):
            if not self.session.auth_result:
                reply.code = '550'
                reply.message = '5.7.1 <{0}> Not authenticated'
                return

    # Your edge creation line would now look like...
    edge = SmtpEdge(('', 587), queue, tls=tls_args,
                    validator_class=MyValidators, auth_class=MyAuth)
    edge.start()

Your SMTP server will now reject a client's ``MAIL FROM:<...>`` command if they
have not first issued a successful ``AUTH`` command. If the client cannot issue
their ``MAIL FROM``, then the SMTP command sequence cannot continue and they
cannot send mail.

Configuring port 465 for SSL-only traffic looks very similar, with one extra
keyword argument. Don't worry, two |Edge| services may be configured and run
simultaneously::

    ssl_edge = SmtpEdge(('', 465), queue, tls_tls_args, tls_immediately=True,
                        validator_class=MyValidators, auth_class=MyAuth)
    ssl_edge.start()

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

.. _MSA: http://en.wikipedia.org/wiki/Mail_submission_agent
.. _Open Relay: http://en.wikipedia.org/wiki/Open_mail_relay

