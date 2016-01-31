
import unittest2 as unittest

from slimta.util.bytesformat import BytesFormat


class TestBytesFormat(unittest.TestCase):

    def test_basic(self):
        bf = BytesFormat(b'abc{test}ghi{0}mno')
        self.assertEqual(b'abcdefghijklmno', bf.format(b'jkl', test=b'def'))

    def test_basic_with_encoding(self):
        bf = BytesFormat(b'abc{test}ghi')
        self.assertEqual(b'abcdefghi', bf.format(test='def'))

    def test_mode_ignore(self):
        bf = BytesFormat(b'abc{test}ghi')
        self.assertEqual(b'abc{test}ghi', bf.format())

    def test_mode_remove(self):
        bf = BytesFormat(b'abc{test}ghi', mode='remove')
        self.assertEqual(b'abcghi', bf.format())

    def test_mode_strict(self):
        bf = BytesFormat(b'abc{test}ghi{0}mno', mode='strict')
        with self.assertRaises(KeyError):
            bf.format(b'jkl')
        with self.assertRaises(IndexError):
            bf.format(test=b'def')

    def test_repr(self):
        bf = BytesFormat(b'abc{test}ghi{0}mno', mode='strict')
        self.assertRegexpMatches(repr(bf), r"b?'abc\{test\}ghi\{0\}mno'")


# vim:et:fdm=marker:sts=4:sw=4:ts=4
