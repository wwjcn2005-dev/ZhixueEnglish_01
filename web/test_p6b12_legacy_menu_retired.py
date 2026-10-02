#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P6-B-12-FIX 验收：旧七项 Unit 菜单体系已退役，正式六入口不受影响

覆盖：
  A 首页仍然只有正式六入口，顺序不变
  B 六入口 `/unit/<slug>/p5/<entry>` 全部正常响应
  C 旧宿主 `/unit/<slug>` 已退役（404，且不再出现「本单元学习」）
  D 旧七项路由（read / page / words / sentence-read / 4×drill）已退役（404）

全程只读：不写 learning.db / questionbank.db / contentpack；AI 调用 0。
运行：python D:\ZhixueEnglish\web\test_p6b12_legacy_menu_retired.py
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

BASE = HERE.parent

ENTRY_LABELS = ("跟读练习", "听音辨意", "音标写词", "词形变化", "本课检测", "自主练习")
ENTRIES = ("read", "listen", "phonetic", "form", "check", "practice")
#: 旧七项菜单路由（课文点读 = read + page 两个历史路由）
LEGACY_SUBPATHS = ("read", "page", "words", "sentence-read",
                   "vocab-drill", "phrase-drill", "reading-drill", "listening-drill")


def _sha(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class LegacyMenuRetiredTest(unittest.TestCase):

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
                        ("questionbank.db", BASE / "structured" / "questionbank" / "questionbank.db"),
                        ("contentpack", content_mod.CONTENTPACK)):
            assert _sha(p) == cls.assets[name], "%s 被修改" % name

    def _get(self, path):
        """GET → (status, body)；404 不抛异常。"""
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d%s" % (self.port, path),
                                        timeout=30) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8", "replace")

    @staticmethod
    def _visible(body: str) -> str:
        """页面可见文字（去掉 <style>/<script>，避免样式注释干扰判断）。"""
        text = re.sub(r"<style.*?</style>", " ", body, flags=re.S)
        text = re.sub(r"<script.*?</script>", " ", text, flags=re.S)
        return re.sub(r"<[^>]+>", " ", text)

    # ---------------- A 首页六入口 ----------------
    def test_A_home_has_exactly_six_entries_in_order(self):
        status, body = self._get("/")
        self.assertEqual(status, 200)
        got = re.findall(r'<a class="entryrow [^"]*" href="([^"]*)"><span class="ico">.*?'
                         r'<span class="nm">([^<]*)</span>', body, re.S)
        self.assertEqual(len(got), 6, "首页必须正好六个入口")
        self.assertEqual([label for _, label in got], list(ENTRY_LABELS),
                         "首页入口必须是正式六入口且顺序不变")
        for entry, (href, _) in zip(ENTRIES, got):
            self.assertIn("/p5/%s" % entry, href, "入口必须指向正式 P5 入口页")
        # 旧七项入口不得再作为首页入口出现（按入口行判断；页面内 CSS 注释不算入口）
        labels = {label for _, label in got}
        for legacy in ("课文点读", "单词跟读", "听音辨词", "短语练习", "阅读练习", "听力练习"):
            self.assertNotIn(legacy, labels, "首页不得再出现旧入口：%s" % legacy)
        self.assertNotIn("本单元学习", self._visible(body))

    # ---------------- B 六入口可用 ----------------
    def test_B_six_entry_pages_respond(self):
        for entry in ENTRIES:
            path = "/unit/unit1/p5/%s?lesson=DEVELOPING_IDEAS" % entry
            status, body = self._get(path)
            self.assertEqual(status, 200, path)
            # P6-B-12-FIX：无资源时的空态文案已改为准确的孩子口径（不再使用"这一章…/换个章节看看"）
            self.assertNotIn("这一章暂时没有这个入口的内容", body, path)
            self.assertNotIn("换个章节看看", body, path)

    # ---------------- C 旧宿主退役 ----------------
    def test_C_legacy_unit_host_is_retired(self):
        for unit in ("unit1", "starter", "unit4"):
            status, body = self._get("/unit/%s" % unit)
            self.assertEqual(status, 404, "/unit/%s 必须已退役" % unit)
            visible = self._visible(body)
            self.assertNotIn("本单元学习", visible, "不得保留旧七项菜单空壳")
            for legacy in ("课文点读", "单词跟读", "听音辨词", "短语练习", "阅读练习", "听力练习"):
                self.assertNotIn(legacy, visible)

    # ---------------- D 旧七项路由退役 ----------------
    def test_D_legacy_entry_routes_are_retired(self):
        for sub in LEGACY_SUBPATHS:
            for unit in ("unit1", "starter"):
                path = "/unit/%s/%s" % (unit, sub)
                status, _body = self._get(path)
                self.assertEqual(status, 404, "%s 必须已退役" % path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
