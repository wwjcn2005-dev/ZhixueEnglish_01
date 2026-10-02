"""P1-08-B · 教材证据组装层机制测试（只读）。

覆盖任务要求的 Test A–E 与 Case 1–5。不修改任何数据库或 fixture。
"""
import json
import os
import sqlite3
import sys
import unittest
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import evidence_assembly as EA  # noqa: E402

BASE = r"D:\ZhixueEnglish"
CP = os.path.join(BASE, "structured", "contentpack", "v5", "FLTRP-EN-7A-2022CUR.sqlite")
RUNS = os.path.join(BASE, "audit", "AI_question_generation_spike",
                    "P1_05_real_validation", "runs")

U1_UI = "FLTRP-EN-7A-2022CUR:U1:UNDERSTANDING_IDEAS"
P22 = "FLTRP-EN-7A-2022CUR:P22"
LESSON_UNITS = ("FLTRP-EN-7A-2022CUR:STARTER", "FLTRP-EN-7A-2022CUR:U1",
                "FLTRP-EN-7A-2022CUR:U2", "FLTRP-EN-7A-2022CUR:U3",
                "FLTRP-EN-7A-2022CUR:U4", "FLTRP-EN-7A-2022CUR:U5",
                "FLTRP-EN-7A-2022CUR:U6")


def connect():
    c = sqlite3.connect("file:" + CP + "?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


class EvidenceAssemblyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = connect()
        cls.ranges = EA.section_page_ranges(cls.conn)
        cls.old = EA.blocks_by_activity_only(cls.conn)
        cls.lesson_sections = [s for s in cls.ranges
                               if s.rsplit(":", 1)[0] in LESSON_UNITS]

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    # ---------------------------------------------------------------- Case 1 / Test A
    def test_A_case1_page_has_text_but_no_activity(self):
        """Unit 1 教材第17页 / PDF22：有正文、无 Activity，修复后必须进入 U1 UI 证据。"""
        acts = EA.activities_of_section(self.conn, U1_UI)
        self.assertFalse([a for a in acts if a["pdf_page"] == 22],
                         "该页本应没有 Activity（前提不变）")
        pages = EA.pages_of_section(self.conn, U1_UI)
        self.assertIn(22, pages, "修复后该页必须进入 Section 页码范围")
        ev = EA.build_section_evidence(self.conn, U1_UI)
        ids = [b["block_id"] for b in ev["blocks"]]
        p22_ids = [i for i in ids if i.startswith(P22 + ":")]
        self.assertEqual(len(p22_ids), 10, "该页 10 个非页脚 block 必须全部进入证据")
        # 关键 block（课文主体）
        for bid in (P22 + ":B2", P22 + ":B6", P22 + ":B9"):
            self.assertIn(bid, ids)
        # 旧逻辑必须确实丢过（证明这是真缺陷而不是新问题）
        old_ids = {b["block_id"] for b in self.old.get(U1_UI, [])}
        self.assertFalse([i for i in p22_ids if i in old_ids],
                         "旧逻辑确实没有这些 block（缺陷复现）")
        self.assertEqual(ev["stats"]["blocks"], ev["stats"]["blocks_unique"],
                         "不得出现重复 block")

    # ---------------------------------------------------------------- Test B / Case 2
    def test_B_page_has_activity_and_text_unchanged(self):
        """有 Activity 的正常页面：原有**非空正文**证据不得被破坏。

        唯一允许的行为差异：旧逻辑把纯空白 block（text 仅含空白字符）也纳入，
        新逻辑过滤了这类无证据价值的 block —— 该差异必须全部属于纯空白 block。
        """
        broken = []
        dropped_empty = []
        for sid in self.lesson_sections:
            new_ids = {b["block_id"] for b in EA.blocks_of_section(self.conn, sid)}
            for b in self.old.get(sid, []):
                if b["block_id"] in new_ids:
                    continue
                if (b.get("text_raw") or "").strip() == "":
                    dropped_empty.append(b["block_id"])
                else:
                    broken.append((sid, b["block_id"], (b.get("text_raw") or "")[:30]))
        self.assertEqual(broken, [], "存在原有证据被破坏的 Section：%s" % broken)
        # 记录（不失败）：被过滤的纯空白 block 数量
        EvidenceAssemblyTests.dropped_empty_blocks = dropped_empty

    # ---------------------------------------------------------------- Test C
    def test_C_same_block_not_duplicated(self):
        """同一 section 内 block 不重复；且每个 block 只归属一个 Section。"""
        for sid in self.ranges:
            bl = EA.blocks_of_section(self.conn, sid)
            ids = [b["block_id"] for b in bl]
            self.assertEqual(len(ids), len(set(ids)), "%s 内 block 重复" % sid)
        owner = defaultdict(set)
        for sid in self.ranges:
            for b in EA.blocks_of_section(self.conn, sid):
                owner[b["block_id"]].add(sid)
        multi = {k: sorted(v) for k, v in owner.items() if len(v) > 1}
        self.assertEqual(multi, {}, "存在被多个 Section 同时归属的 block：%s" % list(multi)[:3])

    # ---------------------------------------------------------------- Test D / Case 3
    def test_D_multi_page_section_order_preserved(self):
        """多页 Section：顺序按 (pdf_page, reading_order) 单调。"""
        for sid in self.lesson_sections:
            bl = EA.blocks_of_section(self.conn, sid)
            keys = [(b["pdf_page"], b["reading_order"] or 0) for b in bl]
            self.assertEqual(keys, sorted(keys), "%s 顺序不正确" % sid)
            pages = sorted({b["pdf_page"] for b in bl})
            self.assertEqual(pages, sorted(set(pages)), "%s 页集合异常" % sid)

    # ---------------------------------------------------------------- Test E / Case 4
    def test_E_activity_evidence_not_duplicated_by_page_text(self):
        """Activity 原有证据不因页面正文补充而重复。"""
        for sid in self.lesson_sections:
            ev = EA.build_section_evidence(self.conn, sid)
            act_pages = {a["pdf_page"] for a in ev["activities"] if a["pdf_page"]}
            bl = ev["blocks"]
            ids = [b["block_id"] for b in bl]
            self.assertEqual(len(ids), len(set(ids)), "%s block 重复（含 activity 页）" % sid)
            # activity 页上的 block 只出现一次
            on_act = [b["block_id"] for b in bl if b["pdf_page"] in act_pages]
            self.assertEqual(len(on_act), len(set(on_act)),
                             "%s activity 页 block 被重复拼接" % sid)

    # ---------------------------------------------------------------- Case 5
    def test_case5_p1_06_fixture_regression(self):
        """P1-06 fixture：新证据必须是其超集，且 fixture 的 evidence block 全部存在。"""
        files = {"S1": "01_Unit2_UNDERSTANDING_IDEAS_context.json",
                 "S2": "03_Unit1_UNDERSTANDING_IDEAS_context.json",
                 "S3": "04_Unit5_UNDERSTANDING_IDEAS_context.json",
                 "S4": "05_Starter_GET_READY_context.json"}
        parsed = {"S1": "S1_parsed.json", "S2": "S2_parsed.json",
                  "S3": "S3_parsed.json", "S4": "S4_parsed.json"}
        d6 = os.path.join(BASE, "audit", "AI_question_generation_spike",
                          "P1_06_batch_stability")
        for tag, f in files.items():
            with open(os.path.join(RUNS, f), encoding="utf-8") as fh:
                ctx = json.load(fh)
            sid = ctx["textbook_position"]["section_id"]
            new_ids = {b["block_id"] for b in EA.blocks_of_section(self.conn, sid)}
            old_ids = {b["block_id"] for b in ctx["textbook_blocks"]}
            self.assertTrue(old_ids <= new_ids,
                            "%s：fixture 中的 block 在新证据里缺失" % tag)
            with open(os.path.join(d6, parsed[tag]), encoding="utf-8") as fh:
                qs = json.load(fh)["questions"]
            for q in qs:
                for bid in q.get("evidence_block_ids") or []:
                    self.assertIn(bid, new_ids, "%s 的 evidence block 不在新证据中" % tag)


if __name__ == "__main__":
    unittest.main(verbosity=2)
