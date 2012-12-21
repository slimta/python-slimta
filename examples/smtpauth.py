
from gevent import monkey; monkey.patch_thread()

import shelve
import logging

from slimta.edge.smtp import SmtpEdge
from slimta.queue import Queue
from slimta.queue.dict import DictStorage
from slimta.relay import RelayError
from slimta.relay.smtp.mx import MxSmtpRelay
from slimta.policy.headers import *
from slimta.policy.forward import Forward
from slimta.bounce import Bounce
from slimta.smtp.auth import Auth, CredentialsInvalidError

logging.basicConfig(level=logging.DEBUG)

relay = MxSmtpRelay()

env_db = shelve.open('envelope.db')
meta_db = shelve.open('meta.db')
queue_storage = DictStorage(env_db, meta_db)
queue = Queue(queue_storage, relay)

queue.add_prequeue_policy(AddDateHeader())
queue.add_prequeue_policy(AddMessageIdHeader())
queue.add_prequeue_policy(AddReceivedHeader())

class TestAuth(Auth):
    def verify_secret(self, cid, secret, zid=None):
        if cid == 'testuser' and secret == 'testpass':
            return 'testuser'
        else:
            raise CredentialsInvalidError()
    def get_secret(self, cid, zid=None):
        if cid == 'testuser':
            return 'testpass', 'testuser'
        else:
            raise CredentialsInvalidError()

tls = {'keyfile': 'cert.pem', 'certfile': 'cert.pem'}
edge = SmtpEdge(('127.0.0.1', 1337), queue, auth=TestAuth, tls=tls)
edge.start()
queue.start()
try:
    edge.get()
except KeyboardInterrupt:
    print
finally:
    for key in env_db.keys():
        print 'env', key
    for key in meta_db.keys():
        print 'meta', key
    env_db.close()
    meta_db.close()

# vim:et:fdm=marker:sts=4:sw=4:ts=4
