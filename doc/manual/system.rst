
.. include:: /global.rst

System Helpers
==============

.. toctree::
   :hidden:

Long-running applications usually require some special tricks for management and
security.

Daemonization
"""""""""""""

Running |slimta| in the background as a daemon is relatively easy::

   pid = slimta.system.daemonize()

:func:`slimta.system.daemonize()` can be described with the following
pseudo-code::

   fork()
   setsid()
   fork()
   chdir("/")
   umask(0)
   setsid()
   return getpid()

Often it is not desired to leave standard I/O streams connected to the terminal.
Before calling :func:`~slimta.system.daemonize()`, you should first call
:func:`slimta.system.redirect_stdio()`.

Dropping System Privileges
""""""""""""""""""""""""""

Most ports that |slimta| systems will often need to open require root
privileges, such as port 25. However, once these sockets are open, there is
little reason to retain those privileges.

A call to :func:`slimta.system.drop_privileges()` is *highly* recommended after
opening all ports, if running |slimta| as root.

