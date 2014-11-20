# Copyright (c) 2013 Ian C. Good
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

""".. versionadded:: 0.3.21

Relays an |Envelope| locally to an external process. This functionality is
modeled closely off the pipe_ daemon in postfix.

.. _pipe: http://www.postfix.org/pipe.8.html
.. _courier-maildrop: http://www.courier-mta.org/maildrop/
.. _LDA: http://wiki.dovecot.org/LDA

"""

from __future__ import absolute_import

import re

from gevent import Timeout
from gevent import subprocess

from slimta.smtp.reply import Reply
from slimta.relay import Relay, PermanentRelayError, TransientRelayError
from slimta import logging

__all__ = ['PipeRelay', 'MaildropRelay', 'DovecotLdaRelay']

log = logging.getSubprocessLogger(__name__)


class PipeRelay(Relay):
    """When delivery attempts are made on this object, it will create a new
    subprocess and pipe envelope data to it. Delivery success or failure
    depends on the return code of the sub-process and error messages are pulled
    from standard error output.

    To facilitate passing the |Envelope| metadata, the process's command-line
    arguments can be populated with macros replaced using :py:meth:`str.format`
    with corresponding keywords:

    * ``{sender}``: The sender address.
    * ``{recipient}``: The first address in the recipient last.
    * ``{message_id}``: The ``Message-Id`` header.
    * ``{client_ip}``: The client IP address string.
    * ``{client_host}``: The reverse-lookup hostname of the client IP.
    * ``{client_ehlo}``: The EHLO string given by the client.
    * ``{client_protocol}``: The protocol used by the client.
    * ``{client_auth}``: The authentication identity used by the client.

    :param args: List of arguments used to spawn the external process, as you
                 would provide them to the :py:class:`~subprocess.Popen`
                 constructor. Each argument has :py:meth:`str.format` called on
                 it, as described above.
    :param timeout: The length of time a delivery is allowed to run before it
                    fails transiently, default unlimited.
    :param popen_kwargs: Extra keyword arguments passed in to the
                         :py:class:`~subprocess.Popen`.

    """

    permanent_error_pattern = re.compile(r'^5\.\d+\.\d+\s')

    def __init__(self, args, timeout=None, **popen_kwargs):
        super(PipeRelay, self).__init__()
        self.args = args
        self.timeout = timeout
        self.popen_kwargs = popen_kwargs

    def _process_args(self, env):
        macros = {'sender': env.sender,
                  'recipient': env.recipients[0],
                  'message_id': env.headers.get('Message-Id', ''),
                  'client_ip': env.client.get('ip', ''),
                  'client_host': env.client.get('host', ''),
                  'client_ehlo': env.client.get('name', ''),
                  'client_protocol': env.client.get('protocol', ''),
                  'client_auth': env.client.get('auth', '')}
        return [arg.format(**macros) for arg in self.args]

    def _exec_process(self, envelope):
        header_data, message_data = envelope.flatten()
        stdin = ''.join((header_data, message_data))
        with Timeout(self.timeout):
            args = self._process_args(envelope)
            p = subprocess.Popen(args, stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 **self.popen_kwargs)
            log.popen(p, args)
            stdout, stderr = p.communicate(stdin)
        log.stdio(p, stdin, stdout, stderr)
        log.exit(p)
        return p.returncode, stdout, stderr

    def _try_pipe(self, envelope):
        try:
            status, stdout, stderr = self._exec_process(envelope)
        except Timeout:
            msg = 'Delivery timed out'
            reply = Reply('450', msg)
            raise TransientRelayError(msg, reply)
        if status != 0:
            self.raise_error(status, stdout, stderr)

    def raise_error(self, status, stdout, stderr):
        """This method may be over-ridden by sub-classes if you need to control
        how the relay error is generated. By default, the error raised is a
        :class:`~slimta.relay.TransientRelayError` unless the process output
        begins with a ``5.X.X`` enhanced status code. This behavior attempts to
        mimic the postfix pipe_ daemon.

        This method is only called if the subprocess returns a non-zero exit
        status.

        :param status: The non-zero exit status of the subprocess.
        :param stdout: The subprocess's standard output, as received by
                       :py:meth:`~subprocess.Popen.communicate`.
        :type stdout: string
        :param stderr: The subprocess's standard error output, as received by
                       :py:meth:`~subprocess.Popen.communicate`.
        :type stderr: string
        :raises: :class:`~slimta.relay.TransientRelayError`,
                 :class:`~slimta.relay.PermanentRelayError`

        """
        error_msg = stdout.rstrip() or stderr.rstrip() or 'Delivery failed'
        if self.permanent_error_pattern.match(error_msg):
            reply = Reply('550', error_msg)
            raise PermanentRelayError(error_msg, reply)
        else:
            reply = Reply('450', error_msg)
            raise TransientRelayError(error_msg, reply)

    def attempt(self, envelope, attempts):
        self._try_pipe(envelope)


class MaildropRelay(PipeRelay):
    """Variation of :class:`PipeRelay` that is specifically tailored for
    calling `courier-maildrop`_ for local mail delivery.

    :param path: The path to the ``maildrop`` command on the system. By
                 default, ``$PATH`` is searched.
    :param timeout: The length of time ``maildrop`` is allowed to run before it
                    fails transiently, default unlimited.
    :param extra_args: List of extra arguments, if any, to pass to
                       ``maildrop``. By default, only the sender is passed in
                       with ``-f``.

    """

    EX_TEMPFAIL = 75

    def __init__(self, path=None, timeout=None, extra_args=None):
        args = [path or 'maildrop', '-f', '{sender}']
        if extra_args:
            args += extra_args
        super(MaildropRelay, self).__init__(args, timeout)

    def raise_error(self, status, stdout, stderr):
        error_msg = 'Delivery failed'
        if stdout.startswith('maildrop: '):
            error_msg = stdout[10:].rstrip()
        elif stderr.startswith('maildrop: '):
            error_msg = stderr[10:].rstrip()
        if status == self.EX_TEMPFAIL:
            reply = Reply('450', error_msg)
            raise TransientRelayError(error_msg, reply)
        else:
            reply = Reply('550', error_msg)
            raise PermanentRelayError(error_msg, reply)


class DovecotLdaRelay(PipeRelay):
    """Variation of :class:`PipeRelay` that is specifically tailored for
    calling dovecot's LDA_ for local mail delivery.

    :param path: The path to the ``dovecot-lda`` command on the system. By
                 default, ``$PATH`` is searched.
    :param timeout: The length of time ``dovecot-lda`` is allowed to run before
                    it fails transiently, default unlimited.
    :param extra_args: List of extra arguments, if any, to pass to
                       ``dovecot-lda``.  By default, only the sender and
                       recipient are passed in with ``-f`` and ``-d``,
                       respectively.

    """

    EX_TEMPFAIL = 75

    def __init__(self, path=None, timeout=None, extra_args=None):
        args = [path or 'dovecot-lda',
                '-f', '{sender}',
                '-d', '{recipient}']
        if extra_args:
            args += extra_args
        super(DovecotLdaRelay, self).__init__(args, timeout)

    def raise_error(self, status, stdout, stderr):
        error_msg = stdout.rstrip() or stderr.rstrip() or 'LDA delivery failed'
        if status == self.EX_TEMPFAIL:
            reply = Reply('450', error_msg)
            raise TransientRelayError(error_msg, reply)
        else:
            reply = Reply('550', error_msg)
            raise PermanentRelayError(error_msg, reply)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
