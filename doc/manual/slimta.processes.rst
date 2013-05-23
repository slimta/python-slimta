
.. include:: /global.rst

Configuring the Processes
=========================

.. toctree::
   :hidden:

   slimta.processes.logging

.. _slimta.conf: https://github.com/icgood/slimta/blob/master/etc/slimta.conf.sample

The first section in ``slimta.conf`` is ``process``::

    process: {
      slimta: {
        daemon: False
        logging: @"logging.conf"
      }
    
      worker: {
        daemon: False
        logging: @"logging.conf"
      }
    }

It has two sub-sections, ``slimta`` and ``worker``, which manage settings for
the ``slimta`` and ``slimta-worker`` executables, respectively. Each sub-section
shares the same possible settings:

* ``daemon``: Boolean

  Whether or not the executables should daemonize on startup. This option can be
  overriden by the ``--no-daemon`` command-line option.

* ``user``: String

  If given, the process will attempt to drop root privileges to this username.
  This is useful for when using privileged ports 25, 465, and/or 587.

* ``group``: String

  Like the ``user`` option, the process will attempt to drop privileges to this
  group name.

* ``stdout``: String

  If given, this path will be opened in append-mode (and created if necessary)
  and all standard output will be written to it instead of the console. This is
  particularly useful when daemonized.

* ``stderr``: String

  Like the ``stdout`` option, this redirects the standard error stream to the
  given path in append mode.

* ``logging``: Sub-section

  See the :doc:`page on logging <slimta.processes.logging>`.

