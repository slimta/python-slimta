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

"""Relays an |Envelope| locally with ``courier-maildrop``."""

from gevent import Timeout
import gevent_subprocess

from slimta.smtp.reply import Reply
from slimta.relay import Relay, PermanentRelayError, TransientRelayError
from slimta import logging

__all__ = ['MaildropRelay']

log = logging.getSubprocessLogger(__name__)


class MaildropRelay(Relay):
    """When delivery attempts are made on this object, it will create a new sub-
    process and pipe envelope data to it. Delivery success or failure depends on
    the return code of the sub-process and error messages are pulled from
    standard error output.

    :param argv0: The command to use for ``maildrop``.
    :param timeout: The length of time a ``maildrop`` delivery is allowed to run
                    before it fails transiently, default unlimited.
    :param extra_args: List of extra arguments passed in to maildrop.

    """

    EX_TEMPFAIL = 75

    def __init__(self, argv0='maildrop', timeout=None, extra_args=None):
        super(MaildropRelay, self).__init__()
        self.argv0 = argv0
        self.timeout = timeout
        self.extra_args = extra_args

    def _exec_maildrop(self, envelope):
        header_data, message_data = envelope.flatten()
        stdin = ''.join((header_data, message_data))
        with Timeout(self.timeout):
            args = [self.argv0, '-f', envelope.sender]
            if self.extra_args:
                args += self.extra_args
            p = gevent_subprocess.Popen(args, stdin=gevent_subprocess.PIPE,
                                              stdout=gevent_subprocess.PIPE,
                                              stderr=gevent_subprocess.PIPE)
            log.popen(p, args)
            stdout, stderr = p.communicate(stdin)
        log.stdio(p, stdin, stdout, stderr)
        log.exit(p)
        if p.returncode == 0:
            return 0, None
        msg = stderr.rstrip()
        if msg.startswith('maildrop: '):
            msg = msg[10:]
        return p.returncode, msg

    def _try_maildrop(self, envelope):
        try:
            status, err = self._exec_maildrop(envelope)
        except Timeout:
            msg = 'Maildrop timed out'
            reply = Reply('450', msg)
            raise TransientRelayError(msg, reply)
        if status == 0:
            pass
        elif status == self.EX_TEMPFAIL:
            reply = Reply('450', err)
            raise TransientRelayError(err, reply)
        else:
            reply = Reply('550', err)
            raise PermanentRelayError(err, reply)

    def attempt(self, envelope, attempts):
        self._try_maildrop(envelope)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
