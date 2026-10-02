# -*- coding: utf-8 -*-
"""P1-09-G: pre-screen discrimination analysis + cost model. AI = 0. Read-only.

Writes risk_layer_analysis.json and cost_model.json
"""

import json
import os

BASE = r"D:\ZhixueEnglish"
SPIKE = os.path.join(BASE, "audit", "AI_question_generation_spike")
HERE = os.path.dirname(os.path.abspath(__file__))

P1_09_F_TOKENS_PER_QUESTION = 5152.0
P1_09_D_TOKENS_PER_QUESTION = 1024.7

KNOWN_RISK = {"FIX-C1": True, "FIX-C2": True}       # P1-09-D/F established true second answers
ACTIVE_APPROVED = {"AIQ:BD59C5958D45"}              # human approved (P1-08-C)


def main():
    pr = json.load(open(os.path.join(HERE, "prescreen_result.json"), encoding="utf-8"))
    items = pr["items"]
    lib_items = [i for i in items if i["source"] == "question_library"]
    fx_items = [i for i in items if i["source"].startswith("P1-09-D")]
    flagged = [i for i in items if i["state"] == "AI_REVIEW_CANDIDATE"]
    rule_fire = {}
    for i in items:
        for r in i["fired_rules"]:
            rule_fire[r] = rule_fire.get(r, 0) + 1

    analysis = {
        "stage": "P1-09-G", "ai_calls": 0,
        "items_evaluated": len(items),
        "library_choice_items": len(lib_items),
        "fixture_items": len(fx_items),
        "ai_review_candidate_total": len(flagged),
        "ai_candidate_rate_all": round(len(flagged) / len(items), 3),
        "ai_candidate_rate_library_only": round(
            sum(1 for i in lib_items if i["state"] == "AI_REVIEW_CANDIDATE") / len(lib_items), 3),
        "rule_fire_counts": rule_fire,
        "rules_never_fired": [r for r in ("R1_option_duplicate_or_containment", "R2_same_lemma_pair")
                              if rule_fire.get(r, 0) == 0],
        "known_risk_detection": {
            q: next(i["state"] for i in items if i["question_id"] == q) for q in KNOWN_RISK},
        "known_risk_missed": [q for q in KNOWN_RISK
                              if next(i["state"] for i in items
                                      if i["question_id"] == q) != "AI_REVIEW_CANDIDATE"],
        "active_approved_item": {
            q: next(i["state"] for i in items if i["question_id"] == q)
            for q in ACTIVE_APPROVED},
        "active_item_flagged": any(
            next(i["state"] for i in items if i["question_id"] == q) == "AI_REVIEW_CANDIDATE"
            for q in ACTIVE_APPROVED),
        "pos_gap_effect": {
            "answer_pos_unknown_items": [i["question_id"] for i in items
                                         if not i["rules"]["R3_same_pos_parallel"]["answer_pos_known"]],
            "note": "答案词性未知 → R3/R4 无法触发；这正是 FIX-C1 被漏掉的直接原因"},
        "p1_09_f_flag_rate": {
            "non_current_options_judged": 6, "flagged_valid_alternatives": 5,
            "rate": round(5 / 6, 3),
            "note": "P1-09-F 实测：6 个非当前答案选项中有 5 个被判为有效（83%）"},
    }

    n = 100
    schemes = []
    for name, share in (("A_100pct", 1.00), ("B_50pct", 0.50), ("C_30pct", 0.30),
                        ("D_20pct", 0.20)):
        calls = int(n * share)
        tokens = round(calls * P1_09_F_TOKENS_PER_QUESTION)
        schemes.append({
            "scheme": name, "share_entering_ai": share,
            "basis": "以 100 道选择题为单位",
            "ai_calls": calls, "tokens": tokens,
            "tokens_per_choice_item": round(tokens / n, 1),
            "multiple_of_p1_09_d_per_item": round(
                tokens / n / P1_09_D_TOKENS_PER_QUESTION, 2),
            "multiple_of_full_per_candidate": round(share, 2),
            "estimated_human_review_items": calls,
            "note": "纯模型估算；人工复核量按进入 AI 的题数计（AI 结论只作人工阅读辅助）"})
    cost = {"stage": "P1-09-G", "ai_calls": 0,
            "measured_basis": {"p1_09_f_tokens_per_question": P1_09_F_TOKENS_PER_QUESTION,
                               "p1_09_d_tokens_per_question": P1_09_D_TOKENS_PER_QUESTION,
                               "source": "P1-09-F 真实调用（2 题 / 10,304 tokens）"},
            "schemes": schemes, "estimates_only": True}

    with open(os.path.join(HERE, "risk_layer_analysis.json"), "w", encoding="utf-8") as fh:
        json.dump(analysis, fh, ensure_ascii=False, indent=2)
    with open(os.path.join(HERE, "cost_model.json"), "w", encoding="utf-8") as fh:
        json.dump(cost, fh, ensure_ascii=False, indent=2)

    print(json.dumps(analysis, ensure_ascii=False, indent=1))
    print()
    for s in schemes:
        print("%-10s ai_calls=%-4d tokens=%-9d per_item=%-8s xP1-09-D=%-6s human_review_items=%s"
              % (s["scheme"], s["ai_calls"], s["tokens"], s["tokens_per_choice_item"],
                 s["multiple_of_p1_09_d_per_item"], s["estimated_human_review_items"]))


if __name__ == "__main__":
    main()
