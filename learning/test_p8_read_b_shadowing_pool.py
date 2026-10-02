#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P8-Read-B 正式跟读资源池验收测试（stdlib unittest，全程只读）

验证：
  * 原有 38 条跟读素材仍全部存在（来源：contentpack 注释 + P3-06 AU06 + P3-07 精选）；
  * 新登记文件 `structured/audio/resources/shadowing_pool_v1.json` 的 72 条均有效；
  * 同句双音源只登记一处、同一教材句不重复；
  * `shadowing_materials()` 能读到新资源，且原有行为完全不变；
  * questionbank.db / learning.db 零写入；AI 调用 0。

运行：python D:\ZhixueEnglish\learning\test_p8_read_b_shadowing_pool.py
"""

from __future__ import annotations

import hashlib
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

import study_call_service as scs          # noqa: E402

BASE = HERE.parent
POOL_PATH = BASE / "structured" / "audio" / "resources" / "shadowing_pool_v1.json"
AUDIO_RESOURCE = BASE / "structured" / "audio" / "resources" / "audio_resource_v1.json"
CONTENTPACK = BASE / "structured" / "contentpack" / "v5" / "FLTRP-EN-7A-2022CUR.sqlite"
QUESTIONBANK = BASE / "structured" / "questionbank" / "questionbank.db"
LEARNING_DB = BASE / "structured" / "learning" / "learning.db"
P3_06 = BASE / "audit" / "P3-06_au06_verified_sentences.json"
P3_07 = BASE / "audit" / "P3-07_preview" / "selected_candidates_final.json"


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _norm(text):
    t = unicodedata.normalize("NFC", str(text or "")).lower()
    t = t.replace("\u2019", "'").replace("\u2018", "'")
    t = t.replace("\u201c", '"').replace("\u201d", '"')
    return re.sub(r"\s+", " ", t).strip()


class ShadowingPoolTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.qb_sha = _sha(QUESTIONBANK)
        cls.lb_sha = _sha(LEARNING_DB)
        cls.pool = json.loads(POOL_PATH.read_text(encoding="utf-8"))
        cls.entries = cls.pool["entries"]
        cls.served = []
        for u in scs.UNIT_ORDER:
            cls.served += scs.shadowing_materials(u)
        cls.served_txt = {_norm(m["text"]) for m in cls.served}
        cls.cp = sqlite3.connect("file:%s?mode=ro" % CONTENTPACK.as_posix(), uri=True)
        cls.cp.row_factory = sqlite3.Row
        cls.blocks = {r["block_id"] for r in cls.cp.execute("SELECT block_id FROM content_block")}
        cls.audio = json.loads(AUDIO_RESOURCE.read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls.cp.close()
        assert _sha(QUESTIONBANK) == cls.qb_sha, "questionbank.db 被修改"
        assert _sha(LEARNING_DB) == cls.lb_sha, "learning.db 被修改"

    # ---------------- 1 原有 38 条仍全部存在
    def test_01_legacy_38_still_present(self):
        texts = set()
        for r in self.cp.execute("SELECT sentence_text, status FROM audio_sentence_annotation "
                                 "WHERE status='VERIFIED'"):
            texts.add(_norm(r["sentence_text"]))
        for s in (json.loads(P3_06.read_text(encoding="utf-8")).get("sentences") or []):
            texts.add(_norm(s.get("text")))
        for r in json.loads(P3_07.read_text(encoding="utf-8")):
            texts.add(_norm(r.get("sentence_text")))
        texts.discard("")
        missing = sorted(t for t in texts if t not in self.served_txt)
        self.assertEqual(len(texts), 38, "既有跟读素材应为 38 条唯一句")
        self.assertEqual(missing, [], "既有跟读素材丢失：%s" % missing[:3])

    # ---------------- 2 新登记资源规模与 HIGH 全覆盖
    def test_02_registered_entries_and_high_coverage(self):
        self.assertEqual(len(self.entries), 72)
        by_status = {}
        for e in self.entries:
            by_status[e["verification_status"]] = by_status.get(e["verification_status"], 0) + 1
        self.assertEqual(by_status, {"VERIFIED": 69, "STATIC_CONFIRMED": 3})
        high = [e for e in self.entries if e["verification_status"] == "VERIFIED"]
        self.assertEqual(len(high), 69)
        missing = [e["text"] for e in high if _norm(e["text"]) not in self.served_txt]
        self.assertEqual(missing, [], "HIGH 资源未进入正式读取链：%s" % missing[:3])

    # ---------------- 3 MEDIUM 静态确认
    def test_03_medium_static_confirmation(self):
        confirmed = self.pool["medium_static_confirmation"]
        self.assertEqual(len(confirmed), 3)
        for c in confirmed:
            self.assertTrue(c["confirmed"])
            self.assertTrue(all(c["checks"].values()), c)
            self.assertTrue(0 < c["start_ms"] < c["end_ms"])
        texts = {_norm(c["text"]) for c in confirmed}
        for e in self.entries:
            if _norm(e["text"]) in texts:
                self.assertEqual(e["verification_status"], "STATIC_CONFIRMED")
                self.assertTrue(0 < e["start_ms"] < e["end_ms"])

    # ---------------- 4 同句双音源只保留一处
    def test_04_dual_source_single_registration(self):
        dual = [e for e in self.entries if e.get("alternate_source")]
        self.assertEqual(len(dual), 3)
        for e in dual:
            self.assertNotEqual(e["audio_code"], e["alternate_source"]["audio_code"])
            same = [x for x in self.entries if _norm(x["text"]) == _norm(e["text"])]
            self.assertEqual(len(same), 1, "同句重复登记：%s" % e["text"])
            served = [m for m in self.served if _norm(m["text"]) == _norm(e["text"])]
            self.assertEqual(len(served), 1, "同句在读取链出现多次：%s" % e["text"])

    # ---------------- 5 每条资源字段完整、时间有效
    def test_05_every_entry_complete_and_valid(self):
        for e in self.entries:
            self.assertTrue(e["resource_id"].startswith("SHP:"))
            self.assertIn(e["unit_code"], scs.UNIT_ORDER)
            self.assertTrue(e["text"].strip())
            self.assertIn(e["content_block"], self.blocks)
            self.assertTrue(re.fullmatch(r"AU\d{2}", e["audio_code"]))
            self.assertEqual(e["audio_url"], "/audio/official/%s.mp3" % e["audio_code"])
            self.assertTrue(0 < int(e["start_ms"]) < int(e["end_ms"]))
            self.assertIn(e["verification_status"], ("VERIFIED", "STATIC_CONFIRMED"))
            self.assertIn(e["pool_role"], ("BACKFILL", "SERVE"))

    # ---------------- 6 同一教材句不重复
    def test_06_no_duplicate_sentences(self):
        keys = [_norm(e["text"]) for e in self.entries]
        self.assertEqual(len(keys), len(set(keys)), "登记文件存在重复教材句")
        ids = [e["resource_id"] for e in self.entries]
        self.assertEqual(len(ids), len(set(ids)), "resource_id 重复")

    # ---------------- 7/8 shadowing_materials() 读取 + 原有行为不变
    def test_07_shadowing_materials_reads_pool(self):
        from_pool = [m for m in self.served if m.get("source") == "shadowing_pool"]
        self.assertEqual(len(from_pool), 1, "新登记资源应只有 1 条真正新增供给")
        m = from_pool[0]
        self.assertTrue(str(m["question_id"]).startswith("SHP:"))
        self.assertEqual(m["unit_code"], "Unit 3")
        self.assertTrue(0 < m["start_ms"] < m["end_ms"])
        self.assertTrue(m["audio_url"].startswith("/audio/official/AU"))

    def test_08_original_behavior_unchanged_without_pool(self):
        missing = BASE / "temp" / "_no_such_shadowing_pool.json"
        for u in scs.UNIT_ORDER:
            base = scs.shadowing_materials(u, shadowing_pool_path=missing)
            with_pool = scs.shadowing_materials(u)
            self.assertEqual(base, scs.shadowing_materials(u, shadowing_pool_path=missing))
            self.assertTrue(all("source" not in x for x in base), "题源条目不应带 pool 标记")
            # 题源部分完全一致（顺序与内容），新增资源只在末尾追加
            self.assertEqual(with_pool[:len(base)], base[:len(with_pool)])
            self.assertEqual(len(with_pool) - len(base), 1 if u == "Unit 3" else 0)

    # ---------------- 9/10/11 零写入与无 AI
    def test_09_formal_databases_untouched(self):
        self.assertEqual(_sha(QUESTIONBANK), self.qb_sha)
        self.assertEqual(_sha(LEARNING_DB), self.lb_sha)

    def test_10_no_ai_calls(self):
        self.assertEqual(self.pool["ai_calls"], 0)
        self.assertEqual(self.pool["generated_by"], "builder/build_shadowing_pool_v01.py")
        paths = [s["path"] for s in self.pool["sources"]]
        self.assertNotIn("ai", " ".join(paths).lower())

    def test_11_sources_match_current_files(self):
        for s in self.pool["sources"]:
            p = BASE / s["path"]
            self.assertTrue(p.exists(), s["path"])
            self.assertEqual(_sha(p), s["sha256"], "来源文件已变化：%s" % s["path"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
