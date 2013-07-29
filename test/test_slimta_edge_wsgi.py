
import unittest
import urllib2

from mox import MoxTestBase, IsA
import gevent

from slimta.edge.wsgi import WsgiEdge
from slimta.envelope import Envelope
from slimta.queue import QueueError
from slimta.smtp.reply import Reply


class TestEdgeWsgi(MoxTestBase):
    pass


# vim:et:fdm=marker:sts=4:sw=4:ts=4
