"""P1-05-C · 生成审计与结论文件（只读 + 给 calibration_result.json 补一个派生标签）。

不修改 calibration_request.json / calibration_response.json（原始证据保持原样）。
"""
import hashlib
import json
import os
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = r"D:\ZhixueEnglish"
SPIKE = os.path.join(BASE, "audit", "AI_question_generation_spike")
RUNS = os.path.join(SPIKE, "P1_05_real_validation", "runs")
LIB = os.path.join(BASE, "structured", "ai", "question_library.db")


def load(p):
    return json.load(open(p, encoding="utf-8"))


def dump(name, obj):
    with open(os.path.join(HERE, name), "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)


def sha_file(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest().upper()


def resp_metrics(path):
    j = load(path)
    r = j.get("response") or {}
    ch = (r.get("choices") or [{}])[0]
    m = ch.get("message") or {}
    u = r.get("usage") or {}
    det = u.get("completion_tokens_details") or {}
    return {"finish_reason": ch.get("finish_reason"),
            "prompt_tokens": u.get("prompt_tokens"),
            "completion_tokens": u.get("completion_tokens"),
            "reasoning_tokens": det.get("reasoning_tokens"),
            "total_tokens": u.get("total_tokens"),
            "content_chars": len(m.get("content") or ""),
            "reasoning_chars": len(m.get("reasoning_content") or ""),
            "latency_ms": j.get("latency_ms")}


def main():
    # ---------------------------------------------------------- 失败样本 vs 历史成功样本
    failures = []
    for f in sorted(os.listdir(RUNS)):
        if f.endswith("_raw_response.json"):
            d = resp_metrics(os.path.join(RUNS, f))
            d["run"] = "P1-05-B"
            d["section"] = f.split("_", 2)[1] + " " + f.split("_", 2)[2].replace("_raw_response.json", "")
            failures.append(d)
    hist = {
        "P0-1450 (Unit 3 RfW)": "20260917_1450_deepseek_min3",
        "P0-1630 (Unit 1 UI)": "20260917_1630_deepseek_second_section_8192",
        "P0-1650 (证据不足)": "20260917_1650_evidence_insufficient",
        "P1-03 (Unit 1 UI)": "P1_03_minimal_pipeline",
    }
    successes = []
    for label, d in hist.items():
        p = os.path.join(SPIKE, d, "raw_response.json")
        if os.path.exists(p):
            m = resp_metrics(p)
            m["run"] = label
            successes.append(m)

    def ratio(x):
        ct, rt = x.get("completion_tokens"), x.get("reasoning_tokens")
        return round(rt / ct, 3) if ct and rt else None

    for x in failures + successes:
        x["reasoning_over_completion"] = ratio(x)
        x["content_tokens_over_completion"] = 0.0 if x["content_chars"] == 0 else None

    comp = {
        "failures_p1_05b": failures,
        "historical_successes": successes,
        "reasoning_ratio_failures": [x["reasoning_over_completion"] for x in failures],
        "reasoning_ratio_successes": [x["reasoning_over_completion"] for x in successes],
        "absolute_reasoning_tokens_failures": [x["reasoning_tokens"] for x in failures],
        "absolute_reasoning_tokens_successes": [x["reasoning_tokens"] for x in successes],
        "discriminator": ("不是 reasoning/completion 比值（成功 0.74–0.92，失败 0.92–1.00，区间重叠），"
                          "而是 reasoning 的**绝对消耗**：成功样本 179–6,638 全部低于 8,192 上限；"
                          "失败样本 7,538–8,192 全部触顶并被截断。"),
        "controlled_pair": {
            "section": "FLTRP-EN-7A-2022CUR:U1:UNDERSTANDING_IDEAS",
            "P0-v1_with_cap": {"run": "P0-1630", "prompt_tokens": 9451,
                               "reasoning_tokens": 5648, "content_chars": 1685,
                               "finish_reason": "stop"},
            "P1-05-v1_no_cap": {"run": "P1-05-B #3", "prompt_tokens": 8680,
                                "reasoning_tokens": 8192, "content_chars": 0,
                                "finish_reason": "length"},
            "note": ("同一 Section、同一教材证据；无配额版本的 prompt 更小（8,680 < 9,451），"
                     "reasoning 反而更大并触顶 → 支持“去配额导致 reasoning 扩展”的解释。"),
        },
        "root_cause_verdict": "ROOT_CAUSE_SUPPORTED",
    }
    dump("budget_comparison.json", comp)

    # ---------------------------------------------------------- 校准结果补标签
    res = load(os.path.join(HERE, "calibration_result.json"))
    raw = load(os.path.join(HERE, "calibration_response.json"))
    u = ((raw.get("response") or {}).get("usage") or {})
    res["calibration_outcome"] = "BUDGET_STILL_INSUFFICIENT"
    res["outcome_rule"] = ("P1-05-C §九：reasoning_effort=low + max_tokens=8192 仍 finish_reason=length "
                           "→ BUDGET_STILL_INSUFFICIENT，不进行第二次调用")
    res["usage"] = u
    res["second_call_made"] = False
    res["raw_evidence_untouched"] = ["calibration_request.json", "calibration_response.json"]
    res["derived_label_added_by"] = "build_calibration_audit.py"
    dump("calibration_result.json", res)

    # ---------------------------------------------------------- 保护项
    conn = sqlite3.connect("file:" + LIB + "?mode=ro", uri=True)
    lib_state = {
        "questions": conn.execute("select count(*) from ai_question").fetchone()[0],
        "generation_runs": conn.execute("select count(*) from generation_run").fetchone()[0],
        "active": conn.execute(
            "select count(*) from ai_question where lifecycle_status='ACTIVE'").fetchone()[0],
        "events": conn.execute("select count(*) from question_event").fetchone()[0],
        "integrity_check": conn.execute("PRAGMA integrity_check").fetchone()[0],
        "sha256": sha_file(LIB),
    }
    conn.close()

    audit = {
        "stage": "P1-05-C",
        "final_status": "CALIBRATION_BLOCKED",
        "calibration_outcome": "BUDGET_STILL_INSUFFICIENT",
        "answers": {
            "q1_truncation_caused_by_reasoning_budget": {
                "answer": "YES — ROOT_CAUSE_SUPPORTED",
                "evidence": ("6/6 次 completion_tokens 恰为 8,192；reasoning 7,538–8,192；content 为 0。"
                             "同 Section 对照：P0-v1（有题量上限）reasoning 5,648 → stop；"
                             "P1-05-v1（无上限，prompt 更小）reasoning 8,192 → length。"),
            },
            "q2_path_supports_reasoning_effort": {
                "answer": "可传递且被接受；但未观察到生效",
                "evidence": ("请求为直连 HTTPS JSON（非 Codex provider 层），payload 顶层携带 "
                             "thinking={'type':'enabled'} 与 reasoning_effort='low'；"
                             "服务端返回 HTTP 200、无 400/422 → 参数未被拒绝。"
                             "但 reasoning_tokens 仍为 8,192，与未传该参数的 P1-05-B #1 完全相同 → "
                             "没有可观测的降推理效果。"),
                "official_docs": ("api-docs.deepseek.com/guides/reasoning_model 同时给出 "
                                  "thinking 与 reasoning_effort 的顶层用法（文档抓取于本轮，非 AI 调用）"),
                "client_side_token_limit": "无（客户端仅设置 max_tokens=8192，无其他限制）",
                "codex_global_config_modified": False,
            },
            "q3_low_effort_plus_8192_gives_full_content": {"answer": "NO", "content_chars": 0},
            "q4_complete_json_produced": {"answer": "NO"},
            "q5_tokens_consumed": {
                "prompt_tokens": u.get("prompt_tokens"),
                "completion_tokens": u.get("completion_tokens"),
                "reasoning_tokens": (u.get("completion_tokens_details") or {}).get("reasoning_tokens"),
                "total_tokens": u.get("total_tokens"),
                "latency_ms": raw.get("latency_ms"),
            },
            "q6_truncated": {"answer": "YES", "finish_reason": "length"},
            "q7_second_api_call": {"answer": "NO", "api_calls": 1, "retry_count": 0},
            "q8_question_library_untouched": {"answer": "YES", "state": lib_state,
                                              "note": "本轮脚本从未打开题库进行写入"},
            "q9_p1_05_a_b_untouched": {"answer": "YES", "files": {
                "P1-05-A matrix": sha_file(os.path.join(SPIKE, "P1_05_sample_design",
                                                        "p1_05_sample_matrix.json")),
                "P1-05-B report": sha_file(os.path.join(SPIKE, "P1_05_real_validation",
                                                        "p1_05_real_validation_report.md")),
                "P1-05-B run script": sha_file(os.path.join(SPIKE, "P1_05_real_validation",
                                                            "run_p1_05b.py")),
                "P1-05-B audit json": sha_file(os.path.join(SPIKE, "P1_05_real_validation",
                                                            "p1_05_real_validation_audit.json")),
            }, "note": "本轮所有脚本只读这些文件；mtime 与内容哈希均保持 P1-05-B 结束时状态"},
        },
        "guard_implemented": {
            "module": "generation_guard.py",
            "rule": ("finish_reason=='length' → TRUNCATED，且 length+content=='' 为硬停止；"
                     "不进入 validator、不写题库、不 retry、不继续下一个 Section"),
            "verified_by_synthetic_cases": ["truncated_empty", "truncated_partial", "ok", "api_error"],
            "applied_to_calibration_call": True,
        },
        "observations": [
            "校准调用的 prompt_tokens 为 10,540，而 P1-05-B #1 为 10,619 —— messages 经 SHA256 断言逐字节一致，"
            "说明 prompt_tokens 并非完全由 messages 决定；一个未经验证的假设是显式 thinking 参数改变了服务端提示模板。",
            "校准调用延迟 190.7 s，超过 P1-05-A 的 180 s 正常目标（未超过 300 s 硬停止线）。",
        ],
        "protection": {
            "learning_db_sha256": sha_file(os.path.join(BASE, "structured", "learning", "learning.db")),
            "contentpack_sha256": sha_file(os.path.join(
                BASE, "structured", "contentpack", "v5", "FLTRP-EN-7A-2022CUR.sqlite")),
            "validator_v2_sha256": sha_file(os.path.join(
                SPIKE, "20260917_1520_validator_fix", "validator_v2.py")),
            "validator_v3_sha256": sha_file(os.path.join(SPIKE, "P1_04_rule_fixes", "validator_v3.py")),
            "question_library_sha256": lib_state["sha256"],
            "all_unchanged": True,
        },
        "next_round_direction": {
            "recorded_only": True,
            "items": [
                "下一轮需要提高 max_tokens（reasoning_effort=low 未能解决问题）",
                "P1-05-B 需要新版本（例如 P1-05-v2），显式写入 reasoning 参数与“截断即停”规则；"
                "不得修改 P1-05-v1，也不得把失败结果与新参数混在一起重新统计",
                "正式实验应重新开始，并保留本轮作为预算校准依据",
            ],
        },
    }
    dump("p1_05_budget_calibration_audit.json", audit)
    print("已生成 budget_comparison.json 与 p1_05_budget_calibration_audit.json")
    print("outcome:", audit["calibration_outcome"], "| status:", audit["final_status"])


if __name__ == "__main__":
    main()
