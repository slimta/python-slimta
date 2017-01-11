import unittest
import errno
import logging
import socket

from testfixtures import log_capture

import slimta.logging.socket
from slimta.logging import getSocketLogger


class FakeSocket(object):

    def __init__(self, fd, peer=None):
        self.fd = fd
        self.peer = peer

    def fileno(self):
        return self.fd

    def getpeername(self):
        return self.peer


class FakeContext(object):

    def session_stats(self):
        return {'hits': 13}


class TestSocketLogger(unittest.TestCase):

    def setUp(self):
        self.log = getSocketLogger('test')

    @log_capture()
    def test_send(self, l):
        sock = FakeSocket(136)
        self.log.send(sock, 'test send')
        l.check(('test', 'DEBUG', 'fd:136:send data=\'test send\''))

    @log_capture()
    def test_recv(self, l):
        sock = FakeSocket(29193)
        self.log.recv(sock, 'test recv')
        l.check(('test', 'DEBUG', 'fd:29193:recv data=\'test recv\''))

    @log_capture()
    def test_accept(self, l):
        server = FakeSocket(926)
        client = FakeSocket(927, 'testpeer')
        self.log.accept(server, client)
        self.log.accept(server, client, 'testpeer2')
        l.check(('test', 'DEBUG', 'fd:926:accept clientfd=927 peer=\'testpeer\''),
                ('test', 'DEBUG', 'fd:926:accept clientfd=927 peer=\'testpeer2\''))

    @log_capture()
    def test_connect(self, l):
        sock = FakeSocket(539, 'testpeer')
        self.log.connect(sock)
        self.log.connect(sock, 'testpeer2')
        l.check(('test', 'DEBUG', 'fd:539:connect peer=\'testpeer\''),
                ('test', 'DEBUG', 'fd:539:connect peer=\'testpeer2\''))

    @log_capture()
    def test_encrypt(self, l):
        sock = FakeSocket(445)
        context = FakeContext()
        self.log.encrypt(sock, context)
        l.check(('test', 'DEBUG', 'fd:445:encrypt hits=13'))

    @log_capture()
    def test_shutdown(self, l):
        sock = FakeSocket(823)
        self.log.shutdown(sock, socket.SHUT_RD)
        self.log.shutdown(sock, socket.SHUT_WR)
        self.log.shutdown(sock, socket.SHUT_RDWR)
        l.check(('test', 'DEBUG', 'fd:823:shutdown how=\'read\''),
                ('test', 'DEBUG', 'fd:823:shutdown how=\'write\''),
                ('test', 'DEBUG', 'fd:823:shutdown how=\'both\''))

    @log_capture()
    def test_close(self, l):
        sock = FakeSocket(771)
        self.log.close(sock)
        l.check(('test', 'DEBUG', 'fd:771:close'))

    @log_capture()
    def test_error(self, l):
        sock = FakeSocket(680)
        exc = OSError(errno.EPIPE, 'Broken pipe')
        self.log.error(sock, exc, 'testaddress')
        slimta.logging.socket.socket_error_log_level = logging.WARNING
        self.log.error(sock, exc)
        l.check(('test', 'ERROR', 'fd:680:error address=\'testaddress\' args=(32, \'Broken pipe\') message=\'[Errno 32] Broken pipe\''),
        		('test', 'WARNING', 'fd:680:error args=(32, \'Broken pipe\') message=\'[Errno 32] Broken pipe\''))


# vim:et:fdm=marker:sts=4:sw=4:ts=4
