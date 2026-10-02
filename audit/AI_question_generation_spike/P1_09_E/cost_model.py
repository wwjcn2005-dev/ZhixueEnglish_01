# -*- coding: utf-8 -*-
"""P1-09-E: cost model for the candidate-pool design (offline estimate, no AI calls).

Baseline = P1-09-D measured cost (15 fixtures / 15,371 tokens).
Writes cost_model.json
"""

import json
import os

BASE = r"D:\ZhixueEnglish"
SPIKE = os.path.join(BASE, "audit", "AI_question_generation_spike")
HERE = os.path.dirname(os.path.abspath(__file__))

TOK_PER_CANDIDATE_PROMPT = 10
TOK_PER_CANDIDATE_OUTPUT = 35
INSTR_TOKENS = 1400
CONTEXT_TOKENS = 250


def main():
    d = json.load(open(os.path.join(SPIKE, "P1_09_D_boundary_validation",
                                   "call_accounting.json"), encoding="utf-8"))
    pools = json.load(open(os.path.join(HERE, "pool_size_analysis.json"), encoding="utf-8"))
    baseline = {"fixtures": d["fixture_count"], "prompt_tokens": d["prompt_tokens"],
                "completion_tokens": d["completion_tokens"],
                "total_tokens": d["total_tokens"], "latency_ms": d["latency_ms"]}
    per_q = {"prompt": d["prompt_tokens"] / d["fixture_count"],
             "completion": d["completion_tokens"] / d["fixture_count"],
             "total": d["total_tokens"] / d["fixture_count"]}
    pool_sizes = {
        "CHOICE_options": {"size": 4, "coverage": "COMPLETE",
                           "note": "选择题的候选池就是题目给出的选项（3-4 个），无需生成，覆盖完整"},
        "FILL_same_slot": {"size": 2, "coverage": "PARTIAL",
                           "note": "同槽位代入，实测 1-3 个，但漏掉两个真实第二答案"},
        "FILL_vocabulary_BOLD_pos": {"size": 117, "coverage": "PARTIAL",
                                     "note": "教材 BOLD 词表 + 同词性，实测 0-117 个，同样漏掉真实第二答案"},
        "FILL_section_text": {"size": 230, "coverage": "COVERS_BUT_TOO_BIG",
                              "note": "Section 正文全部词，实测 225-236 个，覆盖但规模不可用"},
    }
    schemes = []
    for name, info in pool_sizes.items():
        n = info["size"]
        a_in = per_q["prompt"] + n * TOK_PER_CANDIDATE_PROMPT
        a_out = per_q["completion"] + n * TOK_PER_CANDIDATE_OUTPUT
        schemes.append({
            "pool": name, "pool_size": n, "coverage": info["coverage"], "note": info["note"],
            "schemeA_one_call_per_question": {
                "api_calls_per_question": 1, "input_tokens": round(a_in),
                "output_tokens": round(a_out), "total_tokens": round(a_in + a_out),
                "multiple_of_p1_09_d": round((a_in + a_out) / per_q["total"], 2)},
            "schemeB_one_call_per_candidate": {
                "api_calls_per_question": n,
                "total_tokens": round(n * (INSTR_TOKENS + CONTEXT_TOKENS
                                           + TOK_PER_CANDIDATE_OUTPUT)),
                "multiple_of_p1_09_d": round(
                    n * (INSTR_TOKENS + CONTEXT_TOKENS + TOK_PER_CANDIDATE_OUTPUT)
                    / per_q["total"], 2)},
            "schemeC_program_prefilter_then_batch": {
                "api_calls_per_question": 1, "pool_size_after_prefilter": n,
                "total_tokens": round(a_in + a_out),
                "multiple_of_p1_09_d": round((a_in + a_out) / per_q["total"], 2),
                "note": "确定性预筛 + 一次批量判断；效果等于 A 方案配一个小池"}})
    out = {"stage": "P1-09-E", "ai_calls": 0, "baseline_p1_09_d": baseline,
           "baseline_per_question": {k: round(v, 1) for k, v in per_q.items()},
           "tokens_per_candidate": {"prompt": TOK_PER_CANDIDATE_PROMPT,
                                    "output": TOK_PER_CANDIDATE_OUTPUT},
           "pool_sizes": pool_sizes, "schemes": schemes, "estimates_only": True,
           "note": "全部为离线估算，未调用 AI；baseline 为 P1-09-D 实测值。"}
    with open(os.path.join(HERE, "cost_model.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    print("baseline per question (P1-09-D):", out["baseline_per_question"])
    print()
    for s in schemes:
        a = s["schemeA_one_call_per_question"]
        b = s["schemeB_one_call_per_candidate"]
        print("%-26s pool=%-5d A: 1 call %-6d tok (%sx) | B: %-4d calls %-7d tok (%sx)"
              % (s["pool"], s["pool_size"], a["total_tokens"], a["multiple_of_p1_09_d"],
                 b["api_calls_per_question"], b["total_tokens"], b["multiple_of_p1_09_d"]))
        print("      coverage:", s["coverage"], "|", s["note"])
    print()
    print("choice item: pool = options (4) -> +%d tokens/question, coverage COMPLETE"
          % (4 * TOK_PER_CANDIDATE_PROMPT + 4 * TOK_PER_CANDIDATE_OUTPUT))


if __name__ == "__main__":
    main()
