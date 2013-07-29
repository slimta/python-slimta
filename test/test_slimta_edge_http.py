
import unittest
import urllib2

from mox import MoxTestBase, IsA
import gevent

from slimta.edge.http import HttpEdge
from slimta.envelope import Envelope
from slimta.queue import QueueError
from slimta.smtp.reply import Reply


class TestEdgeHttp(MoxTestBase):
    pass


# vim:et:fdm=marker:sts=4:sw=4:ts=4
