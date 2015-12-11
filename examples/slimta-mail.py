#!/usr/bin/env python

from gevent import monkey; monkey.patch_all()

import sys
import logging
import os.path

logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)


# {{{ _start_inbound_relay()
def _start_inbound_relay(args):
    from slimta.relay.pipe import PipeRelay

    relay = PipeRelay(['tee', '{message_id}.eml'])
    return relay
# }}}

# {{{ _start_inbound_queue()
def _start_inbound_queue(args, relay):
    from slimta.queue.dict import DictStorage
    from slimta.queue import Queue
    from slimta.policy.headers import AddDateHeader, \
            AddMessageIdHeader, AddReceivedHeader
    from slimta.policy.spamassassin import SpamAssassin
    import shelve

    envelope_db = shelve.open(args.envelope_db)
    meta_db = shelve.open(args.meta_db)

    storage = DictStorage(envelope_db, meta_db)
    queue = Queue(storage, relay)
    queue.start()

    queue.add_policy(AddDateHeader())
    queue.add_policy(AddMessageIdHeader())
    queue.add_policy(AddReceivedHeader())
    if args.spamassassin:
        queue.add_policy(SpamAssassin())

    return queue
# }}}

# {{{ _start_inbound_edge()
def _start_inbound_edge(args, queue):
    from slimta.edge.smtp import SmtpEdge, SmtpValidators
    from slimta.util.dnsbl import check_dnsbl
    from site_data import inbound_banner, deliverable_addresses

    class EdgeValidators(SmtpValidators):

        @check_dnsbl('zen.spamhaus.org', match_code='520')
        def handle_banner(self, reply, address):
            reply.message = inbound_banner

        def handle_rcpt(self, reply, recipient):
            if recipient not in deliverable_addresses:
                reply.code = '550'
                reply.message = '5.7.1 Recipient <{0}> Not allowed'.format(recipient)
                return

    tls = _get_tls_args(args)

    edge = SmtpEdge(('', args.inbound_port), queue, max_size=10240,
                    validator_class=EdgeValidators, tls=tls,
                    command_timeout=20.0,
                    data_timeout=30.0)
    edge.start()

    return edge
# }}}

# {{{ _start_outbound_relay()
def _start_outbound_relay(args):
    from slimta.relay.smtp.mx import MxSmtpRelay

    tls = _get_tls_args(args)

    relay = MxSmtpRelay(tls=tls, connect_timeout=20.0, command_timeout=10.0,
                                 data_timeout=20.0, idle_timeout=10.0)
    return relay
# }}}

# {{{ _start_outbound_queue()
def _start_outbound_queue(args, relay):
    from slimta.queue.dict import DictStorage
    from slimta.queue import Queue
    from slimta.policy.headers import AddDateHeader, \
            AddMessageIdHeader, AddReceivedHeader
    from slimta.policy.split import RecipientDomainSplit
    import shelve

    envelope_db = shelve.open(args.envelope_db)
    meta_db = shelve.open(args.meta_db)

    storage = DictStorage(envelope_db, meta_db)
    queue = Queue(storage, relay)
    queue.start()

    queue.add_policy(AddDateHeader())
    queue.add_policy(AddMessageIdHeader())
    queue.add_policy(AddReceivedHeader())
    queue.add_policy(RecipientDomainSplit())

    return queue
# }}}

# {{{ _start_outbound_edge()
def _start_outbound_edge(args, queue):
    from slimta.edge.smtp import SmtpEdge, SmtpValidators
    from slimta.util.dnsbl import check_dnsbl
    from slimta.smtp.auth import Auth, CredentialsInvalidError
    from site_data import credentials, outbound_banner

    class EdgeAuth(Auth):

        def verify_secret(self, username, password, identity=None):
            try:
                assert credentials[username] == password
            except (KeyError, AssertionError):
                raise CredentialsInvalidError()
            return username

        def get_secret(self, username, identity=None):
            try:
                return credentials[username], username
            except KeyError:
                raise CredentialsInvalidError()

    class EdgeValidators(SmtpValidators):

        @check_dnsbl('zen.spamhaus.org')
        def handle_banner(self, reply, address):
            reply.message = outbound_banner

        def handle_mail(self, reply, sender):
            print(self.session.auth_result)
            if not self.session.auth_result:
                reply.code = '550'
                reply.message = '5.7.1 Sender <{0}> Not allowed'.format(sender)

    tls = _get_tls_args(args)

    edge = SmtpEdge(('', args.outbound_port), queue, tls=tls,
                    validator_class=EdgeValidators, auth_class=EdgeAuth,
                    command_timeout=20.0, data_timeout=30.0)
    edge.start()

    ssl_edge = SmtpEdge(('', args.outbound_ssl_port), queue,
                        validator_class=EdgeValidators, auth_class=EdgeAuth,
                        tls=tls, tls_immediately=True,
                        command_timeout=20.0, data_timeout=30.0)
    ssl_edge.start()

    return edge, ssl_edge
# }}}

# {{{ _get_tls_args()
def _get_tls_args(args):
    try:
        open(args.keyfile, 'r').close()
        open(args.certfile, 'r').close()
    except IOError:
        logging.warn('Could not find TLS key or cert file, disabling TLS.')
        return None

    return {'keyfile': os.path.realpath(args.keyfile),
            'certfile': os.path.realpath(args.certfile)}
# }}}

# {{{ _daemonize()
def _daemonize(args):
    from slimta import system
    from gevent import sleep

    if args.daemon:
        system.redirect_stdio(args.logfile, args.errorfile)
        system.daemonize()
    sleep(0.1)
    if args.user:
        system.drop_privileges(args.user, args.group)
# }}}

# {{{ main()
def main():
    from gevent.event import Event
    from argparse import ArgumentParser

    parser = ArgumentParser(description='Lightweight SMTP server.')
    parser.add_argument('-d', '--daemon', dest='daemon', action='store_true',
                        help='Daemonize the process.')
    parser.add_argument('--user', dest='user', type=str, metavar='USR',
                        default=None, help='Drop privileges down to USR')
    parser.add_argument('--group', dest='group', type=str, metavar='GRP',
                        default=None, help='Drop privileges down to GRP')

    group = parser.add_argument_group('Queue Configuration')
    group.add_argument('--envelope-db', dest='envelope_db', metavar='FILE',
                       type=str, default='envelope.db',
                       help='File path for envelope database')
    group.add_argument('--meta-db', dest='meta_db', type=str,
                       metavar='FILE', default='meta.db',
                       help='File path for meta database')

    group = parser.add_argument_group('Port Configuration')
    group.add_argument('--inbound-port', dest='inbound_port', type=int,
                       metavar='PORT', default=1025, help='Listening port number for inbound mail')
    group.add_argument('--outbound-port', dest='outbound_port', type=int,
                       metavar='PORT', default=1587, help='Listening port number for outbound mail')
    group.add_argument('--outbound-ssl-port', dest='outbound_ssl_port', type=int,
                       metavar='PORT', default=1465, help='Listening SSL-only port number for outbound mail')

    group = parser.add_argument_group('SSL/TLS Configuration')
    group.add_argument('--cert-file', dest='certfile', metavar='FILE',
                       type=str, default='cert.pem',
                       help='TLS certificate file')
    group.add_argument('--key-file', dest='keyfile', metavar='FILE',
                       type=str, default='cert.pem',
                       help='TLS key file')

    group = parser.add_argument_group('Output Configuration')
    group.add_argument('--log-file', dest='logfile', type=str, metavar='FILE',
                       default='output.log',
                       help='Write logs to FILE')
    group.add_argument('--error-file', dest='errorfile', type=str,
                       metavar='FILE', default='error.log',
                       help='Write errors to FILE')

    group = parser.add_argument_group('Other Configuration')
    group.add_argument('--spamassassin', action='store_true', default=False,
                       help='Scan messages with local SpamAssassin server')

    args = parser.parse_args()

    relay = _start_inbound_relay(args)
    queue = _start_inbound_queue(args, relay)
    _start_inbound_edge(args, queue)

    relay = _start_outbound_relay(args)
    queue = _start_outbound_queue(args, relay)
    _start_outbound_edge(args, queue)

    _daemonize(args)

    try:
        Event().wait()
    except KeyboardInterrupt:
        print
# }}}


if __name__ == '__main__':
    main()

# vim:et:fdm=marker:sts=4:sw=4:ts=4
