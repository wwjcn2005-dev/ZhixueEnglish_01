#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P1-08-C1 最小学习行为模型与记录协议测试（stdlib unittest，无新依赖）

覆盖 P1-08-C1 §十五 的 22 项：study/practice 记录、三类资源、attempt_no、
结果语义、浏览/查询不产生记录、Mastery 更新、C2-A 池联动、历史保留、
learner 隔离、AI/网络/contentpack/正式库安全。

使用隔离临时数据库 + 只读真实 contentpack；同一秒排序问题用显式不同时间戳规避（§十四）。
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

import activity_service as act        # noqa: E402
import behavior_service as beh        # noqa: E402
import learning_service as svc        # noqa: E402
import resource_pool_service as pool  # noqa: E402
import session_service as ses         # noqa: E402


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


class BehaviorServiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.official_db = svc.DEFAULT_LEARNING_DB
        cls.official_sha = sha256_file(cls.official_db)
        cls.contentpack = svc.DEFAULT_CONTENTPACK_DB
        cls.contentpack_sha = sha256_file(cls.contentpack)
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="zhixue_p108c1_"))
        cls.tmp_db = cls.tmpdir / "learning_test.db"
        shutil.copyfile(cls.official_db, cls.tmp_db)
        cp = svc.connect_contentpack_db(cls.contentpack)
        cls.by_type = {}
        for t in act.RESOURCE_TYPES:
            row = cp.execute("SELECT item_id FROM learning_item WHERE item_type=? "
                             "ORDER BY item_id LIMIT 1", (t,)).fetchone()
            cls.by_type[t] = row["item_id"]
        cls.textbook_id = cp.execute("SELECT textbook_id FROM learning_item LIMIT 1").fetchone()["textbook_id"]
        cp.close()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def setUp(self):
        self.c = beh.svc.connect_learning_db(self.tmp_db)
        self.learner = svc.create_learner(self.c, "行为测试")["learner_id"]

    def tearDown(self):
        self.c.close()

    # ---- helpers --------------------------------------------------------
    def _task(self, items=None):
        items = items or [self.by_type["vocabulary"]]
        return svc.create_task(self.c, self.learner, "learn", items,
                               textbook_id=self.textbook_id)["task_id"]

    def _t(self, hhmmss):
        return "2026-09-12T%s+08:00" % hhmmss

    # ---- 1–2 最小行为 ---------------------------------------------------
    def test_01_study_and_practice_produce_records(self):
        task = self._task()
        item = self.by_type["vocabulary"]
        r1 = beh.record_study(self.c, self.learner, task, item, result="done",
                              created_at=self._t("09:00:00"), contentpack_path=self.contentpack)
        r2 = beh.record_practice(self.c, self.learner, task, item, result="correct",
                                 created_at=self._t("09:00:05"), contentpack_path=self.contentpack)
        self.assertEqual(r1["record"]["activity_type"], "study")          # 1
        self.assertEqual(r2["record"]["activity_type"], "practice")       # 2
        self.assertEqual(beh.list_behaviors(), ("study", "practice"))
        self.assertEqual([r["result"] for r in (r1["record"], r2["record"])], ["done", "correct"])

    # ---- 3–5 三类资源 ---------------------------------------------------
    def test_02_all_resource_types_share_one_protocol(self):
        for rtype, item_id in self.by_type.items():
            task = self._task([item_id])
            out = beh.record_practice(self.c, self.learner, task, item_id, result="incorrect",
                                      created_at=self._t("09:10:00"), contentpack_path=self.contentpack)
            self.assertEqual(out["record"]["item_id"], item_id)            # 3/4/5 同一协议
            self.assertEqual(out["record"]["activity_type"], "practice")
            self.assertEqual(svc.get_task(self.c, task)["task_id"], task)

    # ---- 6 attempt_no ---------------------------------------------------
    def test_03_attempt_no_increments(self):
        task = self._task()
        item = self.by_type["vocabulary"]
        a = beh.record_practice(self.c, self.learner, task, item, result="incorrect",
                                created_at=self._t("09:20:00"), contentpack_path=self.contentpack)
        b = beh.record_practice(self.c, self.learner, task, item, result="correct",
                                created_at=self._t("09:20:05"), contentpack_path=self.contentpack)
        self.assertEqual([a["record"]["attempt_no"], b["record"]["attempt_no"]], [1, 2])   # 6
        s = beh.record_study(self.c, self.learner, task, item, result="done",
                             created_at=self._t("09:20:10"), contentpack_path=self.contentpack)
        self.assertEqual(s["record"]["attempt_no"], 1, "换行为重新从 1 开始")

    # ---- 7–8 结果语义 ---------------------------------------------------
    def test_04_result_semantics_unchanged(self):
        task = self._task()
        item = self.by_type["vocabulary"]
        outs = {}
        for i, res in enumerate(("correct", "incorrect", "partial")):
            outs[res] = beh.record_practice(self.c, self.learner, task, item, result=res,
                                            created_at=self._t("09:3%d:00" % i),
                                            contentpack_path=self.contentpack)["record"]
        self.assertEqual([outs[r]["result"] for r in ("correct", "incorrect", "partial")],
                         ["correct", "incorrect", "partial"])                        # 7
        # practice 不允许 correct 之外的对错值混用：done/skipped 不被当成 correct
        d = beh.record_practice(self.c, self.learner, task, item, result="done",
                                created_at=self._t("09:35:00"), contentpack_path=self.contentpack)
        s = beh.record_practice(self.c, self.learner, task, item, result="skipped",
                                created_at=self._t("09:36:00"), contentpack_path=self.contentpack)
        self.assertEqual((d["record"]["result"], s["record"]["result"]), ("done", "skipped"))
        m = svc.get_mastery(self.c, self.learner, item)
        self.assertEqual(m["correct_count"], 1, "只有 1 次 correct 计入 correct_count")   # 8
        self.assertEqual(m["evidence_count"], 4, "done 计入 evidence；skipped 不计入")
        self.assertEqual(m["last_result"], "done",
                         "last_result 为最近一次“参与判断”的结果（done）；skipped 不参与判断、不更新它")

        # study 不接受 correct/incorrect/partial
        for bad in ("correct", "incorrect", "partial"):
            with self.assertRaises(svc.ValidationError):
                beh.record_study(self.c, self.learner, task, item, result=bad,
                                 contentpack_path=self.contentpack)
        with self.assertRaises(svc.ValidationError):
            beh.record_behavior(self.c, self.learner, task, item, "view",
                                contentpack_path=self.contentpack)

    # ---- 9–12 只读操作不产生记录 ----------------------------------------
    def test_05_readonly_operations_do_not_create_records(self):
        before = self.c.execute("SELECT COUNT(*) FROM learning_record").fetchone()[0]
        # 9/10/11 Session + Task + TaskItem 创建
        session = ses.create_learning_session(self.c, self.learner, "vocabulary",
                                              [self.by_type["vocabulary"]],
                                              textbook_id=self.textbook_id,
                                              contentpack_path=self.contentpack)
        # 12 Activity 查询（P1-07-C2）
        acts = act.list_task_activities(self.c, session["task_id"], contentpack_path=self.contentpack)
        self.assertTrue(acts)
        # 浏览/池查询（只读）
        pool.list_current_issue_pool(self.c, self.learner, contentpack_path=self.contentpack)
        ses.list_learning_sessions(self.c, self.learner)
        svc.list_task_items(self.c, session["task_id"])
        after = self.c.execute("SELECT COUNT(*) FROM learning_record").fetchone()[0]
        self.assertEqual(after, before, "创建 Session/Task/TaskItem 与查询 Activity 不得产生 Record")

    # ---- 13–17 Mastery 与池联动 ----------------------------------------
    def test_06_mastery_and_pool_integration(self):
        task = self._task([self.by_type["vocabulary"], self.by_type["phrase"],
                           self.by_type["sentence_pattern"]])
        v, p, sp = self.by_type["vocabulary"], self.by_type["phrase"], self.by_type["sentence_pattern"]
        # incorrect → current_error（14）
        beh.record_practice(self.c, self.learner, task, v, result="incorrect",
                            created_at=self._t("10:00:00"), contentpack_path=self.contentpack)
        # partial → current_weak（15）
        beh.record_practice(self.c, self.learner, task, p, result="partial",
                            created_at=self._t("10:00:05"), contentpack_path=self.contentpack)
        pool1 = pool.list_current_issue_pool(self.c, self.learner, contentpack_path=self.contentpack)
        types = {x["item_id"]: x["issue_type"] for x in pool1}
        self.assertEqual(types.get(v), "current_error")
        self.assertEqual(types.get(p), "current_weak")
        # Mastery 按现有逻辑更新（13）
        mv = svc.get_mastery(self.c, self.learner, v)
        self.assertEqual((mv["evidence_count"], mv["correct_count"], mv["last_result"]), (1, 0, "incorrect"))
        # correct → 退出当前池（16）
        beh.record_practice(self.c, self.learner, task, v, result="correct",
                            created_at=self._t("10:00:10"), contentpack_path=self.contentpack)
        pool2 = pool.list_current_issue_pool(self.c, self.learner, contentpack_path=self.contentpack)
        self.assertNotIn(v, [x["item_id"] for x in pool2])
        self.assertIn(p, [x["item_id"] for x in pool2], "未作答的薄弱项仍保留")
        # 历史 Record 保留（17）
        recs = svc.list_records(self.c, learner_id=self.learner, item_id=v)
        self.assertEqual([r["result"] for r in recs], ["incorrect", "correct"])
        self.assertEqual([r["attempt_no"] for r in recs], [1, 2])

    # ---- 18 learner 隔离 ------------------------------------------------
    def test_07_learner_isolation(self):
        other = svc.create_learner(self.c, "另一个孩子")["learner_id"]
        task = self._task()
        item = self.by_type["vocabulary"]
        beh.record_practice(self.c, self.learner, task, item, result="incorrect",
                            created_at=self._t("11:00:00"), contentpack_path=self.contentpack)
        self.assertEqual(len(svc.list_records(self.c, learner_id=self.learner)), 1)
        self.assertEqual(svc.list_records(self.c, learner_id=other), [])
        self.assertIsNone(svc.get_mastery(self.c, other, item))
        with self.assertRaises(svc.ValidationError):
            beh.record_practice(self.c, other, task, item, result="correct",
                                contentpack_path=self.contentpack)

    # ---- 19–22 安全 -----------------------------------------------------
    def test_08_security(self):
        src = (HERE / "behavior_service.py").read_text(encoding="utf-8").lower()
        forbidden = ["openai", "deepseek", "ollama", "anthropic", "requests.", "urllib",
                     "http.client", "socket", "transformers", "torch", "tensorflow"]
        self.assertEqual([t for t in forbidden if t in src], [])            # 19/20
        for kw in ("insert into", "update ", "delete from", "create table", "alter table"):
            self.assertNotIn(kw, src, "行为协议层不得直接写库（必须委托 record_learning_event）")
        self.assertEqual(sha256_file(self.contentpack), self.contentpack_sha)   # 21
        self.assertEqual(sha256_file(self.official_db), self.official_sha)      # 22
        conn = sqlite3.connect("file:%s?mode=ro" % self.official_db.as_posix(), uri=True)
        rows = {t: conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
                for t in ("learner", "learning_session", "learning_task", "task_item",
                          "learning_record", "mastery_state")}
        conn.close()
        self.assertEqual(rows, OFFICIAL_DB_COUNTS,
                         "正式 learning.db 的真实学习数据不得被修改或删除")


if __name__ == "__main__":
    unittest.main(verbosity=2)
