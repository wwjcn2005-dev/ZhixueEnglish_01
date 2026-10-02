#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-6-D-1 测试：Learning Object → LO Evidence → LO Mastery → LO Diagnosis → Suggestion

全部只读派生；写入仅发生在**临时数据库副本**。
覆盖任务书 §二十三 的 20 项要求。
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True

import diagnosis_service as diag          # noqa: E402
import evidence_service as ev             # noqa: E402
import learning_object_service as lo      # noqa: E402
import learning_service as svc            # noqa: E402
import mastery_service as ms              # noqa: E402

BASE = HERE.parent
RULES_PATH = BASE / "structured" / "learning" / "mastery_rules_v1.json"
OFFICIAL_DB = svc.DEFAULT_LEARNING_DB
CONTENTPACK = svc.DEFAULT_CONTENTPACK_DB


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


OFFICIAL_SHA = sha256_file(OFFICIAL_DB)
OFFICIAL_MTIME = OFFICIAL_DB.stat().st_mtime
CONTENTPACK_SHA = sha256_file(CONTENTPACK)

VS = lo.vocabulary_lo_map()
EX = lo.exercise_lo_map()
COVER = lo.mapping_coverage()


class LoIdentityTest(unittest.TestCase):
    """1–3、6–7：LO 身份与确定性"""

    def test_01_lo_id_is_deterministic(self):
        ck = lo.canonical_lex_key("VOCAB", "Ready", "adj")
        a, b = lo.lo_id("VOCAB", ck), lo.lo_id("VOCAB", ck)
        self.assertEqual(a, b)
        self.assertTrue(a.startswith("LO:FLTRP-EN-7A-2022CUR:VOCAB:"))
        self.assertEqual(lo.lo_id("VOCAB", lo.canonical_lex_key("VOCAB", "ready", "adj")), a,
                         "大小写/空白规范化后必须得到同一 LO")
        self.assertNotEqual(lo.lo_id("VOCAB", ck), lo.lo_id("PHRASE", ck),
                            "不同类型不得合并")

    def test_02_same_vocabulary_entry_same_lo(self):
        item = next(i for i, v in VS.items() if v["lexeme"] == "ready")
        first = VS[item]["learning_object_id"]
        again = lo.vocabulary_lo_map()[item]["learning_object_id"]
        self.assertEqual(first, again)
        self.assertEqual(first, lo.lo_id("VOCAB", VS[item]["canonical_key"]))

    def test_03_all_vocabulary_entries_get_stable_lo(self):
        vocab = [v for v in VS.values() if v["lo_type"] == "VOCAB"]
        self.assertEqual(len(vocab), 288)
        ids = {v["learning_object_id"] for v in vocab}
        self.assertEqual(len(ids), 288, "288 个词条必须得到 288 个不同 LO（词面唯一）")

    def test_04_listening_lo_is_task_level(self):
        listen = [v for v in EX.values() if v["rule"] == "R1_listening_task"]
        self.assertEqual(len(listen), 21)
        for v in listen:
            self.assertEqual(len(v["lo_ids"]), 1)
            self.assertIn(":LISTENING:", v["lo_ids"][0])
        # 同一板块不同活动 → 不同 LO；不同板块同活动号 → 不同 LO
        keys = {(v["unit"], v["section"], v["exercise_no"]): v["lo_ids"][0] for v in listen}
        self.assertEqual(len(set(keys.values())), len(keys), "任务级 LO 不得互相合并")

    def test_05_unmapped_has_no_pseudo_lo(self):
        unmapped = [v for v in EX.values() if v["status"] == "unmapped"]
        self.assertEqual(len(unmapped), 68)
        for v in unmapped:
            self.assertEqual(v["lo_ids"], [])
            self.assertIsNone(v["rule"])


class MappingCoverageTest(unittest.TestCase):
    """4–5：exercise 映射确定性与诚实覆盖率"""

    def test_06_exercise_mapping_deterministic(self):
        again = lo.exercise_lo_map()
        self.assertEqual({k: v["lo_ids"] for k, v in EX.items()},
                         {k: v["lo_ids"] for k, v in again.items()})
        self.assertEqual({k: v["status"] for k, v in EX.items()},
                         {k: v["status"] for k, v in again.items()})

    def test_07_coverage_reported_honestly(self):
        self.assertEqual(COVER["exercises_total"], 157)
        self.assertEqual(COVER["mapped_count"], 89)
        self.assertEqual(COVER["unmapped_count"], 68)
        self.assertEqual(COVER["mapped_count"] + COVER["unmapped_count"], 157)
        self.assertTrue(0 < COVER["coverage_ratio"] < 1)
        self.assertEqual(COVER["by_rule"]["R1_listening_task"], 21)
        self.assertEqual(COVER["by_rule"]["R2_writing_task"], 7)
        self.assertEqual(COVER["by_rule"]["R3_reading_text"], 37)
        self.assertEqual(COVER["by_rule"]["R4_single_core_vocab"], 12)
        self.assertEqual(COVER["by_rule"]["R5_multi_core_vocab"], 12)
        self.assertEqual(COVER["by_rule"]["unmapped"], 68)


class SeedBase(unittest.TestCase):
    """公共夹具：临时库 + 真实同-LO 用例（不含测试方法，避免子类重复执行）。"""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="zhixue_p26d_"))
        cls.db = cls.tmpdir / "learning_test.db"
        shutil.copyfile(OFFICIAL_DB, cls.db)
        cls.textbook = "FLTRP-EN-7A-2022CUR"
        # 真实同-LO 用例（C-4 Case C）：一个单词 + 两个映射到它的练习
        cls.word_item = next(i for i, v in VS.items() if v["lexeme"] == "eraser")
        cls.lo = VS[cls.word_item]["learning_object_id"]
        cls.ex_items = [k for k, v in EX.items() if cls.lo in (v["lo_ids"] or [])]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def setUp(self):
        self.w = svc.connect_learning_db(self.db)
        self.r = ev.connect_learning_db(self.db)
        self.learner = svc.create_learner(self.w, "D1测试")["learner_id"]

    def tearDown(self):
        self.r.close()
        self.w.close()

    def _record(self, item_id, activity_type, result, created_at):
        task = svc.create_task(self.w, self.learner, "learn", [item_id], self.textbook)
        out = svc.record_learning_event(self.w, self.learner, task["task_id"], item_id,
                                        activity_type, result=result, created_at=created_at)
        return out["record"]["record_id"]

    def _same_type_pair(self):
        """找一个 LO，其下至少有两个**同 question_type** 的练习（真实数据中存在）。"""
        by_lo = {}
        for ex_id, v in EX.items():
            for lo_id in v["lo_ids"] or []:
                by_lo.setdefault(lo_id, []).append((ex_id, v["question_type"]))
        for lo_id, items in by_lo.items():
            for i in range(len(items)):
                for j in range(i + 1, len(items)):
                    if items[i][1] == items[j][1]:
                        return type("Pair", (list,), {"lo": lo_id})(
                            [items[i][0], items[j][0]])
        return None


class LoEvidenceTest(SeedBase):
    """8–12：证据聚合、去重与 provenance（临时库）"""

    def test_08_audio_never_produces_evidence(self):
        before = self.r.execute("SELECT COUNT(1) FROM learning_record").fetchone()[0]
        for _ in range(2):                     # 反复读取 LO 视图（含音频相关 LO）
            lo.lo_evidence(self.r, self.learner)
            lo.summary(self.r, self.learner)
        after = self.r.execute("SELECT COUNT(1) FROM learning_record").fetchone()[0]
        self.assertEqual(after, before, "读取/播放相关视图不得产生学习记录（播放≠证据）")
        src = Path(HERE / "learning_object_service.py").read_text(encoding="utf-8")
        self.assertNotIn("audio_asset", src)
        self.assertNotIn("mp3", src.lower())

    def test_09_same_lo_sources_not_duplicated_as_evidence(self):
        pair = self._same_type_pair()
        if pair is None:
            self.skipTest("当前数据无同 LO 且同 task_type 的双练习")
        for item in pair:
            self._record(item, "practice", "correct", "2026-09-20T10:00:00+08:00")
        evs = lo.lo_evidence(self.r, self.learner)
        bucket = evs[pair.lo]
        self.assertEqual(bucket["evidence_count"], 1, "同日同 task_type 换题仍只计 1 条")
        self.assertEqual(len(bucket["evidence"][0]["sources"]), 2,
                         "两个来源都必须保留在 provenance 中")
        self.assertEqual(len(bucket["source_record_ids"]), 2)

    def test_10_natural_day_independence(self):
        self._record(self.word_item, "practice", "correct", "2026-09-20T10:00:00+08:00")
        self._record(self.word_item, "practice", "correct", "2026-09-21T10:00:00+08:00")
        bucket = lo.lo_evidence(self.r, self.learner)[self.lo]
        self.assertEqual(bucket["evidence_count"], 2)
        self.assertEqual(bucket["natural_days"], ["2026-09-20", "2026-09-21"])

    def test_11_task_type_independence(self):
        if not self.ex_items:
            self.skipTest("当前数据无映射练习")
        self._record(self.word_item, "practice", "correct", "2026-09-20T10:00:00+08:00")
        self._record(self.ex_items[0], "practice", "correct", "2026-09-20T11:00:00+08:00")
        bucket = lo.lo_evidence(self.r, self.learner)[self.lo]
        self.assertEqual(bucket["evidence_count"], 2, "recall 与 match 属不同 task_type")
        self.assertEqual(bucket["task_types"], ["match", "recall"])

    def test_12_provenance_fields_kept(self):
        self._record(self.word_item, "practice", "partial", "2026-09-20T10:00:00+08:00")
        bucket = lo.lo_evidence(self.r, self.learner)[self.lo]
        e = bucket["evidence"][0]
        for f in ("source_record_id", "item_id", "task_type", "evidence_date", "result",
                  "learner_id", "sources"):
            self.assertIn(f, e)
        self.assertEqual(e["item_id"], self.word_item)
        self.assertEqual(e["result"], "partial")


class LoMasteryDiagnosisTest(SeedBase):
    """13–15、17–18：Mastery / Diagnosis 复用与语义标注"""

    def test_13_mastery_uses_frozen_rules(self):
        self._record(self.word_item, "practice", "correct", "2026-09-20T10:00:00+08:00")
        rules = json.loads(RULES_PATH.read_text(encoding="utf-8"))
        evs = lo.lo_evidence(self.r, self.learner)
        m = lo.lo_mastery(self.r, self.learner, self.lo, rules=rules, lo_evidences=evs)
        direct = ms.evaluate(self.r, self.learner, self.lo, rules, evidence=evs[self.lo])
        self.assertEqual(m["state"], direct["state"])
        self.assertEqual(m["conditions"]["minimum_valid_evidence"]["required"],
                         rules["stable"]["minimum_valid_evidence"])
        self.assertFalse(m["stable"], "单次正确不得判为稳定掌握")

    def test_14_single_error_is_not_weak(self):
        self._record(self.word_item, "practice", "incorrect", "2026-09-20T10:00:00+08:00")
        d = lo.lo_diagnosis(self.r, self.learner, self.lo)
        self.assertEqual(d["level"], diag.LEVEL_CURRENT_ERROR)
        self.assertNotEqual(d["level"], diag.LEVEL_SUSPECTED_WEAK)

    def test_15_diagnosis_keeps_provenance(self):
        rec = self._record(self.word_item, "practice", "incorrect", "2026-09-20T10:00:00+08:00")
        d = lo.lo_diagnosis(self.r, self.learner, self.lo)
        self.assertIn(rec, d["evidence_ids"])

    def test_16_object_type_is_learning_object(self):
        self._record(self.word_item, "practice", "correct", "2026-09-20T10:00:00+08:00")
        m = lo.lo_mastery(self.r, self.learner, self.lo)
        d = lo.lo_diagnosis(self.r, self.learner, self.lo)
        self.assertEqual(m["object_type"], "learning_object")
        self.assertEqual(m["learning_object_id"], self.lo)
        self.assertEqual(d["object_type"], "learning_object")
        self.assertEqual(d["learning_object_id"], self.lo)

    def test_17_pool_state_none_is_allowed(self):
        self._record(self.word_item, "practice", "incorrect", "2026-09-20T10:00:00+08:00")
        d = lo.lo_diagnosis(self.r, self.learner, self.lo)
        self.assertIn("pool_state", d)
        self.assertTrue(d["pool_state"] is None or isinstance(d["pool_state"], str),
                        "LO 级诊断的 pool_state 允许为 None（不得伪造 item 池信息）")
        self.assertIn("pool_state", d["pool_note"])


class SuggestionTest(SeedBase):
    """16、19–20：教材优先建议与保护"""

    def test_18_suggestion_is_textbook_first_and_not_auto(self):
        self._record(self.word_item, "practice", "incorrect", "2026-09-20T10:00:00+08:00")
        s = lo.lo_suggestion(self.r, self.learner, self.lo)
        self.assertEqual(s["object_type"], "learning_object")
        self.assertFalse(s["auto_execute"])
        self.assertTrue(s["suggestions"], "教材优先建议不得为空")
        order = lo.ev.load_rules()["intervention"]["textbook_first_order"]
        types = [x["type"] for x in s["suggestions"]]
        self.assertEqual(types, [t for t in order if t in types], "建议顺序必须符合教材优先")
        for x in s["suggestions"]:
            self.assertEqual(x["action"], "child_click")

    def test_19_service_does_not_write_database(self):
        self._record(self.word_item, "practice", "correct", "2026-09-20T10:00:00+08:00")
        before = sha256_file(self.db)
        for _ in range(2):
            lo.summary(self.r, self.learner)
            lo.needs_attention(self.r, self.learner)
        self.assertEqual(sha256_file(self.db), before, "只读派生层不得写库")

    def test_20_no_ai_and_source_clean(self):
        src = Path(HERE / "learning_object_service.py").read_text(encoding="utf-8")
        for token in ("openai", "deepseek", "ollama", "requests", "urllib.request", "socket."):
            self.assertNotIn(token, src.lower())
        self.assertIn("只读", src)


class SafetyTest(unittest.TestCase):
    """保护基线：正式库 / contentpack 不被本阶段实现触碰"""

    def test_21_official_db_untouched(self):
        self.assertEqual(sha256_file(OFFICIAL_DB), OFFICIAL_SHA)
        self.assertEqual(OFFICIAL_DB.stat().st_mtime, OFFICIAL_MTIME)

    def test_22_contentpack_untouched(self):
        self.assertEqual(sha256_file(CONTENTPACK), CONTENTPACK_SHA)

    def test_23_no_schema_change(self):
        conn = sqlite3.connect("file:%s?mode=ro" % OFFICIAL_DB.as_posix(), uri=True)
        try:
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertEqual(len(tables), 7)
            self.assertNotIn("learning_object", tables)
            self.assertNotIn("consolidation_action", tables)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
