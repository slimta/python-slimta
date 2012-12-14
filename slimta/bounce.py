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
import email.generator
import email.parser
import cStringIO

from envelope import Envelope

__all__ = ['Bounce']

# {{{ default_header_template
default_header_template = re.sub(r'\r?\n', r'\r\n', """\
From: MAILER-DAEMON
To: {sender}
Subject: Undelivered Mail Returned to Sender
Auto-Submitted: auto-replied
MIME-Version: 1.0
Content-Type: multipart/report; report-type=delivery-status; 
    boundary="{boundary}"
Content-Transfer-Encoding: 7bit

This is a multi-part message in MIME format.

--{boundary}
Content-Type: text/plain

Delivery failed.

Destination host responded:
{code} {message}

--{boundary}
Content-Type: message/delivery-status

Remote-MTA: dns; {client_name} [{client_ip}]
Diagnostic-Code: {protocol}; {code} {message}

--{boundary}
Content-Type: message/rfc822

""")
# }}}

# {{{ default_footer_template
default_footer_template = re.sub(r'\r?\n', r'\r\n', """\

--{boundary}--
""")
# }}}

class Bounce(Envelope):
    """Class that inherits |Envelope| to implement a bounce message, which is
    then delivered back to the original sender to say the message failed to
    deliver.  The original message body is attached to the bounce message.

    :param envelope: The |Envelope| object of the original failed message.
    :param reply: The |Reply| object that caused the failure.
    :param id: Optional ID of the new message.
    :type id: string

    """

    #: The address to use as the sender of new bounce messages. Per SMTP RFCs,
    #: this should usually be an empty string.
    sender = ''

    #: Template to use for the bounce message data, inserted directly before the
    #: original message data. The template is processed with :meth:`str.format`
    #: with the following keys:
    #:
    #: * ``boundary`` -- A randomly generated MIME boundary string.
    #: * ``sender`` -- The sender of the original message.
    #: * ``client_name`` -- The hostname of the original message sending client.
    #: * ``client_ip`` -- The IP address of the original message sending client.
    #: * ``protocol`` -- The protocol used to deliver the original message.
    #: * ``code`` -- The SMTP reply code that caused the message failure.
    #: * ``message`` -- The SMTP reply message that caused the message failure.
    header_template = default_header_template

    #: Template used to add text below the original message data. This template
    #: is processed the same way as ``header_template``.
    footer_template = default_footer_template

    def __init__(self, envelope, reply, id=None):
        message = self._build_message(envelope, reply)
        super(Bounce, self).__init__(id=id, sender=self.sender,
                                     recipients=[envelope.sender],
                                     message=message)

    def _get_substitution_table(self, envelope, reply):
        return {'boundary': 'boundary_={0}'.format(uuid.uuid4().hex),
                'sender': envelope.sender,
                'client_name': 'unknown',
                'client_ip': 'unknown',
                'dest_host': 'unknown',
                'dest_port': 'unknown',
                'protocol': 'SMTP',
                'code': reply.code,
                'message': reply.message}

    def _build_message(self, envelope, reply):
        sub_table = self._get_substitution_table(envelope, reply)
        new_payload = cStringIO.StringIO()
        new_payload.write(self.header_template.format(**sub_table))
        email.generator.Generator(new_payload).flatten(envelope.message)
        new_payload.write(self.footer_template.format(**sub_table))
        new_payload.seek(0)
        return email.parser.Parser().parse(new_payload)


# vim:et:fdm=marker:sts=4:sw=4:ts=4