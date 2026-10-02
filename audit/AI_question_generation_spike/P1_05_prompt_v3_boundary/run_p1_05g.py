"""P1-05-G · 单次调用 P1-05-v3（恢复合理 Fill + 教材素材边界 + 去元语言）。

与 P1-05-F 的对照纪律：教材 context 逐字节相同；model / temperature / max_tokens(16384) /
thinking / reasoning_effort(low) 全部不变；**唯一变量 = system prompt（v2 -> v3）**。
1 次调用、不 retry；finish_reason=length 即停止；不写 question_library.db。
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
CTX_SRC = os.path.join(RUNS, "01_Unit2_UNDERSTANDING_IDEAS_context.json")
F_REQUEST = os.path.join(SPIKE, "P1_05_prompt_v2_textbook_focus", "p1_05f_request.json")
GUARD_DIR = os.path.join(SPIKE, "P1_05_budget_calibration")

MODEL = "deepseek-v4-pro"
ENDPOINT = "https://api.deepseek.com/chat/completions"
MAX_TOKENS = 16384
TEMPERATURE = 0.2
REASONING_EFFORT = "low"
THINKING = {"type": "enabled"}
PROMPT_VERSION = "P1-05-v3"
DRY_RUN = "--dry-run" in sys.argv

sys.path.insert(0, HERE)
sys.path.insert(0, GUARD_DIR)
import prompt_v3 as P  # noqa: E402
import generation_guard as G  # noqa: E402


def sha(b):
    return hashlib.sha256(b).hexdigest().upper()


def sha_file(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest().upper()


def dump(name, obj):
    with open(os.path.join(HERE, name), "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)


def protected_files():
    out = {}
    for sub in ["P1_05_sample_design", "P1_05_real_validation", "P1_05_budget_calibration",
                "P1_05_budget_calibration_v2", "P1_05_manual_review",
                "P1_05_prompt_v2_textbook_focus", "P1_04_rule_fixes",
                "20260917_1520_validator_fix"]:
        p = os.path.join(SPIKE, sub)
        if not os.path.isdir(p):
            continue
        for f in sorted(os.listdir(p)):
            fp = os.path.join(p, f)
            if os.path.isfile(fp):
                out["%s/%s" % (sub, f)] = fp
    out["question_library.db"] = os.path.join(r"D:\ZhixueEnglish", "structured", "ai",
                                              "question_library.db")
    out["learning.db"] = os.path.join(r"D:\ZhixueEnglish", "structured", "learning", "learning.db")
    out["contentpack"] = os.path.join(r"D:\ZhixueEnglish", "structured", "contentpack", "v5",
                                      "FLTRP-EN-7A-2022CUR.sqlite")
    for f in sorted(os.listdir(os.path.join(r"D:\ZhixueEnglish", "structured", "textbook"))):
        fp = os.path.join(r"D:\ZhixueEnglish", "structured", "textbook", f)
        if os.path.isfile(fp):
            out["structured/textbook/%s" % f] = fp
    return out


def main():
    prot = protected_files()
    before = {k: sha_file(p) for k, p in prot.items()}
    print("[0] 保护对象 %d 个文件" % len(prot))

    system_v3, system_v2, user, checks = P.build_v3()
    if not all([checks["old_fill_found"] == 1, checks["anchor_found"] == 1,
                checks["contains_new_fill"], checks["contains_boundary"],
                checks["contains_no_meta"]]):
        dump("p1_05g_result.json", {"final_status": "P1_05_G_BLOCKED", "prompt_checks": checks})
        print("P1_05_G_BLOCKED: v3 提示词构建校验失败")
        return 2

    prev = json.load(open(F_REQUEST, encoding="utf-8"))["payload"]
    cur = {"model": MODEL, "temperature": TEMPERATURE, "max_tokens": MAX_TOKENS,
           "messages": [{"role": "system", "content": system_v3},
                        {"role": "user", "content": user}],
           "thinking": THINKING, "reasoning_effort": REASONING_EFFORT}
    diffs = []
    for k in sorted(set(prev) | set(cur)):
        a, b = prev.get(k), cur.get(k)
        if k == "messages":
            if a[1] != b[1]:
                diffs.append({"field": "messages[1](user prompt)"})
            if a[0] != b[0]:
                diffs.append({"field": "messages[0](system prompt)",
                              "from": "P1-05-v2", "to": PROMPT_VERSION})
            continue
        if a != b:
            diffs.append({"field": k, "p1_05f": a, "p1_05g": b})

    req_doc = {"mode": "TEXTBOOK_FOCUS_V3", "prompt_version": PROMPT_VERSION,
               "sample": "FLTRP-EN-7A-2022CUR:U2:UNDERSTANDING_IDEAS",
               "endpoint": ENDPOINT, "payload": cur,
               "system_prompt_sha256": sha(system_v3.encode()),
               "p1_05v2_system_prompt_sha256": sha(system_v2.encode()),
               "user_prompt_sha256": sha(user.encode()),
               "context_sha256": sha_file(CTX_SRC),
               "prompt_checks": checks,
               "applied_corrections": {
                   "correction_1_restore_fill": {"old": P.OLD_FILL, "new": P.NEW_FILL},
                   "correction_2_material_boundary_no_meta_language": P.NEW_SECTIONS},
               "prompt_diff_vs_p1_05f": diffs,
               "only_system_prompt_changed": (len(diffs) == 1
                                              and diffs[0]["field"] == "messages[0](system prompt)"),
               "api_calls_allowed": 1}
    dump("p1_05g_request.json", req_doc)
    print("[1] 与 P1-05-F 的差异：%s | v3 system 长度 %d（v2 %d）" % (
        [d["field"] for d in diffs], len(system_v3), len(system_v2)))
    if not req_doc["only_system_prompt_changed"]:
        dump("p1_05g_result.json", {"final_status": "P1_05_G_BLOCKED", "diffs": diffs})
        print("P1_05_G_BLOCKED：变量不单一（未调用 API）")
        return 2
    if DRY_RUN:
        print("[dry-run] 通过，未调用 API")
        return 0

    key = json.load(open(os.path.join(os.environ["USERPROFILE"], ".codex", "auth.json"),
                         encoding="utf-8"))["OPENAI_API_KEY"]
    req = urllib.request.Request(ENDPOINT, data=json.dumps(cur).encode(),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer " + key})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=880) as resp:
            body = resp.read().decode("utf-8")
        latency_ms = int((time.time() - t0) * 1000)
        resp_obj, api_error = json.loads(body), None
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

    dump("p1_05g_response.json", {"mode": "TEXTBOOK_FOCUS_V3", "endpoint": ENDPOINT,
                                  "model": MODEL, "max_tokens_requested": MAX_TOKENS,
                                  "latency_ms": latency_ms, "api_calls": 1, "retry_count": 0,
                                  "api_error": api_error, "response": resp_obj})
    print("[2] 调用完成 %.1fs api_error=%s" % (latency_ms / 1000.0, api_error))

    verdict = G.classify(resp_obj, api_error)
    print("[3] guard:", G.summary_line(verdict))
    try:
        G.enforce(verdict)
        decision = "PROCEED"
    except G.GenerationStop as stop:
        decision = "STOP:%s" % stop.status
        print("    guard 触发停止：%s（不解析 / 不入库 / 不 retry）" % stop.detail)

    result = {"mode": "TEXTBOOK_FOCUS_V3", "prompt_version": PROMPT_VERSION,
              "api_calls": 1, "retry_count": 0, "api_error": api_error,
              "latency_ms": latency_ms, "guard_decision": decision,
              "truncated": verdict["status"] == G.STATUS_TRUNCATED,
              "json_parseable": False, "questions_count": 0,
              "wrote_to_question_library": False, "final_status": None}
    if verdict["status"] == G.STATUS_OK:
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
            dump("p1_05g_parsed.json", parsed)
            result["questions_count"] = len(parsed.get("questions") or [])
            result["questions_field_present"] = "questions" in parsed
        except Exception as exc:
            result["parse_error"] = str(exc)
            dump("p1_05g_parsed.json", {"parse_failed": True})
    else:
        result["note"] = "TRUNCATED/EMPTY：未解析、未入库、不重试"

    after = {k: sha_file(p) for k, p in prot.items()}
    result["protection"] = {"checked_files": len(prot), "all_unchanged": before == after,
                            "changed": [k for k in before if before[k] != after[k]]}
    ok = (not api_error and verdict["status"] == G.STATUS_OK and result["json_parseable"]
          and result.get("questions_field_present") and result["protection"]["all_unchanged"])
    result["final_status"] = "P1_05_G_PASS" if ok else "P1_05_G_BLOCKED"
    dump("p1_05g_result.json", result)
    print("[4] 最终状态：%s | 题数=%d | 保护项(%d 文件)未变=%s" % (
        result["final_status"], result["questions_count"],
        result["protection"]["checked_files"], result["protection"]["all_unchanged"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
