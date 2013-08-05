
import unittest

from mox import MoxTestBase, IsA

from slimta.util import build_auth_from_dict
from slimta.smtp.auth import Auth, CredentialsInvalidError


class TestUtil(MoxTestBase):

    def test_build_auth_from_dict(self):
        test = {'user@example.com': 'asdftest'}
        Auth1 = build_auth_from_dict(test)
        Auth2 = build_auth_from_dict(test, lower_case=True)
        Auth3 = build_auth_from_dict(test, only_verify=False)
        self.assertTrue(issubclass(Auth1, Auth))
        self.assertTrue(issubclass(Auth2, Auth))
        self.assertTrue(issubclass(Auth3, Auth))
        auth1 = Auth1(None)
        auth2 = Auth2(None)
        auth3 = Auth3(None)
        self.assertEqual('user@example.com', auth1.verify_secret('user@example.com', 'asdftest', None))
        with self.assertRaises(CredentialsInvalidError):
            auth1.verify_secret('user@example.com', 'derp', None)
        with self.assertRaises(CredentialsInvalidError):
            auth1.verify_secret('USER@EXAMPLE.COM', 'asdftest', None)
        with self.assertRaises(CredentialsInvalidError):
            auth1.get_secret('user@example.com', None)
        auth2.verify_secret('USER@EXAMPLE.COM', 'asdftest', None)
        self.assertEqual(('asdftest', 'user@example.com'), auth3.get_secret('user@example.com', None))
        with self.assertRaises(CredentialsInvalidError):
            auth3.get_secret('bad@example.com', None)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
