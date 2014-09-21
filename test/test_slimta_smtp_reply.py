
import unittest

from assertions import *

from slimta.smtp.reply import Reply
from slimta.smtp.io import IO


class TestSmtpReply(unittest.TestCase):

    def test_not_populated(self):
        r = Reply(command='SOMECOMMAND')
        assert_equal(None, r.code)
        assert_equal(None, r.message)
        assert_equal(None, r.enhanced_status_code)
        assert_false(r)
        assert_equal('SOMECOMMAND', r.command)

    def test_eq(self):
        r1 = Reply('250', '2.1.0 Ok')
        r2 = Reply('250', '2.1.0 Ok')
        r3 = Reply('251', '2.1.0 Ok')
        r4 = Reply('250', '2.1.1 Ok')
        assert_equal(r1, r2)
        assert_not_equal(r1, r3)
        assert_not_equal(r1, r4)
        assert_not_equal(r3, r4)

    def test_repr(self):
        r = Reply('250', '2.1.0 Ok')
        expected = '<Reply code={0!r} message={1!r}>'.format(r.code, r.message)
        assert_equal(expected, repr(r))

    def test_str(self):
        r = Reply('250', '2.1.0 Ok')
        assert_equal('250 2.1.0 Ok', str(r))

    def test_is_error(self):
        replies = [Reply(str(i)+'50', 'Test') for i in range(1, 6)]
        assert_false(replies[0].is_error())
        assert_false(replies[1].is_error())
        assert_false(replies[2].is_error())
        assert_true(replies[3].is_error())
        assert_true(replies[4].is_error())

    def test_copy(self):
        r1 = Reply('250', '2.1.0 Ok')
        r2 = Reply(command='RCPT')
        r2.copy(r1)
        assert_equal('250', r2.code)
        assert_equal('2.1.0', r2.enhanced_status_code)
        assert_equal('2.1.0 Ok', r2.message)
        assert_equal('RCPT', r2.command)

    def test_code_set(self):
        r = Reply()
        r.code = None
        assert_equal(None, r.code)
        r.code = '100'
        assert_equal('100', r.code)

    def test_code_set_bad_value(self):
        r = Reply()
        with assert_raises(ValueError):
            r.code = 'asdf'

    def test_esc_set(self):
        r = Reply('250')
        r.enhanced_status_code = None
        assert_equal('2.0.0', r.enhanced_status_code)
        r.enhanced_status_code = '2.3.4'
        assert_equal('2.3.4', r.enhanced_status_code)

    def test_esc_without_code(self):
        r = Reply()
        r.enhanced_status_code = '2.3.4'
        assert_equal(None, r.enhanced_status_code)
        r.code = '250'
        assert_equal('2.3.4', r.enhanced_status_code)

    def test_esc_set_false(self):
        r = Reply('250', 'Ok')
        assert_equal('2.0.0 Ok', r.message)
        r.enhanced_status_code = None
        assert_equal('2.0.0 Ok', r.message)
        r.enhanced_status_code = False
        assert_equal('Ok', r.message)

    def test_esc_set_bad_value(self):
        r = Reply()
        with assert_raises(ValueError):
            r.enhanced_status_code = 'abc'

    def test_message_set(self):
        r = Reply()
        r.message = None
        assert_equal(None, r.message)
        r.message = 'Ok'
        assert_equal('Ok', r.message)

    def test_message_set_with_esc(self):
        r = Reply('250')
        r.message = '2.3.4 Ok'
        assert_equal('2.3.4 Ok', r.message)
        assert_equal('2.3.4', r.enhanced_status_code)

    def test_message_set_clear_esc(self):
        r = Reply('250', '2.3.4 Ok')
        assert_equal('2.3.4 Ok', r.message)
        assert_equal('2.3.4', r.enhanced_status_code)
        r.message = None
        assert_equal(None, r.message)
        assert_equal('2.0.0', r.enhanced_status_code)

    def test_code_changes_esc_class(self):
        r = Reply('550', '2.3.4 Stuff')
        assert_equal('5.3.4', r.enhanced_status_code)

    def test_send(self):
        r = Reply('250', 'Ok')
        io = IO(None)
        r.send(io)
        assert_equal('250 2.0.0 Ok\r\n', io.send_buffer.getvalue())

    def test_send_newline_first(self):
        r = Reply('250', 'Ok')
        r.newline_first = True
        io = IO(None)
        r.send(io)
        assert_equal('\r\n250 2.0.0 Ok\r\n', io.send_buffer.getvalue())


# vim:et:fdm=marker:sts=4:sw=4:ts=4
