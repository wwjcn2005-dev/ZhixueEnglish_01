#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""第三版 Demo（UI / 交互重构）验收测试

对应任务书 §十七 允许新增的覆盖点：
  顶部返回 / 标题居中 / 词汇跟读布局 / 中文意思 / 底部三个操作图标 /
  词汇练习布局 / 短语练习 / 阅读练习 / 作答返回保护（含浏览器 Back）/
  教材彩页 / 热点播放

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

import app as web_app                   # noqa: E402
import content as content_mod           # noqa: E402
import demo_data as demo                # noqa: E402
import ui                               # noqa: E402

UNIT1 = "/unit/unit1"

OFFICIAL_DB_SHA = "0C27267BF83A70A75BB400F0055B62CB2985A83EDD120B9AC790A7FD5E59CF91"
CONTENTPACK_SHA = "65829CA73E41B75ACA010B93B7339EDDF0F666F919148F0F69ED898419700C39"

#: 第三版 Demo 重新设计过的页面
#: P6-B-12-FIX / P6-B-16：旧七项 Unit 菜单与旧训练岛路由均已退役，这里只保留仍然存在的页面
#: P6-B-23：旧 AI 助教页 /tutor 与旧 p3-06 实验页也已退役
EXISTING_PAGES = ("/", "%s/text" % UNIT1, "/textbook", "/progress")

#: P6-B-12c：旧菜单的作答保护页常量（vocab/phrase/reading/listening-drill）已随旧七项菜单退役

EMOJI = re.compile("[\U0001F300-\U0001FAFF\u25b6\u2190\u2b50\u2600-\u26ff]")


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


class V13HttpTest(unittest.TestCase):
    """第三版 Demo 页面级验收（临时 learning.db 副本）。"""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="zhixue_demo_v13_"))
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

    def _get(self, opener, path, raw=False):
        try:
            with opener.open("http://127.0.0.1:%d%s" % (self.port, path), timeout=90) as r:
                data = r.read()
                return r.status, (data if raw else data.decode("utf-8")), \
                    r.headers.get("Content-Type", "")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8", "replace"), ""

    def _page(self, path):
        st, body, _ct = self._get(self._client(), path)
        self.assertEqual(st, 200, path)
        return body

    # ---------------- 1：一级导航彻底删除 ----------------
    def test_08_official_data_untouched(self):
        self.assertEqual(sha256_file(content_mod.LEARNING_DB), OFFICIAL_DB_SHA)
        self.assertEqual(sha256_file(content_mod.CONTENTPACK), CONTENTPACK_SHA)

    def test_09_no_ai_call_no_new_dependency(self):
        for name in ("app.py", "ui.py", "content.py", "flow.py", "demo_data.py",
                     "pdf_pages.py"):
            src = (HERE / name).read_text(encoding="utf-8").lower()
            for token in ("openai", "deepseek", "ollama", "anthropic", "requests.",
                          "http.client", "socket.", "transformers", "torch",
                          "tensorflow"):
                self.assertNotIn(token, src, "%s 不得包含 AI / 网络调用：%s" % (name, token))
        for frame in ("import react", "import vue", "from react", "from vue",
                      "cdn.jsdelivr", "unpkg.com"):
            self.assertNotIn(frame, ui.STYLE.lower())
            self.assertNotIn(frame, (HERE / "ui.py").read_text(encoding="utf-8").lower())

    def test_10_plain_visits_never_write_demo_state(self):
        """打开页面不会产生学习状态：只有真实学习行为（POST /demo/learn）才会写本机 Cookie。"""
        opener = self._client()
        for path in EXISTING_PAGES:
            with opener.open("http://127.0.0.1:%d%s" % (self.port, path), timeout=90) as r:
                self.assertEqual(r.status, 200, path)
                cookie = r.headers.get("Set-Cookie") or ""
            self.assertNotIn("zx_demo", cookie, "%s 不得写入演示学习状态" % path)


class V4RevisionTest(unittest.TestCase):
    r"""第四轮修订：统一进度条 / 听音辨词状态链 / 文字—音频对应 / 错题池（演示）。"""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="zhixue_v4_"))
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
        return jar, urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def _get(self, opener, path):
        with opener.open("http://127.0.0.1:%d%s" % (self.port, path), timeout=90) as r:
            return r.read().decode("utf-8")

    def _post(self, opener, path, data):
        req = urllib.request.Request("http://127.0.0.1:%d%s" % (self.port, path),
                                     data=urllib.parse.urlencode(data).encode("utf-8"))
        with opener.open(req, timeout=60) as r:
            return r.status

    # ---------------- 1：统一进度条 ----------------
    def test_06_wrong_pool_is_not_a_new_product_center(self):
        body = self._get(self._client()[1], "/")
        text = visible(body)
        for bad in ("错题池", "错题本", "错题管理"):
            self.assertNotIn(bad, text, "错题池不能变成新的一级入口：%s" % bad)
        self.assertNotIn('<nav class="nav"', body)
        for href in ('href="/wrong"', 'href="/mistakes"'):
            self.assertNotIn(href, body)

    # ---------------- 5：音频按钮布局 ----------------
if __name__ == "__main__":
    unittest.main(verbosity=2)
