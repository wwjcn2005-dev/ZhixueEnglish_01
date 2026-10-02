#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""教材音频资源层（audio_resource_v1）验收测试（stdlib unittest，只读）

覆盖验收标准 A–G（完整性 / 状态明确 / 权威来源 / P3 复用 / 无虚假匹配 / 可调用 / 原始资源零破坏）。

运行：python D:\ZhixueEnglish\learning\test_audio_resource_service.py
"""

from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True

import audio_resource_service as ars          # noqa: E402

BASE = HERE.parent
CONTENTPACK = BASE / "structured" / "contentpack" / "v5" / "FLTRP-EN-7A-2022CUR.sqlite"


class AudioResourceLayerTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.rows = ars.list_resources()
        cls.cp = sqlite3.connect("file:%s?mode=ro" % CONTENTPACK.as_posix(), uri=True)
        cls.blocks = {r[0] for r in cls.cp.execute("SELECT block_id FROM content_block")}
        cls.items = {r[0] for r in cls.cp.execute("SELECT item_id FROM learning_item")}
        cls.audios = {r[0].split(":")[-1]: r[0]
                      for r in cls.cp.execute("SELECT audio_id FROM audio_asset")}

    @classmethod
    def tearDownClass(cls):
        cls.cp.close()

    # ---- A 完整性 ----
    def test_A_54_audio_assets_with_identity(self):
        self.assertEqual(len(self.rows), 54)
        self.assertEqual(len(self.audios), 54)
        for r in self.rows:
            self.assertTrue(r["audio_asset_id"], r["audio_code"])
            self.assertEqual(r["audio_asset_id"].split(":")[-1], r["audio_code"])
            self.assertTrue(r["filename"], r["audio_code"])
            self.assertTrue(r["sha256"], r["audio_code"])
            self.assertTrue(r["duration_ms"], r["audio_code"])

    # ---- B 关系状态明确 ----
    def test_B_every_audio_has_explicit_status(self):
        for r in self.rows:
            self.assertIn(r["alignment_status"], ars.STATUSES, r["audio_code"])
            self.assertIn(r["readiness"],
                          ("READY_DETERMINISTIC", "READY_WITH_PROGRAM_PROCESSING",
                           "NEEDS_TEXT_RELATION"), r["audio_code"])
        stat = ars.summary()["alignment_status"]
        self.assertEqual(sum(stat.values()), 54)
        self.assertEqual(stat.get(ars.NO_TEXT_MATCH, 0), 0)

    # ---- C / E 权威来源 & 无虚假匹配 ----
    def test_C_verified_segments_have_text_id_time_and_evidence(self):
        verified = 0
        for r in self.rows:
            for s in r["segments"]:
                if s["status"] != ars.VERIFIED:
                    continue
                verified += 1
                self.assertTrue(s["text_resource_id"], r["audio_code"])
                self.assertIsNotNone(s["start_ms"], r["audio_code"])
                self.assertIsNotNone(s["end_ms"], r["audio_code"])
                self.assertLessEqual(s["start_ms"], s["end_ms"], r["audio_code"])
                self.assertTrue(s["alignment_evidence"], r["audio_code"])
        self.assertGreater(verified, 300)

    def test_E_text_ids_exist_in_contentpack(self):
        for r in self.rows:
            for s in r["segments"]:
                tid = s.get("text_resource_id")
                if not tid:
                    continue
                if s["text_resource_kind"] == "content_block":
                    self.assertIn(tid, self.blocks, "%s %s" % (r["audio_code"], tid))
                elif s["text_resource_kind"] == "learning_item":
                    self.assertIn(tid, self.items, "%s %s" % (r["audio_code"], tid))

    # ---- D P3 成果复用 ----
    def test_D_p3_artifacts_are_reused(self):
        artifacts = {s["source_artifact"] for r in self.rows for s in r["segments"]}
        self.assertIn("audit/P3-07_preview/selected_candidates_final.json", artifacts)
        self.assertIn("audit/P3-07_preview/matched_candidates.json", artifacts)
        self.assertIn("audit/P3-06_au06_verified_sentences.json", artifacts)
        self.assertIn("contentpack: audio_sentence_annotation", artifacts)
        self.assertIn("structured/audio/derived/word_audio_manifest.json", artifacts)
        self.assertEqual(ars.load().get("ai_calls"), 0)

    # ---- F 后续题库可调用 ----
    def test_F_query_chain_for_unit(self):
        ready = ars.generation_ready("Unit 1")
        self.assertTrue(ready[ars.READY_DETERMINISTIC] or ready[ars.READY_WITH_PROGRAM_PROCESSING])
        codes = [r["audio_code"] for r in ars.resources_for_unit("Unit 1")]
        self.assertIn("AU11", codes)
        au11 = ars.get_by_audio("AU11")
        self.assertEqual(au11["unit_code"], "Unit 1")
        self.assertTrue(au11["activity_id"])
        self.assertTrue(ars.capabilities("AU11"))
        self.assertIn(ars.readiness("AU11"),
                      (ars.READY_DETERMINISTIC, ars.READY_WITH_PROGRAM_PROCESSING))
        segs = ars.segments("AU11")
        self.assertTrue(segs)
        self.assertTrue(ars.text_resources("AU11", verified_only=False))

    def test_F_wordlist_audio_supports_word_abilities(self):
        r = ars.get_by_audio("AU48")
        self.assertEqual(r["resource_type"], "wordlist_audio")
        self.assertEqual(r["unit_code"], "Starter")
        self.assertEqual(r["alignment_status"], ars.VERIFIED)
        self.assertEqual(r["readiness"], ars.READY_DETERMINISTIC)
        caps = ars.capabilities("AU48")
        for cap in ("listen_identification", "dictation", "shadowing", "pronunciation"):
            self.assertIn(cap, caps)
        self.assertGreaterEqual(len(ars.segments("AU48", status=ars.VERIFIED)), 30)

    def test_F_phonetics_audio_marked_not_resolved(self):
        for code in ("AU10", "AU17", "AU24", "AU31", "AU38", "AU44"):
            r = ars.get_by_audio(code)
            self.assertEqual(r["resource_type"], "phonetics_audio", code)
            self.assertEqual(r["alignment_status"], ars.NEED_MANUAL_CONFIRMATION, code)
            self.assertEqual(r["readiness"], ars.NEEDS_TEXT_RELATION, code)

    # ---- G 原始资源零破坏 ----
    def test_G_upstream_sources_unchanged(self):
        self.assertTrue(ars.sources_intact(), "资源层记录的上游文件 sha256 已变化")
        mp3_dir = next(d for d in BASE.iterdir() if d.is_dir() and d.name.startswith("2025"))
        self.assertEqual(len(list(mp3_dir.glob("*.mp3"))), 54)
        self.assertTrue(list(mp3_dir.glob("*.pdf")), "原始教材 PDF 仍应存在")

    def test_G_integrity_check_passes(self):
        report = ars.integrity_check()
        self.assertTrue(report["ok"], report["problems"])
        self.assertEqual(report["summary"]["audio_assets"], 54)


if __name__ == "__main__":
    unittest.main(verbosity=2)
