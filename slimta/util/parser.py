from email.parser import Parser as _Parser

import six


if six.PY2:
    from cStringIO import StringIO
    from slimta.util.encoders import utf8only_encode, utf8only_decode

    class Parser(_Parser):
        def parsestr(self, text, headersonly=False):
            if isinstance(text, unicode):
                # difference with vanilla is we encode using utf-8, not ascii
                ret = self.parse(StringIO(utf8only_encode(text)),
                                 headersonly=headersonly)
            else:
                ret = _Parser.parsestr(self, text, headersonly)

            # homogeneous return type with py3
            ret._headers = [(utf8only_decode(i), utf8only_decode(j))
                            for i, j in ret._headers]

            return ret
else:
    Parser = _Parser
