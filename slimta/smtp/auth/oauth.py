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

"""Module containing the definition of the SASL `XOAUTH2`_, used by `OAuth
2.0`_ systems to authenticate using access tokens.

.. _XOAUTH2: https://developers.google.com/gmail/xoauth2_protocol
.. _OAuth 2.0: http://tools.ietf.org/html/draft-ietf-oauth-v2-22

"""

from __future__ import absolute_import

import base64

from . import ClientMechanism

__all__ = ['OAuth2']


class OAuth2(ClientMechanism):
    """``XOAUTH2`` authentication mechanism. Used by email servers that provide
    OAuth 2.0 authentication, such as Gmail. Using their credentials, clients
    will receive a temporary access token string from the identity service.
    This token string is then used by ``XOAUTH2`` to authenticate the SMTP
    session.

    This mechanism is only available for client-side authentication.

    """

    #: This mechanism identifies itself as ``XOAUTH2``.
    name = 'XOAUTH2'

    response_tmpl = 'user={user}\001auth=Bearer{token}\001\001'

    @classmethod
    def client_attempt(cls, io, authcid, secret, authzid):
        response = cls.response_tmpl.format(user=authcid, token=secret)
        b64_response = base64.b64encode(response)
        challenge = cls.send_response_get_challenge(io, b64_response, True)
        if challenge.code == '334':
            return cls.send_response_get_challenge(io, '')
        else:
            return challenge


# vim:et:fdm=marker:sts=4:sw=4:ts=4
