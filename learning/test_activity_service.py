#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P1-07-C2 LearningActivity 最小模型与消费接口测试（stdlib unittest，无新依赖）

覆盖 P1-07-C2 §十五 的 19 项：基础 1–4 / 数据关系 5–8 / 异常 9–12 /
回归 13–15（另两套测试单列运行）/ 安全 16–19。

使用隔离临时数据库（正式 learning.db 副本）+ 只读真实 contentpack。
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

import activity_service as act       # noqa: E402
import learning_service as svc        # noqa: E402


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


#: P2-1-C1：正式 learning.db 已包含真机真实学习数据，「业务表必须为 0 行」不再是有效基线；
#: 新的保护目标是"本次测试运行期间正式数据不得被修改或删除"。
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


class ActivityServiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.official_db = svc.DEFAULT_LEARNING_DB
        cls.official_sha = sha256_file(cls.official_db)
        cls.contentpack = svc.DEFAULT_CONTENTPACK_DB
        cls.contentpack_sha = sha256_file(cls.contentpack)
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="zhixue_p107c2_"))
        cls.tmp_db = cls.tmpdir / "learning_test.db"
        shutil.copyfile(cls.official_db, cls.tmp_db)
        cp = svc.connect_contentpack_db(cls.contentpack)
        cls.by_type = {}
        for t in act.RESOURCE_TYPES:
            row = cp.execute("SELECT item_id, textbook_id FROM learning_item WHERE item_type=? "
                             "ORDER BY item_id LIMIT 1", (t,)).fetchone()
            cls.by_type[t] = row["item_id"]
        cls.textbook_id = cp.execute("SELECT textbook_id FROM learning_item LIMIT 1").fetchone()["textbook_id"]
        cp.close()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def setUp(self):
        self.c = act.connect_learning_db(self.tmp_db)

    def tearDown(self):
        self.c.close()

    # ---- helpers --------------------------------------------------------
    def _task(self, items=None):
        learner = svc.create_learner(self.c, "活动测试")["learner_id"]
        items = items or [self.by_type["vocabulary"]]
        return svc.create_task(self.c, learner, "learn", items,
                               textbook_id=self.textbook_id)["task_id"]

    # ---- 基础（1–4）-----------------------------------------------------
    def test_01_resolve_activity_per_resource_type(self):
        for rtype, item_id in self.by_type.items():
            task = self._task([item_id])
            a = act.resolve_activity(self.c, task, item_id, contentpack_path=self.contentpack)
            self.assertEqual(a["resource_id"], item_id)          # 1 TaskItem 可解析出活动 + 2/3/4
            self.assertEqual(a["resource_type"], rtype)
            self.assertEqual(a["activity_type"], rtype)
            self.assertEqual(a["item_id"], item_id)
            self.assertEqual(a["task_id"], task)
            self.assertTrue(a["activity_id"].startswith(task))
            # 不复制教材正文/释义（投影中无文本字段）
            for k in ("canonical_text", "display_text", "meaning_zh", "text_raw", "text_normalized"):
                self.assertNotIn(k, a)

    # ---- 数据关系（5–8）-------------------------------------------------
    def test_02_activity_belongs_to_task_item(self):
        items = [self.by_type["vocabulary"], self.by_type["phrase"], self.by_type["sentence_pattern"]]
        task = self._task(items)
        acts = act.list_task_activities(self.c, task, contentpack_path=self.contentpack)
        self.assertEqual([a["item_id"] for a in acts], items)            # 5 与 TaskItem 对应（含顺序）
        self.assertEqual([a["ordinal"] for a in acts], [1, 2, 3])
        self.assertEqual([a["resource_id"] for a in acts], items)       # 6 resource_id
        self.assertEqual([a["resource_type"] for a in acts],
                         ["vocabulary", "phrase", "sentence_pattern"])   # 7 resource_type
        self.assertTrue(all(a["textbook_id"] == self.textbook_id for a in acts))   # 8 textbook_id
        for a in acts:
            self.assertEqual(a["activity_id"], "%s|%s" % (task, a["item_id"]))

    # ---- 异常（9–12）----------------------------------------------------
    def test_03_task_item_not_found(self):
        task = self._task()
        with self.assertRaises(svc.NotFoundError):            # 9 TaskItem 不存在
            act.resolve_activity(self.c, task, "FLTRP-EN-7A-2022CUR:V:NOT_IN_TASK",
                                 contentpack_path=self.contentpack)
        with self.assertRaises(svc.NotFoundError):            # 9 未知 task
            act.resolve_activity(self.c, "T_NOT_EXIST", self.by_type["vocabulary"],
                                 contentpack_path=self.contentpack)

    def test_04_resource_not_found(self):
        task = self._task()
        # 直接构造“TaskItem 存在但教材资源不存在”的情形（仅测试临时库）
        self.c.execute("INSERT INTO task_item(task_id, item_id, ordinal, created_at) VALUES(?,?,?,?)",
                       (task, "FLTRP-EN-7A-2022CUR:V:GHOST", 9, svc.now_iso()))
        with self.assertRaises(svc.NotFoundError):            # 10 resource 不存在
            act.resolve_activity(self.c, task, "FLTRP-EN-7A-2022CUR:V:GHOST",
                                 contentpack_path=self.contentpack)

    def test_05_invalid_resource_type_guard(self):
        for bad in ("question", "reading", "listening", "ai_activity", ""):
            with self.assertRaises(svc.ValidationError):      # 11 非法 resource_type
                act.check_resource_type(bad)
        for good in act.RESOURCE_TYPES:
            self.assertEqual(act.check_resource_type(good), good)

    def test_06_textbook_mismatch(self):
        task = self._task()
        self.c.execute("UPDATE learning_task SET textbook_id='OTHER-TEXTBOOK' WHERE task_id=?", (task,))
        with self.assertRaises(svc.ValidationError):          # 12 textbook 不一致（跨教材引用）
            act.resolve_activity(self.c, task, self.by_type["vocabulary"],
                                 contentpack_path=self.contentpack)

    # ---- 安全（16–19）---------------------------------------------------
    def test_07_no_ai_no_network_no_textbook_copy(self):
        src = (HERE / "activity_service.py").read_text(encoding="utf-8").lower()
        forbidden = ["openai", "deepseek", "ollama", "anthropic", "requests.", "urllib",
                     "http.client", "socket", "transformers", "torch", "tensorflow"]
        self.assertEqual([t for t in forbidden if t in src], [])          # 16 AI = 0 / 17 网络 = 0
        for kw in ("insert into", "update ", "delete from", "create table", "alter table"):
            self.assertNotIn(kw, src, "LearningActivity 投影服务必须只读")
        self.assertEqual(sha256_file(self.contentpack), self.contentpack_sha)   # 18 contentpack 不变

    def test_08_official_learning_db_untouched(self):
        self.assertEqual(sha256_file(self.official_db), self.official_sha)      # 19 正式库未污染
        conn = sqlite3.connect("file:%s?mode=ro" % self.official_db.as_posix(), uri=True)
        rows = {t: conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
                for t in ("learner", "learning_session", "learning_task", "task_item",
                          "learning_record", "mastery_state")}
        has_activity_table = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='learning_activity'").fetchone()[0]
        conn.close()
        self.assertEqual(rows, OFFICIAL_DB_COUNTS,
                         "正式 learning.db 的真实学习数据不得被修改或删除")
        self.assertEqual(has_activity_table, 0, "本阶段不得新增 learning_activity 表")

    # ---- 回归（13–15 由 run_all 统一运行，此处做进程内自检）-------------
    def test_09_no_schema_change_in_this_task(self):
        version = self.c.execute("PRAGMA user_version").fetchone()[0]
        tables = sorted(r[0] for r in self.c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))
        self.assertEqual(version, 2, "P1-07-C2 不改变 schema（仍为 P1-07-C1 的 v2）")
        self.assertEqual(len(tables), 7)
        self.assertNotIn("learning_activity", tables)


if __name__ == "__main__":
    unittest.main(verbosity=2)
