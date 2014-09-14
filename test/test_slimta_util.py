
from assertions import *
from mox import MoxTestBase, IsA

from slimta.util import build_auth_from_dict
from slimta.smtp.auth import Auth, CredentialsInvalidError


class TestUtil(MoxTestBase):

    def test_build_auth_from_dict(self):
        test = {'user@example.com': 'asdftest'}
        Auth1 = build_auth_from_dict(test)
        Auth2 = build_auth_from_dict(test, lower_case=True)
        Auth3 = build_auth_from_dict(test, only_verify=False)
        assert_true(issubclass(Auth1, Auth))
        assert_true(issubclass(Auth2, Auth))
        assert_true(issubclass(Auth3, Auth))
        auth1 = Auth1(None)
        auth2 = Auth2(None)
        auth3 = Auth3(None)
        assert_equal('user@example.com', auth1.verify_secret('user@example.com', 'asdftest', None))
        with assert_raises(CredentialsInvalidError):
            auth1.verify_secret('user@example.com', 'derp', None)
        with assert_raises(CredentialsInvalidError):
            auth1.verify_secret('USER@EXAMPLE.COM', 'asdftest', None)
        with assert_raises(TypeError):
            auth1.get_secret('user@example.com', None)
        auth2.verify_secret('USER@EXAMPLE.COM', 'asdftest', None)
        assert_equal(('asdftest', 'user@example.com'), auth3.get_secret('user@example.com', None))
        with assert_raises(CredentialsInvalidError):
            auth3.get_secret('bad@example.com', None)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
