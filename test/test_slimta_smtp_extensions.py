import unittest2 as unittest

from slimta.smtp.extensions import Extensions


class TestSmtpExtensions(unittest.TestCase):

    def setUp(self):
        self.ext = Extensions()
        self.ext.extensions = {b'EMPTY': None, b'TEST': b'STUFF'}

    def test_contains(self):
        self.assertTrue(b'TEST' in self.ext)
        self.assertTrue(b'test' in self.ext)
        self.assertFalse(b'BAD' in self.ext)

    def test_reset(self):
        self.assertTrue(b'TEST' in self.ext)
        self.ext.reset()
        self.assertFalse(b'TEST' in self.ext)

    def test_add(self):
        self.ext.add(b'new')
        self.assertTrue(b'NEW' in self.ext)

    def test_drop(self):
        self.assertTrue(self.ext.drop(b'test'))
        self.assertFalse(b'TEST' in self.ext)
        self.assertFalse(self.ext.drop(b'BAD'))

    def test_getparam(self):
        self.assertEqual(None, self.ext.getparam(b'BAD'))
        self.assertEqual(None, self.ext.getparam(b'EMPTY'))
        self.assertEqual(b'STUFF', self.ext.getparam(b'TEST'))

    def test_getparam_filter(self):
        ret = self.ext.getparam(b'TEST', lambda x: x.strip(b'F'))
        self.assertEqual(b'STU', ret)
        ret = self.ext.getparam(b'EMPTY', lambda x: x)
        self.assertEqual(None, ret)

    def test_getparam_filter_valueerror(self):
        self.assertEqual(None, self.ext.getparam(b'TEST', int))

    def test_parse_string(self):
        ext = Extensions()
        header = ext.parse_string(b"""\
the header
EXT1
PARSETEST DATA""")
        self.assertEqual(b'the header', header)
        self.assertTrue(b'EXT1' in ext)
        self.assertTrue(b'PARSETEST' in ext)
        self.assertEqual(None, ext.getparam(b'EXT1'))
        self.assertEqual(b'DATA', ext.getparam(b'PARSETEST'))

    def test_build_string(self):
        possibilities = (b"""\
the header
EMPTY
TEST STUFF""", b"""\
the header
TEST STUFF
EMPTY""")
        ret = self.ext.build_string(b'the header').replace(b'\r', b'')
        self.assertTrue(ret in possibilities, ret)

    def test_build_string_valueerror(self):
        class MyExtension(object):
            def __init__(self):
                pass
            def __bytes__(self):
                raise ValueError('test')
        ext = Extensions()
        ext.extensions = {b'ONE': b'OK VALUE', b'TWO': MyExtension()}
        expected = b"""the header\r\nONE OK VALUE"""
        self.assertEqual(expected, ext.build_string(b'the header'))


# vim:et:fdm=marker:sts=4:sw=4:ts=4
