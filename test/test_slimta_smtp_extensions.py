
import unittest2 as unittest

from slimta.smtp.extensions import Extensions


class TestSmtpExtensions(unittest.TestCase):

    def setUp(self):
        self.ext = Extensions()
        self.ext.extensions = {'EMPTY': None, 'TEST': 'STUFF'}

    def test_contains(self):
        self.assertTrue('TEST' in self.ext)
        self.assertTrue('test' in self.ext)
        self.assertFalse('BAD' in self.ext)

    def test_reset(self):
        self.assertTrue('TEST' in self.ext)
        self.ext.reset()
        self.assertFalse('TEST' in self.ext)

    def test_add(self):
        self.ext.add('new')
        self.assertTrue('NEW' in self.ext)

    def test_drop(self):
        self.assertTrue(self.ext.drop('test'))
        self.assertFalse('TEST' in self.ext)
        self.assertFalse(self.ext.drop('BAD'))

    def test_getparam(self):
        self.assertEqual(None, self.ext.getparam('BAD'))
        self.assertEqual(None, self.ext.getparam('EMPTY'))
        self.assertEqual('STUFF', self.ext.getparam('TEST'))

    def test_getparam_filter(self):
        ret = self.ext.getparam('TEST', lambda x: x.strip('F'))
        self.assertEqual('STU', ret)
        ret = self.ext.getparam('EMPTY', lambda x: x)
        self.assertEqual(None, ret)

    def test_getparam_filter_valueerror(self):
        self.assertEqual(None, self.ext.getparam('TEST', int))

    def test_parse_string(self):
        ext = Extensions()
        header = ext.parse_string("""\
the header
EXT1
PARSETEST DATA""")
        self.assertEqual('the header', header)
        self.assertTrue('EXT1' in ext)
        self.assertTrue('PARSETEST' in ext)
        self.assertEqual(None, ext.getparam('EXT1'))
        self.assertEqual('DATA', ext.getparam('PARSETEST'))

    def test_build_string(self):
        possibilities = ("""\
the header
EMPTY
TEST STUFF""", """\
the header
TEST STUFF
EMPTY""")
        ret = self.ext.build_string('the header').replace('\r', '')
        self.assertTrue(ret in possibilities)

    def test_build_string_valueerror(self):
        class MyExtension(object):
            def __init__(self):
                pass
            def __str__(self):
                raise ValueError('test')
        ext = Extensions()
        ext.extensions = {'ONE': 'OK VALUE', 'TWO': MyExtension()}
        expected = """the header\r\nONE OK VALUE"""
        self.assertEqual(expected, ext.build_string('the header'))


# vim:et:fdm=marker:sts=4:sw=4:ts=4
