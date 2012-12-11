
.. include:: /global.rst

Deciphering Message Delivery Responses
======================================

Most :doc:`buses <bus>` in *slimta* take table arrays of :mod:`~slimta.message`
objects as requests and expect table arrays of :mod:`~slimta.message.response`
objects as responses. These :mod:`~slimta.message.response` objects are very
important to deciding whether the message was successfully handled or needs
further processing.

Responses have two attributes, ``code`` and ``message``. The ``code``
corresponds to a three digit string using SMTP reply codes. For example, codes
that start with *2* are considered success codes, codes that start with *4* are
temporary failures, and codes that start with *5* are permanent errors.

The ``message`` attribute is a more generic, human-readable description of the
error or success. No format can be assumed about this string, it is only useful
to a human through logging or other display. If :doc:`bounces <bounces>` are
generated, this message may help the message sender figure out what went wrong.

