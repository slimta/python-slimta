import unittest2 as unittest

from slimta.smtp.reply import Reply
from slimta.smtp.io import IO


class TestSmtpReply(unittest.TestCase):

    def test_not_populated(self):
        r = Reply(command=b'SOMECOMMAND')
        self.assertEqual(None, r.code)
        self.assertEqual(None, r.message)
        self.assertEqual(None, r.enhanced_status_code)
        self.assertFalse(r)
        self.assertEqual(b'SOMECOMMAND', r.command)

    def test_eq(self):
        r1 = Reply(b'250', b'2.1.0 Ok')
        r2 = Reply(b'250', b'2.1.0 Ok')
        r3 = Reply(b'251', b'2.1.0 Ok')
        r4 = Reply(b'250', b'2.1.1 Ok')
        self.assertEqual(r1, r2)
        self.assertNotEqual(r1, r3)
        self.assertNotEqual(r1, r4)
        self.assertNotEqual(r3, r4)

    def test_repr(self):
        r = Reply(b'250', b'2.1.0 Ok')
        expected = '<Reply code={0!r} message={1!r}>'.format(r.code, r.message)
        self.assertEqual(expected, repr(r))

    def test_str(self):
        r = Reply(b'250', b'2.1.0 Ok')
        self.assertEqual('250 2.1.0 Ok', str(r))

    def test_bytes(self):
        r = Reply(b'250', b'2.1.0 Ok')
        self.assertEqual(b'250 2.1.0 Ok', bytes(r))

    def test_is_error(self):
        replies = [Reply(str(i).encode('ascii')+b'50', b'Test')
                   for i in range(1, 6)]
        self.assertFalse(replies[0].is_error())
        self.assertFalse(replies[1].is_error())
        self.assertFalse(replies[2].is_error())
        self.assertTrue(replies[3].is_error())
        self.assertTrue(replies[4].is_error())

    def test_copy(self):
        r1 = Reply(b'250', b'2.1.0 Ok')
        r2 = Reply(command=b'RCPT')
        r2.copy(r1)
        self.assertEqual(b'250', r2.code)
        self.assertEqual(b'2.1.0', r2.enhanced_status_code)
        self.assertEqual(b'2.1.0 Ok', r2.message)
        self.assertEqual(b'RCPT', r2.command)

    def test_code_set(self):
        r = Reply()
        r.code = None
        self.assertEqual(None, r.code)
        r.code = b'100'
        self.assertEqual(b'100', r.code)

    def test_code_set_bad_value(self):
        r = Reply()
        with self.assertRaises(ValueError):
            r.code = b'asdf'

    def test_esc_set(self):
        r = Reply(b'250')
        r.enhanced_status_code = None
        self.assertEqual(b'2.0.0', r.enhanced_status_code)
        r.enhanced_status_code = b'2.3.4'
        self.assertEqual(b'2.3.4', r.enhanced_status_code)

    def test_esc_without_code(self):
        r = Reply()
        r.enhanced_status_code = b'2.3.4'
        self.assertEqual(None, r.enhanced_status_code)
        r.code = b'250'
        self.assertEqual(b'2.3.4', r.enhanced_status_code)

    def test_esc_set_false(self):
        r = Reply(b'250', b'Ok')
        self.assertEqual(b'2.0.0 Ok', r.message)
        r.enhanced_status_code = None
        self.assertEqual(b'2.0.0 Ok', r.message)
        r.enhanced_status_code = False
        self.assertEqual(b'Ok', r.message)

    def test_esc_set_bad_value(self):
        r = Reply()
        with self.assertRaises(ValueError):
            r.enhanced_status_code = b'abc'

    def test_message_set(self):
        r = Reply()
        r.message = None
        self.assertEqual(None, r.message)
        r.message = b'Ok'
        self.assertEqual(b'Ok', r.message)

    def test_message_set_with_esc(self):
        r = Reply(b'250')
        r.message = b'2.3.4 Ok'
        self.assertEqual(b'2.3.4 Ok', r.message)
        self.assertEqual(b'2.3.4', r.enhanced_status_code)

    def test_message_set_clear_esc(self):
        r = Reply(b'250', b'2.3.4 Ok')
        self.assertEqual(b'2.3.4 Ok', r.message)
        self.assertEqual(b'2.3.4', r.enhanced_status_code)
        r.message = None
        self.assertEqual(None, r.message)
        self.assertEqual(b'2.0.0', r.enhanced_status_code)

    def test_code_changes_esc_class(self):
        r = Reply(b'550', b'2.3.4 Stuff')
        self.assertEqual(b'5.3.4', r.enhanced_status_code)

    def test_send(self):
        r = Reply(b'250', b'Ok')
        io = IO(None)
        r.send(io)
        self.assertEqual(b'250 2.0.0 Ok\r\n', io.send_buffer.getvalue())

    def test_send_newline_first(self):
        r = Reply(b'250', b'Ok')
        r.newline_first = True
        io = IO(None)
        r.send(io)
        self.assertEqual(b'\r\n250 2.0.0 Ok\r\n', io.send_buffer.getvalue())


# vim:et:fdm=marker:sts=4:sw=4:ts=4
