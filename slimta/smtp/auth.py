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

from slimta.smtp import SmtpError
from slimta.smtp.reply import Reply

__all__ = ['CredentialsInvalidError', 'Auth']

arg_pattern = re.compile(r'^([a-zA-Z0-9_-]+)\s*(.*)$')


class AuthError(SmtpError):
    pass


class ServerAuthError(AuthError):
    
    def __init__(self, msg, reply):
        super(ServerAuthError, self).__init__(msg)
        self.reply = reply


class InvalidMechanismError(ServerAuthError):

    def __init__(self, arg):
        msg = 'Invalid authentication mechanism'
        reply = Reply('504', '5.5.4 '+msg)
        super(InvalidMechanismError, self).__init__(msg, reply)


class AuthenticationCanceled(ServerAuthError):

    def __init__(self):
        msg = 'Authentication canceled by client'
        reply = Reply('501', '5.7.0 '+msg)
        super(AuthenticationCanceled, self).__init__(msg, reply)


class CredentialsInvalidError(ServerAuthError):
    """Thrown when a clients credentials were not correct."""

    def __init__(self):
        msg = 'Authentication credentials invalid'
        reply = Reply('535', '5.7.8 '+msg)
        super(CredentialsInvalidError, self).__init__(msg, reply)



class Auth(object):
    """An object which can be associated with SMTP client or server connections
    to handle authentication by various supported mechanisms.

    :param mechanisms: Classes in :mod:`~slimta.smtp.authmechanisms` that should
                       be supported by the client or server.

    """

    def __init__(self, *mechanisms):
        self.mechanisms = [mechanism(self.verify_secret, self.get_secret)
                           for mechanism in mechanisms]

    def verify_secret(self, authcid, secret, authzid=None):
        """For SMTP server authentication, this method should be overriden
        to verify the given secret for mechanisms that have access to it.
        If ``secret`` is invalid for the given identities,
        :class:`CredentialsInvalidError` should be thrown.

        :param authcid: The authentication identity, usually the username.
        :param secret: The secret (i.e. password) string to verify for the given
                       authentication and authorization identities.
        :param authzid: The authorization identity, if applicable.
        :returns: A representation of the identity that was successfully
                  authenticated. This may be ``authcid``, ``authzid``, a tuple
                  of both, or any alternative.
        :raises: :class:`CredentialsInvalidError`

        """
        raise CredentialsInvalidError()

    def get_secret(self, authcid, authzid=None):
        """For SMTP server authentication mechanisms such as ``CRAM-MD5``, the
        client provides a hash of their secret credentials, and thus the server
        must also have access to the secret credentials in plain-text. This
        method should retrieve and return the secret string assocated with the
        given identities. This method should raise
        :class:`CredentialsInvalidError` only if the given identities did not
        exist.

        :param authcid: The authentication identity, usually the username.
        :param authzid: The authorization identity, if applicable.
        :returns: A tuple of the retrieved secret string followed by a
                  representation of the identity that was authenticated. This
                  may be ``authcid``, ``authzid``, a tuple of both, or any
                  desired alternative.
        :raises: :class:`CredentialsInvalidError`

        """
        raise CredentialsInvalidError()

    def for_server(self, server):
        return ServerAuth(self.mechanisms, server)


class ServerAuth(object):

    def __init__(self, mechanisms, server):
        self.mechanisms = mechanisms
        self.server = server

    def __str__(self):
        return ' '.join([mech.name for mech in self.available_mechanisms()])

    def available_mechanisms(self):
        if self.server.encrypted:
            return self.mechanisms
        else:
            return [mech for mech in self.mechanisms if mech.secure]

    def attempt(self, io, reply, arg):
        match = arg_pattern.match(arg)
        if not match:
            raise InvalidMechanismError(arg)
        mechanism_name = match.group(1).upper()
        for mechanism in self.available_mechanisms():
            if mechanism.name == mechanism_name:
                return mechanism.server_attempt(io, match.group(2))
        raise InvalidMechanismError(arg)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
