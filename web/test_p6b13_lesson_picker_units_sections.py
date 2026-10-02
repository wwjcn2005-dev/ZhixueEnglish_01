#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P6-B-13 验收：首页「当前课时」= Unit → Section（同一个下拉，全部真实 Section）

覆盖：
  A 教材目录聚合：8 个块 / 46 个真实 Section；Unit 1–6 含 PRESENTING_IDEAS；Appendix 含 6 个
  B 首页 picker：Unit 分组（optgroup / .lpgroup）+ 全部真实 Section，Section 值仍是 section_key
  C 跨 Unit 选择：`?unit=<slug>&lesson=<section_key>` → 选中项 / 隐藏 unit / Cookie zx_lesson 正确
  D 暂无正式题的 Section（Presenting ideas、Appendix 6 个）不再被错误回退
  E 首页六个入口顺序不变；正式资产零写入

只读：不写 learning.db / questionbank.db / contentpack；AI 调用 0。
运行：python D:\ZhixueEnglish\web\test_p6b13_lesson_picker_units_sections.py
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
EXPECT_SECTIONS = {"Starter": 4, "Unit 1": 6, "Unit 2": 6, "Unit 3": 6,
                   "Unit 4": 6, "Unit 5": 6, "Unit 6": 6, "Appendix": 6}
APPENDIX_KEYS = ("COMMUNICATION_BANK", "GUIDE_TO_THE_LANGUAGE_USE", "WORDS_AND_EXPRESSIONS",
                 "PROPER_NOUNS", "VOCABULARY", "PRONUNCIATION_GUIDE")


def _sha(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class LessonPickerTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.assets = {name: _sha(p) for name, p in (
            ("learning.db", content_mod.LEARNING_DB),
            ("questionbank.db", BASE / "structured" / "questionbank" / "questionbank.db"),
            ("contentpack", content_mod.CONTENTPACK))}
        cls.catalog = content_mod.list_units_with_sections(str(content_mod.CONTENTPACK))
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
        """GET → (status, body, headers)；404 不抛异常。"""
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d%s" % (self.port, path),
                                        timeout=30) as r:
                return r.status, r.read().decode("utf-8", "replace"), r.headers
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8", "replace"), exc.headers

    @staticmethod
    def _picker(body: str) -> str:
        m = re.search(r'<section class="softcard unitcard">.*?</section>', body, re.S)
        return m.group(0) if m else ""

    # ---------------- A 教材目录聚合 ----------------
    def test_A_catalog_covers_all_real_sections(self):
        self.assertEqual(len(self.catalog), 8)
        got = {u["unit_code"]: len(u["sections"]) for u in self.catalog}
        self.assertEqual(got, EXPECT_SECTIONS, "必须列出全部真实 Section（不做题库过滤）")
        self.assertEqual(sum(got.values()), 46)
        by_code = {u["unit_code"]: [s["section_key"] for s in u["sections"]] for u in self.catalog}
        for unit in ("Unit 1", "Unit 2", "Unit 3", "Unit 4", "Unit 5", "Unit 6"):
            self.assertIn("PRESENTING_IDEAS", by_code[unit], "%s 必须包含 Presenting ideas" % unit)
        self.assertEqual(tuple(by_code["Appendix"]), APPENDIX_KEYS)

    # ---------------- B 首页 picker = 一个下拉 + Unit 分组 ----------------
    def test_B_home_picker_is_one_dropdown_with_unit_groups(self):
        status, body, _ = self._get("/?unit=unit1")
        self.assertEqual(status, 200)
        self.assertEqual(len(re.findall(r'<form method="get" action="/" class="picker">', body)), 1,
                         "首页只能有一个课时下拉")
        blk = self._picker(body)
        groups = re.findall(r'<optgroup label="([^"]*)"', blk)
        self.assertEqual(len(groups), 8, "Unit 必须是分组标题（8 个块）")
        keys = re.findall(r'<option value="([^"]*)"', blk)
        self.assertEqual(len(keys), 46, "全部真实 Section 都必须可选")
        self.assertIn("PRESENTING_IDEAS", keys)
        for k in APPENDIX_KEYS:
            self.assertIn(k, keys, "Appendix 的 %s 必须可选" % k)
        # 可见列表里 Unit 分组行不可点击（div.lpgroup，而非 .lpopt）
        self.assertEqual(len(re.findall(r'<div class="lpgroup">', blk)), 8)
        # 每个可选项都携带 unit_slug 与 section_key（跨 Unit 选择用）
        self.assertEqual(len(re.findall(r'class="lpopt" type="button" data-value="[^"]+" data-unit="[^"]+"', blk)), 46)

    # ---------------- C 跨 Unit 选择 ----------------
    def test_C_cross_unit_selection(self):
        cases = (("/?unit=appendix&lesson=VOCABULARY", "appendix", "VOCABULARY", "Appendix · Vocabulary"),
                 ("/?unit=unit2&lesson=DEVELOPING_IDEAS", "unit2", "DEVELOPING_IDEAS",
                  "Unit 2 · Developing ideas"),
                 ("/?unit=unit1&lesson=PRESENTING_IDEAS", "unit1", "PRESENTING_IDEAS",
                  "Unit 1 · Presenting ideas"))
        for path, slug, key, label in cases:
            status, body, headers = self._get(path)
            self.assertEqual(status, 200, path)
            blk = self._picker(body)
            self.assertRegex(blk, r'<option value="%s" selected>' % key, path)
            self.assertIn('<input type="hidden" name="unit" value="%s">' % slug, blk, path)
            self.assertIn(label, re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", blk)))
            self.assertIn("zx_lesson=%s;" % key, headers.get("Set-Cookie") or "", path)

    # ---------------- D 无题 Section 不再被错误回退 ----------------
    def test_D_no_question_section_is_not_replaced(self):
        for path, key in (("/unit/unit1/p5/check?lesson=PRESENTING_IDEAS", "PRESENTING_IDEAS"),
                          ("/unit/unit1/p5/check?lesson=REFLECTION", "REFLECTION"),
                          ("/unit/appendix/p5/check?lesson=PRONUNCIATION_GUIDE",
                           "PRONUNCIATION_GUIDE")):
            status, body, headers = self._get(path)
            self.assertEqual(status, 200, path)
            self.assertIn("zx_lesson=%s;" % key, headers.get("Set-Cookie") or "",
                          "%s 必须被解析为 %s（不得回退到其它 Section）" % (path, key))

    # ---------------- E 六入口不变 + 资产零写入 ----------------
    def test_E_six_entries_and_assets_unchanged(self):
        status, body, _ = self._get("/")
        self.assertEqual(status, 200)
        rows = re.findall(r'<a class="entryrow [^"]*" href="([^"]*)"><span class="ico">.*?'
                          r'<span class="nm">([^<]*)</span>', body, re.S)
        self.assertEqual([label for _, label in rows], list(ENTRY_LABELS))
        for name, p in (("learning.db", content_mod.LEARNING_DB),
                        ("questionbank.db", BASE / "structured" / "questionbank" / "questionbank.db"),
                        ("contentpack", content_mod.CONTENTPACK)):
            self.assertEqual(_sha(p), self.assets[name], "%s 被写入" % name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
