
import unittest

from mox import MoxTestBase, IsA
import spf

from slimta.spf import EnforceSpf
from slimta.envelope import Envelope
from slimta.smtp.reply import Reply


class TestEnforceSpf(MoxTestBase):

    def setUp(self):
        super(TestEnforceSpf, self).setUp()
        self.mox.StubOutWithMock(spf, 'check2')

    def test_bad_result_type(self):
        espf = EnforceSpf()
        with self.assertRaises(ValueError):
            espf.set_enforcement('asdf')
        espf.set_enforcement('PASS')
        espf.set_enforcement('pass')

    def test_no_policy_match(self):
        espf = EnforceSpf()
        espf.set_enforcement('fail', match_code='550')
        class TestSession(object):
            address = ('1.2.3.4', 56789)
            envelope = None
            ehlo_as = 'testehlo'
        class TestValidators(object):
            def __init__(self):
                self.session = TestSession()
            @espf.check
            def validate_mail(self, reply, sender):
                pass

        spf.check2(i='1.2.3.4', s='sender@example.com', h='testehlo').AndReturn(('none', 'the reason'))
        self.mox.ReplayAll()
        validators = TestValidators()
        reply = Reply('250', '2.0.0 Ok')
        validators.validate_mail(reply, 'sender@example.com')
        self.assertEqual('250', reply.code)
        self.assertEqual('2.0.0 Ok', reply.message)

    def test_policy_match(self):
        espf = EnforceSpf()
        espf.set_enforcement('fail', match_code='550')
        class TestSession(object):
            address = ('1.2.3.4', 56789)
            envelope = None
            ehlo_as = 'testehlo'
        class TestValidators(object):
            def __init__(self):
                self.session = TestSession()
            @espf.check
            def validate_mail(self, reply, sender):
                pass

        spf.check2(i='1.2.3.4', s='sender@example.com', h='testehlo').AndReturn(('fail', 'the reason'))
        self.mox.ReplayAll()
        validators = TestValidators()
        reply = Reply('250', '2.0.0 Ok')
        validators.validate_mail(reply, 'sender@example.com')
        self.assertEqual('550', reply.code)
        self.assertEqual('5.7.1 Access denied', reply.message)

    def test_on_validate_rcpt(self):
        espf = EnforceSpf()
        espf.set_enforcement('fail', match_code='550')
        class TestSession(object):
            address = ('1.2.3.4', 56789)
            envelope = Envelope('sender@example.com')
            ehlo_as = 'testehlo'
        class TestValidators(object):
            def __init__(self):
                self.session = TestSession()
            @espf.check
            def validate_rcpt(self, reply, recipient):
                pass

        spf.check2(i='1.2.3.4', s='sender@example.com', h='testehlo').AndReturn(('fail', 'the reason'))
        self.mox.ReplayAll()
        validators = TestValidators()
        reply = Reply('250', '2.0.0 Ok')
        validators.validate_rcpt(reply, 'asdf')
        self.assertEqual('550', reply.code)
        self.assertEqual('5.7.1 Access denied', reply.message)

    def test_reason_in_message(self):
        espf = EnforceSpf()
        espf.set_enforcement('pass', match_code='250', match_message='{reason}')
        class TestSession(object):
            address = ('1.2.3.4', 56789)
            envelope = None
            ehlo_as = 'testehlo'
        class TestValidators(object):
            def __init__(self):
                self.session = TestSession()
            @espf.check
            def validate_mail(self, reply, sender):
                pass

        spf.check2(i='1.2.3.4', s='sender@example.com', h='testehlo').AndReturn(('pass', 'the reason'))
        self.mox.ReplayAll()
        validators = TestValidators()
        reply = Reply('250', '2.0.0 Ok')
        validators.validate_mail(reply, 'sender@example.com')
        self.assertEqual('250', reply.code)
        self.assertEqual('2.0.0 the reason', reply.message)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
