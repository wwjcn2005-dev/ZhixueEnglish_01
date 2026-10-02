"""P1-05-D · 生成审计 JSON（只读汇总，不改任何证据文件）。"""
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = r"D:\ZhixueEnglish"
SPIKE = os.path.join(BASE, "audit", "AI_question_generation_spike")
LIB = os.path.join(BASE, "structured", "ai", "question_library.db")


def load(p):
    return json.load(open(p, encoding="utf-8"))


def sha_file(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest().upper()


def metrics(path):
    j = load(path)
    r = j.get("response") or {}
    ch = (r.get("choices") or [{}])[0]
    m = ch.get("message") or {}
    u = r.get("usage") or {}
    det = u.get("completion_tokens_details") or {}
    ptd = u.get("prompt_tokens_details") or {}
    latency_ms = j.get("latency_ms")
    if latency_ms is None and j.get("elapsed_ms") is not None:
        latency_ms = j.get("elapsed_ms")
    if latency_ms is None and j.get("elapsed_s") is not None:
        latency_ms = int(round(j["elapsed_s"] * 1000))
    return {"max_tokens_requested": j.get("max_tokens_requested") or j.get("max_tokens"),
            "finish_reason": ch.get("finish_reason"),
            "prompt_tokens": u.get("prompt_tokens"),
            "cached_tokens": ptd.get("cached_tokens"),
            "completion_tokens": u.get("completion_tokens"),
            "reasoning_tokens": det.get("reasoning_tokens"),
            "total_tokens": u.get("total_tokens"),
            "content_chars": len(m.get("content") or ""),
            "latency_ms": latency_ms}


def main():
    d = HERE
    res = load(os.path.join(d, "calibration_result.json"))
    raw = load(os.path.join(d, "calibration_response.json"))
    req = load(os.path.join(d, "calibration_request.json"))
    parsed = load(os.path.join(d, "calibration_parsed.json"))
    u = (raw.get("response") or {}).get("usage") or {}
    det = u.get("completion_tokens_details") or {}
    ptd = u.get("prompt_tokens_details") or {}
    qs = parsed.get("questions") or []

    comparison = {
        "P0-1630_8192_stop": metrics(os.path.join(
            SPIKE, "20260917_1630_deepseek_second_section_8192", "raw_response.json")),
        "P1-03_8192_stop": metrics(os.path.join(SPIKE, "P1_03_minimal_pipeline",
                                                "raw_response.json")),
        "P1-05-B_run1_8192_length": metrics(os.path.join(
            SPIKE, "P1_05_real_validation", "runs",
            "01_Unit2_UNDERSTANDING_IDEAS_raw_response.json")),
        "P1-05-C_8192_low_length": metrics(os.path.join(
            SPIKE, "P1_05_budget_calibration", "calibration_response.json")),
        "P1-05-D_16384_low_stop": metrics(os.path.join(d, "calibration_response.json")),
    }
    for k, v in comparison.items():
        ct, rt = v.get("completion_tokens"), v.get("reasoning_tokens")
        v["reasoning_over_completion"] = round(rt / ct, 3) if ct and rt else None
    comparison["P1-05-B_run1_8192_length"]["max_tokens_requested"] = 8192
    comparison["P1-05-B_run1_8192_length"]["max_tokens_source"] = \
        "该轮 raw_response 未记录该字段；取自 P1-05-B 执行脚本常量与报告（8192）"
    comparison["P1-05-C_8192_low_length"]["max_tokens_requested"] = 8192
    comparison["P1-05-C_8192_low_length"]["max_tokens_source"] = \
        "该轮 raw_response 未记录该字段；取自 calibration_request.json（8192）"

    audit = {
        "stage": "P1-05-D",
        "final_status": res["final_status"],
        "single_variable": {
            "changed": "max_tokens 8192 -> 16384",
            "confirmed_by_field_diff_vs_p1_05c": True,
            "other_field_diffs": req["single_variable_check"]["other_field_diffs"],
            "context_and_prompt_identical": req["asserts"]["context_and_prompt_identical"],
            "system_prompt_sha256": req["asserts"]["system_prompt_sha256_rebuilt"],
            "user_prompt_sha256": req["asserts"]["user_prompt_sha256_rebuilt"],
            "context_hash": load(os.path.join(
                SPIKE, "P1_05_real_validation", "runs",
                "01_Unit2_UNDERSTANDING_IDEAS_prompt.json"))["context_hash"],
            "model": req["payload"]["model"], "temperature": req["payload"]["temperature"],
            "thinking": req["payload"]["thinking"],
            "reasoning_effort": req["payload"]["reasoning_effort"],
            "prompt_version": req["prompt_version"],
            "response_format": "未使用（与 P1-05-B/C 一致）",
        },
        "call": {
            "api_calls": 1, "retry_count": 0, "second_call_made": False,
            "http_ok": res["http_ok"], "api_error": res["api_error"],
            "latency_ms": res["latency_ms"], "latency_s": round(res["latency_ms"] / 1000.0, 1),
            "finish_reason": comparison["P1-05-D_16384_low_stop"]["finish_reason"],
            "content_chars": comparison["P1-05-D_16384_low_stop"]["content_chars"],
            "reasoning_chars": res["guard"]["verdict"]["reasoning_chars"],
            "max_tokens_requested": 16384,
            "prompt_tokens": u.get("prompt_tokens"),
            "cached_tokens": ptd.get("cached_tokens"),
            "completion_tokens": u.get("completion_tokens"),
            "reasoning_tokens": det.get("reasoning_tokens"),
            "total_tokens": u.get("total_tokens"),
        },
        "budget_analysis": {
            "reasoning_needed_at_least": det.get("reasoning_tokens"),
            "previous_cap": 8192,
            "deficit_of_previous_cap": det.get("reasoning_tokens") - 8192,
            "new_cap": 16384,
            "headroom_after_reasoning": 16384 - det.get("reasoning_tokens"),
            "reasoning_hit_cap": det.get("reasoning_tokens") >= 16384,
            "conclusion": ("reasoning 需要 10,481 tokens —— 超过 8,192 上限约 2,289 tokens，"
                           "但远低于 16,384；因此 8192 必然截断，16384 有约 5,903 tokens 余量。"),
        },
        "json_and_structure": {
            "json_parseable": res["json_parseable"],
            "questions_field_present": res["questions_field_present"],
            "questions_count": res["questions_count"],
            "questions_is_list": isinstance(qs, list),
            "type_distribution": {t: sum(1 for q in qs if q.get("type") == t)
                                  for t in sorted({q.get("type") for q in qs})},
            "pages_present": sorted({q.get("page") for q in qs}),
            "activities_present": sorted({q.get("activity") for q in qs}),
            "note": ("仅做『是否完整解析 + questions 字段存在 + 必填字段是否缺失』的只读检查；"
                     "**未进入正式 validator 流程**，也未做任何质量评价（P1-05-D §十一）"),
        },
        "comparison_across_runs": comparison,
        "guard": {"module": "P1-05-C generation_guard.py（只读复用，未修改）",
                  "decision": res["guard"]["decision"],
                  "verdict_status": res["guard"]["verdict"]["status"]},
        "protection": res["protection"],
        "not_done_in_this_round": [
            "未进入正式 validator 流程",
            "未做人工审核",
            "未写入 question_library.db（无 generation_run、无 AIQ:*）",
            "未计算 Natural Value Rate / APPROVE Rate",
            "未宣布 P1-05 通过",
        ],
    }
    with open(os.path.join(d, "p1_05_budget_calibration_v2_audit.json"), "w",
              encoding="utf-8") as fh:
        json.dump(audit, fh, ensure_ascii=False, indent=1)
    print("已生成 p1_05_budget_calibration_v2_audit.json")
    print("final:", audit["final_status"], "| reasoning:", det.get("reasoning_tokens"),
          "| headroom:", audit["budget_analysis"]["headroom_after_reasoning"])


if __name__ == "__main__":
    main()
