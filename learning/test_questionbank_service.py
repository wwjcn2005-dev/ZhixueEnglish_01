#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""本地教材题库（questionbank.db）验收测试（stdlib unittest，只读）

覆盖 §十九 完成标准 A–J：
  A 独立题库存在；B 资源→题目关系；C 确定性题目已导入；D 不为凑数生成；
  E 不伪造答案；F AI 调用 0；G 全部题目可追溯教材 evidence；H 自动完整性/重复检查通过；
  I Unit 1–6 均可查询；J 音频资源层未被修改。

运行：python D:\ZhixueEnglish\learning\test_questionbank_service.py
"""

from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True

import questionbank_service as qb          # noqa: E402
import audio_resource_service as ars       # noqa: E402

BASE = HERE.parent
CONTENTPACK = BASE / "structured" / "contentpack" / "v5" / "FLTRP-EN-7A-2022CUR.sqlite"


class QuestionBankTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.conn = qb.connect()
        cls.cp = sqlite3.connect("file:%s?mode=ro" % CONTENTPACK.as_posix(), uri=True)
        cls.valid = {
            "content_block": {r[0] for r in cls.cp.execute("SELECT block_id FROM content_block")},
            "learning_item": {r[0] for r in cls.cp.execute("SELECT item_id FROM learning_item")},
            "activity": {r[0] for r in cls.cp.execute("SELECT activity_id FROM activity")},
            "section": {r[0] for r in cls.cp.execute("SELECT section_id FROM section")},
            "audio": {r[0] for r in cls.cp.execute("SELECT audio_id FROM audio_asset")},
        }

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        cls.cp.close()

    # ---- A 独立题库 ----
    def test_A_questionbank_exists_with_schema(self):
        self.assertTrue(qb.DB_PATH.exists(), "题库文件不存在")
        tables = {r[0] for r in self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for t in ("question", "question_asset", "generation_run", "quality_review", "supplement_task"):
            self.assertIn(t, tables)

    # ---- C / F 规模与 AI ----
    def test_C_scale_and_no_ai(self):
        s = qb.summary()
        self.assertGreater(s["questions"], 1000)
        # P4 起：允许可追溯的 AI_GENERATED 题（教材证据 + ai_distractor_cache 证据）；
        # 生成运行本身仍必须 ai_calls = 0（本轮复用既有 AI 干扰项缓存，未新增调用）。
        run = s["generation_runs"][0]
        self.assertEqual(run["ai_calls"], 0)
        self.assertEqual(run["generator"], "deterministic")
        self.assertEqual(run["status"], "PASS")

    # ---- E / G 证据与答案 ----
    def test_E_no_fabricated_answers(self):
        rows = self.conn.execute(
            "SELECT COUNT(*) FROM question WHERE answer_status<>'RELIABLE' AND answer_json IS NOT NULL"
        ).fetchone()[0]
        self.assertEqual(rows, 0)
        rows = self.conn.execute(
            "SELECT COUNT(*) FROM question WHERE answer_status='RELIABLE' AND (answer_json IS NULL "
            "OR answer_json IN ('', 'null'))").fetchone()[0]
        self.assertEqual(rows, 0)

    def test_G_every_question_has_primary_evidence(self):
        rows = self.conn.execute(
            "SELECT q.question_id FROM question q WHERE NOT EXISTS (SELECT 1 FROM question_asset a "
            "WHERE a.question_id=q.question_id AND a.role='primary')").fetchall()
        self.assertEqual([r[0] for r in rows], [])

    def test_G_all_references_exist(self):
        bad = []
        for qid, kind, aid in self.conn.execute(
                "SELECT question_id, asset_kind, asset_id FROM question_asset"):
            if kind in self.valid and aid and aid not in self.valid[kind]:
                bad.append((qid, kind, aid))
        self.assertEqual(bad, [])

    # ---- H 完整性 / 重复 ----
    def test_H_integrity_and_duplicates(self):
        report = qb.integrity_report()
        self.assertTrue(report["ok"], report["problems"])
        dup = self.conn.execute("SELECT content_hash FROM question GROUP BY content_hash "
                                "HAVING COUNT(*)>1").fetchall()
        self.assertEqual(dup, [])

    # ---- I Unit 1–6 可查询 ----
    def test_I_all_units_queryable_and_gradeable(self):
        for unit in ("Starter", "Unit 1", "Unit 2", "Unit 3", "Unit 4", "Unit 5", "Unit 6"):
            rows = qb.questions_for_unit(unit, limit=5)
            self.assertTrue(rows, unit)
            graded = qb.questions_for_unit(unit, auto_gradeable_only=True, limit=3)
            self.assertTrue(graded, "%s 无可自动判分题" % unit)
            for q in graded:
                self.assertTrue(qb.can_auto_grade(q), q["question_id"])

    def test_I_query_chain_returns_evidence_and_resources(self):
        rows = qb.questions_for_unit("Unit 1", auto_gradeable_only=True, limit=1)
        q = qb.get_question(rows[0]["question_id"])
        self.assertTrue(q["assets"])
        self.assertTrue(qb.can_auto_grade(q))
        self.assertTrue(q["prompt"].get("text") or q["prompt"].get("instruction"))
        audio_assets = [a for a in q["assets"] if a["asset_kind"] == "audio"]
        for a in audio_assets:
            self.assertIn(a["asset_id"], self.valid["audio"])

    # ---- 待 AI 补足池 ----
    def test_supplement_pool_has_next_stage_tasks(self):
        pool = qb.supplement_pool()
        self.assertTrue(pool)
        self.assertTrue(all(t["status"] == qb.AI_TASK_STATUS for t in pool))
        kinds = {t["kind"] for t in pool}
        for k in ("phonetics_text", "listening_understanding", "open_answer"):
            self.assertIn(k, kinds)

    # ---- D 不为凑数（题型由资源决定） ----
    def test_D_types_are_resource_driven(self):
        s = qb.summary()
        for t in ("vocab_listen_write", "vocab_phonetic_write", "vocab_meaning_choice",
                  "sentence_listen_write", "textbook_native"):
            self.assertIn(t, s["by_type"], t)
        # P4 起：句子听辨干扰项由既有 AI 干扰项缓存（rules-v3）提供，题目必须带 ai_distractor_cache 证据。
        # P4-C：另有 1 道句子听辨用"同 Unit 教材句"作干扰项（PROGRAM_GENERATED），
        #       该题必须有教材 content_block 干扰项证据；此处只约束 AI 生成的那些。
        if s["by_type"].get("sentence_listen_choice"):
            rows = self.conn.execute(
                "SELECT COUNT(*) FROM question q WHERE q.question_type='sentence_listen_choice' "
                "AND q.origin='AI_GENERATED' "
                "AND NOT EXISTS (SELECT 1 FROM question_asset a WHERE a.question_id=q.question_id "
                "AND a.asset_kind IN ('ai_distractor_cache','ai_generation_run'))").fetchone()[0]
            self.assertEqual(rows, 0, "句子听辨题缺 AI 干扰项证据")
            rows = self.conn.execute(
                "SELECT COUNT(*) FROM question q WHERE q.question_type='sentence_listen_choice' "
                "AND q.origin<>'AI_GENERATED' "
                "AND NOT EXISTS (SELECT 1 FROM question_asset a WHERE a.question_id=q.question_id "
                "AND a.asset_kind='content_block' AND a.role='distractor_basis')").fetchone()[0]
            self.assertEqual(rows, 0, "教材句干扰项的句子听辨题缺教材证据")

    # ---- J 上游资源层未修改 ----
    def test_J_audio_layer_untouched(self):
        self.assertTrue(ars.sources_intact(), "音频资源层记录的上游文件已被改动")
        self.assertEqual(ars.summary()["audio_assets"], 54)
        layer = BASE / "structured" / "audio" / "resources" / "audio_resource_v1.json"
        self.assertTrue(layer.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
