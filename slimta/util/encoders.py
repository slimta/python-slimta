import six

__all__ = ['encode_base64']


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
