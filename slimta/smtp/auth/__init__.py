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

from __future__ import absolute_import

import re

from .. import SmtpError
from ..reply import Reply

__all__ = ['CredentialsInvalidError', 'Auth',
           'ServerMechanism', 'ClientMechanism']

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
    """Base class that handles the authentication for an SMTP server session.
    This class should be inherited with its methods overridden as necessary.

    :param session: An active server session object.
    :type session: :class:`~slimta.smtp.server.Server`

    """

    def __init__(self, session):
        self.session = session
        from .standard import standard_mechanisms
        self.server_mechanisms = standard_mechanisms
        if id(Auth.get_secret.__func__) == id(self.get_secret.__func__):
            self.server_mechanisms = [mech for mech in self.server_mechanisms
                                      if not mech.requires_get_secret]

    def verify_secret(self, authcid, secret, authzid=None):
        """For SMTP server authentication, this method should be overriden
        to verify the given secret for mechanisms that have access to it.
        If ``secret`` is invalid for the given identities,
        :class:`CredentialsInvalidError` should be thrown.

        :param authcid: The authentication identity, usually the username.
        :param secret: The secret (i.e. password) string to verify for the
                       given authentication and authorization identities.
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

    def get_available_mechanisms(self, connection_secure=False):
        """Returns a list of mechanism classes that inherit
        :class:`~slimta.smtp.auth.ServerMechanism` that are available on
        the session. This usually depends on whether the connection is
        ``secure``, as plain-text mechanisms should not be used unencrypted.

        Unless overridden, this method will return attempt to use all built-in
        auth mechanisms.

        :param connection_secure: ``True`` if the current connection has been
                                  secured with TLS, ``False`` otherwise. This
                                  flag can be used to adjust which mechanisms
                                  are available to unencrypted sessions.
        :type connection_secure: boolean
        :returns: List of available mechanism classes.

        """
        if connection_secure:
            return self.server_mechanisms
        else:
            return [mech for mech in self.server_mechanisms if mech.secure]

    def __str__(self):
        available = self.get_available_mechanisms(self.session.encrypted)
        if available:
            return ' '.join([mech.name for mech in available])
        else:
            raise ValueError('No mechanisms available')

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
                identity = mech_obj.server_attempt(io, mechanism_arg)
                if not identity:
                    msg = 'Invalid identity returned from authentication'
                    raise ValueError(msg)
                return identity
        raise InvalidMechanismError(arg)


class ServerMechanism(object):
    """Base class of server-side SASL authentication mechanism implementations.

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

    #: This static string should be overriden by sub-classes to specify the
    #: SASL name that identifies this mechanism. This string will be used in
    #: the SMTP session. Custom mechanisms should be prefixed with ``X``.
    name = None

    #: This static flag should be overridden by sub-classes if use of the
    #: mechanism requires direct access to the original password, such as
    #: :class:`~slimta.smtp.auth.standard.CramMd5`.
    #:
    #: If an |Auth| sub-class does not override
    #: :meth:`~slimta.smtp.auth.Auth.get_secret`, mechanisms that have set this
    #: flag to ``True`` will be automatically removed.
    requires_get_secret = False

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


class ClientMechanism(object):
    """Base class of client-side SASL authentication mechanism implementations.
    Sub-classes will not be instantiated and should only use static members and
    class methods.

    """

    #: This static string should be overriden by sub-classes to specify the
    #: SASL name that identifies this mechanism. This string will be used in
    #: the SMTP session. Custom mechanisms should be prefixed with ``X``.
    name = None

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

    @classmethod
    def client_attempt(cls, io, authcid, secret, authzid):
        """Communicates back-and-forth with a server to negotiate
        authentication, based on the desired credentials. This class method
        must be overidden by sub-classes to be used by client-side SMTP
        sessions.

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


# vim:et:fdm=marker:sts=4:sw=4:ts=4
