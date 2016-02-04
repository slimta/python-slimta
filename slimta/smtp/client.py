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
from gevent.socket import wait_read

from pysasl import SASLAuth

from .io import IO
from .auth import AuthSession
from .extensions import Extensions
from .reply import Reply
from .datasender import DataSender

__all__ = ['Client', 'LmtpClient']


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
    :param address: Remote address associated with the socket, which will
                    default to a call to :py:func:`~socket.socket.getpeername`.

    """

    def __init__(self, socket, tls_wrapper=None, address=None):
        self.io = IO(socket, tls_wrapper, address)
        self.reply_queue = []

        #: |Reply| of the last error received from the server.
        self.last_error = None

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
            if reply.is_error():
                self.last_error = reply

    def _encode(self, thing):
        if 'SMTPUTF8' in self.extensions:
            return thing.encode('utf-8')
        else:
            return thing.encode('ascii')

    def has_reply_waiting(self):
        """Checks if the underlying socket has data waiting to be received,
        which means a reply is waiting to be read.

        :rtype: True or False

        """
        sock_fd = self.io.socket.fileno()
        if sock_fd < 0:
            return False
        try:
            wait_read(sock_fd, 0.01, Timeout())
        except Timeout:
            return False
        else:
            return True

    def get_reply(self, command=b'[TIMEOUT]'):
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
        banner = Reply(command=b'[BANNER]')
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
            command = b' '.join((command, arg))
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
        ehlo = Reply(command=b'EHLO')
        ehlo.enhanced_status_code = False
        self.reply_queue.append(ehlo)

        if not isinstance(ehlo_as, bytes):
            ehlo_as = ehlo_as.encode('ascii')
        command = b'EHLO '+ehlo_as
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
        helo = Reply(command=b'HELO')
        helo.enhanced_status_code = False
        self.reply_queue.append(helo)

        if not isinstance(helo_as, bytes):
            helo_as = helo_as.encode('ascii')
        command = b'HELO '+helo_as
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
        reply = self.custom_command(b'STARTTLS')
        if reply.code == '220':
            self.encrypt(tls)
        return reply

    def auth(self, authcid, secret, authzid=None, mechanism=b'PLAIN'):
        """Negotiates authentication for the current SMTP session. This
        transaction may involve several back-and-forth packets to the server,
        depending on the SASL mechanism used, and this function will only
        return once all have completed.

        :param authcid: The authentication identity, usually the username.
        :param secret: The secret (i.e. password) string to send for the given
                       authentication and authorization identities.
        :param authzid: The authorization identity, if applicable.
        :param mechanism: SASL mechanism name to use for authentication.
        :type mechanism: str
        :returns: |Reply| object populated with the response.

        """
        self._flush_pipeline()
        auth = AuthSession(SASLAuth(), self.io)
        return auth.client_attempt(authcid, secret, authzid, mechanism)

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
        mailfrom = Reply(command=b'MAIL')
        self.reply_queue.append(mailfrom)

        command = b''.join((b'MAIL FROM:<', self._encode(address), b'>'))
        if data_size is not None and 'SIZE' in self.extensions:
            command += b' SIZE='+str(data_size).encode()
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
        rcptto = Reply(command=b'RCPT')
        self.reply_queue.append(rcptto)

        command = b''.join((b'RCPT TO:<', self._encode(address), b'>'))
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
        return self.custom_command(b'DATA')

    def send_data(self, *data):
        """Processes and sends message data. At the end of the message data,
        the client will send a line with a single ``.`` to indicate the end of
        the message.  If the server does *not* support PIPELINING, the returned
        reply object is populated immediately.

        :param data: The message data parts.
        :type data: :py:obj:`bytes`
        :returns: |Reply| object that will be populated with the response
                  once a non-pipelined command is called, or if the server does
                  not support PIPELINING.

        """
        send_data = Reply(command=b'[SEND_DATA]')
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

        :returns: |Reply| object that will be populated with the response
                  once a non-pipelined command is called, or if the server does
                  not support PIPELINING.

        """
        send_data = Reply(command=b'[SEND_DATA]')
        self.reply_queue.append(send_data)

        self.io.send_command(b'.')

        if 'PIPELINING' not in self.extensions:
            self._flush_pipeline()

        return send_data

    def rset(self):
        """Sends a RSET command and waits for the response. The intent of the
        RSET command is to reset any :meth:`mail` or :meth:`rcpt` commands that
        are pending.

        :returns: |Reply| object populated with the response.

        """
        return self.custom_command(b'RSET')

    def quit(self):
        """Sends the QUIT command and waits for the response. After the
        response is received (should be 221) the socket should be closed.

        :returns: |Reply| object populated with the response.

        """
        return self.custom_command(b'QUIT')


class LmtpClient(Client):
    """This sub-class has been modified to implement the LMTP protocol instead.
    The first primary difference is the :meth:`.ehlo` and :meth:`.helo` are no
    longer allowed and have been replaced with :meth:`.lhlo`. The second
    primary difference is that the :meth:`.send_data` and
    :meth:`.send_empty_data` methods now return a list of tuples containing the
    address from a successful :meth:`.rcptto` and a |Reply| object. This list
    is in the same order as the calls to :meth:`.rcptto`.

    """

    def __init__(self, socket, tls_wrapper=None, address=None):
        super(LmtpClient, self).__init__(socket, tls_wrapper, address)
        self.rcpttos = []

    def ehlo(self, ehlo_as):
        raise NotImplementedError()

    def helo(self, helo_as):
        raise NotImplementedError()

    def lhlo(self, lhlo_as):
        """Sends the LHLO command with identifier string and waits for the
        reply. When this method returns, the ``self.extensions`` object will
        also be populated with the SMTP extensions the server supports.

        :param lhlo_as: LHLO identifier string, usually an FQDN.
        :returns: |Reply| object populated with the response.

        """
        lhlo = Reply(command=b'LHLO')
        lhlo.enhanced_status_code = False
        self.reply_queue.append(lhlo)

        if not isinstance(lhlo_as, bytes):
            lhlo_as = lhlo_as.encode('ascii')
        command = b'LHLO '+lhlo_as
        self.io.send_command(command)

        self._flush_pipeline()
        if lhlo.code == '250':
            self.rcpttos = []
            self.extensions.reset()
            lhlo.message = self.extensions.parse_string(lhlo.message)

        return lhlo

    def rcptto(self, address):
        reply = super(LmtpClient, self).rcptto(address)
        self.rcpttos.append((address, reply))
        return reply

    def send_data(self, *data):
        ret = []
        for address, rcptto_reply in self.rcpttos:
            if rcptto_reply.code.startswith('2'):
                data_reply = Reply(command=b'[SEND_DATA]')
                self.reply_queue.append(data_reply)
                ret.append((address, data_reply))
        self.rcpttos = []

        data_sender = DataSender(*data)
        data_sender.send(self.io)

        if 'PIPELINING' not in self.extensions:
            self._flush_pipeline()

        return ret

    def send_empty_data(self):
        ret = []
        for address, rcptto_reply in self.rcpttos:
            if rcptto_reply.code.startswith('2'):
                data_reply = Reply(command=b'[SEND_DATA]')
                self.reply_queue.append(data_reply)
                ret.append((address, data_reply))
        self.rcpttos = []

        self.io.send_command(b'.')

        if 'PIPELINING' not in self.extensions:
            self._flush_pipeline()

        return ret

    def rset(self):
        reply = super(LmtpClient, self).rset()
        self.rcpttos = []
        return reply


# vim:et:fdm=marker:sts=4:sw=4:ts=4
