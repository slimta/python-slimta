#!/usr/bin/env python

import sys
import logging
import os.path

from gevent import ssl

# The following lines replace many standard library modules with versions that
# use gevent for concurrency. This is NOT required by slimta, but may help
# you avoid mistakes that can have harsh performance implications!
from gevent import monkey
monkey.patch_all()


logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)


def _start_inbound_relay(args):
    from slimta.relay.pipe import PipeRelay

    relay = PipeRelay(['tee', '{message_id}.eml'])
    return relay


def _start_inbound_queue(args, relay):
    from slimta.queue.dict import DictStorage
    from slimta.queue import Queue
    from slimta.policy.headers import AddDateHeader, \
        AddMessageIdHeader, AddReceivedHeader
    from slimta.policy.spamassassin import SpamAssassin

    envelope_db = {}
    meta_db = {}

    storage = DictStorage(envelope_db, meta_db)
    queue = Queue(storage, relay)
    queue.start()

    queue.add_policy(AddDateHeader())
    queue.add_policy(AddMessageIdHeader())
    queue.add_policy(AddReceivedHeader())
    if args.spamassassin:
        queue.add_policy(SpamAssassin())

    return queue


def _start_inbound_edge(args, queue):
    from slimta.edge.smtp import SmtpEdge, SmtpValidators
    from slimta.util.dnsbl import check_dnsbl
    from site_data import inbound_banner, deliverable_addresses

    class EdgeValidators(SmtpValidators):

        @check_dnsbl('zen.spamhaus.org', match_code='520')
        def handle_banner(self, reply, address):
            reply.message = inbound_banner

        def handle_rcpt(self, reply, recipient, params):
            if recipient not in deliverable_addresses:
                reply.code = '550'
                reply.message = \
                    '5.7.1 Recipient <{0}> Not allowed'.format(recipient)

    context = _get_ssl_context_server(args)

    edge = SmtpEdge(('', args.inbound_port), queue, max_size=10240,
                    validator_class=EdgeValidators, context=context,
                    command_timeout=20.0,
                    data_timeout=30.0)
    edge.start()

    ssl_edge = SmtpEdge(('', args.inbound_ssl_port), queue,
                        validator_class=EdgeValidators,
                        auth=[b'PLAIN', b'LOGIN'],
                        context=context, tls_immediately=True,
                        command_timeout=20.0, data_timeout=30.0)
    ssl_edge.start()

    return edge, ssl_edge


def _start_outbound_relay(args):
    from slimta.relay.smtp.mx import MxSmtpRelay

    context = _get_ssl_context_client(args)

    relay = MxSmtpRelay(connect_timeout=20.0, command_timeout=10.0,
                        data_timeout=20.0, idle_timeout=10.0,
                        context=context)
    return relay


def _start_outbound_queue(args, relay, inbound_queue):
    from slimta.queue.dict import DictStorage
    from slimta.queue import Queue
    from slimta.policy.headers import AddDateHeader, \
        AddMessageIdHeader, AddReceivedHeader
    from slimta.policy.split import RecipientDomainSplit

    envelope_db = {}
    meta_db = {}

    storage = DictStorage(envelope_db, meta_db)
    queue = Queue(storage, relay, bounce_queue=inbound_queue)
    queue.start()

    queue.add_policy(AddDateHeader())
    queue.add_policy(AddMessageIdHeader())
    queue.add_policy(AddReceivedHeader())
    queue.add_policy(RecipientDomainSplit())

    return queue


def _start_outbound_edge(args, queue):
    from slimta.edge.smtp import SmtpEdge, SmtpValidators
    from slimta.util.dnsbl import check_dnsbl
    from site_data import credentials, outbound_banner

    class EdgeValidators(SmtpValidators):

        @check_dnsbl('zen.spamhaus.org')
        def handle_banner(self, reply, address):
            reply.message = outbound_banner

        def handle_auth(self, reply, creds):
            try:
                password = credentials[creds.authcid]
                assert creds.check_secret(password)
            except (KeyError, AssertionError):
                reply.code = '535'
                reply.message = '5.7.8 Authentication credentials invalid'

        def handle_mail(self, reply, sender, params):
            if not self.session.auth:
                reply.code = '550'
                reply.message = '5.7.1 Sender <{0}> Not allowed'.format(sender)

    context = _get_ssl_context_server(args)

    edge = SmtpEdge(('', args.outbound_port), queue, context=context,
                    validator_class=EdgeValidators,
                    auth=[b'PLAIN', b'LOGIN'],
                    command_timeout=20.0, data_timeout=30.0)
    edge.start()

    return edge


def _get_ssl_context_server(args):
    ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ctx.load_cert_chain(keyfile=os.path.realpath(args.keyfile),
                        certfile=os.path.realpath(args.certfile))
    return ctx


def _get_ssl_context_client(args):
    ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    ctx.load_cert_chain(keyfile=os.path.realpath(args.keyfile),
                        certfile=os.path.realpath(args.certfile))
    return ctx


def _daemonize(args):
    from slimta.util import system
    from gevent import sleep

    if args.daemon:
        system.redirect_stdio(args.logfile, args.errorfile)
        system.daemonize()
    sleep(0.1)
    if args.user:
        system.drop_privileges(args.user, args.group)


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

    group = parser.add_argument_group('Port Configuration')
    group.add_argument('--inbound-port', dest='inbound_port', type=int,
                       metavar='PORT', default=1025,
                       help='Listening port number for inbound mail')
    group.add_argument('--inbound-ssl-port', dest='inbound_ssl_port',
                       type=int, metavar='PORT', default=1465,
                       help='Listening SSL-only port number for inbound mail')
    group.add_argument('--outbound-port', dest='outbound_port', type=int,
                       metavar='PORT', default=1587,
                       help='Listening port number for outbound mail')

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

    in_relay = _start_inbound_relay(args)
    in_queue = _start_inbound_queue(args, in_relay)
    _start_inbound_edge(args, in_queue)

    out_relay = _start_outbound_relay(args)
    out_queue = _start_outbound_queue(args, out_relay, in_queue)
    _start_outbound_edge(args, out_queue)

    _daemonize(args)

    try:
        Event().wait()
    except KeyboardInterrupt:
        print


if __name__ == '__main__':
    main()


# vim:et:fdm=marker:sts=4:sw=4:ts=4
