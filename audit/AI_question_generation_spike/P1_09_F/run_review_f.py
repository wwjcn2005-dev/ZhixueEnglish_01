# -*- coding: utf-8 -*-
"""P1-09-F: one DeepSeek call for per-option judgement, then program-side aggregation.

Exactly one API call. The model never returns an overall verdict; the program computes
UNIQUE_RISK / UNIQUE_UNCERTAIN / UNIQUE_SUPPORTED from the per-candidate fields.

Writes: review_request.json, review_response.json, ai_review_output.json,
        call_accounting.json, assessment.json
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
import reviewer_prompt_f as RP  # noqa: E402

ENDPOINT = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-v4-pro"
TEMPERATURE = 0.2
MAX_TOKENS = 16384
REASONING_EFFORT = "low"
THINKING = {"type": "enabled"}

YN = {"YES", "NO"}
YNU = {"YES", "NO", "UNKNOWN"}
FORBIDDEN_FIELDS = ["unique", "assessment", "score", "total_score", "ranking", "priority",
                    "approve", "activate", "automatic_status", "accepted", "rejected"]


def canonical(o):
    return hashlib.sha256(
        json.dumps(o, ensure_ascii=False, sort_keys=True).encode()).hexdigest().upper()


def dump(name, obj):
    with open(os.path.join(HERE, name), "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)


def norm(v):
    return str(v or "").strip().upper()


def main():
    blind = json.load(open(os.path.join(HERE, "ai_input_snapshot.json"), encoding="utf-8"))
    cmap = json.load(open(os.path.join(HERE, "candidate_map.json"),
                          encoding="utf-8"))["candidate_map"]
    expected = [it["question_id"] for it in blind["items"]]

    system, user = RP.SYSTEM_PROMPT, RP.build_user_message(blind)
    payload = {"model": MODEL, "temperature": TEMPERATURE, "max_tokens": MAX_TOKENS,
               "messages": [{"role": "system", "content": system},
                            {"role": "user", "content": user}],
               "thinking": THINKING, "reasoning_effort": REASONING_EFFORT}
    dump("review_request.json", {
        "stage": "P1-09-F", "endpoint": ENDPOINT, "prompt_version": RP.REVIEW_VERSION,
        "model": MODEL, "temperature": TEMPERATURE, "max_tokens": MAX_TOKENS,
        "thinking": THINKING, "reasoning_effort": REASONING_EFFORT,
        "system_prompt_sha256": canonical({"s": system}),
        "user_prompt_sha256": canonical({"u": user}),
        "ai_input_sha256": canonical(blind), "fixture_count": len(expected), "payload": payload})

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

    dump("review_response.json", {"stage": "P1-09-F", "endpoint": ENDPOINT, "model": MODEL,
                                  "requested_max_tokens": MAX_TOKENS, "latency_ms": latency_ms,
                                  "api_calls": 1, "retry_count": 0, "api_error": api_error,
                                  "response": resp_obj})

    usage = ((resp_obj or {}).get("usage") or {})
    details = usage.get("completion_tokens_details") or {}
    choice = ((resp_obj or {}).get("choices") or [{}])[0]
    message = choice.get("message") or {}
    finish_reason = choice.get("finish_reason")
    content = message.get("content") or ""
    reasoning = message.get("reasoning_content") or ""

    accounting = {"stage": "P1-09-F", "api_calls": 1, "retry_count": 0, "model": MODEL,
                  "temperature": TEMPERATURE, "max_tokens": MAX_TOKENS,
                  "reasoning_effort": REASONING_EFFORT, "prompt_version": RP.REVIEW_VERSION,
                  "latency_ms": latency_ms, "finish_reason": finish_reason, "api_error": api_error,
                  "input_tokens": usage.get("prompt_tokens"),
                  "output_tokens": usage.get("completion_tokens"),
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
        items = parsed.get("items")
        if not isinstance(items, list):
            status = "INVALID_OUTPUT"
            notes.append("缺少 items 数组")
        else:
            got = [i.get("question_id") for i in items]
            if [g for g in got if g not in expected] or [e for e in expected if e not in got]:
                status = "INCOMPLETE"
                notes.append("题目不匹配：got=%s expected=%s" % (got, expected))
            bad, bad_fields = [], []
            for i in items:
                qid = i.get("question_id")
                n_expected = cmap[qid]["options_count"]
                cands = i.get("candidates") or []
                if len(cands) != n_expected:
                    bad.append((qid, "candidate_count", len(cands), n_expected))
                for c in cands:
                    if norm(c.get("grammar_valid")) not in YNU:
                        bad.append((qid, "grammar_valid", c.get("grammar_valid")))
                    if norm(c.get("semantic_valid")) not in YNU:
                        bad.append((qid, "semantic_valid", c.get("semantic_valid")))
                    if norm(c.get("textbook_context_valid")) not in YNU:
                        bad.append((qid, "textbook_context_valid", c.get("textbook_context_valid")))
                    if norm(c.get("need_more_context")) not in YN:
                        bad.append((qid, "need_more_context", c.get("need_more_context")))
                    if norm(c.get("valid_alternative")) not in YNU:
                        bad.append((qid, "valid_alternative", c.get("valid_alternative")))
                    if not str(c.get("reason_cn") or "").strip():
                        bad.append((qid, "reason_cn", "empty"))
                    for f in FORBIDDEN_FIELDS:
                        if f in c or f in i:
                            bad_fields.append((qid, f))
            if bad:
                status = "INVALID_OUTPUT"
                notes.append("非法取值：%s" % bad)
            if bad_fields:
                status = "INVALID_OUTPUT"
                notes.append("模型返回了禁止字段：%s" % sorted(set(bad_fields)))
            if status == "PARSED":
                dump("ai_review_output.json", {
                    "stage": "P1-09-F", "prompt_version": RP.REVIEW_VERSION, "model": MODEL,
                    "raw_review_version": parsed.get("review_version"),
                    "raw_object_keys": sorted(parsed.keys()), "items": items})

    accounting["status"] = status
    accounting["notes"] = notes
    dump("call_accounting.json", accounting)

    print("api_calls: 1  retry_count: 0  finish_reason:", finish_reason, " status:", status)
    print("latency_ms:", latency_ms, "| tokens in/out/reasoning/total: %s/%s/%s/%s"
          % (usage.get("prompt_tokens"), usage.get("completion_tokens"),
             details.get("reasoning_tokens"), usage.get("total_tokens")))
    for n in notes:
        print("  note:", n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
