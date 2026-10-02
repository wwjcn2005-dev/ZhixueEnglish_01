#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-4 测试：教材完整重构（结构 / 视觉 / 上下文 / 音频 / 题目 / 证据包）。

全部只读：不写 learning.db、不改 contentpack、不动 PDF/MP3。
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True

import content as content_mod           # noqa: E402

BASE = HERE.parent
TB = BASE / "structured" / "textbook"
EX = BASE / "structured" / "exercises"
AU = BASE / "structured" / "audio"
AI = BASE / "structured" / "ai"
AUDIT = BASE / "audit" / "P2-4_textbook_reconstruction.json"
PDF = (BASE / "2025年度初一外研版英语教材"
       / "（根据2022年版课程标准修订）义务教育教科书·英语 七年级上册.pdf")
TEXTBOOK_DIR = BASE / "2025年度初一外研版英语教材"

VISUAL_ROLES = {"context_image", "instruction_support", "listening_context", "reading_context",
                "vocabulary_support", "writing_model", "question_context", "decorative",
                "unknown", "blank_line"}
RELATION_TYPES = {"contains", "precedes", "follows", "belongs_to", "supports", "illustrates",
                  "uses", "tests", "references", "continues", "depends_on", "paired_with",
                  "audio_for", "image_for", "question_for", "vocabulary_in", "grammar_in"}
BUSINESS_TABLES = ("learner", "learning_session", "learning_task", "task_item",
                   "learning_record", "mastery_state")


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def business_counts(db_path) -> dict:
    conn = sqlite3.connect("file:%s?mode=ro" % Path(db_path).as_posix(), uri=True)
    try:
        return {t: conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
                for t in BUSINESS_TABLES}
    finally:
        conn.close()


OFFICIAL_DB = content_mod.LEARNING_DB
OFFICIAL_DB_SHA = sha256_file(OFFICIAL_DB)
OFFICIAL_DB_COUNTS = business_counts(OFFICIAL_DB)
CONTENTPACK_SHA = sha256_file(content_mod.CONTENTPACK)


class StructureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.st = json.loads((TB / "textbook_structure_v2.json").read_text(encoding="utf-8"))
        cls.cat = json.loads((EX / "exercise_catalog_v3.json").read_text(encoding="utf-8"))
        cls.acts = cls.cat["activities"]

    def test_01_book_and_counts(self):
        self.assertEqual(self.st["book"]["textbook_id"], "FLTRP-EN-7A-2022CUR")
        c = self.st["counts"]
        self.assertEqual(c["units"], 7)
        self.assertGreaterEqual(c["sections"], 34)
        self.assertGreaterEqual(c["activities"], 157)
        self.assertGreaterEqual(c["questions"], 157)
        self.assertGreaterEqual(c["listening_activities"], 21)

    def test_02_unit_section_activity_chain(self):
        for u in self.st["units"]:
            if u["kind"] != "unit":
                continue
            for s in u["sections"]:
                for a in s["activities"]:
                    self.assertTrue(a["instruction"])
                    self.assertIsNotNone(a["activity_no"])
                    self.assertTrue(u["pages"][0] <= a["pdf_page"] <= u["pages"][1])

    def test_03_no_duplicate_activity_number_in_section(self):
        seen = set()
        for u in self.st["units"]:
            for s in u["sections"]:
                for a in s["activities"]:
                    key = (u["unit_code"], s["section_key"], a["activity_no"])
                    self.assertNotIn(key, seen, "同一板块活动编号重复：%s" % (key,))
                    seen.add(key)

    def test_04_structure_has_grammar_and_phonetics_evidence(self):
        units = [u for u in self.st["units"] if u["kind"] == "unit"]
        self.assertTrue(any(u.get("grammar_pointers") for u in units))
        self.assertTrue(any(u.get("phonetics_in_use") for u in units))


class VisualTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vis = json.loads((TB / "textbook_visual_relations_v2.json").read_text(encoding="utf-8"))

    def test_01_objects_have_role_and_evidence(self):
        self.assertGreater(len(self.vis["objects"]), 500)
        for o in self.vis["objects"]:
            self.assertIn(o["visual_role"], VISUAL_ROLES, o["visual_id"])
            self.assertTrue(o["role_evidence"])
            if o["visual_role"] == "unknown":
                self.assertEqual(o["review_status"], "NEEDS_REVIEW")
            else:
                self.assertEqual(o["review_status"], "OK")

    def test_02_no_object_is_invented(self):
        for o in self.vis["objects"]:
            self.assertTrue(8 <= o["page"] <= 114, o["visual_id"])
            self.assertEqual(len(o["bbox"]), 4)

    def test_03_blank_lines_and_icons_present(self):
        stats = self.vis["counts"]
        self.assertGreaterEqual(stats["blank_lines"], 100)
        self.assertGreaterEqual(stats["icons"], 21)
        self.assertGreaterEqual(stats["images"], 50)


class ContextTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx = json.loads((TB / "textbook_context_relations_v2.json")
                             .read_text(encoding="utf-8"))
        cls.content = json.loads((TB / "textbook_content_relations_v2.json")
                                 .read_text(encoding="utf-8"))

    def test_01_relations_are_typed_and_evidenced(self):
        self.assertGreater(len(self.ctx["relations"]), 1000)
        for r in self.ctx["relations"]:
            self.assertIn(r["relation"], RELATION_TYPES, r["relation"])
            self.assertTrue(r["evidence"])
            self.assertIn(r["review_status"], ("OK", "NEEDS_REVIEW"))

    def test_02_contains_and_order_relations_exist(self):
        kinds = {r["relation"] for r in self.ctx["relations"]}
        for k in ("contains", "belongs_to", "precedes", "follows"):
            self.assertIn(k, kinds)

    def test_03_content_relations_built_from_textbook(self):
        self.assertGreater(len(self.content["vocabulary_in"]), 50)
        self.assertTrue(self.content["grammar_in"])
        self.assertTrue(self.content["text_references"])
        for g in self.content["grammar_in"]:
            if g["relation"] == "grammar_in":
                self.assertGreaterEqual(g["appendices_page"], 100)


class AudioTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.map = json.loads((AU / "exercise_audio_map_v3.json").read_text(encoding="utf-8"))
        cls.qrel = json.loads((AU / "audio_question_relations_v3.json")
                              .read_text(encoding="utf-8"))

    def test_01_all_54_audio_confirmed_with_evidence(self):
        self.assertEqual(self.map["count"], 54)
        for e in self.map["audio"]:
            self.assertEqual(e["status"], "CONFIRMED", e["filename"])
            self.assertTrue(e["reason"])
            self.assertTrue(e["evidence"])
            self.assertIn(e["audio_scope"], ("activity", "section"))

    def test_02_audio_files_and_pdf_unchanged(self):
        for e in self.map["audio"]:
            p = TEXTBOOK_DIR / e["filename"]
            self.assertTrue(p.is_file(), p)
            self.assertEqual(sha256_file(p), e["sha256"], "原始 MP3 被修改：%s" % p.name)
        st = json.loads((TB / "textbook_structure_v2.json").read_text(encoding="utf-8"))
        self.assertEqual(sha256_file(PDF), st["book"]["pdf_sha256"], "原始 PDF 被修改")

    def test_03_audio_question_scope_marked(self):
        self.assertGreater(len(self.qrel["relations"]), 50)
        for r in self.qrel["relations"]:
            self.assertEqual(r["scope"], "activity")
            self.assertIn("不伪造", r["note"])
            self.assertTrue(r["question_id"].startswith("Q:"))


class QuestionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.q = json.loads((EX / "exercise_question_relations_v3.json").read_text(encoding="utf-8"))
        cls.cat = json.loads((EX / "exercise_catalog_v3.json").read_text(encoding="utf-8"))
        cls.ev = json.loads((AI / "textbook_evidence_map_v1.json").read_text(encoding="utf-8"))
        cls.audit = json.loads(AUDIT.read_text(encoding="utf-8"))

    def test_01_questions_have_full_scope(self):
        types = {a["question_type"] for a in self.cat["activities"]}
        for q in self.q["questions"]:
            self.assertTrue(q["unit"] and q["section"] and q["activity_id"])
            self.assertTrue(q["text"])
            self.assertIn(q["question_type"], types)

    def test_02_question_types_not_flattened(self):
        types = {a["question_type"] for a in self.cat["activities"]}
        for t in ("choice", "fill", "match", "short_answer"):
            self.assertIn(t, types, "题型被压平：%s" % t)
        self.assertGreaterEqual(len(types), 6)

    def test_03_blank_counts_evidence(self):
        fill = [a for a in self.cat["activities"] if a["question_type"] == "fill"]
        self.assertGreater(len(fill), 20)
        missing = [a for a in fill if a["blank_count"] == 0]
        issues = self.audit["consistency"]["issues"]
        reported = {i["ids"][0] for i in issues if i["detail"].startswith("填空类活动")}
        for a in missing:
            self.assertIn(a["activity_id"], reported,
                          "未识别空线的填空活动必须被记录：%s" % a["activity_id"])
        self.assertLessEqual(len(missing), 3)

    def test_04_options_keep_textbook_labels(self):
        for a in self.cat["activities"]:
            for o in a.get("options") or []:
                self.assertIn(o["label"], "abcdABCD", "选项标签被改写：%s" % o)

    def test_05_no_answer_invented(self):
        for q in self.q["questions"]:
            self.assertEqual(q["answer_source"], "NO_RELIABLE_SOURCE")
            self.assertNotIn("answer", q)

    def test_06_evidence_packages_complete(self):
        self.assertEqual(self.ev["package_count"], len(self.q["questions"]))
        for p in self.ev["packages"][:200]:
            for key in ("scope", "textbook_reference", "original_question",
                        "related_listening", "related_image", "answer_source", "ai_rules"):
                self.assertIn(key, p)
            self.assertEqual(p["answer_source"], "NO_RELIABLE_SOURCE")
            self.assertTrue(p["ai_rules"])

    def test_07_consistency_report_written(self):
        self.assertIn("by_kind", self.audit["consistency"])
        self.assertIn("model_assessment", self.audit)
        for kind in ("KEEP", "EXTEND", "REBUILD"):
            self.assertTrue(self.audit["model_assessment"][kind])


class SafetyTest(unittest.TestCase):
    def test_01_learning_db_untouched(self):
        self.assertEqual(sha256_file(OFFICIAL_DB), OFFICIAL_DB_SHA)
        self.assertEqual(business_counts(OFFICIAL_DB), OFFICIAL_DB_COUNTS)

    def test_02_contentpack_untouched(self):
        self.assertEqual(sha256_file(content_mod.CONTENTPACK), CONTENTPACK_SHA)

    def test_03_no_ai_or_network(self):
        import ai_grading
        self.assertFalse(ai_grading.ai_configured())
        self.assertEqual(ai_grading.analyze_short_answer("Q?", "A.")["ai_status"],
                         "not_connected")

    def test_04_boundaries_declared(self):
        audit = json.loads(AUDIT.read_text(encoding="utf-8"))
        b = audit["boundaries"]
        self.assertFalse(b["pdf_modified"])
        self.assertFalse(b["mp3_modified"])
        self.assertFalse(b["learning_db_touched"])
        self.assertFalse(b["contentpack_modified"])
        self.assertEqual(b["ai_calls"], 0)


if __name__ == "__main__":
    unittest.main()
