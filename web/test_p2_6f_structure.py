#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-6-F-1 / F-2 / F-4 教材正文 + Question 结构 + 音频活动锚定（只读验证）

验证对象：
  * F-1 教材正文进入 Unit 页面（contentpack content_block 原文）
  * F-2 教材练习按原题型呈现（choice / fill / match / judge），不再降级成自评
  * F-4 题目按活动锚定（不再按页取题，不跨活动串题），音频仍是官方完整音频

边界：不写正式 learning.db；不调用 AI；不修改教材事实。
"""

from __future__ import annotations

import json
import sys
import threading
import unittest
import urllib.request
from pathlib import Path

BASE = Path(r"D:\ZhixueEnglish")
sys.path.insert(0, str(BASE / "web"))
sys.dont_write_bytecode = True

import content as content_mod        # noqa: E402
import exercises as ex_mod           # noqa: E402
import ui                            # noqa: E402

E10 = "FLTRP-EN-7A-2022CUR:X:1C4143922B1C"       # Starter GET_READY A10（Listen and choose.）
A9 = "FLTRP-EN-7A-2022CUR:X:ED3C7BD7A9AA"        # Starter GET_READY A9（Match the words…）


def _catalog():
    return json.loads(ex_mod.CATALOG.read_text(encoding="utf-8"))["exercises"]


class StructureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cat = _catalog()
        cls.by_id = {e["exercise_id"]: e for e in cls.cat}

    def _q(self, eid):
        return ex_mod.build_questions(self.by_id[eid])

    def _html(self, eid):
        e = self.by_id[eid]
        q = ex_mod.build_questions(e)
        return q, ui.exercise_page({
            "exercise": e, "questions": q,
            "unit": {"slug": "starter", "unit_code": e["unit"], "title": "t"},
            "key": "k", "type_labels": ex_mod.TYPE_LABELS,
            "audio_url": ex_mod.audio_url(e), "ask_name": False})

    # ---- Exercise 10 -----------------------------------------------------
    def test_01_exercise10_has_question_structure(self):
        q = self._q(E10)
        self.assertEqual(q["kind"], "choice")
        self.assertIsNotNone(q["textbook_task"])
        self.assertEqual(q["textbook_task"]["kind"], "choice")
        self.assertEqual(q["blanks"], 8)
        self.assertTrue(q["material"], "Exercise 10 应带上教材原题材料（对话 8 空）")
        self.assertIn("Nana", q["material"]["text"])

    def test_02_exercise10_has_options(self):
        q = self._q(E10)
        self.assertGreaterEqual(len(q["options"]), 8)
        texts = [o["text"] for o in q["options"]]
        self.assertIn("sports trousers", texts)
        _q, html = self._html(E10)
        self.assertIn("sports trousers", html)
        self.assertIn("教材本页词框", html)

    def test_03_exercise10_has_answer_control(self):
        _q, html = self._html(E10)
        self.assertIn('name="t1"', html)
        self.assertIn('name="t8"', html)
        self.assertIn("提交作答", html)

    def test_04_exercise10_audio_is_au03(self):
        e = self.by_id[E10]
        self.assertEqual(e["audio_id"], "FLTRP-EN-7A-2022CUR:AU03")
        self.assertEqual(ex_mod.audio_url(e), "/audio/official/AU03.mp3")
        _q, html = self._html(E10)
        self.assertIn("/audio/official/AU03.mp3", html)
        self.assertIn("🎧", html)

    # ---- 活动锚定（F-4）--------------------------------------------------
    def test_05_sub_questions_do_not_cross_activities(self):
        """同页不同活动不会互相串题：锚定失败时宁可不返回题目。"""
        for e in self.cat:
            if e["question_type"] != "short_answer":
                continue
            qs = ex_mod.sub_questions_for_activity(e)
            for text in qs:
                self.assertTrue(text.strip())
        # 旧接口（按页取题）在 Starter P15 会把 A3 的题给 A4；新接口必须为空
        a4 = next(x for x in self.cat if x["unit"] == "Starter"
                  and x["section"] == "GET_TO_KNOW_EACH_OTHER" and x["exercise_no"] == 4)
        self.assertEqual(ex_mod.sub_questions_for_activity(a4), [],
                         "A4（Read and check your answers）不应拿到同页 A3 的题")

    def test_06_a9_a10_anchoring_is_correct(self):
        q9 = self._q(A9)
        q10 = self._q(E10)
        self.assertEqual(q9["material"]["activity_id"], "FLTRP-EN-7A-2022CUR:STARTER:GET_READY:A9")
        self.assertEqual(q10["material"]["activity_id"], "FLTRP-EN-7A-2022CUR:STARTER:GET_READY:A10")
        self.assertIn("sports trousers", q9["material"]["text"])       # 词框属于 A9
        self.assertNotIn("sports trousers", q10["material"]["text"])   # A10 的对话里没有词框
        self.assertIn("Nana", q10["material"]["text"])
        self.assertNotIn("Nana", q9["material"]["text"])

    # ---- 原题型呈现（F-2）------------------------------------------------
    def test_07_choice_never_degrades_to_self_check(self):
        for e in self.cat:
            if e["question_type"] not in ("choice", "judge"):
                continue
            q = ex_mod.build_questions(e)
            if e["type"] == "vocabulary":
                # 词汇型练习的主表单仍是既有词汇自测；教材原题必须同时按原题型可见
                self.assertEqual(q["textbook_task"]["kind"], "choice", e["exercise_id"])
                continue
            if e["question_type"] == "judge":
                self.assertEqual(q["kind"], "choice", e["exercise_id"])
            elif q["options"] or (q["textbook_task"] or {}).get("inline_choices"):
                self.assertEqual(q["kind"], "choice", e["exercise_id"])
            else:
                # 没有可确定选项的题不再伪装成选择题（保持记录型）
                self.assertIn(q["kind"], ("self_check", "spelling"), e["exercise_id"])

    def test_08_fill_never_degrades_to_vocabulary_spelling(self):
        for e in self.cat:
            if e["question_type"] != "fill":
                continue
            q = ex_mod.build_questions(e)
            self.assertTrue(q["textbook_task"], e["exercise_id"])
            self.assertEqual(q["textbook_task"]["kind"], "fill", e["exercise_id"])
            if q["kind"] == "spelling":           # 词汇型练习：教材原题必须仍然可见
                self.assertEqual(q["textbook_task"]["kind"], "fill")
            else:
                self.assertEqual(q["kind"], "fill")

    def test_09_match_never_degrades_to_vocabulary_spelling(self):
        for e in self.cat:
            if e["question_type"] not in ("match", "order"):
                continue
            q = ex_mod.build_questions(e)
            self.assertTrue(q["textbook_task"], e["exercise_id"])
            self.assertEqual(q["textbook_task"]["kind"], "match", e["exercise_id"])

    def test_10_judge_has_real_answer_control(self):
        e = next(x for x in self.cat if x["question_type"] == "judge")
        q = ex_mod.build_questions(e)
        self.assertEqual(q["kind"], "choice")
        self.assertEqual(len(q["options"]), 2)
        self.assertIn("F", q["options"][0]["label"])
        self.assertEqual(q["textbook_task"].get("groups"), 6)
        _q, html = self._html(e["exercise_id"])
        self.assertIn('name="t1"', html)
        self.assertIn('name="t6"', html)
        self.assertIn('type="radio"', html)

    def test_11_noise_never_enters_options(self):
        noise = {n.lower() for n in ex_mod.NOISE_OPTION_TEXTS}
        for e in self.cat:
            q = ex_mod.build_questions(e)
            for o in q["options"]:
                self.assertNotIn((o.get("text") or "").strip().lower(), noise, e["exercise_id"])

    def test_12_nine_blank_counts_are_fixed(self):
        self.assertEqual(len(ex_mod.BLANK_FIX), 9)
        for eid, (n, _ev) in ex_mod.BLANK_FIX.items():
            e = self.by_id[eid]
            self.assertEqual(ex_mod.blank_count(e), n, eid)
        self.assertEqual(ex_mod.blank_count(self.by_id["FLTRP-EN-7A-2022CUR:X:88C641F5FA05"]), 6)
        self.assertEqual(ex_mod.blank_count(self.by_id["FLTRP-EN-7A-2022CUR:X:0AD8920218D8"]), 9)

    def test_13_no_answer_fact_is_created(self):
        self.assertEqual(ex_mod.STRUCTURE_VERSION, "P2-6-F-1/F-2/F-4")
        for e in self.cat:
            q = ex_mod.build_questions(e)
            self.assertFalse(q["answer_available"], e["exercise_id"])
            if q["kind"] != "spelling":            # 词汇自测用的是教材词表答案（既有能力）
                for item in q["questions"]:
                    if isinstance(item, dict):
                        self.assertNotIn("answer", item, e["exercise_id"])
            task = q["textbook_task"] or {}
            for item in (task.get("questions") or []):
                if isinstance(item, dict):
                    self.assertNotIn("answer", item, e["exercise_id"])
            self.assertEqual(q["textbook"]["answer_status"], "NO_RELIABLE_SOURCE")

    def test_14_textbook_exercise_never_becomes_vocabulary(self):
        """教材练习不会因为“含词汇”就变成词汇拼写题：原题型必须同时可见。"""
        checked = 0
        for e in self.cat:
            if e["type"] != "vocabulary":
                continue
            q = ex_mod.build_questions(e)
            self.assertTrue(q["textbook_task"], e["exercise_id"])
            self.assertIn(q["textbook_task"]["kind"],
                          ("choice", "fill", "match", "short_answer"), e["exercise_id"])
            checked += 1
        self.assertEqual(checked, 26, "词汇型教材练习应为 26 条")

    def test_15_vocabulary_capability_kept(self):
        """词汇学习能力保留：词汇型练习仍然带有教材词表自测（规则判分）。"""
        e = next(x for x in self.cat if x["type"] == "vocabulary" and x["unit"] == "Unit 1")
        q = ex_mod.build_questions(e)
        self.assertEqual(q["kind"], "spelling")
        self.assertTrue(q["vocab_selftest"])
        self.assertEqual(len(q["questions"]), len(q["vocab_selftest"]["questions"]))
        for item in q["questions"]:
            self.assertTrue(item["answer"])


class UnitTextTest(unittest.TestCase):
    """F-1：教材正文进入 Unit 页面。"""

    def test_01_unit1_text_sections_exist(self):
        data = content_mod.unit_text_sections("unit1")
        self.assertIsNotNone(data)
        keys = [s["section_key"] for s in data["sections"]]
        for k in ("STARTING_OUT", "UNDERSTANDING_IDEAS", "DEVELOPING_IDEAS", "READING_FOR_WRITING"):
            self.assertIn(k, keys)
        self.assertGreater(data["block_count"], 100)

    def test_02_reading_passage_is_present(self):
        data = content_mod.unit_text_sections("unit1")
        text = "\n".join(b["text"] for s in data["sections"] for b in s["blocks"])
        self.assertIn("The first lesson", text)
        self.assertIn("Ms Chen", text)
        self.assertNotIn("A new start  17", text)      # 页脚不进入正文

    def test_03_text_page_renders(self):
        data = content_mod.unit_text_sections("unit1")
        html = ui.unit_text_page({"unit": {"slug": "unit1", "unit_code": "Unit 1",
                                           "title": "A new start"}, "text": data})
        self.assertIn("教材原文", html)
        self.assertIn("Ms Chen", html)
        # P6-B-12c：旧宿主 /unit/<slug> 已退役，教材原文页的返回目标 = 首页
        self.assertIn('href="/"', html)


class HttpSmokeTest(unittest.TestCase):
    """真实 HTTP：Unit 页面出现教材原文入口。"""

    @classmethod
    def setUpClass(cls):
        import http.server
        import app as web_app
        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), web_app.Handler)
        cls.port = cls.srv.server_address[1]
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.thread.join(timeout=5)

    def _get(self, path):
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d%s" % (self.port, path),
                                        timeout=15) as r:
                return r.status, r.read().decode("utf-8")
        except Exception as exc:                       # pragma: no cover
            return 0, repr(exc)

    def test_01b_legacy_text_page_still_works(self):
        """兼容：旧的教材原文文字页仍然可打开（不再作为主要入口）。"""
        st, body = self._get("/unit/unit1/text")
        self.assertEqual(st, 200)
        self.assertIn("教材原文", body)
        # P6-B-12：正文只展示"能与官方音频可靠对应（VERIFIED）"的块；
        # 旧断言"整段教材正文必然出现"属已废止规则，这里改为断言一块已核验的正文。
        self.assertIn("Our English teacher Ms Chen writes the sentence on the blackboard", body)

    def test_02_unit_text_page_loads(self):
        st, body = self._get("/unit/unit1/text")
        self.assertEqual(st, 200)
        self.assertIn("教材原文", body)
        self.assertIn("Our English teacher Ms Chen writes the sentence on the blackboard", body)

    def test_03_exercise10_page_shows_options(self):
        key = ex_mod.exercise_key(E10)
        st, body = self._get("/exercise/%s" % key)
        self.assertEqual(st, 200)
        self.assertIn("sports trousers", body)
        self.assertIn("/audio/official/AU03.mp3", body)
        self.assertIn('name="t1"', body)
        self.assertNotIn("NEEDS_REVIEW", body)


if __name__ == "__main__":
    unittest.main(verbosity=2)
