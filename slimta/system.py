# Copyright (c) 2012 Ian C. Good
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

"""Contains functions to simplify the usual daemonization procedures for long-
running processes.

"""

from __future__ import absolute_import

import os
import os.path
import sys
from contextlib import contextmanager
from pwd import getpwnam
from grp import getgrnam

__all__ = ['daemonize', 'redirect_stdio', 'drop_privileges', 'PidFile']


def daemonize():
    """Daemonizes the current process using the standard double-fork.
    This function does not affect standard input, output, or error.

    :returns: The PID of the daemonized process.

    """

    # Fork once.
    try:
        pid = os.fork()
        if pid > 0:
            os._exit(0)
    except OSError:
        return

    # Set some options to detach from the terminal.
    os.chdir('/')
    os.setsid()
    os.umask(0)

    # Fork again.
    try:
        pid = os.fork()
        if pid > 0:
            os._exit(0)
    except OSError:
        return

    os.setsid()
    return os.getpid()


def redirect_stdio(stdout=None, stderr=None, stdin=None):
    """Redirects standard output, error, and input to the given
    filenames. Standard output and error are opened in append-mode, and
    standard input is opened in read-only mode. Leaving any parameter
    blank leaves that stream alone.

    :param stdout: filename to append the standard output stream into.
    :param stderr: filename to append the standard error stream into.
    :param stdin: filename to read from as the standard input stream.

    """

    # Find the OS /dev/null equivalent.
    nullfile = getattr(os, 'devnull', '/dev/null')

    # Redirect all standard I/O to /dev/null.
    sys.stdout.flush()
    sys.stderr.flush()
    si = open(stdin or nullfile, 'r')
    so = open(stdout or nullfile, 'a+')
    se = open(stderr or nullfile, 'a+', 0)
    os.dup2(si.fileno(), sys.stdin.fileno())
    os.dup2(so.fileno(), sys.stdout.fileno())
    os.dup2(se.fileno(), sys.stderr.fileno())


def drop_privileges(user=None, group=None):
    """Uses the system calls :func:`~os.setuid` and :func:`~os.setgid` to drop
    root privileges to the given user and group. This is useful for security
    purposes, once root-only ports like 25 are opened.

    :param user: user name (from /etc/passwd) or UID.
    :param group: group name (from /etc/group) or GID.

    """
    if group:
        try:
            gid = int(group)
        except ValueError:
            gid = getgrnam(group).gr_gid
        os.setgid(gid)
    if user:
        try:
            uid = int(user)
        except ValueError:
            uid = getpwnam(user).pw_uid
        os.setuid(uid)


class PidFile(object):
    """.. versionadded:: 0.3.13

    Context manager which creates a PID file containing the current process id,
    runs the context, and then removes the PID file.

    An :py:exc:`OSError` exceptions when creating the PID file will be
    propogated without executing the context.

    :param filename: The filename to use for the PID file. If ``None`` is
                     given, the context is simply executed with no PID file
                     created.

    """

    def __init__(self, filename=None):
        super(PidFile, self).__init__()
        if not filename:
            self.filename = None
        else:
            self.filename = os.path.abspath(filename)

    def __enter__(self):
        if self.filename:
            with open(self.filename, 'w') as pid:
                pid.write('{0}\n'.format(os.getpid()))
            return self.filename

    def __exit__(self, exc_type, exc_value, traceback):
        if self.filename:
            try:
                os.unlink(self.filename)
            except OSError:
                pass


# vim:et:fdm=marker:sts=4:sw=4:ts=4
