#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P6-B-16 验收：旧「训练岛」（/train · /weekend · /stage）已正式退休

覆盖：
  A 旧路由全部 404：/train、/unit/<slug>/train、/unit/<slug>/weekend、/unit/<slug>/stage
     （以及同样只服务旧岛的 /unit/<slug>/practice 重定向）
  B 当前正式产品未受影响：/、/textbook、/?unit=<slug> 全部 200；
     当前课时 picker = 1 form / 8 Unit 分组 / 46 Section；六入口顺序完全不变
  C 旧岛残留：/progress、/unit/<slug>/text、/unit/<slug>/result 中不再有指向旧岛的链接
  D 正式数据库零写入（learning.db / questionbank.db / contentpack）

只读：不写任何正式资产；AI 调用 0。
运行：python D:\ZhixueEnglish\web\test_p6b16_training_island_retired.py
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
RETIRED = ("/train", "/unit/unit1/train", "/unit/unit1/weekend", "/unit/unit1/stage",
           "/unit/unit1/practice")


def _sha(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class TrainingIslandRetiredTest(unittest.TestCase):

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
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d%s" % (self.port, path),
                                        timeout=30) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8", "replace")

    # ---------------- A 旧路由全部 404 ----------------
    def test_A_retired_routes_are_404(self):
        for path in RETIRED:
            status, _body = self._get(path)
            self.assertEqual(status, 404, "%s 必须已退休（404）" % path)

    # ---------------- B 当前正式产品未受影响 ----------------
    def test_B_current_product_unaffected(self):
        for path in ("/", "/textbook", "/?unit=starter", "/?unit=unit1",
                     "/?unit=unit6", "/?unit=appendix"):
            status, body = self._get(path)
            self.assertEqual(status, 200, path)
            if path in ("/", "/?unit=starter", "/?unit=unit1", "/?unit=unit6", "/?unit=appendix"):
                blk = re.search(r'<section class="softcard unitcard">.*?</section>', body, re.S)
                blk = blk.group(0) if blk else ""
                self.assertEqual(len(re.findall(r'class="picker"', blk)), 1, path)
                self.assertEqual(len(re.findall(r"<optgroup", blk)), 8, path)
                self.assertEqual(len(re.findall(r"<option", blk)), 46, path)
        _st, body = self._get("/")
        rows = re.findall(r'<a class="entryrow [^"]*" href="([^"]*)"><span class="ico">.*?'
                          r'<span class="nm">([^<]*)</span>', body, re.S)
        self.assertEqual([label for _, label in rows], list(ENTRY_LABELS))
        _st, tb = self._get("/textbook")
        self.assertEqual(tb.count('class="unitrow"'), 8)
        self.assertEqual(sorted(set(re.findall(r'<a class="unitrow" href="([^"]*)"', tb))),
                         sorted("/?unit=%s" % s for s in
                                ("starter", "unit1", "unit2", "unit3", "unit4", "unit5",
                                 "unit6", "appendix")))

    # ---------------- C 旧岛残留入口已清理 ----------------
    def test_C_no_ui_links_into_retired_island(self):
        # P6-B-23：/unit/<slug>/result 与 /unit/<slug>/sentence 也已退休，改为 404 断言
        for path in ("/progress", "/unit/unit1/text", "/textbook"):
            status, body = self._get(path)
            self.assertEqual(status, 200, path)
            links = set(re.findall(r'href="([^"]*)"', body))
            for bad in ("/train", "/weekend", "/stage"):
                self.assertNotIn(bad, " ".join(links), "%s 仍指向已退休页面" % path)
            self.assertFalse([h for h in links if h.endswith("/practice")],
                             "%s 仍指向已退休的 /practice" % path)
        for path in ("/unit/unit1/result", "/unit/unit1/sentence"):
            status, _body = self._get(path)
            self.assertEqual(status, 404, "%s 必须已退休（P6-B-23）" % path)

    # ---------------- D 正式资产零写入 ----------------
    def test_D_formal_assets_unchanged(self):
        for name, p in (("learning.db", content_mod.LEARNING_DB),
                        ("questionbank.db", BASE / "structured" / "questionbank" / "questionbank.db"),
                        ("contentpack", content_mod.CONTENTPACK)):
            self.assertEqual(_sha(p), self.assets[name], "%s 被写入" % name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
