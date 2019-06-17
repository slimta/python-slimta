from mox3.mox import MoxTestBase, IsA, IgnoreArg
import unittest
import logging

import slimta.logging
from slimta.policy.headers import AddDateHeader, AddMessageIdHeader, \
                                  AddReceivedHeader, AddDKIMHeader
from slimta.envelope import Envelope


class TestPolicyHeaders(MoxTestBase, unittest.TestCase):

    def test_add_date_header(self):
        env = Envelope()
        env.parse(b'')
        env.timestamp = 1234567890
        adh = AddDateHeader()
        self.assertEqual(None, env.headers['Date'])
        adh.apply(env)
        self.assertTrue(env.headers['Date'])

    def test_add_date_header_existing(self):
        env = Envelope()
        epoch = 'Thu, 01 Jan 1970 00:00:00 -0000'
        env.parse(b'Date: '+epoch.encode()+b'\r\n')
        adh = AddDateHeader()
        self.assertEqual(epoch, env.headers['Date'])
        adh.apply(env)
        self.assertEqual(epoch, env.headers['Date'])

    def test_add_message_id_header(self):
        env = Envelope()
        env.parse(b'')
        env.timestamp = 1234567890
        amih = AddMessageIdHeader('example.com')
        self.assertEqual(None, env.headers['Message-Id'])
        amih.apply(env)
        pattern = r'^<[0-9a-fA-F]{32}\.1234567890@example.com>$'
        self.assertRegexpMatches(env.headers['Message-Id'], pattern)

    def test_add_message_id_header_existing(self):
        env = Envelope()
        env.parse(b'Message-Id: testing\r\n')
        amih = AddMessageIdHeader()
        self.assertEqual('testing', env.headers['Message-Id'])
        amih.apply(env)
        self.assertEqual('testing', env.headers['Message-Id'])

    def test_add_received_header(self):
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse(b'From: test@example.com\r\n')
        env.timestamp = 1234567890
        env.client['name'] = 'mail.example.com'
        env.client['ip'] = '1.2.3.4'
        env.client['protocol'] = 'ESMTPS'
        env.receiver = 'test.com'
        arh = AddReceivedHeader()
        arh.apply(env)
        self.assertRegexpMatches(env.headers['Received'],
                r'from mail\.example\.com \(unknown \[1.2.3.4\]\) by test.com '
                r'\(slimta [^\)]+\) with ESMTPS for <rcpt@example.com>; ')

    def test_add_received_header_prepended(self):
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse(b'From: test@example.com\r\n')
        AddReceivedHeader().apply(env)
        self.assertEqual(['Received', 'From'], env.headers.keys())

    def test_add_dkim_header(self):
        log = []
        def set_log(a,b,c,d, **kwargs):
            log.append(d)
        self.mox.StubOutWithMock(slimta.logging, 'logline')
        slimta.logging.logline(IgnoreArg(), IsA(str), IsA(int), IsA(str),
                sender='sender').WithSideEffects(set_log)
        slimta.logging.logline(IgnoreArg(), IsA(str), IsA(int),
                IsA(str)).WithSideEffects(set_log)
        slimta.logging.logline(IgnoreArg(), IsA(str), IsA(int),
                IsA(str), domain=b'example.com',
                sender='sender@example.com').WithSideEffects(set_log)
        self.mox.ReplayAll()
        env = Envelope('sender', ['rcpt@example.com'])
        env.parse(b'From: test@example.com\r\n')
        dkim = {}
        AddDKIMHeader(dkim).apply(env)
        self.assertFalse(env.headers['DKIM-Signature'])
        self.assertTrue(log[0] == "DKIM: invalid sender")
        env = Envelope('sender@example.com', ['rcpt@example.com'])
        env.parse(b'From: test@example.com\r\n')
        AddDKIMHeader(dkim).apply(env)
        self.assertFalse(env.headers['DKIM-Signature'])
        self.assertTrue(log[1] ==
                "DKIM: domain :'example.com' is not setup, ignore")
        dkim['example.com'] = { 'privkey': 'bad', 'selector': 'sel',
                'signature_algorithm': 'rsa-sha1',
                'include_headers': ['from','subject'] }
        AddDKIMHeader(dkim).apply(env)
        self.assertFalse(env.headers['DKIM-Signature'])
        self.assertTrue(log[2] == "DKIM: exception:Private key not found")
        pk = """
-----BEGIN RSA PRIVATE KEY-----
MIIBOwIBAAJBAMhmwtECnKod9ywj8KcK308anyuS2iglAAoaAsibaduk0TTZX/sG
wOAwwh71jsrdMIMDKGAnOn7ikYSVfxvFUQsCAwEAAQJAVWVsyRIa3mcsh9O83gHF
DPlkMHZAnnC95pAU9ZU8c8qzGolDz2h3g+3py09L2dNN1KrmHgjs706OuKznTK3C
KQIhAPocPlKGOQvM5t1Iv7kU2dkMsDso5iMLWJ7si5zTAM7/AiEAzR7aoUhJiFaD
gm35ak2QzAk99H6uZXL5pPCvQJ+HyfUCIQCxTXJU2Df6iJAk0JyxXPmuJ5OK7Mxw
jWuOhgvW6bIKCwIhAJ7RT+hmpwCYM7TuX5puOjmwwjanS3KjRiXucVMw8httAiBV
LB94QlyDoRo6NOTbRIU1quGV/G3jufSl5hgqwuibQw==
-----END RSA PRIVATE KEY-----
"""
        dkim['example.com'] = { 'privkey': pk, 'selector': 'sel',
                'signature_algorithm': 'rsa-sha1',
                'include_headers': ['from','subject'] }
        AddDKIMHeader(dkim).apply(env)
        self.assertTrue(env.headers['DKIM-Signature'])
        sighd = env.headers['DKIM-Signature']
        self.assertIn('a=rsa-sha1', sighd)
        self.assertIn('d=example.com', sighd)
        self.assertIn('s=sel', sighd)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
