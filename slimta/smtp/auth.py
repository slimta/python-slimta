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

import re

from slimta.smtp.reply import Reply

__all__ = ['Auth']

arg_pattern = re.compile(r'^([a-zA-Z_-]+)\s*(.*)$')


class Auth(object):

    def __init__(self, secret_func, mechanisms):
        self.mechanisms = [mechanism(secret_func) for mechanism in mechanisms]

    def for_server(self, server):
        return ServerAuth(mechanisms, server)


class ServerAuth(object):

    def __init__(self, mechanisms, server):
        self.mechanisms = mechanisms
        self.server = server

    def __str__(self):
        return ' '.join(self.available_mechanisms())

    def available_mechanisms(self):
        if self.server.encrypted:
            return [mech.name for mech in self.mechanisms]
        else:
            return [mech.name for mech in self.mechanisms if mech.secure]

    def _parse_arg(self, arg):
        match = arg_pattern.match(arg)
        if not match:
            return None, None
        mechanism_name = match.group(1).upper()
        for mechanism in self.mechanisms:
            if mechanism.name == mechanism_name:
                return mechanism, match.group(2)

    def new_attempt(self, reply, arg):
        mechanism, response = self._parse_arg(arg)
        return ServerAuthAttempt(mechanism, response, reply)


class ServerAuthAttempt(object):

    invalid_mechanism = Reply('504', '5.5.4 Invalid authentication mechanism')
    client_canceled = Reply('501', '5.7.0 Authentication canceled by client')

    def __init__(self, mechanism, initial_response, reply):
        self.mechanism = mechanism
        self.last_response = initial_response
        self.auth_result = None
        self.reply = reply

    def challenge(self):
        if not self.mechanism:
            self.reply.copy(self.invalid_mechanism)
            return
        data = {}
        challenge_func = self.mechanism.challenge
        while True:
            if self.last_response == '*':
                self.reply.copy(client_canceled)
                return

            self.auth_result, challenge = challenge_func(data,
                                                         self.last_response,
                                                         self.reply)
            if challenge:
                yield challenge
            else:
                break

    def submit_response(self, response):
        self.last_response = response

    def get_result(self):
        return self.auth_result


# vim:et:fdm=marker:sts=4:sw=4:ts=4
