# -*- coding: utf-8 -*-
"""P1-09-D: ONE DeepSeek batch call over the 15 boundary fixtures.

Exactly one call per run of this script; no retry logic. A second call is only permitted by the
phase rules when the first failed at HTTP/service level with no analyzable content, and that
decision is made manually.

Usage: python run_review_d.py [attempt]
Writes: review_request.json, review_response.json, ai_review_output.json, call_accounting.json
"""

import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import reviewer_prompt_d as RP  # noqa: E402

ENDPOINT = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-v4-pro"
TEMPERATURE = 0.2
MAX_TOKENS = 16384
REASONING_EFFORT = "low"
THINKING = {"type": "enabled"}

ALLOWED = {
    "english_correct": {"PASS", "CONCERN", "FAIL"},
    "answer_unique": {"PASS", "CONCERN", "FAIL"},
    "naturalness": {"PASS", "CONCERN", "FAIL"},
    "learning_value": {"PASS", "CONCERN", "FAIL"},
    "distractor_quality": {"PASS", "CONCERN", "FAIL", "NOT_APPLICABLE"},
    "grade_fit": {"PASS", "CONCERN", "FAIL"},
    "mechanical_level": {"DIRECT_REPRODUCTION", "MECHANICAL_REWRITE", "RECOMBINED",
                         "NOT_APPLICABLE"},
    "suggested_decision": {"SUGGEST_ACCEPT", "SUGGEST_REVIEW", "SUGGEST_REJECT"},
    "context_status": {"SUFFICIENT", "CONTEXT_INSUFFICIENT"},
    "confidence": {"HIGH", "MEDIUM", "LOW"},
}
FORBIDDEN = ["score", "total_score", "ranking", "priority", "automatic_status", "approve",
             "activate", "APPROVED", "ACTIVE"]


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def dump(name, obj):
    with open(os.path.join(HERE, name), "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)


def main():
    attempt = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    blind = json.load(open(os.path.join(HERE, "ai_input_snapshot.json"), encoding="utf-8"))
    expected = [it["fixture_id"] for it in blind["items"]]

    system, user = RP.SYSTEM_PROMPT, RP.build_user_message(blind)
    payload = {"model": MODEL, "temperature": TEMPERATURE, "max_tokens": MAX_TOKENS,
               "messages": [{"role": "system", "content": system},
                            {"role": "user", "content": user}],
               "thinking": THINKING, "reasoning_effort": REASONING_EFFORT}
    dump("review_request.json", {
        "stage": "P1-09-D", "attempt": attempt, "endpoint": ENDPOINT,
        "prompt_version": RP.REVIEW_VERSION, "model": MODEL, "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS, "thinking": THINKING, "reasoning_effort": REASONING_EFFORT,
        "system_prompt_sha256": sha(system), "user_prompt_sha256": sha(user),
        "ai_input_snapshot_sha256": sha(json.dumps(blind, ensure_ascii=False, sort_keys=True)),
        "fixture_count": len(expected), "payload": payload})

    key = json.load(open(os.path.join(os.environ["USERPROFILE"], ".codex", "auth.json"),
                         encoding="utf-8"))["OPENAI_API_KEY"]
    req = urllib.request.Request(
        ENDPOINT, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})

    t0, resp_obj, api_error = time.time(), None, None
    try:
        with urllib.request.urlopen(req, timeout=900) as resp:
            body = resp.read().decode("utf-8")
        latency_ms = int((time.time() - t0) * 1000)
        try:
            resp_obj = json.loads(body)
        except Exception as exc:
            api_error = "response body is not JSON: %s" % exc
    except urllib.error.HTTPError as exc:
        latency_ms = int((time.time() - t0) * 1000)
        detail = ""
        try:
            detail = exc.read().decode("utf-8")[:800]
        except Exception:
            pass
        api_error = "HTTPError %s: %s %s" % (exc.code, exc.reason, detail)
    except Exception as exc:
        latency_ms = int((time.time() - t0) * 1000)
        api_error = "%s: %s" % (type(exc).__name__, exc)

    dump("review_response.json", {"stage": "P1-09-D", "attempt": attempt, "endpoint": ENDPOINT,
                                  "model": MODEL, "requested_max_tokens": MAX_TOKENS,
                                  "latency_ms": latency_ms, "api_calls": 1, "retry_count": 0,
                                  "api_error": api_error, "response": resp_obj})

    usage = ((resp_obj or {}).get("usage") or {})
    details = usage.get("completion_tokens_details") or {}
    choice = ((resp_obj or {}).get("choices") or [{}])[0]
    message = choice.get("message") or {}
    finish_reason = choice.get("finish_reason")
    content = message.get("content") or ""
    reasoning = message.get("reasoning_content") or ""

    accounting = {"stage": "P1-09-D", "attempt": attempt, "api_calls": 1, "retry_count": 0,
                  "model": MODEL, "temperature": TEMPERATURE, "max_tokens": MAX_TOKENS,
                  "reasoning_effort": REASONING_EFFORT, "thinking": THINKING,
                  "prompt_version": RP.REVIEW_VERSION, "latency_ms": latency_ms,
                  "finish_reason": finish_reason, "api_error": api_error,
                  "prompt_tokens": usage.get("prompt_tokens"),
                  "completion_tokens": usage.get("completion_tokens"),
                  "reasoning_tokens": details.get("reasoning_tokens"),
                  "total_tokens": usage.get("total_tokens"),
                  "content_chars": len(content), "reasoning_chars": len(reasoning),
                  "fixture_count": len(expected)}

    status, notes, parsed = None, [], None
    if api_error and not content:
        status = "API_ERROR"
        notes.append(api_error)
    elif finish_reason == "length":
        status = "TRUNCATED"
        notes.append("finish_reason=length：立即停止，不解析、不补救、不重试")
    elif not content.strip():
        status = "API_ERROR"
        notes.append("content 为空")
    else:
        text = content.strip()
        if text.startswith("```"):
            import re
            text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        try:
            parsed = json.loads(text)
            status = "PARSED"
        except Exception as exc:
            status = "INVALID_OUTPUT"
            notes.append("JSON 解析失败：%s" % exc)

    if status == "PARSED":
        reviews = parsed.get("reviews")
        if not isinstance(reviews, list):
            status, _ = "INVALID_OUTPUT", notes.append("缺少 reviews 数组")
        else:
            got = [r.get("fixture_id") for r in reviews]
            missing = [i for i in expected if i not in got]
            extra = [i for i in got if i not in expected]
            dup = sorted({i for i in got if got.count(i) > 1})
            if missing or extra or dup:
                status = "INCOMPLETE"
                notes.append("缺少=%s 多出=%s 重复=%s" % (missing, extra, dup))
            bad_enum, bad_field = [], []
            for r in reviews:
                for k, allowed in ALLOWED.items():
                    if r.get(k) not in allowed:
                        bad_enum.append((r.get("fixture_id"), k, r.get(k)))
                for f in FORBIDDEN:
                    if f in r:
                        bad_field.append((r.get("fixture_id"), f))
                if not isinstance(r.get("short_reason"), str) or not r["short_reason"].strip():
                    bad_enum.append((r.get("fixture_id"), "short_reason", r.get("short_reason")))
            if bad_enum:
                status = "INVALID_OUTPUT"
                notes.append("非法取值：%s" % bad_enum)
            if bad_field:
                status = "INVALID_OUTPUT"
                notes.append("出现禁止字段：%s" % bad_field)
            if status == "PARSED":
                dump("ai_review_output.json", {
                    "stage": "P1-09-D", "prompt_version": RP.REVIEW_VERSION, "model": MODEL,
                    "fixture_count": len(reviews), "raw_review_version": parsed.get("review_version"),
                    "raw_object_keys": sorted(parsed.keys()), "reviews": reviews})

    accounting["status"] = status
    accounting["notes"] = notes
    dump("call_accounting.json", accounting)

    print("attempt      :", attempt)
    print("api_calls    : 1   retry_count: 0")
    print("finish_reason:", finish_reason)
    print("latency_ms   :", latency_ms)
    print("tokens       : prompt=%s completion=%s reasoning=%s total=%s"
          % (usage.get("prompt_tokens"), usage.get("completion_tokens"),
             details.get("reasoning_tokens"), usage.get("total_tokens")))
    print("content_chars:", len(content), " reasoning_chars:", len(reasoning))
    print("status       :", status)
    for n in notes:
        print("  note:", n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
