
import unittest

from assertions import *

from slimta.smtp.extensions import Extensions


class TestSmtpExtensions(unittest.TestCase):

    def setUp(self):
        self.ext = Extensions()
        self.ext.extensions = {'EMPTY': None, 'TEST': 'STUFF'}

    def test_contains(self):
        assert_true('TEST' in self.ext)
        assert_true('test' in self.ext)
        assert_false('BAD' in self.ext)

    def test_reset(self):
        assert_true('TEST' in self.ext)
        self.ext.reset()
        assert_false('TEST' in self.ext)

    def test_add(self):
        self.ext.add('new')
        assert_true('NEW' in self.ext)

    def test_drop(self):
        assert_true(self.ext.drop('test'))
        assert_false('TEST' in self.ext)
        assert_false(self.ext.drop('BAD'))

    def test_getparam(self):
        assert_equal(None, self.ext.getparam('BAD'))
        assert_equal(None, self.ext.getparam('EMPTY'))
        assert_equal('STUFF', self.ext.getparam('TEST'))

    def test_getparam_filter(self):
        ret = self.ext.getparam('TEST', lambda x: x.strip('F'))
        assert_equal('STU', ret)
        ret = self.ext.getparam('EMPTY', lambda x: x)
        assert_equal(None, ret)

    def test_getparam_filter_valueerror(self):
        assert_equal(None, self.ext.getparam('TEST', int))

    def test_parse_string(self):
        ext = Extensions()
        header = ext.parse_string("""\
the header
EXT1
PARSETEST DATA""")
        assert_equal('the header', header)
        assert_true('EXT1' in ext)
        assert_true('PARSETEST' in ext)
        assert_equal(None, ext.getparam('EXT1'))
        assert_equal('DATA', ext.getparam('PARSETEST'))

    def test_build_string(self):
        possibilities = ("""\
the header
EMPTY
TEST STUFF""", """\
the header
TEST STUFF
EMPTY""")
        ret = self.ext.build_string('the header').replace('\r', '')
        assert_true(ret in possibilities)

    def test_build_string_valueerror(self):
        class MyExtension(object):
            def __init__(self):
                pass
            def __str__(self):
                raise ValueError('test')
        ext = Extensions()
        ext.extensions = {'ONE': 'OK VALUE', 'TWO': MyExtension()}
        expected = """the header\r\nONE OK VALUE"""
        assert_equal(expected, ext.build_string('the header'))


# vim:et:fdm=marker:sts=4:sw=4:ts=4
