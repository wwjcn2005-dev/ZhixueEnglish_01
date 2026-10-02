#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-6-D-2 测试：Learning Object → `/review` 最小接入（只读接入，临时库）。

覆盖任务书 §十五 的 8 项要求，并追加空状态与异常降级 2 项。
"""

from __future__ import annotations

import hashlib
import http.cookiejar
import json
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
sys.path.insert(0, str(HERE.parent / "learning"))
sys.dont_write_bytecode = True

import app as web_app                     # noqa: E402
import content as content_mod             # noqa: E402
import flow                               # noqa: E402
import learning_object_service as lo_svc  # noqa: E402
import learning_service as svc            # noqa: E402
import ui                                 # noqa: E402

BUSINESS = ("learner", "learning_session", "learning_task", "task_item",
            "learning_record", "mastery_state")
OFFICIAL_DB = content_mod.LEARNING_DB
OFFICIAL_SHA = hashlib.sha256(OFFICIAL_DB.read_bytes()).hexdigest().upper()


class ReviewIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="zhixue_d2_"))
        cls.db = cls.tmpdir / "learning.db"
        shutil.copyfile(OFFICIAL_DB, cls.db)
        web_app.Handler.learning_db = cls.db
        web_app.Handler.contentpack_path = content_mod.CONTENTPACK
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), web_app.Handler)
        cls.port = cls.srv.server_address[1]
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()
        cls.textbook = "FLTRP-EN-7A-2022CUR"
        # 真实同-LO 用例：单词 eraser（含映射练习，D-1 Case C）
        VS = lo_svc.vocabulary_lo_map()
        cls.word_item = next(i for i, v in VS.items() if v["lexeme"] == "eraser")
        cls.lo_id = VS[cls.word_item]["learning_object_id"]

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.thread.join(timeout=5)
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    # ---------- helpers ----------
    def _client(self):
        jar = http.cookiejar.CookieJar()
        return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def _get(self, opener, path):
        try:
            with opener.open("http://127.0.0.1:%d%s" % (self.port, path), timeout=15) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8")

    def _post(self, opener, path, data):
        body = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request("http://127.0.0.1:%d%s" % (self.port, path), data=body,
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        with opener.open(req, timeout=15) as r:
            return r.status, r.read().decode("utf-8")

    def _seed_attention(self, name="D2注意力"):
        """建立学习者 + 一条 incorrect 证据 → 该 LO 进入 current_error。"""
        opener = self._client()
        self._post(opener, "/review", {"name": name})
        conn = sqlc = sqlite3.connect(str(self.db))
        sqlc.row_factory = sqlite3.Row
        try:
            lid = conn.execute("SELECT learner_id FROM learner WHERE display_name=?",
                               (name,)).fetchone()["learner_id"]
            task = svc.create_task(conn, lid, "learn", [self.word_item], self.textbook)
            svc.record_learning_event(conn, lid, task["task_id"], self.word_item, "practice",
                                      result="incorrect", created_at="2026-09-22T10:00:00+08:00")
        finally:
            conn.close()
        return opener, lid

    def _counts(self):
        conn = sqlite3.connect("file:%s?mode=ro" % self.db.as_posix(), uri=True)
        try:
            return {t: conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
                    for t in BUSINESS}
        finally:
            conn.close()

    def _render(self, lid):
        conn = flow.pool.connect_learning_db(self.db)
        try:
            section = flow.lo_review_section(conn, lid)
            html = ui.review_page({"pool": flow.need_relearn(conn, lid),
                                   "suggestions": flow.textbook_review_suggestions(conn, lid),
                                   "lo_section": section, "learner_name": "测试"})
            return section, html
        finally:
            conn.close()

    # ---------- 1–8：任务书要求 ----------
    def test_01_review_renders_lo_section(self):
        opener, lid = self._seed_attention()
        status, body = self._get(opener, "/review")
        self.assertEqual(status, 200)
        self.assertIn("教材学习建议", body)
        section, _ = self._render(lid)
        self.assertTrue(section["items"], "该 LO 应出现在建议区")
        # 页面渲染孩子可读内容（标题/诊断/建议），不暴露内部 LO id
        self.assertIn(section["items"][0]["title"], body)
        self.assertNotIn(self.lo_id, body, "不得向孩子暴露内部 LO id")

    def test_02_text_comes_from_d1_service(self):
        _opener, lid = self._seed_attention()
        section, html = self._render(lid)
        item = section["items"][0]
        self.assertEqual(item["mastery_display_text"], "学习证据 1 次（不代表掌握）")
        self.assertIn(item["mastery_display_text"], html)
        self.assertIn(item["diagnosis_label"], html)

    def test_03_ui_does_not_recompute_mastery(self):
        src = Path(HERE / "ui.py").read_text(encoding="utf-8")
        for token in ("mastery_service", "evidence_service", "diagnosis_service",
                      "learning_object_service", "resource_pool_service"):
            self.assertNotIn(token, src, "UI 不得直接 import 学习服务：%s" % token)

    def test_04_suggestion_order_from_d1(self):
        _opener, lid = self._seed_attention()
        section, html = self._render(lid)
        types = [s["type"] for s in section["items"][0]["suggestions"]]
        self.assertTrue(types)
        order = flow.lo_svc.ev.load_rules()["intervention"]["textbook_first_order"]
        self.assertEqual(types, [t for t in order if t in types])
        self.assertIn("回看原教材文本", html)

    def test_05_links_are_plain_anchors(self):
        opener, _lid = self._seed_attention()
        _status, body = self._get(opener, "/review")
        self.assertIn("<a href=", body)
        self.assertNotIn("onclick", body.lower())
        self.assertNotIn("<script", body.lower())

    def test_06_no_auto_execution(self):
        opener, _lid = self._seed_attention()
        _status, body = self._get(opener, "/review")
        for token in ("autoplay", "setTimeout", "location.href =", "window.location",
                      "auto-submit", "onload="):
            self.assertNotIn(token.lower(), body.lower())

    def test_07_no_command_language(self):
        opener, _lid = self._seed_attention()
        _status, body = self._get(opener, "/review")
        for token in ("今日任务", "必须完成", "下一步必须学习", "系统为你安排", "推荐任务",
                      "立即开始", "任务完成"):
            self.assertNotIn(token, body)
        self.assertIn("都由你自己决定", body)

    def test_08_get_review_writes_nothing(self):
        opener, _lid = self._seed_attention()
        before = self._counts()
        for _ in range(2):
            status, _body = self._get(opener, "/review")
            self.assertEqual(status, 200)
        self.assertEqual(self._counts(), before, "GET /review 必须零写入")

    # ---------- 9–10：追加（空状态 / 异常降级） ----------
    def test_09_empty_state_when_no_attention(self):
        opener = self._client()
        self._post(opener, "/review", {"name": "D2空态"})
        status, body = self._get(opener, "/review")
        self.assertEqual(status, 200)
        self.assertIn("暂时没有需要再看的教材学习对象", body)

    def test_10_degrades_safely_on_service_error(self):
        _opener, lid = self._seed_attention("D2降级")
        original = lo_svc.needs_attention
        lo_svc.needs_attention = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
        try:
            section, html = self._render(lid)
        finally:
            lo_svc.needs_attention = original
        self.assertFalse(section["available"])
        self.assertEqual(section["items"], [])
        self.assertIn("暂时无法生成教材学习建议", html)
        self.assertIn("需要再学", html, "现有 Review 内容必须仍然正常")

    def test_11_official_db_untouched(self):
        self.assertEqual(hashlib.sha256(OFFICIAL_DB.read_bytes()).hexdigest().upper(),
                         OFFICIAL_SHA)


if __name__ == "__main__":
    unittest.main()
