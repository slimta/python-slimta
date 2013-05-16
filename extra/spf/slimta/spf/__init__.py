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

"""This module provides classes to check the `SPF`_ records of the sending
client address.

.. _SPF: http://en.wikipedia.org/wiki/Sender_Policy_Framework

"""

from __future__ import absolute_import

from functools import wraps

import gevent
import spf

from slimta.smtp.reply import Reply

__all__ = ['EnforceSpf']


class EnforceSpf(object):
    """Class used to check SPF records and enforce a policy against the results.
    By default, results are logged but not acted upon.

    :param timeout: Timeout in seconds before giving up the check. An SPF check
                    that times out is equivalent to a ``'temperror'`` result.

    """

    def __init__(self, timeout=10.0):
        self.policies = {}
        self.timeout = timeout

    def set_enforcement(self, result, match_code='550',
                                      match_message='5.7.1 Access denied'):
        """Adds an enforcement policy to a particular SPF result. If the given
        result is seen, the ``MAIL FROM`` reply is set accordingly.

        :param result: The result code, one of ``'pass'``, ``'permerror'``,
                      ``'fail'``, ``'temperror'``, ``'softfail'``, ``'none'``,
                      ``'neutral'``.
        :param match_code: When the result code matches, set the |Reply| code to
                           this string.
        :param match_message: When the result code matches, set the |Reply|
                              message to this string. You can use the
                              ``{reason}`` template in your string.

        """
        if result.lower() not in ['pass', 'permerror', 'fail', 'temperror',
                                  'softfail', 'none', 'neutral']:
            raise ValueError(result)
        self.policies[result.lower()] = (match_code, match_message)

    def query(self, sender, ip, ehlo_as):
        """Performs a direct query to check the sender's domain to see if the
        given IP and EHLO string are authorized to send for that domain.

        :param sender: The sender address.
        :param ip: The IP address string of the sending client.
        :param ehlo_as: The EHLO string given by the sending client.
        :returns: A tuple of the result and reason strings.

        """
        result, reason = 'temperror', 'Timed out'
        with gevent.Timeout(self.timeout, False):
            result, reason = spf.check2(i=ip, s=sender, h=ehlo_as)
        return result, reason

    def check(self, f):
        """Decorates :class:`~slimta.edge.smtp.SmtpValidators` methods that are
        given a |Reply| object. It will check the current SMTP session's
        connecting IP address and EHLO string against the given sender address.
        If enforcement policies are set for the result, the |Reply| is modified
        before calling the validator method.

        This decorator can only be used on ``handle_mail()``, ``handle_rcpt()``,
        and ``handle_data()``.

        :param f: The overloaded :class:`~slimta.edge.smtp.SmtpValidators`
                  method to decorate.

        """
        @wraps(f)
        def new_f(f_self, reply, *args, **kwargs):
            ip = f_self.session.address[0]
            ehlo_as = f_self.session.ehlo_as
            if f_self.session.envelope:
                sender = f_self.session.envelope.sender
            else:
                sender = args[0]
            result, reason = self.query(sender, ip, ehlo_as)
            if result in self.policies:
                reply.code = self.policies[result][0]
                reply.message = self.policies[result][1].format(reason=reason)
            return f(f_self, reply, *args, **kwargs)
        return new_f


# vim:et:fdm=marker:sts=4:sw=4:ts=4
