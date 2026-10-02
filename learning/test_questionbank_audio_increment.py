#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""题库音频增量（P4-01）验收测试（stdlib unittest，只读）

只校验"由 P3-08 VERIFIED 句段生成的句级听写题"的结构不变量，
不写死数量，不修改任何数据。

运行：python D:\ZhixueEnglish\learning\test_questionbank_audio_increment.py
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
import unicodedata
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True

import questionbank_service as qb          # noqa: E402
import audio_resource_service as ars       # noqa: E402

BASE = HERE.parent
CONTENTPACK = BASE / "structured" / "contentpack" / "v5" / "FLTRP-EN-7A-2022CUR.sqlite"


def _norm(text) -> str:
    t = unicodedata.normalize("NFC", str(text or "")).replace("\u2019", "'")
    return re.sub(r"\s+", " ", t).strip().lower()


class AudioIncrementQuestionTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.conn = qb.connect()
        cls.cp = sqlite3.connect("file:%s?mode=ro" % CONTENTPACK.as_posix(), uri=True)
        cls.cp.row_factory = sqlite3.Row
        cls.blocks = {r["block_id"]: (r["text_raw"] or "")
                      for r in cls.cp.execute("SELECT block_id, text_raw FROM content_block")}
        cls.layer = {r["audio_code"]: r for r in ars.list_resources()}
        cls.seg_owner, cls.seg = {}, {}
        for r in ars.list_resources():
            for s in r["segments"]:
                cls.seg_owner[s["segment_id"]] = r
                cls.seg[s["segment_id"]] = s
        # 音频增量生成的句级听写题：prompt 带 resource layer 的 segment_id
        cls.rows = []
        for row in cls.conn.execute(
                "SELECT * FROM question WHERE question_type='sentence_listen_write' "
                "AND prompt_json LIKE '%segment_id%'"):
            row = dict(row)
            row["prompt"] = json.loads(row["prompt_json"])
            row["answer"] = json.loads(row["answer_json"])
            cls.rows.append(row)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        cls.cp.close()

    def _assets(self, qid):
        return [dict(r) for r in self.conn.execute(
            "SELECT asset_kind, asset_id, role FROM question_asset WHERE question_id=?", (qid,))]

    # ---- A 证据完整 ----
    def test_A_primary_text_and_audio_evidence(self):
        self.assertTrue(self.rows, "没有音频增量句级听写题")
        for q in self.rows:
            kinds = {(a["asset_kind"], a["role"]) for a in self._assets(q["question_id"])}
            self.assertIn(("content_block", "primary"), kinds, q["question_id"])
            self.assertIn(("audio", "audio_source"), kinds, q["question_id"])

    # ---- B 只用 VERIFIED 精确句段 ----
    def test_B_only_verified_exact_segments_from_verified_audio(self):
        for q in self.rows:
            sid = q["prompt"]["segment_id"]
            self.assertIn(sid, self.seg, q["question_id"])
            seg, res = self.seg[sid], self.seg_owner[sid]
            self.assertEqual(seg["status"], "VERIFIED", sid)
            self.assertEqual(seg["timing_kind"], "exact", sid)
            self.assertEqual(res["alignment_status"], "VERIFIED", sid)
            self.assertEqual(res["resource_type"], "activity_audio", sid)

    # ---- C 答案可追溯到教材正文 ----
    def test_C_answer_text_is_official_textbook_text(self):
        for q in self.rows:
            primary = [a["asset_id"] for a in self._assets(q["question_id"])
                       if a["role"] == "primary" and a["asset_kind"] == "content_block"]
            self.assertEqual(len(primary), 1, q["question_id"])
            block = primary[0]
            self.assertIn(block, self.blocks, q["question_id"])
            self.assertIn(_norm(q["answer"]["text"]), _norm(self.blocks[block]), q["question_id"])

    # ---- D 时间范围合法 ----
    def test_D_time_range_within_audio_duration(self):
        for q in self.rows:
            res = self.seg_owner[q["prompt"]["segment_id"]]
            start, end = q["prompt"]["start_ms"], q["prompt"]["end_ms"]
            self.assertEqual((start, end), (self.seg[q["prompt"]["segment_id"]]["start_ms"],
                                            self.seg[q["prompt"]["segment_id"]]["end_ms"]))
            self.assertTrue(0 <= start < end <= (res["duration_ms"] or 0), q["question_id"])

    # ---- E Unit 一致（不跨 Unit、不使用未来 Unit 资源）----
    def test_E_unit_matches_audio_and_not_future_unit(self):
        for q in self.rows:
            res = self.seg_owner[q["prompt"]["segment_id"]]
            self.assertEqual(q["unit_code"], res["unit_code"], q["question_id"])

    # ---- F 判分与来源完整 ----
    def test_F_auto_gradeable_and_origin(self):
        for q in self.rows:
            self.assertEqual(q["answer_status"], "RELIABLE", q["question_id"])
            self.assertIn(q["answer_kind"], qb.DETERMINISTIC_KINDS, q["question_id"])
            self.assertEqual(q["origin"], "PROGRAM_GENERATED", q["question_id"])
            self.assertTrue(q["generation_run_id"] and q["rules_version"], q["question_id"])
            self.assertTrue(qb.can_auto_grade(qb.get_question(q["question_id"])), q["question_id"])

    # ---- G 全局不变量 ----
    def test_G_no_ai_generated_and_no_duplicate_hash(self):
        # P4 起：AI_GENERATED 题允许存在，但必须带教材/音频证据 + AI 来源证据（可追溯）。
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) FROM question q WHERE q.origin='AI_GENERATED' AND ("
            " NOT EXISTS (SELECT 1 FROM question_asset a WHERE a.question_id=q.question_id "
            "             AND a.role IN ('primary','audio_source'))"
            " OR NOT EXISTS (SELECT 1 FROM question_asset a WHERE a.question_id=q.question_id "
            "                AND a.asset_kind IN ('ai_distractor_cache','ai_generation_run')))"
        ).fetchone()[0], 0)
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) FROM (SELECT content_hash FROM question GROUP BY content_hash "
            "HAVING COUNT(*)>1)").fetchone()[0], 0)
        report = qb.integrity_report()
        self.assertTrue(report["ok"], report["problems"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
