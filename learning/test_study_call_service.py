#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P5 学习调用层验收测试（stdlib unittest）

全部在 **temp/ 下的正式库副本**上运行：
  * 不改 structured/questionbank/questionbank.db
  * 不改 structured/learning/learning.db
测试前后对比两个正式库的 SHA256，必须完全一致（test 14）。

运行：python D:\ZhixueEnglish\learning\test_study_call_service.py
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True

import study_call_service as scs          # noqa: E402
import questionbank_service as qb         # noqa: E402
import learning_service as svc            # noqa: E402
import evidence_service as ev             # noqa: E402

BASE = HERE.parent
TEMP = BASE / "temp" / ("p5_call_fixture_%d" % os.getpid())   # 每次进程独立副本，避免并发互踩
QB_ORIG = BASE / "structured" / "questionbank" / "questionbank.db"
LB_ORIG = BASE / "structured" / "learning" / "learning.db"


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class StudyCallServiceTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        TEMP.mkdir(parents=True, exist_ok=True)
        cls.qb = TEMP / "questionbank.db"
        cls.lb = TEMP / "learning.db"
        shutil.copyfile(QB_ORIG, cls.qb)
        shutil.copyfile(LB_ORIG, cls.lb)
        cls.orig_qb_sha = _sha(QB_ORIG)
        cls.orig_lb_sha = _sha(LB_ORIG)

    @classmethod
    def tearDownClass(cls):
        # 14. 正式数据库零修改
        assert _sha(QB_ORIG) == cls.orig_qb_sha, "正式 questionbank.db 被修改"
        assert _sha(LB_ORIG) == cls.orig_lb_sha, "正式 learning.db 被修改"

    # ---------------- 工具
    def _learner(self, name="测试学习者"):
        conn = scs.connect_learning_db(self.lb)
        try:
            return svc.create_learner(conn, name)["learner_id"]
        finally:
            conn.close()

    def _first(self, entry, unit, **kw):
        cands = scs.select_questions(entry, unit, questionbank_path=self.qb,
                                     learning_db=self.lb, **kw)
        return cands[0] if cands else None

    def _pick_question(self, qtype, unit=None):
        conn = scs.connect_questionbank(self.qb)
        try:
            sql = ("SELECT question_id FROM question WHERE question_type=? "
                   "AND quality_status='PASS' AND answer_status='RELIABLE' ")
            args = [qtype]
            if unit:
                sql += "AND unit_code=? "
                args.append(unit)
            sql += "ORDER BY question_id LIMIT 1"
            row = conn.execute(sql, args).fetchone()
            return row["question_id"] if row else None
        finally:
            conn.close()

    def _session_with(self, learner_id, entry, unit):
        out = scs.start_practice_session(entry, unit, learner_id, learning_db=self.lb,
                                         questionbank_path=self.qb)
        self.assertTrue(out["session"], "会话未创建：%s" % out)
        return out

    def _answer(self, qid):
        """给出该题的正确答案。"""
        q = qb.get_question(qid, path=self.qb)
        if q["answer_kind"] == "option_key":
            return q["answer"]["key"]
        return q["answer"]["text"]

    # ---------------- 1 首次学习
    def test_01_first_time(self):
        learner = self._learner()
        c = self._first("check", "Unit 1", learner_id=learner)
        self.assertIsNotNone(c)
        self.assertIn(c["reason"], ("not_started", "new"))
        self.assertIn(c["question_type"], scs.allowed_types("check"))

    # ---------------- 2 correct
    def test_02_correct_writes_record(self):
        learner = self._learner()
        s = self._session_with(learner, "phonetic", "Unit 1")
        qid = s["questions"][0]["question_id"]
        out = scs.record_answer(s["session"]["session_id"], qid, self._answer(qid),
                                learner_id=learner, learning_db=self.lb,
                                questionbank_path=self.qb)
        self.assertTrue(out["recorded"], out)
        self.assertEqual(out["result"], "correct")
        self.assertTrue(out["mastery"]["evidence_count"] >= 1)

    # ---------------- 3 incorrect
    def test_03_incorrect_becomes_current_error(self):
        learner = self._learner()
        s = self._session_with(learner, "phonetic", "Unit 1")
        first = s["questions"][0]
        qid, item = first["question_id"], first["evidence_item_id"]
        out = scs.record_answer(s["session"]["session_id"], qid, "zzz-wrong",
                                learner_id=learner, learning_db=self.lb,
                                questionbank_path=self.qb)
        self.assertEqual(out["result"], "incorrect")
        after = scs.select_questions("phonetic", "Unit 1", learner_id=learner,
                                     learning_db=self.lb, questionbank_path=self.qb)
        same_item = [c for c in after if c["evidence_item_id"] == item]
        self.assertTrue(same_item)
        self.assertEqual(same_item[0]["reason"], "current_error")
        self.assertEqual(same_item[0]["priority"], 0)

    # ---------------- 4 partial → current_weak
    def test_04_partial_becomes_current_weak(self):
        learner = self._learner()
        s = self._session_with(learner, "phonetic", "Unit 1")
        first = s["questions"][0]
        scs.record_answer(s["session"]["session_id"], first["question_id"], "",
                          learner_id=learner, force_result="partial", learning_db=self.lb,
                          questionbank_path=self.qb)
        after = scs.select_questions("phonetic", "Unit 1", learner_id=learner,
                                     learning_db=self.lb, questionbank_path=self.qb)
        same = [c for c in after if c["evidence_item_id"] == first["evidence_item_id"]]
        self.assertTrue(same)
        self.assertEqual(same[0]["reason"], "current_weak")
        self.assertEqual(same[0]["priority"], 1)

    # ---------------- 5 mastered → mastered_skip（降权但不禁止）
    def test_05_mastered_is_deprioritised_not_forbidden(self):
        learner = self._learner()
        s = scs.start_practice_session("check", "Unit 1", learner,
                                       learning_db=self.lb, questionbank_path=self.qb)
        # 用词汇 item：其 task_type 由 activity_type 决定，才能达到"≥2 种任务类型"
        qid = self._pick_question("vocab_meaning_choice", "Unit 1")
        item = scs.evidence_item_for(qid, qb_path=self.qb)
        self.assertTrue(item)
        conn = scs.connect_learning_db(self.lb)
        try:
            task_id = s["session"]["task_id"]
            for i in range(3):                      # 3 条有效证据（跨 3 天 / 2 种任务类型）
                svc.record_learning_event(
                    conn, learner, task_id, item, "recognize" if i < 2 else "spell",
                    result="correct", created_at="2026-09-%02dT10:00:00" % (10 + i))
        finally:
            conn.close()
        cands = scs.select_questions("check", "Unit 1", learner_id=learner,
                                     learning_db=self.lb, questionbank_path=self.qb)
        same = [c for c in cands if c["evidence_item_id"] == item]
        self.assertTrue(same)
        self.assertEqual(same[0]["reason"], "mastered_skip")
        self.assertEqual(cands[-1]["reason"], "mastered_skip")   # 排在最后

    # ---------------- 6 current_weak 排序优先于 not_started
    def test_06_weak_before_not_started(self):
        learner = self._learner()
        s = self._session_with(learner, "phonetic", "Unit 2")
        first = s["questions"][0]
        scs.record_answer(s["session"]["session_id"], first["question_id"], "",
                          learner_id=learner, force_result="partial", learning_db=self.lb,
                          questionbank_path=self.qb)
        cands = scs.select_questions("phonetic", "Unit 2", learner_id=learner,
                                     learning_db=self.lb, questionbank_path=self.qb)
        self.assertEqual(cands[0]["reason"], "current_weak")

    # ---------------- 7 / 21 自主练习覆盖已学连续前缀
    def test_07_practice_covers_learned_prefix(self):
        learner = self._learner()
        s = scs.start_practice_session("check", "Unit 1", learner,
                                       learning_db=self.lb, questionbank_path=self.qb)
        item = s["questions"][0]["evidence_item_id"]
        self.assertTrue(item)
        conn = scs.connect_learning_db(self.lb)
        try:
            svc.record_learning_event(conn, learner, s["session"]["task_id"], item,
                                      "recognize", result="correct")
        finally:
            conn.close()
        cands = scs.select_questions("practice", "Unit 2", learner_id=learner,
                                     learning_db=self.lb, questionbank_path=self.qb)
        units = {c["unit_code"] for c in cands}
        self.assertIn("Starter", units)
        self.assertIn("Unit 1", units)
        self.assertIn("Unit 2", units)

    # ---------------- 8 当前 Unit 无资源 / 9 词形变化（P7 起已有正式资源）
    def test_08_no_resource_entries_return_empty(self):
        learner = self._learner()
        self.assertEqual(scs.select_questions("read", "Unit 1", learner_id=learner,
                                              learning_db=self.lb, questionbank_path=self.qb), [])
        # P7：词形变化已有正式资源（教材正文句挖空 / 教材附录词形规则）→ form 入口返回词形题，
        # 且只返回 vocab_word_form，不越过 Unit 范围、不造题。
        forms = scs.select_questions("form", "Unit 1", learner_id=learner,
                                     learning_db=self.lb, questionbank_path=self.qb)
        self.assertTrue(forms, "P7 起 form 入口应有正式词形题")
        self.assertEqual({c["question_type"] for c in forms}, {"vocab_word_form"})
        self.assertEqual({c["unit_code"] for c in forms}, {"Unit 1"})
        self.assertTrue(all(c["question"]["quality_status"] == "PASS"
                            and c["question"]["answer_status"] == "RELIABLE" for c in forms))
        conn = scs.connect_questionbank(self.qb)
        try:
            self.assertGreater(conn.execute(
                "SELECT COUNT(*) FROM question WHERE question_type='vocab_word_form'"
            ).fetchone()[0], 0)
        finally:
            conn.close()

    # ---------------- 10 重复调用确定性一致 / 18 排序稳定
    def test_10_deterministic_and_stable_order(self):
        learner = self._learner()
        a = scs.select_questions("check", "Unit 3", learner_id=learner, learning_db=self.lb,
                                 questionbank_path=self.qb)
        b = scs.select_questions("check", "Unit 3", learner_id=learner, learning_db=self.lb,
                                 questionbank_path=self.qb)
        self.assertEqual([c["question_id"] for c in a], [c["question_id"] for c in b])
        keys = [(c["priority"], scs.UNIT_ORDER.index(c["unit_code"]),
                 c["question_type"], c["question_id"]) for c in a]
        self.assertEqual(keys, sorted(keys))

    # ---------------- 11 focus 专项过滤
    def test_11_focus_only_filters(self):
        learner = self._learner()
        c = scs.select_questions("practice", "Unit 1", learner_id=learner, focus="reading_choice",
                                 learning_db=self.lb, questionbank_path=self.qb)
        self.assertTrue(c)
        self.assertEqual({x["question_type"] for x in c}, {"reading_choice"})
        # focus 不能扩大题型：本课检测不允许 textbooks_native 之外的越界类型
        self.assertEqual(scs.select_questions("check", "Unit 1", learner_id=learner,
                                              focus="listening_choice", learning_db=self.lb,
                                              questionbank_path=self.qb), [])

    # ---------------- P6-B-6：「听音写词」(spell) 已删除，听音辨意只剩三种模式
    def test_11b_listen_modes_are_three_only(self):
        self.assertEqual(scs.MODES, ("word", "sentence", "reading"))
        self.assertNotIn("spell", scs.LISTEN_MODE_TYPES)
        self.assertNotIn("spell", scs.ENTRY_TYPES["listen"])
        with self.assertRaises(ValueError):
            scs.allowed_types("listen", "spell")

    # ---------------- 12 / 22 绝不进入未来 Unit（自主练习）
    def test_12_never_future_unit(self):
        learner = self._learner()
        cands = scs.select_questions("practice", "Unit 2",
                                     learned_prefix=("Starter", "Unit 1", "Unit 5"),
                                     learner_id=learner, learning_db=self.lb,
                                     questionbank_path=self.qb)
        self.assertEqual({c["unit_code"] for c in cands}, {"Starter", "Unit 1", "Unit 2"})

    # ---------------- 13 排除非正式题
    def test_13_only_formal_questions(self):
        learner = self._learner()
        for entry, unit in (("check", "Unit 1"), ("listen", "Unit 4"), ("practice", "Unit 1")):
            for c in scs.select_questions(entry, unit, learner_id=learner, learning_db=self.lb,
                                          questionbank_path=self.qb):
                self.assertEqual(c["question"]["quality_status"], "PASS")
                self.assertEqual(c["question"]["answer_status"], "RELIABLE")
        # textbook_native 是 NO_RELIABLE_SOURCE → 不得出现在本课检测候选中
        kinds = {c["question_type"] for c in scs.select_questions(
            "check", "Unit 1", learner_id=learner, learning_db=self.lb, questionbank_path=self.qb)}
        self.assertNotIn("textbook_native", kinds)

    # ---------------- 14 正式数据库零修改
    def test_14_formal_databases_untouched(self):
        self.assertEqual(_sha(QB_ORIG), self.orig_qb_sha)
        self.assertEqual(_sha(LB_ORIG), self.orig_lb_sha)

    # ---------------- 15 / 16 无 evidence item 的题
    def test_15_16_questions_without_evidence_item(self):
        learner = self._learner()
        conn = scs.connect_questionbank(self.qb)
        try:
            rows = [r["question_id"] for r in conn.execute(
                "SELECT question_id FROM question ORDER BY question_id")]
        finally:
            conn.close()
        no_item = [q for q in rows if scs.evidence_item_for(q, qb_path=self.qb) is None]
        self.assertTrue(no_item, "应当存在无法解析证据 item 的题（不得因此伪造）")
        # 16. 这些题仍可被调用（能出现在候选里）
        cands = scs.select_questions("listen", "Unit 4", learner_id=learner, learning_db=self.lb,
                                     questionbank_path=self.qb)
        self.assertTrue(cands)
        # 15. 对它们作答不写 LearningRecord
        s = self._session_with(learner, "listen", "Unit 4")
        target = next((c for c in s["questions"] if not c["evidence_item_id"]), None)
        if target is None:
            self.skipTest("当前 Unit 4 候选中没有无证据 item 的题")
        before = self._record_count(learner)
        out = scs.record_answer(s["session"]["session_id"], target["question_id"], "x",
                                learner_id=learner, learning_db=self.lb,
                                questionbank_path=self.qb)
        self.assertFalse(out["recorded"])
        self.assertEqual(out["reason"], "no_evidence_item")
        self.assertEqual(self._record_count(learner), before)

    def _record_count(self, learner):
        conn = scs.connect_learning_db_ro(self.lb)
        try:
            return conn.execute("SELECT COUNT(*) FROM learning_record WHERE learner_id=?",
                                (learner,)).fetchone()[0]
        finally:
            conn.close()

    # ---------------- 17 同一 session 内 question_id 不重复
    def test_17_no_repeat_within_session(self):
        learner = self._learner()
        s = self._session_with(learner, "phonetic", "Unit 1")
        sid = s["session"]["session_id"]
        first = s["questions"][0]["question_id"]
        nxt = scs.next_question(sid, "phonetic", "Unit 1", learner_id=learner,
                                served_question_ids=[first],
                                learning_db=self.lb, questionbank_path=self.qb)
        self.assertTrue(nxt)
        self.assertNotEqual(nxt["question_id"], first)
        # 作答后（correct）该题不再作为"未出现"返回
        scs.record_answer(sid, first, self._answer(first), learner_id=learner,
                          learning_db=self.lb, questionbank_path=self.qb)
        nxt2 = scs.next_question(sid, "phonetic", "Unit 1", learner_id=learner,
                                 learning_db=self.lb, questionbank_path=self.qb)
        self.assertTrue(nxt2)
        self.assertNotEqual(nxt2["question_id"], first)

    # ---------------- 19 mastered 题在自主练习仍可被主动调用
    def test_19_mastered_can_be_selected_on_demand(self):
        learner = self._learner()
        qid = self._pick_question("vocab_meaning_choice", "Unit 1")
        item = scs.evidence_item_for(qid, qb_path=self.qb)
        s = scs.start_practice_session("check", "Unit 1", learner, learning_db=self.lb,
                                       questionbank_path=self.qb)
        qid = self._pick_question("vocab_meaning_choice", "Unit 1")
        item = scs.evidence_item_for(qid, qb_path=self.qb)
        self.assertTrue(item)
        conn = scs.connect_learning_db(self.lb)
        try:
            for i in range(3):
                svc.record_learning_event(conn, learner, s["session"]["task_id"], item,
                                          "recognize" if i < 2 else "spell", result="correct",
                                          created_at="2026-09-%02dT10:00:00" % (10 + i))
        finally:
            conn.close()
        cands = scs.select_questions("practice", "Unit 1", learner_id=learner,
                                     focus="vocab_meaning_choice", learning_db=self.lb,
                                     questionbank_path=self.qb)
        self.assertIn(item, [c["evidence_item_id"] for c in cands])

    # ---------------- 20 本课检测绝不调用历史 Unit
    def test_20_check_uses_current_unit_only(self):
        learner = self._learner()
        cands = scs.select_questions("check", "Unit 3",
                                     learned_prefix=("Starter", "Unit 1", "Unit 2"),
                                     learner_id=learner, learning_db=self.lb,
                                     questionbank_path=self.qb)
        self.assertTrue(cands)
        self.assertEqual({c["unit_code"] for c in cands}, {"Unit 3"})

    # ---------------- 24 跟读 done 不进入 mastery 判断
    def test_24_shadowing_done_is_not_mastery_evidence(self):
        learner = self._learner()
        mats = scs.shadowing_materials("Unit 1", questionbank_path=self.qb)
        self.assertTrue(mats)
        s = scs.start_practice_session("practice", "Unit 1", learner, learning_db=self.lb,
                                       questionbank_path=self.qb)
        in_session = {c["question_id"]: c for c in s["questions"]}
        m = next((x for x in mats if x["question_id"] in in_session
                  and in_session[x["question_id"]]["evidence_item_id"]), None)
        if m is None:
            self.skipTest("Unit 1 跟读素材没有可归属 item 且不在本会话候选中")
        out = scs.record_shadowing(s["session"]["session_id"], m["question_id"],
                                   learner_id=learner, learning_db=self.lb,
                                   questionbank_path=self.qb)
        self.assertEqual(out.get("result"), "done")
        if out.get("recorded"):
            conn = scs.connect_learning_db_ro(self.lb)
            try:
                evd = ev.collect_evidence(conn, learner, m["evidence_item_id"])
            finally:
                conn.close()
            # done 不是有效判断证据 → 不产生 correct/incorrect 掌握证据
            self.assertTrue(all(e["result"] != "done" for e in evd["evidence"]))
            self.assertEqual(evd["evidence_count"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
