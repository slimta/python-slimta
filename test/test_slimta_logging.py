
import unittest

from assertions import *

from testfixtures import log_capture

from slimta.logging import logline, parseline, log_exception


class TestLogging(unittest.TestCase):

    def _check_logline(self, expected):
        def check(data):
            assert_equal(expected, data)
        return check

    def test_logline_nodata(self):
        check = self._check_logline('test:asdf:nodata')
        logline(check, 'test', 'asdf', 'nodata')

    def test_logline_withdata(self):
        check = self._check_logline('test:asdf:withdata one=1 two=\'two\'')
        logline(check, 'test', 'asdf', 'withdata', one=1, two='two')

    def test_parseline_nodata(self):
        line = 'test:jkl:nodata'
        type, id, op, data = parseline(line)
        assert_equal('test', type)
        assert_equal('jkl', id)
        assert_equal('nodata', op)
        assert_equal({}, data)

    def test_parseline_withdata(self):
        line = 'test:jkl:withdata one=1 two=\'two\''
        type, id, op, data = parseline(line)
        assert_equal('test', type)
        assert_equal('jkl', id)
        assert_equal('withdata', op)
        assert_equal({'one': 1, 'two': 'two'}, data)

    def test_parseline_badbeginning(self):
        with assert_raises(ValueError):
            parseline('bad!')

    def test_parseline_baddata(self):
        line = 'test:jkl:baddata one=1 two=two'
        type, id, op, data = parseline(line)
        assert_equal('test', type)
        assert_equal('jkl', id)
        assert_equal('baddata', op)
        assert_equal({'one': 1}, data)
        line = 'test:jkl:baddata one=one two=\'two\''
        type, id, op, data = parseline(line)
        assert_equal('test', type)
        assert_equal('jkl', id)
        assert_equal('baddata', op)
        assert_equal({}, data)

    @log_capture()
    def test_log_exception(self, l):
        log_exception('test', extra='not logged')
        try:
            raise ValueError('testing stuff')
        except Exception:
            log_exception('test', extra='more stuff')
        assert_equal(1, len(l.records))
        rec = l.records[0]
        assert_equal('test', rec.name)
        assert_equal('ERROR', rec.levelname)
        type, id, op, data = parseline(rec.msg)
        assert_equal('exception', type)
        assert_equal('ValueError', id)
        assert_equal('unhandled', op)
        assert_equal('more stuff', data['extra'])
        assert_equal(('testing stuff', ), data['args'])
        assert_equal('testing stuff', data['message'])
        assert_true(data['traceback'])


# vim:et:fdm=marker:sts=4:sw=4:ts=4
