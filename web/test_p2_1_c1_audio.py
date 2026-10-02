#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-1-C1「教材之声」测试（stdlib unittest，无新依赖）

覆盖任务书 §十五 要求的验证点：
  * Vocabulary 教材顺序（reading_order，而不是页号+词形）
  * 黑体重点词加粗 / 白体词普通字重且不再显示"认识即可"说明
  * NEED_REVIEW 不暴露任何内部数据治理语言
  * 数据修正：Starter `yourself`、Unit 2 `smile`
  * 派生词音频：Starter 32 条 / Unit 1 35 条，来源标注 derived_from_official_unit_audio
  * 整单元词汇音频、Phonetics、Reading/Listening 官方音频接入
  * 音频端点（Range、MIME、404、路径穿越防护）
  * 原始 MP3 未被修改、learning.db / contentpack 不被测试写入

所有 HTTP 流程都只写 %TEMP% 的 learning.db 副本。
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
import audio as audio_mod               # noqa: E402
import content as content_mod           # noqa: E402
import flow as flow_mod                 # noqa: E402
import ui                               # noqa: E402

BASE = HERE.parent
DERIVED = BASE / "structured" / "audio" / "derived"
MANIFEST = DERIVED / "word_audio_manifest.json"


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


class VocabularyOrderAndDisplayTest(unittest.TestCase):
    """C1-01 / C1-03：教材顺序 + 黑体/白体显示。"""

    @classmethod
    def setUpClass(cls):
        cls.cp = content_mod._ro(content_mod.CONTENTPACK)

    @classmethod
    def tearDownClass(cls):
        cls.cp.close()

    def _item(self, text):
        return self.cp.execute(
            "SELECT item_id, canonical_text, phonetic, part_of_speech, meaning_zh, "
            "learning_requirement FROM learning_item WHERE item_type='vocabulary' "
            "AND canonical_text=?", (text,)).fetchone()

    # ---- 1：教材顺序 -------------------------------------------------------
    def test_01_vocabulary_follows_printed_wordlist_order(self):
        starter = content_mod.list_unit_resources("starter", "vocabulary")
        words = [i["text"] for i in starter["items"]]
        self.assertEqual(len(words), 32, "Starter 教材词表应为 32 条")
        self.assertEqual(words[:6], ["ready", "textbook", "eraser", "junior high",
                                     "geography", "biology"])
        self.assertEqual(words[-4:], ["nervous", "join", "team", "take part in"])
        # yourself 在教材词表中的位置：introduce 之后、hobby 之前
        self.assertLess(words.index("introduce"), words.index("yourself"))
        self.assertLess(words.index("yourself"), words.index("hobby"))
        orders = [i["order"] for i in starter["items"]]
        self.assertEqual(orders, sorted(orders))
        for item in starter["items"]:
            self.assertTrue(item["order"], "每条都必须有教材词表顺序证据")

    def test_02_unit1_and_unit2_order_and_counts(self):
        u1 = content_mod.list_unit_resources("unit1", "vocabulary")
        self.assertEqual(len(u1["items"]), 35)
        self.assertEqual(u1["items"][0]["text"], "without")
        u2 = content_mod.list_unit_resources("unit2", "vocabulary")
        self.assertEqual(len(u2["items"]), 45)
        self.assertIn("smile", [i["text"] for i in u2["items"]])

    # ---- 2：黑体 / 白体显示 ------------------------------------------------
    def test_03_core_is_bold_recognition_is_plain(self):
        rows = {}
        for text, kind in (("ready", "core"), ("textbook", "plain")):
            item = self._item(text)
            rows[text] = item
            self.assertEqual(item["learning_requirement"],
                             "CORE" if kind == "core" else "RECOGNITION")
        html = ui.resource_list_page({
            "unit": {"slug": "starter", "unit_code": "Starter", "title": "t"},
            "kind": "vocabulary", "label": "词汇", "unmapped_count": 0,
            "has_study": True, "items": [
                {"item_id": rows["ready"]["item_id"], "key": flow_mod.item_key(rows["ready"]["item_id"]),
                 "text": "ready", "phonetic": None, "part_of_speech": None, "meaning": None,
                 "can_study": True, "status_label": "", "order": (155, 2)},
                {"item_id": rows["textbook"]["item_id"],
                 "key": flow_mod.item_key(rows["textbook"]["item_id"]),
                 "text": "textbook", "phonetic": None, "part_of_speech": None, "meaning": None,
                 "can_study": False, "status_label": "", "order": (155, 3)}]})
        self.assertIn('class="w core">ready<', html)
        self.assertIn('class="w plain">textbook<', html)
        # C1-01：白体词不再有任何解释性标签
        for token in ("认识一下", "暂不需要专门学习", "普通词", "非重点"):
            self.assertNotIn(token, html)

    def test_04_no_internal_governance_language_on_page(self):
        """孩子端页面不得出现内部治理语言（源码注释不算，渲染结果才算）。"""
        src = (HERE / "flow.py").read_text(encoding="utf-8")
        self.assertNotIn("UNAVAILABLE_NOTES", src, "内部说明表必须已移除")
        html = ui.resource_list_page({
            "unit": {"slug": "unit6", "unit_code": "Unit 6", "title": "Fantastic friends"},
            "kind": "vocabulary", "label": "词汇", "unmapped_count": 0, "has_study": False,
            "items": [{"item_id": "FLTRP-EN-7A-2022CUR:V:X", "key": "k", "text": "peaceful",
                       "phonetic": None, "part_of_speech": None, "meaning": None,
                       "can_study": False, "status_label": "", "order": (162, 13)}]})
        self.assertIn("peaceful", html)
        for token in ("教材确认", "审核", "NEED_REVIEW", "待确认", "暂时不能学习"):
            self.assertNotIn(token, html, "孩子端不得出现内部治理语言：%s" % token)


class DataFixTest(unittest.TestCase):
    """C1-02：`yourself` 补回、`smile` 归位。"""

    @classmethod
    def setUpClass(cls):
        cls.cp = content_mod._ro(content_mod.CONTENTPACK)
        cls.attribution = content_mod._attribution(cls.cp)

    @classmethod
    def tearDownClass(cls):
        cls.cp.close()

    def test_01_yourself_restored_with_textbook_evidence(self):
        row = self.cp.execute(
            "SELECT item_id, item_type, phonetic, part_of_speech, meaning_zh, "
            "learning_requirement, display_text FROM learning_item "
            "WHERE canonical_text='yourself'").fetchone()
        self.assertIsNotNone(row, "教材 Starter 词表中的 yourself 必须存在")
        self.assertEqual(row["item_type"], "vocabulary")
        self.assertEqual(row["phonetic"], "/jɔːˈself/")
        self.assertEqual(row["part_of_speech"], "pron")
        self.assertEqual(row["meaning_zh"], "你自己")
        self.assertEqual(row["learning_requirement"], "CORE")     # 教材黑体
        info = self.attribution[row["item_id"]]
        self.assertEqual(info["unit_code"], "Starter")
        self.assertEqual(info["page"], 9)
        refs = self.cp.execute("SELECT source_id FROM source_ref WHERE item_id=?",
                               (row["item_id"],)).fetchall()
        self.assertIn("FLTRP-EN-7A-2022CUR:P155:B30", [r["source_id"] for r in refs])

    def test_02_introduce_no_longer_absorbs_yourself(self):
        row = self.cp.execute("SELECT item_id, meaning_zh, display_text FROM learning_item "
                              "WHERE canonical_text='introduce'").fetchone()
        self.assertEqual(row["meaning_zh"], "介绍")
        self.assertNotIn("你自己", row["display_text"])
        refs = [r["source_id"] for r in self.cp.execute(
            "SELECT source_id FROM source_ref WHERE item_id=?", (row["item_id"],))]
        self.assertNotIn("FLTRP-EN-7A-2022CUR:P155:B31", refs)

    def test_03_smile_belongs_to_unit2(self):
        row = self.cp.execute("SELECT item_id, meaning_zh FROM learning_item "
                              "WHERE canonical_text='smile'").fetchone()
        self.assertEqual(self.attribution[row["item_id"]]["unit_code"], "Unit 2")
        self.assertEqual(row["meaning_zh"], "笑容")
        refs = [r["source_id"] for r in self.cp.execute(
            "SELECT source_id FROM source_ref WHERE item_id=?", (row["item_id"],))]
        self.assertIn("FLTRP-EN-7A-2022CUR:P157:B15", refs)       # 属于 smile 的续行

    def test_04_yard_no_longer_absorbs_yourself(self):
        row = self.cp.execute("SELECT display_text FROM learning_item "
                              "WHERE canonical_text='yard'").fetchone()
        self.assertNotIn("你自己", row["display_text"])

    def test_05_contentpack_integrity(self):
        conn = sqlite3.connect("file:%s?mode=ro" % content_mod.CONTENTPACK.as_posix(), uri=True)
        try:
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(len(conn.execute("PRAGMA foreign_key_check").fetchall()), 0)
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM learning_item WHERE item_type='vocabulary'").fetchone()[0],
                288)
        finally:
            conn.close()


class DerivedWordAudioTest(unittest.TestCase):
    """C1-05：Starter / Unit 1 派生词音频（独立资源 + 来源标注 + 时间轴）。"""

    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.cp = content_mod._ro(content_mod.CONTENTPACK)

    @classmethod
    def tearDownClass(cls):
        cls.cp.close()

    def test_01_manifest_declares_derivation(self):
        self.assertEqual(self.manifest["derivation"], "derived_from_official_unit_audio")
        self.assertIn("不是官方独立单词音频", self.manifest["notice"])

    def test_02_starter_and_unit1_slice_counts(self):
        units = self.manifest["units"]
        self.assertEqual(len(units["Starter"]["words"]), 32)
        self.assertEqual(len(units["Unit 1"]["words"]), 35)
        # 派生音频必须真实存在且是合法 WAV
        for unit in units.values():
            for item in unit["words"]:
                path = DERIVED / item["path"]
                self.assertTrue(path.is_file(), "缺少派生音频：%s" % path)
                with wave.open(str(path), "rb") as w:
                    ms = int(w.getnframes() / w.getframerate() * 1000)
                self.assertLessEqual(abs(ms - item["duration_ms"]), 60,
                                     "切片时长必须与清单一致：%s" % item["canonical_text"])

    def test_03_time_axis_is_ordered_and_inside_source(self):
        for unit in self.manifest["units"].values():
            source_ms = unit["source_duration_ms"]
            last_end = -1
            for item in unit["words"]:
                self.assertGreater(item["start_ms"], last_end, "切片不得重叠")
                self.assertLess(item["end_ms"], source_ms, "切片必须落在源音频内")
                self.assertEqual(item["end_ms"] - item["start_ms"], item["duration_ms"])
                last_end = item["end_ms"]
                self.assertEqual(item["derivation"], "derived_from_official_unit_audio")
                self.assertEqual(item["source_audio_id"].split(":")[-1],
                                 unit["audio_id"].split(":")[-1])

    def test_04_slices_map_to_real_vocabulary(self):
        for unit_code, unit in self.manifest["units"].items():
            for item in unit["words"]:
                row = self.cp.execute("SELECT canonical_text FROM learning_item WHERE item_id=?",
                                      (item["item_id"],)).fetchone()
                self.assertIsNotNone(row, "派生音频必须指向真实词条：%s" % item["item_id"])
                self.assertEqual(row["canonical_text"], item["canonical_text"])

    def test_05_source_mp3_untouched(self):
        for unit in self.manifest["units"].values():
            asset = self.cp.execute("SELECT filename, sha256, size_bytes FROM audio_asset "
                                    "WHERE audio_id=?", (unit["audio_id"],)).fetchone()
            path = audio_mod.OFFICIAL_AUDIO_DIRS[0] / Path(asset["filename"]).name
            self.assertTrue(path.is_file())
            self.assertEqual(sha256_file(path), asset["sha256"].upper(),
                             "原始教材 MP3 不得被修改")


class UnitAudioCatalogTest(unittest.TestCase):
    """C1-07 / C1-08 / C1-09：整单元词表 / Phonetics / Reading / Listening 接入。"""

    def test_01_unit1_has_all_four_kinds(self):
        kinds = [i["kind"] for i in audio_mod.unit_audio("Unit 1")]
        self.assertEqual(kinds, ["word_list", "phonetics", "reading", "listening"])

    def test_02_word_list_audio_for_all_seven_units(self):
        for unit in ("Starter", "Unit 1", "Unit 2", "Unit 3", "Unit 4", "Unit 5", "Unit 6"):
            items = [i for i in audio_mod.unit_audio(unit) if i["kind"] == "word_list"]
            self.assertEqual(len(items), 1, "%s 必须有整单元词汇音频" % unit)
            self.assertIn("官方整单元词汇音频", items[0]["note"])

    def test_03_phonetics_audio_for_six_units(self):
        for unit in ("Unit 1", "Unit 2", "Unit 3", "Unit 4", "Unit 5", "Unit 6"):
            items = [i for i in audio_mod.unit_audio(unit) if i["kind"] == "phonetics"]
            self.assertEqual(len(items), 1, "%s 必须有 Phonetics in use 音频" % unit)

    def test_04_classification_uses_only_real_filenames(self):
        cp = content_mod._ro(content_mod.CONTENTPACK)
        try:
            names = [r["filename"] for r in cp.execute("SELECT filename FROM audio_asset")]
        finally:
            cp.close()
        counts = {}
        for name in names:
            counts[audio_mod.classify(name)] = counts.get(audio_mod.classify(name), 0) + 1
        self.assertEqual(counts["word_list"], 7)
        self.assertEqual(counts["phonetics"], 6)
        self.assertEqual(counts["reading"], 12)
        self.assertEqual(counts["listening"], 18)
        self.assertEqual(sum(counts.values()), 54)

class AudioHttpTest(unittest.TestCase):
    """音频端点 + Vocabulary Study 发音（真实 HTTP，临时 learning.db 副本）。"""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="zhixue_p21c1_"))
        cls.tmp_db = cls.tmpdir / "learning.db"
        shutil.copyfile(content_mod.LEARNING_DB, cls.tmp_db)
        web_app.Handler.learning_db = cls.tmp_db
        web_app.Handler.contentpack_path = content_mod.CONTENTPACK
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), web_app.Handler)
        cls.port = cls.srv.server_address[1]
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()
        cp = content_mod._ro(content_mod.CONTENTPACK)
        cls.with_audio = cp.execute("SELECT item_id, canonical_text FROM learning_item "
                                    "WHERE item_type='vocabulary' AND canonical_text='ready'").fetchone()
        cls.without_audio = cp.execute("SELECT item_id, canonical_text FROM learning_item "
                                       "WHERE item_type='vocabulary' AND canonical_text='electric'").fetchone()
        cp.close()

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

    def _url(self, path):
        return "http://127.0.0.1:%d%s" % (self.port, path)

    def _get(self, path, range_header=None):
        req = urllib.request.Request(self._url(path))
        if range_header:
            req.add_header("Range", range_header)
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.status, r.read(), dict(r.headers)
        except urllib.error.HTTPError as e:
            return e.code, e.read(), dict(e.headers)

    def _study(self, word):
        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        key = flow_mod.item_key(word["item_id"])
        body = urllib.parse.urlencode({"name": "音频测试", "pick": key}).encode("utf-8")
        req = urllib.request.Request(self._url("/vocabulary/study"), data=body,
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        with opener.open(req, timeout=15) as r:
            return r.read().decode("utf-8")

    # ---- 1：官方音频端点 ---------------------------------------------------
    def test_01_official_audio_endpoint(self):
        status, body, headers = self._get("/audio/official/AU48.mp3")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Content-Type"), "audio/mpeg")
        self.assertGreater(len(body), 1_000_000)
        self.assertEqual(headers.get("Accept-Ranges"), "bytes")

    def test_02_range_request(self):
        status, body, headers = self._get("/audio/official/AU48.mp3", "bytes=1000-2999")
        self.assertEqual(status, 206)
        self.assertEqual(len(body), 2000)
        self.assertTrue(headers.get("Content-Range", "").startswith("bytes 1000-2999/"))

    def test_03_word_audio_endpoint(self):
        item = audio_mod.word_audio_index()[flow_mod.item_key(self.with_audio["item_id"])]
        status, body, headers = self._get(item["url"])
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Content-Type"), "audio/wav")
        self.assertEqual(len(body), (DERIVED / item["path"]).stat().st_size)

    def test_04_unknown_audio_and_path_traversal_are_404(self):
        for path in ("/audio/official/AU99.mp3", "/audio/word/deadbeef0000.wav",
                     "/audio/word/../../app.py", "/audio/official/../app.py"):
            status, _, _ = self._get(path)
            self.assertEqual(status, 404, path)

    # ---- 2：Study 页发音（孩子主动点击） ----------------------------------
    def test_05_study_page_has_pronunciation_player(self):
        html = self._study(self.with_audio)
        key = flow_mod.item_key(self.with_audio["item_id"])
        self.assertIn("/audio/word/%s.wav" % key, html)
        self.assertIn('preload="none"', html)
        self.assertNotIn("autoplay", html)
        for token in ("mp3", "start_ms", "end_ms", "source_ref", "FrutigerNext", "bbox",
                      "derived_from_official_unit_audio"):
            self.assertNotIn(token, html, "学习页不得暴露内部音频信息：%s" % token)

    def test_06_every_covered_word_has_derived_audio(self):
        """P2-2 起全部正式词条都有逐词音频（Unit 2 的 electric 同样有）。"""
        html = self._study(self.without_audio)
        key = flow_mod.item_key(self.without_audio["item_id"])
        self.assertIn("/audio/word/%s.wav" % key, html)
        self.assertIn(self.without_audio["canonical_text"], html)   # 学习闭环仍然正常

    # ---- 3：闭环不受影响 ---------------------------------------------------
    def test_07_flow_unchanged_after_audio(self):
        html = self._study(self.with_audio)
        self.assertIn("我看完了", html)
        self.assertIn("教材来源", html)

    # ---- 4：数据安全 -------------------------------------------------------
    def test_08_official_data_untouched(self):
        self.assertEqual(sha256_file(content_mod.LEARNING_DB), OFFICIAL_DB_SHA)
        self.assertEqual(sha256_file(content_mod.CONTENTPACK), CONTENTPACK_SHA)
        self.assertEqual(business_counts(content_mod.LEARNING_DB), OFFICIAL_DB_COUNTS,
                         "正式学习数据不得被本次测试修改或删除")

    def test_09_no_ai_or_network_in_audio_layer(self):
        src = (HERE / "audio.py").read_text(encoding="utf-8").lower()
        for token in ("openai", "deepseek", "ollama", "anthropic", "requests.",
                      "urllib.request", "http.client", "socket.", "transformers",
                      "torch", "tts", "asr", "whisper"):
            self.assertNotIn(token, src, "音频层不得调用 AI / 网络：%s" % token)


if __name__ == "__main__":
    unittest.main(verbosity=2)
