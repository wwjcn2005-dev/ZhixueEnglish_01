#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P1-06-C1 学习层最小业务服务测试（stdlib unittest，无新依赖）

测试使用**临时测试数据库**（正式 learning.db 的副本），测试结束即清理：
  - 不污染 structured/learning/learning.db
  - 不修改 contentpack v5（只读打开）

覆盖：A 创建 Learner / B 创建 Task / C TaskItem / D Record / E Mastery /
      F attempt_no / G partial / H skipped / I NULL /
      J 事务回滚 / K completed 拒绝 / L dropped 拒绝 / M AI=0
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
sys.dont_write_bytecode = True          # 不产生 __pycache__（保持项目最小改动）

import learning_service as svc  # noqa: E402


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


class LearningServiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.official_learning_db = svc.DEFAULT_LEARNING_DB
        cls.official_learning_sha = sha256_file(cls.official_learning_db)
        cls.official_contentpack = svc.DEFAULT_CONTENTPACK_DB
        cls.contentpack_sha = sha256_file(cls.official_contentpack)
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="zhixue_c1_"))
        cls.tmp_db = cls.tmpdir / "learning_test.db"
        shutil.copyfile(cls.official_learning_db, cls.tmp_db)   # 只读复制正式库（空库）
        cp = svc.connect_contentpack_db(cls.official_contentpack)
        cls.items = [r["item_id"] for r in cp.execute(
            "SELECT item_id FROM learning_item ORDER BY item_id LIMIT 4").fetchall()]
        cls.textbook_id = cp.execute(
            "SELECT textbook_id FROM learning_item LIMIT 1").fetchone()["textbook_id"]
        cp.close()
        assert len(cls.items) >= 4, "需要至少 4 条教材资源用于测试"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def setUp(self):
        self.conn = svc.connect_learning_db(self.tmp_db)

    def tearDown(self):
        self.conn.close()

    # ---- helpers -------------------------------------------------------
    def _learner(self, name="测试学习者"):
        return svc.create_learner(self.conn, name)

    def _task(self, learner_id, items=None, kind="learn", textbook_id=None):
        return svc.create_task(self.conn, learner_id, kind, items or [self.items[0]],
                               textbook_id=textbook_id or self.textbook_id)

    # ---- A. Learner ----------------------------------------------------
    def test_A_create_learner(self):
        learner = self._learner("小明")
        self.assertTrue(learner["learner_id"].startswith("L"))
        self.assertEqual(learner["display_name"], "小明")
        self.assertEqual(learner["status"], "active")
        self.assertIsNone(learner["updated_at"])
        self.assertTrue(learner["created_at"])
        self.assertEqual(svc.get_learner(self.conn, learner["learner_id"])["display_name"], "小明")
        with self.assertRaises(svc.ValidationError):
            svc.create_learner(self.conn, "   ")
        with self.assertRaises(svc.NotFoundError):
            svc.get_learner(self.conn, "L_NOT_EXIST")

    # ---- B. Task -------------------------------------------------------
    def test_B_create_task(self):
        learner = self._learner()
        task = self._task(learner["learner_id"], [self.items[0], self.items[1]])
        self.assertEqual(task["status"], "active")
        self.assertEqual(task["task_kind"], "learn")
        self.assertEqual(task["textbook_id"], self.textbook_id)
        items = svc.list_task_items(self.conn, task["task_id"])
        self.assertEqual([i["item_id"] for i in items], [self.items[0], self.items[1]])
        self.assertEqual([i["ordinal"] for i in items], [1, 2])

        with self.assertRaises(svc.ValidationError):
            svc.create_task(self.conn, learner["learner_id"], "learn", [], textbook_id=self.textbook_id)
        with self.assertRaises(svc.ValidationError):
            svc.create_task(self.conn, learner["learner_id"], "practice", [self.items[0]],
                            textbook_id=self.textbook_id)
        with self.assertRaises(svc.NotFoundError):
            svc.create_task(self.conn, learner["learner_id"], "learn", [self.items[0]],
                            textbook_id="NOT-A-TEXTBOOK")
        with self.assertRaises(svc.NotFoundError):
            svc.create_task(self.conn, learner["learner_id"], "learn", ["FLTRP-EN-7A-2022CUR:V:不存在"],
                            textbook_id=self.textbook_id)
        with self.assertRaises(svc.NotFoundError):
            svc.create_task(self.conn, "L_NOT_EXIST", "learn", [self.items[0]],
                            textbook_id=self.textbook_id)

    # ---- C. TaskItem ---------------------------------------------------
    def test_C_task_item(self):
        learner = self._learner()
        task = self._task(learner["learner_id"], [self.items[0]])
        svc.add_task_item(self.conn, task["task_id"], self.items[2], ordinal=5)
        self.assertEqual(len(svc.list_task_items(self.conn, task["task_id"])), 2)
        with self.assertRaises(svc.ConflictError):
            svc.add_task_item(self.conn, task["task_id"], self.items[0])   # 重复
        self.assertEqual(svc.remove_task_item(self.conn, task["task_id"], self.items[2]), 1)
        self.assertEqual([i["item_id"] for i in svc.list_task_items(self.conn, task["task_id"])],
                         [self.items[0]])

    # ---- D/E. Record + Mastery ----------------------------------------
    def test_D_E_record_creates_record_and_mastery(self):
        learner = self._learner()
        task = self._task(learner["learner_id"], [self.items[0]])
        out = svc.record_learning_event(
            self.conn, learner["learner_id"], task["task_id"], self.items[0],
            "spell", result="correct", response_raw="peaceful")
        rec, mastery = out["record"], out["mastery"]
        self.assertEqual(rec["activity_type"], "spell")
        self.assertEqual(rec["result"], "correct")
        self.assertEqual(rec["attempt_no"], 1)
        self.assertEqual(rec["response_raw"], "peaceful")
        self.assertEqual(rec["hints_used"], 0)
        self.assertEqual(rec["textbook_id"], self.textbook_id)
        self.assertTrue(rec["snapshot_id"])                 # 自动填充当前 active 快照
        self.assertTrue(rec["created_at"])                   # 行为发生时间必填
        self.assertEqual(mastery["mastery_level"], "unknown")   # 不实现算法
        self.assertEqual(mastery["evidence_count"], 1)
        self.assertEqual(mastery["correct_count"], 1)
        self.assertEqual(mastery["last_result"], "correct")
        self.assertEqual(mastery["review_needed"], 0)
        self.assertEqual(len(svc.list_records(self.conn, learner_id=learner["learner_id"])), 1)

    # ---- F. attempt_no -------------------------------------------------
    def test_F_attempt_no_sequence(self):
        learner = self._learner()
        task = self._task(learner["learner_id"], [self.items[0]])
        r1 = svc.record_learning_event(self.conn, learner["learner_id"], task["task_id"],
                                       self.items[0], "spell", result="incorrect")["record"]
        r2 = svc.record_learning_event(self.conn, learner["learner_id"], task["task_id"],
                                       self.items[0], "spell", result="correct")["record"]
        self.assertEqual((r1["attempt_no"], r2["attempt_no"]), (1, 2))
        # 换 activity_type → 重新从 1
        r3 = svc.record_learning_event(self.conn, learner["learner_id"], task["task_id"],
                                       self.items[0], "read", result="done")["record"]
        self.assertEqual(r3["attempt_no"], 1)
        # 换 Task → 重新从 1
        task2 = self._task(learner["learner_id"], [self.items[0]])
        r4 = svc.record_learning_event(self.conn, learner["learner_id"], task2["task_id"],
                                       self.items[0], "spell", result="correct")["record"]
        self.assertEqual(r4["attempt_no"], 1)

    # ---- G. partial ----------------------------------------------------
    def test_G_partial_does_not_count_as_correct(self):
        learner = self._learner()
        task = self._task(learner["learner_id"], [self.items[0]])
        svc.record_learning_event(self.conn, learner["learner_id"], task["task_id"],
                                  self.items[0], "produce", result="correct")
        m = svc.record_learning_event(self.conn, learner["learner_id"], task["task_id"],
                                      self.items[0], "produce", result="partial")["mastery"]
        self.assertEqual(m["evidence_count"], 2)
        self.assertEqual(m["correct_count"], 1)          # partial 不计入 correct
        self.assertEqual(m["last_result"], "partial")

    # ---- H. skipped ----------------------------------------------------
    def test_H_skipped_does_not_update_mastery(self):
        learner = self._learner()
        task = self._task(learner["learner_id"], [self.items[0]])
        svc.record_learning_event(self.conn, learner["learner_id"], task["task_id"],
                                  self.items[0], "spell", result="incorrect")
        before = svc.get_mastery(self.conn, learner["learner_id"], self.items[0])
        out = svc.record_learning_event(self.conn, learner["learner_id"], task["task_id"],
                                        self.items[0], "spell", result="skipped")
        self.assertEqual(out["record"]["result"], "skipped")
        after = svc.get_mastery(self.conn, learner["learner_id"], self.items[0])
        self.assertEqual(after["evidence_count"], before["evidence_count"])
        self.assertEqual(after["correct_count"], before["correct_count"])
        self.assertEqual(after["last_result"], before["last_result"])
        self.assertEqual(after["last_practiced_at"], before["last_practiced_at"])

    # ---- I. NULL result ------------------------------------------------
    def test_I_null_result_does_not_update_mastery(self):
        learner = self._learner()
        task = self._task(learner["learner_id"], [self.items[0]])
        out = svc.record_learning_event(self.conn, learner["learner_id"], task["task_id"],
                                        self.items[0], "review", result=None)
        self.assertIsNone(out["record"]["result"])
        m = out["mastery"]
        self.assertEqual(m["evidence_count"], 0)
        self.assertEqual(m["correct_count"], 0)
        self.assertIsNone(m["last_result"])
        # 空字符串不落库（保存 NULL）
        out2 = svc.record_learning_event(self.conn, learner["learner_id"], task["task_id"],
                                         self.items[0], "read", result="done", response_raw="   ")
        self.assertIsNone(out2["record"]["response_raw"])

    # ---- J. 事务回滚 ----------------------------------------------------
    def test_J_transaction_rollback(self):
        learner = self._learner()
        task = self._task(learner["learner_id"], [self.items[0]])
        original = svc._upsert_mastery

        def boom(*args, **kwargs):
            raise RuntimeError("injected mastery failure")

        svc._upsert_mastery = boom
        try:
            with self.assertRaises(RuntimeError):
                svc.record_learning_event(self.conn, learner["learner_id"], task["task_id"],
                                          self.items[0], "spell", result="correct")
        finally:
            svc._upsert_mastery = original
        self.assertEqual(len(svc.list_records(self.conn, task_id=task["task_id"])), 0)
        self.assertIsNone(svc.get_mastery(self.conn, learner["learner_id"], self.items[0]))
        # 回滚后仍可正常记录
        out = svc.record_learning_event(self.conn, learner["learner_id"], task["task_id"],
                                        self.items[0], "spell", result="correct")
        self.assertEqual(out["record"]["attempt_no"], 1)

    # ---- K/L. completed / dropped 拒绝 ----------------------------------
    def test_K_completed_task_rejects_record(self):
        learner = self._learner()
        task = self._task(learner["learner_id"], [self.items[0]])
        done = svc.complete_task(self.conn, task["task_id"])
        self.assertEqual(done["status"], "completed")
        self.assertTrue(done["completed_at"])
        with self.assertRaises(svc.ConflictError):
            svc.record_learning_event(self.conn, learner["learner_id"], task["task_id"],
                                      self.items[0], "spell", result="correct")
        with self.assertRaises(svc.ConflictError):
            svc.add_task_item(self.conn, task["task_id"], self.items[1])
        with self.assertRaises(svc.ConflictError):
            svc.complete_task(self.conn, task["task_id"])     # 不可逆

    def test_L_dropped_task_rejects_record(self):
        learner = self._learner()
        task = self._task(learner["learner_id"], [self.items[0]])
        dropped = svc.drop_task(self.conn, task["task_id"])
        self.assertEqual(dropped["status"], "dropped")
        with self.assertRaises(svc.ConflictError):
            svc.record_learning_event(self.conn, learner["learner_id"], task["task_id"],
                                      self.items[0], "read", result="done")

    # ---- 其他业务校验 ---------------------------------------------------
    def test_validation_rules(self):
        learner = self._learner()
        other = self._learner("另一个孩子")
        task = self._task(learner["learner_id"], [self.items[0]])
        with self.assertRaises(svc.ValidationError):     # Task 不属于该 Learner
            svc.record_learning_event(self.conn, other["learner_id"], task["task_id"],
                                      self.items[0], "spell", result="correct")
        with self.assertRaises(svc.ValidationError):     # item 不在该 Task
            svc.record_learning_event(self.conn, learner["learner_id"], task["task_id"],
                                      self.items[1], "spell", result="correct")
        with self.assertRaises(svc.ValidationError):     # 非法 activity_type
            svc.record_learning_event(self.conn, learner["learner_id"], task["task_id"],
                                      self.items[0], "view", result="done")
        with self.assertRaises(svc.ValidationError):     # 非法 result
            svc.record_learning_event(self.conn, learner["learner_id"], task["task_id"],
                                      self.items[0], "spell", result="perfect")
        with self.assertRaises(svc.ValidationError):     # hints_used 非法
            svc.record_learning_event(self.conn, learner["learner_id"], task["task_id"],
                                      self.items[0], "spell", result="correct", hints_used=-1)

    # ---- M. AI = 0 -----------------------------------------------------
    def test_M_no_ai_or_network_dependency(self):
        src = (HERE / "learning_service.py").read_text(encoding="utf-8").lower()
        forbidden = ["openai", "deepseek", "ollama", "requests.", "urllib", "http.client",
                     "socket", "transformers", "torch", "tensorflow", "anthropic", "pytesseract"]
        hits = [token for token in forbidden if token in src]
        self.assertEqual(hits, [], "学习服务不得包含 AI / 网络依赖：%s" % hits)
        # append-only：不得存在 update / delete 的 Record 写入口（只允许文档中的说明文字）
        self.assertNotIn("def update_record", src)
        self.assertNotIn("def delete_record", src)
        self.assertNotIn("update learning_record", src)
        self.assertNotIn("delete from learning_record", src)

    # ---- 回归：正式库与教材库未被污染 ------------------------------------
    def test_regression_official_dbs_untouched(self):
        self.assertEqual(sha256_file(self.official_learning_db), self.official_learning_sha)
        self.assertEqual(sha256_file(self.official_contentpack), self.contentpack_sha)
        conn = sqlite3.connect("file:%s?mode=ro" % self.official_learning_db.as_posix(), uri=True)
        rows = {t: conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
                for t in ("learner", "learning_task", "task_item", "learning_record", "mastery_state")}
        conn.close()
        expected = {t: OFFICIAL_DB_COUNTS[t] for t in rows}
        self.assertEqual(rows, expected,
                         "正式 learning.db 的真实学习数据不得被修改或删除")


if __name__ == "__main__":
    unittest.main(verbosity=2)
