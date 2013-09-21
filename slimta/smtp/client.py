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

"""An SMTP client library that supports PIPELINING commands."""

from __future__ import absolute_import

from gevent import Timeout
from gevent.ssl import SSLSocket
from gevent.socket import wait_read

from .io import IO
from .extensions import Extensions
from .reply import Reply
from .datasender import DataSender
from .auth import ClientMechanism

__all__ = ['Client']


class Client(object):
    """Class whose methods perform various SMTP commands on a given socket. The
    return value from each command is a |Reply| object. Commands that are
    pipelined may not have their replies filled until subsequent commands are
    executed.

    The ``extensions`` attribute contains the |Extensions| object that are made
    available by the server.

    :param socket: Connected socket to use for the client.
    :param tls_wrapper: Optional function that takes a socket and the ``tls``
                        dictionary, creates a new encrypted socket, performs
                        the TLS handshake, and returns it. The default uses
                        :class:`~gevent.ssl.SSLSocket`.

    """

    def __init__(self, socket, tls_wrapper=None):
        self.io = IO(socket, tls_wrapper)
        self.reply_queue = []
        from .auth.standard import standard_mechanisms
        self.client_mechanisms = standard_mechanisms

        #: :class:`Extensions` object of the client, populated once the EHLO
        #: command returns its response.
        self.extensions = Extensions()

    def _flush_pipeline(self):
        self.io.flush_send()
        while True:
            try:
                reply = self.reply_queue.pop(0)
            except IndexError:
                return None
            reply.recv(self.io)

    def has_reply_waiting(self):
        """Checks if the underlying socket has data waiting to be received,
        which means a reply is waiting to be read.

        :rtype: True or False

        """
        sock_fd = self.io.socket.fileno()
        try:
            wait_read(sock_fd, 0.1, Timeout())
        except Timeout:
            return False
        else:
            return True

    def get_reply(self, command='[TIMEOUT]'):
        """Gets a reply from the server that was not triggered by the client
        sending a command. This is most useful for receiving timeout
        notifications.

        :param command: Optional command name to associate with the reply.
        :returns: |Reply| object populated with the response.

        """
        reply = Reply(command=command)
        self.reply_queue.append(reply)

        self._flush_pipeline()

        return reply

    def get_banner(self):
        """Waits for the SMTP banner at the beginning of the connection.

        :returns: |Reply| object populated with the response.

        """
        banner = Reply(command='[BANNER]')
        banner.enhanced_status_code = False
        self.reply_queue.append(banner)

        self._flush_pipeline()

        return banner

    def custom_command(self, command, arg=None):
        """Sends a custom command to the SMTP server and waits for the reply.

        :param command: The command to send.
        :param arg: Optonal argument string to send with the command.
        :returns: |Reply| object populated with the response.

        """
        custom = Reply(command=command.upper())
        self.reply_queue.append(custom)

        if arg:
            command = ' '.join((command, arg))
        self.io.send_command(command)

        self._flush_pipeline()

        return custom

    def ehlo(self, ehlo_as):
        """Sends the EHLO command with identifier string and waits for the
        reply. When this method returns, the ``self.extensions`` object will
        also be populated with the SMTP extensions the server supports.

        :param ehlo_as: EHLO identifier string, usually an FQDN.
        :returns: |Reply| object populated with the response.

        """
        ehlo = Reply(command='EHLO')
        ehlo.enhanced_status_code = False
        self.reply_queue.append(ehlo)

        command = 'EHLO '+ehlo_as
        self.io.send_command(command)

        self._flush_pipeline()
        if ehlo.code == '250':
            self.extensions.reset()
            ehlo.message = self.extensions.parse_string(ehlo.message)

        return ehlo

    def helo(self, helo_as):
        """Sends the HELO command with identifier string and waits for the
        reply.

        :param helo_as: HELO identifier string, usually an FQDN.
        :returns: |Reply| object populated with the response.

        """
        helo = Reply(command='HELO')
        helo.enhanced_status_code = False
        self.reply_queue.append(helo)

        command = 'HELO '+helo_as
        self.io.send_command(command)

        self._flush_pipeline()

        return helo

    def encrypt(self, tls):
        """Encrypts the underlying socket with the information given by
        ``tls``.  This call should only be used directly against servers that
        expect to be immediately encrypted. If encryption is negotiated with
        :meth:`starttls()` there is no need to call this method.

        :param tls: Dictionary of keyword arguments for
                    :class:`~gevent.ssl.SSLSocket`.

        """
        self.io.encrypt_socket(tls)

    def starttls(self, tls):
        """Sends the STARTTLS command with identifier string and waits for the
        reply. When the reply is received and the code is 220, the socket is
        encrypted with the parameters in ``tls``. This should be followed by a
        another call to :meth:`ehlo()`.

        :param tls: Dictionary of keyword arguments for
                    :class:`~gevent.ssl.SSLSocket`.
        :returns: |Reply| object populated with the response.

        """
        reply = self.custom_command('STARTTLS')
        if reply.code == '220':
            self.encrypt(tls)
        return reply

    def auth(self, authcid, secret, authzid=None, mechanism=None):
        """Negotiates authentication for the current SMTP session. This
        transaction may involve several back-and-forth packets to the server,
        depending on the SASL mechanism used, and this function will only
        return once all have completed.

        :param authcid: The authentication identity, usually the username.
        :param secret: The secret (i.e. password) string to send for the given
                       authentication and authorization identities.
        :param authzid: The authorization identity, if applicable.
        :param mechanism: Force the usage of the given SASL mechanism
                          sub-class.  If not given, the best mechanism
                          available is used.
        :type mechanism: :class:`~slimta.smtp.auth.ClientMechanism`
        :returns: |Reply| object populated with the response.

        """
        if not mechanism:
            server_supports = self.extensions.getparam('AUTH') or []
            for mech in self.client_mechanisms:
                mechanism = mech
                if mech.name in server_supports:
                    break
        elif not issubclass(mechanism, ClientMechanism):
            raise TypeError(mechanism)
        self._flush_pipeline()
        return mechanism.client_attempt(self.io, authcid, secret, authzid)

    def mailfrom(self, address, data_size=None):
        """Sends the MAIL command with the ``address`` and possibly the message
        size. The message size is sent if the server supports the SIZE
        extension. If the server does *not* support PIPELINING, the returned
        reply object is populated immediately.

        :param address: The sender address to send.
        :param data_size: Optional size of the message body.
        :returns: |Reply| object that will be populated with the response
                  once a non-pipelined command is called, or if the server does
                  not support PIPELINING.

        """
        mailfrom = Reply(command='MAIL')
        self.reply_queue.append(mailfrom)

        command = 'MAIL FROM:<{0}>'.format(address)
        if data_size is not None and 'SIZE' in self.extensions:
            command += ' SIZE='+str(data_size)
        self.io.send_command(command)

        if 'PIPELINING' not in self.extensions:
            self._flush_pipeline()

        return mailfrom

    def rcptto(self, address):
        """Sends the RCPT command with the ``address``. If the server
        does *not* support PIPELINING, the returned reply object is
        populated immediately.

        :param address: The sender address to send.
        :param data_size: Optional size of the message body.
        :returns: |Reply| object that will be populated with the response
                  once a non-pipelined command is called, or if the server does
                  not support PIPELINING.

        """
        rcptto = Reply(command='RCPT')
        self.reply_queue.append(rcptto)

        command = 'RCPT TO:<{0}>'.format(address)
        self.io.send_command(command)

        if 'PIPELINING' not in self.extensions:
            self._flush_pipeline()

        return rcptto

    def data(self):
        """Sends the DATA command and waits for the response. If the response
        from the server is a 354, the server is respecting message data and
        should be sent :meth:`send_data` or :meth:`send_empty_data`.

        :returns: |Reply| object populated with the response.

        """
        return self.custom_command('DATA')

    def send_data(self, *data):
        """Processes and sends message data. At the end of the message data,
        the client will send a line with a single ``.`` to indicate the end of
        the message.  If the server does *not* support PIPELINING, the returned
        reply object is populated immediately.

        :param data: The message data parts.
        :type data: :py:obj:`str` or :py:obj:`unicode`
        :returns: |Reply| object that will be populated with the response
                  once a non-pipelined command is called, or if the server does
                  not support PIPELINING.

        """
        send_data = Reply(command='[SEND_DATA]')
        self.reply_queue.append(send_data)

        data_sender = DataSender(*data)
        data_sender.send(self.io)

        if 'PIPELINING' not in self.extensions:
            self._flush_pipeline()

        return send_data

    def send_empty_data(self):
        """Sends a line with a single ``.`` to indicate an empty message. If
        the server does *not* support PIPELINING, the returned reply object is
        populated immediately.

        :param data: The message data.
        :type data: :py:obj:`str` or :py:obj:`unicode`
        :returns: |Reply| object that will be populated with the response
                  once a non-pipelined command is called, or if the server does
                  not support PIPELINING.

        """
        send_data = Reply(command='[SEND_DATA]')
        self.reply_queue.append(send_data)

        self.io.send_command('.')

        if 'PIPELINING' not in self.extensions:
            self._flush_pipeline()

        return send_data

    def rset(self):
        """Sends a RSET command and waits for the response. The intent of the
        RSET command is to reset any :meth:`mail` or :meth:`rcpt` commands that
        are pending.

        :returns: |Reply| object populated with the response.

        """
        return self.custom_command('RSET')

    def quit(self):
        """Sends the QUIT command and waits for the response. After the
        response is received (should be 221) the socket should be closed.

        :returns: |Reply| object populated with the response.

        """
        return self.custom_command('QUIT')


# vim:et:fdm=marker:sts=4:sw=4:ts=4
