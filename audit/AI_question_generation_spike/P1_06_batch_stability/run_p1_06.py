"""P1-06 · 批量稳定性验证：用冻结的 P1-05-v3 在 4 个不同类型的 Section 上各调用 1 次。

纪律：
  * system prompt 固定为 P1-05-v3；**每 Section 只替换末尾的 page/activity 适用范围行**
    （这是 P1-05-F/G 已确立的参数化，不是修改提示词；除该行外与 P1-05-G 的 v3 完全一致）
  * context 复用 P1-05-B 已构建的同 Section context（逐字节，记录 SHA256）
  * 每个 Section 1 次调用、retry=0；任一 Section 出现 finish_reason=length 立即终止后续调用
  * 不写 question_library.db；不改任何既有产物
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
V3_REQUEST = os.path.join(SPIKE, "P1_05_prompt_v3_boundary", "p1_05g_request.json")
GUARD_DIR = os.path.join(SPIKE, "P1_05_budget_calibration")

MODEL = "deepseek-v4-pro"
ENDPOINT = "https://api.deepseek.com/chat/completions"
MAX_TOKENS = 16384
TEMPERATURE = 0.2
REASONING_EFFORT = "low"
THINKING = {"type": "enabled"}
PROMPT_VERSION = "P1-05-v3"
DRY_RUN = "--dry-run" in sys.argv

SECTIONS = [
    dict(tag="S1", prefix="01", name="Unit2_UNDERSTANDING_IDEAS", category="RICH_READING (基准)"),
    dict(tag="S2", prefix="03", name="Unit1_UNDERSTANDING_IDEAS", category="DIALOGUE / B"),
    dict(tag="S3", prefix="04", name="Unit5_UNDERSTANDING_IDEAS", category="VOCABULARY / Language use"),
    dict(tag="S4", prefix="05", name="Starter_GET_READY", category="INFO_MATCH + 部分音频证据"),
]

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


def protected_files():
    out = {}
    for sub in ["P1_05_sample_design", "P1_05_real_validation", "P1_05_budget_calibration",
                "P1_05_budget_calibration_v2", "P1_05_manual_review",
                "P1_05_prompt_v2_textbook_focus", "P1_05_prompt_v3_boundary",
                "P1_04_rule_fixes", "20260917_1520_validator_fix"]:
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


def build_system(v3_base, pages, acts):
    """把 v3 末尾的 page/activity 行换成该 Section 的真实范围（唯一按 Section 变化的行）。"""
    lines = v3_base.splitlines()
    idx = [i for i, l in enumerate(lines) if l.startswith("page must be one of ")]
    if len(idx) != 1:
        raise RuntimeError("找不到唯一的 page/activity 行：%d" % len(idx))
    lines[idx[0]] = ("page must be one of %s and activity must be one of %s (or null)."
                     % (",".join(str(p) for p in pages), ",".join(str(a) for a in acts)))
    return "\n".join(lines)


def main():
    prot = protected_files()
    before = {k: sha_file(p) for k, p in prot.items()}
    print("[0] 保护对象 %d 个文件" % len(prot))

    v3_base = json.load(open(V3_REQUEST, encoding="utf-8"))["payload"]["messages"][0]["content"]
    key = json.load(open(os.path.join(os.environ["USERPROFILE"], ".codex", "auth.json"),
                         encoding="utf-8"))["OPENAI_API_KEY"]

    overall = {"stage": "P1-06", "prompt_version": PROMPT_VERSION, "model": MODEL,
               "max_tokens": MAX_TOKENS, "sections": [], "stopped": None,
               "api_calls": 0, "retry_count": 0}
    calls = 0
    for sec in SECTIONS:
        if calls >= 4:
            overall["stopped"] = "已达 4 次调用上限"
            break
        pf = os.path.join(RUNS, [f for f in os.listdir(RUNS)
                                 if f.startswith(sec["prefix"] + "_") and f.endswith("_prompt.json")][0])
        cf = os.path.join(RUNS, [f for f in os.listdir(RUNS)
                                 if f.startswith(sec["prefix"] + "_") and f.endswith("_context.json")][0])
        meta = json.load(open(pf, encoding="utf-8"))
        ctx = json.load(open(cf, encoding="utf-8"))
        SYSTEM = build_system(v3_base, meta["pages"], meta["activity_nos"])
        USER = ("Textbook scope and evidence (JSON):\n" + json.dumps(ctx, ensure_ascii=False) +
                "\n\nGenerate questions for this Section now. Output JSON only.")
        payload = {"model": MODEL, "temperature": TEMPERATURE, "max_tokens": MAX_TOKENS,
                   "messages": [{"role": "system", "content": SYSTEM},
                                {"role": "user", "content": USER}],
                   "thinking": THINKING, "reasoning_effort": REASONING_EFFORT}
        dump("%s_request.json" % sec["tag"],
             {"tag": sec["tag"], "section_id": meta["section_id"], "category": sec["category"],
              "prompt_version": PROMPT_VERSION, "endpoint": ENDPOINT, "payload": payload,
              "system_prompt_sha256": sha(SYSTEM.encode()),
              "user_prompt_sha256": sha(USER.encode()),
              "context_sha256": sha_file(cf),
              "pages": meta["pages"], "activity_nos": meta["activity_nos"],
              "blocks": meta["blocks"], "packages": meta["packages"]})

        req = urllib.request.Request(ENDPOINT, data=json.dumps(payload).encode(),
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
        calls += 1
        overall["api_calls"] = calls
        dump("%s_response.json" % sec["tag"],
             {"tag": sec["tag"], "section_id": meta["section_id"], "endpoint": ENDPOINT,
              "model": MODEL, "max_tokens_requested": MAX_TOKENS, "latency_ms": latency_ms,
              "api_calls": 1, "retry_count": 0, "api_error": api_error, "response": resp_obj})

        verdict = G.classify(resp_obj, api_error)
        try:
            G.enforce(verdict)
            decision = "PROCEED"
        except G.GenerationStop as stop:
            decision = "STOP:%s" % stop.status

        u = ((resp_obj or {}).get("usage") or {})
        det = u.get("completion_tokens_details") or {}
        rec = {"tag": sec["tag"], "section_id": meta["section_id"], "category": sec["category"],
               "latency_ms": latency_ms, "finish_reason": verdict["finish_reason"],
               "guard": decision, "truncated": verdict["status"] == G.STATUS_TRUNCATED,
               "source_blocks": meta["blocks"], "source_packages": meta["packages"],
               "prompt_tokens": u.get("prompt_tokens"), "completion_tokens": u.get("completion_tokens"),
               "reasoning_tokens": det.get("reasoning_tokens"), "total_tokens": u.get("total_tokens"),
               "api_error": api_error}
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
                dump("%s_parsed.json" % sec["tag"], parsed)
                rec["questions_count"] = len(parsed.get("questions") or [])
                rec["parsed"] = True
            except Exception as exc:
                dump("%s_parsed.json" % sec["tag"], {"parse_failed": True, "raw": text[:500]})
                rec["questions_count"] = 0
                rec["parsed"] = False
                rec["parse_error"] = str(exc)
        else:
            rec["questions_count"] = 0
            rec["parsed"] = False
        overall["sections"].append(rec)
        print("[%s] %-24s %-6s gen=%s  %.1fs  p=%s c=%s r=%s" % (
            sec["tag"], sec["name"], verdict["finish_reason"], rec["questions_count"],
            latency_ms / 1000.0, rec["prompt_tokens"], rec["completion_tokens"],
            rec["reasoning_tokens"]))

        if verdict["status"] != G.STATUS_OK:
            overall["stopped"] = "%s 出现 %s，按纪律终止后续调用" % (sec["tag"], verdict["status"])
            break

    after = {k: sha_file(p) for k, p in prot.items()}
    overall["protection"] = {"checked_files": len(prot), "all_unchanged": before == after,
                             "changed": [k for k in before if before[k] != after[k]]}
    overall["formal_assets_changed"] = not overall["protection"]["all_unchanged"]
    overall["total_tokens"] = sum(s.get("total_tokens") or 0 for s in overall["sections"])
    overall["total_latency_ms"] = sum(s.get("latency_ms") or 0 for s in overall["sections"])
    overall["total_questions"] = sum(s.get("questions_count") or 0 for s in overall["sections"])
    dump("p1_06_result.json", overall)
    print("总调用 %d 次 | 总题数 %d | 总 token %d | 保护项未变=%s" % (
        overall["api_calls"], overall["total_questions"], overall["total_tokens"],
        overall["protection"]["all_unchanged"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
