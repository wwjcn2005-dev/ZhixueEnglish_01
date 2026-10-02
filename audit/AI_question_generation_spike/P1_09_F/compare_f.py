# -*- coding: utf-8 -*-
"""P1-09-F: after-the-call comparison against the frozen P1-09-D gold (no AI call).

Writes comparison.json
"""

import json
import os

BASE = r"D:\ZhixueEnglish"
SPIKE = os.path.join(BASE, "audit", "AI_question_generation_spike")
P1_09_D = os.path.join(SPIKE, "P1_09_D_boundary_validation")
HERE = os.path.dirname(os.path.abspath(__file__))

# experimenter-side expectation, taken verbatim from the P1-09-D fixture definitions
# (FIX-C1 introduced_defect names `students`; FIX-C2 introduced_defect names `word`)
DESIGNED_ALTERNATIVE = {"FIX-C1": "students", "FIX-C2": "word"}
EXPECTED_ASSESSMENT = {"FIX-C1": "UNIQUE_RISK", "FIX-C2": "UNIQUE_RISK"}
# anchoring patterns that would indicate the forbidden reasoning
ANCHOR_PATTERNS = ["与课文一致，所以", "与课文一致所以", "所以唯一", "因此唯一", "课文里有，所以",
                   "没有第二", "唯一答案", "其他选项都不", "其他选项均不"]


def main():
    asmt = json.load(open(os.path.join(HERE, "assessment.json"), encoding="utf-8"))
    gold = json.load(open(os.path.join(P1_09_D, "hidden_gold.json"), encoding="utf-8"))["gold"]
    gold = {g["fixture_id"]: g for g in gold}
    acc = json.load(open(os.path.join(HERE, "call_accounting.json"), encoding="utf-8"))

    rows, anchoring_hits = [], []
    for it in asmt["items"]:
        qid = it["question_id"]
        designed = DESIGNED_ALTERNATIVE[qid]
        flagged = it["flagged_candidates"]
        reasons = " ".join(c["reason_cn"] for c in it["candidates"])
        hits = [p for p in ANCHOR_PATTERNS if p in reasons]
        if hits:
            anchoring_hits.append({"question_id": qid, "patterns": hits})
        extra = [c for c in flagged if c != designed]
        rows.append({
            "question_id": qid,
            "gold_answer_unique_expected": gold[qid]["scored"]["answer_unique"]["must_be_in"],
            "gold_decision_rule": gold[qid]["decision_rule"],
            "designed_second_answer": designed,
            "program_assessment": it["assessment"],
            "expected_assessment": EXPECTED_ASSESSMENT[qid],
            "assessment_match": it["assessment"] == EXPECTED_ASSESSMENT[qid],
            "second_answer_detected": designed in flagged,
            "current_answer_valid": it["current_answer_valid"],
            "current_answer_wrongly_excluded": not it["current_answer_valid"],
            "flagged_candidates": flagged,
            "extra_flagged_beyond_designed": extra,
            "excluded_candidates": [c["candidate_text"] for c in it["candidates"]
                                    if not c["program_valid_alternative"]
                                    and not c["is_current_answer"]],
            "coverage": it["candidate_coverage"],
            "need_more_context": it["need_more_context_candidates"],
            "ai_vs_program_rollup_all_agree": all(
                c["ai_vs_program_agreement"] is not False for c in it["candidates"]),
            "anchoring_patterns_found": hits,
            "reasons": {c["candidate_text"]: c["reason_cn"] for c in it["candidates"]},
        })

    summary = {
        "fixtures": len(rows),
        "second_answer_detected": sum(1 for r in rows if r["second_answer_detected"]),
        "assessment_match": sum(1 for r in rows if r["assessment_match"]),
        "false_negative": sum(1 for r in rows if not r["second_answer_detected"]),
        "false_positive_current_answer_excluded":
            sum(1 for r in rows if r["current_answer_wrongly_excluded"]),
        "extra_flags_total": sum(len(r["extra_flagged_beyond_designed"]) for r in rows),
        "ai_rollup_disagreements": sum(1 for r in rows if not r["ai_vs_program_rollup_all_agree"]),
        "anchoring_pattern_hits": len(anchoring_hits),
        "coverage_all_complete": all(r["coverage"] == "COMPLETE" for r in rows),
        "need_more_context_total": sum(len(r["need_more_context"]) for r in rows),
        "cost": {"ai_calls": acc["api_calls"], "input_tokens": acc["input_tokens"],
                 "output_tokens": acc["output_tokens"], "reasoning_tokens": acc["reasoning_tokens"],
                 "total_tokens": acc["total_tokens"], "latency_ms": acc["latency_ms"],
                 "tokens_per_question": round(acc["total_tokens"] / acc["fixtures"] if "fixtures"
                                              in acc else acc["total_tokens"] / 2, 1),
                 "p1_09_d_tokens_per_question": 1024.7},
    }
    summary["cost"]["ratio_vs_p1_09_d"] = round(
        summary["cost"]["tokens_per_question"] / summary["cost"]["p1_09_d_tokens_per_question"], 2)

    out = {"stage": "P1-09-F", "summary": summary, "rows": rows,
           "anchoring_hits": anchoring_hits,
           "note": "gold 仅在 AI 调用完成后读取；AI 输入快照已通过泄漏断言。"}
    with open(os.path.join(HERE, "comparison.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print()
    for r in rows:
        print("%-8s designed=%-9s detected=%-5s assessment=%-12s match=%-5s "
              "current_valid=%-5s extra_flagged=%s excluded=%s"
              % (r["question_id"], r["designed_second_answer"], r["second_answer_detected"],
                 r["program_assessment"], r["assessment_match"], r["current_answer_valid"],
                 r["extra_flagged_beyond_designed"], r["excluded_candidates"]))


if __name__ == "__main__":
    main()
