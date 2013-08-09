
.. include:: /global.rst

Application Usage
=================

.. _config package: http://www.red-dove.com/config-doc/

.. toctree::
   :hidden:

   slimta.processes
   slimta.edges
   slimta.queues
   slimta.relays

Building your own MTA from the ``python-slimta`` building blocks is great, but
it's not for everyone. This guide walks you through setting up and configuring
the ``slimta`` application, which glues together all the pieces with easy-to-use
configuration files.

The configuration files are interpreted using the `config package`_, which
provides a great combination of convenience and readability. Config data is
organized with keys (mappings) and lists, similar to JSON, with extra features
like key references and file inclusion. The included sample configs use some of
these features, as a reference.

* `Getting Started <https://github.com/slimta/slimta#getting-started>`_
* :doc:`slimta.processes`
* :doc:`slimta.edges`
* :doc:`slimta.queues`
* :doc:`slimta.relays`

