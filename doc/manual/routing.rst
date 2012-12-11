
.. include:: /global.rst

Message Routing
===============

The SMTP protocol does not allow a client to explicitly tell a server where or
how to deliver a message. It is the server's responsibility to have *routing*
policies that tell it what to do with all messages that it accepts
responsibility for.

Static Routing
""""""""""""""

Sometimes the routing logic for a server is very simple. For example, if your
*MTA* simply looks up what storage server a mailbox is hosted on but always uses
the SMTP protocol and port 25, you don't want or need to look up the *MX*
records for recipient domains.

::

   local function get_storage_server(message)
       local rcpt_hash = hash(message.envelope.recipients[1])
       return storage_servers[rcpt_hash]
   end

   local static_routing = slimta.routing.static.new("SMTP", get_storage_server, 25)

   for i, message in ipairs(messages)
       static_routing:route(message)
   end

For each message, ``get_storage_server()`` would be called on the message to
figure out where to deliver it. Any argument to
:func:`~slimta.routing.static.new()` can be given as a function and *slimta*
will call that function with the :mod:`~slimta.message`, or they can be given as
a string or number literal.

MX Routing
""""""""""

*MX* routing is significantly more complicated than static routing. The problem
is, a message can have many recipients and each recipient can have *MX* records
pointing to a set of hosts. Furthermore, *MX* records should be cycled through
in order of priority in case one is unresponsive.

Although the input of an *MX* routing policy is one :mod:`~slimta.message`
object, the output can potentially be multiple message objects. For every unique
host, the message is split such the new message's recipients all resolved to
that host. If any recipient could not be queried (e.g. it did not have a
fully-qualified domain name) that recipient is left in the original message
object.

It will be easier to understand with an example::

   local mx_routing = slimta.routing.mx.new()

   local message = get_current_message()
   local new_messages, unroutable = mx_routing:route(message)

   for i, message in ipairs(new_messages) do
       local n_rcpt = #message.envelope.recipients
       local host = message.envelope.dest_host
       print(("%d recipients routing to %s."):format(n_rcpt, host))
   end

   print(("%d recipients were unroutable."):format(#unroutable.envelope.recipients))

Each new message in the example could be passed off to an :ref:`SMTP relayer
<relay-smtp>`.

Keep in mind that :doc:`buses <bus>` will expect the same number of responses as
requests. That is, if 10 messages are sent, exactly 10 responses are expected.
If *MX* routing splits one of those messages into 3, it might be hard to decide
which of those 3 messages' responses to send back. There is no good answer to
this, because the SMTP protocol only allows one response per message, even if
that message had many recipients. Generally it is safe to arbitrarily pick one
of the responses as the "representative".

