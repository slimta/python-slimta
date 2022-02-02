
from contextlib import contextmanager

from mox import MoxTestBase, IsA

from slimta.lookup.drivers.dbapi2 import DBAPI2Lookup


class TestDBAPI2Lookup(MoxTestBase):

    def setUp(self):
        super(TestDBAPI2Lookup, self).setUp()
        self.conn = self.mox.CreateMockAnything()
        self.cur = self.mox.CreateMockAnything()
        @contextmanager
        def conn_ctxmgr():
            yield self.conn
        self.conn_ctxmgr = conn_ctxmgr

    def test_no_conn_ctxmgr(self):
        drv = DBAPI2Lookup(None, None, conn=1234)
        with drv.conn_ctxmgr() as conn:
            self.assertEqual(1234, conn)

    def test_all_keywords_lookup_hit(self):
        self.conn.cursor().AndReturn(self.cur)
        self.cur.execute('test query', {'one': 1, 'two': 2})
        self.cur.fetchone().AndReturn({'test': 'pass'})
        self.conn.rollback()
        self.cur.close()
        self.mox.ReplayAll()
        drv = DBAPI2Lookup(self.conn_ctxmgr, 'test query')
        self.assertEqual({'test': 'pass'}, drv.lookup(one=1, two=2))

    def test_all_keywords_lookup_miss(self):
        self.conn.cursor().AndReturn(self.cur)
        self.cur.execute('test query', {'one': 1, 'two': 2})
        self.cur.fetchone().AndReturn(None)
        self.conn.rollback()
        self.cur.close()
        self.mox.ReplayAll()
        drv = DBAPI2Lookup(self.conn_ctxmgr, 'test query')
        self.assertEqual(None, drv.lookup(one=1, two=2))

    def test_no_keywords_lookup_hit(self):
        self.conn.cursor().AndReturn(self.cur)
        self.cur.execute('test query', [1, 2])
        self.cur.fetchone().AndReturn([3, 4])
        self.conn.rollback()
        self.cur.close()
        self.mox.ReplayAll()
        query_param_order = ['one', 'two']
        result_order = ['a', 'b']
        drv = DBAPI2Lookup(self.conn_ctxmgr, 'test query',
                           query_param_order, result_order)
        self.assertEqual({'a': 3, 'b': 4}, drv.lookup(one=1, two=2))


# vim:et:fdm=marker:sts=4:sw=4:ts=4
