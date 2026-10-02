#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P1-07-C1 最小学习会话服务测试（stdlib unittest，无新依赖）

覆盖任务书 §十二 的 25 项：Session 基础 / Session↔Task / 生命周期 / 数据完整性 /
学习闭环（Session → Task → TaskItem → Record → MasteryState → 当前错误/薄弱池）/ 安全。

使用隔离临时数据库（正式 learning.db 的副本）+ 只读真实 contentpack：
  - 正式 learning.db 不被污染
  - contentpack 不发生写入
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
sys.dont_write_bytecode = True

import learning_service as svc          # noqa: E402
import resource_pool_service as pool     # noqa: E402
import session_service as ses            # noqa: E402


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


class SessionServiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.official_db = svc.DEFAULT_LEARNING_DB
        cls.official_sha = sha256_file(cls.official_db)
        cls.contentpack = svc.DEFAULT_CONTENTPACK_DB
        cls.contentpack_sha = sha256_file(cls.contentpack)
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="zhixue_p107c1_"))
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
        self.c = ses.connect_learning_db(self.tmp_db)

    def tearDown(self):
        self.c.close()

    # ---- helpers --------------------------------------------------------
    def _learner(self, name="会话测试"):
        return svc.create_learner(self.c, name)["learner_id"]

    def _session(self, learner_id, items=None, entry_point="vocabulary", **kw):
        if items is None:
            items = [self.items[0]]
        return ses.create_learning_session(self.c, learner_id, entry_point,
                                           list(items),
                                           textbook_id=kw.pop("textbook_id", self.textbook_id),
                                           contentpack_path=self.contentpack, **kw)

    # ---- Session 基础（1–5）---------------------------------------------
    def test_01_create_session_and_basic_fields(self):
        learner = self._learner()
        session = self._session(learner, [self.items[0], self.items[1]], entry_point="unit")
        self.assertTrue(session["session_id"].startswith("S"))          # 1 创建成功
        self.assertEqual(session["learner_id"], learner)                # 2 learner_id
        self.assertEqual(session["entry_point"], "unit")                # 3 entry_point
        self.assertTrue(session["started_at"])                          # 4 started_at
        self.assertIsNone(session["ended_at"])                          # 5 ended_at 初始为空

    # ---- Session / Task（6–8）------------------------------------------
    def test_02_session_task_link_and_items(self):
        learner = self._learner()
        session = self._session(learner, [self.items[0], self.items[1]])
        task = ses.get_session_task(self.c, session["session_id"], learner)
        self.assertEqual(task["task_id"], session["task_id"])           # 6 正确关联 Task
        self.assertEqual(task["learner_id"], learner)
        self.assertEqual(task["status"], "active")
        self.assertEqual(task["task_kind"], "learn")
        self.assertEqual(task["textbook_id"], self.textbook_id)
        items = ses.list_session_items(self.c, session["session_id"], learner)
        self.assertEqual([i["item_id"] for i in items], [self.items[0], self.items[1]])   # 7
        self.assertEqual([i["ordinal"] for i in items], [1, 2])

    def test_03_cross_learner_session_isolation(self):
        a, b = self._learner("孩子A"), self._learner("孩子B")
        session = self._session(a)
        self.assertEqual(ses.get_learning_session(self.c, session["session_id"], a)["learner_id"], a)
        for call in (lambda: ses.get_learning_session(self.c, session["session_id"], b),
                     lambda: ses.get_session_task(self.c, session["session_id"], b),
                     lambda: ses.end_learning_session(self.c, session["session_id"], b),
                     lambda: ses.list_session_items(self.c, session["session_id"], b)):
            with self.assertRaises(svc.ValidationError):                 # 8 跨 learner 拒绝
                call()
        self.assertEqual(len(ses.list_learning_sessions(self.c, a)), 1)
        self.assertEqual(ses.list_learning_sessions(self.c, b), [])
        # 正式库与临时库均未受影响（孩子A 的会话仍为未结束）
        self.assertIsNone(ses.get_learning_session(self.c, session["session_id"], a)["ended_at"])

    # ---- 生命周期（9–12）------------------------------------------------
    def test_04_end_session_lifecycle(self):
        learner = self._learner()
        session = self._session(learner)
        ended = ses.end_learning_session(self.c, session["session_id"], learner)   # 9
        self.assertIsNotNone(ended["ended_at"])                                    # 10
        self.assertTrue(ended["ended_at"])
        with self.assertRaises(svc.ConflictError):                                 # 11 不能重复结束
            ses.end_learning_session(self.c, session["session_id"], learner)
        with self.assertRaises(svc.NotFoundError):                                 # 12 未知 session
            ses.get_learning_session(self.c, "S_NOT_EXIST")
        with self.assertRaises(svc.NotFoundError):
            ses.end_learning_session(self.c, "S_NOT_EXIST", learner)

    # ---- 数据完整性（13–17）---------------------------------------------
    def test_05_validation_rules(self):
        learner = self._learner()
        with self.assertRaises(svc.ValidationError):                  # 13 item_ids 为空
            self._session(learner, items=[])
        with self.assertRaises(svc.ValidationError):                  # 14 非法 entry_point
            self._session(learner, entry_point="grammar")
        with self.assertRaises(svc.NotFoundError):                    # 15 learner 不存在
            self._session("L_NOT_EXIST")
        with self.assertRaises(svc.ValidationError):                  # 16 textbook/item 不匹配
            self._session(learner, textbook_id="NOT-A-TEXTBOOK")
        with self.assertRaises(svc.NotFoundError):                    # item 不存在
            self._session(learner, items=["FLTRP-EN-7A-2022CUR:V:NOPE"])
        # 以上失败均未留下 Session 或 Task
        self.assertEqual(ses.list_learning_sessions(self.c, learner), [])
        self.assertEqual(self.c.execute(
            "SELECT COUNT(*) FROM learning_task WHERE learner_id=?", (learner,)).fetchone()[0], 0)

    def test_06_no_orphan_session_or_task_on_failure(self):
        learner = self._learner()
        sid = "S_FIXED_%s" % learner[-6:]
        before = (self.c.execute("SELECT COUNT(*) FROM learning_session").fetchone()[0],
                  self.c.execute("SELECT COUNT(*) FROM learning_task").fetchone()[0],
                  self.c.execute("SELECT COUNT(*) FROM task_item").fetchone()[0])
        first = self._session(learner, session_id=sid)                # 先占用一个 session_id
        self.assertEqual(first["session_id"], sid)
        after_first = (self.c.execute("SELECT COUNT(*) FROM learning_session").fetchone()[0],
                       self.c.execute("SELECT COUNT(*) FROM learning_task").fetchone()[0],
                       self.c.execute("SELECT COUNT(*) FROM task_item").fetchone()[0])
        self.assertEqual(tuple(a - b for a, b in zip(after_first, before)), (1, 1, 1))
        with self.assertRaises(sqlite3.IntegrityError):               # 17 Session 插入失败
            self._session(learner, session_id=sid)
        # 补偿清理后：不留下孤立 Task / TaskItem
        after_fail = (self.c.execute("SELECT COUNT(*) FROM learning_session").fetchone()[0],
                      self.c.execute("SELECT COUNT(*) FROM learning_task").fetchone()[0],
                      self.c.execute("SELECT COUNT(*) FROM task_item").fetchone()[0])
        self.assertEqual(after_fail, after_first, "失败的创建不得留下 Session/Task/TaskItem")

    # ---- 学习闭环（18–21）-----------------------------------------------
    def test_07_full_learning_loop(self):
        learner = self._learner()
        session = self._session(learner, [self.items[0], self.items[1]], entry_point="reading")

        # 显式给定不同时间戳，避免依赖“同一秒内多条记录”的排序细节
        # （C2-A 的“最近一条”在同秒时以随机 record_id 作为 tie-break，属已知限制，见实施报告 NOTE）
        out = ses.record_session_event(self.c, session["session_id"], self.items[0], "spell",
                                       result="incorrect", response_raw="peacful",
                                       created_at="2026-09-12T10:00:00+08:00",
                                       contentpack_path=self.contentpack)            # 18 委托
        record, mastery = out["record"], out["mastery"]                              # 19 Record 产生
        self.assertEqual(record["task_id"], session["task_id"])
        self.assertEqual(record["activity_type"], "spell")
        self.assertEqual(record["result"], "incorrect")
        self.assertEqual(record["attempt_no"], 1)
        self.assertEqual(mastery["evidence_count"], 1)                               # 20 Mastery 更新
        self.assertEqual(mastery["correct_count"], 0)
        self.assertEqual(mastery["last_result"], "incorrect")

        pool_before = pool.list_current_issue_pool(self.c, learner, contentpack_path=self.contentpack)
        self.assertIn(self.items[0], [x["item_id"] for x in pool_before])            # 21 池反映
        self.assertEqual(pool_before[0]["issue_type"], "current_error")

        ses.record_session_event(self.c, session["session_id"], self.items[0], "spell",
                                 result="correct", created_at="2026-09-12T10:00:05+08:00",
                                 contentpack_path=self.contentpack)
        m2 = svc.get_mastery(self.c, learner, self.items[0])
        self.assertEqual(m2["correct_count"], 1)
        pool_after = pool.list_current_issue_pool(self.c, learner, contentpack_path=self.contentpack)
        self.assertNotIn(self.items[0], [x["item_id"] for x in pool_after])          # 答对后出池
        r2 = svc.list_records(self.c, learner_id=learner, item_id=self.items[0])
        self.assertEqual([r["attempt_no"] for r in r2], [1, 2])                      # 历史保留

        ended = ses.end_learning_session(self.c, session["session_id"], learner)
        self.assertTrue(ended["ended_at"])

    # ---- 安全（22–25）---------------------------------------------------
    def test_08_no_ai_no_network_no_writes_to_contentpack(self):
        src = (HERE / "session_service.py").read_text(encoding="utf-8").lower()
        forbidden = ["openai", "deepseek", "ollama", "anthropic", "requests.", "urllib",
                     "http.client", "socket", "transformers", "torch", "tensorflow"]
        self.assertEqual([t for t in forbidden if t in src], [])         # 23 AI calls = 0 / 24 网络 = 0
        for kw in ("insert into learning_item", "update learning_item", "delete from learning_item",
                   "insert into content_block", "update content_block"):
            self.assertNotIn(kw, src)
        self.assertEqual(sha256_file(self.contentpack), self.contentpack_sha)   # 25 contentpack 未写入

    def test_09_official_learning_db_untouched(self):
        self.assertEqual(sha256_file(self.official_db), self.official_sha)      # 22 未污染正式库
        conn = sqlite3.connect("file:%s?mode=ro" % self.official_db.as_posix(), uri=True)
        rows = {t: conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
                for t in ("learner", "learning_session", "learning_task", "task_item",
                          "learning_record", "mastery_state")}
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        conn.close()
        self.assertEqual(rows, OFFICIAL_DB_COUNTS,
                         "正式 learning.db 的真实学习数据不得被修改或删除")
        self.assertEqual(version, 2, "正式 learning.db 应已迁移到 v2（learning_session）")


if __name__ == "__main__":
    unittest.main(verbosity=2)
