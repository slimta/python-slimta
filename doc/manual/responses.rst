
.. include:: /global.rst

.. _ENHANCEDSTATUSCODES: http://tools.ietf.org/html/rfc2034

Deciphering Message Delivery Responses
======================================

Because |slimta| is an email server, responses are always given as or translated
to SMTP-style code and message. That is, a 3-digit code and a free-form message
describing the success or what caused the failure. The |Reply| objects that
represent the responses have ``code`` and ``message`` properties for accessing
ad setting these values.

The 3-digit code will start with *2* for responses indicating success, such as
when a message was accepted by the destination. Codes that start with *4* or *5*
indicate some sort of failure, *4* indicating a transient failure where retrying
may resolve the issue, *5* indicating a permanent failure where a retry will not
succeed.

When using non-SMTP transports such as HTTP or :mod:`~slimta.relay.maildrop`,
responses will be translated to or from the expected format of the transport. 
HTTP, for example, uses *4xx* error codes for client errors (often permanent)
and *5xx* error codes for server errors (often transient).

If a response message begins with an ENHANCEDSTATUSCODES_ string, it is made
available by the ``enhanced_status_code`` property. This value *can* be used
programmatically, though |slimta| does not currently do so. No other part of the
response message should be parsed programmatically.

