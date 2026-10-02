#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P6-B-9 验收：Section 级学习进度（learned_sections）＋自主练习范围

覆盖：
  T1 真实数据映射分类（520 / 191 / 329 / 0 多 Section / 0 无法映射）
  T2 真实 learning.db 只能推出"有证据的 Section 集合"，不是 Unit 全量
  T3 Section 集合不是连续前缀（A、C 有证据 → 只 {A, C}）
  T4 Unit 级资源（词表/短语/附录语言运用）不新增 Section，也不破坏 Unit 级资源池
  T5 当前 Section 不再额外收窄自主练习范围
  T6 GET / POST 使用同一候选池计算（同一函数、同一结果）

全部在 **temp/ 下的 learning.db 副本**上运行：
  * 不改 structured/learning/learning.db
  * 不改 structured/questionbank/questionbank.db
  * 不改 structured/contentpack
测试前后对比三个正式资产的 SHA256，必须完全一致。

运行：python D:\ZhixueEnglish\learning\test_p6b9_section_progress.py
"""

from __future__ import annotations

import collections
import hashlib
import os
import shutil
import sqlite3
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "web"))
sys.dont_write_bytecode = True

import study_call_service as scs          # noqa: E402
import content as content_mod             # noqa: E402  （web/content.py：只读教材读取）
import app as web_app                     # noqa: E402  （只用 Handler 的范围计算函数）

BASE = HERE.parent
TEMP = BASE / "temp" / ("p6b9_fixture_%d" % os.getpid())
LB_ORIG = BASE / "structured" / "learning" / "learning.db"
QB_ORIG = BASE / "structured" / "questionbank" / "questionbank.db"
CP_ORIG = BASE / "structured" / "contentpack" / "v5" / "FLTRP-EN-7A-2022CUR.sqlite"
TEXTBOOK_ID = "FLTRP-EN-7A-2022CUR"


def _sha(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class _ScopeStub:
    """只借用 `web.app.Handler` 的范围计算函数（不启动服务、不写任何库）。"""

    path = "/unit/unit1/p5/practice?lesson=DEVELOPING_IDEAS"
    contentpack_path = str(CP_ORIG)
    P5_LESSON_TYPES = web_app.Handler.P5_LESSON_TYPES
    P5_VOCAB_TYPES = web_app.Handler.P5_VOCAB_TYPES
    _p5_items = web_app.Handler._p5_items
    _p5_scope_items = web_app.Handler._p5_scope_items
    _p5_word_items = web_app.Handler._p5_word_items
    _lesson_rows = web_app.Handler._lesson_rows
    _lessons_for = web_app.Handler._lessons_for
    _p5_lesson_qs = staticmethod(web_app.Handler._p5_lesson_qs) if hasattr(
        web_app.Handler, "_p5_lesson_qs") else None

    def __init__(self, learning_db: str):
        self.learning_db = learning_db

    def _set_cookie(self, *args, **kwargs):   # 范围计算不需要真 Cookie
        pass


class SectionProgressTest(unittest.TestCase):

    # ---------------- fixture ----------------
    @classmethod
    def setUpClass(cls):
        os.makedirs(TEMP, exist_ok=True)
        cls.lb = str(TEMP / "learning.db")
        shutil.copy2(LB_ORIG, cls.lb)
        cls.sha_lb = _sha(LB_ORIG)
        cls.sha_qb = _sha(QB_ORIG)
        cls.sha_cp = _sha(CP_ORIG)
        cp = scs.connect_contentpack(str(CP_ORIG))
        try:
            index = scs.section_index(cp)
            cls.item_sections = {}
            cls.item_type = {}
            cls.items = []
            for r in cp.execute("SELECT item_id, item_type FROM learning_item"):
                secs = scs.item_teaching_sections(r["item_id"], cp, index)
                cls.item_sections[r["item_id"]] = secs
                cls.item_type[r["item_id"]] = r["item_type"]
                cls.items.append(r["item_id"])
        finally:
            cp.close()
        cls.unit1 = content_mod.get_unit("unit1", str(CP_ORIG))

    @classmethod
    def tearDownClass(cls):
        assert _sha(LB_ORIG) == cls.sha_lb, "正式 learning.db 被修改"
        assert _sha(QB_ORIG) == cls.sha_qb, "正式 questionbank.db 被修改"
        assert _sha(CP_ORIG) == cls.sha_cp, "正式 contentpack 被修改"
        shutil.rmtree(TEMP, ignore_errors=True)

    # ---------------- 工具（只写 temp/ 副本） ----------------
    def _wr(self):
        conn = sqlite3.connect(self.lb)
        conn.row_factory = sqlite3.Row
        return conn

    def _new_learner(self, name="P6B9 测试学生"):
        cls = type(self)
        cls._seq = getattr(cls, "_seq", 0) + 1
        learner_id = "L-P6B9-%03d" % cls._seq
        conn = self._wr()
        try:
            conn.execute("INSERT INTO learner(learner_id, display_name, status, created_at) "
                         "VALUES(?,?,?,?)", (learner_id, name, "active", "2026-09-22T00:00:00+08:00"))
            conn.commit()
        finally:
            conn.close()
        return learner_id

    def _add_record(self, learner_id, item_id, activity_type="practice", result="correct",
                    n=1):
        conn = self._wr()
        try:
            task_id = "T-P6B9-%s-%d" % (learner_id[-4:], n)
            conn.execute("INSERT OR REPLACE INTO learning_task(task_id, learner_id, task_kind, "
                         "status, textbook_id, created_at) VALUES(?,?,?,?,?,?)",
                         (task_id, learner_id, "learn", "active", TEXTBOOK_ID,
                          "2026-09-22T00:00:00+08:00"))
            conn.execute("INSERT INTO learning_record(record_id, learner_id, task_id, item_id, "
                         "activity_type, result, attempt_no, hints_used, textbook_id, created_at) "
                         "VALUES(?,?,?,?,?,?,?,?,?,?)",
                         ("R-P6B9-%s-%d-%d" % (learner_id[-4:], n, len(item_id)), learner_id,
                          task_id, item_id, activity_type, result, 1, 0, TEXTBOOK_ID,
                          "2026-09-22T00:00:0%d+08:00" % (n % 10)))
            conn.commit()
        finally:
            conn.close()

    def _item_for(self, unit_code, section_key):
        for item_id in self.items:
            if self.item_sections[item_id] == {(unit_code, section_key)}:
                return item_id
        self.skipTest("没有可唯一定位到 %s/%s 的 item" % (unit_code, section_key))

    def _unit_level_item(self, item_type):
        for item_id in self.items:
            if not self.item_sections[item_id] and self.item_type[item_id] == item_type:
                return item_id
        self.skipTest("没有 %s 型 Unit 级 item" % item_type)

    def _real_learner(self):
        conn = scs.connect_learning_db_ro(self.lb)
        try:
            row = conn.execute("SELECT learner_id FROM learning_record LIMIT 1").fetchone()
            return row["learner_id"] if row else None
        finally:
            conn.close()

    # ---------------- T1 真实数据映射分类 ----------------
    def test_T1_item_section_mapping_counts(self):
        mapped = none = multi = 0
        by_type = collections.Counter()
        by_path = collections.Counter()
        cp = scs.connect_contentpack(str(CP_ORIG))
        try:
            index = scs.section_index(cp)
            for item_id in self.items:
                secs = scs.item_teaching_sections(item_id, cp, index)
                if len(secs) > 1:
                    multi += 1
                elif not secs:
                    none += 1
                else:
                    mapped += 1
                    by_type[self.item_type[item_id]] += 1
                    kinds = {r["source_type"] for r in cp.execute(
                        "SELECT source_type FROM source_ref WHERE item_id=?", (item_id,))}
                    by_path["activity" if "activity" in kinds else (
                        "content_block" if "content_block" in kinds else "textbook_page")] += 1
        finally:
            cp.close()
        self.assertEqual(len(self.items), 520, "learning_item 总数")
        self.assertEqual(mapped, 191, "可唯一映射到教学 Section 的 item")
        self.assertEqual(none, 329, "Unit 级（仅附录/词表位置）的 item")
        self.assertEqual(multi, 0, "跨多个教学 Section 的 item")
        self.assertEqual(dict(by_type), {"exercise": 157, "sentence_pattern": 34})
        self.assertEqual(dict(by_path), {"activity": 93, "content_block": 34, "textbook_page": 64})

    # ---------------- T2 真实 learning.db ----------------
    def test_T2_real_learning_db_sections(self):
        learner = self._real_learner()
        self.assertTrue(learner, "测试副本里应有真实学习记录")
        got = scs.learned_sections(learner, learning_db=self.lb)
        self.assertEqual(got, {("Starter", "GET_READY"), ("Unit 1", "DEVELOPING_IDEAS")})
        # 不能退化成"Unit 1 全部 Section"
        self.assertNotIn(("Unit 1", "UNDERSTANDING_IDEAS"), got)
        self.assertNotIn(("Unit 1", "STARTING_OUT"), got)
        self.assertEqual(len([s for s in got if s[0] == "Unit 1"]), 1)

    # ---------------- T3 非连续 Section ----------------
    def test_T3_non_contiguous_sections(self):
        learner = self._new_learner()
        a = self._item_for("Unit 1", "STARTING_OUT")
        c = self._item_for("Unit 1", "DEVELOPING_IDEAS")
        self._add_record(learner, a, n=1)
        self._add_record(learner, c, n=2)
        got = scs.learned_sections(learner, learning_db=self.lb)
        self.assertEqual(got, {("Unit 1", "STARTING_OUT"), ("Unit 1", "DEVELOPING_IDEAS")})
        self.assertNotIn(("Unit 1", "UNDERSTANDING_IDEAS"), got, "无证据的中间 Section 不得自动补上")

    # ---------------- T4 Unit 级资源 ----------------
    def test_T4_unit_level_items_do_not_add_sections(self):
        learner = self._new_learner()
        for i, item_type in enumerate(("vocabulary", "phrase", "sentence_pattern")):
            self._add_record(learner, self._unit_level_item(item_type),
                             activity_type="study", result="done", n=i + 1)
        self.assertEqual(scs.learned_sections(learner, learning_db=self.lb), set(),
                         "Unit 级资源不应新增 learned Section")
        # Unit 级资源池不受影响（练习候选仍然存在）
        pool = scs.select_questions("practice", "Unit 1", learner, learning_db=self.lb)
        self.assertTrue(pool, "Unit 级资源池不应被本次改动破坏")
        self.assertTrue({c["question_type"] for c in pool} & set(web_app.Handler.P5_VOCAB_TYPES))

    # ---------------- T5 当前 Section 不额外收窄 practice ----------------
    def test_T5_current_section_does_not_narrow_practice(self):
        learner = self._new_learner()
        for n, target in enumerate((("Starter", "GET_READY"),
                                    ("Unit 1", "UNDERSTANDING_IDEAS"),
                                    ("Unit 1", "DEVELOPING_IDEAS")), start=1):
            self._add_record(learner, self._item_for(*target), n=n)
        stub = _ScopeStub(self.lb)
        # 当前 Section = Unit 1 / DEVELOPING_IDEAS
        items = stub._p5_items(self.unit1, "practice", learner, "",
                               lesson_key="DEVELOPING_IDEAS")
        self.assertTrue(items, "自主练习候选不应为空")
        lesson_items = [i for i in items
                        if i["question"].get("question_type") in web_app.Handler.P5_LESSON_TYPES]
        sections = {(i["question"].get("unit_code"), i["question"].get("section_key"))
                    for i in lesson_items}
        self.assertEqual(sections, {("Starter", "GET_READY"),
                                    ("Unit 1", "UNDERSTANDING_IDEAS"),
                                    ("Unit 1", "DEVELOPING_IDEAS")},
                         "Section 级候选应等于已学 Section 集合，而不是只剩当前 Section")
        self.assertTrue(len(sections) > 1, "不得只剩当前 Section")

    # ---------------- T6 GET / POST 同一候选池 ----------------
    def test_T6_get_and_post_share_one_scope(self):
        learner = self._new_learner()
        for n, target in enumerate((("Starter", "GET_READY"), ("Unit 1", "DEVELOPING_IDEAS")), start=1):
            self._add_record(learner, self._item_for(*target), n=n)
        stub = _ScopeStub(self.lb)
        get_ids = [i["question_id"] for i in stub._p5_scope_items(self.unit1, "practice", learner, "", "")]
        post_ids = [i["question_id"] for i in stub._p5_scope_items(self.unit1, "practice", learner, "", "")]
        self.assertEqual(get_ids, post_ids, "GET / POST 必须使用同一候选集合")
        self.assertTrue(get_ids)
        # 结构保证：两侧确实调用同一个范围函数，且旧的"POST 不带范围参数"调用已消失
        src = (HERE.parent / "web" / "app.py").read_text(encoding="utf-8")
        self.assertEqual(src.count("self._p5_scope_items("), 2,
                         "_p5_page 与 _p5_submit 必须各调用一次 _p5_scope_items")
        self.assertNotIn("items = self._p5_items(unit, entry, learner_id)", src,
                         "POST 不应再单独调用不带范围参数的 _p5_items")


if __name__ == "__main__":
    unittest.main(verbosity=2)
