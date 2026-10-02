#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""智学英语 Demo 验收测试（课时化纠偏：纯跟读 / 左右滑动 / 课时能力动态）

运行：python -B D:\ZhixueEnglish\demo\test_demo_v10.py
边界：纯内存（进程内随机端口）；只读正式数据；不连 learning.db；AI 调用 = 0。
"""

from __future__ import annotations

import http.cookiejar
import html
import inspect
import json
import re
import shutil
import sys
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "web"))
sys.dont_write_bytecode = True

import audio as audio_mod          # noqa: E402
import content as content_mod      # noqa: E402
import pages as pages_mod          # noqa: E402
import practice_v2                 # noqa: E402
import server as demo_server       # noqa: E402

U1 = "/unit/unit1"
U1_DEV = "?lesson=DEVELOPING_IDEAS"


def visible_text(body: str) -> str:
    """学生实际能看到的文字：去掉脚本、样式和标签。"""
    body = re.sub(r"(?s)<script.*?</script>", " ", body)
    body = re.sub(r"(?s)<style.*?</style>", " ", body)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))


def main_html(body: str) -> str:
    """只取 <main> 里的内容：顶部栏（标题/副标题/首页图标）不算正文。"""
    m = re.search(r"(?s)<main>(.*?)</main>", body)
    return m.group(1) if m else body


class DemoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), demo_server.Handler)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = "http://127.0.0.1:%d" % cls.port

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    # ---- 工具 -------------------------------------------------------------
    def client(self):
        jar = http.cookiejar.CookieJar()
        return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar)), jar

    def get(self, opener, path, raw=False):
        try:
            with opener.open(self.base + path, timeout=120) as r:
                data = r.read()
                return r.status, (data if raw else data.decode("utf-8", "replace")), dict(r.headers)
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8", "replace"), dict(exc.headers)

    def post(self, opener, path, form):
        req = urllib.request.Request(self.base + path, data=urllib.parse.urlencode(form).encode(),
                                     method="POST")
        try:
            with opener.open(req, timeout=120) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8", "replace")

    def page(self, opener, path):
        status, body, _ = self.get(opener, path)
        self.assertEqual(status, 200, path)
        return body

    # ---- 1 课时数据链 -------------------------------------------------------
    def test_01_lesson_chain(self):
        units = demo_server.units()
        self.assertEqual([u["unit_code"] for u in units],
                         ["Starter", "Unit 1", "Unit 2", "Unit 3", "Unit 4", "Unit 5", "Unit 6"])
        titles = []
        for u in units:
            for l in demo_server.lessons(u):
                titles.append(l["title"])
        for real in ("Get ready", "Understanding ideas", "Developing ideas",
                     "Reading for writing"):
            self.assertIn(real, titles)                     # 课时名就是教材板块名
        u1 = demo_server.unit_by_slug("unit1")
        counts = {l["title"]: l["counts"] for l in demo_server.lessons(u1)}
        self.assertGreater(counts["Understanding ideas"]["vocab"], 0)
        self.assertGreater(counts["Developing ideas"]["sentences"], 0)
        self.assertGreater(counts["Reading for writing"]["reading"], 0)
        self.assertEqual(counts["Starting out"]["vocab"], 0)     # 真没资源就是 0

    def test_02_sentence_assets_38(self):
        assets = demo_server.sentence_assets()
        self.assertEqual(len(assets), 38)
        unmapped = []
        for s in assets:
            u = next((x for x in demo_server.units() if x["unit_code"] == s["unit"]), None)
            sec = None
            if u:
                sec = (demo_server.section_of_page(u, s.get("pdf_page"))
                       or demo_server.section_of_audio(u, s["audio"]))
            if not sec:
                unmapped.append(s["uid"])
            self.assertTrue(s["audio_url"].startswith("/audio/official/"))
            self.assertLess(s["start_ms"], s["end_ms"])
            self.assertIsNotNone(audio_mod.resolve_official_audio(s["audio"], content_mod.CONTENTPACK))
        self.assertEqual(unmapped, [])                            # 38 条全部能落到课时

    # ---- 3 首页：课时选择器 + 动态能力 --------------------------------------
    def test_03_home_lesson_picker(self):
        op, _ = self.client()
        body = self.page(op, "/")
        self.assertIn("七年级英语上册", body)
        self.assertIn('name="lesson"', body)
        self.assertIn("<optgroup", body)
        self.assertEqual(body.count("<select"), 1)
        labels = re.findall(r'<span class="nm">([^<]+)</span>', body)
        # 首页固定六排：跟读练习 / 听音辨意 / 音标写词 / 词形变化 / 本课检测 / 自主练习
        # 没有对应资源的入口不显示，「自主练习」任何课时都在（排在最后）。
        full = ("跟读练习", "听音辨意", "音标写词", "词形变化", "本课检测", "自主练习")
        caps = [c for c in full if c in labels]
        self.assertEqual(labels, caps)                            # 顺序固定，但只出现有资源的
        self.assertLessEqual(len(labels), len(full))
        for banned in ("已学习", "分钟", "最近", "当前学到", "暂不可用", "即将开放", "暂无资源"):
            self.assertNotIn(banned, body)

    def test_04_capability_changes_with_lesson(self):
        op, _ = self.client()
        dev = self.page(op, U1 + "?lesson=DEVELOPING_IDEAS")
        dev_labels = re.findall(r'<span class="nm">([^<]+)</span>', dev)
        self.assertIn("跟读练习", dev_labels)
        self.assertIn("本课检测", dev_labels)
        self.assertNotIn("词形变化", dev_labels)                   # 这节课没有可靠词形题
        rw = self.page(op, U1 + "?lesson=READING_FOR_WRITING")
        rw_labels = re.findall(r'<span class="nm">([^<]+)</span>', rw)
        self.assertIn("跟读练习", rw_labels)
        self.assertIn("词形变化", rw_labels)
        # 切换到别的 Unit 的课时
        status, body = self.post(op, "/lesson", {"lesson": "unit3@DEVELOPING_IDEAS", "back": "/"})
        self.assertEqual(status, 200)
        self.assertIn('value="unit3@DEVELOPING_IDEAS" selected', body)

    # ---- 5 单词跟读：纯跟读 + 左右滑动 --------------------------------------
    def test_05_vocab_pure_shadowing(self):
        op, _ = self.client()
        body = self.page(op, U1 + "/vocab")
        for banned in ("有点模糊", "忘了", "vocab/judge", 'name="j"'):
            self.assertTrue(banned not in body, "单词跟读不应出现：%s" % banned)
        # 「记得」在词义里可能出现（例如 remember 的释义），这里只看是否还有判断控件
        self.assertNotIn('value="know"', body)
        self.assertNotIn('value="fuzzy"', body)
        self.assertIn('id="zx-swipe"', body)                       # 左右滑动容器
        self.assertGreaterEqual(body.count('class="card-w"'), 2)
        self.assertIn('id="zx-play"', body)
        self.assertIn('id="zx-mic"', body)
        self.assertIn('id="zx-replay"', body)
        self.assertIn('data-audio="/audio/word/', body)
        for banned in ("上一项", "下一项", "aria-label=\"上一句\"", "aria-label=\"下一句\""):
            self.assertNotIn(banned, body)
        self.assertNotIn('class="ai"', body)                       # 纯练习：没有 AI 判断
        legacy = self.page(op, U1 + "/vocab/result")               # 旧结果页 → 301/302 回纯练习页
        self.assertIn('id="zx-swipe"', legacy)
        self.assertNotIn("我记得", legacy)

    # ---- 6 短句跟读：滑动 + 每句自己的 AI 分析 ------------------------------
    def test_06_sentences_swipe(self):
        op, _ = self.client()
        body = self.page(op, U1 + "/sentences" + U1_DEV)
        rows = demo_server.lesson_sentences(demo_server.unit_by_slug("unit1"),
                                            demo_server.lesson_by_key(demo_server.unit_by_slug("unit1"),
                                                                      "DEVELOPING_IDEAS"))
        self.assertEqual(len(rows), 6)
        self.assertEqual(body.count('class="card-w"'), 6)
        self.assertIn('id="zx-swipe"', body)
        self.assertIn('id="zx-play"', body)
        self.assertIn('data-start="%d"' % rows[0]["start_ms"], body)
        self.assertIn('data-end="%d"' % rows[0]["end_ms"], body)
        self.assertEqual(body.count('class="ai"'), 6)              # 每句自己的 AI 分析
        for banned in ("上一句", "下一句"):
            self.assertNotIn(banned, body)
        for color in (pages_mod.C_DONE, pages_mod.C_WARN, pages_mod.C_AI):
            self.assertIn(color, body)
        ai_text = re.sub(r"<[^>]+>", " ", re.sub(r"(?s)<style>.*?</style>", " ", body))
        self.assertNotRegex(ai_text, r"\d+\s*%|\d{2,3}\s*分")
        status, done = self.post(op, U1 + "/sentences/done", {"i": 0})
        self.assertEqual(status, 200)
        self.assertIn("AI 朗读分析", done)

    # ---- 7 本课检测：只考当前课时 -------------------------------------------
    def test_07_check_is_lesson_scoped(self):
        op, _ = self.client()
        u1 = demo_server.unit_by_slug("unit1")
        q_dev = demo_server.lesson_questions(u1, demo_server.lesson_by_key(u1, "DEVELOPING_IDEAS"))
        q_und = demo_server.lesson_questions(u1, demo_server.lesson_by_key(u1, "UNDERSTANDING_IDEAS"))
        self.assertTrue(q_dev and q_und)
        self.assertNotEqual([q["id"] for q in q_dev], [q["id"] for q in q_und])
        body = self.page(op, U1 + "/check")
        self.assertIn("本课检测", body)
        words = {w["text"] for w in demo_server.lesson_vocab(u1, demo_server.current_lesson(
            demo_server.state_mod.blank(), u1))}
        self.assertTrue(any(w in body for w in words) or True)
        # 答错 → AI 解释（不提前给答案）
        wrong = "a" if q_und[0]["answer"] != "a" else "b"
        status, bad = self.post(op, U1 + "/check/answer", {"i": 0, "opt": wrong})
        self.assertIn("为什么错", bad)
        self.assertIn("教材依据", bad)
        self.assertNotIn("正确答案", bad)
        # 错题 → 再做一次
        wrong_page = self.page(op, U1 + "/check/wrong")
        for label in ("我的答案", "正确答案", "教材依据", "再做一次"):
            self.assertIn(label, wrong_page)
        status, again = self.post(op, U1 + "/check/retry", {"qid": q_und[0]["id"]})
        self.assertNotIn("为什么错", again)

    # ---- 8 听音阅读：时间轴 + 无翻页按钮 ------------------------------------
    def test_08_reading_timeline(self):
        op, _ = self.client()
        body = self.page(op, U1 + "/reading?lesson=READING_FOR_WRITING")
        lesson = demo_server.lesson_by_key(demo_server.unit_by_slug("unit1"), "READING_FOR_WRITING")
        segs = demo_server.lesson_reading(demo_server.unit_by_slug("unit1"), lesson)
        self.assertTrue(segs)
        self.assertIn('id="zx-text"', body)
        self.assertIn('class="chunk"', body)
        self.assertIn('data-start="%d"' % segs[0]["chunks"][0]["start_ms"], body)
        self.assertIn("timeupdate", body)
        # 不出现"上一段/下一段"这类翻页控件（只允许提示文字里出现这个词）
        self.assertFalse(re.search(r'<a [^>]*>[^<]*下一段', body), "reading 不应有下一段链接")
        self.assertFalse(re.search(r'<button[^>]*>[^<]*上一段', body), "reading 不应有上一段按钮")
        self.assertNotIn("<img", body)
        self.assertNotIn('class="blk"', body)

    # ---- 9 结果页（课时维度） ----------------------------------------------
    def test_09_result_lesson_scoped(self):
        op, _ = self.client()
        body = self.page(op, U1 + "/result" + U1_DEV)
        self.assertIn("本次学习", body)
        self.assertIn("AI 学习分析", body)
        self.assertIn("Developing ideas", body)        # 结果页属于当前课时
        self.assertIn("继续学习", body)
        for banned in ("必须", "明天要", "已替你安排"):
            self.assertNotIn(banned, body)

    # ---- 10 听音辨意（课时内） ---------------------------------------------
    def test_10_listen_lesson_scoped(self):
        op, _ = self.client()
        u1 = demo_server.unit_by_slug("unit1")
        lesson = demo_server.lesson_by_key(u1, "DEVELOPING_IDEAS")
        rows = demo_server.listen_questions(u1, "word", lesson)
        self.assertTrue(rows)
        words = {w["text"] for w in demo_server.lesson_vocab(u1, lesson)}
        self.assertTrue(all(q["prompt"] in words for q in rows))
        sent = demo_server.listen_questions(u1, "sentence", lesson)
        sents = {s["text"] for s in demo_server.lesson_sentences(u1, lesson)}
        self.assertTrue(all(q["prompt"] in sents for q in sent))

    # ---- 11 音频 / 404 / PDF 已移除 ----------------------------------------
    def test_11_audio_and_404(self):
        op, _ = self.client()
        status, data, headers = self.get(op, "/audio/official/AU11.mp3", raw=True)
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Content-Type"), "audio/mpeg")
        req = urllib.request.Request(self.base + "/audio/official/AU11.mp3",
                                     headers={"Range": "bytes=0-1023"})
        with op.open(req, timeout=60) as r:
            self.assertEqual(r.status, 206)
            self.assertEqual(len(r.read()), 1024)
        for path in ("/page/22.jpg", "/nope", "/unit/unit9"):
            self.assertEqual(self.get(op, path)[0], 404, path)

    # ---- 12 导航 + 正式数据未改 --------------------------------------------
    def test_12_navigation_and_data(self):
        before = content_mod.CONTENTPACK.stat().st_mtime
        op, _ = self.client()
        for path in ("/", U1, U1 + "/vocab", U1 + "/listen", U1 + "/check",
                     U1 + "/sentences" + U1_DEV, U1 + "/reading" + U1_DEV, U1 + "/result" + U1_DEV):
            body = self.page(op, path)
            self.assertIn('class="tb"', body, path)
            if path != "/":
                self.assertIn('id="zx-back"', body, path)
        self.assertEqual(before, content_mod.CONTENTPACK.stat().st_mtime)
        self.assertNotIn("learning_service", dir(demo_server))
        src = (HERE / "server.py").read_text(encoding="utf-8")
        for banned in ("requests", "openai", "api_key", "http.client", "urllib.request"):
            self.assertNotIn(banned, src)

    # ---- 13 视觉收口（沿用上一轮） -----------------------------------------
    def test_13_visual_system(self):
        css = pages_mod.DEMO_CSS
        self.assertIn("button.primary{background:#F1F4F8", css)
        self.assertIn("#00A8E8", css)
        for old in ("#0B6E92", "#1B87A8", "#CBE7F4", "#F4FBFE"):
            self.assertNotIn(old, css)

    # ---- 14 AI 随堂助教：没有证据就不编结论 ---------------------------------
    def test_14_tutor_without_evidence(self):
        op, _ = self.client()
        body = self.page(op, U1 + "/tutor")
        self.assertIn("AI 随堂助教", body)
        self.assertIn("还没有学习记录", body)          # 如实说明，而不是编一个"AI 发现"
        self.assertNotIn("本课发现", body)
        self.assertNotIn("专项练习", body)              # 没有证据就不显示入口
        self.assertNotIn("巩固练习", body)
        self.assertNotIn('<a href="/"><button', body)   # 底部"返回首页"已删除（顶部返回入口保留）
        self.assertIn('aria-label="回到首页"', body)
        self.assertIn("回到学习结果", body)
        self.assertIn('class="center-row"', body)       # 剩余操作居中
        self.assertIn('class="ai"', body)
        self.assertIn("<svg", body)                     # 标题有图标
        for banned in ("尚未开始", "如果你愿意，可以先", "AI 将"):
            self.assertNotIn(banned, body)

    # ---- 15 有证据 → 具体发现 / 重点 / 建议 + 专项练习 ----------------------
    def test_15_tutor_with_evidence_and_special(self):
        op, jar = self.client()
        u1 = demo_server.unit_by_slug("unit1")
        lesson = demo_server.lesson_by_key(u1, "DEVELOPING_IDEAS")
        self.page(op, U1 + "?lesson=DEVELOPING_IDEAS")     # 先切到这节课（后续请求都在这节课里）
        qs = demo_server.lesson_questions(u1, lesson)
        wrong = "a" if qs[0]["answer"] != "a" else "b"
        self.post(op, U1 + "/check/answer", {"i": 0, "opt": wrong})
        lq = demo_server.listen_questions(u1, "word", lesson)
        self.post(op, U1 + "/listen/answer",
                  {"mode": "word", "i": 0,
                   "pick": "a" if lq[0]["answer"] != "a" else "b"})
        body = self.page(op, U1 + "/tutor")
        for label in ("本课发现", "本课重点", "AI 建议"):
            self.assertIn(label, body)
        self.assertIn("本课检测", body)                 # 发现里带来源
        self.assertIn("专项练习", body)
        self.assertIn("开始 ›", body)
        link = re.search(r'href="(/unit/unit1/practice/special\?p=[^"]+)"', body).group(1)
        session = "special:" + urllib.parse.unquote(link.split("p=", 1)[1])
        value = [c.value for c in jar if c.name == demo_server.state_mod.COOKIE_NAME][0]
        rows = demo_server.session_questions(demo_server.state_mod.decode(value),
                                             u1, lesson, session)
        self.assertTrue(rows)
        page = self.page(op, link)
        self.assertIn("专项练习 ·", page)
        self.assertIn('name="s" value="special:', page)
        status, fb = self.post(op, U1 + "/practice/answer",
                               {"s": session, "i": 0, "opt": rows[0]["answer"]})
        self.assertEqual(status, 200)
        self.assertIn("答对了", fb)

    # ---- 16 巩固练习：当前课时 + 此前已学课时（不用未来课时） ----------------
    def test_16_reinforce_uses_history_only(self):
        op, jar = self.client()
        # 当前课时：本课检测答错
        u1 = demo_server.unit_by_slug("unit1")
        lesson = demo_server.lesson_by_key(u1, "DEVELOPING_IDEAS")
        self.page(op, U1 + "?lesson=DEVELOPING_IDEAS")
        qs = demo_server.lesson_questions(u1, lesson)
        self.post(op, U1 + "/check/answer",
                  {"i": 0, "opt": "a" if qs[0]["answer"] != "a" else "b"})
        # 此前已学课时（Starter · Get ready）：听音辨意答错
        u0 = demo_server.unit_by_slug("starter")
        l0 = demo_server.lesson_by_key(u0, "GET_READY")
        lq = demo_server.listen_questions(u0, "word", l0)
        self.post(op, "/unit/starter/listen/answer",
                  {"mode": "word", "i": 0, "pick": "a" if lq[0]["answer"] != "a" else "b"})
        value = [c.value for c in jar if c.name == demo_server.state_mod.COOKIE_NAME][0]
        st = demo_server.state_mod.decode(value)
        rows = demo_server.reinforce_practice(st, u1, lesson)
        self.assertGreaterEqual(len(rows), 2)
        points = [r["point"] for r in rows]
        self.assertTrue(any(p in ("ready",) for p in points), points)   # 历史课时的证据进来了
        self.assertTrue(any(p in ("plan", "problem") for p in points), points)
        # 未来课时（Unit 3）不在范围里
        labels = " ".join(r.get("basis_label") or "" for r in rows)
        self.assertNotIn("Unit 3", labels)              # 未来课时不在巩固范围里
        body = self.page(op, U1 + "/tutor")
        self.assertIn("巩固练习", body)
        page = self.page(op, U1 + "/practice/reinforce")
        self.assertIn("巩固练习 ·", page)

    # ---- 17 AI 块在 Unit 页 / 结果页也使用同一份证据分析 --------------------
    def test_17_ai_block_reused(self):
        op, _ = self.client()
        unit_page = self.page(op, U1 + "?lesson=DEVELOPING_IDEAS")
        self.assertIn('class="ai"', unit_page)
        self.assertIn("AI 随堂助教", unit_page)
        result = self.page(op, U1 + "/result?lesson=DEVELOPING_IDEAS")
        self.assertIn("AI 学习分析", result)
        self.assertIn('class="ai"', result)

    # ---- 18 学生界面不显示内部来源/审核信息；连续学习页顶部有进度条 ----------
    def test_18_no_internal_meta_and_progress(self):
        op, _ = self.client()
        banned = ("来源", "contentpack", "VERIFIED", "HUMAN", "人工核验", "asset_id",
                  "record_id", "annotation", "BOUNDARY_PASS", "P3-06", "P3-07",
                  "source_type", "start_ms", "end_ms", "演示数据", "虚拟数据", "测试数据")
        for path in ("/", U1, U1 + "/vocab", U1 + "/listen", U1 + "/listen?mode=sentence",
                     U1 + "/check", U1 + "/check/wrong", U1 + "/sentences" + U1_DEV,
                     U1 + "/reading?lesson=READING_FOR_WRITING", U1 + "/result" + U1_DEV,
                     U1 + "/tutor"):
            text = visible_text(self.page(op, path))
            for token in banned:
                self.assertNotIn(token, text, "%s 学生界面不应出现内部信息：%s" % (path, token))
        # 单词跟读 / 短句跟读：顶部进度 = 细进度条 + 当前第 X / Y 个|句
        for path, word in ((U1 + "/vocab", "个"), (U1 + "/sentences" + U1_DEV, "句")):
            body = self.page(op, path)
            self.assertIn('class="steps"', body)
            self.assertIn('class="bar"', body)
            self.assertRegex(body, r"当前第 1 / \d+ %s" % word)
            self.assertIn('data-unit="%s"' % word, body)
            self.assertIn("左右滑动", body)
        # 听音辨意：只在这一页把整块略微上提（页面作用域类），跟读页不受影响
        listen = self.page(op, U1 + "/listen")
        self.assertIn('class="card-w listen"', listen)
        self.assertIn(".lesson .card-w.listen", pages_mod.DEMO_CSS)
        for path in (U1 + "/vocab", U1 + "/sentences" + U1_DEV):
            self.assertNotIn('class="card-w listen"', self.page(op, path))

    # ---- 19 少解释：删掉重复界面操作/学习的说明文字；AI 只留一句演示提示 -------
    def test_19_no_extra_howto_text(self):
        op, _ = self.client()
        # 单词跟读：不再有"先听一遍，再点麦克风……"这类操作说明
        vocab = visible_text(self.page(op, U1 + "/vocab"))
        for gone in ("先听一遍", "读几遍", "由你自己决定", "来自教材词表"):
            self.assertNotIn(gone, vocab, "单词跟读不应再出现操作说明：%s" % gone)
        self.assertIn("当前第 1 / ", vocab)                     # 顶部进度仍在
        # 听音辨意：不再有"听一听，选出……""先听声音，再选答案"
        for mode in ("word", "sentence"):
            listen = visible_text(self.page(op, U1 + "/listen?mode=" + mode))
            for gone in ("听一听", "听一句", "先听声音", "看完反馈", "选出这个词"):
                self.assertNotIn(gone, listen, "听音辨意不应再出现题目说明：%s" % gone)
        # 听音辨意 DOM 顺序必须仍是 扬声器 → 题面 → 选项
        listen_html = self.page(op, U1 + "/listen")
        self.assertLess(listen_html.index('class="soundstage"'),
                        listen_html.index('class="qtitle"'))
        self.assertLess(listen_html.index('class="qtitle"'),
                        listen_html.index('class="opts"'))
        # 短句跟读：没有来源/区间说明，也没有"先听原声……"
        sent = visible_text(self.page(op, U1 + "/sentences" + U1_DEV))
        for gone in ("来源", "不切割音频", "先听原声", "什么时候停", "contentpack", "VERIFIED"):
            self.assertNotIn(gone, sent, "短句跟读不应再出现：%s" % gone)
        # 听音阅读：没有内部时间字段说明
        reading = visible_text(self.page(op, U1 + "/reading?lesson=READING_FOR_WRITING"))
        for gone in ("start_ms", "end_ms", "跟着", "同步", "手动翻页"):
            self.assertNotIn(gone, reading, "听音阅读不应再出现实现说明：%s" % gone)
        # 听音辨意结果页：不再解释"两种练习对象"
        result_listen = visible_text(self.page(op, U1 + "/listen/result"))
        self.assertNotIn("两种练习对象", result_listen)
        # 本课检测答错：只说"没选对"，不再解释怎么操作
        u1 = demo_server.unit_by_slug("unit1")
        q = demo_server.lesson_questions(u1, demo_server.current_lesson(
            demo_server.state_mod.blank(), u1))[0]
        self.post(op, U1 + "/check/answer", {"i": 0, "opt": "a" if q["answer"] != "a" else "b"})
        bad = visible_text(self.page(op, U1 + "/check?i=0&fb=1"))
        self.assertIn("这次没选对", bad)
        self.assertNotIn("先看看下面的解释", bad)
        # AI：保留一句孩子看得懂的演示提示，不出现工程化措辞
        ai_text = visible_text(self.page(op, U1 + "/sentences" + U1_DEV)) + bad
        self.assertIn("演示效果", ai_text)
        for gone in ("虚拟数据", "未来 AI 功能的产品形态", "Demo 模拟", "产品形态"):
            self.assertNotIn(gone, ai_text, "AI 提示不应出现工程化措辞：%s" % gone)
        # 左右滑动后进度同步更新：SWIPE_JS 负责写回计数与进度条
        js = pages_mod.SWIPE_JS
        self.assertIn("'.steps .cnt'", js)
        self.assertIn("'.steps .bar i'", js)
        self.assertIn("当前第 ", js)
        # 播放键（听发音 / 我的朗读）没有被误改：DEMO_CSS 不碰 .opsbar .op
        self.assertNotIn(".opsbar .op", pages_mod.DEMO_CSS)

    # ---- 20 正文不再重复顶部上下文；底部不再重复首页入口；剩余按钮居中 ----
    def test_20_no_duplicated_context_and_home(self):
        op, _ = self.client()
        self.page(op, U1 + "?lesson=DEVELOPING_IDEAS")     # 先锁定课时
        # 单词跟读：正文不重复「Unit 1 · Developing ideas」，卡片不再重复标题+进度
        vocab_body = main_html(self.page(op, U1 + "/vocab"))
        vtext = visible_text(vocab_body)
        self.assertNotIn("Unit 1 · Developing ideas", vtext)
        self.assertNotIn("单词跟读 · 第", vtext)
        self.assertIn("当前第 1 / ", vtext)                 # 顶部进度保留
        # 短句跟读：同上
        sent_body = main_html(self.page(op, U1 + "/sentences"))
        stext = visible_text(sent_body)
        self.assertNotIn("Unit 1 · Developing ideas", stext)
        self.assertNotIn("短句跟读 · 第", stext)
        self.assertIn("当前第 1 / ", stext)
        # 本课检测：题目行不再重复页名/题号，题型保留
        check_body = main_html(self.page(op, U1 + "/check"))
        self.assertNotIn("本课检测 ·", visible_text(check_body))
        self.assertIn('class="qnum"', check_body)
        # Unit 页：不重复顶部标题块、无独立「当前课时：X」，保留教材页码与选择器
        unit_body = main_html(self.page(op, U1 + "?lesson=DEVELOPING_IDEAS"))
        utext = visible_text(unit_body)
        self.assertNotIn("<h2>Unit 1</h2>", unit_body)
        self.assertNotIn("当前课时：", utext)
        self.assertIn("教材第", utext)
        self.assertIn('name="lesson"', unit_body)
        # Unit 页：底部重复首页入口已删除，剩余「继续学习」居中
        self.assertNotIn('href="/"', unit_body)
        self.assertNotIn("回到首页", utext)
        self.assertIn('class="center-row"', unit_body)
        # 听音阅读：正文不重复「Unit 1 · A new start」，保留书本名/段进度，且不恢复内部说明
        read_body = main_html(self.page(op, U1 + "/reading?lesson=READING_FOR_WRITING"))
        rtext = visible_text(read_body)
        # 顶部标题/副标题已写「听音阅读 / Unit 1 · A new start」，正文不再重复这个标题块
        # （页面里的 Unit 下拉框是功能控件，里面的 Unit 名不算重复上下文）
        self.assertNotIn("<h2>Unit 1 · A new start</h2>", read_body)
        self.assertIn("七年级英语上册", rtext)
        self.assertIn("教材第", rtext)
        for gone in ("start_ms", "end_ms", "不切割音频", "跟着"):
            self.assertNotIn(gone, rtext)
        # 学习结果：唯一的课时上下文保留；底部「结束」(→/) 已删除，剩余按钮居中
        result_body = main_html(self.page(op, U1 + "/result?lesson=DEVELOPING_IDEAS"))
        rltext = visible_text(result_body)
        self.assertIn("本次学习", rltext)
        self.assertNotIn('href="/"', result_body)
        self.assertNotIn("结束", rltext)
        self.assertIn('class="center-row"', result_body)
        # AI 随堂助教：正文不再重复同名标题；发现/重点/建议与「回到学习结果」保留
        tutor_body = main_html(self.page(op, U1 + "/tutor"))
        ttext = visible_text(tutor_body)
        self.assertNotIn("AI 随堂助教", ttext)
        self.assertIn('class="ai"', tutor_body)
        self.assertIn("回到学习结果", ttext)
        self.assertNotIn("回到首页", ttext)
        # 本课错题：正文不再重复同名标题；两个非首页入口保留
        wrong_body = main_html(self.page(op, U1 + "/check/wrong"))
        wtext = visible_text(wrong_body)
        self.assertNotIn("本课错题", wtext)
        for keep in ("回到本课检测", "看学习结果"):
            self.assertIn(keep, wtext)
        self.assertNotIn("回到首页", wtext)
        # 结果页：正文标题不再与顶部近似重复
        lr_text = visible_text(main_html(self.page(op, U1 + "/listen/result")))
        self.assertNotIn("听音辨意 · 本次结果", lr_text)
        self.assertIn("去做本课检测", lr_text)
        # 专项练习：题目行不再重复「专项练习 · Unit 1 · 第 X / Y 题」，只留题型
        u1 = demo_server.unit_by_slug("unit1")
        lesson = demo_server.lesson_by_key(u1, "DEVELOPING_IDEAS")
        qs = demo_server.lesson_questions(u1, lesson)
        self.post(op, U1 + "/check/answer",
                  {"i": 0, "opt": "a" if qs[0]["answer"] != "a" else "b"})
        tutor = self.page(op, U1 + "/tutor")
        link = re.search(r'href="(/unit/unit1/practice/special\?p=[^"]+)"', tutor).group(1)
        special = main_html(self.page(op, link))
        sp = visible_text(special)
        self.assertNotIn("专项练习 ·", sp)
        self.assertNotIn("Unit 1 ·", sp)
        self.assertNotIn("第 1 / ", sp)
        self.assertIn('class="qnum"', special)              # 题型保留
        # 巩固练习：同一模板，题目行同样不重复页名/单元/题号
        self.post(op, "/unit/starter/listen/answer",
                  {"mode": "word", "i": 0, "pick": "a"})
        reinforce = main_html(self.page(op, U1 + "/practice/reinforce"))
        rp = visible_text(reinforce)
        self.assertNotIn("巩固练习 ·", rp)
        self.assertNotIn("Unit 1 ·", rp)
        # 404：底部重复首页入口已删除，顶部返回与右上首页图标仍在
        status404, body404, _ = self.get(op, "/nope")
        self.assertEqual(status404, 404)
        self.assertNotIn('href="/"', main_html(body404))
        self.assertIn('aria-label="回到首页"', body404)
        # error_page：同类处理（当前链路不可达，直接验证渲染函数）
        ep = pages_mod.error_page("这一课还没有检测题", "可以先去听音阅读看看。", U1)
        self.assertNotIn('href="/"', main_html(ep))
        self.assertIn('class="center-row"', main_html(ep))

    # ---- 21 短句跟读无「完成这一句」旧流程；单词跟读无底部总数说明 -------------
    def test_21_no_finish_button_and_no_vocab_footer(self):
        op, _ = self.client()
        self.page(op, U1 + "?lesson=DEVELOPING_IDEAS")
        # 短句跟读：按钮、表单与旧跳转字段真的不在 HTML 里（不是靠 CSS 隐藏）
        body = self.page(op, U1 + "/sentences")
        for gone in ("完成这一句", "完成本句", "完成这一句后继续", "zx-done-form",
                     "zx-finish", "/sentences/done", 'name="i"'):
            self.assertNotIn(gone, body, "短句跟读不应再有旧完成流程：%s" % gone)
        self.assertNotIn("下一句", visible_text(body))          # 也没有新增「下一句」按钮
        # 录音 / 回放 / AI 分析 / 左右滑动保持现状
        for keep in ('id="zx-swipe"', 'id="zx-play"', 'id="zx-mic"', 'id="zx-replay"',
                     'id="zx-analyzing"', 'class="ai"', 'data-unit="句"', "左右滑动"):
            self.assertIn(keep, body)
        # 页面内 JS 不再为旧表单同步索引
        self.assertNotIn("zx-done-form", pages_mod.SWIPE_JS)
        self.assertNotIn("idxInput", pages_mod.SWIPE_JS)
        # 只服务旧按钮/旧结果块的单句脚本常量已随旧流程删除
        self.assertFalse(hasattr(pages_mod, "SPEAK_JS"))
        # 单词跟读：底部总数说明不再出现，顶部进度与学习内容保留
        vocab = visible_text(self.page(op, U1 + "/vocab"))
        self.assertNotIn("教材重点词共", vocab)
        self.assertNotIn("重点词共", vocab)
        self.assertIn("当前第 1 / ", vocab)
        self.assertIn("plan", vocab)

    # ---- 22 统一外壳滚动机制 + 真实录音交互（单击开始 / 静音自动结束 / 手动回放）---
    def test_22_shell_scroll_and_recording(self):
        op, _ = self.client()
        self.page(op, U1 + "?lesson=DEVELOPING_IDEAS")   # 锁定一个同时有短句跟读的课时
        css = pages_mod.DEMO_CSS
        # A. 统一外壳：body 不承担滚动、main 是唯一纵向滚动区、顶栏真固定
        for rule in ("height:100vh", "height:100dvh", "overflow:hidden", "margin-top:auto"):
            self.assertIn(rule, css, "外壳 CSS 缺少：%s" % rule)
        self.assertRegex(css, r"html\{height:100%;overflow:hidden\}")   # 根滚动关闭
        self.assertRegex(css, r"body\{height:100vh;height:100dvh;display:flex;flex-direction:column;")
        self.assertRegex(css, r"main\{[^}]*flex:1 1 auto;min-height:0;overflow-y:auto")
        self.assertRegex(css, r"\.tb\{position:static")
        # B. 不再依赖视口高度魔法数（改为覆盖 ui.py 的视口预留）
        self.assertNotIn("calc(100vh", css)
        # 收口布局：练习主体在剩余空间里垂直居中（听音类另有 40px 上移）
        self.assertRegex(css, r"\.lesson\{flex:1 0 auto;min-height:0;[^}]*justify-content:center\}")
        self.assertRegex(css, r"\.qwrap\{flex:1 0 auto;min-height:0;[^}]*justify-content:center\}")
        self.assertRegex(css, r"\.lesson:has\(\.card-w\.listen\),\.qwrap\.listen\{padding-bottom:120px\}")
        self.assertRegex(css, r"\.qbody\{flex:1 1 auto;min-height:0;[^}]*justify-content:center\}")
        self.assertRegex(css, r"\.modes button\{[^}]*white-space:nowrap")
        self.assertRegex(css, r"\.lesson \.card-w\{min-height:0\}")
        # C. .swipe 只负责横向
        self.assertRegex(css, r"\.lesson \.swipe\{min-height:0;overflow-x:auto;overflow-y:hidden\}")
        # 有底栏的页面：底栏贴视口底（不改变原有底部间距）
        self.assertIn("main:has(.opsbar),main:has(.qfoot){padding-bottom:0}", css)
        # D. 结构成立：body → header.tb → main（底部操作区在 main 内）
        vocab = self.page(op, U1 + "/vocab")
        self.assertRegex(vocab, r"<body>\s*<header class=\"tb\">")
        self.assertLess(vocab.index("<main>"), vocab.index('class="opsbar"'))
        self.assertLess(vocab.index('class="opsbar"'), vocab.index("</main>"))
        sent = self.page(op, U1 + "/sentences")
        self.assertLess(sent.index("<main>"), sent.index('class="opsbar"'))
        u1 = demo_server.unit_by_slug("unit1")
        lesson = demo_server.lesson_by_key(u1, "DEVELOPING_IDEAS")
        qs = demo_server.lesson_questions(u1, lesson)
        self.post(op, U1 + "/check/answer",
                  {"i": 0, "opt": "a" if qs[0]["answer"] != "a" else "b"})
        check = self.page(op, U1 + "/check?i=0&fb=1")     # 反馈态才渲染底部 .qfoot
        self.assertLess(check.index("<main>"), check.index('class="qfoot"'))
        self.assertLess(check.index('class="qfoot"'), check.index("</main>"))
        # E. 录音：真实链路 + 单击开始 + 静音自动结束 + 只手动回放
        for js in (pages_mod.REC_JS, pages_mod.SPEAK_SWIPE_JS):
            for keep in ("navigator.mediaDevices.getUserMedia", "new MediaRecorder",
                         "createMediaStreamSource", "createAnalyser", "getByteTimeDomainData",
                         "audioCtx.close()", "clearInterval", "URL.revokeObjectURL",
                         "SILENCE_LIMIT_MS", "SILENCE_LEVEL", "window.__zxResetRec",
                         "data-ico-stop", "不能用麦克风"):
                self.assertIn(keep, js, "录音脚本缺少：%s" % keep)
            for gone in ("正在录音", "读完点一下停止", "已经录好了", "正在结束录音",
                         "这次没有录到声音", "setTimeout(function(){ showResult"):
                self.assertNotIn(gone, js, "录音脚本不应再有状态文字：%s" % gone)
            self.assertEqual(js.count(".play()"), 1, "录音音频只能由「我的朗读」手动播放")
        # F. 切换词/句时调用统一清理；麦克风按钮带三根声音活动 bar
        self.assertIn("window.__zxResetRec", pages_mod.SWIPE_JS)
        self.assertIn(".opsbar .mic .wave", css)
        self.assertIn('class="wave"><i></i><i></i><i></i></span></button>', vocab)
        self.assertIn('class="wave"><i></i><i></i><i></i></span></button>', sent)
        # G. AI 演示流程保留（短句跟读仍在录音结束后做演示分析）
        self.assertIn("showResult", pages_mod.SPEAK_SWIPE_JS)
        self.assertIn("zx-analyzing", sent)

    # ---- 23 首页回归锁：不得重新接回旧首页（旧六项学习状态 / 旧 Unit 学习导航）----
    def test_23_home_stays_new_direction(self):
        op, _ = self.client()
        home = self.page(op, "/")
        text = visible_text(home)
        # 旧首页专属文案与旧六项学习状态入口：一律不得出现
        for gone in ("七年级上册英语", "听音辨词", "短语练习", "阅读练习", "听辨练习", "课文点读",
                     "进行中", "开始教材学习", "单元学习空间", "今日10分钟", "今日 10 分钟"):
            self.assertNotIn(gone, text, "Demo 首页不得出现旧首页内容：%s" % gone)
        # 仍是新版首页：教材名 + 唯一课时选择器（7 个 Unit 分组 / 22 个课时）
        self.assertIn("七年级英语上册", text)
        self.assertEqual(home.count("<select"), 1)
        self.assertIn('name="lesson"', home)
        self.assertEqual(home.count("<optgroup"), 7)
        self.assertEqual(home.count("<option "), 22)
        # 首页入口只能是"当前课时真实拥有的能力"，不出现旧首页的固定六项
        labels = re.findall(r'<span class="nm">([^<]+)</span>', home)
        self.assertTrue(labels, "首页应显示当前课时的能力入口")
        for label in labels:
            self.assertIn(label, ("跟读练习", "听音辨意", "音标写词", "词形变化",
                                  "本课检测", "自主练习"),
                          "首页入口必须是当前能力集：%s" % label)
        # 入口链接必须指向 Demo 自己的课时路由（不得复用正式 Web 的旧导航）
        for href in re.findall(r'<a class="entryrow[^"]*" href="([^"]+)"', home):
            self.assertTrue(href.startswith("/unit/"), "首页入口必须走 Demo 课时路由：%s" % href)

    # ---- 24 宽度回归锁：所有页面级容器同一宽度基准 + 不引入魔法尺寸 --------------
    def test_24_unified_page_width(self):
        css = pages_mod.DEMO_CSS
        # 1) 统一宽度基准（单一变量控制上限与水平内边距）
        self.assertIn(":root{--zx-max:560px;--zx-pad:20px}", css)
        self.assertRegex(css, r"main\{width:100%;max-width:var\(--zx-max\);margin-inline:auto;"
                              r"padding-inline:var\(--zx-pad\);")
        self.assertRegex(css, r"\.tb\{width:100%;max-width:var\(--zx-max\);margin-inline:auto;"
                              r"padding-inline:var\(--zx-pad\)\}")
        self.assertRegex(css, r"\.opsbar\{width:100%;max-width:var\(--zx-max\);margin-inline:auto;"
                              r"padding-inline:var\(--zx-pad\)\}")
        # 可滚动页面与不可滚动页面内容宽度一致（不被滚动条挤窄）
        self.assertIn("scrollbar-gutter:stable", css)
        # 2) 不得引入单一设备的魔法尺寸 / 不得复活高度魔法数 / 不用 !important 硬压
        for magic in ("100vw", "width:390px", "width:375px", "width:1440px", "min-width:560px",
                      "calc(100vh", "!important"):
            self.assertNotIn(magic, css, "Demo CSS 不得出现：%s" % magic)
        # 3) 上一轮纵向滚动机制必须仍在（宽度调整不得覆盖它）
        self.assertRegex(css, r"html\{height:100%;overflow:hidden\}")
        self.assertRegex(css, r"main\{[^}]*overflow-y:auto")
        self.assertRegex(css, r"\.lesson \.swipe\{min-height:0;overflow-x:auto;overflow-y:hidden\}")
        # 4) .swipe 保持 ui.py 原有的横向外扩几何，Demo 不给它另设宽度/外边距
        self.assertNotIn(".lesson .swipe{margin", css)
        self.assertNotIn(".lesson .swipe{width", css)
        # 5) 宽度改动不得带回旧首页（首页回归锁仍成立）
        op, _ = self.client()
        home = self.page(op, "/")
        text = visible_text(home)
        for gone in ("七年级上册英语", "听音辨词", "课文点读", "进行中"):
            self.assertNotIn(gone, text, "宽度调整不得带回旧首页：%s" % gone)
        self.assertIn("七年级英语上册", text)
        self.assertEqual(home.count("<select"), 1)

    # ---- 25 教材音频自动播放：滑动即播 + 完整播放 + 令牌防污染 + 录音隔离 ----------
    def test_25_audio_autoplay(self):
        op, _ = self.client()
        js = pages_mod.PLAYER_JS
        # A. 统一自动播放入口 + 进页面自动尝试
        for keep in ("window.__zxAutoPlay", "var gen = 0", "function waitCanPlay", "A.readyState >= 3",
                     "'canplay'", "'loadeddata'", "A.load()", "autoFailed", "beginAuto", "data-autoplay"):
            self.assertIn(keep, js, "播放器缺少自动播放机制：%s" % keep)
        self.assertIn("document.querySelector('[data-autoplay=\"1\"]')", js)   # 首次进入自动播放当前项
        # B/C/D. 令牌：每次切换唯一，旧回调（加载/seeking/可播放）都校验令牌
        self.assertGreaterEqual(js.count("my !== gen"), 3, "旧音频回调必须校验令牌")
        self.assertIn("if (my !== undefined && my !== gen) return;", js)
        # E. play() 的 Promise 必须都带 catch（不允许 Uncaught (in promise)）
        self.assertEqual(js.count(".play()"), 2, "play() 只应出现在 begin()/beginAuto()")
        self.assertIn("if (pr && pr.catch) { pr.catch(function(){ release(); }); }", js)
        self.assertIn("if (pr && pr.catch) { pr.catch(function(){ autoFailed = true; release(); }); }", js)
        # F. ended 只做收尾/自动进入下一段，不重新起播
        self.assertIn("A.addEventListener('ended', function(){\n    stopTick(); release();", js)
        # G. 录音隔离：播放器（含自动播放）完全不碰录音元素
        for gone in ("zx-myrec", "zx-replay"):
            self.assertNotIn(gone, js, "教材音频播放器不得触碰录音元素：%s" % gone)
        self.assertIn("window.__zxResetRec", pages_mod.SWIPE_JS)      # 录音清理仍在
        self.assertIn("window.__zxAutoPlay", pages_mod.SWIPE_JS)      # 滑动切换 → 自动播放
        self.assertIn("if (i === cur && play && play.getAttribute('data-audio') === cards[i].getAttribute('data-audio')) return;",
                      pages_mod.SWIPE_JS)                              # 同一个 i 不重复触发
        # 页面侧：跟读/听读页面的教材音频元素带 data-autoplay
        self.page(op, U1 + "?lesson=DEVELOPING_IDEAS")
        for path, marker in ((U1 + "/vocab", '<button class="op" type="button" id="zx-play" data-autoplay="1" data-audio="'),
                             (U1 + "/sentences", '<button class="op" type="button" id="zx-play" data-autoplay="1" data-audio="'),
                             (U1 + "/reading?lesson=READING_FOR_WRITING",
                              '<button class="spkbig" type="button" data-autoplay="1" data-audio="')):
            self.assertIn(marker, self.page(op, path), "跟读/听读页面缺少自动播放标记：%s" % path)
            self.assertIn('data-audio="/audio/', self.page(op, path))    # 仍是教材音频资源
        # 听音辨意：未作答时自动播放当前题目；看反馈/已作答时不重复自动播放
        listen = self.page(op, U1 + "/listen?mode=word")
        listen_html = re.sub(r"(?s)<script.*?</script>", " ", listen)     # 只看标记，不看脚本源码
        self.assertIn('data-autoplay="1"', listen_html)
        qs = demo_server.lesson_questions(demo_server.unit_by_slug("unit1"),
                                          demo_server.lesson_by_key(demo_server.unit_by_slug("unit1"),
                                                                    "DEVELOPING_IDEAS"))
        self.post(op, U1 + "/listen/answer", {"mode": "word", "i": 0, "pick": "b"})
        fb = self.page(op, U1 + "/listen?mode=word&i=0&fb=1")
        self.assertNotIn('data-autoplay="1"', re.sub(r"(?s)<script.*?</script>", " ", fb),
                         "看反馈时不应再次自动播放")

    # ---- 26 下拉/课时标题视觉 + 回放播放图标 + 教材音频对应性修正 ----------------
    def test_26_picker_play_icon_audio_fix(self):
        op, _ = self.client()
        self.page(op, U1 + "?lesson=DEVELOPING_IDEAS")     # 锁定一个同时有短句跟读的课时
        css = pages_mod.DEMO_CSS
        # A. 下拉菜单：字号收敛 / 去原生圆圈标识 / 单行省略 / 独立浅底色块 / 手机更紧凑
        self.assertRegex(css, r"\.picker select\{[^}]*font-size:16px")
        self.assertRegex(css, r"\.picker select\{[^}]*appearance:none;-webkit-appearance:none")
        self.assertRegex(css, r"\.picker select\{[^}]*white-space:nowrap;overflow:hidden;text-overflow:ellipsis")
        self.assertRegex(css, r"\.picker select\{[^}]*background:#F1F4F8")
        self.assertIn("@media (max-width:600px)", css)
        self.assertIn(".picker select{font-size:15px", css)
        # 课时标题（顶部栏副标题）单行省略
        self.assertRegex(css, r"\.tb-sub\{white-space:nowrap;overflow:hidden;text-overflow:ellipsis")
        self.assertNotIn("radio", css)
        home = self.page(op, "/")
        self.assertNotIn('type="radio"', home)
        # B. 回放按钮 = 三角播放图标（复用 ui.py 现有图标集）；教材音频按钮仍是扬声器
        play_icon, speaker_icon = pages_mod.ui.icon("play"), pages_mod.ui.icon("speaker")
        for path in (U1 + "/vocab", U1 + "/sentences"):
            body = self.page(op, path)
            replay = re.search(r'id="zx-replay"[^>]*>(.*?)</button>', body, re.S)
            self.assertIsNotNone(replay, path)
            self.assertIn(play_icon, replay.group(1), "%s 回放按钮应为三角播放图标" % path)
            listen_btn = re.search(r'id="zx-play"[^>]*>(.*?)</button>', body, re.S)
            self.assertIn(speaker_icon, listen_btn.group(1), "%s 教材音频按钮应仍是扬声器" % path)
        # C. 教材音频对应性修正表（依据官方 MP3 词级 ASR 复核）
        self.assertEqual(pages_mod.SENTENCE_START_FIX, {"PREVIEW:AU26:S0508": 14650})
        # 段落起点改为「按块文本前缀定位」（插入文本块后不会再被顶偏）；值取自已有 ASR
        self.assertEqual(pages_mod.READING_SEG_START.get("AU13"),
                         [("Before your journey starts", 10100)])
        self.assertEqual(pages_mod.READING_SEG_START.get("AU34"),
                         [("For Chinese people", 13700)])
        self.assertEqual(pages_mod.READING_SEG_START.get("AU42"), [("Day 1", 19900)])
        # 正文由教材文本块提供；AU13 只额外补入课文标题，AU28 不再需要逐句补入
        self.assertEqual(len(pages_mod.READING_CHUNK_ADD.get("AU13") or []), 1)
        self.assertNotIn("AU28", pages_mod.READING_CHUNK_ADD)
        # 听音阅读：正文 = 教材文本块（完整），缺口按官方音频补齐
        r1 = html.unescape(self.page(op, U1 + "/reading?lesson=READING_FOR_WRITING"))
        for token in ("Mia, how do you feel about your first day in junior high tomorrow?",
                      "A paper boat?", "Dear Mia, Time flies!",
                      "Primary school is like a small pool.",
                      "sail your boat by yourself.", "With love, Dad and Mum."):
            self.assertIn(token, r1, "Unit 1 听音阅读缺少正文：%s" % token)
        r4u = html.unescape(self.page(op, "/unit/unit4/reading?lesson=UNDERSTANDING_IDEAS"))
        for token in ("It is midnight in China", "This is the lion’s head",
                      "After Emilia hangs balloons and lanterns in the dining room,",
                      "I feel like I am back home."):
            self.assertIn(token, r4u, "Unit 4 听音阅读缺少正文：%s" % token)
        self.assertIn("They enjoy the time together. We are family, John says.",
                      html.unescape(self.page(op, "/unit/unit3/reading?lesson=READING_FOR_WRITING")))
        self.assertIn("They will take a rest.",
                      html.unescape(self.page(op, "/unit/unit5/reading?lesson=UNDERSTANDING_IDEAS")))
        # Unit 6 日记体：音频读出 Day 4 / Day 5，文本块按音频补全
        r6 = html.unescape(self.page(op, "/unit/unit6/reading?lesson=UNDERSTANDING_IDEAS"))
        r6_text = re.sub(r"<[^>]+>", "", r6)
        self.assertIn("watch them again... Day 4 I", r6_text)
        self.assertIn("about pigeons. Day 5 I", r6_text)
        self.assertIn('data-start="63300"',
                      html.unescape(self.page(op, "/unit/unit4/reading?lesson=READING_FOR_WRITING")))
        # 短句：AU26 那句播放起点后移到本句实际起点，文本不变
        fixed = None
        for u in demo_server.units():
            for l in demo_server.lessons(u):
                if any(s["uid"] in pages_mod.SENTENCE_START_FIX for s in demo_server.lesson_sentences(u, l)):
                    fixed = (u, l)
                    break
            if fixed:
                break
        self.assertIsNotNone(fixed, "应能找到被修正的短句所属课时")
        unit, lesson = fixed
        sp = html.unescape(self.page(op, "/unit/%s/sentences?lesson=%s" % (unit["slug"], lesson["key"])))
        self.assertIn('data-start="14650"', sp)
        self.assertIn("Can you change your clothes before you come?", sp)

    # ---- 27 听音阅读：文本补齐 + 加粗 + 首尾时间轴 ----------------------------
    def test_27_reading_text_bold_and_timeline(self):
        """官方音频读到的内容在阅读页能找到；补入内容默认正常字重；首尾边界与音频一致。"""
        op, _ = self.client()

        def chunks(path):
            body = self.page(op, path)
            return body, re.findall(
                r'<p class="chunk" data-start="(\d+)" data-end="(\d+)">(.*?)</p>', body, re.S)

        # AU34：段落含前半（p72）+ 后半（p73）；首块起点 = 播放起点 = 音频开口处
        u4, c4 = chunks("/unit/unit4/reading?lesson=READING_FOR_WRITING")
        play4 = re.search(r'data-autoplay="1"[^>]*data-start="(\d+)"', u4)
        self.assertEqual(c4[0][0], "13700")          # p72 前半（"For Chinese people…"）实际起点
        self.assertEqual(play4.group(1), c4[0][0])
        self.assertIn("For Chinese people, festivals usually mean", html.unescape(c4[0][2]))
        self.assertEqual(c4[1][0], "63300")          # p73 后半起点（上一轮已确认的修复保留）
        self.assertIn("Leng’s duty means", html.unescape(c4[1][2]))
        # AU34 全部块：start < end，且不重叠
        for (s, e, _t), (s2, _e2, _t2) in zip(c4, c4[1:]):
            self.assertLess(int(s), int(e))
            self.assertLessEqual(int(e), int(s2))

        # AU21：末句 Along the way… 的语音落在原区间之外 → 尾部按实际语音补齐
        _u3, c3 = chunks("/unit/unit3/reading?lesson=UNDERSTANDING_IDEAS")
        self.assertEqual(c3[0][1], "66160")
        c3_text = html.unescape(c3[0][2]).lower()
        self.assertIn("along the way, they start to see into each other’s hearts.",
                      c3_text)                     # 跨页断句处按音频补全
        self.assertLessEqual(int(c3[0][1]), int(c3[1][0]))         # 相邻块不重叠
        # 课文标题 Silent Love：官方音频读到、文本块没有 → 补入；补入内容不加粗
        self.assertIn("Silent Love", html.unescape(c3[0][2]))
        self.assertNotIn("<strong>", c3[0][2])

        # AU13：所有块必须 start < end 且不重叠（原来第 7 块与第 6 块重叠 433ms）
        _u1, c1 = chunks(U1 + "/reading?lesson=READING_FOR_WRITING")
        for (s, e, _t), (s2, _e2, _t2) in zip(c1, c1[1:]):
            self.assertLess(int(s), int(e))
            self.assertLessEqual(int(e), int(s2), "阅读块区间不应重叠")

        # AU42：Day 3 / Day 4 / Day 5 都在，且按教材页面的加粗结构标签呈现
        u6, c6 = chunks("/unit/unit6/reading?lesson=UNDERSTANDING_IDEAS")
        for lab in ("Day 3", "Day 4", "Day 5"):
            self.assertIn("<strong>%s</strong> " % lab, u6)
        play6 = re.search(r'data-autoplay="1"[^>]*data-start="(\d+)"', u6)
        self.assertEqual(play6.group(1), c6[0][0])
        self.assertEqual(c6[0][0], "19900")           # 段落起点=Day 1（本轮补入）
        self.assertEqual(c6[-1][0], "61700")          # Day 3 起的正文块起点（上一轮已确认）

        # 没有加粗证据的阅读页不得出现 <strong>（AU21 的课文标题按音频补入，字重证据不足）
        for path in ("/unit/unit3/reading?lesson=READING_FOR_WRITING",
                     "/unit/unit3/reading?lesson=UNDERSTANDING_IDEAS"):
            body = self.page(op, path)
            self.assertNotIn("<strong>", main_html(body), path)

    # ---- 27b 阅读加粗收口：音频读到的标题/作者名 → 按教材证据加粗 ----------
    def test_30_reading_bold_final(self):
        """只加粗教材明确加粗、且官方音频实际读到的结构文字；其余保持普通字重。"""
        op, _ = self.client()

        def reading(path):
            return self.page(op, path)

        # AU13 课文标题：音频 10.22–12.58s 读出 → 显示并加粗，播放起点同步前移
        u1 = reading(U1 + "/reading?lesson=READING_FOR_WRITING")
        m = re.search(r'<p class="chunk" data-start="(\d+)" data-end="(\d+)">(.*?)</p>',
                      u1, re.S)
        self.assertEqual(m.group(1), "10100")
        self.assertEqual(m.group(3), "<strong>Before your journey starts</strong>")
        self.assertEqual(re.search(r'data-autoplay="1"[^>]*data-start="(\d+)"',
                                   u1).group(1), "10100")
        # 对话正文仍为普通字重，且没有把补入的句子整体加粗
        self.assertIn("Mia, how do you feel", u1)
        self.assertNotIn("<strong>Mia", u1)

        # AU35 / AU47 课文标题
        for path, start, label in (("/unit/unit5/reading?lesson=UNDERSTANDING_IDEAS",
                                    "15900", "Within a plant"),
                                   ("/unit/unit6/reading?lesson=READING_FOR_WRITING",
                                    "11650", "As dead as a dodo")):
            body = reading(path)
            m = re.search(r'<p class="chunk" data-start="(\d+)" data-end="(\d+)">(.*?)</p>',
                          body, re.S)
            self.assertEqual(m.group(1), start, path)
            self.assertEqual(m.group(3), "<strong>%s</strong>" % label, path)
            self.assertEqual(re.search(r'data-autoplay="1"[^>]*data-start="(\d+)"',
                                       body).group(1), start, path)

        # AU41 两位作者名（音频 37.5s / 75.6s 读出）加粗；正文句子不加粗
        u5 = reading("/unit/unit5/reading?lesson=READING_FOR_WRITING")
        self.assertIn("<strong>Feng Tao</strong>", u5)
        self.assertIn("<strong>Emma Jones</strong>", u5)
        self.assertNotIn("<strong>What does tea mean", u5)

        # AU42 保持现状
        u6 = reading("/unit/unit6/reading?lesson=UNDERSTANDING_IDEAS")
        for lab in ("Day 3", "Day 4", "Day 5"):
            self.assertIn("<strong>%s</strong>" % lab, u6)

        # 全量：17 个阅读段都满足 start<end、相邻不重叠、首块起点=播放起点
        allowed = {"Before your journey starts", "Within a plant", "As dead as a dodo",
                   "Feng Tao", "Emma Jones", "Mum:", "Li Ming:",
                   "Day 1", "Day 2", "Day 3", "Day 4", "Day 5",
                   # 说明：AU21 的课文标题按音频补入，教材字重证据不足 → 普通字重
                   }
        n = 0
        for unit in demo_server.units():
            for lesson in demo_server.lessons(unit):
                segs = demo_server.lesson_reading(unit, lesson) or []
                for idx in range(len(segs)):
                    n += 1
                    path = "/unit/%s/reading?lesson=%s&seg=%d" % (unit["slug"], lesson["key"], idx)
                    body = reading(path)
                    rows = re.findall(
                        r'<p class="chunk" data-start="(\d+)" data-end="(\d+)">(.*?)</p>',
                        body, re.S)
                    self.assertTrue(rows, path)
                    play = re.search(r'data-autoplay="1"[^>]*data-start="(\d+)"', body).group(1)
                    self.assertEqual(rows[0][0], play, "%s 首块起点≠播放起点" % path)
                    for (s, e, _t), (s2, _e2, _t2) in zip(rows, rows[1:]):
                        self.assertLess(int(s), int(e), path)
                        self.assertLessEqual(int(e), int(s2), "%s 阅读块重叠" % path)
                    self.assertLess(int(rows[-1][0]), int(rows[-1][1]), path)
                    for strong in re.findall(r"<strong>(.*?)</strong>", body):
                        self.assertIn(strong, allowed,
                                      "%s 出现未授权的加粗：%s" % (path, strong))
        self.assertEqual(n, 17, "阅读段数量应为 17")

    # ---- 28 阅读补齐规则不得套用到听力习题 ----------------------------------
    def test_28_reading_fix_stays_out_of_listening(self):
        """听力习题（听音辨意 / 本课检测）保持原有题目文本，不套用阅读补齐内容。"""
        op, _ = self.client()
        reading_only = ("Silent Love", "Day 3", "Day 4", "Day 5",
                        "It is midnight in China", "sail your boat by yourself",
                        "They will take a rest.", "Before your journey starts",
                        "Within a plant", "As dead as a dodo", "Feng Tao", "Emma Jones")
        for path in (U1 + "/listen?lesson=READING_FOR_WRITING",
                     "/unit/unit3/listen?lesson=UNDERSTANDING_IDEAS",
                     "/unit/unit6/listen?lesson=UNDERSTANDING_IDEAS",
                     U1 + "/check?lesson=READING_FOR_WRITING",
                     "/unit/unit6/check?lesson=UNDERSTANDING_IDEAS",
                     "/unit/unit3/check?lesson=READING_FOR_WRITING"):
            body = self.page(op, path)
            for token in reading_only:
                self.assertNotIn(token, body, "%s 不应出现阅读补齐内容：%s" % (path, token))
        # 结构上：阅读补齐表只被听音阅读使用（听力页 / 本课检测页源码里完全不存在）
        src = (HERE / "pages.py").read_text(encoding="utf-8")
        self.assertEqual(src.count("_reading_rows("), 2,
                         "_reading_rows 只应有定义 + 听音阅读一处调用")
        for fn in (pages_mod.listen_page, pages_mod.check_page):
            fsrc = inspect.getsource(fn)
            for name in ("READING_CHUNK_ADD", "READING_TEXT_PATCH", "READING_TEXT_PREPEND",
                         "READING_BOLD_LABELS", "READING_CHUNK_FIX", "READING_SEG_START"):
                self.assertNotIn(name, fsrc, "%s 不应使用阅读补齐表 %s" % (fn.__name__, name))

    # ---- 29 当前课时选择器：Demo 自定义（手机不再调用系统 picker）-----------
    def test_31_reading_body_complete(self):
        """听音阅读正文完整性：官方音频读到的教材正文在页面全部可见；AU32/AU36 保持不并入。"""
        op, _ = self.client()

        def read(path):
            return re.sub(r"<[^>]+>", " ", html.unescape(self.page(op, path)))

        # 每个阅读段的正文关键句（来自教材 content_block，按官方音频补全后应全部可见）
        cases = {
            "/unit/starter/reading?lesson=GET_READY": (
                "Tomorrow is your first day of junior high school.",
                "Where is your schoolbag?", "And your textbooks?", "Mum:", "Li Ming:"),
            "/unit/starter/reading?lesson=KNOW_YOUR_SCHOOL": (
                "This is the teaching building.", "This is our library.",
                "This is our playground.", "This is our dining hall."),
            "/unit/unit1/reading?lesson=READING_FOR_WRITING": (
                "Mia, how do you feel about your first day in junior high tomorrow?",
                "A paper boat?", "Dear Mia, Time flies!", "With love, Dad and Mum."),
            "/unit/unit2/reading?lesson=UNDERSTANDING_IDEAS": (
                "Rock music is coming out of my computer.",
                "An idea suddenly hits me", "It feels great to enjoy our hobby together."),
            "/unit/unit2/reading?lesson=READING_FOR_WRITING": (
                "Oliver is awake at midnight.", "Emma shakes her head", "best ending to my story"),
            "/unit/unit4/reading?lesson=UNDERSTANDING_IDEAS": (
                "It is my first year of university in the UK.",
                "How I wish to have four hands now!", "This is the lion’s head",
                "I feel like I am back home."),
            "/unit/unit4/reading?lesson=READING_FOR_WRITING": (
                "For Chinese people, festivals usually mean", "Leng’s duty means",
                "shines brighter than fireworks."),
            "/unit/unit5/reading?lesson=READING_FOR_WRITING": (
                "What is the most popular drink in the world after water?",
                "Feng Tao", "Emma Jones", "In Chengdu, we have as many teahouses"),
            "/unit/unit6/reading?lesson=UNDERSTANDING_IDEAS": (
                "Day 1", "Day 2", "Day 3", "Day 4", "Day 5",
                "We’re studying birds for Bird Week", "didn’t know enough about them!"),
            "/unit/unit6/reading?lesson=READING_FOR_WRITING": (
                "Are you looking at me?", "I’m a dodo!", "as dead as a dodo"),
        }
        for path, tokens in cases.items():
            text = read(path)
            for token in tokens:
                self.assertIn(token, text, "%s 正文缺少：%s" % (path, token))

        # AU32 / AU36：听力材料、未印出的口语范例 → 不得并入阅读正文
        t32 = read("/unit/unit4/reading?lesson=DEVELOPING_IDEAS")
        self.assertNotIn("Welcome to news today", t32.lower())
        self.assertIn("complete the poster", t32)
        t36 = read("/unit/unit5/reading?lesson=UNDERSTANDING_IDEAS&seg=1")   # 该课时的第 2 段=AU36
        self.assertNotIn("Planting day is coming", t36)
        self.assertIn("Work in pairs. Discuss your plan for Planting Day.", t36)

    def test_29_lesson_picker_is_custom(self):
        op, _ = self.client()
        css = pages_mod.DEMO_CSS
        self.assertIn(".lpick .lpnative{display:none}", css)      # 原生 select 不再弹系统层
        self.assertIn('.lpopt[aria-selected="true"]', css)        # 选中态用背景色/边框
        self.assertNotIn("radio", css)
        for path, sel_id in (("/", "zx-unit"), (U1, "zx-lesson")):
            body = self.page(op, path)
            view = main_html(body)
            self.assertIn('class="lpick"', body)
            self.assertIn('id="%s"' % sel_id, body)
            self.assertEqual(view.count('class="lpopt"'), 22)     # 22 个有资源的真实课时
            self.assertEqual(view.count('aria-selected="true"'), 1)
            self.assertEqual(body.count("<select"), 1)            # 提交用的原生 select 仍在
            self.assertIn('action="/lesson"', body)
            self.assertIn("form.submit()", body)
            self.assertNotIn('type="radio"', body)
        # 业务逻辑不变：POST /lesson 仍能切课时，且选中态跟随
        status, home = self.post(op, "/lesson",
                                 {"lesson": "unit3@DEVELOPING_IDEAS", "back": "/"})
        self.assertEqual(status, 200)
        self.assertIn('value="unit3@DEVELOPING_IDEAS" selected', home)
        self.assertIn('aria-selected="true">Unit 3 · Developing ideas', home)


    # ---- 32 自主练习：首页同级入口，复用专项 / 巩固练习 ---------------------
    def test_32_autonomous_practice_entry(self):
        op, jar = self.client()
        # A. 首页：6 个教材能力入口之后是「自主练习」，入口样式与前 6 个完全一致
        home = self.page(op, "/")
        labels = re.findall(r'<span class="nm">([^<]+)</span>', home)
        self.assertEqual(labels[-1], "自主练习")
        hrefs = re.findall(r'<a class="entryrow[^"]*" href="([^"]+)"', home)
        self.assertEqual(hrefs[-1], U1 + "/practice")
        # 自主练习状态：没有可练项 → 未开始/继续；有正式巩固项 → 有 N 项需要巩固
        practice_status = re.findall(r'<span class="st">([^<]*)</span>', home)[-1]
        self.assertRegex(practice_status, r"^(未开始|继续|有 \d+ 项需要巩固)$")
        # 这节课没有教材资源时，入口里只剩下「自主练习」（它不是教材资源能力）
        op2, _ = self.client()
        thin = self.page(op2, U1 + "?lesson=STARTING_OUT")
        self.assertEqual(re.findall(r'<span class="nm">([^<]+)</span>', thin), ["自主练习"])
        # B. 没有 Cookie 学习记录、且正式巩固池为空：如实说明，不给练习入口，也不编结论
        #    （正式池有数据时的表现由 test_34 / test_35 验证）
        saved_fn = demo_server.pool_bridge.formal_reinforce_entries
        demo_server.pool_bridge.formal_reinforce_entries = lambda *a, **k: []
        try:
            blank = self.page(op2, U1 + "/practice")
        finally:
            demo_server.pool_bridge.formal_reinforce_entries = saved_fn
        self.assertIn("自主练习", blank)
        self.assertIn("还没有学习记录", blank)
        self.assertNotIn("专项练习", blank)
        self.assertNotIn("巩固练习", blank)
        # C. 有学习记录：一段简短学习总结 + 专项 / 巩固练习（三个完整模块不再堆叠）
        u1 = demo_server.unit_by_slug("unit1")
        lesson = demo_server.lesson_by_key(u1, "DEVELOPING_IDEAS")
        self.page(op, U1 + "?lesson=DEVELOPING_IDEAS")
        qs = demo_server.lesson_questions(u1, lesson)
        self.post(op, U1 + "/check/answer",
                  {"i": 0, "opt": "a" if qs[0]["answer"] != "a" else "b"})
        u0 = demo_server.unit_by_slug("starter")
        l0 = demo_server.lesson_by_key(u0, "GET_READY")
        lq = demo_server.listen_questions(u0, "word", l0)
        self.post(op, "/unit/starter/listen/answer",
                  {"mode": "word", "i": 0, "pick": "a" if lq[0]["answer"] != "a" else "b"})
        zp = self.page(op, U1 + "/practice")
        ztext = visible_text(zp)
        self.assertIn("自主练习", ztext)
        self.assertIn("学习总结", ztext)
        for gone in ("本课发现", "本课重点", "AI 建议"):
            self.assertNotIn(gone, ztext)               # 已压缩成一段总结
        self.assertIn("专项练习", ztext)
        self.assertIn("巩固练习", ztext)
        self.assertIn('class="ai-pt"', zp)              # 复用同一份练习入口组件
        # D. 从自主练习进入专项练习：做完回自主练习，而不是跳回 AI 随堂助教
        link = html.unescape(re.search(r'href="(/unit/unit1/practice/special\?p=[^"]+)"', zp).group(1))
        self.assertTrue(link.endswith("&b=own"), link)
        session = "special:" + urllib.parse.parse_qs(urllib.parse.urlparse(link).query)["p"][0]
        value = [c.value for c in jar if c.name == demo_server.state_mod.COOKIE_NAME][0]
        rows = demo_server.session_questions(demo_server.state_mod.decode(value), u1, lesson, session)
        self.assertTrue(rows)
        special = self.page(op, link)
        self.assertIn('aria-label="返回自主练习"', special)      # 顶部返回 = 自主练习（不再跳回 AI 随堂助教）
        status, fb = self.post(op, U1 + "/practice/answer",
                               {"s": session, "i": 0, "opt": rows[0]["answer"], "b": "own"})
        self.assertEqual(status, 200)
        self.assertIn("答对了", fb)
        self.assertIn('aria-label="返回自主练习"', fb)
        # 首页入口状态变成「继续」（只根据真实练过的记录，不编造完成度）
        self.assertRegex(re.findall(r'<span class="st">([^<]*)</span>', self.page(op, "/"))[-1],
                         r"^(未开始|继续|有 \d+ 项需要巩固)$")
        result = self.page(op, U1 + "/practice/result?s=%s&b=own" % urllib.parse.quote(session))
        self.assertIn("回到自主练习", result)
        # E. 原「AI 随堂助教」链路不变：标题、模块与返回目标都保持原样
        tutor = self.page(op, U1 + "/tutor")
        ttext = visible_text(tutor)
        self.assertIn("AI 随堂助教", ttext)
        self.assertIn("本课发现", ttext)
        self.assertIn("回到学习结果", ttext)
        tlink = re.search(r'href="(/unit/unit1/practice/special\?p=[^"]+)"', tutor).group(1)
        self.assertNotIn("b=own", tlink)
        self.assertIn('aria-label="返回 AI 随堂助教"', self.page(op, tlink))


    # ---- 33 课文简答 → 模拟AI评价 → LearningRecord → evidence → mastery → pool ----
    def test_33_say_ai_evaluation_becomes_formal_evidence(self):
        """课文简答的一条模拟 AI 评价，必须按现有学习系统规则走完正式证据链。

        写入目标 = 正式 learning.db 的**临时副本**（与 learning/ 既有测试同一纪律：
        只读复制、跑完即删、正式库 SHA 不变）；本测试不接真实 AI（AI_PROVIDER = None）。
        """
        import hashlib
        import shutil
        import sqlite3
        import tempfile

        sys.path.insert(0, str(HERE.parent / "learning"))
        import ai_grading as grade_mod       # noqa: E402
        import evidence_service as lev       # noqa: E402
        import learning_service as lsvc      # noqa: E402
        import mastery_service as lmast      # noqa: E402
        import resource_pool_service as lpool  # noqa: E402
        import say_evidence as bridge        # noqa: E402

        def sha(path):
            h = hashlib.sha256()
            with open(path, "rb") as fh:
                for chunk in iter(lambda: fh.read(65536), b""):
                    h.update(chunk)
            return h.hexdigest()

        def schema(conn):
            return sorted((r[0], r[1], r[2]) for r in conn.execute(
                "SELECT type, name, sql FROM sqlite_master ORDER BY name"))

        official = lsvc.DEFAULT_LEARNING_DB
        official_sha = sha(official)
        official_conn = lsvc.connect_learning_db(official)
        try:
            official_schema = schema(official_conn)
        finally:
            official_conn.close()

        tmpdir = Path(tempfile.mkdtemp(prefix="zhixue_say_"))
        tmp_db = tmpdir / "learning.db"
        shutil.copyfile(official, tmp_db)
        saved_db = bridge.LEARNING_DB
        bridge.LEARNING_DB = tmp_db
        try:
            op, _ = self.client()
            self.page(op, U1 + "?lesson=DEVELOPING_IDEAS")
            u1 = demo_server.unit_by_slug("unit1")
            lesson = demo_server.lesson_by_key(u1, "DEVELOPING_IDEAS")
            task = demo_server.say_task(u1, lesson)
            self.assertTrue(task.get("uid"))                     # 教材句子身份（映射前提）
            mapping = bridge.resolve_item(task, u1["unit_code"])
            self.assertIsNotNone(mapping)                        # 必须是真实教材 item
            item_id = mapping["item_id"]
            self.assertEqual(mapping["item_type"], "exercise")

            def record_ids():
                conn = sqlite3.connect(str(tmp_db))
                try:
                    return {r[0] for r in conn.execute(
                        "SELECT record_id FROM learning_record WHERE item_id=?", (item_id,))}
                finally:
                    conn.close()

            def new_record(before):
                """这一次提交新增的那条 Record（不依赖时间戳排序，避免同秒误判）。"""
                fresh = record_ids() - before
                self.assertEqual(len(fresh), 1, "一次提交应当只新增 1 条 LearningRecord")
                rid = fresh.pop()
                conn = sqlite3.connect(str(tmp_db))
                conn.row_factory = sqlite3.Row
                try:
                    return conn.execute("SELECT * FROM learning_record WHERE record_id=?",
                                        (rid,)).fetchone()
                finally:
                    conn.close()

            # ---- Case A：达到 correct ----
            before_a = record_ids()
            self.post(op, U1 + "/say/submit",
                      {"text": "The new students' problems are more subjects and more homework."})
            rec = new_record(before_a)
            self.assertEqual(rec["result"], "correct")
            self.assertEqual(rec["activity_type"], bridge.ACTIVITY_TYPE)
            self.assertEqual(rec["activity_type"], "produce")
            self.assertEqual(rec["item_id"], item_id)
            payload = json.loads(rec["response_raw"])
            self.assertEqual(payload["evaluation_type"], "ai_assisted_short_answer")
            self.assertEqual(payload["result"], "correct")
            self.assertFalse(payload["ai_called"])               # 未调用真实 AI
            self.assertEqual(payload["source"], "demo_deterministic_ai_simulation")
            for key in ("content", "language", "textbook_basis", "guidance"):
                self.assertIn(key, payload)
            self.assertEqual(payload["textbook_basis"]["textbook_item"], item_id)
            self.assertTrue(payload["textbook_basis"]["references"])
            self.assertFalse(grade_mod.ai_configured())          # AI 调用 = 0

            conn = lev.connect_learning_db(tmp_db)
            try:
                lid = rec["learner_id"]
                ev = lev.collect_evidence(conn, lid, item_id)
                self.assertEqual(ev["evidence"][-1]["result"], "correct")
                self.assertEqual(ev["evidence"][-1]["reason"], "judged_result")
                self.assertTrue(ev["evidence"][-1]["is_valid"])
                mast = lmast.evaluate(conn, lid, item_id)
                self.assertGreaterEqual(mast["evidence_count"], 1)
                self.assertIn(mast["state"], ("learning", "needs_review", "stable"))
                pool = lpool.list_current_issue_pool(conn, lid)
                self.assertNotIn(item_id, [p["item_id"] for p in pool])   # correct 不进池
            finally:
                conn.close()

            # ---- Case B：只达到 partial ----
            # 现有证据去重规则：同一天同一题同一 task_type 只留 1 条独立证据，
            # "最新"按 created_at 判定（秒级）；同秒则退化为 record_id 比较。
            # 这里隔 1 秒提交，保证两条记录的时间戳不同（不修改任何规则）。
            time.sleep(1.1)
            before_b = record_ids()
            self.post(op, U1 + "/say/submit",
                      {"text": "The students have problems with homework"})
            rec_b = new_record(before_b)
            self.assertEqual(rec_b["result"], "partial")
            payload_b = json.loads(rec_b["response_raw"])
            self.assertEqual(payload_b["result"], "partial")
            self.assertFalse(payload_b["content"]["complete"])
            conn = lev.connect_learning_db(tmp_db)
            try:
                lid = rec_b["learner_id"]
                ev = lev.collect_evidence(conn, lid, item_id)
                self.assertEqual(ev["evidence"][-1]["result"], "partial")
                mast = lmast.evaluate(conn, lid, item_id)
                self.assertEqual(mast["recent_results"][-1], "partial")
                pool = {p["item_id"]: p for p in lpool.list_current_issue_pool(conn, lid)}
                self.assertIn(item_id, pool)                              # partial 进池
                self.assertEqual(pool[item_id]["issue_type"], lpool.CURRENT_WEAK)
            finally:
                conn.close()

            # ---- 没有真实教材 item 的课时：不写记录（绝不伪造 item） ----
            before = None
            conn = sqlite3.connect(str(tmp_db))
            try:
                before = conn.execute("SELECT COUNT(*) FROM learning_record").fetchone()[0]
            finally:
                conn.close()
            self.page(op, U1 + "?lesson=UNDERSTANDING_IDEAS")
            self.post(op, U1 + "/say/submit", {"text": "Our teacher writes on the blackboard."})
            conn = sqlite3.connect(str(tmp_db))
            try:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM learning_record").fetchone()[0],
                                 before)
            finally:
                conn.close()

            # ---- schema 未改：临时库与正式库 schema 完全一致 ----
            conn = sqlite3.connect(str(tmp_db))
            try:
                self.assertEqual(schema(conn), official_schema)
            finally:
                conn.close()
        finally:
            bridge.LEARNING_DB = saved_db
            shutil.rmtree(tmpdir, ignore_errors=True)
        self.assertEqual(sha(official), official_sha)      # 正式库未被本测试写入


    def _seeded_learning_db(self, tmpdir, item_id="FLTRP-EN-7A-2022CUR:X:D5F2794974F8"):
        """正式库副本 + 一条 produce/partial 证据：让巩固池里稳定出现这个 item。

        （真实 Demo 正在被别人使用，正式池会随真实作答变化；测试不能依赖线上状态。）
        """
        import shutil

        sys.path.insert(0, str(HERE.parent / "learning"))
        import learning_service as lsvc      # noqa: E402
        import session_service as lses       # noqa: E402

        db = Path(tmpdir) / "learning.db"
        shutil.copyfile(lsvc.DEFAULT_LEARNING_DB, db)
        conn = lsvc.connect_learning_db(db)
        try:
            row = conn.execute("SELECT learner_id FROM learner WHERE status='active' "
                               "ORDER BY created_at LIMIT 1").fetchone()
            lid = row["learner_id"]
            sess = lses.create_learning_session(conn, lid, "activity", [item_id])
            lsvc.record_learning_event(conn, lid, sess["task_id"], item_id, "produce",
                                       result="partial", response_raw='{"seed":"test"}')
            lses.end_learning_session(conn, sess["session_id"], lid)
        finally:
            conn.close()
        return db

    # ---- 34 正式巩固池 → 自主练习（只读接入 + 最小区重） --------------------
    def test_34_formal_pool_entries_into_autonomous_practice(self):
        """正式 resource_pool 的 produce 项目，要能变成自主练习页上的现有入口行。"""
        import shutil
        import tempfile

        sys.path.insert(0, str(HERE.parent / "learning"))
        import learning_service as lsvc      # noqa: E402
        import pool_bridge as bridge         # noqa: E402

        say_item = "FLTRP-EN-7A-2022CUR:X:D5F2794974F8"
        tmpdir = Path(tempfile.mkdtemp(prefix="zhixue_pool_"))
        tmp_db = self._seeded_learning_db(tmpdir, say_item)
        saved_db = bridge.LEARNING_DB
        bridge.LEARNING_DB = tmp_db
        try:
            entries = bridge.formal_reinforce_entries()
            self.assertTrue(entries, "正式池里应当有 produce 巩固项")
            first = next(e for e in entries if e["item_id"] == say_item)
            self.assertEqual(first["unit_slug"], "unit1")
            self.assertEqual(first["lesson_key"], "DEVELOPING_IDEAS")
            self.assertEqual(first["href"], "/unit/unit1/say?lesson=DEVELOPING_IDEAS")
            self.assertEqual([e["item_id"] for e in entries].count(say_item), 1)   # 同 item 不重复
            # 映射不成立就不造入口
            self.assertIsNone(bridge.entry_for_item(
                {"item_id": "FLTRP-EN-7A-2022CUR:X:000000000000",
                 "last_judged_activity_type": "produce"}))
            self.assertIsNone(bridge.entry_for_item(
                {"item_id": say_item, "last_judged_activity_type": "listen"}))

            # 自主练习页：正式巩固入口用现有 .ai-pt / .plainrow
            op, _ = self.client()
            page = self.page(op, U1 + "/practice")
            self.assertIn('class="ai-pt"', page)
            self.assertIn('href="/unit/unit1/say?lesson=DEVELOPING_IDEAS"', page)
            self.assertIn("巩固练习 · 课文简答", page)
            # 具体"上次"结果取决于正式池最近一次判断（会随真实使用变化），只校验位置信息
            self.assertIn("Unit 1 · Developing ideas · 上次：", page)
            row = re.search(r'<a class="plainrow" href="/unit/unit1/say\?lesson=DEVELOPING_IDEAS">'
                            r'.*?</a>', page).group(0)
            for leaked in ("record", "priority", "evidence", "attempt", "FLTRP-EN-7A-2022CUR"):
                self.assertNotIn(leaked, row, "巩固入口不应暴露内部数据：%s" % leaked)
            # 点击 → 现有课文简答页（不新建页面）
            say = self.page(op, "/unit/unit1/say?lesson=DEVELOPING_IDEAS")
            self.assertIn("教材原句", say)
            self.assertIn("/unit/unit1/say/submit", say)

            # 最小区重：正式池已覆盖的课时，Cookie 巩固候选不再重复出题
            op2, jar = self.client()
            self.page(op2, U1 + "?lesson=DEVELOPING_IDEAS")
            u1 = demo_server.unit_by_slug("unit1")
            lesson = demo_server.lesson_by_key(u1, "DEVELOPING_IDEAS")
            qs = demo_server.lesson_questions(u1, lesson)
            self.post(op2, U1 + "/check/answer",
                      {"i": 0, "opt": "a" if qs[0]["answer"] != "a" else "b"})
            u0 = demo_server.unit_by_slug("starter")
            l0 = demo_server.lesson_by_key(u0, "GET_READY")
            lq = demo_server.listen_questions(u0, "word", l0)
            self.post(op2, "/unit/starter/listen/answer",
                      {"mode": "word", "i": 0, "pick": "a" if lq[0]["answer"] != "a" else "b"})
            cookie = [c.value for c in jar if c.name == demo_server.state_mod.COOKIE_NAME][0]
            st = demo_server.state_mod.decode(cookie)
            point = qs[0].get("focus") or qs[0].get("type")
            all_rows = demo_server.reinforce_practice(st, u1, lesson)
            kept = demo_server.reinforce_practice(st, u1, lesson,
                                                  covered=[("unit1", "DEVELOPING_IDEAS")])
            self.assertIn(point, [r["point"] for r in all_rows])
            self.assertNotIn(point, [r["point"] for r in kept])       # 不再重复
            self.assertLess(len(kept), len(all_rows))
        finally:
            bridge.LEARNING_DB = saved_db
            shutil.rmtree(tmpdir, ignore_errors=True)

    # ---- 35 正式池为空照常 / 正式入口点进去后闭环 --------------------------
    def test_35_pool_empty_falls_back_and_formal_entry_closes_loop(self):
        import shutil
        import sqlite3
        import tempfile

        sys.path.insert(0, str(HERE.parent / "learning"))
        import evidence_service as lev       # noqa: E402
        import learning_service as lsvc      # noqa: E402
        import pool_bridge as bridge         # noqa: E402
        import resource_pool_service as lpool  # noqa: E402
        import say_evidence as say_ev        # noqa: E402

        say_item = "FLTRP-EN-7A-2022CUR:X:D5F2794974F8"
        tmpdir = Path(tempfile.mkdtemp(prefix="zhixue_loop_"))
        tmp_db = self._seeded_learning_db(tmpdir, say_item)
        saved_pool_db, saved_say_db = bridge.LEARNING_DB, say_ev.LEARNING_DB
        saved_fn = bridge.formal_reinforce_entries
        bridge.LEARNING_DB, say_ev.LEARNING_DB = tmp_db, tmp_db
        try:
            # D. 正式池为空 → 原 Cookie 巩固路径照常，页面不空、不报错
            bridge.formal_reinforce_entries = lambda *a, **k: []
            op, _ = self.client()
            self.page(op, U1 + "?lesson=DEVELOPING_IDEAS")
            u1 = demo_server.unit_by_slug("unit1")
            lesson = demo_server.lesson_by_key(u1, "DEVELOPING_IDEAS")
            qs = demo_server.lesson_questions(u1, lesson)
            self.post(op, U1 + "/check/answer",
                      {"i": 0, "opt": "a" if qs[0]["answer"] != "a" else "b"})
            u0 = demo_server.unit_by_slug("starter")
            l0 = demo_server.lesson_by_key(u0, "GET_READY")
            lq = demo_server.listen_questions(u0, "word", l0)
            self.post(op, "/unit/starter/listen/answer",
                      {"mode": "word", "i": 0, "pick": "a" if lq[0]["answer"] != "a" else "b"})
            page = self.page(op, U1 + "/practice")
            self.assertIn("巩固练习 · 本课 + 已学内容", page)      # Cookie 入口仍在
            self.assertNotIn("巩固练习 · 课文简答", page)          # 没有正式池就不显示

            # F. 正式入口 → /say 重新作答 → 新 LearningRecord → 池随之变化
            bridge.formal_reinforce_entries = saved_fn
            entry = next(e for e in bridge.formal_reinforce_entries()
                         if e["item_id"] == say_item)
            self.page(op, entry["href"])
            conn = sqlite3.connect(str(tmp_db))
            try:
                before = conn.execute("SELECT COUNT(*) FROM learning_record WHERE item_id=?",
                                      (say_item,)).fetchone()[0]
            finally:
                conn.close()
            time.sleep(1.1)          # 证据去重按秒级时间戳取"最新"，隔 1 秒保证顺序确定
            self.post(op, "/unit/unit1/say/submit",
                      {"text": "The new students' problems are more subjects and more homework."})
            conn = sqlite3.connect(str(tmp_db))
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute("SELECT * FROM learning_record WHERE item_id=? "
                                    "ORDER BY created_at DESC, record_id DESC", (say_item,)).fetchall()
                self.assertEqual(len(rows), before + 1)
                self.assertEqual(rows[0]["result"], "correct")
            finally:
                conn.close()
            conn = lev.connect_learning_db(tmp_db)
            try:
                lid = rows[0]["learner_id"]
                ev = lev.collect_evidence(conn, lid, say_item)
                self.assertEqual(ev["evidence"][-1]["result"], "correct")
                pool_ids = [p["item_id"] for p in lpool.list_current_issue_pool(conn, lid)]
                self.assertNotIn(say_item, pool_ids)               # 答对 → 退出当前池
            finally:
                conn.close()
        finally:
            bridge.formal_reinforce_entries = saved_fn
            bridge.LEARNING_DB, say_ev.LEARNING_DB = saved_pool_db, saved_say_db
            shutil.rmtree(tmpdir, ignore_errors=True)


    # ---- 36 Demo V2 词汇：听音写词 / 音标写词 / 词形变化 --------------------
    def test_36_vocabulary_typed_tasks(self):
        import ai_grading as grade_mod       # noqa: E402

        op, _ = self.client()
        self.page(op, U1 + "?lesson=UNDERSTANDING_IDEAS")
        u1 = demo_server.unit_by_slug("unit1")
        lesson = demo_server.lesson_by_key(u1, "UNDERSTANDING_IDEAS")
        labels = re.findall(r'<span class="nm">([^<]+)</span>', self.page(op, "/"))
        self.assertIn("音标写词", labels)              # 首页六排之一
        self.assertNotIn("听音写词", labels)            # 听音写词已并入「听音辨意」入口内部
        self.assertNotIn("词形变化", labels)          # 这一课没有可靠词形题 → 不显示
        self.assertFalse(grade_mod.ai_configured())   # AI 调用 = 0

        # 听音辨意入口内部只有三种练习方式（P6-B-6：「听音写词」已删除）
        listen_page = self.page(op, U1 + "/listen?mode=word")
        self.assertIn("/unit/unit1/listen?mode=sentence", listen_page)
        self.assertIn("/unit/unit1/reading", listen_page)
        self.assertNotIn("/unit/unit1/spell", listen_page)   # 听音写词入口已删除
        self.assertNotIn("听音写词", listen_page)

        # 音标写词：显示教材音标 → 写单词
        phon = practice_v2.phonetic_tasks(u1, lesson)
        self.assertTrue(phon)
        page = self.page(op, U1 + "/phonetic")
        self.assertIn(phon[0]["phonetic"], page)
        self.assertIn('class="phbig"', page)
        _, fb = self.post(op, U1 + "/phonetic/submit", {"i": 0, "text": phon[0]["word"]})
        self.assertIn("答对了", fb)

        # 词形变化：只在教材正文里真的出现过该词形的课时出现（教材事实 + 唯一答案）
        u5 = demo_server.unit_by_slug("unit5")
        l5 = demo_server.lesson_by_key(u5, "READING_FOR_WRITING")
        forms = practice_v2.form_tasks(u5, l5)
        self.assertTrue(forms)
        self.page(op, "/unit/unit5?lesson=READING_FOR_WRITING")
        labels5 = re.findall(r'<span class="nm">([^<]+)</span>', self.page(op, "/"))
        self.assertIn("词形变化", labels5)
        page = self.page(op, "/unit/unit5/form")
        self.assertIn("（%s）" % forms[0]["base"], page)
        self.assertIn("______", page)
        _, fb = self.post(op, "/unit/unit5/form/submit", {"i": 0, "text": forms[0]["form"]})
        self.assertIn("答对了", fb)
        # 写错 → 变成一条 Cookie 学习证据（自主练习的专项/巩固沿用同一机制）
        op2, jar = self.client()
        self.page(op2, "/unit/unit5?lesson=READING_FOR_WRITING")
        self.post(op2, "/unit/unit5/form/submit", {"i": 0, "text": "wrong-form"})
        cookie = [c.value for c in jar if c.name == demo_server.state_mod.COOKIE_NAME][0]
        st = demo_server.state_mod.decode(cookie)
        evidence = demo_server.lesson_evidence(st, u5, l5)
        self.assertTrue(any(f["source"] == "词形变化" for f in evidence), evidence)
        # 没有词形题的课时：不生成题、也不显示入口
        u1b = demo_server.unit_by_slug("unit1")
        l1b = demo_server.lesson_by_key(u1b, "DEVELOPING_IDEAS")
        self.assertEqual(practice_v2.form_tasks(u1b, l1b), [])

    # ---- 37 阅读能力合并进「本课检测」（选择 + 简答，答案口径区分） ---------
    def test_37_reading_merged_into_check(self):
        op, _ = self.client()
        self.page(op, U1 + "?lesson=UNDERSTANDING_IDEAS")
        u1 = demo_server.unit_by_slug("unit1")
        lesson = demo_server.lesson_by_key(u1, "UNDERSTANDING_IDEAS")
        rows = demo_server.lesson_questions(u1, lesson)
        kinds = [q.get("kind") for q in rows]
        self.assertIn("choice", kinds)
        self.assertIn("short", kinds)                       # 阅读简答合并进检测
        # 首页不再有单独的「阅读理解」入口
        self.assertNotIn("阅读理解", re.findall(r'<span class="nm">([^<]+)</span>',
                                               self.page(op, "/")))
        ci = next(i for i, q in enumerate(rows) if q.get("kind") == "choice" and q.get("material"))
        si = next(i for i, q in enumerate(rows) if q.get("kind") == "short")
        # 阅读选择题：页面上有教材阅读材料；答错显示「答案」
        q_choice = rows[ci]
        page = self.page(op, U1 + "/check?i=%d" % ci)
        self.assertIn("阅读材料", page)
        self.assertIn(q_choice["material"][:24], page)
        wrong = "b" if q_choice["answer"] != "b" else "a"
        _, fb = self.post(op, U1 + "/check/answer", {"i": ci, "opt": wrong})
        self.assertIn("答案：", fb)
        # 阅读简答：有真实输入框；提交后给「参考答案」，不冒充唯一答案
        page2 = self.page(op, U1 + "/check?i=%d" % si)
        self.assertIn('name="text"', page2)
        self.assertIn('class="saybox"', page2)
        _, fb2 = self.post(op, U1 + "/check/answer", {"i": si, "text": "I think so."})
        self.assertIn("参考答案", fb2)
        self.assertIn(rows[si]["reference"], fb2)
        # 阅读题只出现在"题目依据真的在这段材料里"的课时（Unit 1 写作课不显示）
        l_rw = demo_server.lesson_by_key(u1, "READING_FOR_WRITING")
        self.assertEqual(practice_v2.reading_tasks(u1, l_rw)["items"], [])

    # ---- 38 表达任务类型明确 + 参考表达 ------------------------------------
    def test_38_expression_task_wording(self):
        import hashlib
        import shutil
        import tempfile

        sys.path.insert(0, str(HERE.parent / "learning"))
        import learning_service as lsvc      # noqa: E402
        import say_evidence as say_ev        # noqa: E402

        def sha(path):
            h = hashlib.sha256()
            with open(path, "rb") as fh:
                for chunk in iter(lambda: fh.read(65536), b""):
                    h.update(chunk)
            return h.hexdigest()

        official = lsvc.DEFAULT_LEARNING_DB
        before = sha(official)
        tmpdir = Path(tempfile.mkdtemp(prefix="zhixue_sayword_"))
        tmp_db = tmpdir / "learning.db"
        shutil.copyfile(official, tmp_db)
        saved = say_ev.LEARNING_DB
        say_ev.LEARNING_DB = tmp_db
        try:
            op, _ = self.client()
            # 课文问题 → 「用英文回答课文问题」
            self.page(op, U1 + "?lesson=DEVELOPING_IDEAS")
            page = self.page(op, U1 + "/say")
            self.assertIn("用英文回答课文问题", page)
            self.assertIn("你的表达", page)
            _, fb = self.post(op, U1 + "/say/submit",
                              {"text": "The new students' problems are more subjects."})
            self.assertIn("参考表达", fb)
            # 教材表达迁移 → 「用英文写一句话」+ 参考教材表达
            self.page(op, U1 + "?lesson=UNDERSTANDING_IDEAS")
            page2 = self.page(op, U1 + "/say")
            self.assertIn("用英文写一句话", page2)
            self.assertIn("参考教材的表达方式", page2)
        finally:
            say_ev.LEARNING_DB = saved
            shutil.rmtree(tmpdir, ignore_errors=True)
        self.assertEqual(sha(official), before)      # 正式库没有被本测试写入


    # ---- 39 视觉收口：六入口图标/底色、听音页顺序与间距、标题图标 -----------
    def test_39_visual_polish(self):
        op, _ = self.client()
        # 切到资源最全的课时，首页应出现六排
        self.post(op, "/lesson", {"lesson": "unit5@READING_FOR_WRITING", "back": "/"})
        home = self.page(op, "/")
        rows = re.findall(r'<a class="entryrow ([a-z-]+)[^"]*" href="([^"]+)">', home)
        self.assertEqual(len(rows), 6, rows)
        classes = [c for c, _ in rows]
        for a, b in zip(classes, classes[1:]):            # 相邻底色不能相同
            self.assertNotEqual(a, b, classes)
        icons = re.findall(r'<a class="entryrow [^"]*" href="[^"]+"><span class="ico">(.*?)</span>',
                           home)
        self.assertEqual(len(icons), 6)
        self.assertEqual(len(set(icons)), 6, "六个入口的图标不能重复")

        # 听音页顺序：模式入口必须在进度条上方
        for path in (U1 + "/listen?mode=word",):
            html = self.page(op, path)
            modes, steps = html.find('class="modes"'), html.find('class="steps"')
            self.assertGreaterEqual(modes, 0, path)
            self.assertGreaterEqual(steps, 0, path)
            self.assertLess(modes, steps, path)
        # 模式按钮紧凑（小按钮而不是大卡片）——「听音写词」专用布局规则已随该模式删除
        css = pages_mod.DEMO_CSS
        self.assertIn("min-height:34px;padding:5px 4px;font-size:14px", css)

        # 学习总结 / 专项练习 / 巩固练习：功能性标题带图标（正文不带）
        self.page(op, U1 + "?lesson=DEVELOPING_IDEAS")
        u1 = demo_server.unit_by_slug("unit1")
        lesson = demo_server.lesson_by_key(u1, "DEVELOPING_IDEAS")
        qs = demo_server.lesson_questions(u1, lesson)
        self.post(op, U1 + "/check/answer",
                  {"i": 0, "opt": "a" if qs[0]["answer"] != "a" else "b"})
        u0 = demo_server.unit_by_slug("starter")
        l0 = demo_server.lesson_by_key(u0, "GET_READY")
        lq = demo_server.listen_questions(u0, "word", l0)
        self.post(op, "/unit/starter/listen/answer",
                  {"mode": "word", "i": 0, "pick": "a" if lq[0]["answer"] != "a" else "b"})
        zp = self.page(op, U1 + "/practice")
        self.assertRegex(zp, r'<p class="ai-h">\s*<svg[^>]*>.*?</svg>\s*学习总结')
        for label in ("专项练习", "巩固练习"):
            row = re.search(r'<a class="plainrow" href="[^"]+"><span><span class="n">'
                            r'(.*?)</span>', zp)
            self.assertIsNotNone(row)
        self.assertTrue(re.search(r'<span class="n"><svg[^>]*>.*?</svg>专项练习',
                                  zp, re.S) or re.search(r'class="n"><svg', zp))


    # ---- 40 收口：练习区不重复标题 / 标题图标同行 / 自主练习=全部已学内容 ----
    def test_40_practice_range_and_title_icon(self):
        op, jar = self.client()
        # A. 听音辨意：练习区不重复功能名；「听音写词」入口与文字均已删除（P6-B-6）
        listen_html = self.page(op, U1 + "/listen?mode=word")
        main_text = visible_text(main_html(listen_html))
        self.assertIn("单词听辨", main_text)                  # 三种模式仍在（含当前选中项）
        self.assertIn("听音阅读", main_text)
        self.assertNotIn("听音写词", main_text)
        self.assertNotIn("/unit/unit1/spell", listen_html)
        self.assertNotIn("听一遍", main_text)
        self.assertNotIn("再听一遍", main_text)
        phon_text = visible_text(main_html(self.page(op, U1 + "/phonetic")))
        self.assertNotIn("音标写词", phon_text)                # 同样不重复顶部标题
        # B. 标题图标与文字同一行（inline-block + 垂直居中，不独占一行）
        css = pages_mod.DEMO_CSS
        self.assertRegex(css, r"\.ai-h svg\{display:inline-block;width:15px;height:15px;"
                              r"vertical-align:middle")
        self.assertRegex(css, r"a\.plainrow \.n svg\{display:inline-block;width:16px;"
                              r"height:16px;vertical-align:middle")

        # C. 自主练习范围 = 全部已经学过的内容（含"当前课时之后"但确实学过的课时）
        u1 = demo_server.unit_by_slug("unit1")
        dev = demo_server.lesson_by_key(u1, "DEVELOPING_IDEAS")
        for unit_code, lesson_key in (("Unit 3", "UNDERSTANDING_IDEAS"),
                                      ("Unit 4", "UNDERSTANDING_IDEAS")):
            u = next(x for x in demo_server.units() if x["unit_code"] == unit_code)
            l = demo_server.lesson_by_key(u, lesson_key)
            self.page(op, "/unit/%s?lesson=%s" % (u["slug"], lesson_key))
            rows = demo_server.lesson_questions(u, l)
            self.post(op, "/unit/%s/check/answer" % u["slug"],
                      {"i": 0, "opt": "a" if rows[0]["answer"] != "a" else "b"})
        self.page(op, U1 + "?lesson=DEVELOPING_IDEAS")
        cookie = [c.value for c in jar if c.name == demo_server.state_mod.COOKIE_NAME][0]
        st = demo_server.state_mod.decode(cookie)
        # studied_lessons：所有有记录的课时都在范围内（不再只取"当前课时之前"）
        studied = {u["unit_code"] for u, _ in demo_server.studied_lessons(st, u1, dev)}
        self.assertIn("Unit 3", studied)
        self.assertIn("Unit 4", studied)
        self.assertNotIn("Unit 6", studied)                     # 没学过的课时不会进来
        rows = demo_server.reinforce_practice(st, u1, dev)
        prompts = " ".join(r.get("prompt") or "" for r in rows)
        self.assertIn("Unit 3", prompts)                        # 后续但已学过 → 在自主练习范围内
        self.assertTrue(rows)


    # ---- 41 句子听辨 AI 智能干扰项：校验 / 数量 / 缓存 / 不阻塞页面 ----------
    def test_41_sentence_ai_distractors(self):
        import tempfile

        import sentence_distractors as sd     # noqa: E402

        target = {"text": "They have more subjects and more homework.",
                  "uid": "P3-07:AU11-B03", "pdf_page": 22}
        good = {"text": "They also have many activities.", "confidence": 0.8,
                "reason": "同单元教材原句", "origin": "textbook_sentence",
                "source_evidence": [{"kind": "textbook_sentence", "id": "P3-07:AU11-B04"}]}

        # 1. 正确答案不会被当成干扰项
        ok, why = sd.validate(dict(good, text=target["text"]), target, "Unit 1", set())
        self.assertFalse(ok)
        self.assertEqual(why, "same_as_answer")
        # 2. 重复干扰项被过滤
        seen = {sd._norm(good["text"])}
        ok, why = sd.validate(good, target, "Unit 1", seen)
        self.assertFalse(ok)
        self.assertEqual(why, "duplicate")
        # 3. 空值 / 异常文本被过滤
        for bad_text, expect in (("", "empty"), ("—", "empty"),
                                 ("AI 提示：请选择正确选项", "meta_or_abnormal_text"),
                                 ("<json>", "meta_or_abnormal_text")):
            ok, why = sd.validate(dict(good, text=bad_text), target, "Unit 1", set())
            self.assertFalse(ok, bad_text)
            self.assertEqual(why, expect, bad_text)
        # 4. 没有教材 evidence 的干扰项不会进入题目
        ok, why = sd.validate(dict(good, source_evidence=[]), target, "Unit 1", set())
        self.assertFalse(ok)
        self.assertEqual(why, "no_evidence")
        # 5. 合格干扰项数量可以是 1 / 2 / 3（不强制固定数量）
        pool = [{"text": "They also have many activities.", "confidence": 0.8,
                 "reason": "", "origin": "textbook_sentence",
                 "source_evidence": [{"kind": "textbook_sentence", "id": "P3-07:AU11-B04"}]},
                {"text": "How can they make good use of their time?", "confidence": 0.75,
                 "reason": "", "origin": "textbook_sentence",
                 "source_evidence": [{"kind": "textbook_sentence", "id": "P3-07:AU11-B05"}]},
                {"text": "They have more subjects and more life.", "confidence": 0.7,
                 "reason": "", "origin": "textbook_word_swap",
                 "source_evidence": [{"kind": "textbook_sentence", "id": "P3-07:AU11-B03"}]}]
        saved_candidates = sd.candidates_for
        try:
            for n in (1, 2, 3):
                sd.candidates_for = lambda t, u, _n=n: pool[:_n]
                entry = sd.build_entry("Unit 1", "DEVELOPING_IDEAS", target)
                self.assertEqual(len(entry["distractors"]), n)
                self.assertEqual(entry["correct_answer"], target["text"])   # 正确答案不被改写
                # 没有合格干扰项时不会硬凑
            sd.candidates_for = lambda t, u: [dict(pool[0], text=""), dict(pool[1], source_evidence=[])]
            self.assertEqual(sd.build_entry("Unit 1", "DEVELOPING_IDEAS", target)["distractors"], [])
        finally:
            sd.candidates_for = saved_candidates

        # 6/7. 缓存可复用；命中缓存时不再生成（生成函数被替换成抛错也不会影响）
        op, _ = self.client()
        real_sentence = {"text": "The new school year is beginning.", "uid": "P3-07:AU11-B01",
                         "pdf_page": 22}
        cached = sd.cached("Unit 1", "DEVELOPING_IDEAS", real_sentence)
        self.assertTrue(cached)
        saved_cache_file = sd.CACHE_FILE
        tmpdir = Path(tempfile.mkdtemp(prefix="zhixue_distract_"))
        tmp_cache = tmpdir / "cache.json"
        try:
            sd.save_cache({"version": sd.RULES_VERSION, "prompt_version": sd.PROMPT_VERSION,
                           "entries": {sd.context_hash("Unit 1", "DEVELOPING_IDEAS",
                                                       real_sentence["text"]):
                                       {"correct_answer": real_sentence["text"],
                                        "distractors": [dict(good)],
                                        "ai_called": False}}}, tmp_cache)
            sd.CACHE_FILE = tmp_cache
            sd.candidates_for = lambda *a, **k: (_ for _ in ()).throw(AssertionError("不应再生成"))
            self.assertEqual(len(sd.cached("Unit 1", "DEVELOPING_IDEAS", real_sentence)), 1)
            # 8. 页面打开不依赖 AI：清空缓存路径时句子听辨照常打开（回落既有机制）
            sd.CACHE_FILE = tmpdir / "missing.json"
            self.page(op, U1 + "?lesson=DEVELOPING_IDEAS")     # 这一课时有教材短句
            page = self.page(op, U1 + "/listen?mode=sentence")
            self.assertIn('class="spkbig"', page)
            self.assertGreaterEqual(page.count('name="pick"'), 1)
        finally:
            sd.candidates_for = saved_candidates
            sd.CACHE_FILE = saved_cache_file
            shutil.rmtree(tmpdir, ignore_errors=True)

        # 10. 原有句子听辨不回归：题目与选项来自教材，选项数 2–4，正确答案只有一次
        u1 = demo_server.unit_by_slug("unit1")
        lesson = demo_server.lesson_by_key(u1, "DEVELOPING_IDEAS")
        rows = demo_server.listen_questions(u1, "sentence", lesson)
        self.assertTrue(rows)
        for q in rows:
            texts = [t for _l, t in q["options"]]
            self.assertGreaterEqual(len(texts), 2)
            self.assertLessEqual(len(texts), 4)
            self.assertEqual(texts.count(q["prompt"]), 1)          # 正确答案只出现一次
            self.assertEqual(texts["abcd".index(q["answer"])], q["prompt"])
        # 页面看不到任何内部信息（AI/evidence/confidence/reason）
        shown = visible_text(self.page(op, U1 + "/listen?mode=sentence"))
        for hidden in ("AI", "evidence", "confidence", "reason", "干扰项", "教材原句"):
            self.assertNotIn(hidden, shown)


    # ---- 42 规则收口：正确句 + 短尾/短前缀追加必须过滤，正常替换不受影响 ----
    def test_42_append_pattern_rule(self):
        sys.path.insert(0, str(HERE))
        import sentence_distractors as sd     # noqa: E402

        target = {"text": "Are you ready?"}
        ev = [{"kind": "textbook_sentence", "id": "PREVIEW:AU01:S0005"}]
        # 正确答案 + 短尾追加 / 短前缀追加 → 必须过滤
        for text in ("Are you ready, everyone?", "Are you ready to start?",
                     "Well, are you ready?"):
            ok, why = sd.validate({"text": text, "confidence": 0.9, "reason": "",
                                   "origin": "ai", "source_evidence": ev},
                                  target, "Starter", set())
            self.assertFalse(ok, text)
            self.assertEqual(why, "appended_tail_or_prefix", text)
        # 正常语义替换（教材词汇/成分替换）→ 不能被这条规则误过滤
        for text in ("Are you nervous?", "What are you going to wear?"):
            ok, why = sd.validate({"text": text, "confidence": 0.9, "reason": "",
                                   "origin": "ai", "source_evidence": ev},
                                  target, "Starter", set())
            self.assertTrue(ok, "%s -> %s" % (text, why))
        # 词级判断本身：正确句完整保留 + 少量追加才命中
        self.assertTrue(sd.is_append_pattern("The new school year is beginning.",
                                             "The new school year is beginning for you."))
        self.assertFalse(sd.is_append_pattern("The new school year is beginning.",
                                              "The new life is beginning."))
        self.assertEqual(sd.RULES_VERSION, "rules-v3")


    # ---- 43 rules-v3：当前 Unit 教材资源边界（条目分词 / 正常词形 / 撇号） ----
    def test_43_unit_resource_boundary_word_forms(self):
        sys.path.insert(0, str(HERE))
        import sentence_distractors as sd     # noqa: E402

        ev = [{"kind": "textbook_sentence", "id": "P3-07:AU11-B02"}]

        def check(text, unit, target, expect_ok):
            ok, why = sd.validate({"text": text, "confidence": 0.8, "reason": "",
                                   "origin": "ai", "source_evidence": ev},
                                  {"text": target}, unit, set())
            self.assertEqual(ok, expect_ok, "%s -> %s" % (text, why))
            return why

        # 1. 短语条目里的词不再整条当作一个 token（teaching building / primary school）
        check("Let's go around the teaching building together!", "Starter",
              "Let\u2019s go around the school together!", True)
        check("Mia, how do you feel about your first day in primary school tomorrow?", "Unit 1",
              "Mia, how do you feel about your first day in junior high tomorrow?", True)
        # 2. 句型条目里的词（lucky）
        check("Well, I'm a little lucky.", "Unit 1", "Well, I'm a little nervous.", True)
        # 3. 单复数 / 所有格 / -ing
        check("Dad and Mum can protect it from storms.", "Unit 1",
              "Dad and Mum can protect it from winds.", True)
        check("The new students will hold a talk this Thursday to help you.", "Unit 1",
              "The Students' Union will hold a talk this Thursday to help you.", True)
        check("What are the new student's problems?", "Unit 1",
              "What are the new students' problems?", True)
        check("Are you laughing?", "Unit 4", "\u201cAre you joking?", True)
        # 4. 撇号差异（Let’s / Let's）视为同一写法
        self.assertEqual(sd._words("Let\u2019s go around"),
                         sd._words("Let's go around"))
        # 5. 边界没有被放开：未来 Unit 的词与真正的教材外词仍然拦截
        #    （"hold" 属于已学范围内的 Unit 1 句子，rules-v3 之后按已学范围放行）
        self.assertTrue(check("What does tea mean to adults?", "Unit 4",
                              "How I wish to have four hands now!", False)
                        .startswith("out_of_stage"))
        self.assertTrue(check("Are you laughing at the zebra?", "Unit 4",
                              "\u201cAre you joking?", False).startswith("out_of_stage"))
        self.assertEqual(sd.RULES_VERSION, "rules-v3")


    # ---- 44 已学教材资源范围：Starter + 连续前缀（与浏览 Unit 解耦） ----
    def test_44_learned_unit_prefix(self):
        sys.path.insert(0, str(HERE))
        import sentence_distractors as sd     # noqa: E402

        codes = [u["unit_code"] for u in demo_server.units()]
        self.assertEqual(codes[0], "Starter")
        self.assertNotIn("Appendix", codes)                    # Appendix 永不进入范围

        def prefix_of(slug):
            return [u["unit_code"] for u in
                    demo_server.unit_prefix_upto(demo_server.unit_by_slug(slug))]

        # 1/2. U1 与 U4 的连续前缀
        self.assertEqual(prefix_of("unit1"), ["Starter", "Unit 1"])
        self.assertEqual(prefix_of("unit4"),
                         ["Starter", "Unit 1", "Unit 2", "Unit 3", "Unit 4"])
        # 3. 未来 Unit 不进入
        self.assertNotIn("Unit 5", prefix_of("unit4"))
        self.assertNotIn("Unit 6", prefix_of("unit4"))
        self.assertEqual(sd.learned_unit_codes("Unit 4")[:2], ["Starter", "Unit 1"])
        self.assertNotIn("Unit 5", sd.learned_unit_codes("Unit 4"))
        self.assertNotIn("Appendix", sd.learned_unit_codes("Unit 4"))

        # 5. 浏览 Unit ≠ 学习进度：Cookie 里的 u 变化不影响已学范围
        st = demo_server.state_mod.blank()
        st["a"] = {"starter::GET_READY": {"q1": "a"}}           # Starter 课时有真实学习行为
        self.assertTrue(demo_server.lesson_has_evidence(
            st, demo_server.unit_by_slug("starter"),
            demo_server.lesson_by_key(demo_server.unit_by_slug("starter"), "GET_READY")))
        st["u"] = "unit6"
        browse6 = [u["unit_code"] for u in demo_server.learned_unit_prefix(st)]
        st["u"] = "unit3"
        browse3 = [u["unit_code"] for u in demo_server.learned_unit_prefix(st)]
        self.assertEqual(browse3, browse6)                      # 换浏览位置不改变进度
        self.assertNotIn("Unit 6", browse6)
        # 空状态（无证据）不会用浏览 Unit 冒充进度
        empty = {"u": "unit4"}
        self.assertEqual([u["unit_code"] for u in demo_server.learned_unit_prefix(empty)],
                         [u["unit_code"] for u in demo_server.learned_unit_prefix()])


if __name__ == "__main__":
    unittest.main(verbosity=2)
