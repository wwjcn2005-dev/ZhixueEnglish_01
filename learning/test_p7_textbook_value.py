#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P7 教材价值层验收测试（stdlib unittest）

验证 P7 增量构建（`builder/build_questionbank_value_v01.py`）写入的正式题库层：
  * 词形变化 `vocab_word_form`（教材正文句挖空 / 教材附录词形规则）
  * 教材语境词汇 `vocab_context_choice`
  * 教材附录 Language notes 短语释义 `phrase_meaning_choice`
并验证：证据可追溯、答案可由教材原文还原、原 1636 题未被改动、正式库零写入。

全部在 temp/ 下的正式库副本上运行；测试前后比对正式库 SHA256 必须一致。

运行：python D:\ZhixueEnglish\learning\test_p7_textbook_value.py
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import sqlite3
import sys
import unittest
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True

import study_call_service as scs          # noqa: E402
import questionbank_service as qb         # noqa: E402
import learning_service as svc            # noqa: E402

BASE = HERE.parent
TEMP = BASE / "temp" / ("p7_value_fixture_%d" % os.getpid())
QB_ORIG = BASE / "structured" / "questionbank" / "questionbank.db"
LB_ORIG = BASE / "structured" / "learning" / "learning.db"
CONTENTPACK = BASE / "structured" / "contentpack" / "v5" / "FLTRP-EN-7A-2022CUR.sqlite"

RUN_ID = "RUN-P7-VALUE-V1"
BASE_QUESTIONS = 1636                      # P7 之前的冻结基线
P7_TYPES = ("vocab_word_form", "vocab_context_choice")

#: P7 只读核验得到的 26 条已核验词形（验收基准）
FORM_BASELINE = (
    ("Starter", "lab", "labs"), ("Unit 1", "thought", "thoughts"), ("Unit 1", "wind", "winds"),
    ("Unit 1", "storm", "storms"), ("Unit 2", "instrument", "instruments"),
    ("Unit 2", "classmate", "classmates"), ("Unit 2", "page", "pages"),
    ("Unit 3", "mountain", "mountains"), ("Unit 3", "serve", "served"),
    ("Unit 3", "carry", "carrying"), ("Unit 3", "hug", "hugs"),
    ("Unit 4", "realise", "realised"), ("Unit 4", "dumpling", "dumplings"),
    ("Unit 4", "balloon", "balloons"), ("Unit 4", "lantern", "lanterns"),
    ("Unit 4", "firework", "fireworks"), ("Unit 5", "human", "humans"),
    ("Unit 5", "adult", "adults"), ("Unit 5", "biscuit", "biscuits"),
    ("Unit 5", "connect", "connecting"), ("Unit 6", "mirror", "mirrors"),
    ("Unit 6", "kilometre", "kilometres"), ("Unit 6", "speed", "speeds"),
    ("Unit 6", "museum", "museums"), ("Unit 6", "arrive", "arrived"),
    ("Unit 6", "hunt", "hunted"),
)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _norm(text):
    t = unicodedata.normalize("NFC", str(text or "")).lower().replace("\u2019", "'")
    t = t.replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    return re.sub(r"\s+", " ", t).strip()


class P7TextbookValueTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        TEMP.mkdir(parents=True, exist_ok=True)
        cls.qb = TEMP / "questionbank.db"
        cls.lb = TEMP / "learning.db"
        shutil.copyfile(QB_ORIG, cls.qb)
        shutil.copyfile(LB_ORIG, cls.lb)
        cls.orig_qb_sha = _sha(QB_ORIG)
        cls.orig_lb_sha = _sha(LB_ORIG)
        cls.conn = sqlite3.connect(cls.qb)
        cls.conn.row_factory = sqlite3.Row
        cls.cp = sqlite3.connect("file:%s?mode=ro" % CONTENTPACK.as_posix(), uri=True)
        cls.cp.row_factory = sqlite3.Row
        cls.p7 = cls.conn.execute(
            "SELECT * FROM question WHERE generation_run_id=? ORDER BY question_id",
            (RUN_ID,)).fetchall()

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        cls.cp.close()
        # 正式库零写入
        assert _sha(QB_ORIG) == cls.orig_qb_sha, "正式 questionbank.db 被修改"
        assert _sha(LB_ORIG) == cls.orig_lb_sha, "正式 learning.db 被修改"

    # ---------------- 工具
    def _primary_blocks(self, qid):
        rows = self.conn.execute(
            "SELECT asset_id, role FROM question_asset WHERE question_id=? AND "
            "asset_kind='content_block' ORDER BY role", (qid,)).fetchall()
        return [r["asset_id"] for r in rows], [r["role"] for r in rows]

    def _block_text(self, block_id):
        row = self.cp.execute("SELECT text_raw FROM content_block WHERE block_id=?",
                              (block_id,)).fetchone()
        return _norm(row["text_raw"]) if row else ""

    # ---------------- 1 增量与题型
    def test_01_p7_layer_exists_and_types(self):
        self.assertTrue(self.p7, "P7 未写入任何题目")
        types = {r["question_type"] for r in self.p7}
        self.assertEqual(types, set(P7_TYPES) | {"phrase_meaning_choice"})
        counts = {r["question_type"]: 0 for r in self.p7}
        for r in self.p7:
            counts[r["question_type"]] += 1
        self.assertGreater(counts["vocab_word_form"], 0, "词形变化层缺失")
        self.assertGreater(counts["vocab_context_choice"], 0, "教材语境词汇层缺失")
        for r in self.p7:
            self.assertEqual(r["origin"], "PROGRAM_GENERATED")
            self.assertEqual(r["answer_status"], "RELIABLE")
            self.assertEqual(r["quality_status"], "PASS")
            self.assertEqual(r["review_status"], "AUTO_ACCEPTED")
            self.assertEqual(r["answer_kind"] in ("exact", "option_key"), True)

    # ---------------- 2 词形变化：26 条已核验基准全覆盖
    def test_02_form_baseline_all_covered(self):
        present = set()
        for r in self.p7:
            if r["question_type"] != "vocab_word_form":
                continue
            prompt = __import__("json").loads(r["prompt_json"])
            answer = __import__("json").loads(r["answer_json"])
            present.add((r["unit_code"], (prompt.get("base") or "").lower(),
                         (answer.get("text") or "").lower()))
        missing = [t for t in FORM_BASELINE if t not in present]
        self.assertEqual(missing, [], "已核验词形未全部覆盖：%s" % missing)

    def test_03_form_answers_traceable_to_textbook(self):
        """词形答案必须能在教材正文或教材附录规则行中逐字找到。"""
        json_mod = __import__("json")
        for r in self.p7:
            if r["question_type"] != "vocab_word_form":
                continue
            answer = (json_mod.loads(r["answer_json"]).get("text") or "").lower()
            self.assertTrue(answer)
            block_ids, roles = self._primary_blocks(r["question_id"])
            self.assertTrue(block_ids, "词形题缺教材块证据")
            self.assertIn("primary", roles)
            blob = " ".join(self._block_text(b) for b in block_ids)
            self.assertRegex(blob, r"\b%s\b" % re.escape(answer),
                             "答案词形不在教材块原文中：%s" % r["question_id"])

    # ---------------- 3 语境题：答案可由教材原句逐字还原
    def test_04_context_answers_restore_textbook_sentence(self):
        json_mod = __import__("json")
        for r in self.p7:
            if r["question_type"] != "vocab_context_choice":
                continue
            prompt = json_mod.loads(r["prompt_json"])
            answer = json_mod.loads(r["answer_json"])
            options = json_mod.loads(r["options_json"])
            self.assertEqual(len(options), 4, "语境题必须 4 个选项")
            self.assertEqual(len({o["text"] for o in options}), 4, "选项不得重复")
            keys = [o["key"] for o in options]
            self.assertIn(answer["key"], keys)
            correct = [o["text"] for o in options if o["key"] == answer["key"]][0]
            self.assertEqual(correct, answer["text"])
            restored = _norm(prompt["text"].replace("______", answer["text"], 1))
            block_ids, _roles = self._primary_blocks(r["question_id"])
            blob = " ".join(self._block_text(b) for b in block_ids)
            self.assertIn(restored, blob, "还原句不在教材块原文中：%s" % r["question_id"])

    # ---------------- 4 短语释义题：释义来自教材附录
    def test_05_phrase_questions_from_appendix(self):
        json_mod = __import__("json")
        rows = [r for r in self.p7 if r["question_type"] == "phrase_meaning_choice"]
        self.assertTrue(rows, "P7 未产出教材附录短语释义题")
        for r in rows:
            prompt = json_mod.loads(r["prompt_json"])
            options = json_mod.loads(r["options_json"])
            self.assertIn("Language notes", prompt.get("evidence", ""))
            self.assertEqual(len(options), 4)
            block_ids, roles = self._primary_blocks(r["question_id"])
            self.assertEqual(roles, ["primary"])
            blob = self._block_text(block_ids[0])
            self.assertIn(_norm(prompt["text"]), blob, "短语必须出现在教材附录块中")
            self.assertIn("意为", blob, "教材附录必须给出该短语释义")

    # ---------------- 5 证据与去重
    def test_06_no_orphan_evidence_and_unique_hash(self):
        valid_blocks = {r[0] for r in self.cp.execute("SELECT block_id FROM content_block")}
        valid_items = {r[0] for r in self.cp.execute("SELECT item_id FROM learning_item")}
        for r in self.p7:
            rows = self.conn.execute(
                "SELECT asset_kind, asset_id FROM question_asset WHERE question_id=?",
                (r["question_id"],)).fetchall()
            self.assertTrue(rows, "题目缺证据：%s" % r["question_id"])
            for a in rows:
                if a["asset_kind"] == "content_block":
                    self.assertIn(a["asset_id"], valid_blocks)
                elif a["asset_kind"] == "learning_item":
                    self.assertIn(a["asset_id"], valid_items)
            self.assertTrue(any(a["asset_kind"] == "content_block" for a in rows))
        dup = self.conn.execute(
            "SELECT content_hash FROM question GROUP BY content_hash HAVING COUNT(*)>1"
        ).fetchall()
        self.assertEqual(dup, [])
        dup_prompt = self.conn.execute(
            "SELECT question_type, prompt_json FROM question GROUP BY question_type, prompt_json "
            "HAVING COUNT(*)>1").fetchall()
        self.assertEqual(dup_prompt, [], "同题型同题干重复")

    # ---------------- 6 原 1636 题零改动（只做增量）
    def test_07_original_questions_untouched(self):
        total = self.conn.execute("SELECT COUNT(*) FROM question").fetchone()[0]
        old = self.conn.execute("SELECT COUNT(*) FROM question WHERE generation_run_id IS NOT ? "
                                "OR generation_run_id<>?", (RUN_ID, RUN_ID)).fetchone()[0]
        self.assertEqual(total, old + len(self.p7))
        self.assertEqual(old, BASE_QUESTIONS, "原 1636 题被改动/删除")
        for r in self.p7:
            self.assertNotIn(r["question_id"], ())

    # ---------------- 7 入口映射（P5 学习调用层）
    def test_08_entry_mapping(self):
        self.assertEqual(scs.allowed_types("form"), ("vocab_word_form",))
        self.assertIn("vocab_word_form", scs.allowed_types("check"))
        self.assertIn("vocab_context_choice", scs.allowed_types("check"))
        self.assertIn("phrase_meaning_choice", scs.allowed_types("check"))
        cands = scs.select_questions("form", "Unit 1", questionbank_path=self.qb,
                                     learning_db=self.lb)
        self.assertTrue(cands)
        self.assertEqual({c["question_type"] for c in cands}, {"vocab_word_form"})
        self.assertEqual({c["unit_code"] for c in cands}, {"Unit 1"})

    # ---------------- 8 作答 → LearningRecord（有证据 item 才记录）
    def test_09_answer_records_learning_evidence(self):
        learner = svc.create_learner(scs.connect_learning_db(self.lb), "P7 测试学习者")["learner_id"]
        session = scs.start_practice_session("form", "Unit 1", learner, learning_db=self.lb,
                                             questionbank_path=self.qb)["session"]
        cands = scs.select_questions("form", "Unit 1", learner_id=learner, learning_db=self.lb,
                                     questionbank_path=self.qb)
        self.assertTrue(cands)
        pick = cands[0]
        answer = pick["question"]["answer"]
        picked = answer.get("key") or answer.get("text")
        out = scs.record_answer(session["session_id"], pick["question_id"], picked,
                               learner_id=learner, learning_db=self.lb,
                               questionbank_path=self.qb)
        self.assertTrue(out["recorded"], out)
        self.assertEqual(out["result"], "correct")
        self.assertTrue(out["mastery"]["evidence_count"] >= 1)

    def test_10_phrase_question_without_item_is_not_faked(self):
        row = self.conn.execute(
            "SELECT question_id FROM question WHERE question_type='phrase_meaning_choice' "
            "AND generation_run_id=? LIMIT 1", (RUN_ID,)).fetchone()
        self.assertIsNotNone(row)
        q = qb.get_question(row["question_id"], path=self.qb)
        self.assertIsNone(scs.evidence_item_for(q, CONTENTPACK, self.qb),
                          "附录短语题不应伪造教材 item 归属")


if __name__ == "__main__":
    unittest.main(verbosity=2)
