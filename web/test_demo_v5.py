#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""第五轮综合修正验收（页面命名 / 听音辨词动态扬声器 / 单词跟读浅底图标 /
固定入库的例句与练习 / 教材点读自然文本块）。

只读：临时 learning.db 副本 + 只读 contentpack；不写任何正式数据。
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
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True

import app as web_app                    # noqa: E402
import content as content_mod            # noqa: E402
import demo_content                      # noqa: E402
import reading_map                       # noqa: E402
import ui                                # noqa: E402

UNIT1 = "/unit/unit1"
OFFICIAL_DB_SHA = "0C27267BF83A70A75BB400F0055B62CB2985A83EDD120B9AC790A7FD5E59CF91"
CONTENTPACK_SHA = "65829CA73E41B75ACA010B93B7339EDDF0F666F919148F0F69ED898419700C39"


def sha256_file(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


def visible(body: str) -> str:
    text = re.sub(r"(?s)<style>.*?</style>", " ", body)
    text = re.sub(r"(?s)<script>.*?</script>", " ", text)
    return re.sub(r"<[^>]+>", " ", text)


class V5Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="zhixue_v5_"))
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
        jar = http.cookiejar.CookieJar()
        return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def _get(self, opener, path):
        try:
            with opener.open("http://127.0.0.1:%d%s" % (self.port, path), timeout=90) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8", "replace")

    # ---------------- 1：页面命名统一 ----------------
    def test_04_home_menu_is_bigger(self):
        _st, body = self._get(self._client(), "/")
        self.assertIn('class="softcard unitcard"', body)
        self.assertIn('class="um-now"', body)
        self.assertIn("Unit 1 · A new start", body)
        self.assertIn(".unitcard .um-now{font-size:22px", ui.STYLE)
        self.assertIn(".picker select{width:100%;font:inherit;font-size:17px", ui.STYLE)
        self.assertIn("min-height:56px", ui.STYLE)

    # ---------------- 5：例句固定入库 + 完整中文翻译 ----------------
    def test_06_no_context_sentence_fragments(self):
        """旧的 _context_sentence（容易产生碎片句）已下线。"""
        self.assertFalse(hasattr(web_app.Handler, "_context_sentence"))
        src = (HERE / "app.py").read_text(encoding="utf-8")
        self.assertNotIn("_context_sentence", src)

    # ---------------- 6：短句练习 / 阅读练习（教材优先 + 固定补充） ----------------
    def test_08_natural_blocks_unit1(self):
        blocks = reading_map.natural_blocks("Unit 1")
        pages = sorted(b["page"] for b in blocks)
        self.assertEqual(pages, [22, 29, 30])
        kinds = {b["page"]: b["kind"] for b in blocks}
        self.assertEqual(kinds[22], "passage")
        self.assertEqual(kinds[29], "dialogue")
        self.assertEqual(kinds[30], "letter")
        for b in blocks:
            self.assertGreaterEqual(b["row_cover"], 0.9, "每条匹配都要通过复核")
            self.assertGreater(len(b["rects"]), 0)
            self.assertTrue(b["audio_url"].startswith("/audio/official/AU"))

    def test_10_old_hotspot_mechanism_is_gone(self):
        src = (HERE / "pdf_pages.py").read_text(encoding="utf-8")
        self.assertNotIn("locate_exact", src)
        self.assertIn("def text_rects", src)          # 只保留「文字 → 矩形」的几何能力
        self.assertFalse(hasattr(web_app.Handler, "_page_entries"))
        self.assertFalse(hasattr(web_app.Handler, "_page_activities"))
        import demo_data                              # noqa: E402
        self.assertFalse(hasattr(demo_data, "paragraphs"))
        ui_src = (HERE / "ui.py").read_text(encoding="utf-8")
        self.assertNotIn("data-hot", ui_src)

    # ---------------- 8：边界 ----------------
    def test_11_frozen_data_untouched(self):
        self.assertEqual(sha256_file(content_mod.LEARNING_DB), OFFICIAL_DB_SHA)
        self.assertEqual(sha256_file(content_mod.CONTENTPACK), CONTENTPACK_SHA)
        # 本轮新增的 Demo 数据层只读运行，不写正式数据
        self.assertTrue(demo_content.VERSION)
        self.assertTrue((HERE / "demo_content.py").exists())
        self.assertTrue((HERE / "reading_map.py").exists())

    def test_12_no_runtime_ai_calls(self):
        for name in ("app.py", "ui.py", "demo_content.py", "reading_map.py",
                     "demo_data.py", "pdf_pages.py"):
            src = (HERE / name).read_text(encoding="utf-8").lower()
            for token in ("openai", "deepseek", "ollama", "anthropic", "requests.",
                          "http.client", "socket.", "transformers", "torch"):
                self.assertNotIn(token, src, "%s 不得包含 AI / 网络调用：%s" % (name, token))

    # P6-B-16：旧「当前路径不得出现旧入口」清单（含 train/weekend/stage/practice）
    # 随对应页面退休一并删除（其断言测试已在 P6-B-12a 退役）

    def _crawl(self, opener, start="/", depth=2, limit=40):
        """从首页出发爬取站内链接（只 GET，不写任何数据）。"""
        seen, found = {start}, {start}
        frontier = [start]
        for _ in range(depth):
            nxt = []
            for path in frontier:
                _st, body = self._get(opener, path)
                for href in re.findall(r'href="(/[^"]*)"', body):
                    href = href.split("#")[0]
                    if href in seen or len(seen) >= limit:
                        continue
                    seen.add(href)
                    found.add(href)
                    nxt.append(href)
            frontier = nxt
            if not frontier:
                break
        return found

if __name__ == "__main__":
    unittest.main(verbosity=2)
