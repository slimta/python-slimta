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

from __future__ import absolute_import

import re
import base64

from pysasl import  AuthenticationError, ServerChallenge, \
                   AuthenticationCredentials

from . import SmtpError
from .reply import Reply

__all__ = ['ServerAuthError', 'AuthSession']

noarg_pattern = re.compile(r'^([a-zA-Z0-9_-]+)$')
witharg_pattern = re.compile(r'^([a-zA-Z0-9_-]+)\s+(.+)$')


class ServerAuthError(SmtpError):

    def __init__(self, msg, reply):
        super(ServerAuthError, self).__init__(msg)
        self.reply = reply


class InvalidAuthString(ServerAuthError):

    def __init__(self):
        msg = 'Invalid authentication string'
        reply = Reply('501', '5.5.2 '+msg)
        super(InvalidAuthString, self).__init__(msg, reply)


class InvalidMechanismError(ServerAuthError):

    def __init__(self):
        msg = 'Invalid authentication mechanism'
        reply = Reply('504', '5.5.4 '+msg)
        super(InvalidMechanismError, self).__init__(msg, reply)


class AuthenticationCanceled(ServerAuthError):

    def __init__(self):
        msg = 'Authentication canceled by client'
        reply = Reply('501', '5.7.0 '+msg)
        super(AuthenticationCanceled, self).__init__(msg, reply)


class UnexpectedAuthError(ServerAuthError):

    def __init__(self, exc):
        reply = Reply('501', '5.5.2 '+str(exc))
        super(UnexpectedAuthError, self).__init__(str(exc), reply)


class AuthSession(object):

    def __init__(self, auth, io):
        super(AuthSession, self).__init__()
        self.auth = auth
        self.io = io

    def __str__(self):
        available = self.server_mechanisms
        if available:
            return ' '.join(sorted([mech.name for mech in available]))
        else:
            raise ValueError('No mechanisms available')

    def _parse_arg(self, arg):
        match = noarg_pattern.match(arg)
        if match:
            return match.group(1).upper(), None
        match = witharg_pattern.match(arg)
        if match:
            return match.group(1).upper(), match.group(2)
        raise InvalidMechanismError()

    @property
    def server_mechanisms(self):
        return [mech for mech in self.auth.server_mechanisms
                if self.io.encrypted or not getattr(mech, 'insecure', False)]

    @property
    def client_mechanisms(self):
        return [mech for mech in self.auth.client_mechanisms
                if self.io.encrypted or not getattr(mech, 'insecure', False)]

    def _server_challenge(self, challenge, response=None):
        if not response:
            challenge_raw = base64.b64encode(challenge)
            Reply('334', challenge_raw).send(self.io, flush=True)
            response = self.io.recv_line()
        if response == '*':
            raise AuthenticationCanceled()
        try:
            return base64.b64decode(response)
        except TypeError:
            raise InvalidAuthString()

    def server_attempt(self, arg):
        mechanism_name, mechanism_arg = self._parse_arg(arg)
        for mechanism in self.server_mechanisms:
            if mechanism.name == mechanism_name:
                responses = []
                while True:
                    try:
                        return mechanism.server_attempt(responses)
                    except AuthenticationError as exc:
                        raise UnexpectedAuthError(exc)
                    except ServerChallenge as chal:
                        resp = self._server_challenge(chal.challenge,
                                                      mechanism_arg)
                        mechanism_arg = None
                        chal.set_response(resp)
                        responses.append(chal)
        raise InvalidMechanismError()

    def _client_respond(self, mech, response, first=False):
        if first:
            command = 'AUTH {0}'.format(mech.name)
            if response:
                response_raw = base64.b64encode(response)
                command = ' '.join((command, response_raw))
        else:
            command = base64.b64encode(response)
        self.io.send_command(command)
        self.io.flush_send()
        ret = Reply(command='AUTH')
        ret.recv(self.io)
        if ret.code == '334':
            return base64.b64decode(ret.message), ret
        return None, ret

    def client_attempt(self, authcid, secret, authzid, mech_name):
        mechanism = self.auth.get(mech_name)
        if not mechanism:
            raise InvalidMechanismError()
        creds = AuthenticationCredentials(authcid, secret, authzid)
        resp = mechanism.client_attempt(creds, [])
        chal, reply = self._client_respond(
            mechanism, resp.get_response(), True)
        responses = [resp]
        while chal is not None:
            resp.set_challenge(chal)
            resp = mechanism.client_attempt(creds, responses)
            responses.append(resp)
            chal, reply = self._client_respond(mechanism, resp.get_response())
        return reply


# vim:et:fdm=marker:sts=4:sw=4:ts=4
