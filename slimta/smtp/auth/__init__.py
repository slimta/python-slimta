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

"""Package implementing the ability for client and server SMTP sessions to
authenticate.

For servers, use |Auth| as a base class and override the
:meth:`~Auth.verify_secret()` and :meth:`~Auth.get_secret()` methods as needed.
To modify which auth mechanisms are advertised in clear- and encrypted
channels, you can override the :meth:`~Auth.get_available_mechanisms()` method
as well. Your |Auth| sub-class may be passed in to your
:class:`~slimta.smtp.server.Server` or :class:`~slimta.edge.smtp.SmtpEdge`.

"""

import re

from slimta.smtp import SmtpError
from slimta.smtp.reply import Reply

__all__ = ['CredentialsInvalidError', 'Auth']

noarg_pattern = re.compile(r'^([a-zA-Z0-9_-]+)$')
witharg_pattern = re.compile(r'^([a-zA-Z0-9_-]+)\s+(.*)$')


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
    """Base class that handles the authentication for an SMTP client or server
    session. This class should be inherited with its methods overridden as
    necessary.

    :param session: One of either a :class:`~slimta.smtp.server.Server` or a
                    :class:`~slimta.smtp.client.Client` object for the session.

    """

    def __init__(self, session):
        self.session = session
        from slimta.smtp.auth.mechanisms import supported
        self.supported_mechanisms = supported

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

    def get_available_mechanisms(self, secure=False):
        """Returns a list of mechanism classes from the
        :mod:`~slimta.smtp.auth.mechanisms` module that are available on the
        session. This usually depends on whether the connection is ``secure``,
        as plain-text mechanisms should not be used unencrypted.

        Unless overridden, this method will return attempt to use all built-in
        auth mechanisms.

        :param secure: Whether or not the session is encrypted.
        :type secure: ``True`` or ``False``
        :returns: List of available mechanism classes.

        """
        if secure:
            return self.supported_mechanisms
        else:
            return [mech for mech in self.supported_mechanisms if mech.secure]

    def __str__(self):
        available = self.get_available_mechanisms(self.session.encrypted)
        return ' '.join([mech.name for mech in available])

    def _parse_arg(self, arg):
        match = noarg_pattern.match(arg)
        if match:
            return match.group(1).upper(), None
        match = witharg_pattern.match(arg)
        if match:
            return match.group(1).upper(), match.group(2)
        raise InvalidMechanismError(arg)

    def server_attempt(self, io, arg):
        mechanism_name, mechanism_arg = self._parse_arg(arg)
        for mechanism in self.get_available_mechanisms(self.session.encrypted):
            if mechanism.name == mechanism_name:
                mech_obj = mechanism(self.verify_secret, self.get_secret)
                if mechanism_arg == '*':
                    raise AuthenticationCanceled()
                return mech_obj.server_attempt(io, mechanism_arg)
        raise InvalidMechanismError(arg)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
