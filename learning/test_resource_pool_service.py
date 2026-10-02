#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P1-06-C2-A 当前错误/薄弱资源池只读服务测试（stdlib unittest，无新依赖）

使用**临时测试数据库**（正式 learning.db 的副本）+ 只读真实 contentpack：
  - 正式 learning.db 不被污染（测试前后 SHA256 一致、业务表仍 0 行）
  - contentpack 全程只读

覆盖：1 空集合 / 2 当前错误 / 3 历史错误已被纠正 → 出池 / 4 AI Training miss 语义（按结果入池）/
      5 priority_score 与排序 / 6 不同学习者与不同教材不互串 / 7 查询不写库 / 8 无 AI 调用 /
      9 排序稳定 / 10 正式库不被污染
"""

from __future__ import annotations

import hashlib
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True          # 不产生 __pycache__

import learning_service as svc            # noqa: E402  （C1：写入用，仅用于测试播种）
import resource_pool_service as pool      # noqa: E402  （C2-A：被测试对象，只读）


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


#: P2-1-C1：正式 learning.db 已包含真机真实学习数据，「业务表必须为 0 行」不再是有效基线。
BUSINESS_TABLES = ("learner", "learning_session", "learning_task", "task_item",
                   "learning_record", "mastery_state")


def business_counts(db_path) -> dict:
    conn = sqlite3.connect("file:%s?mode=ro" % Path(db_path).as_posix(), uri=True)
    try:
        return {t: conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
                for t in BUSINESS_TABLES}
    finally:
        conn.close()


OFFICIAL_DB_COUNTS = business_counts(svc.DEFAULT_LEARNING_DB)


class ResourcePoolTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.official_db = svc.DEFAULT_LEARNING_DB
        cls.official_sha = sha256_file(cls.official_db)
        cls.contentpack = svc.DEFAULT_CONTENTPACK_DB
        cls.contentpack_sha = sha256_file(cls.contentpack)
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="zhixue_c2a_"))
        cls.tmp_db = cls.tmpdir / "learning_test.db"
        shutil.copyfile(cls.official_db, cls.tmp_db)
        cp = svc.connect_contentpack_db(cls.contentpack)
        cls.items = [r["item_id"] for r in cp.execute(
            "SELECT item_id FROM learning_item ORDER BY item_id LIMIT 4").fetchall()]
        cls.textbook_id = cp.execute("SELECT textbook_id FROM learning_item LIMIT 1").fetchone()["textbook_id"]
        cp.close()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def setUp(self):
        self.w = svc.connect_learning_db(self.tmp_db)     # 写入（播种测试数据）
        self.r = pool.connect_learning_db(self.tmp_db)    # 只读（被测试服务）

    def tearDown(self):
        self.r.close()
        self.w.close()

    # ---- helpers -------------------------------------------------------
    def _learner(self, name="池测试"):
        return svc.create_learner(self.w, name)["learner_id"]

    def _task(self, learner_id, items=None, textbook_id=None, kind="learn"):
        return svc.create_task(self.w, learner_id, kind, items or [self.items[0]],
                               textbook_id=textbook_id or self.textbook_id)["task_id"]

    def _rec(self, learner_id, task_id, item_id, result, activity="spell", at=None, raw=None):
        return svc.record_learning_event(self.w, learner_id, task_id, item_id, activity,
                                         result=result, response_raw=raw, created_at=at)

    def _pool(self, learner_id):
        return pool.list_current_issue_pool(self.r, learner_id, contentpack_path=self.contentpack)

    # ---- 1. 空集合 -----------------------------------------------------
    def test_1_empty_pool(self):
        learner = self._learner()
        self.assertEqual(self._pool(learner), [])
        summary = pool.summarize_pool(self.r, learner, contentpack_path=self.contentpack)
        self.assertEqual((summary["total"], summary["has_data"]), (0, False))

    # ---- 2. 当前错误 ---------------------------------------------------
    def test_2_current_error(self):
        learner = self._learner()
        task = self._task(learner, [self.items[0]])
        self._rec(learner, task, self.items[0], "incorrect")
        got = self._pool(learner)
        self.assertEqual(len(got), 1)
        item = got[0]
        self.assertEqual(item["issue_type"], "current_error")
        self.assertEqual(item["priority_score"], 2)
        self.assertEqual(item["last_judged_result"], "incorrect")
        self.assertEqual(item["knowledge_id"], self.items[0])
        self.assertTrue(item["knowledge_name"])            # 来自 contentpack（只读）
        self.assertIn(item["resource_type"], ("vocabulary", "phrase", "sentence_pattern"))
        self.assertEqual(item["textbook_id"], self.textbook_id)
        self.assertEqual(item["data_basis"]["source"], "learning_record")

    # ---- 3. 历史错误已被纠正 → 出池 ------------------------------------
    def test_3_corrected_history_not_in_pool(self):
        learner = self._learner()
        task = self._task(learner, [self.items[0]])
        self._rec(learner, task, self.items[0], "incorrect", at="2026-09-12T10:00:00+08:00")
        self.assertEqual(len(self._pool(learner)), 1)
        self._rec(learner, task, self.items[0], "correct", at="2026-09-12T11:00:00+08:00")
        self.assertEqual(self._pool(learner), [], "correct 之后必须退出当前池")
        # 历史记录仍永久保留（两条都在）
        recs = svc.list_records(self.w, learner_id=learner, item_id=self.items[0])
        self.assertEqual(len(recs), 2)
        self.assertEqual([r["result"] for r in recs], ["incorrect", "correct"])
        # correct 之后再次 incorrect → 重新入池
        self._rec(learner, task, self.items[0], "incorrect", at="2026-09-12T12:00:00+08:00")
        self.assertEqual(len(self._pool(learner)), 1)

    # ---- 4. AI Training miss 语义（按结果入池，无独立 AI 通道） ----------
    def test_4_ai_training_miss_semantics(self):
        learner = self._learner()
        task = self._task(learner, [self.items[1]])
        # 未来 AI Training 产生的 miss，本质仍是一条真实学习行为记录（result=incorrect）
        self._rec(learner, task, self.items[1], "incorrect", activity="produce")
        got = self._pool(learner)
        self.assertEqual([x["item_id"] for x in got], [self.items[1]])
        self.assertEqual(got[0]["issue_type"], "current_error")
        # 服务不依赖任何 AI 通道（无 AI 特有的 source/字段）
        self.assertNotIn("ai", [k.lower() for k in got[0].keys()])
        # 生成记录不会伪造普通历史错误：Record 只有一条，且 result 由真实调用给出
        self.assertEqual(len(svc.list_records(self.w, learner_id=learner)), 1)

    # ---- 5. priority_score 与排序 --------------------------------------
    def test_5_priority_score_and_ordering(self):
        learner = self._learner()
        task = self._task(learner, [self.items[0], self.items[1]], kind="learn")
        self._rec(learner, task, self.items[0], "partial", at="2026-09-12T09:00:00+08:00")
        self._rec(learner, task, self.items[1], "incorrect", at="2026-09-12T08:00:00+08:00")
        got = self._pool(learner)
        self.assertEqual([x["item_id"] for x in got], [self.items[1], self.items[0]])
        self.assertEqual([x["priority_score"] for x in got], [2, 1])
        self.assertTrue(got[0]["priority_score"] > got[1]["priority_score"])

    # ---- 6. 学习者 / 教材 隔离 -----------------------------------------
    def test_6_learner_and_textbook_isolation(self):
        a, b = self._learner("孩子A"), self._learner("孩子B")
        ta = self._task(a, [self.items[0]])
        tb = self._task(b, [self.items[1]])
        self._rec(a, ta, self.items[0], "incorrect")
        self._rec(b, tb, self.items[1], "incorrect")
        pa, pb = self._pool(a), self._pool(b)
        self.assertEqual([x["item_id"] for x in pa], [self.items[0]])
        self.assertEqual([x["item_id"] for x in pb], [self.items[1]])
        # 教材过滤：不存在的 textbook_id → 空
        self.assertEqual(pool.list_current_issue_pool(self.r, a, textbook_id="NOT-A-TEXTBOOK",
                                                      contentpack_path=self.contentpack), [])
        self.assertEqual(len(pool.list_current_issue_pool(self.r, a, textbook_id=self.textbook_id,
                                                          contentpack_path=self.contentpack)), 1)

    # ---- 7. 查询不写库 --------------------------------------------------
    def test_7_query_performs_no_write(self):
        learner = self._learner()
        task = self._task(learner, [self.items[0]])
        self._rec(learner, task, self.items[0], "incorrect")
        before_hash = sha256_file(self.tmp_db)
        before_changes = self.r.total_changes
        for _ in range(3):
            pool.list_current_issue_pool(self.r, learner, contentpack_path=self.contentpack)
            pool.summarize_pool(self.r, learner, contentpack_path=self.contentpack)
            pool.get_item_pool_status(self.r, learner, self.items[0], contentpack_path=self.contentpack)
        self.assertEqual(self.r.total_changes, before_changes, "只读查询不得产生任何写入")
        self.assertEqual(sha256_file(self.tmp_db), before_hash, "查询前后数据库文件必须一致")

    # ---- 8. 无 AI 调用 --------------------------------------------------
    def test_8_no_ai_or_network(self):
        src = (HERE / "resource_pool_service.py").read_text(encoding="utf-8").lower()
        forbidden = ["openai", "deepseek", "ollama", "anthropic", "requests.", "urllib",
                     "http.client", "socket", "transformers", "torch", "tensorflow"]
        self.assertEqual([t for t in forbidden if t in src], [])
        # 只检查 SQL 写语句形态（docstring 中的“无 INSERT / UPDATE / DELETE”说明文字不算）
        for kw in ("insert into", "update learning_", "update mastery_state", "update learner",
                   "delete from", "drop table", "alter table", "create table"):
            self.assertNotIn(kw, src, "只读服务不得包含写操作：%s" % kw)

    # ---- 9. 排序稳定 ----------------------------------------------------
    def test_9_stable_ordering(self):
        learner = self._learner()
        task = self._task(learner, [self.items[0], self.items[1], self.items[2]])
        self._rec(learner, task, self.items[0], "partial", at="2026-09-12T09:00:00+08:00")
        self._rec(learner, task, self.items[1], "incorrect", at="2026-09-12T09:00:00+08:00")
        self._rec(learner, task, self.items[2], "incorrect", at="2026-09-12T07:00:00+08:00")
        first = [x["item_id"] for x in self._pool(learner)]
        for _ in range(5):
            self.assertEqual([x["item_id"] for x in self._pool(learner)], first)
        # 同为 incorrect：时间新者在前；时间相同则 item_id 升序
        self.assertEqual(first[0], self.items[1])
        self.assertEqual(first[1], self.items[2])
        self.assertEqual(first[2], self.items[0])

    # ---- 10. 正式库 / 教材库不被污染 ------------------------------------
    def test_10_official_dbs_untouched(self):
        self.assertEqual(sha256_file(self.official_db), self.official_sha)
        self.assertEqual(sha256_file(self.contentpack), self.contentpack_sha)
        conn = sqlite3.connect("file:%s?mode=ro" % self.official_db.as_posix(), uri=True)
        rows = {t: conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
                for t in ("learner", "learning_task", "task_item", "learning_record", "mastery_state")}
        conn.close()
        expected = {t: OFFICIAL_DB_COUNTS[t] for t in rows}
        self.assertEqual(rows, expected,
                         "正式 learning.db 的真实学习数据不得被修改或删除")


if __name__ == "__main__":
    unittest.main(verbosity=2)
