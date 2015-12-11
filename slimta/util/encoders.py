# -*- coding: utf-8 -*-

import six

__all__ = ['encode_base64']


def utf8only_decode(bytestr):
    """ Decode bytes assuming it's utf-8, raising no exception

    Part of the "be liberal in what you accept" policy

    :param bytestr: a string where no non-utf8 char is supposed to occur
    :type bytestr: str
    :rtype: bytes
    """
    return bytestr.decode('utf-8', 'replace')


printable_decode = utf8only_decode


def utf8only_encode(unistr):
    """ Encode to ascii

    Silently replaces invalid chars with "�"

    :param unistr: a string that may contain non-utf-8 characters
    :type unistr: str
    :rtype: bytes
    """
    return unistr.encode('utf-8', 'replace')


def strict_encode(unistr):
    """ Encode to ascii

    Silently replaces invalid chars with "?"

    :param unistr: a string where no 8-bit char is supposed to occur
    :type unistr: str
    :rtype: bytes
    """
    return unistr.encode('ascii', 'replace')


def xmlcharref_encode(unistr):
    """ Encode to ascii with xml escapment codes for 8-bit chars

    Note that those chars are nicely decoded by a wide range of MUA (even if
    that behavior is not part of any standard).

    :param unistr: a string where no 8-bit char is supposed to occur
    :type unistr: str
    :rtype: bytes
    """
    return unistr.encode('ascii', 'xmlcharref_encode')


if six.PY2:
    from email.encoders import _bencode

    def fix_payload_decode(payload):
        """ Inspired from pyton3.x email.message
        """
        try:
            bpayload = payload.encode('ascii')
        except UnicodeError:
            # This won't happen for RFC compliant messages (messages
            # containing only ASCII codepoints in the unicode input).
            # If it does happen, turn the string into bytes in a way
            # guaranteed not to fail.
            bpayload = payload.encode('raw-unicode-escape')
        return bpayload

    def encode_base64(msg):
        """Encode the message's payload in Base64.

        Also, add an appropriate Content-Transfer-Encoding header.
        """
        orig = msg.get_payload(decode=True)
        # it is likely decode=True did nothing and orig is still unicode data
        # (we expect bytes) acording to py2 implementation
        if isinstance(orig, unicode):
            orig = fix_payload_decode(orig)
        encdata = unicode(_bencode(orig), 'ascii')
        msg.set_payload(encdata)
        msg['Content-Transfer-Encoding'] = 'base64'

else:
    from email.encoders import encode_base64 as encode_base64
