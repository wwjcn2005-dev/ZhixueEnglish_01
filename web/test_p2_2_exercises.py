#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-2 测试：教材练习体系 + 逐词音频 + 扬声器 UI + 数据安全。

全部 HTTP 流程只写 %TEMP% 的 learning.db 副本；正式库只读并做完整性核对。
"""

from __future__ import annotations

import hashlib
import http.cookiejar
import json
import re
import shutil
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
import wave
from http.server import ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True

import app as web_app                   # noqa: E402
import ai_grading                       # noqa: E402
import audio as audio_mod               # noqa: E402
import content as content_mod           # noqa: E402
import exercises as ex_mod              # noqa: E402
import ui                               # noqa: E402

BASE = HERE.parent
CATALOG = BASE / "structured" / "exercises" / "exercise_catalog.json"
MANIFEST = BASE / "structured" / "audio" / "derived" / "word_audio_manifest.json"
DERIVED = BASE / "structured" / "audio" / "derived"


def sha256_file(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


BUSINESS_TABLES = ("learner", "learning_session", "learning_task", "task_item",
                   "learning_record", "mastery_state")


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
FROZEN_SERVICES = {
    "learning_service.py": "01341A05231EFCA6E0C801CF95D8A96F3DF732753F1F679688D44708586DF1D6",
    "session_service.py": "0CF7A20615780831F544BDF295202028CE2EEFB15D234820CD1184AD4A6B665F",
    "activity_service.py": "AAFF907C869797EE697D5F756C7E03C62CEB942809B2406933761195DA092028",
    "behavior_service.py": "0C6EF4822F60D9251B68382C95A5D3D9987650811F4FC93C70875AF48249FC6D",
    "vocabulary_service.py": "D06DCC76A5A4CCAF5C0BC3C17BB33CFF5D6056B7C872406A3934223C8870D632",
    "resource_pool_service.py": "D4488E1FFBA6B553EB6932BE195932A4C464D9526790B138C0C55DAA612D2F37",
}


class CatalogTest(unittest.TestCase):
    """教材练习目录：来源可追溯、音频匹配真实、未确定不伪装。"""

    @classmethod
    def setUpClass(cls):
        cls.cat = json.loads(CATALOG.read_text(encoding="utf-8"))
        cls.cp = content_mod._ro(content_mod.CONTENTPACK)

    @classmethod
    def tearDownClass(cls):
        cls.cp.close()

    def test_01_catalog_covers_all_units(self):
        units = {e["unit"] for e in self.cat["exercises"]}
        self.assertEqual(units, {"Starter", "Unit 1", "Unit 2", "Unit 3", "Unit 4",
                                 "Unit 5", "Unit 6"})
        self.assertEqual(len(self.cat["exercises"]), 93)

    def test_02_every_exercise_has_page_and_instruction(self):
        for e in self.cat["exercises"]:
            self.assertTrue(e["instruction"])
            self.assertTrue(e["textbook_page"])
            self.assertIsNotNone(e["exercise_no"])
            self.assertIn(e["type"], ex_mod.TYPE_LABELS)

    def test_03_listening_icon_matches_listen_exactly(self):
        scan = json.loads((BASE / "audit" / "P2-2_exercise_audio_scan.json")
                          .read_text(encoding="utf-8"))
        self.assertTrue(scan["scan"]["icon_matches_listen_exactly"])
        self.assertEqual(scan["scan"]["listening_icon_hits"], 15)
        self.assertEqual(scan["scan"]["listen_instructions"], 15)

    def test_04_audio_links_point_to_real_assets(self):
        codes = {r["audio_id"] for r in self.cp.execute("SELECT audio_id FROM audio_asset")}
        for e in self.cat["exercises"]:
            if e["audio_id"]:
                self.assertIn(e["audio_id"], codes)
                self.assertIn(e["match_method"],
                              ("filename_activity_exact", "filename_activity_number"))

    def test_05_every_audio_required_exercise_is_matched_or_marked(self):
        for e in self.cat["exercises"]:
            if e["audio_required"]:
                self.assertTrue(e["audio_id"] or e["needs_review"],
                                "需要音频的练习必须有音频或标记 NEEDS_REVIEW：%s" % e["activity_id"])

    def test_06_exercise_items_and_refs_written(self):
        n = self.cp.execute("SELECT COUNT(*) FROM learning_item WHERE item_type='exercise'").fetchone()[0]
        # P2-2 的 93 条练习条目必须仍然存在（P2-3 在其之上补回 64 个真实教材活动 → 157 条）
        self.assertGreaterEqual(n, len(self.cat["exercises"]))
        rows = {r["display_text"] for r in self.cp.execute(
            "SELECT display_text FROM learning_item WHERE item_type='exercise'")}
        for e in self.cat["exercises"]:
            self.assertIn(e["instruction"], rows)
        refs = self.cp.execute("SELECT COUNT(*) FROM source_ref WHERE item_type='learning_item' "
                               "AND source_type='activity'").fetchone()[0]
        # P2-3 补回的教材活动在 contentpack 里没有 activity 行，其来源是教材页本身
        all_refs = self.cp.execute(
            "SELECT COUNT(*) FROM source_ref sr JOIN learning_item li ON li.item_id=sr.item_id "
            "WHERE li.item_type='exercise'").fetchone()[0]
        self.assertGreaterEqual(refs, len(self.cat["exercises"]))
        self.assertEqual(all_refs, n)

    def test_07_audio_mapping_rows_are_matched_with_evidence(self):
        rows = [dict(r) for r in self.cp.execute(
            "SELECT * FROM audio_mapping WHERE target_type='activity'")]
        matched = [r for r in rows if r["mapping_status"] == "MATCHED"]
        self.assertGreaterEqual(len(matched), 28)
        for r in matched:
            self.assertTrue(r["basis"])
            self.assertIsNotNone(r["confidence"])
            self.assertIn("exercise_audio_scan", r["review_note"] or "")

    def test_08_unmatched_audio_is_reported_not_forced(self):
        scan = json.loads((BASE / "audit" / "P2-2_exercise_audio_scan.json")
                          .read_text(encoding="utf-8"))
        self.assertEqual(len(scan["scan"]["unresolved_audio"]), 13)
        forced = [e for e in self.cat["exercises"]
                  if e["audio_id"] and e["match_method"] == "sequence_inference"]
        self.assertEqual(forced, [], "不得使用未经证实的推断匹配")


class WordAudioCoverageTest(unittest.TestCase):
    """P2-2：Starter + Unit 1–6 全部正式词条都有逐词音频。"""

    @classmethod
    def setUpClass(cls):
        cls.man = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.cp = content_mod._ro(content_mod.CONTENTPACK)

    @classmethod
    def tearDownClass(cls):
        cls.cp.close()

    def test_01_all_units_present(self):
        self.assertEqual(set(self.man["units"]),
                         {"Starter", "Unit 1", "Unit 2", "Unit 3", "Unit 4", "Unit 5", "Unit 6"})
        expect = {"Starter": 32, "Unit 1": 35, "Unit 2": 45, "Unit 3": 40,
                  "Unit 4": 45, "Unit 5": 46, "Unit 6": 45}
        for unit, n in expect.items():
            self.assertEqual(len(self.man["units"][unit]["words"]), n, unit)
        self.assertEqual(sum(len(u["words"]) for u in self.man["units"].values()), 288)

    def test_02_manifest_covers_every_vocabulary_item(self):
        items = {r["item_id"] for r in self.cp.execute(
            "SELECT item_id FROM learning_item WHERE item_type='vocabulary'")}
        covered = {w["item_id"] for u in self.man["units"].values() for w in u["words"]}
        self.assertEqual(covered, items)

    def test_03_slices_exist_and_match_manifest(self):
        for unit in self.man["units"].values():
            for w in unit["words"]:
                p = DERIVED / w["path"]
                self.assertTrue(p.is_file(), p)
                with wave.open(str(p), "rb") as f:
                    ms = int(f.getnframes() / f.getframerate() * 1000)
                self.assertLessEqual(abs(ms - w["duration_ms"]), 60, w["canonical_text"])
                self.assertEqual(w["derivation"], "derived_from_official_unit_audio")

    def test_04_segmentation_count_is_consistent(self):
        for unit in self.man["units"].values():
            seg = unit["segmentation"]
            self.assertEqual(seg["segments"], seg["words"] + seg["head_items"])

    def test_05_source_mp3_untouched(self):
        for unit in self.man["units"].values():
            asset = self.cp.execute("SELECT filename, sha256 FROM audio_asset WHERE audio_id=?",
                                    (unit["audio_id"],)).fetchone()
            p = audio_mod.OFFICIAL_AUDIO_DIRS[0] / Path(asset["filename"]).name
            self.assertEqual(sha256_file(p), asset["sha256"].upper())


class ExerciseUiTest(unittest.TestCase):
    """UI：扬声器图标、播放状态、删除整单元词汇入口。"""

    def test_02_vocabulary_list_uses_small_speaker(self):
        html = ui.resource_list_page({
            "unit": {"slug": "starter", "unit_code": "Starter", "title": "t"},
            "kind": "vocabulary", "label": "词汇", "unmapped_count": 0, "has_study": True,
            "items": [{"item_id": "X", "key": "k", "text": "ready", "phonetic": None,
                       "part_of_speech": None, "meaning": None, "can_study": True,
                       "status_label": "", "order": (155, 2),
                       "audio_url": "/audio/word/abc.wav"}]})
        self.assertIn('class="spk word"', html)
        self.assertIn("/audio/word/abc.wav", html)
        self.assertIn('preload="none"', html)
        self.assertNotIn("autoplay", html)
        body = re.sub(r"(?s)<style>.*?</style>", " ", html)
        self.assertNotIn("audiorow", body)          # 正文不再使用大块播放条
        # P2-3 实现：原生控件保持可点击但透明；上层是纯 CSS 扬声器 + 声波（详见 test_p2_3_audio_button.py）
        self.assertIn(".spk{position:relative;display:inline-block;width:40px;height:40px;"
                      "overflow:hidden;", ui.STYLE)
        self.assertIn("opacity:0;background:transparent", ui.STYLE)

    def test_03_study_page_speaker_and_source_moved_below_button(self):
        ctx = {"word": "ready", "phonetic": "/ˈredi/", "part_of_speech": "adj",
               "meaning": "准备好的", "session_id": "S1", "key": "k", "learner_id": "L1",
               "back_href": "/textbook", "source_unit_label": "Starter · Welcome",
               "source_list_label": "Words and expressions · 第 150 页",
               "word_audio_url": "/audio/word/abc.wav"}
        html = ui.study_page(ctx)
        self.assertIn('class="spk word"', html)
        self.assertLess(html.index("我看完了"), html.index("教材来源"))
        self.assertNotIn("autoplay", html)

    def test_04_no_gamification_words(self):
        for forbidden in ("积分", "排名", "徽章", "连胜", "闯关", "五星"):
            self.assertNotIn(forbidden, ui.STYLE)


class ExerciseFlowTest(unittest.TestCase):
    """教材练习闭环：打开 → 作答 → 提交 → 结果（真实 HTTP，临时库）。"""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="zhixue_p22_"))
        cls.tmp_db = cls.tmpdir / "learning.db"
        shutil.copyfile(content_mod.LEARNING_DB, cls.tmp_db)
        web_app.Handler.learning_db = cls.tmp_db
        web_app.Handler.contentpack_path = content_mod.CONTENTPACK
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), web_app.Handler)
        cls.port = cls.srv.server_address[1]
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()
        cls.listening = next(e for e in ex_mod.exercises_of_unit("Unit 1")
                             if e["type"] == "listening" and e["audio_id"])
        cls.vocab = next(e for e in ex_mod.exercises_of_unit("Unit 1")
                         if e["type"] == "vocabulary")
        cls.reading = next(
            (e for u in ("Unit 1", "Unit 2", "Unit 3", "Unit 4", "Unit 5", "Unit 6")
             for e in ex_mod.exercises_of_unit(u)
             if e["type"] == "reading" and ex_mod.sub_questions(e["pdf_page"])), None)

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
        """{record_id: (activity_type, result, item_id)}（用集合差集取本次新增，避免同秒 tie-break）"""
        conn = sqlite3.connect("file:%s?mode=ro" % self.tmp_db.as_posix(), uri=True)
        try:
            return {r[0]: (r[1], r[2], r[3]) for r in conn.execute(
                "SELECT record_id, activity_type, result, item_id FROM learning_record")}
        finally:
            conn.close()

    def test_01_exercise_list_shows_catalog(self):
        st, body = self._get(self._client(), "/unit/unit1/exercises")
        self.assertEqual(st, 200)
        self.assertIn("教材练习", body)
        self.assertIn("教材第", body)
        self.assertIn("/exercise/", body)
        self.assertNotIn("NEEDS_REVIEW", body)

    def test_02_listening_exercise_has_official_audio(self):
        key = ex_mod.exercise_key(self.listening["exercise_id"])
        st, body = self._get(self._client(), "/exercise/%s" % key)
        self.assertEqual(st, 200)
        code = self.listening["audio_id"].split(":")[-1]
        self.assertIn("/audio/official/%s.mp3" % code, body)
        self.assertIn(self.listening["instruction"][:20], body)
        self.assertIn("我完成了这次练习", body)

    def test_03_self_check_submit_records_listen_event(self):
        opener = self._client()
        key = ex_mod.exercise_key(self.listening["exercise_id"])
        before = business_counts(self.tmp_db)
        before_ids = set(self._records())
        st, body = self._post(opener, "/exercise/%s/submit" % key,
                              {"name": "练习小朋友", "self_check": "done"})
        self.assertEqual(st, 200)
        self.assertIn("这次练习", body)
        after = business_counts(self.tmp_db)
        self.assertEqual(after["learning_record"], before["learning_record"] + 1)
        self.assertEqual(after["learning_session"], before["learning_session"] + 1)
        new_ids = set(self._records()) - before_ids
        self.assertEqual(len(new_ids), 1)
        row = self._records()[new_ids.pop()]
        conn = sqlite3.connect("file:%s?mode=ro" % self.tmp_db.as_posix(), uri=True)
        ended = conn.execute("SELECT ended_at FROM learning_session "
                             "ORDER BY started_at DESC LIMIT 1").fetchone()[0]
        conn.close()
        self.assertEqual(row[0], "listen")
        self.assertEqual(row[1], "done")
        self.assertEqual(row[2], self.listening["exercise_id"])
        self.assertIsNotNone(ended, "提交后会话应正常结束")

    def test_04_spelling_exercise_is_rule_graded(self):
        opener = self._client()
        self._post(opener, "/exercise/%s/submit" % ex_mod.exercise_key(self.listening["exercise_id"]),
                   {"name": "练习小朋友", "self_check": "done"})
        key = ex_mod.exercise_key(self.vocab["exercise_id"])
        st, body = self._get(opener, "/exercise/%s" % key)
        self.assertEqual(st, 200)
        q = ex_mod.build_questions(self.vocab)
        self.assertEqual(q["kind"], "spelling")
        answers = {"name": "练习小朋友"}
        for item in q["questions"]:
            answers["q%d" % item["no"]] = item["answer"]
        before_ids = set(self._records())
        st, body = self._post(opener, "/exercise/%s/submit" % key, answers)
        self.assertEqual(st, 200)
        self.assertIn("写对", body)
        new_ids = set(self._records()) - before_ids
        row = self._records()[new_ids.pop()]
        self.assertEqual(row[0], "recognize")
        self.assertEqual(row[1], "correct")

    def test_05_wrong_spelling_is_marked_incorrect(self):
        opener = self._client()
        key = ex_mod.exercise_key(self.vocab["exercise_id"])
        q = ex_mod.build_questions(self.vocab)
        answers = {"name": "练习小朋友"}
        for item in q["questions"]:
            answers["q%d" % item["no"]] = "zzz"
        before_ids = set(self._records())
        st, body = self._post(opener, "/exercise/%s/submit" % key, answers)
        self.assertEqual(st, 200)
        self.assertIn("再看一眼", body)
        new_ids = set(self._records()) - before_ids
        row = self._records()[new_ids.pop()]
        self.assertEqual(row[1], "incorrect")

    def test_06_short_answer_gets_rule_analysis_without_ai(self):
        if self.reading is None:
            self.skipTest("Unit 1 没有阅读练习")
        opener = self._client()
        key = ex_mod.exercise_key(self.reading["exercise_id"])
        st, body = self._get(opener, "/exercise/%s" % key)
        self.assertEqual(st, 200)
        q = ex_mod.build_questions(self.reading)
        if q["kind"] != "short_answer":
            self.skipTest("该阅读练习没有教材理解题")
        answers = {"name": "练习小朋友"}
        for item in q["questions"]:
            answers["q%d" % item["no"]] = "i think it is because the writer is happy"
        st, body = self._post(opener, "/exercise/%s/submit" % key, answers)
        self.assertEqual(st, 200)
        self.assertIn("你的回答", body)
        self.assertTrue("可以再" in body or "提示" in body or "基本" in body)

    def test_07_no_ai_call_in_this_phase(self):
        self.assertFalse(ai_grading.ai_configured())
        res = ai_grading.analyze_short_answer("Why do you like English?", "I like it.")
        self.assertEqual(res["ai_status"], "not_connected")
        self.assertFalse(res["ai_available"])

    def test_08_unknown_exercise_is_natural_error(self):
        st, body = self._get(self._client(), "/exercise/deadbeef0000")
        self.assertEqual(st, 200)
        self.assertIn("没有找到这个练习", body)


class DataSafetyTest(unittest.TestCase):
    def test_01_official_data_untouched(self):
        self.assertEqual(sha256_file(content_mod.LEARNING_DB), OFFICIAL_DB_SHA)
        self.assertEqual(business_counts(content_mod.LEARNING_DB), OFFICIAL_DB_COUNTS,
                         "正式学习数据不得被本次测试修改或删除")
        self.assertEqual(sha256_file(content_mod.CONTENTPACK), CONTENTPACK_SHA)

    def test_02_frozen_services_unchanged(self):
        for name, expected in FROZEN_SERVICES.items():
            self.assertEqual(sha256_file(BASE / "learning" / name), expected, name)

    def test_03_no_ai_or_network_tokens(self):
        for name in ("audio.py", "exercises.py", "ai_grading.py"):
            src = (HERE / name).read_text(encoding="utf-8").lower()
            for token in ("openai", "deepseek", "ollama", "anthropic", "requests.",
                          "urllib.request", "http.client", "socket.", "tts", "asr"):
                self.assertNotIn(token, src, "%s 不得包含 AI/网络调用：%s" % (name, token))


if __name__ == "__main__":
    unittest.main(verbosity=2)
