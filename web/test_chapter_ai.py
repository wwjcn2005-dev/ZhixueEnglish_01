#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""章节选择 + 学习状态驱动的单元总结（原 V1.1 专项用例，第五轮按当前契约重写）

覆盖：首次打开只说「该学什么」不评价孩子 / 章节切换同步 / 学习行为才改变状态 /
只浏览不改变状态 / 状态不写正式 learning.db / 状态解析安全。

说明：本文件在第五轮的一次批量文本替换事故中被破坏（字符级替换），
已按当前产品契约重写为等价覆盖。
"""

from __future__ import annotations

import hashlib
import http.cookiejar
import re
import shutil
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
import content as content_mod           # noqa: E402
import demo_data as demo                # noqa: E402
import ui                               # noqa: E402

OFFICIAL_DB_SHA = "0C27267BF83A70A75BB400F0055B62CB2985A83EDD120B9AC790A7FD5E59CF91"


def sha256_file(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


def visible(body: str) -> str:
    text = re.sub(r"(?s)<style>.*?</style>", " ", body)
    text = re.sub(r"(?s)<script>.*?</script>", " ", text)
    return re.sub(r"<[^>]+>", " ", text)


def ai_section(body: str) -> str:
    """取出单元总结（AI 随堂助教）那一段可见文字。"""
    if '<section class="ai">' in body:
        seg = body.split('<section class="ai">')[1].split("</section>")[0]
    else:
        seg = body.split("<main>")[-1].split('<p class="demo-note">')[0]
    seg = re.sub(r"(?s)<[^>]+>", "\n", seg)
    return "\n".join(x.strip() for x in seg.split("\n") if x.strip())


class ChapterAiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="zhixue_chapter_"))
        cls.tmp_db = cls.tmpdir / "learning.db"
        shutil.copyfile(content_mod.LEARNING_DB, cls.tmp_db)
        web_app.Handler.learning_db = cls.tmp_db
        web_app.Handler.contentpack_path = content_mod.CONTENTPACK
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), web_app.Handler)
        cls.port = cls.srv.server_address[1]
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.thread.join(timeout=5)
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def _client(self):
        self.jar = jar = http.cookiejar.CookieJar()
        return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def _get(self, opener, path):
        try:
            with opener.open("http://127.0.0.1:%d%s" % (self.port, path), timeout=60) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8", "replace")

    def _state(self):
        """本机演示学习状态（就是页面读写的那条 Cookie）。"""
        for cookie in getattr(self, "jar", []):
            if cookie.name == web_app.DEMO_STATE_COOKIE:
                return demo.parse_state(urllib.parse.unquote(cookie.value))
        return {}

    def _ai_card(self, slug="unit1", state=None):
        """按页面同一条代码路径装配 AI 随堂助教卡（不经过 socket）。

        P6-B-23：旧的独立「AI 助教页」/tutor 已退休，AI 卡的数据与渲染能力保留，
        这里直接验证「当前章节 + 本机学习状态 → AI 卡内容」这条契约。
        """
        h = web_app.Handler.__new__(web_app.Handler)
        h.contentpack_path = content_mod.CONTENTPACK
        h.learning_db = self.tmp_db
        unit = content_mod.get_unit(slug, content_mod.CONTENTPACK)
        training = h._unit_training(unit)
        ai, _focus, _steps = h._chapter_ai(unit, training, state or {})
        return ui.ai_card(ai, unit["unit_code"], unit.get("title") or "")

    def _learn(self, opener, unit, step):
        req = urllib.request.Request(
            "http://127.0.0.1:%d/demo/learn" % self.port,
            data=urllib.parse.urlencode({"unit": unit, "step": step}).encode("utf-8"))
        with opener.open(req, timeout=30) as r:
            return r.status

    def test_01_first_open_says_what_to_learn(self):
        card = self._ai_card("unit1")
        ai = ai_section(card)
        self.assertIn("这一单元主要围绕", ai)
        self.assertEqual(len(re.findall(r'<span class="fw">([^<]+)</span>', card)), 3,
                         "首次进入只给最重要的 3 个知识点")
        for bad in ("你已经完成", "整体基础不错", "掌握得", "薄弱", "AI发现你不会"):
            self.assertNotIn(bad, ai, "首次进入不得出现学习评价：%s" % bad)

    def test_02_chapter_switch_switches_ai(self):
        one, two = self._ai_card("unit1"), self._ai_card("unit2")
        self.assertNotEqual(ai_section(one), ai_section(two))
        opener = self._client()
        _st, home1 = self._get(opener, "/?unit=unit1")
        _st, home2 = self._get(opener, "/?unit=unit2")
        self.assertIn("Unit 1 · A new start", home1)
        self.assertIn("Unit 2 · More than fun", home2)
        # P6-B-18：P6-B-13 起「当前课时」选择器是唯一的 Unit → Section 下拉 ——
        # Unit 由 optgroup 分组表达，option 的 value 是真实 section_key
        # （旧的 Unit-level option value 已经退出，不再出现 value="<unit_slug>"）。
        def picker_block(html: str) -> str:
            return html.split('<section class="softcard unitcard">')[1].split("</section>")[0]

        blk1, blk2 = picker_block(home1), picker_block(home2)
        for blk in (blk1, blk2):
            self.assertEqual(len(re.findall(r'class="picker"', blk)), 1,
                             "当前课时只能有一个下拉")
            self.assertEqual(len(re.findall(r"<optgroup label=", blk)), 8,
                             "Unit 必须是分组（8 个块）")
        keys1 = re.findall(r'<option value="([^"]*)"', blk1)
        self.assertEqual(len(keys1), 46, "必须列出全部 46 个真实 Section")
        catalog = content_mod.list_units_with_sections(str(content_mod.CONTENTPACK))
        for u in catalog:
            # 每个 Unit 以分组标题出现；且不得再以 Unit slug 充当 option value
            self.assertIn('label="%s · %s"' % (u["unit_code"], u["title"]), blk1)
            self.assertNotIn(u["slug"], keys1,
                             "不得再出现 Unit-level option value：%s" % u["slug"])
        # 每个分组内的选项 = 该 Unit 的真实 Section（顺序一致）：Unit → Section 是正式映射
        groups = re.findall(r'<optgroup label="([^"]*)">(.*?)</optgroup>', blk1, re.S)
        self.assertEqual(len(groups), 8)
        for label, opts in groups:
            code = label.split(" · ")[0]
            expect = [s["section_key"] for u in catalog if u["unit_code"] == code
                      for s in u["sections"]]
            self.assertEqual(re.findall(r'<option value="([^"]*)"', opts), expect, label)
        # 当前 Unit 上下文：隐藏 unit 字段 + 该 Unit 的第一个真实 Section（STARTING_OUT）
        for blk, slug in ((blk1, "unit1"), (blk2, "unit2")):
            self.assertIn('<input type="hidden" name="unit" value="%s">' % slug, blk)
            self.assertIn('<option value="STARTING_OUT" selected>', blk)
            self.assertIn('data-value="STARTING_OUT" data-unit="%s"' % slug, blk)

    def test_03_learning_behaviours_change_the_ai(self):
        opener = self._client()
        first = ai_section(self._ai_card("unit1", self._state()))
        self._learn(opener, "unit1", "reading")
        self._learn(opener, "unit1", "vocabulary")
        second = ai_section(self._ai_card("unit1", self._state()))
        self.assertNotEqual(first, second, "产生学习行为后内容必须变化")
        self.assertIn("你已经完成了", second)
        self.assertIn("Unit 1", second)

    def test_04_visits_alone_never_change_state(self):
        opener = self._client()
        first = ai_section(self._ai_card("unit3", self._state()))
        for _ in range(3):
            self._get(opener, "/?unit=unit3")
            self._get(opener, "/?unit=unit1")
        self.assertEqual(first, ai_section(self._ai_card("unit3", self._state())),
                         "只浏览不得让 AI 认为孩子进步了")

    def test_05_unit_state_does_not_pollute_other_units(self):
        opener = self._client()
        base = ai_section(self._ai_card("unit1", self._state()))
        self._learn(opener, "unit2", "vocabulary")
        self.assertEqual(base, ai_section(self._ai_card("unit1", self._state())),
                         "Unit 2 的行为不得影响 Unit 1")
        self.assertIn("你已经完成了 Unit 2",
                      ai_section(self._ai_card("unit2", self._state())))

    def test_09_legacy_tutor_page_is_retired(self):
        """P6-B-23：旧的独立「AI 助教页」已正式退休（AI 能力保留，页面不再存在）。"""
        status, _body = self._get(self._client(), "/tutor?unit=unit1")
        self.assertEqual(status, 404)

    def test_06_no_ai_calls_and_no_db_write(self):
        for name in ("app.py", "ui.py", "content.py", "flow.py", "demo_data.py",
                     "demo_content.py", "reading_map.py"):
            src = (HERE / name).read_text(encoding="utf-8").lower()
            for token in ("openai", "deepseek", "ollama", "anthropic", "requests.",
                          "urllib.request", "http.client", "socket.", "transformers",
                          "torch", "tensorflow", "tts", "ocr"):
                self.assertNotIn(token, src, "%s 不得包含 AI / 网络调用：%s" % (name, token))
        src = (HERE / "demo_data.py").read_text(encoding="utf-8").lower()
        for token in ("asr", "whisper", "speech"):
            self.assertNotIn(token, src, "演示数据层不得包含语音识别能力：%s" % token)
        opener = self._client()
        before = sha256_file(self.tmp_db)
        self._learn(opener, "unit1", "vocabulary")
        self._get(opener, "/?unit=unit1")
        self.assertEqual(sha256_file(self.tmp_db), before, "章节学习状态不得写库")

    def test_07_state_parsing_is_safe(self):
        state = demo.parse_state("unit1:reading,vocabulary=partial|unit2:phrase")
        self.assertEqual(demo.steps_of(state, "unit1"),
                         {"reading": "done", "vocabulary": "partial"})
        self.assertEqual(demo.steps_of(state, "unit2"), {"phrase": "done"})
        self.assertEqual(demo.parse_state("../../etc:reading|unit1:evil=1|unit1:"), {})
        self.assertEqual(demo.dump_state(demo.parse_state("unit1:reading")), "unit1:reading")

    def test_08_official_db_untouched(self):
        self.assertEqual(sha256_file(content_mod.LEARNING_DB), OFFICIAL_DB_SHA)


if __name__ == "__main__":
    unittest.main(verbosity=2)
