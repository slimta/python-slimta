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

"""Module containing useful tools, helpers, and other features that didn't
belong under any other module.

"""

from __future__ import absolute_import

from contextlib import contextmanager

from gevent import monkey

__all__ = ['monkeypatch_all', 'dns_resolver']


@contextmanager
def monkeypatch_all(*args, **kwds):
    """Returns a context manager that monkey-patches before execution and
    reverts after execution.

    :param args: Positional arguments fed directly into
                 :func:`gevent.monkey.patch_all`.
    :param kwds: Keyword arguments fed directly into
                 :func:`gevent.monkey.patch_all`.

    """
    modules = ['socket', 'ssl', 'os', 'time', 'select', 'thread', 'threading',
               'httplib']
    before = {}
    for mod in modules:
        mod_obj = __import__(mod)
        before[mod] = (mod_obj, vars(mod_obj).copy())
    monkey.patch_all(*args, **kwds)
    try:
        yield
    finally:
        for mod in modules:
            for k, v in before[mod][1].items():
                setattr(before[mod][0], k, v)


with monkeypatch_all():
    import dns.resolver

#: .. versionadded:: 0.3.19
#:
#: This is an instance of `dns.resolver.Resolver()
#: <http://www.dnspython.org/docs/1.11.1/dns.resolver.Resolver-class.html>`_
#: monkey-patched with :mod:`gevent`. Additionally it has its
#: ``retry_servfail`` attribute set to ``True``.
#:
#: Built-in slimta modules use this resolver for custom DNS queries, such as
#: *MX* record lookup. You can modify attributes such as ``timeout`` or
#: ``lifetime`` to control query behavior.
dns_resolver = dns.resolver.Resolver()
dns_resolver.retry_servfail = True


# vim:et:fdm=marker:sts=4:sw=4:ts=4
