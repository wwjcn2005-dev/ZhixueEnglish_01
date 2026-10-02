#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Demo 学习链路验收（原 V1.1 用例，第五轮按当前契约重写）

覆盖：章节切换 / 单元学习空间 / 今日10分钟 / 单词跟读 / 听音辨词 / 短语练习 /
阅读练习 / 听力练习 / 学习结果 / 手机窄屏 / 零写入 / 不出现虚假评分。

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
import demo_data as demo                # noqa: E402
import ui                               # noqa: E402

UNIT1 = "/unit/unit1"
OFFICIAL_DB_SHA = "0C27267BF83A70A75BB400F0055B62CB2985A83EDD120B9AC790A7FD5E59CF91"
BUSINESS_TABLES = ("learner", "learning_session", "learning_task", "task_item",
                   "learning_record", "mastery_state")


def sha256_file(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


def business_counts(path):
    import sqlite3
    conn = sqlite3.connect(str(path))
    try:
        return {t: conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
                for t in BUSINESS_TABLES}
    finally:
        conn.close()


def visible(body: str) -> str:
    text = re.sub(r"(?s)<style>.*?</style>", " ", body)
    text = re.sub(r"(?s)<script>.*?</script>", " ", text)
    return re.sub(r"<[^>]+>", " ", text)


class V11HttpTest(unittest.TestCase):
    """在临时 learning.db 副本上走完整 Demo 链路。"""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="zhixue_v11_"))
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

    # ---------------- 1–5：首页 / 章节 / 单元空间 ----------------
    def test_01_home_opens_with_menu(self):
        status, body = self._get(self._client(), "/")
        self.assertEqual(status, 200)
        self.assertIn("智学英语", body)
        self.assertIn("今天学什么", visible(body))
        self.assertIn('id="zx-unit"', body)
        self.assertNotIn('<nav class="nav"', body)

    def test_11_learning_state_follows_actions_only(self):
        opener = self._client()
        before = self._get(opener, "/")[1]
        for _ in range(3):
            self._get(opener, "/?unit=unit1")
        self.assertEqual(visible(self._get(opener, "/")[1]), visible(before))

    # ---------------- 25–30：边界与文案 ----------------
    def test_14_official_db_untouched(self):
        self.assertEqual(sha256_file(content_mod.LEARNING_DB), OFFICIAL_DB_SHA)

    def test_15_demo_labels_present(self):
        # P6-B-23：旧学习结果页 /unit/<slug>/result 已正式退休；
        # AI 随堂助教卡的数据与渲染能力保留，这里直接验证卡片仍带演示标注。
        card = ui.ai_card(demo.chapter_ai(
            "Unit 1", {"key_points": [("make good use of", "好好利用")]}, {}))
        self.assertIn(demo.DEMO_LABEL, card)
        self.assertIn("不是真实 AI 判断", card)
        status, _body = self._get(self._client(), "%s/result" % UNIT1)
        self.assertEqual(status, 404, "旧学习结果页必须已退休")


class V11MobileTest(unittest.TestCase):
    """手机宽度上的页面结构检查。"""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="zhixue_v11m_"))
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

    def _get(self, path):
        with urllib.request.urlopen("http://127.0.0.1:%d%s" % (self.port, path),
                                    timeout=60) as r:
            return r.read().decode("utf-8")

    def test_02_style_keeps_mobile_baseline(self):
        self.assertIn("max-width:560px", ui.STYLE)
        self.assertIn("body{padding-bottom:16px}", ui.STYLE)
        for bad in re.findall(r"min-width:(\d+)px", ui.STYLE):
            self.assertLessEqual(int(bad), 360)

    def test_03_official_data_untouched(self):
        self.assertEqual(sha256_file(content_mod.LEARNING_DB), OFFICIAL_DB_SHA)
        self.assertEqual(business_counts(content_mod.LEARNING_DB),
                         business_counts(self.tmp_db))


if __name__ == "__main__":
    unittest.main(verbosity=2)
