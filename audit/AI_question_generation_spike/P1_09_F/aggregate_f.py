# -*- coding: utf-8 -*-
"""P1-09-F: program-side aggregation of the per-option judgements (no AI call).

The program recomputes each candidate's validity from the three fields (it does NOT copy the
model's own roll-up), then derives the final assessment:
  any non-answer option with grammar=YES & semantic=YES & context=YES -> UNIQUE_RISK
  else any candidate with need_more_context=YES                     -> UNIQUE_UNCERTAIN
  else coverage=COMPLETE and all others excluded                    -> UNIQUE_SUPPORTED

Writes assessment.json
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def norm(v):
    return str(v or "").strip().upper()


def rollup(c):
    """Program recomputation: valid only if all three flags are YES."""
    return (norm(c.get("grammar_valid")) == "YES" and norm(c.get("semantic_valid")) == "YES"
            and norm(c.get("textbook_context_valid")) == "YES")


def main():
    ai = json.load(open(os.path.join(HERE, "ai_review_output.json"), encoding="utf-8"))
    cmap = json.load(open(os.path.join(HERE, "candidate_map.json"),
                          encoding="utf-8"))["candidate_map"]

    items = []
    for it in ai["items"]:
        qid = it["question_id"]
        current = cmap[qid]["current_answer"]
        cands = []
        for c in it["candidates"]:
            prog = rollup(c)
            recorded = norm(c.get("valid_alternative"))
            cands.append({
                "candidate": c["option"], "candidate_text": c["candidate_text"],
                "is_current_answer": c["candidate_text"] == current,
                "grammar_valid": norm(c["grammar_valid"]),
                "semantic_valid": norm(c["semantic_valid"]),
                "textbook_context_valid": norm(c["textbook_context_valid"]),
                "need_more_context": norm(c["need_more_context"]),
                "ai_valid_alternative": recorded,
                "program_valid_alternative": prog,
                "ai_vs_program_agreement": (recorded == "YES") == prog if recorded in ("YES", "NO")
                else None,
                "reason_cn": c["reason_cn"]})

        others = [c for c in cands if not c["is_current_answer"]]
        flagged = [c for c in others if c["program_valid_alternative"]]
        need_ctx = [c for c in cands if c["need_more_context"] == "YES"]
        current_cand = next((c for c in cands if c["is_current_answer"]), None)
        coverage = "COMPLETE"
        coverage_reason = ("选择题的候选集合就是题目给出的全部选项（%d 个），无需生成，"
                           "覆盖度天然完整" % len(cands))
        if flagged:
            assessment = "UNIQUE_RISK"
            basis = "存在 %d 个非当前答案选项同时满足 grammar/semantic/textbook_context = YES" % len(flagged)
        elif need_ctx:
            assessment = "UNIQUE_UNCERTAIN"
            basis = "有 %d 个候选 need_more_context=YES" % len(need_ctx)
        elif current_cand and current_cand["program_valid_alternative"]:
            assessment = "UNIQUE_SUPPORTED"
            basis = "所有非当前答案选项均被排除，且覆盖度 COMPLETE"
        else:
            assessment = "UNIQUE_UNCERTAIN"
            basis = "当前答案本身未被判定为有效，无法支撑唯一性结论"
        items.append({
            "question_id": qid, "question_type": next(
                b["question_type"] for b in json.load(
                    open(os.path.join(HERE, "ai_input_snapshot.json"),
                         encoding="utf-8"))["items"] if b["question_id"] == qid),
            "current_textbook_answer": current,
            "candidate_coverage": coverage, "coverage_reason": coverage_reason,
            "assessment": assessment, "assessment_basis": basis,
            "flagged_candidates": [c["candidate_text"] for c in flagged],
            "flagged_letters": [c["candidate"] for c in flagged],
            "current_answer_valid": bool(current_cand and current_cand["program_valid_alternative"]),
            "current_answer_included": bool(current_cand),
            "need_more_context_candidates": [c["candidate_text"] for c in need_ctx],
            "candidate_count": len(cands), "excluded_count": len(others) - len(flagged),
            "candidates": cands,
        })

    out = {"stage": "P1-09-F", "ai_calls": 0,
           "aggregation_rule": {
               "step1": "任一非当前答案选项 grammar=YES 且 semantic=YES 且 textbook_context=YES "
                        "→ UNIQUE_RISK",
               "step2": "否则若任一候选 need_more_context=YES → UNIQUE_UNCERTAIN",
               "step3": "否则若 coverage=COMPLETE 且其余选项全部被排除 → UNIQUE_SUPPORTED",
               "note": "valid_alternative 由程序按三个字段重算，不使用模型的自我汇总；"
                       "模型不得输出任何整体唯一性结论（本轮输出中已确认没有）。"},
           "items": items}
    with open(os.path.join(HERE, "assessment.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    for it in items:
        print("%-8s coverage=%-8s assessment=%-16s flagged=%s current_valid=%s excluded=%d/%d"
              % (it["question_id"], it["candidate_coverage"], it["assessment"],
                 it["flagged_candidates"], it["current_answer_valid"], it["excluded_count"],
                 it["candidate_count"] - 1))
        for c in it["candidates"]:
            print("      %-2s %-9s prog_valid=%-5s ai_valid=%-5s agree=%-5s need_ctx=%-4s | %s"
                  % (c["candidate"], c["candidate_text"], c["program_valid_alternative"],
                     c["ai_valid_alternative"], c["ai_vs_program_agreement"],
                     c["need_more_context"], c["reason_cn"]))


if __name__ == "__main__":
    main()
