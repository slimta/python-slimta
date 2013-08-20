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
queuing or before relaying the message with the
:meth:`slimta.queue.Queue.add_policy()` and
:meth:`slimta.relay.Relay.add_policy()`, respectively.

If a policy is applied before queuing, it is executed only once and any changes
it makes to the |Envelope| will be stored persistently. This is especially
useful for tasks such as header and content modification, since these may be
more expensive operations and should only run once.

If a policy is applied before relaying, it is executed before each delivery
attempt and no resulting changes will be persisted to storage. This is useful
for policies that have to do with delivery, such as forwarding.

"""

from __future__ import absolute_import

from slimta.core import SlimtaError

__all__ = ['PolicyError', 'QueuePolicy', 'RelayPolicy']


class PolicyError(SlimtaError):
    """Base exception for all custom ``slimta.policy`` errors."""
    pass


class QueuePolicy(object):
    """Base class for queue policies. These are run before a message is
    persistently queued and may overwrite the original |Envelope| with one or
    many new |Envelope| objects.

    """

    def apply(self, envelope):
        """:class:`QueuePolicy` sub-classes must override this method, which
        will be called by the |Queue| before storage.

        :param envelope: The |Envelope| object the policy execution should
                         apply any changes to. This envelope object *may* be
                         modified, though if new envelopes are returned this
                         object is discarded.
        :returns: Optionally return or generate an iterable of |Envelope|
                  objects to replace the given ``envelope`` going forward.
                  Returning ``None`` or an empty list will keep using
                  ``envelope``.

        """
        raise NotImplementedError()


class RelayPolicy(object):
    """Base class for relay policies. These are run immediately before a relay
    attempt is made.

    """

    def apply(self, envelope):
        """:class:`RelayPolicy` sub-classes must override this method, which
        will be called by the |Relay| before delivery.

        :param envelope: The |Envelope| object the policy execution should
                         apply any changes to.

        """
        raise NotImplementedError()


# vim:et:fdm=marker:sts=4:sw=4:ts=4
