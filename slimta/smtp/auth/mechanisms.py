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

"""Module containing the built-in supported authentication mechanisms.

.. _RFC 4616: http://tools.ietf.org/html/rfc4616
.. _RFC 2195: http://tools.ietf.org/html/rfc2195

"""

from __future__ import absolute_import

import re
import time
import uuid
import hmac
import hashlib
import base64

from gevent.socket import gethostname

from slimta.smtp.reply import Reply
from slimta.smtp.auth import ServerAuthError, CredentialsInvalidError, \
                             AuthenticationCanceled

__all__ = ['Mechanism', 'Plain', 'Login', 'CramMd5']


class Mechanism(object):
    """Base class of SASL authentication mechanism implementations.

    :param verify_secret: Function used by an SMTP server to verify credentials
                          given by the client.
    :param get_secret: Function used by an SMTP server to retrieve the secret
                       (password) string for comparison with credentials given
                       by the client.

    """

    #: This static flag should be overidden by sub-classes to specify whether
    #: the implementation is safe to use over unencrypted channels. By default,
    #: unsafe mechanisms will not be advertised until TLS is negotiated.
    secure = False

    #: This static string should be overriden by sub-classes to specify the SASL
    #: name that identifies this mechanism. This string will be used in the SMTP
    #: session. Custom mechanisms should be prefixed with ``X``.
    name = None

    def __init__(self, verify_secret, get_secret):
        self.verify_secret = verify_secret
        self.get_secret = get_secret

    def send_challenge_get_response(self, io, challenge_str):
        """This method can be used in :meth:`server_attempt` implementations to
        send intermediate SASL challenge strings to the client. The challenge
        string will be automatically prefixed with the ``334`` code to
        indicate it expects a response from the client. The cancellation
        response ``*`` is also handled by this method, which raises an internal
        exception to break out of the :meth:`server_attempt` method.

        :param io: The underlying IO object.
        :type io: :class:`~slimta.smtp.io.IO`
        :param challenge_str: The challenge string to send to the client.
        :returns: The string sent back by the client in response to the
                  challenge.

        """
        Reply('334', challenge_str).send(io, flush=True)
        ret = io.recv_line()
        if ret == '*':
            raise AuthenticationCanceled()
        return ret

    @classmethod
    def send_response_get_challenge(cls, io, response_str='', first=False):
        """This method can be used in :meth:`client_attempt` implementations to
        send response strings to the server and wait for its challenge. It is
        up to the implementation to check if this challenge is ``334`` (and
        thus requires another response) or if it is the final reply.

        :param io: The underlying IO object.
        :type io: :class:`~slimta.smtp.io.IO`
        :param response_str: The response string to send to the server.
        :param first: Every SASL implementation must first send a response with
                      this argument as ``True`` to initiate the authentication
                      request. Subsequent calls should use ``False``.
        :type first: bool
        :returns: The challenge or final |Reply| sent back by the server after
                  the response.

        """
        if first:
            if response_str:
                command = 'AUTH {0} {1}'.format(cls.name, response_str)
            else:
                command = 'AUTH {0}'.format(cls.name)
        else:
            command = response_str
        io.send_command(command)
        io.flush_send()
        ret = Reply(command='AUTH')
        ret.recv(io)
        return ret

    def server_attempt(self, io, initial_response):
        """Communicates back-and-forth with the connected client to negotiate
        authentication, based on the client's auth string. This method must be
        overidden by sub-classes to be used by server-side SMTP sessions.

        :param io: The underlying IO object.
        :type io: :class:`~slimta.smtp.io.IO`
        :param initial_response: The initial string sent by the client along
                                 with its AUTH command.
        :returns: A representation of the identity that was successfully
                  authenticated. This may be ``authcid``, ``authzid``, a tuple
                  of both, or any alternative.
        :raises: :class:`CredentialsInvalidError`

        """
        raise NotImplementedError()

    @classmethod
    def client_attempt(cls, io, authcid, secret, authzid):
        """Communicates back-and-forth with a server to negotiate
        authentication, based on the desired credentials. This class method must
        be overidden by sub-classes to be used by client-side SMTP sessions.

        :param io: The underlying IO object.
        :type io: :class:`~slimta.smtp.io.IO`
        :param authcid: The authentication identity, usually the username.
        :param secret: The secret (i.e. password) string to send for the given
                       authentication and authorization identities.
        :param authzid: The authorization identity, if applicable.
        :returns: |Reply| object received by the final authentication
                  negotiation response from the server.

        """
        raise NotImplementedError()


class Plain(Mechanism):
    """``PLAIN`` authentication mechanism. This is the primary mechanism to use
    on encrypted channels.
    
    See `RFC 4616`_ for details.

    """

    #: This mechanism identifies itself as ``PLAIN``.
    name = 'PLAIN'

    #: This mechanism is **not** secure for use on unencrypted channels.
    secure = False

    pattern = re.compile(r'^([^\x00]*)\x00([^\x00]+)\x00([^\x00]*)$')

    def server_attempt(self, io, initial_response):
        if not initial_response:
            initial_response = self.send_challenge_get_response(io, '')

        decoded = base64.b64decode(initial_response)
        match = self.pattern.match(decoded)
        if not match:
            msg = 'Invalid PLAIN authentication string'
            reply = Reply('501', '5.5.2 '+msg)
            raise ServerAuthError(msg, reply)
        zid, cid, secret = match.groups()

        return self.verify_secret(cid, secret, zid)

    @classmethod
    def client_attempt(cls, io, authcid, secret, authzid):
        response = '{0}\x00{1}\x00{2}'.format(authzid or '', authcid, secret)
        b64_response = base64.b64encode(response)
        return cls.send_response_get_challenge(io, b64_response, True)

class Login(Mechanism):
    """``LOGIN`` authentication mechanism. Simply a back-and-forth request from
    the client for its username and password, base64-encoded.

    """

    #: This mechanism identifies itself as ``LOGIN``.
    name = 'LOGIN'

    #: This mechanism is **not** secure for use on unencrypted channels.
    secure = False

    def server_attempt(self, io, initial_response):
        if not initial_response:
            # base64.b64encode('Username:')
            ret = self.send_challenge_get_response(io, 'VXNlcm5hbWU6')
            username = base64.b64decode(ret)
        else:
            username = base64.b64decode(initial_response)
        # base64.b64encode('Password:')
        ret = self.send_challenge_get_response(io, 'UGFzc3dvcmQ6')
        password = base64.b64decode(ret)
        return self.verify_secret(username, password)

    @classmethod
    def client_attempt(cls, io, authcid, secret, authzid):
        initial_ret = cls.send_response_get_challenge(io, first=True)
        if initial_ret.code != '334':
            return initial_ret
        username_str = base64.b64encode(authcid)
        username_ret = cls.send_response_get_challenge(io, username_str)
        if username_ret.code != '334':
            return username_ret
        password_str = base64.b64encode(secret)
        return cls.send_response_get_challenge(io, password_str)


class CramMd5(Mechanism):
    """``CRAM-MD5`` authentication mechanism. With this mechanism, the server
    presents an arbitrary challenge string and the client must MD5 hash that
    string using their password as a key. This means the password is not ever
    communicated in a reversible form. However, it also means the server must
    have access to un-hashed passwords, which is not always possible or desired.

    See `RFC 2195`_ for details.

    """

    #: This mechanism identifies itself as ``CRAM-MD5``.
    name = 'CRAM-MD5'

    #: This mechanism is secure for use on unencrypted channels.
    secure = True

    #: This is the hostname used when generating the initial challenge.
    hostname = gethostname()

    pattern = re.compile(r'^(.*) ([^ ]+)$')

    def _build_initial_challenge(self):
        uid = uuid.uuid4().hex
        timestamp = time.time()
        return '<{0}.{1:.0f}@{2}>'.format(uid, timestamp, self.hostname)

    def server_attempt(self, io, initial_response):
        challenge = self._build_initial_challenge()
        encoded_challenge = base64.b64encode(challenge)
        response = self.send_challenge_get_response(io, encoded_challenge)

        decoded = base64.b64decode(response)
        match = self.pattern.match(decoded)
        if not match:
            msg = 'Invalid CRAM-MD5 response'
            reply = Reply('501', '5.5.2 '+msg)
            raise ServerAuthError(msg, reply)
        username, digest = match.groups()
        secret, identity = self.get_secret(username)

        expected = hmac.new(secret, challenge, hashlib.md5).hexdigest()
        if expected != digest:
            raise CredentialsInvalidError()

        return identity

    @classmethod
    def client_attempt(cls, io, authcid, secret, authzid):
        initial_ret = cls.send_response_get_challenge(io, first=True)
        if initial_ret.code != '334':
            return initial_ret
        challenge = base64.b64decode(initial_ret.message)

        digest = hmac.new(secret, challenge, hashlib.md5).hexdigest()
        response_str = base64.b64encode('{0} {1}'.format(authcid, digest))
        return cls.send_response_get_challenge(io, response_str)


supported = [CramMd5, Plain, Login]


# vim:et:fdm=marker:sts=4:sw=4:ts=4
