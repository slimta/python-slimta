# Copyright (c) 2014 Ian C. Good
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

"""Implements slimta lookup against a `DB API 2.0`_ database interface. This
driver should be flexible enough to support any implementing database.

Any database used with this driver should use gevent sockets (or
monkey-patching) to ensure good performance.

This module also provides a SQLite_ convenience class.

.. _DB API 2.0: http://legacy.python.org/dev/peps/pep-0249/
.. _SQLite: http://www.sqlite.org/
.. _context manager: \
https://docs.python.org/2/library/stdtypes.html#context-manager-types

"""

from __future__ import absolute_import

import sqlite3
from collections.abc import Mapping
from contextlib import contextmanager

from . import LookupBase

__all__ = ['DBAPI2Lookup', 'SQLite3Lookup']


class DBAPI2Lookup(LookupBase):
    """Implements the slimta lookup interface using the generic `DB API 2.0`_
    specification.

    :param conn_ctxmgr: A `context manager`_ that, given no arguments, produces
                        an open database connection, and cleans it up
                        afterwards. This allows flexibility in how connections
                        are managed or pooled.
    :param query: The query string used to lookup records in the database.
    :type query: str
    :param query_param_order: If ``query`` uses positional parameters, this
                              must be a list of keywords from the
                              :meth:`.lookup` to translate from keywords to
                              positional arguments.
    :type query_param_order: list
    :param result_order: Most database implementations return rows as a
                         sequence instead of a mapping. In this case, this
                         argument must be given to translate the sequence into
                         a dictionary, ``TypeError`` may be raised in the
                         :meth:`.lookup` method otherwise.
    :param conn: If ``conn_ctxmgr`` is ``None``, a simple one is generated that
                 simply returns the value of this argument. Useful for
                 databases that have a single, persistent connection object.

    """

    def __init__(self, conn_ctxmgr, query, query_param_order=None,
                 result_order=None, conn=None):
        super(DBAPI2Lookup, self).__init__()
        self.query = query
        self.query_param_order = query_param_order
        self.result_order = result_order

        if not conn_ctxmgr:
            @contextmanager
            def get_conn():
                yield conn

            self.conn_ctxmgr = get_conn
        else:
            self.conn_ctxmgr = conn_ctxmgr

    def _do_lookup(self, kwargs):
        params = kwargs
        if self.query_param_order is not None:
            params = [kwargs[key] for key in self.query_param_order]
        with self.conn_ctxmgr() as conn:
            assert conn is not None
            cur = conn.cursor()
            try:
                cur.execute(self.query, params)
                row = cur.fetchone()
                if not row:
                    return
                if not isinstance(row, Mapping):
                    try:
                        result_order = row.keys()
                    except AttributeError:
                        result_order = self.result_order
                    assert result_order is not None
                    ret = {}
                    for i, key in enumerate(result_order):
                        ret[key] = row[i]
                    return ret
                return row
            finally:
                conn.rollback()
                cur.close()

    def lookup(self, **kwargs):
        ret = self._do_lookup(kwargs)
        self.log(__name__, kwargs, ret)
        return ret


class SQLite3Lookup(DBAPI2Lookup):
    """Implements the slimta lookup interface using the :py:mod:`sqlite3`
    module. The connection object is created immediately and kept open for all
    calls to :meth:`.lookup`.

    :param database: The database filename, as given in
                     :py:func:`sqlite3.connect`.
    :type database: str
    :param query: The query string used to lookup records in the database. This
                  query must use named-style placeholders (e.g.
                  ``col = :keyword``.
    :type query: str

    """

    def __init__(self, database, query):
        conn = sqlite3.connect(database)
        super(SQLite3Lookup, self).__init__(None, query, conn=conn)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
