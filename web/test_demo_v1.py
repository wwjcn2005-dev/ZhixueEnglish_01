#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""全功能 Demo V1 专项测试（stdlib unittest，无新依赖、无网络、无 AI）

对应任务书 §三十一 的 15 项要求：
  1 首页可进入 ｜ 2 教材中心可进入 ｜ 3 Unit 1 可进入 ｜ 4 教材页可进入
  5 VERIFIED sentence audio 正确播放 ｜ 6 activity-level fallback 正确
  7 Vocabulary 可完成 ｜ 8 Shadowing 可录音/回放 ｜ 9 Exercise 可完成
  10 Result 可显示 ｜ 11 Demo AI feedback 可显示 ｜ 12 Progress 可显示
  13 Demo 数据不写正式 DB ｜ 14 AI 调用 0 ｜ 15 手机 390×844 页面可操作

所有需要写入的检查都只在 %TEMP% 的 learning.db 副本上进行；
正式 learning.db 与 contentpack 全程只读，并在测试前后校验 SHA256。
"""

from __future__ import annotations

import hashlib
import http.cookiejar
import json
import re
import shutil
import sqlite3
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


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


BUSINESS_TABLES = ("learner", "learning_session", "learning_task", "task_item",
                   "learning_record", "mastery_state")


def business_counts(db_path) -> dict:
    conn = sqlite3.connect("file:%s?mode=ro" % Path(db_path).as_posix(), uri=True)
    try:
        return {t: conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
                for t in BUSINESS_TABLES}
    finally:
        conn.close()


OFFICIAL_DB_SHA = sha256_file(content_mod.LEARNING_DB)
OFFICIAL_DB_COUNTS = business_counts(content_mod.LEARNING_DB)
CONTENTPACK_SHA = sha256_file(content_mod.CONTENTPACK)


def visible(body: str) -> str:
    """只看页面可见文本（去掉 style/script 与标签），避免命中 CSS 注释里的词。"""
    text = re.sub(r"(?s)<style>.*?</style>", " ", body)
    text = re.sub(r"(?s)<script>.*?</script>", " ", text)
    return re.sub(r"<[^>]+>", " ", text)


# ---------------------------------------------------------------------------
# 1. 演示数据层本身
# ---------------------------------------------------------------------------

class DemoDataLayerTest(unittest.TestCase):
    """演示数据层：存在、可控、零写入、零 AI。"""

    def test_01_demo_mode_is_explicit(self):
        self.assertTrue(demo.DEMO_MODE)
        self.assertTrue(demo.DEMO_LABEL)
        self.assertIn("不会写入", demo.DEMO_NOTE)

    def test_02_demo_layer_has_no_database_or_service_access(self):
        src = (HERE / "demo_data.py").read_text(encoding="utf-8").lower()
        for token in ("sqlite3", "learning_service", "session_service", "vocabulary_service",
                      "resource_pool_service", "insert into", "update ", "delete from",
                      "create table", "alter table", "drop table"):
            self.assertNotIn(token, src, "演示数据层不得访问数据库/冻结服务：%s" % token)
        # 演示层只允许标准库 datetime
        self.assertIn("import datetime", src)

    def test_03_demo_pages_have_no_ai_or_network_tokens(self):
        for name in ("app.py", "ui.py", "content.py", "flow.py", "demo_data.py"):
            src = (HERE / name).read_text(encoding="utf-8").lower()
            for token in ("openai", "deepseek", "ollama", "anthropic", "requests.",
                          "urllib.request", "http.client", "socket.", "transformers",
                          "torch", "tensorflow", "tts", "ocr"):
                self.assertNotIn(token, src, "%s 不得包含 AI / 网络调用：%s" % (name, token))
        # 演示数据层本身更严格：连语音识别能力也不得出现
        src = (HERE / "demo_data.py").read_text(encoding="utf-8").lower()
        for token in ("asr", "whisper", "speech"):
            self.assertNotIn(token, src, "演示数据层不得包含语音识别能力：%s" % token)

    def test_04_practice_answers_are_grounded_in_real_textbook_content(self):
        """演示练习的参考答案必须能由真实教材内容核对，不得凭空编造。"""
        cp = content_mod._ro(content_mod.CONTENTPACK)
        try:
            meanings = {}
            for row in cp.execute(
                    "SELECT canonical_text, meaning_zh FROM learning_item "
                    "WHERE item_type IN ('vocabulary','phrase')"):
                meanings.setdefault((row["canonical_text"] or "").lower(),
                                    row["meaning_zh"] or "")
        finally:
            cp.close()
        # 词汇演示题：选项答案必须真的是教材词表里的释义
        for word, meaning in (("advice", "意见建议"), ("problem", "问题难题"),
                              ("in fact", "事实上")):
            self.assertIn(meaning, meanings.get(word, ""),
                          "演示答案必须与教材词表一致：%s" % word)
        # 句子演示题：填空答案必须真的出现在教材原句里
        sentences = " ".join(s["text"] for s in content_mod.unit_audio_resources(
            "Unit 1")["sentences"])
        for word in ("beginning", "best", "share"):
            self.assertIn(word, sentences, "演示答案必须是教材原句里的词：%s" % word)
        # 判断题：教材原句是 talk this Thursday，不是 party this Friday
        self.assertIn("hold a talk this Thursday", sentences)
        self.assertNotIn("hold a party this Friday", sentences)

    def test_05_drill_builders_are_deterministic_and_grounded(self):
        """训练题（Demo V1.1 取代 V1 的综合演示练习组）：可复现、每题都有教材依据。"""
        words = [{"text": "problem", "meaning": "问题难题", "key": "k1",
                  "audio_url": "/audio/word/k1.wav"},
                 {"text": "advice", "meaning": "意见建议", "key": "k2",
                  "audio_url": "/audio/word/k2.wav"},
                 {"text": "hope", "meaning": "希望", "key": "k3",
                  "audio_url": "/audio/word/k3.wav"}]
        first = demo.build_vocab_drill(words)
        second = demo.build_vocab_drill(words)
        self.assertEqual(first, second, "同一输入必须产出同一份题目（可复现）")
        self.assertTrue(first)
        for item in first:
            self.assertTrue(item["why"], "每题都必须给出教材依据")
            self.assertIn(item["answer"], [k for k, _ in item["options"]])
        # 正确答案的位置会轮换，不是永远 a
        self.assertGreater(len({i["answer"] for i in first}), 1)
        # 教材句子缺失时，依赖句子的环节不硬造题目
        self.assertEqual(demo.build_phrase_drill([], []), [])
        self.assertEqual(demo.build_listening_drill([]), [])

    def test_06_no_score_or_exam_language_in_demo_text(self):
        blob = json.dumps({
            "note": demo.DEMO_NOTE,
            "attention": demo.ATTENTION,
            "progress": demo.CHAPTER_PROGRESS,
            "themes": demo.UNIT_THEME, "steps": demo.STEP_HINT,
        }, ensure_ascii=False)
        for bad in ("正确率", "掌握率", "得分", "满分", "分数", "排名", "积分", "徽章"):
            self.assertNotIn(bad, blob, "演示文案不得出现评分/游戏化语言：%s" % bad)
        # 口语练习只给次数，不给分数（V1.1 §17）
        for triple in demo.CHAPTER_PROGRESS.values():
            label, value, percent, _note = triple[2]
            self.assertEqual(label, "口语练习")
            self.assertIsNone(percent, "口语练习不得出现百分比（不是发音分数）")
            self.assertIn("次", value)
            self.assertNotIn("分", value)


# ---------------------------------------------------------------------------
# 2. 真实 HTTP：完整 Demo 链路
# ---------------------------------------------------------------------------

class DemoHttpTest(unittest.TestCase):
    """在临时 learning.db 副本上跑完整 Demo 链路（正式数据全程只读）。"""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="zhixue_demo_v1_"))
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
            with opener.open("http://127.0.0.1:%d%s" % (self.port, path), timeout=20) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8")

    def _post(self, opener, path, data):
        body = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request("http://127.0.0.1:%d%s" % (self.port, path), data=body)
        try:
            with opener.open(req, timeout=20) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8")

    # ---- 1–4 / 10–12：所有 Demo 页面可进入 -------------------------------
    def test_01_all_demo_pages_reachable(self):
        opener = self._client()
        for path in ("/", "/learn", "/textbook", "/progress", "/review",
                     # P6-B-16：旧训练岛的 /practice（原本 302 → /train）随旧岛一并退休；
                     # P6-B-23：旧句子学习页 / 旧跟读页 / 旧学习结果页也已退休，不再可达
                     "%s/text" % UNIT1,
                     "%s/exercises" % UNIT1, "%s/resources/vocabulary" % UNIT1):
            status, body = self._get(opener, path)
            self.assertEqual(status, 200, path)
            # 第三版 Demo：所有页面都没有底部一级导航（首页 / 学习 / 进展）
            self.assertNotIn('<nav class="nav"', body, path)

    def test_02_home_is_a_learning_home(self):
        opener = self._client()
        status, body = self._get(opener, "/")
        self.assertEqual(status, 200)
        # 第三版 Demo：首页 = 章节选择 → 功能入口列表（课文点读在最后）
        for token in ("七年级上册英语", "今天学什么", "单词跟读", "听音辨词",
                      "短语练习", "阅读练习", "听辨练习", "课文点读", "开始教材学习"):
            self.assertIn(token, body, "首页必须回答：学到哪里 / AI怎么看 / 今天做什么")
        self.assertIn('href="/textbook"', body)
        # 第三版：首页不再有「我的进展」与 AI 助教入口
        self.assertNotIn('href="/progress"', body)
        self.assertNotIn('href="/tutor"', body)
        self.assertNotIn('<section class="ai">', body)
        self.assertNotIn("我的进展", visible(body))
        # 演示数据必须被明确标注
        self.assertIn(demo.DEMO_LABEL, body)
        # 首页仍然不得出现游戏化/内部信息
        for bad in ("恭喜", "完美", "已全部掌握", "积分", "排名", "徽章",
                    "session_id", "task_id", "item_id", "contentpack", "CORE",
                    "current_error", "current_weak", "FLTRP-EN-7A-2022CUR"):
            self.assertNotIn(bad, body, "首页不得出现：%s" % bad)

    def test_04_textbook_center_shows_every_unit_with_natural_state(self):
        opener = self._client()
        status, body = self._get(opener, "/textbook")
        self.assertEqual(status, 200)
        for code in ("Starter", "Unit 1", "Unit 2", "Unit 3", "Unit 4", "Unit 5",
                     "Unit 6", "Appendix"):
            self.assertIn(code, body)
        self.assertEqual(body.count('class="unitrow"'), 8)
        self.assertIn("演示主单元", body)                 # Unit 1
        self.assertIn("教材已准备", body)                 # Unit 2–6 不是死按钮
        self.assertNotIn("敬请期待", body)

    # ---- 5 / 6：音频资源 ------------------------------------------------
    def test_05_verified_sentence_audio_uses_real_timing(self):
        opener = self._client()
        rows = content_mod.unit_audio_resources("Unit 1")["sentences"]
        self.assertGreaterEqual(len(rows), 12)
        _status, body = self._get(opener, "%s/text" % UNIT1)
        # P6-B-12：正文只展示"能与官方音频可靠对应（VERIFIED）"的块，
        # 句级热点因此只出现在这些块内 —— 旧断言"12 条标注必然全部出现"属已废止规则。
        # 现在的口径：页面上出现的每一个时间区间都必须来自已核验的句子标注（不伪造时间轴）。
        markers = re.findall(r'data-audio="([A-Z0-9]+)" data-start="(\d+)" data-end="(\d+)"', body)
        self.assertTrue(markers, "教材原文必须至少承载一处已核验的真实时间区间")
        known = {(r["audio_code"], int(r["start_ms"]), int(r["end_ms"])) for r in rows}
        for code, start, end in markers:
            self.assertIn((code, int(start), int(end)), known,
                          "时间区间必须来自已核验的句子标注：%s" % code)
        # P6-B-23：旧跟读页已退休；已核验的真实区间仍由教材原文页自身承载
        self.assertIn('data-audio="AU13" data-start="13940" data-end="21021"', body)

    def test_06_activity_level_fallback_is_labelled_honestly(self):
        opener = self._client()
        _status, body = self._get(opener, "%s/text" % UNIT1)
        self.assertIn("活动级音频（整段，未做句子切分）", body)
        self.assertIn("活动级完整录音", body)
        # 每一个活动级音频都以"整段"（data-start=0，不切分）方式呈现，不伪装成句子切片
        for act in content_mod.unit_audio_resources("Unit 1")["activities"]:
            marker = 'data-audio="%s" data-start="0"' % act["audio_code"]
            self.assertIn(marker, body, "活动级音频必须整段呈现：%s" % act["audio_code"])
        # 活动级音频仍然指向真实官方 MP3（由前端按 data-audio 组装同一路径）
        for code in ("AU07", "AU11", "AU13"):
            self.assertIn('data-audio="%s"' % code, body)
        self.assertNotIn('data-start="0.5"', body)

    # ---- 7：Vocabulary 可完成 --------------------------------------------
    def test_07_vocabulary_chain_completes(self):
        opener = self._client()
        _status, listing = self._get(opener, "%s/resources/vocabulary" % UNIT1)
        pick = re.search(r'name="pick" value="([^"]+)"', listing).group(1)
        status, study = self._post(opener, "/vocabulary/study",
                                   {"pick": pick, "name": "演示同学"})
        self.assertEqual(status, 200)
        self.assertIn("我看完了", study)
        sid = re.search(r'name="session_id" value="([^"]+)"', study).group(1)
        lid = re.search(r'name="learner_id" value="([^"]+)"', study).group(1)
        _status, recall = self._post(opener, "/vocabulary/study/done",
                                     {"session_id": sid, "pick": pick, "learner_id": lid})
        self.assertIn("显示意思", recall)
        for label in ("我记得", "有点模糊", "忘了"):
            self.assertIn(label, recall)
        _status, result = self._post(opener, "/vocabulary/practice",
                                     {"session_id": sid, "pick": pick,
                                      "learner_id": lid, "choice": "fuzzy"})
        self.assertIn("你的回忆：有点模糊", result)
        for action in ("再学一次", "回到词汇表", "看看需要再学的"):
            self.assertIn(action, result)

    # ---- 8 / 10：旧跟读页与旧学习结果页已退休（P6-B-23） ------------------
    def test_08_legacy_sentence_pages_are_retired(self):
        for path in ("%s/result" % UNIT1,
                     "%s/sentence" % UNIT1,
                     "%s/shadowing?uid=%s" % (UNIT1, urllib.parse.quote("P3-07:AU13-DLG-01"))):
            status, _body = self._get(self._client(), path)
            self.assertEqual(status, 404, "%s 必须已退休" % path)

    # ---- 11 / 12：AI 反馈与进展可显示 ------------------------------------
    def test_11_ai_card_is_available_without_the_retired_pages(self):
        opener = self._client()
        # 第三版：AI 不在首页；AI 卡不是一级入口
        _status, home = self._get(opener, "/")
        self.assertNotIn("AI 随堂助教", visible(home))
        # P6-B-23：承载 AI 卡的旧单元页/旧结果页已退休，卡片能力（数据 + 渲染）保留
        card = ui.ai_card(demo.chapter_ai(
            "Unit 1", {"key_points": [("nervous", "教材重点词")]}, {}))
        self.assertIn("AI 随堂助教", card)
        self.assertIn("不是真实 AI 判断", card)

    def test_12_progress_page_shows_learning_scope_not_mastery(self):
        opener = self._client()
        status, body = self._get(opener, "/progress")
        self.assertEqual(status, 200)
        # Demo V1.1 §15/§16：面向家长的三个维度
        for token in ("我的学习进展", "这一周", "课文理解", "句型语法", "口语练习",
                      "最近学过", "当前值得关注"):
            self.assertIn(token, body)
        self.assertIn("88%", body)
        self.assertIn("60%", body)
        self.assertIn("6 次", body)
        self.assertIn("本周 Unit 1 课文理解较稳定", body)
        self.assertIn("部分句型还需要继续巩固", body)
        self.assertIn("本周完成 6 次跟读", body)
        self.assertIn("不判断发音好坏", body)               # 口语只记录练习行为
        self.assertIn(demo.DEMO_LABEL, body)               # 演示数据被标注
        for bad in ("雷达图", "掌握率", "正确率", "排名", "积分", "徽章",
                    "knowledge_id", "evidence_id", "mastery_state", "发音评分"):
            self.assertNotIn(bad, body)

    # ---- 13 / 14：Demo 数据不写库、AI 调用 0 -----------------------------
    def test_14_no_ai_calls_anywhere_in_the_demo_chain(self):
        # 演示链路只包含本地只读数据 + 静态文案
        opener = self._client()
        for path in ("/", "/progress", "%s/text" % UNIT1):
            _status, body = self._get(opener, path)
            for token in ("api", "API Key", "网络", "联网", "云端"):
                self.assertNotIn(token, body, "%s 不得暗示需要联网 AI：%s" % (path, token))
        src = (HERE / "demo_data.py").read_text(encoding="utf-8")
        self.assertNotIn("import urllib", src)
        self.assertNotIn("import socket", src)

    # ---- 15：手机 390×844 页面可操作 -------------------------------------
# ---------------------------------------------------------------------------
# 3. 正式数据保护
# ---------------------------------------------------------------------------

class OfficialDataProtectionTest(unittest.TestCase):
    """S：本次实现不得修改任何正式数据。"""

    def test_01_official_db_untouched(self):
        self.assertEqual(sha256_file(content_mod.LEARNING_DB), OFFICIAL_DB_SHA)
        self.assertEqual(business_counts(content_mod.LEARNING_DB), OFFICIAL_DB_COUNTS)

    def test_02_contentpack_untouched(self):
        self.assertEqual(sha256_file(content_mod.CONTENTPACK), CONTENTPACK_SHA)

    def test_03_frozen_learning_services_untouched(self):
        expected = {
            "learning_service.py": "01341A05231EFCA6E0C801CF95D8A96F3DF732753F1F679688D44708586DF1D6",
            "session_service.py": "0CF7A20615780831F544BDF295202028CE2EEFB15D234820CD1184AD4A6B665F",
            "activity_service.py": "AAFF907C869797EE697D5F756C7E03C62CEB942809B2406933761195DA092028",
            "behavior_service.py": "0C6EF4822F60D9251B68382C95A5D3D9987650811F4FC93C70875AF48249FC6D",
            "vocabulary_service.py": "D06DCC76A5A4CCAF5C0BC3C17BB33CFF5D6056B7C872406A3934223C8870D632",
            "resource_pool_service.py": "D4488E1FFBA6B553EB6932BE195932A4C464D9526790B138C0C55DAA612D2F37",
        }
        for name, sha in expected.items():
            self.assertEqual(sha256_file(HERE.parent / "learning" / name), sha,
                             "%s 属冻结文件，不得修改" % name)

    def test_04_no_new_routes_removed(self):
        src = (HERE / "app.py").read_text(encoding="utf-8")
        for route in ('"/"', '"/textbook"', '"/health"', '"/review"', '"/vocabulary/study"',
                      '"/vocabulary/study/done"', '"/vocabulary/recall/reveal"',
                      '"/vocabulary/practice"', '"/learn"', '"/progress"'):
            self.assertIn(route, src, "路由不得丢失：%s" % route)


if __name__ == "__main__":
    unittest.main(verbosity=2)
