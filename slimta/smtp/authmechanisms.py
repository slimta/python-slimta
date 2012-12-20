# Copyright (c) 2012 Ian C. Good
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

from gevent.socket import getfqdn

__all__ = ['Plain', 'Login', 'CramMd5']


class Plain(object):

    name = 'PLAIN'

    def __init__(self, secret_func):
        self.secret_func = secret_func

    def challenge(data, last_response, final_reply):
        pass


class Login(object):

    name = 'LOGIN'

    def __init__(self, secret_func):
        self.secret_func = secret_func

    def challenge(data, last_response, final_reply):
        pass


class CramMd5(object):

    name = 'CRAMMD5'

    def __init__(self, secret_func, hostname=None):
        self.secret_func = secret_func
        self.hostname = hostname or getfqdn()

    def challenge(data, last_response, final_reply):
        pass


# vim:et:fdm=marker:sts=4:sw=4:ts=4
