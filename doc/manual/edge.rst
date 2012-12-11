
.. include:: /global.rst

Edge Services
=============

The term *edge* is not necessarily common among other *MTAs*. It was adapted
loosely by *slimta* from the `Edge Transport Server Role`_ in Microsoft
Exchange, but the name is about where the similarities end.

In *slimta*, an edge service are those that are listening for new messages
entering the system. The protocol does not matter, an edge service produces an
|Envelope| object and hands it off to the next stage of delivery.

Edge services usually send their requests to and receive their responses from a
*queue* service. That means the response delivered to the client does not
signify whether the message was successfully delivered, but rather that the
*queue* service has taken responsibility for its delivery. An edge service
**may** be configured to deliver directly to a relay service, creating a form of
email message proxy.

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
   *250 2.6.0 Message queued as e6482085-5322-4254-8654-2d1bd59ba6cd*
   QUIT
   *221 2.0.0 Bye*

SMTP edge services are somewhat unique in that they control not just the receipt
of and response to the message, but also a lot of interim requests. A server may
respond negatively to any command sent to it by the client, and often, crucial
policies are implemented that way. For example, if you are sure you don't want
to accept messages from a certain IP (e.g. known spammers) you would want to
limit the amount of memory and CPU cycles they consume by rejecting ``MAIL`` or
``RCPT`` commands.

Creating SMTP Edge Objects
''''''''''''''''''''''''''

::

   local rec = ratchet.socket.prepare_tcp("0.0.0.0", 25)
   local socket = ratchet.socket.new(rec.family, rec.socktype, rec.protocol)
   socket:setsockopt("SO_REUSEADDR", true)
   socket:bind(rec.addr)
   socket:listen()

   local bus_server, bus_client = slimta.bus.new_local()

   local smtp_edge = slimta.edge.smtp.new(socket, bus_client)

Once we have our new ``smtp_edge`` object, we most likely want to customize its
behavior.

Basic Behavior Changes
''''''''''''''''''''''

One of the first things to do with our ``smtp_edge`` object is to set the new
banner message, to give it a more personal touch with
:func:`~slimta.edge.smtp.set_banner_message()`::

   smtp_edge:set_banner_message("220", hostname .. " ESMTP Mail Gateway")

It is recommended that the the banner message start with the local hostname
followed by ``ESMTP``, some old/bad clients may depend on that.

The next low-hanging fruit is to set a maximum message size allowed by the
server. This will prevent clients from abusing the mail server, and can be used
to enforce storage size policies. This is done with
:func:`~slimta.edge.smtp.set_max_message_size()`::

   smtp_edge:set_max_message_size(78643200)

Finally, with the default settings an SMTP edge server will wait indefinitely
for data from the clients, which could tie up server file descriptors. This is
preventable with :func:`~slimta.edge.smtp.set_timeout()`::

   smtp_edge:set_timeout(30.0)

Encryption
''''''''''

For secure SMTP sessions, `TLS`_ can encrypt either the entire socket session or
starting encryption when the client sends the ``STARTTLS`` command. Either way,
you must create a *ratchet* SSL context object::

   local ssl = ratchet.ssl.new(ratchet.ssl.TLSv1_server)
   ssl:load_certs("/path/to/cert.pem")

Once you have your context ready, a simple call to
:func:`~slimta.edge.smtp.enable_tls()` will tell the SMTP edge object to use
it::

   smtp_edge:enable_tls(ssl)

That call will enable the ``STARTTLS`` ESMTP extension, allowing clients to
encrypt the session by calling the ``STARTTLS`` command. To ensure that sockets
are encrypted immediately, send true as a second parameter::

   smtp_edge:enable_tls(ssl, true)

This method should **not** be used on port 25, according to the RFCs, and should
be avoided in favor of ``STARTTLS``. If your use case requires it, make sure you
use a different port (usually 465) and also have an unencrypted SMTP edge on
port 25.

Authentication
''''''''''''''

*MSAs* will usually require clients to authenticate themselves as a valid sender
as a precaution to prevent spammers from hijacking the server. This is done as
per `RFC 4954`_ with challenge-response mechanisms and the ``AUTH`` ESMTP
extension.

:mod:`slimta.edge.smtp.auth` objects control the behavior of SMTP edge
authentication. The first step is to create an auth object and register its
supported mechanisms. Then, let the SMTP edge object know that it should use the
authentication with :func:`~slimta.edge.smtp.enable_authentication()`::

   local function get_auth_secret(username)
       return auth_secrets[username]
   end

   local auth = slimta.edge.smtp.auth.new()
   auth:add_mechanism("PLAIN", get_auth_secret)
   auth:add_mechanism("LOGIN", get_auth_secret)
   auth:add_mechanism("CRAM-MD5", get_auth_secret, local_hostname)

   smtp_edge:enable_authentication(auth)

Command Validators
''''''''''''''''''

As mentioned before, SMTP edge services may respond negatively to any client
command. This is done by adding validator functions. Validator functions can
modify the reply (which defaults to success) of the commands they are registered
to. They are registered with :func:`~slimta.edge.smtp.set_validator()`::

   local function ensure_secure_and_authed(session, reply, address)
       if not session.authed or session.security ~= "TLS" then
           reply.code = "550"
           reply.message = ("<%s> Not authorized"):format(address)
           reply.enhanced_status_code = "5.7.1"
       end
   end

   smtp_edge:set_validator("MAIL", ensure_secure_and_authed)

That example will register a validator to be called when the client sends the
``MAIL`` command. The validator takes a ``session`` object parameter, which has
properties such as ``authed``, ``from_ip``, ``security``, and ``ehlo_as``. These
properties should probably not be modified unless you know what you are doing.

The validator also takes a ``reply`` object parameter. You can modify this
object's ``code``, ``message``, and ``enhanced_status_code`` properties to
modify the server's reply to the command. The server will recognize changes and
act accordingly, for example changing ``code`` to an error code may prevent the
SMTP session from proceeding until the client retries the command and gets a
success.

Finally, the validator has access to any extra data from the command as
additional parameters. These are only useful for commands that receive data,
such as ``EHLO``, ``MAIL``, and ``RCPT``. This data will be stripped down into a
useful form, for example for ``MAIL`` and ``RCPT`` the parameter is an email
address rather than the full ``TO:<address@...>`` expression.

If you add a validator for the ``STARTTLS`` command and are using immediate
(socket-level) encryption, the validator will be called immediately when a
client connects and the ``reply`` object will be igored.

.. _edge-http:

HTTP Edge Services
""""""""""""""""""

*slimta* provides an extra built-in edge service using HTTP. There is no
standard way of sending email messages over HTTP, so *slimta's* method is
custom. Information normally sent using SMTP's ``EHLO``, ``MAIL``, and ``RCPT``
commands are sent as ``X-Ehlo``, ``X-Sender``, and ``X-Recipient`` HTTP headers,
respectively. HTTP edge services provide no capabilities for encryption or
authentication, if this becomes a popular utility then these features may be
added. However, the HTTP edge service is provided primarily as a
proof-of-concept example of non-SMTP edges.

::

   local rec = ratchet.socket.prepare_tcp("0.0.0.0", 8025)
   local socket = ratchet.socket.new(rec.family, rec.socktype, rec.protocol)
   socket:setsockopt("SO_REUSEADDR", true)
   socket:bind(rec.addr)
   socket:listen()

   local bus_server, bus_client = slimta.bus.new_local()

   local http_edge = slimta.edge.http.new(socket, bus_client)

Using the ``http_edge`` object as above, the following could be an example of a
client session, with edge server responses emphasized:

.. parsed-literal::

   POST /email HTTP/1.0
   X-Ehlo: client.example.com
   X-Sender: sender@client.example.com
   X-Recipient: recipient1@client.example.com
   X-Recipient: recipient2@client.example.com
   Content-Type: message/rfc822
   Content-Length: 150

   From: sender@client.example.com
   To: recipient1@client.example.com
   Cc: recipient2@client.example.com
   Subject: slimta testing

   HTTP message submission!
   *HTTP/1.0 200 Message queued as e6482085-5322-4254-8654-2d1bd59ba6cd*
   *Content-Length: 36*

   *e6482085-5322-4254-8654-2d1bd59ba6cd*

Receiving Edge Messages
"""""""""""""""""""""""

Once you have an edge object, either :class:`~slimta.edge.smtp.SmtpEdge` or
:class:`~slimta.edge.http.HttpEdge`, you need to wait for new connections and
handle them.  The :func:`~slimta.edge.smtp.accept()` function does the trick.
It returns an object that, when called as a function, handles the connection,
sends a bus request and receives the response, and returns that response to the
client.  Because you would want an edge service to accept many, simultaneous
connections, this object should usually be attached to a greenlet. It's not as
complicated as it sounds::

   while true do
       local callable = smtp_edge:accept()
       ratchet.thread.attach(callable)
   end

.. _Edge Transport Server Role: http://technet.microsoft.com/en-us/library/bb124701.aspx
.. _ZeroMQ: http://www.zeromq.org/
.. _RFC 5321: http://tools.ietf.org/html/rfc5321
.. _RFC 2821: http://tools.ietf.org/html/rfc2821
.. _RFC 821: http://tools.ietf.org/html/rfc821
.. _TLS: http://en.wikipedia.org/wiki/Transport_Layer_Security
.. _RFC 4954: http://tools.ietf.org/html/rfc4954

