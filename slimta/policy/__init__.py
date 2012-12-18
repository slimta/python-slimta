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

"""Package containing useful policies, which can be configured to run before
or after queuing the message with the
:meth:`~slimta.queue.Queue.add_prequeue_policy()` and
:meth:`~slimta.queue.Queue.add_postqueue_policy()`, respectively.

If a policy is applied before queuing, it is executed only once and any changes
it makes to the |Envelope| will be stored persistently. This is especially
useful for tasks such as header and content modification, since these may be
more expensive operations and should only run once.

If a policy is applied after queuing, it is executed before each delivery
attempt and no resulting changes will be persisted to storage. This is useful
for policies that have to do with delivery, such as forwarding.

"""

from slimta import SlimtaError

__all__ = ['PolicyError', 'Policy']


class PolicyError(SlimtaError):
    """Base exception for all custom ``slimta.policy`` errors."""
    pass


class Policy(object):
    """Base class for all policies."""

    def apply(self, envelope):
        """:class:`Policy` sub-classes must override this method, which will
        be called by the |Queue| before or after storage.

        :param envelope: The |Envelope| object the policy execution should
                         apply any changes to.

        """
        raise NotImplemented()


# vim:et:fdm=marker:sts=4:sw=4:ts=4
