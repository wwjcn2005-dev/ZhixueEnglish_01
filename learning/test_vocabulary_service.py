#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P1-09-C1 Vocabulary 最小学习消费链路测试（stdlib unittest，无新依赖）

覆盖 P1-09-C1 §十 的 9 组检查：核心 Vocabulary 全链路 / 非核心拒绝 / study /
practice（correct·incorrect·partial）/ learner 隔离 / 数据库完整性 /
contentpack 未修改 / AI=0 / 网络=0。

隔离临时数据库 + 只读真实 contentpack；时间戳显式不同秒（规避 C2-A 同秒 tie-break 既有问题）。
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

import activity_service as act          # noqa: E402
import learning_service as svc          # noqa: E402
import resource_pool_service as pool    # noqa: E402
import session_service as ses           # noqa: E402
import vocabulary_service as voc        # noqa: E402


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


class VocabularyChainTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.official_db = svc.DEFAULT_LEARNING_DB
        cls.official_sha = sha256_file(cls.official_db)
        cls.contentpack = svc.DEFAULT_CONTENTPACK_DB
        cls.contentpack_sha = sha256_file(cls.contentpack)
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="zhixue_p109c1_"))
        cls.tmp_db = cls.tmpdir / "learning_test.db"
        shutil.copyfile(cls.official_db, cls.tmp_db)
        cp = svc.connect_contentpack_db(cls.contentpack)
        cls.core = cp.execute("SELECT item_id FROM learning_item WHERE item_type='vocabulary' "
                              "AND learning_requirement='CORE' ORDER BY item_id LIMIT 1").fetchone()["item_id"]
        cls.core2 = cp.execute("SELECT item_id FROM learning_item WHERE item_type='vocabulary' "
                               "AND learning_requirement='CORE' ORDER BY item_id LIMIT 1 OFFSET 1").fetchone()["item_id"]
        cls.recognition = cp.execute("SELECT item_id FROM learning_item WHERE item_type='vocabulary' "
                                     "AND learning_requirement='RECOGNITION' ORDER BY item_id LIMIT 1").fetchone()["item_id"]
        cls.needs_review = cp.execute("SELECT item_id FROM learning_item WHERE item_type='vocabulary' "
                                      "AND learning_requirement='NEED_REVIEW' LIMIT 1").fetchone()
        cls.phrase = cp.execute("SELECT item_id FROM learning_item WHERE item_type='phrase' "
                                "ORDER BY item_id LIMIT 1").fetchone()["item_id"]
        cp.close()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def setUp(self):
        self.c = voc.svc.connect_learning_db(self.tmp_db)
        self.learner = svc.create_learner(self.c, "英语学习者")["learner_id"]

    def tearDown(self):
        self.c.close()

    def _t(self, hhmmss):
        return "2026-09-12T%s+08:00" % hhmmss

    # ---- 1. 核心 Vocabulary 全链路 --------------------------------------
    def test_01_core_vocabulary_full_chain(self):
        v = voc.get_vocabulary(self.core, self.contentpack)
        self.assertTrue(v["is_core_vocabulary"])                 # 可解析
        self.assertEqual(v["learning_requirement"], "CORE")
        self.assertEqual(v["textbook_emphasis"], "BOLD")
        self.assertTrue(v["source_refs"] and v["source_refs"][0]["pdf_page"])
        self.assertTrue(v["trace"]["rule"])

        started = voc.start_vocabulary_study(self.c, self.learner, self.core,
                                             contentpack_path=self.contentpack)
        session, task, activity = started["session"], started["task"], started["activity"]
        self.assertEqual(session["entry_point"], "vocabulary")    # Session
        self.assertEqual(session["learner_id"], self.learner)
        self.assertEqual(task["task_id"], session["task_id"])     # Task
        self.assertEqual(task["textbook_id"], v["textbook_id"])
        items = ses.list_session_items(self.c, session["session_id"], self.learner)   # TaskItem
        self.assertEqual([i["item_id"] for i in items], [self.core])
        self.assertEqual(activity["item_id"], self.core)          # LearningActivity
        self.assertEqual(activity["resource_type"], "vocabulary")
        self.assertEqual(activity["task_id"], task["task_id"])

        out = voc.record_vocabulary_study(self.c, session["session_id"], self.core,
                                          learner_id=self.learner, created_at=self._t("09:00:00"),
                                          contentpack_path=self.contentpack)
        rec = out["record"]                                       # LearningRecord
        self.assertEqual(rec["activity_type"], "study")
        self.assertEqual(rec["result"], "done")
        self.assertEqual(rec["item_id"], self.core)
        self.assertEqual(rec["attempt_no"], 1)
        self.assertEqual(svc.get_mastery(self.c, self.learner, self.core)["evidence_count"], 1)
        # study 不进入当前问题池
        self.assertEqual(pool.list_current_issue_pool(self.c, self.learner,
                                                      contentpack_path=self.contentpack), [])

    # ---- 2. 非核心 Vocabulary -------------------------------------------
    def test_02_non_core_rejected(self):
        r = voc.get_vocabulary(self.recognition, self.contentpack)
        self.assertFalse(r["is_core_vocabulary"])
        self.assertEqual(r["learning_requirement"], "RECOGNITION")
        self.assertEqual(r["textbook_emphasis"], "PLAIN")
        with self.assertRaises(svc.ValidationError):              # 不允许进入核心链路
            voc.require_core_vocabulary(self.recognition, self.contentpack)
        with self.assertRaises(svc.ValidationError):
            voc.start_vocabulary_study(self.c, self.learner, self.recognition,
                                       contentpack_path=self.contentpack)
        if self.needs_review:                                     # NEED_REVIEW 同样不允许
            with self.assertRaises(svc.ValidationError):
                voc.require_core_vocabulary(self.needs_review["item_id"], self.contentpack)
        # 非核心资源未产生任何学习记录
        self.assertEqual(svc.list_records(self.c, learner_id=self.learner), [])
        self.assertEqual(ses.list_learning_sessions(self.c, self.learner), [])
        self.assertEqual(self.c.execute(
            "SELECT COUNT(*) FROM task_item WHERE item_id=?", (self.recognition,)).fetchone()[0], 0)
        # 非 Vocabulary 资源也被拒绝
        with self.assertRaises(svc.ValidationError):
            voc.get_vocabulary(self.phrase, self.contentpack)
        with self.assertRaises(svc.NotFoundError):
            voc.get_vocabulary("FLTRP-EN-7A-2022CUR:V:NOT_EXIST", self.contentpack)

    # ---- 3. study 语义 ---------------------------------------------------
    def test_03_study_result_semantics(self):
        started = voc.start_vocabulary_study(self.c, self.learner, self.core,
                                             contentpack_path=self.contentpack)
        sid = started["session"]["session_id"]
        d = voc.record_vocabulary_study(self.c, sid, self.core, learner_id=self.learner,
                                        created_at=self._t("09:10:00"), contentpack_path=self.contentpack)
        self.assertEqual(d["record"]["result"], "done")
        s = voc.record_vocabulary_study(self.c, sid, self.core, learner_id=self.learner,
                                        result="skipped", created_at=self._t("09:10:05"),
                                        contentpack_path=self.contentpack)
        self.assertEqual(s["record"]["result"], "skipped")
        for bad in ("correct", "incorrect", "partial"):
            with self.assertRaises(svc.ValidationError):          # study 不接受对错结果
                voc.record_vocabulary_study(self.c, sid, self.core, learner_id=self.learner,
                                            result=bad, contentpack_path=self.contentpack)
        self.assertEqual(pool.list_current_issue_pool(self.c, self.learner,
                                                      contentpack_path=self.contentpack), [])

    # ---- 4. practice 语义 -----------------------------------------------
    def test_04_practice_results(self):
        started = voc.start_vocabulary_study(self.c, self.learner, self.core,
                                             contentpack_path=self.contentpack)
        sid = started["session"]["session_id"]
        inc = voc.record_vocabulary_practice(self.c, sid, self.core, result="incorrect",
                                             learner_id=self.learner, created_at=self._t("09:20:00"),
                                             contentpack_path=self.contentpack)["record"]
        par = voc.record_vocabulary_practice(self.c, sid, self.core, result="partial",
                                             learner_id=self.learner, created_at=self._t("09:20:05"),
                                             contentpack_path=self.contentpack)["record"]
        cor = voc.record_vocabulary_practice(self.c, sid, self.core, result="correct",
                                             learner_id=self.learner, created_at=self._t("09:20:10"),
                                             contentpack_path=self.contentpack)["record"]
        self.assertEqual([inc["result"], par["result"], cor["result"]],
                         ["incorrect", "partial", "correct"])
        self.assertEqual([inc["activity_type"], cor["activity_type"]], ["practice", "practice"])
        self.assertEqual([inc["attempt_no"], par["attempt_no"], cor["attempt_no"]], [1, 2, 3])
        m = svc.get_mastery(self.c, self.learner, self.core)
        self.assertEqual((m["evidence_count"], m["correct_count"], m["last_result"]), (3, 1, "correct"))
        # 最后一条参与判断为 correct → 退出当前池；历史 3 条全部保留
        self.assertEqual(pool.list_current_issue_pool(self.c, self.learner,
                                                      contentpack_path=self.contentpack), [])
        self.assertEqual([r["result"] for r in svc.list_records(self.c, learner_id=self.learner)],
                         ["incorrect", "partial", "correct"])

    def test_05_practice_partial_is_current_weak(self):
        started = voc.start_vocabulary_study(self.c, self.learner, self.core2,
                                             contentpack_path=self.contentpack)
        sid = started["session"]["session_id"]
        voc.record_vocabulary_practice(self.c, sid, self.core2, result="partial",
                                       learner_id=self.learner, created_at=self._t("09:30:00"),
                                       contentpack_path=self.contentpack)
        p = pool.list_current_issue_pool(self.c, self.learner, contentpack_path=self.contentpack)
        self.assertEqual([(x["item_id"], x["issue_type"]) for x in p], [(self.core2, "current_weak")])
        # incorrect 覆盖后转为 current_error
        voc.record_vocabulary_practice(self.c, sid, self.core2, result="incorrect",
                                       learner_id=self.learner, created_at=self._t("09:30:05"),
                                       contentpack_path=self.contentpack)
        p2 = pool.list_current_issue_pool(self.c, self.learner, contentpack_path=self.contentpack)
        self.assertEqual([(x["item_id"], x["issue_type"]) for x in p2], [(self.core2, "current_error")])

    # ---- 5. learner 隔离 ------------------------------------------------
    def test_06_learner_isolation(self):
        other = svc.create_learner(self.c, "另一个孩子")["learner_id"]
        started = voc.start_vocabulary_study(self.c, self.learner, self.core,
                                             contentpack_path=self.contentpack)
        sid = started["session"]["session_id"]
        voc.record_vocabulary_study(self.c, sid, self.core, learner_id=self.learner,
                                    created_at=self._t("09:40:00"), contentpack_path=self.contentpack)
        voc.record_vocabulary_practice(self.c, sid, self.core, result="incorrect",
                                       learner_id=self.learner, created_at=self._t("09:40:05"),
                                       contentpack_path=self.contentpack)
        self.assertEqual(len(svc.list_records(self.c, learner_id=self.learner)), 2)
        self.assertEqual(svc.list_records(self.c, learner_id=other), [])          # B 无记录
        self.assertIsNone(svc.get_mastery(self.c, other, self.core))              # B 无掌握状态
        self.assertEqual(pool.list_current_issue_pool(self.c, other,
                                                      contentpack_path=self.contentpack), [])
        # 另一个 learner 不能操作该 session
        with self.assertRaises(svc.ValidationError):
            voc.record_vocabulary_study(self.c, sid, self.core, learner_id=other,
                                        contentpack_path=self.contentpack)

    # ---- 6–9. 数据库 / contentpack / AI / 网络 ---------------------------
    def test_07_security_and_integrity(self):
        src = (HERE / "vocabulary_service.py").read_text(encoding="utf-8").lower()
        forbidden = ["openai", "deepseek", "ollama", "anthropic", "requests.", "urllib",
                     "http.client", "socket", "transformers", "torch", "tensorflow"]
        self.assertEqual([t for t in forbidden if t in src], [])          # AI=0 / 网络=0
        for kw in ("insert into learning_item", "update learning_item", "delete from learning_item",
                   "insert into content_block", "update content_block"):
            self.assertNotIn(kw, src)
        self.assertEqual(sha256_file(self.contentpack), self.contentpack_sha)   # contentpack 未改
        self.assertEqual(sha256_file(self.official_db), self.official_sha)      # 正式库未污染

    def test_08_schema_unchanged_and_tables_clean(self):
        version = self.c.execute("PRAGMA user_version").fetchone()[0]
        tables = sorted(r[0] for r in self.c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))
        self.assertEqual(version, 2, "P1-09-C1 不改变 schema")
        self.assertEqual(tables, ["learner", "learning_record", "learning_session",
                                  "learning_task", "mastery_state", "schema_migration", "task_item"])
        # 正式库业务表仍为 0 行
        conn = sqlite3.connect("file:%s?mode=ro" % self.official_db.as_posix(), uri=True)
        rows = {t: conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
                for t in ("learner", "learning_session", "learning_task", "task_item",
                          "learning_record", "mastery_state")}
        conn.close()
        self.assertEqual(rows, OFFICIAL_DB_COUNTS,
                         "正式 learning.db 的真实学习数据不得被修改或删除")


if __name__ == "__main__":
    unittest.main(verbosity=2)
