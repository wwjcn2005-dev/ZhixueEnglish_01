#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-6-B 测试：有效证据 / 掌握判定 / 诊断 / 教材优先建议（全部只读派生）。

测试隔离：
  * 所有写入都发生在**临时数据库**（正式 learning.db 的副本）
  * contentpack / 正式 learning.db / 规范 V1.2 全程只读，测试前后 SHA256 一致
  * 不调用 AI、不联网
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
import intervention_service as interv     # noqa: E402
import learning_service as svc            # noqa: E402
import mastery_service as mastery         # noqa: E402

BASE = HERE.parent
RULES_PATH = BASE / "structured" / "learning" / "mastery_rules_v1.json"
SPEC_V12 = BASE / "初中英语AI辅助学习系统_最高指导原则与开发规范_V1.2.docx"


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


OFFICIAL_DB = svc.DEFAULT_LEARNING_DB
OFFICIAL_DB_SHA = sha256_file(OFFICIAL_DB)
OFFICIAL_DB_MTIME = OFFICIAL_DB.stat().st_mtime
CONTENTPACK = svc.DEFAULT_CONTENTPACK_DB
CONTENTPACK_SHA = sha256_file(CONTENTPACK)
SPEC_SHA = sha256_file(SPEC_V12)
RULES = ev.load_rules()


class BaseCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="zhixue_p26b_"))
        cls.tmp_db = cls.tmpdir / "learning_test.db"
        shutil.copyfile(OFFICIAL_DB, cls.tmp_db)
        cp = svc.connect_contentpack_db(CONTENTPACK)
        cls.vocab = cp.execute("SELECT item_id FROM learning_item WHERE item_type='vocabulary' "
                               "ORDER BY item_id LIMIT 1").fetchone()["item_id"]
        cls.vocab2 = cp.execute("SELECT item_id FROM learning_item WHERE item_type='vocabulary' "
                                "ORDER BY item_id LIMIT 1 OFFSET 1").fetchone()["item_id"]
        cls.textbook = cp.execute("SELECT textbook_id FROM learning_item LIMIT 1").fetchone()["textbook_id"]
        cp.close()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def setUp(self):
        self.w = svc.connect_learning_db(self.tmp_db)       # 写入（播种）
        self.r = ev.connect_learning_db(self.tmp_db)        # 只读（被测服务）

    def tearDown(self):
        self.r.close()
        self.w.close()

    # ---------- 播种辅助 ----------
    def learner(self, name="P2-6B"):
        return svc.create_learner(self.w, name)["learner_id"]

    def task(self, learner_id, item_id):
        return svc.create_task(self.w, learner_id, "learn", [item_id], self.textbook)

    def record(self, learner_id, item_id, activity_type, result, created_at,
               response_raw=None, task_id=None):
        t = task_id or self.task(learner_id, item_id)
        return svc.record_learning_event(
            self.w, learner_id, t["task_id"], item_id, activity_type, result=result,
            response_raw=response_raw, created_at=created_at)["record"]["record_id"]

    def evidence(self, learner_id, item_id):
        return ev.collect_evidence(self.r, learner_id, item_id, RULES)


class EvidenceTest(BaseCase):
    """§二十一 Evidence 1–9"""

    def test_01_done_is_not_valid_evidence(self):
        lid = self.learner()
        self.record(lid, self.vocab, "study", "done", "2026-09-01T10:00:00+08:00")
        e = self.evidence(lid, self.vocab)
        self.assertEqual(e["evidence_count"], 0)
        self.assertTrue(all(x["reason"] == "result_not_judged" for x in e["invalid"]))

    def test_02_skipped_is_not_valid_evidence(self):
        lid = self.learner()
        self.record(lid, self.vocab, "practice", "skipped", "2026-09-01T10:00:00+08:00")
        self.assertEqual(self.evidence(lid, self.vocab)["evidence_count"], 0)

    def test_03_contact_only_is_not_valid_evidence(self):
        lid = self.learner()
        # study + 非 done（假设未来有 study/correct）也必须被排除为“仅接触”
        self.record(lid, self.vocab, "study", "correct", "2026-09-01T10:00:00+08:00")
        e = self.evidence(lid, self.vocab)
        self.assertEqual(e["evidence_count"], 0)
        self.assertTrue(any(x["reason"] == "contact_only" for x in e["not_evaluable"]))

    def test_04_judged_result_is_valid_evidence(self):
        lid = self.learner()
        self.record(lid, self.vocab, "practice", "correct", "2026-09-01T10:00:00+08:00")
        e = self.evidence(lid, self.vocab)
        self.assertEqual(e["evidence_count"], 1)
        self.assertEqual(e["evidence"][0]["result"], "correct")
        self.assertEqual(e["evidence"][0]["task_type"], "recall")

    def test_05_same_day_same_item_same_task_type_counts_once(self):
        lid = self.learner()
        for i in range(8):
            self.record(lid, self.vocab, "practice", "correct",
                        "2026-09-01T%02d:00:00+08:00" % (10 + i))
        e = self.evidence(lid, self.vocab)
        self.assertEqual(e["evidence_count"], 1)
        self.assertEqual(e["suppressed_count"], 7)
        self.assertEqual(len(e["evidence"][0]["deduped_from"]), 7)

    def test_06_different_natural_days_are_independent(self):
        lid = self.learner()
        self.record(lid, self.vocab, "practice", "correct", "2026-09-01T10:00:00+08:00")
        self.record(lid, self.vocab, "practice", "correct", "2026-09-02T10:00:00+08:00")
        e = self.evidence(lid, self.vocab)
        self.assertEqual(e["evidence_count"], 2)
        self.assertEqual(e["natural_days"], ["2026-09-01", "2026-09-02"])

    def test_07_different_task_types_are_independent(self):
        lid = self.learner()
        self.record(lid, self.vocab, "practice", "correct", "2026-09-01T10:00:00+08:00")
        self.record(lid, self.vocab, "recognize", "correct", "2026-09-01T11:00:00+08:00")
        e = self.evidence(lid, self.vocab)
        self.assertEqual(e["evidence_count"], 2)
        self.assertEqual(sorted(e["task_types"]), ["recall", "recognize"])

    def test_08_self_assessment_alone_is_not_judged_evidence(self):
        lid = self.learner()
        self.record(lid, self.vocab, "listen", "partial", "2026-09-01T10:00:00+08:00",
                    response_raw=json.dumps({"answers": {"self_check": "partial"}}))
        e = self.evidence(lid, self.vocab)
        self.assertEqual(e["evidence_count"], 0)
        self.assertTrue(any(x["reason"] == "self_assessment_only" for x in e["not_evaluable"]))

    def test_09_unevaluable_is_marked_not_counted(self):
        lid = self.learner()
        self.record(lid, self.vocab, "practice", None, "2026-09-01T10:00:00+08:00")
        e = self.evidence(lid, self.vocab)
        self.assertEqual(e["evidence_count"], 0)
        self.assertTrue(e["invalid"] or e["not_evaluable"])
        self.assertEqual(e["evidence"], [])


class MasteryTest(BaseCase):
    """§二十一 Mastery 10–19"""

    def _seed(self, spec):
        """spec: [(day, activity_type, result)]"""
        lid = self.learner()
        for i, (day, atype, result) in enumerate(spec):
            self.record(lid, self.vocab, atype, result,
                        "%sT%02d:00:00+08:00" % (day, 10 + i))
        return lid

    def test_10_fewer_than_three_evidence(self):
        lid = self._seed([("2026-09-01", "practice", "correct"),
                          ("2026-09-02", "recognize", "correct")])
        m = mastery.evaluate(self.r, lid, self.vocab, RULES)
        self.assertFalse(m["stable"])
        self.assertFalse(m["conditions"]["minimum_valid_evidence"]["met"])

    def test_11_single_task_type(self):
        lid = self._seed([("2026-09-01", "practice", "correct"),
                          ("2026-09-02", "practice", "correct"),
                          ("2026-09-03", "practice", "correct")])
        m = mastery.evaluate(self.r, lid, self.vocab, RULES)
        self.assertFalse(m["stable"])
        self.assertFalse(m["conditions"]["minimum_task_types"]["met"])

    def test_12_single_natural_day(self):
        lid = self._seed([("2026-09-01", "practice", "correct"),
                          ("2026-09-01", "recognize", "correct"),
                          ("2026-09-01", "practice", "correct")])
        m = mastery.evaluate(self.r, lid, self.vocab, RULES)
        self.assertFalse(m["stable"])
        self.assertFalse(m["conditions"]["minimum_natural_days"]["met"])

    def test_13_recent_three_only_one_correct(self):
        lid = self._seed([("2026-09-01", "practice", "correct"),
                          ("2026-09-02", "recognize", "correct"),
                          ("2026-09-03", "practice", "incorrect"),
                          ("2026-09-04", "recognize", "incorrect"),
                          ("2026-09-05", "practice", "correct")])
        m = mastery.evaluate(self.r, lid, self.vocab, RULES)
        self.assertFalse(m["stable"])
        self.assertFalse(m["conditions"]["recent_correct_minimum"]["met"])

    def test_14_unresolved_current_error_blocks_stable(self):
        lid = self._seed([("2026-09-01", "practice", "correct"),
                          ("2026-09-02", "recognize", "correct"),
                          ("2026-09-03", "practice", "correct"),
                          ("2026-09-04", "recognize", "incorrect")])
        m = mastery.evaluate(self.r, lid, self.vocab, RULES)
        self.assertFalse(m["stable"])
        self.assertFalse(m["conditions"]["no_unresolved_current_error"]["met"])
        self.assertEqual(m["state"], mastery.STATE_NEEDS_REVIEW)

    def test_15_all_five_conditions_yields_stable(self):
        lid = self._seed([("2026-09-01", "practice", "correct"),
                          ("2026-09-02", "recognize", "correct"),
                          ("2026-09-03", "practice", "correct")])
        m = mastery.evaluate(self.r, lid, self.vocab, RULES)
        self.assertTrue(all(c["met"] for c in m["conditions"].values()))
        self.assertTrue(m["stable"])
        self.assertEqual(m["state"], mastery.STATE_STABLE)
        self.assertIn("掌握较稳定", mastery.display_text(m))

    def test_16_single_correct_is_not_stable(self):
        lid = self._seed([("2026-09-01", "practice", "correct")])
        m = mastery.evaluate(self.r, lid, self.vocab, RULES)
        self.assertFalse(m["stable"])
        self.assertIn("不代表掌握", mastery.display_text(m))

    def test_17_single_error_is_not_suspected_weak(self):
        lid = self._seed([("2026-09-01", "practice", "incorrect")])
        d = diag.diagnose(self.r, lid, self.vocab, RULES)
        self.assertEqual(d["level"], diag.LEVEL_CURRENT_ERROR)
        self.assertNotEqual(d["level"], diag.LEVEL_SUSPECTED_WEAK)

    def test_18_same_day_repeat_cannot_create_stable(self):
        lid = self.learner()
        for i in range(8):
            self.record(lid, self.vocab, "practice", "correct",
                        "2026-09-01T%02d:00:00+08:00" % (9 + i))
        m = mastery.evaluate(self.r, lid, self.vocab, RULES)
        self.assertFalse(m["stable"])
        self.assertEqual(m["evidence_count"], 1)

    def test_19_official_data_never_becomes_stable(self):
        """正式库现有真实数据在判定后不得出现 stable（验收 I）。"""
        official = ev.connect_learning_db(OFFICIAL_DB)       # 直接只读正式库（不使用临时库）
        try:
            for row in official.execute("SELECT learner_id FROM learner"):
                items = mastery.evaluate_many(official, row["learner_id"], rules=RULES)
                for item_id, m in items.items():
                    self.assertFalse(m["stable"], "正式数据不应判为 stable：%s" % item_id)
                if items:
                    self.assertGreater(len(items), 0)
        finally:
            official.close()


class DiagnosisTest(BaseCase):
    """§二十一 Diagnosis 20–22"""

    def test_20_single_error_is_current_error_only(self):
        lid = self.learner()
        self.record(lid, self.vocab, "practice", "incorrect", "2026-09-01T10:00:00+08:00")
        d = diag.diagnose(self.r, lid, self.vocab, RULES)
        self.assertEqual(d["level"], diag.LEVEL_CURRENT_ERROR)
        self.assertIn("不判定为薄弱", d["note"])

    def test_21_repeated_errors_become_suspected_weak(self):
        lid = self.learner()
        self.record(lid, self.vocab, "practice", "incorrect", "2026-09-01T10:00:00+08:00")
        self.record(lid, self.vocab, "recognize", "incorrect", "2026-09-02T10:00:00+08:00")
        d = diag.diagnose(self.r, lid, self.vocab, RULES)
        self.assertEqual(d["level"], diag.LEVEL_SUSPECTED_WEAK)
        self.assertEqual(d["error_count"], 2)

    def test_22_diagnosis_traceable_to_evidence(self):
        lid = self.learner()
        rid = self.record(lid, self.vocab, "practice", "incorrect", "2026-09-01T10:00:00+08:00")
        d = diag.diagnose(self.r, lid, self.vocab, RULES)
        self.assertIn(rid, d["evidence_ids"])
        self.assertTrue(d["thresholds"]["suspected_weak"])


class InterventionTest(BaseCase):
    """§二十一 Intervention 23–26"""

    def test_23_suggestions_are_textbook_first(self):
        lid = self.learner()
        self.record(lid, self.vocab, "practice", "incorrect", "2026-09-01T10:00:00+08:00")
        s = interv.suggest(self.r, lid, self.vocab, RULES)
        self.assertTrue(s["textbook_first"])
        types = [x["type"] for x in s["suggestions"]]
        self.assertTrue(types, "必须给出教材优先建议")
        order = RULES["intervention"]["textbook_first_order"]
        self.assertEqual(types, [t for t in order if t in types])
        self.assertEqual(s["suggestions"][0]["type"], "reread_text")

    def test_24_missing_mapping_is_not_fabricated(self):
        lid = self.learner()
        fake_item = "FLTRP-EN-7A-2022CUR:V:NOT-A-REAL-ITEM"
        s = interv.suggest(self.r, lid, fake_item, RULES)
        self.assertTrue(s["requires_resource_mapping"])
        self.assertTrue(s["missing"])
        for sug in s["suggestions"]:
            anchor = sug["anchor"]
            self.assertNotIn("textbook_page", anchor)     # 不得伪造页码

    def test_25_suggestions_never_auto_execute(self):
        lid = self.learner()
        self.record(lid, self.vocab, "practice", "incorrect", "2026-09-01T10:00:00+08:00")
        s = interv.suggest(self.r, lid, self.vocab, RULES)
        self.assertFalse(s["auto_execute"])
        for sug in s["suggestions"]:
            self.assertEqual(sug["action"], "child_click")
        self.assertEqual(s["ai_assist"], "not_implemented")

    def test_26_no_ai_or_network_and_no_writes(self):
        src = Path(HERE / "evidence_service.py").read_text(encoding="utf-8")
        for token in ("openai", "deepseek", "requests", "urllib.request", "socket."):
            self.assertNotIn(token, src)
        before = sha256_file(self.tmp_db)
        lid = self.learner()
        self.record(lid, self.vocab, "practice", "incorrect", "2026-09-01T10:00:00+08:00")
        seed = sha256_file(self.tmp_db)
        for _ in range(3):                              # 反复调用只读服务
            mastery.evaluate_many(self.r, lid, rules=RULES)
            diag.list_attention(self.r, lid, RULES)
            interv.suggest_for_learner(self.r, lid, RULES)
        self.assertEqual(sha256_file(self.tmp_db), seed, "只读服务不得写库")
        self.assertNotEqual(before, seed)               # 播种确实写入（仅临时库）


class SafetyTest(unittest.TestCase):
    """§二十一 / §二十六：正式数据、contentpack、规范 V1.2 保护"""

    def test_01_official_db_untouched(self):
        self.assertEqual(sha256_file(OFFICIAL_DB), OFFICIAL_DB_SHA)
        self.assertEqual(OFFICIAL_DB.stat().st_mtime, OFFICIAL_DB_MTIME)

    def test_02_contentpack_untouched(self):
        self.assertEqual(sha256_file(CONTENTPACK), CONTENTPACK_SHA)

    def test_03_spec_v12_untouched(self):
        self.assertEqual(sha256_file(SPEC_V12), SPEC_SHA)

    def test_04_no_schema_migration(self):
        conn = sqlite3.connect("file:%s?mode=ro" % OFFICIAL_DB.as_posix(), uri=True)
        try:
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertEqual(len(tables), 7, "schema 不得迁移：%s" % sorted(tables))
        finally:
            conn.close()

    def test_05_rules_are_external_and_adjustable(self):
        rules = json.loads(RULES_PATH.read_text(encoding="utf-8"))
        for key in ("minimum_valid_evidence", "minimum_task_types", "minimum_natural_days",
                    "recent_attempt_window", "recent_correct_minimum"):
            self.assertIn(key, rules["stable"])
        self.assertIn("可验证、可调整", rules["note"])
        src = Path(HERE / "mastery_service.py").read_text(encoding="utf-8")
        self.assertIn("rules[\"stable\"]", src, "阈值必须从 JSON 读取，不得写死")


if __name__ == "__main__":
    unittest.main()
