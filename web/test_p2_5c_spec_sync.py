#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-5-C 规范同步校验：V1.2 是否完整、正确地吸收了 P2-5 已确认原则。

对应任务书 §十六 的 12 项检查（2–12 项在此自动校验；第 1 项为人工版本对比，见报告）。
只读：不修改任何文档、数据与代码。
"""

from __future__ import annotations

import hashlib
import re
import sys
import unittest
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True

import content as content_mod            # noqa: E402

BASE = HERE.parent
DOC_V10 = BASE / "初中英语AI辅助学习系统_最高指导原则与开发规范_V1.0.docx"
DOC_V11 = BASE / "初中英语AI辅助学习系统_最高指导原则与开发规范_V1.1.docx"
DOC_V12 = BASE / "初中英语AI辅助学习系统_最高指导原则与开发规范_V1.2.docx"
MD_V11 = BASE / "docs" / "初中英语AI辅助学习系统最高指导原则与开发规范_V1.1.md"
MD_V12 = BASE / "docs" / "初中英语AI辅助学习系统最高指导原则与开发规范_V1.2.md"
P25_DESIGN = BASE / "audit" / "P2-5_learning_system_design.md"
ARCH_MD = BASE / "audit" / "P2-5_architecture_impact.md"

#: 已记录的基线哈希（P2-5-C 之前）：V1.0 与 V1.1 不得被改动
SHA_V10 = "68B3A18FCB6ACFA16D75FE624981F4084911FBA3FF57A61C9DE0D3078A73368C"
SHA_V11 = "D1919A4B0B11BCDD07677461B61295014A6B5BB667B3D7931B0FCD70544F51B7"
SHA_CONTENTPACK = "ACEBC8C29CF5D11BAB50BF7962FBEE5DE42CD9CFC7FE48AB6316699D265E1A3F"

CN_NUM = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二", "十三",
          "十四", "十五", "十六", "十七", "十八", "十九", "二十", "二十一", "二十二"]


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def docx_paragraphs(path) -> list:
    xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
    out = []
    for m in re.finditer(r"<w:p\b.*?</w:p>", xml, re.S):
        p = m.group(0)
        txt = " ".join(re.findall(r"<w:t(?:\s[^>]*)?>(.*?)</w:t>", p, re.S)).strip()
        st = re.search(r'<w:pStyle w:val="([^"]+)"/>', p)
        out.append((st.group(1) if st else "", txt))
    return xml, out


XML12, PARAS12 = docx_paragraphs(DOC_V12)
XML11, PARAS11 = docx_paragraphs(DOC_V11)
BODY12 = "".join(t for _, t in PARAS12)
MD12_TEXT = MD_V12.read_text(encoding="utf-8")


class VersionTest(unittest.TestCase):
    def test_01_v12_exists_and_parses(self):
        self.assertTrue(DOC_V12.is_file())
        self.assertIn("word/document.xml", zipfile.ZipFile(DOC_V12).namelist())
        self.assertTrue(MD_V12.is_file())
        self.assertIn("最高指导原则与开发规范 V1.2", BODY12)

    def test_02_previous_versions_preserved(self):
        self.assertEqual(sha256_file(DOC_V10), SHA_V10, "V1.0 不得被修改")
        self.assertEqual(sha256_file(DOC_V11), SHA_V11, "V1.1 不得被修改")
        self.assertTrue(MD_V11.is_file())

    def test_03_heading_numbering_continuous(self):
        h1 = [t for s, t in PARAS12 if s == "Heading1"]
        self.assertEqual(len(h1), 22)
        for t, c in zip(h1, CN_NUM):
            self.assertTrue(t.startswith(c + "、"), t)
        self.assertTrue(h1[-1].startswith("二十二、学习系统原则"))

    def test_04_v11_content_preserved(self):
        s12 = {t for _, t in PARAS12 if t}
        for _s, t in PARAS11:
            if not t:
                continue
            if "V1.1" in t and ("最高指导原则与开发规范 V1.1" in t or "从本文件 V1.1 起" in t):
                continue                      # 允许的版本号替换
            self.assertIn(t, s12, "V1.1 段落丢失：%s" % t[:50])


class PrincipleSyncTest(unittest.TestCase):
    """§十六 2：P2-5 核心决策是否全部进入正式规范。"""

    TOKENS = [
        "二十二、学习系统原则（P2-5 同步）",
        "自主权不等于取消结构",
        "推荐顺序，但不强制",
        "Activity 是任务容器，不等于学习对象",
        "是产生学习证据的任务，不等于学习对象",
        "至少主动发生过一次学习行为",
        "必须基于多维证据，而不是单次正确",
        "只看过不能单独证明掌握",
        "只听过不能单独证明掌握",
        "自评不能单独升级掌握状态",
        "同一学习时段内的重复操作不能无限增加独立证据权重",
        "一次错误不等于薄弱",
        "先回到教材，再考虑 AI 辅助",
        "巩固不是无限重复错题",
        "决定孩子学什么",
        "自动安排学习路径",
        "在证据不足时做确定性结论",
        "阶段验证不是考试产品",
        "教材主线下的辅助入口",
        "独立 AI 题库",
        "证据聚合",
        "孩子决定是否巩固",
        "返回教材或进入下一 Unit",
    ]

    def test_01_all_principles_present(self):
        missing = [t for t in self.TOKENS if t not in BODY12]
        self.assertEqual(missing, [], "缺少原则：%s" % missing)

    def test_02_child_ownership_definition(self):
        for token in ("孩子决定：学哪一部分", "系统负责：按教材结构组织内容",
                      "AI 负责：教材范围内的分析", "系统和 AI 都不得"):
            self.assertIn(token, BODY12)
        for forbidden in ("孩子完全自由", "没有任何结构", "孩子想学什么就学什么，系统不介入"):
            self.assertNotIn(forbidden, BODY12, "自主权被误写为完全无结构")

    def test_03_ai_boundary_not_expanded(self):
        for token in ("决定什么时候学", "自动推进学习", "生成教材范围之外的学习内容",
                      "用 AI 题替代教材原题", "用分数、排名、等级评价孩子"):
            self.assertIn(token, BODY12)
        self.assertNotIn("AI 自动安排", BODY12)
        self.assertNotIn("AI 决定学习路径", BODY12)

    def test_04_textbook_mainline_explicit(self):
        self.assertIn("教材是主线", BODY12)
        self.assertIn("教材是主线，APP 负责整理与提效，学习是核心，孩子做主，AI 是助手", BODY12)


class ParameterVsPrincipleTest(unittest.TestCase):
    """§十三 / §十六 3：不得把工程参数写成永久教育规则。"""

    def test_01_threshold_marked_adjustable(self):
        self.assertIn("属于当前工程初始参数，不是不可修改的教育真理", BODY12)
        self.assertIn("可验证、可调整", BODY12)

    def test_02_stage_item_count_marked_experimental(self):
        self.assertIn("5–8 题", BODY12)
        self.assertIn("只是当前实验性工程参数，不是永久固定规则", BODY12)

    def test_03_parameter_list_present(self):
        for token in ("掌握阈值具体数字", "阶段验证具体题数", "AI 错误类别最终数量",
                      "提醒频率", "巩固间隔", "某个具体数据库表结构", "某个具体 API 实现"):
            self.assertIn(token, BODY12)
        self.assertIn("原则应稳定，参数可以调整", BODY12)


class ConfusionCheckTest(unittest.TestCase):
    """§十六 8–12：常见混淆的否定式检查。"""

    def test_01_no_seen_equals_mastered(self):
        self.assertIn("不等于学会、掌握、熟练或掌握较稳定", BODY12)
        for bad in ("看过即掌握", "学过就是掌握", "看过等于学会"):
            self.assertNotIn(bad, BODY12)

    def test_02_no_single_correct_mastery(self):
        self.assertIn("而不是单次正确", BODY12)
        self.assertNotIn("做对一次即为掌握", BODY12)

    def test_03_no_single_error_weakness(self):
        self.assertIn("一次错误不等于薄弱", BODY12)
        self.assertNotIn("一次错误即为薄弱", BODY12)

    def test_04_stage_assessment_is_not_exam(self):
        self.assertIn("阶段验证不是考试产品", BODY12)
        for token in ("不做排名", "不做等级", "不以分数为核心", "不直接因为一次阶段验证结果修改掌握状态"):
            self.assertIn(token, BODY12)

    def test_05_special_learning_is_not_a_bank(self):
        self.assertIn("专项学习属于教材主线下的辅助入口，不是一级主线", BODY12)
        self.assertIn("明确拒绝：专项学习 = 独立 AI 题库", BODY12)


class ConsistencyWithP25Test(unittest.TestCase):
    def test_01_design_docs_referenced(self):
        self.assertIn("audit/P2-5_learning_system_design.md", BODY12)
        self.assertIn("audit/P2-5_architecture_impact.md", BODY12)
        self.assertIn("structured/learning/", BODY12)
        for name in ("learning_model_v1.json", "learning_evidence_model_v1.json",
                     "learning_flow_v1.json", "intervention_model_v1.json",
                     "stage_assessment_model_v1.json", "ai_role_model_v1.json"):
            self.assertIn(name, BODY12, "依据文档未列出：%s" % name)

    def test_02_markdown_archive_matches(self):
        self.assertIn("二十二、学习系统原则", MD12_TEXT)
        self.assertIn("参数可以调整", MD12_TEXT)
        self.assertIn("V1.2 基于 V1.1", MD12_TEXT)

    def test_03_no_business_or_data_change(self):
        self.assertEqual(sha256_file(content_mod.CONTENTPACK), SHA_CONTENTPACK,
                         "contentpack 不得被规范同步修改")
        self.assertTrue(P25_DESIGN.is_file())
        self.assertTrue(ARCH_MD.is_file())
        # P2-5 六份设计 JSON 必须仍在（P2-6-B 新增 mastery_rules_v1.json 属授权增量）
        names = {p.name for p in (BASE / "structured" / "learning").glob("*_v1.json")}
        for name in ("learning_model_v1.json", "learning_evidence_model_v1.json",
                     "learning_flow_v1.json", "intervention_model_v1.json",
                     "stage_assessment_model_v1.json", "ai_role_model_v1.json"):
            self.assertIn(name, names, "P2-5 设计 JSON 缺失：%s" % name)


if __name__ == "__main__":
    unittest.main()
