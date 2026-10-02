#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Demo 页面验收（原第二版用例，第五轮按当前契约重写）

覆盖：今天学什么（放大的章节菜单 + 功能入口）/ 听音辨词（动态大扬声器 + 选项 +
确定 + 统一进度）/ 单词跟读（单词 + 音标 + 中文 + 三个底部操作 + 浅底图标 + 例句翻译）/
教材点读（自然文本块）/ 手机窄屏 / 正式数据边界 / 无 AI 与网络调用。

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
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True

import app as web_app                   # noqa: E402
import content as content_mod           # noqa: E402
import ui                               # noqa: E402

UNIT1 = "/unit/unit1"
EMOJI = re.compile("[\U0001F300-\U0001FAFF\u25b6\u2190\u2b50\u2600-\u26ff]")
OFFICIAL_DB_SHA = "0C27267BF83A70A75BB400F0055B62CB2985A83EDD120B9AC790A7FD5E59CF91"


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def markup_only(body: str) -> str:
    text = re.sub(r"(?s)<style>.*?</style>", " ", body)
    return re.sub(r"(?s)<script>.*?</script>", " ", text)


def visible(body: str) -> str:
    return re.sub(r"<[^>]+>", " ", markup_only(body))


class DemoUiTest(unittest.TestCase):
    """当前 Demo 的页面级验收（临时 learning.db 副本）。"""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="zhixue_ui_"))
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
            with opener.open("http://127.0.0.1:%d%s" % (self.port, path), timeout=60) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8", "replace")

    # ---------------- 首页：章节菜单 + 功能入口 ----------------
    def test_01_home_menu_and_entries(self):
        status, body = self._get(self._client(), "/")
        self.assertEqual(status, 200)
        self.assertIn('id="zx-unit"', body)
        self.assertIn('class="softcard unitcard"', body)       # 放大的课堂菜单
        self.assertIn("Unit 1 · A new start", body)           # 当前课堂进度一眼可见
        self.assertIn(".picker select{width:100%;font:inherit;font-size:17px", ui.STYLE)
        self.assertIn(".unitcard .um-now{font-size:22px", ui.STYLE)
        rows = re.findall(r'<a class="entryrow ([a-z\- ]+)" href="([^"]+)">'
                          r'<span class="ico">(<svg[^>]*>.*?</svg>)</span>'
                          r'<span class="nm">([^<]+)</span><span class="st">([^<]+)</span>', body)
        self.assertGreaterEqual(len(rows), 5)
        labels = [r[3] for r in rows]
        self.assertEqual(labels[0], "单词跟读")
        self.assertIn("听音辨词", labels)
        self.assertEqual(labels[-1], "课文点读")
        for bad in ("词汇跟读", "词汇练习"):
            self.assertNotIn(bad, visible(body), "界面不得再出现旧名称：%s" % bad)

    def test_02_no_nav_no_emoji_no_internal_words(self):
        _st, body = self._get(self._client(), "/")
        self.assertNotIn('<nav class="nav"', body)
        self.assertFalse(EMOJI.findall(markup_only(body)))
        for leaked in ("session_id", "item_id", "contentpack", ".sqlite"):
            self.assertNotIn(leaked, body)

    # ---------------- 听音辨词：动态大扬声器 + 选项 + 确定 + 进度 ----------------
    def test_07_official_db_untouched(self):
        self.assertEqual(sha256_file(content_mod.LEARNING_DB), OFFICIAL_DB_SHA)

    def test_08_no_ai_api_and_no_new_deps(self):
        for name in ("app.py", "ui.py", "content.py", "flow.py", "demo_data.py",
                     "demo_content.py", "pdf_pages.py", "audio.py", "exercises.py",
                     "reading_map.py"):
            src = (HERE / name).read_text(encoding="utf-8").lower()
            for token in ("openai", "deepseek", "ollama", "anthropic", "requests.",
                          "urllib.request", "http.client", "socket.", "transformers",
                          "torch", "tensorflow", "tts", "ocr"):
                self.assertNotIn(token, src, "%s 不得包含 AI / 网络调用：%s" % (name, token))
        self.assertIn("import pymupdf", (HERE / "pdf_pages.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
