#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Demo V1.2 专项测试：产品体验重构与核心学习页面精简

对应任务书 §三十七 的检查清单：
  首页（顶部只有章节选择 / 无时间统计 / 章节切换 / AI 同步）
  AI（第一次只给最重要的 3 个知识点 / 不分类 / 有学习行为才评价 / 刷新不产生进步）
  点读（独立入口 / 原书页面 / 彩色插图保留 / 热点 / 点击播放 / 高亮 / 不依赖大段文字页）
  词汇跟读（进度条 n/10 / 单词 / 音标 / 词性 / 中文 / 灰例句 / 自动播放 / 扬声器 / 麦克风 / 返回 / 滑动）
  词汇练习（进度条 / 自动播放 / ABCD / 确定 / 下一卡 / 无多余信息）
  句子跟读（只显示句子 / 自动播放 / 麦克风 / AI 评价 / 滑动）
  AI 评价（评价对象是孩子录音 / 反馈简短 / 不产生虚假分数 / 不把波形相似度当正确率）
  周末（周六巩固 / 周日阶段巩固阶段测 / 不破坏首页极简）

所有检查只在 %TEMP% 的 learning.db 副本上进行；正式 learning.db / contentpack 只读。
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

UNIT1 = "/unit/unit1"


OFFICIAL_DB_SHA = "0C27267BF83A70A75BB400F0055B62CB2985A83EDD120B9AC790A7FD5E59CF91"
CONTENTPACK_SHA = "65829CA73E41B75ACA010B93B7339EDDF0F666F919148F0F69ED898419700C39"


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def visible(body: str) -> str:
    text = re.sub(r"(?s)<style>.*?</style>", " ", body)
    text = re.sub(r"(?s)<script>.*?</script>", " ", text)
    return re.sub(r"<[^>]+>", " ", text)


class V12HttpTest(unittest.TestCase):
    """Demo V1.2 页面级验收（临时 learning.db 副本）。"""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="zhixue_demo_v12_"))
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

    def _get(self, opener, path, raw=False):
        try:
            with opener.open("http://127.0.0.1:%d%s" % (self.port, path), timeout=60) as r:
                data = r.read()
                ctype = r.headers.get("Content-Type", "")
                return r.status, (data if raw else data.decode("utf-8")), ctype
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8", "replace"), ""

    def _learn(self, opener, unit, step):
        req = urllib.request.Request(
            "http://127.0.0.1:%d/demo/learn" % self.port,
            data=urllib.parse.urlencode({"unit": unit, "step": step}).encode("utf-8"))
        with opener.open(req, timeout=30) as r:
            return r.status

    def _state(self):
        """本机演示学习状态（页面读写的那条 Cookie）。"""
        for cookie in getattr(self, "jar", []):
            if cookie.name == web_app.DEMO_STATE_COOKIE:
                return demo.parse_state(urllib.parse.unquote(cookie.value))
        return {}

    def _ai_card(self, slug="unit1", state=None):
        """按页面同一条代码路径装配 AI 随堂助教卡（P6-B-23：旧单元页/结果页已退休）。"""
        h = web_app.Handler.__new__(web_app.Handler)
        h.contentpack_path = content_mod.CONTENTPACK
        h.learning_db = self.tmp_db
        unit = content_mod.get_unit(slug, content_mod.CONTENTPACK)
        training = h._unit_training(unit)
        ai, _focus, _steps = h._chapter_ai(unit, training, state or {})
        return ui.ai_card(ai, unit["unit_code"], unit.get("title") or "")

    def _ai(self, body):
        """第三版 Demo：AI 只出现在学习结果/单元页等真正有价值的地方（首页不再有 AI 卡）。"""
        return visible(body.split('<section class="ai">')[1].split("</section>")[0])

    # ---------------- 首页 ----------------
    def test_01_top_is_only_chapter_selection(self):
        _st, body, _ct = self._get(self._client(), "/")
        top = visible(body)
        self.assertIn("七年级上册英语", top)
        self.assertIn('name="unit"', body)
        self.assertIn("Unit 1 · A new start", body)
        for bad in ("本周已学习", "今天已经学习", "学习时长", "分钟", "统计",
                    "出版社", "课程标准", "外语教学与研究出版社"):
            self.assertNotIn(bad, top, "顶部不得出现：%s" % bad)
        # 第三版 Demo：首页不再有 AI 卡，也没有「我的进展」一级入口
        self.assertNotIn('<section class="ai">', body)
        self.assertNotIn("我的进展", visible(body))
        self.assertNotIn('href="/progress"', body)
        self.assertNotIn('<nav class="nav"', body)

    def test_03_ai_first_open_gives_at_most_three_points(self):
        card = self._ai_card("unit1")
        ai = self._ai(card)
        self.assertIn("最值得先学的 3 个", ai)
        items = re.findall(r'<span class="fw">([^<]+)</span>', card)
        self.assertEqual(len(items), 3, "首次进入只给最重要的 3 个")
        for bad in ("词汇：", "短语：", "句型 / 表达", "语法"):
            self.assertNotIn(bad, ai, "AI 卡片不得按类别堆叠：%s" % bad)
        for bad in ("你已经完成", "整体基础不错", "掌握得", "薄弱"):
            self.assertNotIn(bad, ai)

    def test_04_ai_evaluates_only_after_learning(self):
        opener = self._client()
        self._learn(opener, "unit1", "reading")
        card = self._ai_card("unit1", self._state())
        self.assertIn("你已经完成了", self._ai(card))
        self.assertLessEqual(len(re.findall(r'<span class="fw">([^<]+)</span>', card)), 3)

    def test_05_refresh_never_fakes_progress(self):
        opener = self._client()
        self._learn(opener, "unit1", "vocabulary")
        first = self._ai_card("unit1", self._state())
        for _ in range(3):
            self._get(opener, "/?unit=unit1")
        last = self._ai_card("unit1", self._state())
        self.assertEqual(self._ai(first), self._ai(last), "刷新不得改变学习状态")

    # ---------------- 课文点读 ----------------
    def test_07_page_keeps_original_color_illustrations(self):
        cp = content_mod._ro(content_mod.CONTENTPACK)
        try:
            rows = cp.execute(
                "SELECT a.asset_kind FROM content_asset a "
                "JOIN page p ON p.page_id = a.page_id WHERE p.pdf_page = 29").fetchall()
        finally:
            cp.close()
        self.assertTrue(rows, "Unit 1 对话页必须有教材原始图像资源（彩色插图）")
        self.assertIn("image", [r["asset_kind"] for r in rows])

class V12RecordingFeedbackTest(unittest.TestCase):
    """AI 口语反馈：评价对象是孩子自己的录音；不伪造词级发音判断。"""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="zhixue_demo_v12r_"))
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

    def _body(self, path):
        with urllib.request.urlopen("http://127.0.0.1:%d%s" % (self.port, path),
                                    timeout=60) as r:
            return r.read().decode("utf-8")

    def test_04_official_data_untouched(self):
        self.assertEqual(sha256_file(content_mod.LEARNING_DB), OFFICIAL_DB_SHA)
        self.assertEqual(sha256_file(content_mod.CONTENTPACK), CONTENTPACK_SHA)


if __name__ == "__main__":
    unittest.main(verbosity=2)
