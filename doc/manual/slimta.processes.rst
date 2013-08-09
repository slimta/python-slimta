
.. include:: /global.rst

Configuring the Processes
=========================

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
  overriden by the ``--no-daemon`` command-line option. This value is False by
  default.

* ``user``: String

  If given, the process will attempt to drop root privileges to this username.
  This is useful for when using privileged ports 25, 465, and/or 587. By
  default, privileges are not dropped by the process.

* ``group``: String

  Like the ``user`` option, the process will attempt to drop privileges to this
  group name. By default, privileges are not dropped by the process.

* ``stdout``: String

  If given, this path will be opened in append-mode (and created if necessary)
  and all standard output will be written to it instead of the console. This is
  particularly useful when daemonized. By default, the standard output stream is
  not redirected.

* ``stderr``: String

  Like the ``stdout`` option, this redirects the standard error stream to the
  given path in append mode. By default, the standard error stream is not
  redirected.

* ``logging``: Dictionary

  See the section on logging below. It's often convenient to put logging configs
  in a separate config file, like in the example above. By default, debug-level
  logging is written to standard output.

Logging Configuration
"""""""""""""""""""""

.. _dictionary schema: http://docs.python.org/2/library/logging.config.html#configuration-dictionary-schema
.. _logging.conf: https://github.com/slimta/slimta/blob/master/etc/logging.conf.sample

Because the ``logging`` sub-section is parsed into a dictionary-like object, it
is compatible with the :func:`logging.config.dictConfig` function. The
`dictionary schema`_ explains how to use this configuration, and the
`logging.conf`_ sample config has a good starting point.

A more advanced, logging config that produces log files ready for rotation in a
readable and parseable format might look like this::

    version: 1

    formatters: {
      console: {
        format: '%(levelname)-8s %(name)-15s %(message)s'
      }
      default: {
        format: '%(asctime)s %(levelname)s %(name)s %(message)s'
      }
    }

    handlers: {
      console: {
        class: 'logging.StreamHandler'
        level: DEBUG
        formatter: console
        stream: 'ext://sys.stdout'
      }
      file: {
        class: 'logging.handlers.WatchedFileHandler'
        level: DEBUG
        formatter: default
        filename: '/var/log/slimta/slimta.log'
      }
    }

    loggers: {
      celery: {
        level: WARNING
        propagate: True
      }
      slimta: {
        level: DEBUG
        propagate: True
      }
    }

    root: {
      level: DEBUG
      handlers: [file]
    }

    # vim:sw=2:ts=2:sts=2:et:ai:

