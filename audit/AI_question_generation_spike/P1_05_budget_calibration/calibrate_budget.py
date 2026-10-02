"""P1-05-C · 单次隔离校准调用（CALIBRATION_ONLY）。

变量纪律：
  * context 与 prompt **逐字节复用** P1-05-B #1（Unit 2 · UNDERSTANDING_IDEAS），
    调用前用记录的 SHA256 断言验证；
  * model / temperature / max_tokens / response 格式**全部不变**；
  * **唯一新增**：reasoning 配置 `thinking={"type":"enabled"}` + `reasoning_effort="low"`
    （官方文档确认二者为顶层参数，见报告 §2）。

硬纪律：
  * 只允许 **1 次** DeepSeek 调用；不 retry；
  * **绝不**写入 question_library.db，不创建 generation_run，不产生 AIQ:*。
"""
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SPIKE = os.path.join(r"D:\ZhixueEnglish", "audit", "AI_question_generation_spike")
RUNS = os.path.join(SPIKE, "P1_05_real_validation", "runs")
PROMPT_SRC = os.path.join(RUNS, "01_Unit2_UNDERSTANDING_IDEAS_prompt.json")
CTX_SRC = os.path.join(RUNS, "01_Unit2_UNDERSTANDING_IDEAS_context.json")
VALIDATOR_DIR = os.path.join(SPIKE, "P1_04_rule_fixes")

MODEL = "deepseek-v4-pro"
ENDPOINT = "https://api.deepseek.com/chat/completions"
MAX_TOKENS = 8192          # 与 P1-05-B 完全一致，不放大
TEMPERATURE = 0.2
PROMPT_VERSION = "P1-05-v1"   # 内容不变；本轮只是校准调用，不产生新版本
REASONING_EFFORT = "low"
THINKING = {"type": "enabled"}

sys.path.insert(0, HERE)
import generation_guard as G  # noqa: E402
sys.path.insert(0, VALIDATOR_DIR)
import validator_v3 as V3  # noqa: E402


def sha(b):
    return hashlib.sha256(b).hexdigest().upper()


def dump(name, obj):
    with open(os.path.join(HERE, name), "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)


def main():
    saved = json.load(open(PROMPT_SRC, encoding="utf-8"))
    ctx = json.load(open(CTX_SRC, encoding="utf-8"))

    # ---- 逐字节复现 P1-05-B #1 的 system / user prompt，并用记录的 SHA 断言
    SYSTEM = saved["system_prompt"]
    USER = ("Textbook scope and evidence (JSON):\n" + json.dumps(ctx, ensure_ascii=False) +
            "\n\nGenerate questions for this Section now. Output JSON only.")
    asserts = {
        "system_prompt_sha256_expected": saved["system_prompt_sha256"],
        "system_prompt_sha256_rebuilt": sha(SYSTEM.encode()),
        "user_prompt_sha256_expected": saved["user_prompt_sha256"],
        "user_prompt_sha256_rebuilt": sha(USER.encode()),
        "user_prompt_len_expected": saved["user_prompt_len"],
        "user_prompt_len_rebuilt": len(USER),
        "context_hash_expected": saved["context_hash"],
        "context_hash_rebuilt": sha(json.dumps(ctx, ensure_ascii=False,
                                               sort_keys=True).encode()),
    }
    asserts["context_and_prompt_identical"] = (
        asserts["system_prompt_sha256_expected"] == asserts["system_prompt_sha256_rebuilt"]
        and asserts["user_prompt_sha256_expected"] == asserts["user_prompt_sha256_rebuilt"]
        and asserts["user_prompt_len_expected"] == asserts["user_prompt_len_rebuilt"])
    if not asserts["context_and_prompt_identical"]:
        print("CALIBRATION_BLOCKED: 无法逐字节复现 P1-05-B #1 的上下文/提示词")
        return 2

    payload = {
        "model": MODEL,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": USER}],
        # ---- 本轮唯一新增：reasoning 控制 ----
        "thinking": THINKING,
        "reasoning_effort": REASONING_EFFORT,
    }
    dump("calibration_request.json", {
        "mode": "CALIBRATION_ONLY",
        "sample": saved["section_id"],
        "endpoint": ENDPOINT,
        "payload": payload,
        "payload_note": ("与 P1-05-B #1 完全相同的 model/temperature/max_tokens/messages；"
                         "唯一差异是新增顶层 thinking 与 reasoning_effort"),
        "max_tokens": MAX_TOKENS, "temperature": TEMPERATURE,
        "reasoning_effort": REASONING_EFFORT, "thinking": THINKING,
        "prompt_version": PROMPT_VERSION,
        "asserts": asserts,
        "api_calls_allowed": 1,
    })

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
        resp_obj = None
        api_error = "HTTPError %s: %s %s" % (exc.code, exc.reason, detail)
    except Exception as exc:
        latency_ms = int((time.time() - t0) * 1000)
        resp_obj = None
        api_error = "%s: %s" % (type(exc).__name__, exc)

    dump("calibration_response.json", {
        "mode": "CALIBRATION_ONLY", "endpoint": ENDPOINT, "model": MODEL,
        "latency_ms": latency_ms, "api_calls": 1, "retry_count": 0,
        "api_error": api_error, "response": resp_obj,
    })
    print("调用完成 %.1fs  api_error=%s" % (latency_ms / 1000.0, api_error))

    # ---- 截断即停保护
    verdict = G.classify(resp_obj, api_error)
    print("guard:", G.summary_line(verdict))
    guard_decision = None
    try:
        G.enforce(verdict)
        guard_decision = "PROCEED"
    except G.GenerationStop as stop:
        guard_decision = "STOP:%s" % stop.status
        print("guard 触发停止：%s（不进入 validator / 不写题库 / 不 retry / 不继续）" % stop.detail)

    result = {
        "mode": "CALIBRATION_ONLY",
        "final_status": None,
        "sample": saved["section_id"],
        "api_calls": 1, "retry_count": 0, "second_call_made": False,
        "latency_ms": latency_ms,
        "request_delta_vs_p1_05b": {
            "added": ["thinking={'type':'enabled'}", "reasoning_effort='low'"],
            "unchanged": ["model", "temperature", "max_tokens=8192", "messages(system/user)",
                          "context", "prompt_version"],
        },
        "guard": {"decision": guard_decision, "verdict": verdict},
        "json_parseable": False, "questions_field_present": False,
        "questions_count": 0, "structure_ok": None, "structure_notes": [],
        "truncated": verdict["status"] == G.STATUS_TRUNCATED,
        "wrote_to_question_library": False,
        "validator_formal_run": False,
    }

    if resp_obj is not None and verdict["status"] == G.STATUS_OK:
        choice = (resp_obj.get("choices") or [{}])[0]
        content = (choice.get("message") or {}).get("content") or ""
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
        dump("calibration_parsed.json", parsed or {"parse_failed": True})
        if isinstance(parsed, dict):
            result["questions_field_present"] = "questions" in parsed
            qs = parsed.get("questions") or []
            result["questions_count"] = len(qs)
            # 只读结构检查（不进入正式 validator 流程）
            checks = []
            for i, q in enumerate(qs, 1):
                ok, reason = V3.type_rules(q)
                missing = [k for k in ("question", "answer", "unit", "section", "page",
                                       "evidence_block_ids", "evidence_quote")
                           if not q.get(k)]
                checks.append({"index": i, "type": q.get("type"), "type_rules_ok": ok,
                               "type_rules_reason": reason, "missing_fields": missing})
            result["structure_ok"] = bool(qs) and all(
                c["type_rules_ok"] and not c["missing_fields"] for c in checks)
            result["structure_checks"] = checks
            if not qs:
                result["structure_notes"].append(
                    "questions 为空数组（可能为证据不足的正常弃题，需结合 reasoning 判断）")
    elif verdict["status"] == G.STATUS_TRUNCATED:
        result["structure_notes"].append("截断：未解析、未校验、未入库")
    else:
        result["structure_notes"].append("调用失败或 content 为空：未解析、未校验、未入库")

    if result["truncated"] or api_error:
        result["final_status"] = "CALIBRATION_BLOCKED"
    elif result["json_parseable"] and result["questions_field_present"] and result["structure_ok"]:
        result["final_status"] = "CALIBRATION_PASS"
    else:
        result["final_status"] = "CALIBRATION_BLOCKED"
        if not result["structure_ok"]:
            result["structure_notes"].append("结构检查未通过")

    dump("calibration_result.json", result)
    print("最终状态：%s | questions=%d | json_parseable=%s" % (
        result["final_status"], result["questions_count"], result["json_parseable"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
