#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-3 测试：教材练习重建 + 听力严格匹配 + 真实题型 + 数据安全。

全部 HTTP 流程只写 %TEMP% 的 learning.db 副本；正式库 / contentpack / MP3 只读核对。
"""

from __future__ import annotations

import hashlib
import http.cookiejar
import json
import shutil
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True

import app as web_app                   # noqa: E402
import ai_grading                       # noqa: E402
import content as content_mod           # noqa: E402
import exercises as ex_mod              # noqa: E402
import ui                               # noqa: E402

BASE = HERE.parent
CATALOG_V2 = BASE / "structured" / "exercises" / "exercise_catalog_v2.json"
MAP_V2 = BASE / "structured" / "exercises" / "exercise_audio_map_v2.json"
AUDIT_MD = BASE / "audit" / "P2-3_exercise_rebuild.md"
AUDIT_JSON = BASE / "audit" / "P2-3_exercise_rebuild.json"
TEXTBOOK_DIR = BASE / "2025年度初一外研版英语教材"

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


OFFICIAL_DB_SHA = sha256_file(content_mod.LEARNING_DB)
OFFICIAL_DB_COUNTS = business_counts(content_mod.LEARNING_DB)
CONTENTPACK_SHA = sha256_file(content_mod.CONTENTPACK)


class ScanEvidenceTest(unittest.TestCase):
    """教材结构 + 音频证据链。"""

    @classmethod
    def setUpClass(cls):
        cls.cat = json.loads(CATALOG_V2.read_text(encoding="utf-8"))
        cls.map = json.loads(MAP_V2.read_text(encoding="utf-8"))
        cls.audit = json.loads(AUDIT_JSON.read_text(encoding="utf-8"))
        cls.by_id = {e["exercise_id"]: e for e in cls.cat["exercises"]}

    def test_01_catalog_is_rescanned_from_real_pdf(self):
        self.assertEqual(self.cat["rule_set"], "P2-3-exercise-rebuild-v1")
        self.assertIn("教材 PDF", self.cat["derivation"])
        self.assertGreaterEqual(len(self.cat["exercises"]), 157)
        self.assertEqual({e["unit"] for e in self.cat["exercises"]},
                         {"Starter", "Unit 1", "Unit 2", "Unit 3", "Unit 4",
                          "Unit 5", "Unit 6"})

    def test_02_structure_unit_section_activity(self):
        for e in self.cat["exercises"]:
            self.assertTrue(e["unit"])
            self.assertTrue(e["section"], e["exercise_id"])
            self.assertIsNotNone(e["exercise_no"])
            self.assertTrue(e["textbook_page"])
            self.assertTrue(e["instruction"])
            self.assertEqual(e["pdf_page"] - 5, e["textbook_page"])

    def test_03_activity_question_and_types(self):
        known = set(ex_mod.QUESTION_LABELS)
        for e in self.cat["exercises"]:
            self.assertIn(e["question_type"], known, e["exercise_id"])
            for q in e["questions"]:
                self.assertIn("no", q)
        types = {e["question_type"] for e in self.cat["exercises"]}
        for t in ("choice", "fill", "match", "short_answer"):
            self.assertIn(t, types, "教材真实题型不能被压平：%s" % t)

    def test_04_every_confirmed_audio_has_multi_evidence(self):
        confirmed = [m for m in self.map["mappings"] if m["status"] == "CONFIRMED"]
        self.assertGreater(len(confirmed), 0)
        for m in confirmed:
            ev = m["evidence"]
            if m["target_type"] == "activity":
                self.assertTrue(ev["unit_match"])
                self.assertTrue(ev["section_match"])
                self.assertTrue(ev["number_match"])
                strong = (ev["instruction_similarity"] >= 0.8
                          or ev.get("instruction_prefix_of_textbook")
                          or ev["listening_icon"])
                self.assertTrue(strong, m["filename"])
            elif m["kind"] == "phonetics":
                self.assertTrue(ev["heading_found"])
            elif m["kind"] == "word_list":
                self.assertGreaterEqual(ev["coverage"], 0.6)
                self.assertTrue(ev["appendix_order_consistent"])

    def test_05_needs_review_is_never_promoted(self):
        for m in self.map["mappings"]:
            self.assertIn(m["status"], ("CONFIRMED", "NEEDS_REVIEW"))
            if m["status"] != "CONFIRMED":
                self.assertIsNone(m.get("exercise_id"),
                                  "未确认的关系不得指向具体练习：%s" % m["filename"])

    def test_06_p2_2_leftovers_are_resolved_with_evidence(self):
        audit = self.audit["summary"]["delta_vs_p2_2"]
        self.assertEqual(audit["p2_2_unmatched"], 13)
        self.assertEqual(len(audit["p2_2_unmatched_resolved"]), 13)
        for r in audit["p2_2_unmatched_resolved"]:
            self.assertEqual(r["status"], "CONFIRMED")
            self.assertTrue(r["target"])

    def test_07_no_fabricated_answers(self):
        for e in self.cat["exercises"]:
            self.assertEqual(e["answer_status"], "NO_RELIABLE_SOURCE")
            self.assertNotIn("answer", e)
            for q in e["questions"]:
                self.assertNotIn("answer", q)

    def test_08_mp3_and_pdf_unchanged_since_scan(self):
        for a in self.audit["audio_files"]:
            p = TEXTBOOK_DIR / a["filename"]
            self.assertTrue(p.is_file(), p)
            self.assertEqual(sha256_file(p), a["sha256"], "原始 MP3 不得被修改：%s" % p.name)
        self.assertFalse(self.audit["boundaries"]["pdf_modified"])
        self.assertFalse(self.audit["boundaries"]["mp3_modified"])

    def test_09_audit_report_written(self):
        text = AUDIT_MD.read_text(encoding="utf-8")
        for token in ("教材扫描结果", "音频结果", "题型结果", "与 P2-2 对比", "数据安全"):
            self.assertIn(token, text)


class ExerciseUiTest(unittest.TestCase):
    """教材练习在 APP 里的呈现（真实题型，不伪造答案）。"""

    def _render(self, exercise):
        q = ex_mod.build_questions(exercise)
        html = ui.exercise_page({
            "exercise": exercise, "questions": q,
            "unit": {"slug": "unit1", "unit_code": exercise["unit"], "title": "t"},
            "key": "k", "type_labels": ex_mod.TYPE_LABELS,
            "audio_url": ex_mod.audio_url(exercise), "ask_name": False})
        return q, html

    def _first(self, qtype, **cond):
        for e in self.cat["exercises"]:
            if e["question_type"] != qtype:
                continue
            if all(e.get(k) == v for k, v in cond.items()):
                return e
        return None

    @classmethod
    def setUpClass(cls):
        cls.cat = json.loads(CATALOG_V2.read_text(encoding="utf-8"))

    def test_01_choice_renders_options_when_textbook_has_them(self):
        e = self._first("choice")
        self.assertIsNotNone(e)
        with_opts = next((x for x in self.cat["exercises"]
                          if x["question_type"] == "choice" and x["options"]), None)
        if with_opts is None:
            self.skipTest("教材选项为图片，无可渲染文本选项")
        q, html = self._render(with_opts)
        self.assertEqual(q["kind"], "choice")
        # 教材原题是「Read and tick」时用复选框（勾选），其余选择题用单选；
        # 两者都属于真实的选项控件。
        self.assertTrue('type="radio"' in html or 'type="checkbox"' in html)
        # P2-6-F-2：选项以教材原页 ☐ 清单为准（已过滤页眉 / 页脚噪声），
        # 不再直接使用目录里的错误选项值（例如 Starter A2 目录里的 a/b/c 属于同册另一个活动）。
        self.assertTrue(q["options"], "教材原题应渲染出选项")
        self.assertIn(q["options"][0]["text"][:12], html)

    def test_02_fill_renders_inputs_and_keeps_textbook_blanks(self):
        e = self._first("fill")
        q, html = self._render(e)
        self.assertEqual(q["kind"], "fill")
        self.assertIn("<input name=", html)
        self.assertEqual(len(q["questions"]), min(max(e["blanks"], 1), 8))

    def test_03_match_keeps_textbook_items(self):
        e = self._first("match")
        q, html = self._render(e)
        self.assertIn(q["kind"], ("match", "spelling"))
        if e["check_items"]:
            self.assertIn(e["check_items"][0][:10], html)

    def test_04_listening_uses_headphone_and_official_audio(self):
        e = next(x for x in self.cat["exercises"] if x["listening_icon"] and x["audio_id"])
        _q, html = self._render(e)

        body = html.split("<body>", 1)[-1]          # 只看页面正文，忽略 CSS 注释
        self.assertIn("🎧", body)
        self.assertIn("/audio/official/%s.mp3" % e["audio_id"].split(":")[-1], body)
        self.assertNotIn("🔊", body)

    def test_05_no_fake_grading_in_ui(self):
        e = self._first("fill")
        _q, html = self._render(e)
        for forbidden in ("正确", "错误", "得分", "分数", "满分"):
            self.assertNotIn(forbidden, html)


class ExerciseFlowTest(unittest.TestCase):
    """提交 → 真实学习记录（临时库）。"""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="zhixue_p23_"))
        cls.tmp_db = cls.tmpdir / "learning.db"
        shutil.copyfile(content_mod.LEARNING_DB, cls.tmp_db)
        web_app.Handler.learning_db = cls.tmp_db
        web_app.Handler.contentpack_path = content_mod.CONTENTPACK
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), web_app.Handler)
        cls.port = cls.srv.server_address[1]
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()
        cls.cat = json.loads(CATALOG_V2.read_text(encoding="utf-8"))
        cls.new_exercise = next(e for e in cls.cat["exercises"] if not e["in_contentpack_activity"])
        cls.listening = next(e for e in cls.cat["exercises"] if e["listening_icon"] and e["audio_id"])

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.thread.join(timeout=5)
        for _ in range(10):
            try:
                shutil.rmtree(cls.tmpdir)
                break
            except Exception:
                import time
                time.sleep(0.2)

    def _client(self):
        jar = http.cookiejar.CookieJar()
        return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def _get(self, opener, path):
        try:
            with opener.open("http://127.0.0.1:%d%s" % (self.port, path), timeout=15) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8")

    def _post(self, opener, path, data):
        body = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request("http://127.0.0.1:%d%s" % (self.port, path), data=body,
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        try:
            with opener.open(req, timeout=15) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8")

    def _records(self):
        conn = sqlite3.connect("file:%s?mode=ro" % self.tmp_db.as_posix(), uri=True)
        try:
            return {r[0]: (r[1], r[2], r[3]) for r in conn.execute(
                "SELECT record_id, activity_type, result, item_id FROM learning_record")}
        finally:
            conn.close()

    def test_01_recovered_activity_is_openable(self):
        key = ex_mod.exercise_key(self.new_exercise["exercise_id"])
        st, body = self._get(self._client(), "/exercise/%s" % key)
        self.assertEqual(st, 200)
        self.assertIn(self.new_exercise["instruction"][:20], body)
        self.assertIn("教材原题", body)

    def test_02_submit_records_real_behavior(self):
        key = ex_mod.exercise_key(self.listening["exercise_id"])
        opener = self._client()
        before = business_counts(self.tmp_db)
        before_ids = set(self._records())
        st, body = self._post(opener, "/exercise/%s/submit" % key,
                              {"name": "教材练习小朋友", "self_check": "done"})
        self.assertEqual(st, 200)
        after = business_counts(self.tmp_db)
        self.assertEqual(after["learning_record"], before["learning_record"] + 1)
        self.assertEqual(after["learning_session"], before["learning_session"] + 1)
        new_ids = set(self._records()) - before_ids
        self.assertEqual(len(new_ids), 1)
        row = self._records()[new_ids.pop()]
        self.assertEqual(row[2], self.listening["exercise_id"])
        self.assertIn(row[0], ("listen", "read", "understand", "recognize", "produce", "repeat"))

    def test_03_answer_is_recorded_without_fabricated_mark(self):
        e = next(x for x in self.cat["exercises"] if x["question_type"] == "fill")
        key = ex_mod.exercise_key(e["exercise_id"])
        opener = self._client()
        st, body = self._post(opener, "/exercise/%s/submit" % key,
                              {"name": "教材练习小朋友", "q1": "textbook answer",
                               "self_check": "done"})
        self.assertEqual(st, 200)
        self.assertIn("自己核对", body)
        self.assertNotIn("写对", body)


class SafetyTest(unittest.TestCase):
    def test_01_official_data_untouched(self):
        self.assertEqual(sha256_file(content_mod.LEARNING_DB), OFFICIAL_DB_SHA)
        self.assertEqual(business_counts(content_mod.LEARNING_DB), OFFICIAL_DB_COUNTS)
        self.assertEqual(sha256_file(content_mod.CONTENTPACK), CONTENTPACK_SHA)

    def test_02_no_ai_calls(self):
        self.assertFalse(ai_grading.ai_configured())
        self.assertEqual(ai_grading.analyze_short_answer("Q?", "A.")["ai_status"],
                         "not_connected")

    def test_03_learning_db_schema_unchanged(self):
        conn = sqlite3.connect("file:%s?mode=ro" % Path(content_mod.LEARNING_DB).as_posix(),
                               uri=True)
        try:
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertGreaterEqual(len(tables), 7)
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(len(conn.execute("PRAGMA foreign_key_check").fetchall()), 0)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
