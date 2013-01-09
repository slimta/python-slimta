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

import re
import time
import uuid
import hmac
import hashlib
import base64

from gevent.socket import getfqdn

from slimta.smtp.reply import Reply
from slimta.smtp.auth import ServerAuthError, CredentialsInvalidError, \
                             AuthenticationCanceled

__all__ = ['Plain', 'Login', 'CramMd5']


class Mechanism(object):

    def __init__(self, verify_secret, get_secret):
        self.verify_secret = verify_secret
        self.get_secret = get_secret

    def _send_challenge_get_response(self, io, challenge_str):
        Reply('334', challenge_str).send(io, flush=True)
        ret = io.recv_line()
        if ret == '*':
            raise AuthenticationCanceled()
        return ret

    def server_attempt(self, io, initial_response):
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
            initial_response = self._send_challenge_get_response(io, '')

        decoded = base64.b64decode(initial_response)
        match = self.pattern.match(decoded)
        if not match:
            msg = 'Invalid PLAIN authentication string'
            reply = Reply('501', '5.5.2 '+msg)
            raise ServerAuthError(msg, reply)
        zid, cid, secret = match.groups()

        return self.verify_secret(cid, secret, zid)


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
            ret = self._send_challenge_get_response(io, 'VXNlcm5hbWU6')
            username = base64.b64decode(ret)
        else:
            username = base64.b64decode(initial_response)
        # base64.b64encode('Password:')
        ret = self._send_challenge_get_response(io, 'UGFzc3dvcmQ6')
        password = base64.b64decode(ret)
        return self.verify_secret(username, password)


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
    hostname = getfqdn()

    pattern = re.compile(r'^(.*) ([^ ]+)$')

    def _build_initial_challenge(self):
        uid = uuid.uuid4().hex
        timestamp = time.time()
        return '<{0}.{1:.0f}@{2}>'.format(uid, timestamp, self.hostname)

    def server_attempt(self, io, initial_response):
        challenge = self._build_initial_challenge()
        encoded_challenge = base64.b64encode(challenge)
        response = self._send_challenge_get_response(io, encoded_challenge)

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


supported = [Plain, Login, CramMd5]


# vim:et:fdm=marker:sts=4:sw=4:ts=4
