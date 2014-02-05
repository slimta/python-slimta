
import unittest
import re


class _AssertRaisesContextManager(object):

    def __init__(self, expected_exception):
        super(_AssertRaisesContextManager, self).__init__()
        self._expected_exception = expected_exception

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.exception = exc_val
        return issubclass(exc_type, self._expected_exception)


class BackportedAssertions(unittest.TestCase):

    def assertIs(self, a, b):
        msg = '{0!r} is not {1!r}'.format(a, b)
        self.assertTrue(a is b, msg)

    def assertIsNot(self, a, b):
        msg = '{0!r} is {1!r}'.format(a, b)
        self.assertTrue(a is not b, msg)

    def assertIsNone(self, a):
        msg = '{0!r} is not None'.format(a)
        self.assertTrue(a is None, msg)

    def assertIsNotNone(self, a):
        msg = '{0!r} is None'.format(a)
        self.assertTrue(a is not None, msg)

    def assertIn(self, a, b):
        msg = '{0!r} not in {1!r}'.format(a, b)
        self.assertTrue(a in b, msg)

    def assertNotIn(self, a, b):
        msg = '{0!r} in {1!r}'.format(a, b)
        self.assertTrue(a not in b, msg)

    def assertIsInstance(self, a, b):
        msg = '{0!r} is not an instance of {1}'.format(a, b.__name__)
        self.assertTrue(isinstance(a, b), msg)

    def assertNotIsInstance(self, a, b):
        msg = '{0!r} is an instance of {1}'.format(a, b.__name__)
        self.assertTrue(not isinstance(a, b), msg)

    def assertRegexpMatches(self, s, r):
        msg = '{0!r} does not match {1!r}'.format(s, r)
        self.assertTrue(re.match(r, s), msg)

    def assertNotRegexpMatches(self, s, r):
        msg = '{0!r} matches {1!r}'.format(s, r)
        self.assertFalse(re.match(r, s), msg)

    def assertRaises(self, exception, callable=None, *args, **kwargs):
        if callable:
            old_assertRaises = super(BackportedAssertions, self).assertRaises
            return old_assertRaises(exception, callable, *args, **kwargs)
        else:
            return _AssertRaisesContextManager(exception)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
