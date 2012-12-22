
from gevent import monkey; monkey.patch_thread()

import shelve
import logging

from slimta.edge.smtp import SmtpEdge
from slimta.queue import Queue
from slimta.queue.dict import DictStorage
from slimta.relay.maildrop import MaildropRelay
from slimta.policy.headers import *
from slimta.bounce import Bounce

logging.basicConfig(level=logging.DEBUG)

relay = MaildropRelay()

env_db = shelve.open('envelope.db')
meta_db = shelve.open('meta.db')
queue_storage = DictStorage(env_db, meta_db)
queue = Queue(queue_storage, relay)

queue.add_prequeue_policy(AddDateHeader())
queue.add_prequeue_policy(AddMessageIdHeader())
queue.add_prequeue_policy(AddReceivedHeader())

edge = SmtpEdge(('127.0.0.1', 1337), queue)
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
