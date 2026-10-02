# -*- coding: utf-8 -*-
"""P1-09-B cost analysis: real tokens of this run + relative comparison vs P1-09-A model.

The per-question variant is NOT executed; it is a relative estimate only (as required).
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SPIKE = os.path.dirname(HERE)
P1_09_A = os.path.join(SPIKE, "P1_09_A_quality_review_design")
P1_06 = os.path.join(SPIKE, "P1_06_batch_stability")


def main():
    acc = json.load(open(os.path.join(HERE, "call_accounting.json"), encoding="utf-8"))
    req = json.load(open(os.path.join(HERE, "review_request.json"), encoding="utf-8"))
    out = json.load(open(os.path.join(HERE, "ai_review_output.json"), encoding="utf-8"))
    a_cost = json.load(open(os.path.join(P1_09_A, "cost_model.json"), encoding="utf-8"))
    p106 = json.load(open(os.path.join(P1_06, "p1_06_result.json"), encoding="utf-8"))

    n = acc["sample_count"]
    ratio = a_cost["measurement_basis"]["chars_per_prompt_token_mean"]
    instr_chars = 4376 + 60          # reviewer system prompt (measured) + user wrapper
    item_chars = 3173 / n            # measured blind payload per item
    gen_per_q = p106["total_tokens"] / 22

    batch = {
        "api_calls": 1,
        "prompt_tokens": acc["prompt_tokens"], "completion_tokens": acc["completion_tokens"],
        "reasoning_tokens": acc["reasoning_tokens"], "total_tokens": acc["total_tokens"],
        "latency_ms": acc["latency_ms"],
        "tokens_per_question": round(acc["total_tokens"] / n, 1),
        "output_tokens_per_question": round(acc["completion_tokens"] / n, 1),
    }
    per_q_estimate = {
        "api_calls": n,
        "input_tokens": round((instr_chars + item_chars) * n / ratio),
        "output_tokens": round(acc["completion_tokens"] / n * n),
        "note": "理论估算，未实际执行；instruction 每条题目重复一次",
    }
    per_q_estimate["total_tokens"] = (per_q_estimate["input_tokens"]
                                      + per_q_estimate["output_tokens"])
    per_q_estimate["tokens_per_question"] = round(per_q_estimate["total_tokens"] / n, 1)

    report = {
        "stage": "P1-09-B",
        "this_run_real": {
            "api_calls": 1, "retry_count": 0, "model": acc["model"],
            "temperature": acc["temperature"], "max_tokens": acc["max_tokens"],
            "reasoning_effort": acc["reasoning_effort"], "prompt_version": acc["prompt_version"],
            "finish_reason": acc["finish_reason"], "latency_ms": acc["latency_ms"],
            "questions_reviewed": n,
            "prompt_tokens": acc["prompt_tokens"],
            "completion_tokens": acc["completion_tokens"],
            "reasoning_tokens": acc["reasoning_tokens"],
            "total_tokens": acc["total_tokens"],
            "tokens_per_question": batch["tokens_per_question"],
        },
        "variants": {
            "batch_per_section_like": batch,
            "per_question_estimate_only": per_q_estimate,
            "only_program_PASS": {
                "api_calls": 1,
                "note": "当前生产流程默认只把程序验证 PASS 的题送审；本批 22 题 program PASS=22/22，"
                        "因此这一档在本数据集上与批量审核完全相同，过滤不出任何题",
            },
        },
        "comparison_with_generation": {
            "generation_tokens_per_question_p1_06": round(gen_per_q, 1),
            "batch_review_tokens_per_question": batch["tokens_per_question"],
            "batch_review_pct_of_generation": round(batch["tokens_per_question"] / gen_per_q * 100, 1),
            "per_question_review_pct_of_generation":
                round(per_q_estimate["tokens_per_question"] / gen_per_q * 100, 1),
            "note": "生成基准 = P1-06 4 次真实调用的 82,641 tokens / 22 题。",
        },
        "estimate_vs_actual": {
            "p1_09_a_estimate_input_tokens": a_cost["strategies"][1]["input_tokens"],
            "p1_09_a_estimate_output_tokens": a_cost["strategies"][1]["output_tokens"],
            "p1_09_a_estimate_total_tokens": (a_cost["strategies"][1]["input_tokens"]
                                              + a_cost["strategies"][1]["output_tokens"]),
            "actual_total_tokens": acc["total_tokens"],
            "actual_vs_estimate_ratio": round(acc["total_tokens"] /
                                              (a_cost["strategies"][1]["input_tokens"]
                                               + a_cost["strategies"][1]["output_tokens"]), 2),
            "note": "P1-09-A 的估算把输出按每题 220 tokens 计，没有给 reasoning 留预算；"
                    "本次实测 reasoning 占 completion 的 %.0f%%，因此输出被低估约 %.1f 倍。"
                    % (100.0 * acc["reasoning_tokens"] / acc["completion_tokens"],
                       (acc["completion_tokens"] / n) / 220.0),
        },
        "corrected_unit_cost": {
            "review_tokens_per_question_actual": batch["tokens_per_question"],
            "review_vs_generation_pct_actual": round(batch["tokens_per_question"] / gen_per_q * 100, 1),
        },
    }
    with open(os.path.join(HERE, "review_cost.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    print(json.dumps(report["this_run_real"], ensure_ascii=False, indent=1))
    print(json.dumps(report["comparison_with_generation"], ensure_ascii=False, indent=1))
    print(json.dumps(report["estimate_vs_actual"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
