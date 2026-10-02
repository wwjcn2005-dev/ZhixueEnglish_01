# -*- coding: utf-8 -*-
"""P1-11 Test B: AI quality review for FIX-C1 / FIX-C2 with Chinese summary.

Exactly ONE AI call for both fixtures (same batching as P1-09-F).
The program computes answer_unique; the model must not return it.
Writes: test_b_raw_response.json, review run file under structured/ai/quality_review/,
        test_b_result.json
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = r"D:\ZhixueEnglish"
SPIKE = os.path.join(BASE, "audit", "AI_question_generation_spike")
P1_09_D = os.path.join(SPIKE, "P1_09_D_boundary_validation")
sys.path.insert(0, HERE)
import p1_11_pipeline as P  # noqa: E402
import reviewer_prompt_p1_11 as RP  # noqa: E402

ENDPOINT = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-v4-pro"
MAX_TOKENS = 16384
GRADE = "外研版初中英语 七年级上册（初一第一学期）"
FIXTURE_SECTION = {"FIX-C1": "FLTRP-EN-7A-2022CUR:U2:UNDERSTANDING_IDEAS",
                   "FIX-C2": "FLTRP-EN-7A-2022CUR:U1:UNDERSTANDING_IDEAS"}
TARGETS = ["FIX-C1", "FIX-C2"]
LETTERS = ["A", "B", "C", "D"]


def build_items():
    fx = json.load(open(os.path.join(P1_09_D, "fixtures.json"), encoding="utf-8"))["fixtures"]
    items, meta = [], {}
    for f in fx:
        if f["fixture_id"] not in TARGETS:
            continue
        opts = [{"option": LETTERS[i], "text": t} for i, t in enumerate(f["options"])]
        items.append({
            "question_id": f["fixture_id"], "question_type": f["question_type"],
            "question_text": f["question"], "options": opts,
            "stored_answer": f["answer"], "answer_standard": f["answer_standard"],
            "textbook_location": f["location"],
            "textbook_evidence": [{"textbook_page": b["textbook_page"], "text": b["text"]}
                                  for b in f["textbook_context"]]})
        meta[f["fixture_id"]] = {"options": opts, "current_answer": f["answer"],
                                 "evidence_quote": f["textbook_context"][0]["text"]}
    return items, meta


def call_ai(system, user):
    payload = {"model": MODEL, "temperature": 0.2, "max_tokens": MAX_TOKENS,
               "messages": [{"role": "system", "content": system},
                            {"role": "user", "content": user}]}
    key = json.load(open(os.path.join(os.environ["USERPROFILE"], ".codex", "auth.json"),
                         encoding="utf-8"))["OPENAI_API_KEY"]
    req = urllib.request.Request(ENDPOINT, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer " + key})
    t0, resp_obj, api_error = time.time(), None, None
    try:
        with urllib.request.urlopen(req, timeout=900) as resp:
            body = resp.read().decode("utf-8")
        latency_ms = int((time.time() - t0) * 1000)
        resp_obj = json.loads(body)
    except urllib.error.HTTPError as exc:
        latency_ms = int((time.time() - t0) * 1000)
        api_error = "HTTPError %s: %s" % (exc.code, exc.reason)
    except Exception as exc:
        latency_ms = int((time.time() - t0) * 1000)
        api_error = "%s: %s" % (type(exc).__name__, exc)
    return resp_obj, api_error, latency_ms, payload


def main():
    items, meta = build_items()
    system = RP.SYSTEM_PROMPT
    user = RP.build_user_message(items, GRADE)
    raw_path = os.path.join(HERE, "test_b_raw_response.json")
    saved = None
    if "--reuse" in sys.argv and os.path.exists(raw_path):
        # the previous attempt already returned a complete response and saved it;
        # re-use it instead of spending a second API call
        saved = json.load(open(raw_path, encoding="utf-8"))
        resp_obj, api_error, latency_ms = saved["response"], saved["api_error"], saved["latency_ms"]
        reused = True
    else:
        resp_obj, api_error, latency_ms, payload = call_ai(system, user)
        reused = False

    usage = ((resp_obj or {}).get("usage") or {})
    details = usage.get("completion_tokens_details") or {}
    choice = ((resp_obj or {}).get("choices") or [{}])[0]
    finish = choice.get("finish_reason")
    content = (choice.get("message") or {}).get("content") or ""
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    parsed, status = None, "PARSED"
    if api_error:
        status = "API_ERROR"
    elif finish == "length":
        status = "TRUNCATED"
    elif not text:
        status = "EMPTY_CONTENT"
    else:
        try:
            parsed = json.loads(text)
        except Exception as exc:
            status, parsed = "INVALID_OUTPUT", None
            print("parse error:", exc)

    if not reused:
        with open(raw_path, "w", encoding="utf-8") as fh:
            json.dump({"endpoint": ENDPOINT, "model": MODEL, "max_tokens": MAX_TOKENS,
                       "api_calls": 1, "retry_count": 0, "api_error": api_error, "status": status,
                       "finish_reason": finish, "latency_ms": latency_ms,
                       "prompt_version": RP.REVIEW_VERSION, "system_sha256": P.sha(system),
                       "user_sha256": P.sha(user), "response": resp_obj}, fh,
                      ensure_ascii=False, indent=2)
    if status != "PARSED":
        raise SystemExit("Test B blocked: %s" % status)

    reviews_by_id = {r["question_id"]: r for r in parsed["items"]}
    records = []
    for it in items:
        qid = it["question_id"]
        raw = reviews_by_id[qid]
        cands = [{"candidate": c["option"], "candidate_text": c["candidate_text"],
                  "grammar_valid": str(c["grammar_valid"]).upper(),
                  "semantic_valid": str(c["semantic_valid"]).upper(),
                  "textbook_context_valid": str(c["textbook_context_valid"]).upper(),
                  "need_more_context": str(c["need_more_context"]).upper(),
                  "valid_alternative": str(c["valid_alternative"]).upper(),
                  "reason_cn": c["reason_cn"]} for c in raw["candidates"]]
        au = P.compute_answer_unique(it["question_type"], cands, meta[qid]["current_answer"])
        fp = P.fingerprint(FIXTURE_SECTION[qid], "", it["question_type"],
                           it["question_text"], meta[qid]["evidence_quote"])
        ctx_hash = P.review_context_hash([it])
        rec = {
            "question_id": qid, "question_fingerprint": fp,
            "review_context_hash": ctx_hash,
            "review_version": (saved or {}).get("prompt_version") if reused else RP.REVIEW_VERSION,
            "prompt_version_effective": (saved or {}).get("prompt_version") if reused
            else RP.REVIEW_VERSION,
            "prompt_version_current_source": RP.REVIEW_VERSION,
            "question_text": it["question_text"],
            "question_type": it["question_type"],
            "candidates": cands,
            "candidate_coverage": au["answer_unique_coverage"],
            "answer_unique": au["answer_unique"],
            "answer_unique_status": au["answer_unique_status"],
            "answer_unique_basis": au["basis"],
            "flagged_candidates": au.get("flagged_candidates", []),
            "english_correct": str(raw["english_correct"]).upper(),
            "naturalness": str(raw["naturalness"]).upper(),
            "learning_value": str(raw["learning_value"]).upper(),
            "distractor_quality": str(raw["distractor_quality"]).upper(),
            "grade_fit": str(raw["grade_fit"]).upper(),
            "suggested_decision": str(raw["suggested_decision"]).upper(),
            "summary_zh": raw["summary_zh"], "issues_zh": raw["issues_zh"],
            "evidence_note_zh": raw["evidence_note_zh"],
            "model": MODEL,
            "prompt_version": (saved or {}).get("prompt_version") if reused else RP.REVIEW_VERSION,
            "assessed_at": P.now(),
        }
        rec["safety"] = P.check_record_safety(rec)
        rec["human_view"] = P.human_view(rec)
        records.append(rec)

    run_id = "AIRV:%s:P111_B" % time.strftime("%Y%m%dT%H%M%S")
    path = P.write_review_run(run_id, records, meta={
        "fixtures": TARGETS, "source": "P1_09_D_boundary_validation/fixtures.json (verbatim)",
        "usage": usage, "latency_ms": latency_ms, "finish_reason": finish,
        "api_calls": 1, "retry_count": 0})

    result = {"stage": "P1-11", "test": "B_choice_review",
              "ai_calls": 0 if reused else 1, "retry_count": 0,
              "reused_saved_response": reused,
              "original_attempt_api_calls": 1,
              "status": status, "finish_reason": finish, "latency_ms": latency_ms,
              "tokens": {"input": usage.get("prompt_tokens"),
                         "output": usage.get("completion_tokens"),
                         "reasoning": details.get("reasoning_tokens"),
                         "total": usage.get("total_tokens")},
              "review_run_file": path, "reviews": records}
    with open(os.path.join(HERE, "test_b_result.json"), "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)

    print("status:", status, "| finish:", finish, "| latency_ms:", latency_ms)
    print("tokens:", result["tokens"])
    print("review file:", path)
    for r in records:
        print("---", r["question_id"], "| answer_unique:", r["answer_unique"],
              "/", r["answer_unique_status"], "| decision:", r["suggested_decision"])
        print("    flagged:", r["flagged_candidates"], "| coverage:", r["candidate_coverage"])
        print("    summary_zh:", r["summary_zh"])
        print("    issues_zh:", r["issues_zh"])
        print("    evidence_note_zh:", r["evidence_note_zh"])
        print("    safety:", r["safety"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
