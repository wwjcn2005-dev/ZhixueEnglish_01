# -*- coding: utf-8 -*-
"""P1-11 Test A: real 0-question Section -> SUCCESS_ZERO_QUESTIONS.

Reuses the already-validated P0 evidence-insufficient scenario verbatim:
  Unit 1 · DEVELOPING_IDEAS · Activity 1 (audio task, no transcript)
  the same input_context.json and the same system/user prompt text as that round.

Exactly ONE AI call. Writes: test_a_raw_response.json, test_a_result.json
"""

import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = r"D:\ZhixueEnglish"
P0_DIR = os.path.join(BASE, "audit", "AI_question_generation_spike",
                      "20260917_1650_evidence_insufficient")
sys.path.insert(0, HERE)
import p1_11_pipeline as P  # noqa: E402

ENDPOINT = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-v4-pro"
MAX_TOKENS = 8192
PROMPT_VERSION = "P0-v1-inssufficient-scenario"   # same prompt text as the P0 round
SECTION_ID = "FLTRP-EN-7A-2022CUR:U1:DEVELOPING_IDEAS"


def extract_prompt_text():
    """Read SYSTEM / USER assignments verbatim from the P0 runner (read-only reuse)."""
    src = open(os.path.join(P0_DIR, "run_insufficient_scenario.py"), encoding="utf-8").read()
    sys_m = re.search(r'SYSTEM = """(.*?)"""', src, re.S)
    usr_m = re.search(r'USER = \((.*?)\)\n', src, re.S)
    if not sys_m or not usr_m:
        raise RuntimeError("cannot extract the P0 prompt text verbatim")
    ctx = json.load(open(os.path.join(P0_DIR, "input_context.json"), encoding="utf-8"))
    ns = {"json": json, "ctx": ctx}
    exec("USER = (" + usr_m.group(1) + ")", ns)  # noqa: S102 - verbatim reuse
    return sys_m.group(1), ns["USER"], ctx


def main():
    system, user, ctx = extract_prompt_text()
    ctx_path = os.path.join(P0_DIR, "input_context.json")
    ctx_sha = hashlib.sha256(open(ctx_path, "rb").read()).hexdigest().upper()
    guard_dir = os.path.join(BASE, "audit", "AI_question_generation_spike",
                             "P1_05_budget_calibration")
    sys.path.insert(0, guard_dir)
    import generation_guard as G  # noqa: E402

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
        with urllib.request.urlopen(req, timeout=600) as resp:
            body = resp.read().decode("utf-8")
        latency_ms = int((time.time() - t0) * 1000)
        resp_obj = json.loads(body)
    except urllib.error.HTTPError as exc:
        latency_ms = int((time.time() - t0) * 1000)
        api_error = "HTTPError %s: %s" % (exc.code, exc.reason)
    except Exception as exc:
        latency_ms = int((time.time() - t0) * 1000)
        api_error = "%s: %s" % (type(exc).__name__, exc)

    verdict = G.classify(resp_obj, api_error)
    content = ((resp_obj or {}).get("choices") or [{}])[0].get("message", {}).get("content") or ""
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    parsed = None
    if verdict["status"] == G.STATUS_OK and text:
        try:
            parsed = json.loads(text)
        except Exception:
            parsed = None
    usage = verdict.get("usage") or {}
    details = usage.get("completion_tokens_details") or {}

    with open(os.path.join(HERE, "test_a_raw_response.json"), "w", encoding="utf-8") as fh:
        json.dump({"endpoint": ENDPOINT, "model": MODEL, "max_tokens": MAX_TOKENS,
                   "api_calls": 1, "retry_count": 0, "api_error": api_error,
                   "latency_ms": latency_ms, "guard_status": verdict["status"],
                   "finish_reason": verdict["finish_reason"], "context_sha256": ctx_sha,
                   "prompt_version": PROMPT_VERSION, "response": resp_obj}, fh,
                  ensure_ascii=False, indent=2)

    cls = P.classify_generation(verdict["status"], parsed, api_error)
    run_id = "AIRUN:%s:P111_ZERO" % time.strftime("%Y%m%dT%H%M%S")
    record = None
    if cls["outcome"] == P.SUCCESS_ZERO_QUESTIONS:
        record = P.record_generation_run(
            run_id=run_id,
            scope_key=P.sha("\x01".join([SECTION_ID, "", PROMPT_VERSION, ctx_sha])),
            section_id=SECTION_ID, unit_id="FLTRP-EN-7A-2022CUR:U1",
            model=MODEL, prompt_version=PROMPT_VERSION, context_hash=ctx_sha,
            context_ref="audit/AI_question_generation_spike/"
                        "20260917_1650_evidence_insufficient/input_context.json",
            raw_ref="audit/AI_question_generation_spike/P1_11/test_a_raw_response.json",
            finish_reason=verdict["finish_reason"], usage=usage, elapsed_ms=latency_ms,
            outcome=cls["outcome"], reason=cls["reason"], max_tokens=MAX_TOKENS,
            question_count=0)

    result = {"stage": "P1-11", "test": "A_zero_questions",
              "section_id": SECTION_ID, "ai_calls": 1, "retry_count": 0,
              "finish_reason": verdict["finish_reason"], "guard_status": verdict["status"],
              "latency_ms": latency_ms,
              "tokens": {"input": usage.get("prompt_tokens"),
                         "output": usage.get("completion_tokens"),
                         "reasoning": details.get("reasoning_tokens"),
                         "total": usage.get("total_tokens")},
              "questions_returned": 0 if parsed else None,
              "insufficient_reason": cls.get("reason"),
              "outcome": cls["outcome"],
              "generation_run_row": record,
              "context_sha256": ctx_sha, "prompt_version": PROMPT_VERSION}
    with open(os.path.join(HERE, "test_a_result.json"), "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
