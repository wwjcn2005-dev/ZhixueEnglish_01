#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-5 设计验证：结构校验 + 教育规则一致性 + 边界检查（全部离线，不接 AI）。

对应任务书 §十八 的 10 项测试要求。
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True

BASE = HERE.parent
LM_DIR = BASE / "structured" / "learning"
AUDIT = BASE / "audit"


def load(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


MODEL = load(LM_DIR / "learning_model_v1.json")
EVIDENCE = load(LM_DIR / "learning_evidence_model_v1.json")
FLOW = load(LM_DIR / "learning_flow_v1.json")
INTERVENTION = load(LM_DIR / "intervention_model_v1.json")
STAGE = load(LM_DIR / "stage_assessment_model_v1.json")
AI = load(LM_DIR / "ai_role_model_v1.json")
DESIGN = load(AUDIT / "P2-5_learning_system_design.json")
ARCH_MD = (AUDIT / "P2-5_architecture_impact.md").read_text(encoding="utf-8")


class SchemaTest(unittest.TestCase):
    """1. JSON schema / structure validation"""

    def test_01_all_models_parse_and_identified(self):
        for doc, name in ((MODEL, "learning_model"), (EVIDENCE, "learning_evidence_model"),
                          (FLOW, "learning_flow"), (INTERVENTION, "intervention_model"),
                          (STAGE, "stage_assessment_model"), (AI, "ai_role_model")):
            self.assertEqual(doc["model"], name)
            self.assertEqual(doc["version"], "v1")
            self.assertEqual(doc["stage"], "P2-5")
            self.assertTrue(doc["purpose"])

    def test_02_design_json_and_docs_exist(self):
        for key in ("documents", "core_decisions", "rejects", "closed_loop", "architecture",
                    "answers", "certainties", "needs_real_kid_validation", "boundaries"):
            self.assertIn(key, DESIGN)
        self.assertTrue((AUDIT / "P2-5_learning_system_design.md").is_file())
        self.assertTrue((AUDIT / "P2-5_architecture_impact.md").is_file())


class ModelTest(unittest.TestCase):
    """2/3/7/8. 学习流程与对象关系、无“一次即掌握”、无“一次错误即薄弱”"""

    def test_01_states_are_defined_with_evidence(self):
        ids = [s["id"] for s in MODEL["states"]]
        self.assertIn("contacted", ids)
        self.assertIn("stable", ids)
        self.assertEqual(len(ids), len(set(ids)))
        for s in MODEL["states"]:
            self.assertIn("is_ability_claim", s)

    def test_02_no_single_event_mastery(self):
        stable = next(s for s in MODEL["states"] if s["id"] == "stable")
        req = " | ".join(stable["required_evidence"])
        self.assertIn("≥3", req)
        self.assertIn("任务类型", req)
        self.assertIn("自然日", req)
        contacted = next(s for s in MODEL["states"] if s["id"] == "contacted")
        self.assertFalse(contacted["is_ability_claim"],
                         "‘学过’不得是能力判断（否则等价于看过=会了）")

    def test_03_no_single_error_weakness(self):
        rules = " | ".join(r["rule"] for r in EVIDENCE["combination_rules"])
        self.assertIn("疑似薄弱", rules)
        self.assertIn("≥2 次错误", rules)
        rejected = {r["concept"] for r in MODEL["rejected_concepts"]}
        self.assertIn("错一次 = 薄弱点", rejected)

    def test_04_weak_evidence_cannot_upgrade_alone(self):
        self.assertFalse(EVIDENCE["strength_scale"]["weak"]["may_alone_raise_state"])
        weak_ids = {e["id"] for e in EVIDENCE["evidence_sources"] if e["strength"] == "weak"}
        self.assertTrue({"EV-study-done", "EV-self-check"} <= weak_ids)

    def test_05_learning_objects_are_textbook_based(self):
        kinds = {o["kind"] for o in MODEL["core_learning_unit"]["object_kinds"]}
        for k in ("vocabulary", "phrase", "sentence_pattern", "grammar_point",
                  "listening_task", "reading_text", "writing_task"):
            self.assertIn(k, kinds)
        self.assertIn("Activity", MODEL["core_learning_unit"]["why_not_activity"])
        self.assertIn("Exercise", MODEL["core_learning_unit"]["why_not_exercise"])


class FlowTest(unittest.TestCase):
    """4. Evidence → Diagnosis → Intervention 链路；2. 流程一致性"""

    def test_01_loop_contains_required_stages(self):
        names = [s["name"] for s in FLOW["closed_loop"]["steps"]]
        for required in ("教材", "学习", "练习", "AI批改", "证据", "证据聚合", "诊断（可选）",
                         "孩子决定", "干预/巩固", "再次验证", "继续教材", "阶段验证（可选）"):
            self.assertIn(required, names, "闭环缺少环节：%s" % required)

    def test_02_every_step_has_owner(self):
        for s in FLOW["closed_loop"]["steps"]:
            self.assertIn(s["owner"], ("孩子", "系统", "AI", "孩子+AI"), s["id"])

    def test_03_child_decision_points_exist_and_ai_has_none(self):
        steps = FLOW["closed_loop"]["steps"]
        child_decides = [s for s in steps if s["owner"] == "孩子" and s["child_decision"] != "—"]
        self.assertGreaterEqual(len(child_decides), 4)
        for s in steps:
            if s["owner"] == "AI":
                self.assertIn(s["child_decision"], ("—", "是否看批改理由、是否接受建议"),
                              "AI 步骤不得替孩子做决定：%s" % s["id"])

    def test_04_intervention_covers_all_problem_types(self):
        for p in INTERVENTION["problem_types"]:
            self.assertTrue(p["problem"])
            self.assertTrue(p["signals"])
            self.assertTrue(p["interventions"])
            for iv in p["interventions"]:
                self.assertIsInstance(iv["textbook_first"], bool)

    def test_05_no_intervention_for_slip(self):
        slip = next(p for p in INTERVENTION["problem_types"] if p["id"] == "P7")
        self.assertEqual(slip["problem"], "粗心/偶发错误")
        self.assertEqual(slip["interventions"][0]["type"], "no_intervention")
        self.assertFalse(slip["ai_may_generate"])

    def test_06_textbook_first_by_default(self):
        for p in INTERVENTION["problem_types"]:
            self.assertTrue(p["interventions"][0]["textbook_first"],
                            "%s 的第一顺位干预必须教材优先" % p["id"])


class BoundaryTest(unittest.TestCase):
    """5/9/10. AI 边界、专项不脱离教材、阶段测试范围"""

    def test_01_ai_has_required_outputs(self):
        ids = [o["id"] for o in AI["outputs"]]
        self.assertEqual(ids, ["O1", "O2", "O3", "O4", "O5", "O6", "O7"])
        for o in AI["outputs"]:
            self.assertTrue(o["name"])

    def test_02_ai_must_not_decide_or_produce_content(self):
        must_not = " | ".join(AI["boundaries"]["ai_must_not"])
        for token in ("决定孩子学什么", "自动进入下一个内容", "生成教材之外的知识内容",
                      "分数、排名、等级"):
            self.assertIn(token, must_not)
        self.assertEqual(len(AI["must_not_conclude"]), 6)

    def test_03_ai_generated_practice_is_conditional_and_textbook_scoped(self):
        gen = [p for p in INTERVENTION["problem_types"] if p["ai_may_generate"]]
        self.assertGreaterEqual(len(gen), 1)
        self.assertLessEqual(len(gen), 4, "允许 AI 生成练习的问题类型必须保持低频")
        for p in gen:
            conds = []
            for iv in p["interventions"]:
                if iv["type"] == "ai_variant":
                    conds = iv.get("only_when") or []
            self.assertTrue(conds, "%s 的 AI 变式必须带触发条件" % p["id"])
        self.assertIn("教材范围内", json.dumps(INTERVENTION, ensure_ascii=False))

    def test_04_special_learning_recommendation_is_explicit(self):
        sl = DESIGN["special_learning_options"]
        self.assertEqual(sl["recommended"], "B")
        for key in ("A_comparative", "B_comparative", "C_comparative"):
            self.assertIn("结论", sl[key])
            self.assertIn(sl[key]["结论"], ("推荐", "不推荐"))

    def test_05_stage_assessment_has_no_grade(self):
        self.assertIn("分数", STAGE["result_report"]["child_never_sees"])
        self.assertIn("排名", STAGE["result_report"]["child_never_sees"])
        self.assertTrue(any("计分" in r["rule"] or "分数" in r["rule"]
                            for r in STAGE["design_rules"]))
        self.assertTrue(any("刚做过" in r["rule"] for r in STAGE["design_rules"]))
        self.assertTrue(any("不直接改写掌握状态" in r["rule"] for r in STAGE["design_rules"]))

    def test_06_stage_scope_matches_learned_objects(self):
        self.assertIn("只覆盖本阶段已接触过的 LearningObject",
                      STAGE["scope"]["learning_objects"])
        self.assertIn("不做强制关卡", " ".join(STAGE["not_when"]))


class ArchitectureTest(unittest.TestCase):
    """13/14 and 边界：现有架构分类与数据安全声明"""

    def test_01_architecture_categories_complete(self):
        arch = DESIGN["architecture"]
        for key in ("KEEP", "EXTEND", "REBUILD", "DEFER"):
            self.assertTrue(arch[key], "%s 不能为空" % key)
        rebuild = " ".join(arch["REBUILD"])
        self.assertIn("掌握判定算法", rebuild)
        self.assertIn("诊断", rebuild)
        self.assertIn("AI 批改", rebuild)

    def test_02_mastery_shell_is_reported(self):
        self.assertIn("从不推进", ARCH_MD)
        self.assertIn("KEEP", ARCH_MD)
        self.assertIn("REBUILD", ARCH_MD)

    def test_03_boundaries_declared_and_clean(self):
        b = DESIGN["boundaries"]
        for key in ("modified_learning_db", "modified_contentpack", "modified_p2_4_products",
                    "modified_android", "modified_web_ui", "produced_real_learning_record"):
            self.assertFalse(b[key], "%s 必须为 false" % key)
        self.assertEqual(b["real_ai_calls"], 0)
        self.assertTrue(b["new_files_only"])

    def test_04_questions_all_answered(self):
        answers = DESIGN["answers"]
        self.assertEqual(len(answers), 14, "14 个核心问题必须逐一回答")
        for key, value in answers.items():
            self.assertTrue(value, key)

    def test_05_certainties_and_open_questions_listed(self):
        self.assertGreaterEqual(len(DESIGN["certainties"]), 5)
        self.assertGreaterEqual(len(DESIGN["needs_real_kid_validation"]), 4)


if __name__ == "__main__":
    unittest.main()
