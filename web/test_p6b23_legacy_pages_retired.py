#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P6-B-23 验收：旧 Demo 老页面已正式退休

退休对象（全部保持 404，不得恢复、不得创建替代路由）：
  /tutor · /p3-06/au06-test · /p3-06/au11-hearing · /unit/<slug>/p3-06
  /unit/<slug>/sentence · /unit/<slug>/shadowing · /unit/<slug>/result

覆盖：
  A 旧路由全部 404
  B 当前正式产品未受影响：/、/textbook、/?unit=<slug> 全部 200；
    当前课时 picker = 1 form / 8 Unit 分组 / 46 Section；六入口顺序完全不变
  C 旧链接残留：/、/textbook、/progress、/unit/<slug>/text 不再指向任何已退休页面
  D 核心能力保留：教材音频事实、P5 跟读服务、共享播放/录音组件、AI 卡渲染能力
  E 正式数据库零写入（learning.db / questionbank.db / contentpack）

只读：不写任何正式资产；AI 调用 0。
运行：python D:\ZhixueEnglish\web\test_p6b23_legacy_pages_retired.py
"""

from __future__ import annotations

import hashlib
import http.server
import re
import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True

import app as web_app                     # noqa: E402
import content as content_mod             # noqa: E402
import demo_data as demo                  # noqa: E402
import study_call_service as scs          # noqa: E402
import ui                                 # noqa: E402

BASE = HERE.parent
ENTRY_LABELS = ("跟读练习", "听音辨意", "音标写词", "词形变化", "本课检测", "自主练习")
RETIRED_PATHS = (
    "/tutor",
    "/tutor?unit=unit1",
    "/p3-06/au06-test",
    "/p3-06/au11-hearing",
    "/unit/unit1/p3-06",
    "/unit/unit1/sentence",
    "/unit/unit1/sentence?uid=P3-07:AU13-DLG-01",
    "/unit/unit1/shadowing",
    "/unit/unit1/shadowing?i=1",
    "/unit/unit1/result",
)

#: 任何正式页面里都不应再出现的链接目标片段
RETIRED_LINK_FRAGMENTS = ("/tutor", "/p3-06/", "/sentence", "/shadowing", "/result")


def _sha(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class LegacyPagesRetiredTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.assets = {name: _sha(p) for name, p in (
            ("learning.db", content_mod.LEARNING_DB),
            ("questionbank.db", BASE / "structured" / "questionbank" / "questionbank.db"),
            ("contentpack", content_mod.CONTENTPACK))}
        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), web_app.Handler)
        cls.port = cls.srv.server_address[1]
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.thread.join(timeout=5)
        for name, p in (("learning.db", content_mod.LEARNING_DB),
                        ("questionbank.db",
                         BASE / "structured" / "questionbank" / "questionbank.db"),
                        ("contentpack", content_mod.CONTENTPACK)):
            assert _sha(p) == cls.assets[name], "%s 被修改" % name

    def _get(self, path):
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d%s" % (self.port, path),
                                        timeout=30) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8", "replace")

    # ---------------- A 旧路由全部 404 ----------------
    def test_A_retired_routes_are_404(self):
        for path in RETIRED_PATHS:
            status, _body = self._get(path)
            self.assertEqual(status, 404, "%s 必须已退休（404）" % path)

    # ---------------- B 当前正式产品未受影响 ----------------
    def test_B_current_product_unaffected(self):
        for path in ("/", "/textbook", "/?unit=starter", "/?unit=unit1",
                     "/?unit=unit6", "/?unit=appendix"):
            status, body = self._get(path)
            self.assertEqual(status, 200, path)
            if path.startswith("/?"):
                blk = re.search(r'<section class="softcard unitcard">.*?</section>', body, re.S)
                blk = blk.group(0) if blk else ""
                self.assertEqual(len(re.findall(r'class="picker"', blk)), 1, path)
                self.assertEqual(len(re.findall(r"<optgroup", blk)), 8, path)
                self.assertEqual(len(re.findall(r"<option", blk)), 46, path)
        _st, home = self._get("/")
        blk = re.search(r'<section class="softcard unitcard">.*?</section>', home, re.S)
        blk = blk.group(0) if blk else ""
        self.assertEqual(len(re.findall(r'class="picker"', blk)), 1, "当前课时只允许一个下拉")
        self.assertEqual(len(re.findall(r"<optgroup", blk)), 8)
        self.assertEqual(len(re.findall(r"<option", blk)), 46)
        rows = re.findall(r'<a class="entryrow [^"]*" href="([^"]*)"><span class="ico">.*?'
                          r'<span class="nm">([^<]*)</span>', home, re.S)
        self.assertEqual([label for _, label in rows], list(ENTRY_LABELS))

    # ---------------- C 不再留下指向退休页面的链接 ----------------
    def test_C_no_links_into_retired_pages(self):
        for path in ("/", "/textbook", "/progress", "/unit/unit1/text"):
            status, body = self._get(path)
            self.assertEqual(status, 200, path)
            links = set(re.findall(r'href="([^"]*)"', body))
            joined = " ".join(links)
            for frag in RETIRED_LINK_FRAGMENTS:
                self.assertNotIn(frag, joined,
                                 "%s 仍指向已退休页面：%s" % (path, frag))

    # ---------------- D 核心能力保留 ----------------
    def test_D_core_capabilities_are_kept(self):
        # 教材音频事实（VERIFIED 区间）仍在
        audio = content_mod.unit_audio_resources("Unit 1", content_mod.CONTENTPACK)
        rows = audio["sentences"]
        self.assertGreaterEqual(len(rows), 12)
        for row in rows:
            self.assertIsNotNone(row.get("start_ms"))
            self.assertIsNotNone(row.get("end_ms"))
        # P5 跟读资源池仍在（正式入口跟读练习使用的链路）
        self.assertTrue(scs.shadowing_materials("Unit 1"), "P5 跟读资源池不得为空")
        # 共享播放 / 录音组件仍在
        for name in ("PLAYER_JS", "RECORD_JS", "play_button", "record_block", "ai_card",
                     "P5_SEGMENT_SCRIPT", "P5_SWIPE_SCRIPT", "P5_RECORD_SCRIPT",
                     "p5_segment_speaker", "_p5_big_speaker", "p5_page"):
            self.assertTrue(hasattr(ui, name), "共享组件缺失：%s" % name)
        self.assertTrue(hasattr(web_app.Handler, "_drill_items"))
        # AI 卡能力与数据仍保留（页面退休 ≠ 能力退休）
        self.assertTrue(hasattr(ui, "ai_card"))
        self.assertTrue(hasattr(demo, "chapter_ai"))
        self.assertTrue(hasattr(web_app.Handler, "_chapter_ai"))
        # 服务旧页面的实现必须已经清掉（不得以“不可达”充当退休）
        for name in ("tutor_page", "unit_result_page", "sentence_page", "sentence_list_page",
                     "shadowing_page", "_shadowing_demo_block", "au06_test_page",
                     "au11_hearing_page"):
            self.assertFalse(hasattr(ui, name), "UI 渲染函数应已退休：%s" % name)
        for name in ("shadowing_sentences", "au06_test_data", "au11_hearing_data"):
            self.assertFalse(hasattr(content_mod, name), "内容层函数应已退休：%s" % name)
        for name in ("tutor_demo", "shadow_demo", "sentence_note", "evidence", "result_ai",
                     "state", "SHADOW_DEMO", "TUTOR_FOCUS", "SENTENCE_NOTES",
                     "EVIDENCE_ROWS", "RESULT_AI", "STATE"):
            self.assertFalse(hasattr(demo, name), "演示数据应已退休：%s" % name)
        for name in ("_tutor", "_unit_result", "_sentence"):
            self.assertFalse(hasattr(web_app.Handler, name),
                             "Handler 方法应已退休：%s" % name)

    # ---------------- E 正式资产零写入 ----------------
    def test_E_formal_assets_unchanged(self):
        for name, p in (("learning.db", content_mod.LEARNING_DB),
                        ("questionbank.db",
                         BASE / "structured" / "questionbank" / "questionbank.db"),
                        ("contentpack", content_mod.CONTENTPACK)):
            self.assertEqual(_sha(p), self.assets[name], "%s 被写入" % name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
