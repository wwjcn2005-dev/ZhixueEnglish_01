#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P6-B-11b 验收：read（跟读练习 → 短句跟读）严格限定当前 Section

覆盖：
  T1 当前 Section = Unit 1 / DEVELOPING_IDEAS → 短句跟读只来自该 Section
     （不得出现 UNDERSTANDING_IDEAS / READING_FOR_WRITING）
  T2 当前 Section 无正式 Section 级跟读资源 → 空池，不 fallback 到 Unit 其他 Section
  T3 Unit 级词表分支不受 Section 过滤影响（read + word）
  T4 `shadowing_materials()` 原调用方行为不变（不传 section_key == 原结果）
  T5 practice / `learned_sections()` 未被本次改动触及（结构 + 行为）
  T6 read 的 GET / POST 使用同一套 Section 范围（`_p5_scope_items`）

全程**只读**：不写 learning.db / questionbank.db / contentpack，不建临时库，
不调用 AI / API。测试前后对比三个正式资产的 SHA256，必须完全一致。

运行：python D:\ZhixueEnglish\learning\test_p6b11b_read_section_scope.py
"""

from __future__ import annotations

import hashlib
import inspect
import sqlite3
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "web"))
sys.dont_write_bytecode = True

import study_call_service as scs          # noqa: E402
import content as content_mod             # noqa: E402  （web/content.py：只读教材读取）
import app as web_app                     # noqa: E402  （只用 Handler 的范围计算函数）

BASE = HERE.parent
LB_ORIG = BASE / "structured" / "learning" / "learning.db"
QB_ORIG = BASE / "structured" / "questionbank" / "questionbank.db"
CP_ORIG = BASE / "structured" / "contentpack" / "v5" / "FLTRP-EN-7A-2022CUR.sqlite"

#: P6-B-11b 之前（P8-Read-B 冻结）各 Unit 的整 Unit 跟读句池规模，用于确认向后兼容
BASELINE_UNIT_POOL = {"Starter": 23, "Unit 1": 29, "Unit 2": 8, "Unit 3": 34,
                      "Unit 4": 7, "Unit 5": 19, "Unit 6": 24}


def _sha(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class _ReadStub:
    """只借用 `web.app.Handler` 的范围计算函数（不启动服务、不写任何库）。"""

    contentpack_path = str(CP_ORIG)
    _p5_items = web_app.Handler._p5_items
    _p5_scope_items = web_app.Handler._p5_scope_items
    _p5_word_items = web_app.Handler._p5_word_items
    _lesson_rows = web_app.Handler._lesson_rows
    _lessons_for = web_app.Handler._lessons_for

    def __init__(self, path):
        self.path = path

    def _set_cookie(self, *args, **kwargs):   # 范围计算不需要真 Cookie
        pass


class ReadSectionScopeTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.sha_lb = _sha(LB_ORIG)
        cls.sha_qb = _sha(QB_ORIG)
        cls.sha_cp = _sha(CP_ORIG)
        cls.unit1 = content_mod.get_unit("unit1", str(CP_ORIG))
        cls.slug_of = {u["unit_code"]: u["slug"]
                       for u in content_mod.list_units(str(CP_ORIG))}
        cls.sections = {}                     # unit_code -> [section_key]（教材页顺序）
        cp = scs.connect_contentpack(str(CP_ORIG))
        try:
            cls.index = scs.section_index(cp)
            for r in cp.execute("SELECT u.unit_code, s.section_key FROM section s "
                                "JOIN unit u ON u.unit_id = s.unit_id "
                                "ORDER BY u.pdf_page_start, s.pdf_page_start"):
                cls.sections.setdefault(r["unit_code"], []).append(r["section_key"])
        finally:
            cp.close()
        # 整 Unit 句池（不传 section_key = 原行为）
        cls.base = {u: scs.shadowing_materials(u) for u in scs.UNIT_ORDER}
        cls.qb = sqlite3.connect("file:%s?mode=ro" % QB_ORIG.as_posix(), uri=True)
        cls.qb.row_factory = sqlite3.Row
        # 资源池条目：resource_id -> (unit_code, section_key)
        cls.pool_section = {}
        for e in scs.shadowing_pool_entries():
            cls.pool_section[e["resource_id"]] = scs.locate_section(
                cls.index["blocks"].get(e.get("content_block")), cls.index)

    @classmethod
    def tearDownClass(cls):
        cls.qb.close()
        assert _sha(LB_ORIG) == cls.sha_lb, "正式 learning.db 被修改"
        assert _sha(QB_ORIG) == cls.sha_qb, "正式 questionbank.db 被修改"
        assert _sha(CP_ORIG) == cls.sha_cp, "正式 contentpack 被修改"

    # ---------------- 工具 ----------------
    def _section_of(self, item):
        """跟读条目 → (unit_code, section_key)；无法定位返回 None（不猜测）。"""
        qid = item["question_id"]
        if qid.startswith("SHP:"):
            return self.pool_section.get(qid)
        row = self.qb.execute("SELECT unit_code, section_key FROM question WHERE question_id=?",
                              (qid,)).fetchone()
        if not row or not row["section_key"]:
            return None
        return (row["unit_code"], row["section_key"])

    def _read_sentences(self, unit, section_key, unit_slug="unit1"):
        stub = _ReadStub("/unit/%s/p5/read?mode=sentences&lesson=%s" % (unit_slug, section_key))
        return stub._p5_items(unit, "read", None, mode="sentences", lesson_key=section_key)

    # ---------------- T1 当前 Section ----------------
    def test_T1_read_sentences_only_current_section(self):
        items = self._read_sentences(self.unit1, "DEVELOPING_IDEAS")
        self.assertTrue(items, "Unit 1 / DEVELOPING_IDEAS 应有正式短句跟读资源")
        got = {self._section_of(i) for i in items}
        self.assertEqual(got, {("Unit 1", "DEVELOPING_IDEAS")},
                         "短句跟读只能来自当前 Section，实际：%s" % (sorted(map(str, got)),))
        self.assertNotIn("UNDERSTANDING_IDEAS",
                         {s for _, s in got if s}, "不得出现 UNDERSTANDING_IDEAS")
        self.assertNotIn("READING_FOR_WRITING",
                         {s for _, s in got if s}, "不得出现 READING_FOR_WRITING")
        # 与"整 Unit 池按 Section 切分"完全一致（且确有收窄）
        self.assertLess(len(items), len(self.base["Unit 1"]), "必须真的按 Section 收窄")

    # ---------------- T1b 各 Unit 的 Section 池 = 整 Unit 池的切分 ----------------
    def test_T1b_section_pools_partition_unit_pool(self):
        for unit_code in scs.UNIT_ORDER:
            base_ids = [i["question_id"] for i in self.base[unit_code]]
            self.assertEqual(len(base_ids), BASELINE_UNIT_POOL[unit_code],
                             "%s 整 Unit 句池规模被改变" % unit_code)
            seen = []
            stub = _ReadStub("/unit/unit1/p5/read?mode=sentences")
            unit = content_mod.get_unit(self.slug_of[unit_code], str(CP_ORIG))
            for section in self.sections.get(unit_code, []):
                ids = [i["question_id"] for i in stub._p5_items(
                    unit, "read", None, mode="sentences", lesson_key=section)]
                self.assertEqual(len(set(ids)), len(ids), "同一 Section 内重复供给：%s" % section)
                for i in ids:
                    self.assertEqual(self._section_of({"question_id": i}),
                                     (unit_code, section), "%s 串到其他 Section" % i)
                seen += ids
            self.assertEqual(sorted(seen), sorted(base_ids),
                             "%s 各 Section 池必须正好是整 Unit 池的切分（不多不少）" % unit_code)

    # ---------------- T2 当前 Section 无资源 → 空池 ----------------
    def test_T2_empty_section_pool_no_fallback(self):
        items = self._read_sentences(self.unit1, "STARTING_OUT")
        self.assertEqual(items, [], "无 Section 级跟读资源时必须为空，不得 fallback 到整个 Unit")
        # 明确不是"整 Unit 池"
        self.assertNotEqual([i["question_id"] for i in items],
                            [i["question_id"] for i in self.base["Unit 1"]])
        # 取一个真实存在的空 Section 逐一确认（不引入新规则，只读验证现状）
        empties = [s for s in self.sections["Unit 1"]
                   if not self._read_sentences(self.unit1, s) and s != "STARTING_OUT"]
        self.assertTrue(empties, "Unit 1 应有多个无短句跟读资源的 Section")

    # ---------------- T3 Unit 级词表不受 Section 过滤 ----------------
    def test_T3_unit_vocabulary_not_section_filtered(self):
        stub = _ReadStub("/unit/unit1/p5/read?mode=word")
        expect = stub._p5_word_items(self.unit1)
        self.assertTrue(expect, "Unit 1 应有正式 Unit 级词表")
        for lesson in ("DEVELOPING_IDEAS", "STARTING_OUT", ""):
            for mode in ("word", ""):
                got = stub._p5_items(self.unit1, "read", None, mode=mode, lesson_key=lesson)
                self.assertEqual([i["question_id"] for i in got],
                                 [i["question_id"] for i in expect],
                                 "read + %r 词表分支不得被 Section 过滤（lesson=%r）" % (mode, lesson))

    # ---------------- T4 shadowing_materials() 原调用方行为不变 ----------------
    def test_T4_original_callers_unchanged(self):
        for unit_code in scs.UNIT_ORDER:
            self.assertEqual(scs.shadowing_materials(unit_code), self.base[unit_code])
            # 原调用方只传 questionbank_path / shadowing_pool_path（位置或关键字）也不受影响
            self.assertEqual(
                scs.shadowing_materials(unit_code, None, QB_ORIG, scs.DEFAULT_SHADOWING_POOL),
                self.base[unit_code], "位置参数签名必须向后兼容")
        from_unit3 = [m for m in self.base["Unit 3"] if m.get("source") == "shadowing_pool"]
        self.assertEqual(len(from_unit3), 1, "P8-Read-B 新增供给必须仍然只有 1 条")
        # 不传 section_key 时结果与传 section_key=None 完全一致
        self.assertEqual(scs.shadowing_materials("Unit 1", section_key=None),
                         self.base["Unit 1"])

    # ---------------- T5 practice / learned_sections 未被触及 ----------------
    def test_T5_practice_and_learned_sections_untouched(self):
        src = inspect.getsource(web_app.Handler._p5_items)
        read_block = src.split("else:", 1)[0]          # read 分支代码
        self.assertNotIn("learned_sections", read_block, "read 不得使用 learned_sections")
        self.assertIn("section_key=lesson_key or None", src, "read 必须传入当前 Section")
        self.assertIn('elif entry != "read" and lesson_key:', src,
                      "不得删除 read 的通用 Section 过滤豁免")
        # practice 分支仍只用 learned_sections（未被本次改动改写）
        self.assertIn("scs.learned_sections(", src)
        # P6-B-9：Section 级进度算法本体未被改动
        svc_src = (HERE / "study_call_service.py").read_text(encoding="utf-8")
        self.assertIn("def learned_sections(learner_id", svc_src)
        self.assertIn("def item_teaching_sections(item_id", svc_src)

    # ---------------- T6 GET / POST 同一 Section 范围 ----------------
    def test_T6_get_and_post_share_read_scope(self):
        stub = _ReadStub("/unit/unit1/p5/read?mode=sentences&lesson=DEVELOPING_IDEAS")
        get_ids = [i["question_id"] for i in stub._p5_scope_items(
            self.unit1, "read", None, "sentences", "")]
        post_ids = [i["question_id"] for i in stub._p5_scope_items(
            self.unit1, "read", None, "sentences", "")]
        self.assertEqual(get_ids, post_ids, "read GET / POST 必须使用同一 Section 范围")
        self.assertEqual(get_ids, [i["question_id"]
                                   for i in self._read_sentences(self.unit1, "DEVELOPING_IDEAS")])
        self.assertTrue(get_ids)
        self.assertLess(len(get_ids), len(self.base["Unit 1"]))
        src = (HERE.parent / "web" / "app.py").read_text(encoding="utf-8")
        self.assertEqual(src.count("self._p5_scope_items("), 2,
                         "read 的 GET / POST 必须共用 _p5_scope_items")
if __name__ == "__main__":
    unittest.main(verbosity=2)
