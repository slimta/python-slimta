
.. include:: /global.rst

Implementing Policies
=====================

.. toctree::

   routing

Adding Headers
""""""""""""""

While *MTAs* should usually leave message contents alone, the RFCs do specify
some **additions** to be made to message headers.

Adding ``Date`` Header
''''''''''''''''''''''

The ``Date:`` header should be added to messages that don't already have one as
per *RFC 2822*. The behavior of this addition is controlled by the
:mod:`~slimta.policies.add_date_header` module. Create one of these objects and
use it to add ``Date:`` headers to messages like so::

   local date_header = slimta.policies.add_date_header.new()
   for i, message in ipairs(messages) do
       date_header:add(message)
   end

If the messages do not already have the header, one is generated and added.
Otherwise, existing ``Date:`` headers are left alone.

Adding ``Received`` Header
''''''''''''''''''''''''''

A new ``Received:`` header should be prepended to every message passing through
the *MTA* as per *RFC 2821*. The behavior of this addition is controlled by the
:mod:`~slimta.policies.add_received_header` module. Create one of these objects
and use it to add ``Received:`` headers to messages like so::

   local received_header = slimta.policies.add_received_header.new()
   for i, message in ipairs(messages) do
       received_header:add(message)
   end

A message can (and will) have many ``Received:`` headers, existing ones are left
alone.

Adding ``Message-Id`` Header
''''''''''''''''''''''''''''

The ``Message-Id:`` header should be added to messages that don't already have
one as *RFC 2822*. The behavior of this addition is controlled by the
:mod:`~slimta.policies.add_message_id_header` module. Create one of these
objects and use it to add ``Message-Id:`` headers to messages like so::

   local msgid_header = slimta.policies.add_message_id_header.new(my_hostname)
   for i, message in ipairs(messages) do
       msgid_header:add(message)
   end

If the messages do not already have the header, one is generated and added.
Otherwise, existing ``Message-Id:`` headers are left alone.

Recipient Rewriting (Forwarding)
""""""""""""""""""""""""""""""""

Receipient rewriting is a fairly common policy among *MTAs*. That is, the *MTA*
scans the recipients for patterns that it should rewrite. This could be a
one-to-one rewrite (e.g. rewrite ``abuse@example.com`` to
``postmaster@example.com``) or a many-to-one (e.g. rewrite any address
``@example.com`` to ``admin@example.com`` as a catchall).

This task is implemented in *slimta* using `Lua patterns`_ and `gsub`_ by the
:mod:`slimta.policies.forward` module. An object is created given a mapping
table. This table defines a sequence of translations to be made to each message
recipient. Each translation defines the arguments to `gsub`_, which is then
called to rewrite the recipient. If `gsub`_ does not match the pattern anywhere
in the recipient, the next translation in the sequence is tried until there is a
match or until the end of the translation list is reached. No more than 1
translation will ever be applied to a recipient.

Consider the following rewriting::

   local fwd = slimta.policies.forward.new({
       {pattern = "^staff%-([^%@]+)%@example%.com$", repl = "%1@staff.example.com"},
       {pattern = "^.*$", repl = "admin@example.com"},
   })

   for i, message in ipairs(messages) do
       fwd:map(message)
   end

Consider the recipient ``staff-johnnie@example.com``. It would match the first
pattern and be rewritten to ``johnnie@staff.example.com``. The second pattern,
which will match all strings, will not run because the first pattern matched.

The recipient ``testing@stuff.example.com`` would not match the first pattern
and thus the second pattern would rewrite it to ``admin@example.com``.

While not possible in our example, if no patterns match a recipient then the
recipient will be left untouched.

Policy Proxy
""""""""""""

Policies should usually be applied to all messages passing through a :doc:`bus
<bus>`. The best way to modify and apply policies is to use
:mod:`~slimta.bus.proxy` objects.

Policy proxies should be placed either pre-queue (between *edge* and *queue*
services) or post-queue (between *queue* and *relay* services). With pre-queue
proxies, you can add reception logging or apply any policy that you want enacted
before the message is stored by the *queue*. With post-queue proxies, you can
add delivery logging or apply any policy you want enacted before each delivery
attempt. Often, routing policies are best applied post-queue, so that if routing
data changes it will be noticed before every retry.

Create all the policy objects you want to use in a policy proxy, and then create
a filter function to apply them. Here's an example of a good pre-queue::

   local function prequeue_proxy(to_bus, messages)
       for i, message in ipairs(messages) do
           date_header:add(message)
           received_header:add(message)
           logging.reception(message)
       end
       local transaction = to_bus:send_request(messages)
       return transaction:recv_response()
   end

And a good example of a post-queue with :func:`static
<slimta.routing.static.new>` routing::

   local function postqueue_proxy(to_bus, messages)
       for i, message in ipairs(messages) do
           static_routing:route(message)
       end
       local transaction = to_bus:send_request(messages)
       local responses = transaction:recv_response()
       for i, message in ipairs(messages) do
           logging.delivery_attempt(message, responses[i])
       end
       return responses
   end

Once you have your filters, create your :mod:`proxies <slimta.bus.proxy>` with
something like this::

   local edge_server, edge_client = slimta.bus.new_local()
   local queue_in_server, queue_in_client = slimta.bus.new_local()
   local queue_out_server, queue_out_client = slimta.bus.new_local()
   local relay_server, relay_client = slimta.bus.new_local()

   local prequeue = slimta.bus.proxy.new(edge_server, queue_in_client, prequeue_proxy)
   local postqueue = slimta.bus.proxy.new(queue_out_server, relay_client, postqueue_proxy)

Notice you need to have extra bus's for the proxy, e.g. you are no longer directly
connecting *edge* and *queue* buses but rather going through a proxy.

.. _Lua patterns: http://www.lua.org/manual/5.2/manual.html#6.4.1
.. _gsub: http://www.lua.org/manual/5.2/manual.html#pdf-string.gsub
