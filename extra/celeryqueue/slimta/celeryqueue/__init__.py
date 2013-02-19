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

from celery import Task

from slimta.queue import QueueError
from slimta.bounce import Bounce

__all__ = ['CeleryQueue']


class CeleryQueue(object):

    def __init__(self, task_module):
        self.deliver_envelope = task_module.deliver_envelope
        self.attempt_delivery = task_module.attempt_delivery
        self.generate_bounce = task_module.generate_bounce

    def enqueue(self, envelope):
        attempt = self.attempt_delivery.s(envelope)
        result = self.deliver_envelope.apply_async((attempt, ),
                 link_error=self.generate_bounce.s(envelope))
        return [(env, result.id)]


class DeliverEnvelopeTask(Task):

    abstract = True


# vim:et:fdm=marker:sts=4:sw=4:ts=4
