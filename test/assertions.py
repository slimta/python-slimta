
import re

from nose.tools import assert_raises as old_assert_raises, \
                       assert_true as old_assert_true, \
                       assert_false as old_assert_false, \
                       __all__ as nose_tools_all
from nose.tools import *


__all__ = nose_tools_all


try:
    # This will throw a TypeError exception on Python < 2.7.
    old_assert_raises(Exception)
except TypeError:

    __all__ += ['assert_is', 'assert_is_not',
                'assert_is_none', 'assert_is_not_none',
                'assert_in', 'assert_not_in',
                'assert_is_instance', 'assert_not_is_instance',
                'assert_regexp_matches', 'assert_not_regexp_matches']

    class _AssertRaisesContextManager(object):

        def __init__(self, expected_exception):
            super(_AssertRaisesContextManager, self).__init__()
            self._expected_exception = expected_exception

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.exception = exc_val
            return issubclass(exc_type, self._expected_exception)


    def assert_is(a, b, msg=None):
        msg = msg or '{0!r} is not {1!r}'.format(a, b)
        old_assert_true(a is b, msg)

    def assert_is_not(a, b, msg=None):
        msg = msg or '{0!r} is {1!r}'.format(a, b)
        old_assert_true(a is not b, msg)

    def assert_is_none(a, msg=None):
        msg = msg or '{0!r} is not None'.format(a)
        old_assert_true(a is None, msg)

    def assert_is_not_none(a, msg=None):
        msg = msg or '{0!r} is None'.format(a)
        old_assert_true(a is not None, msg)

    def assert_in(a, b, msg=None):
        msg = msg or '{0!r} not in {1!r}'.format(a, b)
        old_assert_true(a in b, msg)

    def assert_not_in(a, b, msg=None):
        msg = msg or '{0!r} in {1!r}'.format(a, b)
        old_assert_true(a not in b, msg)

    def assert_is_instance(a, b, msg=None):
        msg = msg or '{0!r} is not an instance of {1}'.format(a, b.__name__)
        old_assert_true(isinstance(a, b), msg)

    def assert_not_is_instance(a, b, msg=None):
        msg = msg or '{0!r} is an instance of {1}'.format(a, b.__name__)
        old_assert_true(not isinstance(a, b), msg)

    def assert_regexp_matches(s, r, msg=None):
        msg = msg or '{0!r} does not match {1!r}'.format(s, r)
        old_assert_true(re.match(r, s), msg)

    def assert_not_regexp_matches(s, r, msg=None):
        msg = msg or '{0!r} matches {1!r}'.format(s, r)
        old_assert_false(re.match(r, s), msg)

    def assert_raises(exception, callable=None, *args, **kwargs):
        if callable:
            return old_assert_raises(exception, callable, *args, **kwargs)
        else:
            return _AssertRaisesContextManager(exception)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
