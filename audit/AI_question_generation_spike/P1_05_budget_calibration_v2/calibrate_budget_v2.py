"""P1-05-D · 单变量预算校准：max_tokens 8192 -> 16384。

单变量纪律（可机械验证）：
  * context / prompt 逐字节复用 P1-05-B #1（SHA256 断言）
  * model / temperature / thinking / reasoning_effort / response 形态
    **与 P1-05-C 完全一致**
  * 与 P1-05-C 的 payload 逐字段比对，**唯一差异必须是 max_tokens**

硬纪律：
  * api_calls = 1，retry_count = 0，不做第二次调用；
  * 套用 P1-05-C 的 generation_guard（截断即停，含 content 非空但截断的情形）；
  * 不写 question_library.db、不建 generation_run、不产生 AIQ:*。
"""
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DRY_RUN = "--dry-run" in sys.argv          # 只校验断言与单变量差异，不调用 API
SPIKE = os.path.join(r"D:\ZhixueEnglish", "audit", "AI_question_generation_spike")
RUNS = os.path.join(SPIKE, "P1_05_real_validation", "runs")
PROMPT_SRC = os.path.join(RUNS, "01_Unit2_UNDERSTANDING_IDEAS_prompt.json")
CTX_SRC = os.path.join(RUNS, "01_Unit2_UNDERSTANDING_IDEAS_context.json")
C_DIR = os.path.join(SPIKE, "P1_05_budget_calibration")          # 只读复用 P1-05-C
C_REQUEST = os.path.join(C_DIR, "calibration_request.json")
GUARD_DIR = C_DIR

MODEL = "deepseek-v4-pro"
ENDPOINT = "https://api.deepseek.com/chat/completions"
MAX_TOKENS = 16384          # 本轮唯一变量（P1-05-B / P1-05-C 均为 8192）
TEMPERATURE = 0.2
PROMPT_VERSION = "P1-05-v1"
REASONING_EFFORT = "low"                     # 与 P1-05-C 一致
THINKING = {"type": "enabled"}               # 与 P1-05-C 一致

sys.path.insert(0, GUARD_DIR)
import generation_guard as G  # noqa: E402


def sha(b):
    return hashlib.sha256(b).hexdigest().upper()


def sha_file(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest().upper()


def dump(name, obj):
    with open(os.path.join(HERE, name), "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)


PROTECTED = {
    "question_library.db": os.path.join(r"D:\ZhixueEnglish", "structured", "ai",
                                        "question_library.db"),
    "learning.db": os.path.join(r"D:\ZhixueEnglish", "structured", "learning", "learning.db"),
    "contentpack": os.path.join(r"D:\ZhixueEnglish", "structured", "contentpack", "v5",
                                "FLTRP-EN-7A-2022CUR.sqlite"),
    "validator_v2": os.path.join(SPIKE, "20260917_1520_validator_fix", "validator_v2.py"),
    "validator_v3": os.path.join(SPIKE, "P1_04_rule_fixes", "validator_v3.py"),
    "P1-05-A_matrix": os.path.join(SPIKE, "P1_05_sample_design", "p1_05_sample_matrix.json"),
    "P1-05-B_report": os.path.join(SPIKE, "P1_05_real_validation",
                                   "p1_05_real_validation_report.md"),
    "P1-05-C_report": os.path.join(C_DIR, "p1_05_budget_calibration_report.md"),
    "P1-05-C_request": C_REQUEST,
    "P1-05-C_response": os.path.join(C_DIR, "calibration_response.json"),
    "P1-05-C_guard": os.path.join(C_DIR, "generation_guard.py"),
}


def main():
    before = {k: sha_file(p) for k, p in PROTECTED.items()}

    saved = json.load(open(PROMPT_SRC, encoding="utf-8"))
    ctx = json.load(open(CTX_SRC, encoding="utf-8"))
    SYSTEM = saved["system_prompt"]
    USER = ("Textbook scope and evidence (JSON):\n" + json.dumps(ctx, ensure_ascii=False) +
            "\n\nGenerate questions for this Section now. Output JSON only.")

    asserts = {
        "system_prompt_sha256_expected": saved["system_prompt_sha256"],
        "system_prompt_sha256_rebuilt": sha(SYSTEM.encode()),
        "user_prompt_sha256_expected": saved["user_prompt_sha256"],
        "user_prompt_sha256_rebuilt": sha(USER.encode()),
        "context_hash_expected": saved["context_hash"],
        "user_prompt_len_expected": saved["user_prompt_len"],
        "user_prompt_len_rebuilt": len(USER),
    }
    asserts["context_and_prompt_identical"] = (
        asserts["system_prompt_sha256_expected"] == asserts["system_prompt_sha256_rebuilt"]
        and asserts["user_prompt_sha256_expected"] == asserts["user_prompt_sha256_rebuilt"]
        and asserts["user_prompt_len_expected"] == asserts["user_prompt_len_rebuilt"])
    if not asserts["context_and_prompt_identical"]:
        print("CALIBRATION_BLOCKED: 无法逐字节复现 P1-05-B #1 的上下文/提示词（未调用 API）")
        dump("calibration_result.json", {"final_status": "CALIBRATION_BLOCKED",
                                         "reason": "context_or_prompt_not_identical",
                                         "asserts": asserts, "api_calls": 0})
        return 2

    payload = {
        "model": MODEL, "temperature": TEMPERATURE, "max_tokens": MAX_TOKENS,
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": USER}],
        "thinking": THINKING, "reasoning_effort": REASONING_EFFORT,
    }

    # ---- 与 P1-05-C 的 payload 逐字段比对：唯一差异必须是 max_tokens
    prev = json.load(open(C_REQUEST, encoding="utf-8"))["payload"]
    diffs = []
    for k in sorted(set(payload) | set(prev)):
        a, b = prev.get(k), payload.get(k)
        if k == "max_tokens":
            continue
        if a != b:
            diffs.append({"field": k, "p1_05c": a, "p1_05d": b})
    single_variable = (not diffs
                       and prev.get("max_tokens") == 8192
                       and payload["max_tokens"] == 16384)

    dump("calibration_request.json", {
        "mode": "CALIBRATION_ONLY",
        "sample": saved["section_id"],
        "endpoint": ENDPOINT,
        "payload": payload,
        "max_tokens": MAX_TOKENS, "temperature": TEMPERATURE,
        "thinking": THINKING, "reasoning_effort": REASONING_EFFORT,
        "prompt_version": PROMPT_VERSION,
        "asserts": asserts,
        "single_variable_check": {
            "only_max_tokens_changed_vs_p1_05c": single_variable,
            "p1_05c_max_tokens": prev.get("max_tokens"),
            "p1_05d_max_tokens": payload["max_tokens"],
            "other_field_diffs": diffs,
        },
        "api_calls_allowed": 1,
    })
    if not single_variable:
        print("CALIBRATION_BLOCKED: 与 P1-05-C 的差异不止 max_tokens（未调用 API）")
        dump("calibration_result.json", {"final_status": "CALIBRATION_BLOCKED",
                                         "reason": "not_single_variable",
                                         "diffs": diffs, "api_calls": 0})
        return 3

    if DRY_RUN:
        print("[dry-run] 断言与单变量校验通过，未调用 API")
        print("  context_and_prompt_identical=true | only max_tokens changed 8192 -> 16384")
        return 0

    key = json.load(open(os.path.join(os.environ["USERPROFILE"], ".codex", "auth.json"),
                         encoding="utf-8"))["OPENAI_API_KEY"]
    req = urllib.request.Request(ENDPOINT, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer " + key})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=880) as resp:
            body = resp.read().decode("utf-8")
        latency_ms = int((time.time() - t0) * 1000)
        resp_obj = json.loads(body)
        api_error = None
    except urllib.error.HTTPError as exc:
        latency_ms = int((time.time() - t0) * 1000)
        detail = ""
        try:
            detail = exc.read().decode("utf-8")[:800]
        except Exception:
            pass
        resp_obj, api_error = None, "HTTPError %s: %s %s" % (exc.code, exc.reason, detail)
    except Exception as exc:
        latency_ms = int((time.time() - t0) * 1000)
        resp_obj, api_error = None, "%s: %s" % (type(exc).__name__, exc)

    dump("calibration_response.json", {
        "mode": "CALIBRATION_ONLY", "endpoint": ENDPOINT, "model": MODEL,
        "max_tokens_requested": MAX_TOKENS, "latency_ms": latency_ms,
        "api_calls": 1, "retry_count": 0, "api_error": api_error, "response": resp_obj,
    })
    print("调用完成 %.1fs  api_error=%s" % (latency_ms / 1000.0, api_error))

    # ---- generation_guard（截断即停）
    verdict = G.classify(resp_obj, api_error)
    print("guard:", G.summary_line(verdict))
    try:
        G.enforce(verdict)
        guard_decision = "PROCEED"
    except G.GenerationStop as stop:
        guard_decision = "STOP:%s" % stop.status
        print("guard 触发停止：%s（不解析 / 不入库 / 不 retry / 不继续）" % stop.detail)

    result = {
        "mode": "CALIBRATION_ONLY",
        "sample": saved["section_id"],
        "api_calls": 1, "retry_count": 0, "second_call_made": False,
        "http_ok": api_error is None,
        "api_error": api_error,
        "latency_ms": latency_ms,
        "request_delta_vs_p1_05c": {"only": "max_tokens 8192 -> 16384",
                                    "confirmed_by_field_diff": True},
        "guard": {"decision": guard_decision, "verdict": verdict},
        "truncated": verdict["status"] == G.STATUS_TRUNCATED,
        "json_parseable": False, "questions_field_present": False, "questions_count": 0,
        "structure_ok": None, "structure_notes": [],
        "wrote_to_question_library": False, "validator_entered": False,
        "final_status": None,
    }

    if resp_obj is not None and verdict["status"] == G.STATUS_OK:
        ch = (resp_obj.get("choices") or [{}])[0]
        content = (ch.get("message") or {}).get("content") or ""
        text = content.strip()
        if text.startswith("```"):
            import re
            text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        try:
            parsed = json.loads(text)
            result["json_parseable"] = True
        except Exception as exc:
            parsed = None
            result["structure_notes"].append("JSON 解析失败：%s" % exc)
        dump("calibration_parsed.json", parsed if parsed is not None else {"parse_failed": True})
        if isinstance(parsed, dict):
            result["questions_field_present"] = "questions" in parsed
            qs = parsed.get("questions") or []
            result["questions_count"] = len(qs)
            # 仅只读结构检查：不进入正式 validator 流程
            result["structure_ok"] = result["questions_field_present"] and isinstance(qs, list)
            if not qs:
                result["structure_notes"].append("questions 为空数组（预算校准允许；不代表质量结论）")
    elif verdict["status"] == G.STATUS_TRUNCATED:
        result["structure_notes"].append("截断：未解析、未校验、未入库")
    else:
        result["structure_notes"].append("调用失败或 content 为空：未解析、未校验、未入库")

    if result["truncated"] or api_error or not result["json_parseable"] \
            or not result["questions_field_present"]:
        result["final_status"] = "CALIBRATION_BLOCKED"
    else:
        result["final_status"] = "CALIBRATION_PASS"

    after = {k: sha_file(p) for k, p in PROTECTED.items()}
    result["protection"] = {
        "before": before, "after": after,
        "all_unchanged": before == after,
        "changed": [k for k in before if before[k] != after[k]],
    }
    if not result["protection"]["all_unchanged"]:
        result["final_status"] = "CALIBRATION_BLOCKED"
        result["structure_notes"].append(
            "保护项发生变化：%s" % result["protection"]["changed"])

    dump("calibration_result.json", result)
    print("最终状态：%s | questions=%d | json_parseable=%s | 保护项未变=%s" % (
        result["final_status"], result["questions_count"], result["json_parseable"],
        result["protection"]["all_unchanged"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
