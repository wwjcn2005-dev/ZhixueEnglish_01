#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P6-B-12-FIX 验收：学习入口按【当前 Section 的实际可调用资源】统一显隐

依据：V1.3 第二十九章 §15（+ 2026-09-27 补充）/ V2.0 §5.1·§5.3 / AGENTS §10

覆盖：
  A 有资源 Section：对应入口显示（文案为"候选资源数"口径）
  B 无资源：入口隐藏（纯函数空池 + Appendix 首页 0 入口）
  C 目录与选择器完整保留（8 组 / 46 Section，含零资源 Section 与 Appendix）
  D 主页入口数字与次页实际资源池一致（同一 learner / Section / 模式）
  E Appendix 显式处理：不调用教学 Unit 专属池、不依赖异常被吞掉
  F 直接进入无资源功能页：真实空状态，且不出现"换个章节看看"类误导文案
  G 不静默切换 Section（Cookie 与页面内容都停在请求的 Section）
  H 既有规则不回退（旧 Unit 宿主 404；/text 仍 VERIFIED-only）

只读：测试只用 %TEMP% 下的 learning.db 副本；正式资产前后校验 SHA256。AI 调用 0。
运行：python D:\ZhixueEnglish\web\test_p6b12fix_entry_visibility.py
"""

from __future__ import annotations

import hashlib
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

import app as web_app                     # noqa: E402
import content as content_mod             # noqa: E402
import demo_data as demo                  # noqa: E402
import ui                                 # noqa: E402

BASE = HERE.parent
QUESTIONBANK = BASE / "structured" / "questionbank" / "questionbank.db"

UNIT1 = "unit1"
SEC_WITH = "UNDERSTANDING_IDEAS"          # 有 Section 级资源的 Section
SEC_WITHOUT = "PRESENTING_IDEAS"          # 零题 / 无 Section 级资源的 Section
APPENDIX_SEC = "COMMUNICATION_BANK"
EMPTY_LINE = ui.P5_EMPTY_LINE
MISLEADING = "换个章节看看"
ENTRY_KEYS = ("read", "listen", "phonetic", "form", "check", "practice")


def _sha(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class EntryVisibilityTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.assets = {name: _sha(p) for name, p in (
            ("learning.db", content_mod.LEARNING_DB),
            ("questionbank.db", QUESTIONBANK),
            ("contentpack", content_mod.CONTENTPACK))}
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="zhixue_p6b12fix_"))
        cls.tmp_db = cls.tmpdir / "learning.db"
        shutil.copyfile(content_mod.LEARNING_DB, cls.tmp_db)
        web_app.Handler.learning_db = cls.tmp_db
        web_app.Handler.contentpack_path = content_mod.CONTENTPACK
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), web_app.Handler)
        cls.port = cls.srv.server_address[1]
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()
        import sqlite3
        conn = sqlite3.connect("file:%s?mode=ro" % content_mod.LEARNING_DB.as_posix(), uri=True)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT learner_id FROM learner LIMIT 1").fetchone()
        conn.close()
        cls.learner = row["learner_id"] if row else None

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.thread.join(timeout=5)
        shutil.rmtree(cls.tmpdir, ignore_errors=True)
        for name, p in (("learning.db", content_mod.LEARNING_DB),
                        ("questionbank.db", QUESTIONBANK),
                        ("contentpack", content_mod.CONTENTPACK)):
            assert _sha(p) == cls.assets[name], "%s 被修改" % name

    # ---------- 工具 ----------
    def _get(self, path, cookie=True):
        req = urllib.request.Request("http://127.0.0.1:%d%s" % (self.port, path))
        if cookie and self.learner:
            req.add_header("Cookie", "zx_learner=%s" % self.learner)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, r.read().decode("utf-8", "replace"), dict(r.headers)
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8", "replace"), dict(exc.headers)

    def _handler(self):
        h = web_app.Handler.__new__(web_app.Handler)
        h.contentpack_path = content_mod.CONTENTPACK
        h.learning_db = str(self.tmp_db)
        h.headers = {}
        return h

    @staticmethod
    def _entries(body):
        return re.findall(r'<span class="nm">([^<]*)</span><span class="st">([^<]*)</span>', body)

    def _pool_total(self, slug, entry, section_key):
        h = self._handler()
        unit = content_mod.get_unit(slug, h.contentpack_path)
        modes = {"read": tuple(m for m, _ in ui._P5_READ_MODES),
                 "listen": tuple(m for m, _ in ui._P5_LISTEN_MODES)}.get(entry, ("",))
        return sum(len(h._p5_items(unit, entry, self.learner, mode=m, lesson_key=section_key))
                   for m in modes)

    # ---------- A 有资源 Section：入口显示 ----------
    def test_A_entries_visible_and_section_scoped_number(self):
        status, body, _ = self._get("/?unit=%s&lesson=%s" % (UNIT1, SEC_WITH))
        self.assertEqual(status, 200)
        rows = self._entries(body)
        self.assertEqual(len(rows), 6, "有资源的 Section 应显示六个入口")
        labels = [label for label, _ in rows]
        self.assertEqual(labels, [label for _, label, _, _ in demo.ENTRY_ORDER_FORMAL])
        for _label, st_text in rows:
            self.assertTrue(st_text.startswith("候选"), "文案必须是候选资源数口径：%s" % st_text)
            self.assertNotIn("已完成", st_text)
            self.assertNotIn("需要巩固", st_text)

    # ---------- B 无资源：入口隐藏 ----------
    def test_B_no_resource_means_hidden(self):
        # 纯函数：池为空 → 不产生任何入口
        self.assertEqual(demo.formal_entries("Unit 1", UNIT1, self.learner,
                                             pool=lambda key, mode: []), [])
        # Appendix：首页 0 入口（不是异常，而是显式判定）
        status, body, _ = self._get("/?unit=appendix&lesson=%s" % APPENDIX_SEC)
        self.assertEqual(status, 200)
        self.assertEqual(self._entries(body), [])

    # ---------- C 目录与选择器完整 ----------
    def test_C_catalog_and_picker_keep_all_sections(self):
        for path in ("/?unit=%s&lesson=%s" % (UNIT1, SEC_WITHOUT),
                     "/?unit=%s&lesson=%s" % (UNIT1, SEC_WITH),
                     "/?unit=appendix&lesson=%s" % APPENDIX_SEC):
            status, body, _ = self._get(path)
            self.assertEqual(status, 200, path)
            blk = re.search(r'<section class="softcard unitcard">.*?</section>', body, re.S)
            blk = blk.group(0) if blk else ""
            self.assertEqual(len(re.findall(r"<optgroup", blk)), 8, path)
            self.assertEqual(len(re.findall(r"<option", blk)), 46, path)
            keys = re.findall(r'<option value="([^"]*)"', blk)
            self.assertIn("PRESENTING_IDEAS", keys, path)
            self.assertIn("REFLECTION", keys, path)
            self.assertIn(APPENDIX_SEC, keys, path)

    # ---------- D 主页数字 与 次页资源池一致 ----------
    def test_D_home_numbers_match_page_pools(self):
        for section in (SEC_WITH, SEC_WITHOUT):
            status, body, _ = self._get("/?unit=%s&lesson=%s" % (UNIT1, section))
            self.assertEqual(status, 200)
            shown = dict(self._entries(body))
            for key, label, _cls, _ico in demo.ENTRY_ORDER_FORMAL:
                total = self._pool_total(UNIT1, key, section)
                self.assertIn(label, shown, "%s 有资源时应显示入口" % label)
                self.assertEqual(shown[label], demo.entry_status_text(key, total),
                                 "%s 在 %s 的文案必须等于该 Section 的实际资源池口径" % (label, section))
        # 同一 Unit 的不同 Section，Section 级资源不同 → 数字必须不同（不再用 Unit 总量代替）
        _s, body_with, _ = self._get("/?unit=%s&lesson=%s" % (UNIT1, SEC_WITH))
        _s, body_without, _ = self._get("/?unit=%s&lesson=%s" % (UNIT1, SEC_WITHOUT))
        self.assertNotEqual(dict(self._entries(body_with))["本课检测"],
                            dict(self._entries(body_without))["本课检测"],
                            "本课检测的候选数必须随当前 Section 变化")

    # ---------- E Appendix 显式处理 ----------
    def test_E_appendix_is_explicit_not_exception_swallowed(self):
        def boom(key, mode):
            raise AssertionError("Appendix 不得调用教学 Unit 专属资源池")
        self.assertEqual(demo.formal_entries("Appendix", "appendix", self.learner, pool=boom), [],
                         "Appendix 应显式不进入六入口，且不调用教学 Unit 池")
        h = self._handler()
        unit = content_mod.get_unit("appendix", h.contentpack_path)
        for entry in ENTRY_KEYS:
            self.assertEqual(h._p5_items(unit, entry, self.learner, lesson_key=APPENDIX_SEC), [],
                             "Appendix 的 %s 池应为显式空池（不抛错）" % entry)

    # ---------- F 直接进入无资源页 → 真实空状态 ----------
    def test_F_direct_entry_shows_real_empty_state(self):
        paths = ["/unit/%s/p5/read?lesson=%s&mode=sentences" % (UNIT1, SEC_WITHOUT),
                 "/unit/%s/p5/listen?lesson=%s&mode=sentence" % (UNIT1, SEC_WITHOUT)]
        paths += ["/unit/appendix/p5/%s?lesson=%s" % (e, APPENDIX_SEC) for e in ENTRY_KEYS]
        for path in paths:
            status, body, _ = self._get(path)
            self.assertEqual(status, 200, path)
            self.assertIn(EMPTY_LINE, body, path)
            self.assertNotIn(MISLEADING, body, "不得出现误导文案：%s" % path)

    # ---------- G 不静默切换 Section ----------
    def test_G_no_silent_section_switch(self):
        status, body, headers = self._get("/unit/appendix/p5/read?lesson=%s" % APPENDIX_SEC)
        self.assertEqual(status, 200)
        self.assertIn("zx_lesson=%s;" % APPENDIX_SEC, headers.get("Set-Cookie") or "",
                      "Cookie 必须停在请求的 Section")
        for other in ("STARTING_OUT", "UNDERSTANDING_IDEAS"):
            self.assertNotIn("zx_lesson=%s" % other, headers.get("Set-Cookie") or "")
            self.assertNotIn(other, body, "不得出现其它 Section 的内容：%s" % other)

    # ---------- H 既有规则不回退 ----------
    def test_H_existing_rules_not_regressed(self):
        status, _body, _hd = self._get("/unit/unit1")
        self.assertEqual(status, 404, "旧 Unit 菜单宿主必须保持 404")
        status, text_page, _hd = self._get("/unit/%s/text" % UNIT1)
        self.assertEqual(status, 200)
        self.assertNotIn("The first lesson", text_page, "教材正文仍按 VERIFIED-only 过滤")


if __name__ == "__main__":
    unittest.main(verbosity=2)
