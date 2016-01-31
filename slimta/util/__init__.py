# Copyright (c) 2016 Ian C. Good
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

"""Package containing a variety of useful modules utilities that didn't really
belong anywhere else.

"""

from __future__ import absolute_import

__all__ = ['validate_tls']


def validate_tls(tls, **overrides):
    """Given a dictionary that could be used as keyword arguments to
    :class:`ssl.wrap_socket`, checks the existence of any certificate files.

    :param tls: Dictionary of TLS settings as might be passed in to an |Edge|
                constructor.
    :type tls: dict
    :param overrides: May be used to override any of the elements of the
                      ``tls`` dictionary.
    :type overrides: keyword arguments
    :returns: The new, validated ``tls`` dictionary.
    :raises: OSError

    """
    if not tls:
        return tls
    tls_copy = tls.copy()
    for arg in ('keyfile', 'certfile', 'ca_certs'):
        if arg in tls_copy:
            open(tls_copy[arg], 'r').close()
    tls_copy.update(overrides)
    return tls_copy


# vim:et:fdm=marker:sts=4:sw=4:ts=4
