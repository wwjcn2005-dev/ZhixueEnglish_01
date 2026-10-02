"""P1-05-F · 以教材学习重点为核心出题：prompt_version = P1-05-v2（单次调用）。

与 P1-05-D 的对照纪律：
  * 教材 evidence / context **逐字节相同**（SHA256 断言）
  * model / temperature / max_tokens(16384) / thinking / reasoning_effort(low) 全部不变
  * **唯一变量**：system prompt 的题型指导块 → P1-05-v2（教材学习重点优先 + 反机械复制）
  * 1 次调用、不 retry；finish_reason=length → 立即 TRUNCATED，不解析
  * **不写 question_library.db**，不改 P1-05-D 原始结果
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
V1_PROMPT = os.path.join(RUNS, "01_Unit2_UNDERSTANDING_IDEAS_prompt.json")
CTX_SRC = os.path.join(RUNS, "01_Unit2_UNDERSTANDING_IDEAS_context.json")
D_REQUEST = os.path.join(SPIKE, "P1_05_budget_calibration_v2", "calibration_request.json")
GUARD_DIR = os.path.join(SPIKE, "P1_05_budget_calibration")

MODEL = "deepseek-v4-pro"
ENDPOINT = "https://api.deepseek.com/chat/completions"
MAX_TOKENS = 16384
TEMPERATURE = 0.2
REASONING_EFFORT = "low"
THINKING = {"type": "enabled"}
PROMPT_VERSION = "P1-05-v2"
DRY_RUN = "--dry-run" in sys.argv

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


NEW_BLOCK = """QUANTITY: no quota. Generate as many questions as the supplied textbook learning points can
support with real learning value, and no more. Fewer is acceptable. 0 is an acceptable and
expected answer ({"questions": []}) when there is no suitable learning point. Do not create a
question merely to reach a number.

CORE PRINCIPLE - organise exercises around the textbook's own learning points, not free-form text:
Base every question on one of the following, in this priority order:
  1. learning points the textbook explicitly teaches in this Section (its own exercises, headings,
     grammar focus and language-use boxes)
  2. the Unit vocabulary list (unit_vocabulary); words with emphasis=BOLD are the core words and
     must be preferred
  3. textbook sentences, key expressions and typical patterns (典型句型) shown in the passage or
     in the Section's exercises
  4. important facts and information in the passage: characters, events, relations, reasons,
     details, main idea
  5. other ordinary passage text - use only if nothing above can support a question
The passage text is the CONTEXT that makes a question meaningful; the passage alone is not a
learning point.

Rules per question type:
  - fill: prefer words from unit_vocabulary (BOLD core words first) and the core words of the
    textbook's key phrases. Do NOT pick an arbitrary ordinary word out of the passage.
    The answer must be uniquely determined by the textbook evidence; use the passage context to
    make it unique. If two or more reasonable English words could fill the same blank, do not
    generate that question. A fill that is merely the textbook sentence with one word deleted has
    low learning value - do not build the whole set out of such items.
  - vocab_choice: the correct option must come from unit_vocabulary (BOLD first). You may design a
    new context or recombine information from the textbook. Distractors must be words a Grade 7
    student could plausibly confuse - not obviously unrelated words.
  - sentence / expression items: build on textbook sentences, key expressions, typical patterns and
    key language structures. You may reorganise them or change the way they are tested. Never invent
    a language point the textbook does not contain.
  - reading_choice / reading_judge: ask about important information, characters, events, relations,
    reasons, details or the main idea of the passage. Do not pick a random ordinary sentence just to
    produce one more question.

ANTI-DUPLICATION (hard):
  - Do not reuse the same evidence block for two questions unless the second one tests a genuinely
    different learning point.
  - Do not reproduce the textbook's own exercise as a "new" AI question (same instruction and same
    options).
  - Do not produce several questions that are only the same sentence with different words blanked out.

FREEDOM: you may recombine the textbook's existing vocabulary, reorganise its sentences, combine
different pieces of textbook information, change the testing angle, and design new options inside
the textbook context. You may NOT introduce knowledge with no textbook basis, invent learning
points, pad the count, or use answers the textbook evidence cannot determine.

page must be one of {PAGES} and activity must be one of {ACTS} (or null)."""


PROTECTED = {
    "question_library.db": os.path.join(r"D:\ZhixueEnglish", "structured", "ai",
                                        "question_library.db"),
    "learning.db": os.path.join(r"D:\ZhixueEnglish", "structured", "learning", "learning.db"),
    "contentpack": os.path.join(r"D:\ZhixueEnglish", "structured", "contentpack", "v5",
                                "FLTRP-EN-7A-2022CUR.sqlite"),
    "validator_v2": os.path.join(SPIKE, "20260917_1520_validator_fix", "validator_v2.py"),
    "validator_v3": os.path.join(SPIKE, "P1_04_rule_fixes", "validator_v3.py"),
    "P1-05-D_request": D_REQUEST,
    "P1-05-D_response": os.path.join(SPIKE, "P1_05_budget_calibration_v2",
                                     "calibration_response.json"),
    "P1-05-D_result": os.path.join(SPIKE, "P1_05_budget_calibration_v2",
                                   "calibration_result.json"),
    "P1-05-D_parsed": os.path.join(SPIKE, "P1_05_budget_calibration_v2",
                                   "calibration_parsed.json"),
    "P1-05-A_matrix": os.path.join(SPIKE, "P1_05_sample_design", "p1_05_sample_matrix.json"),
}


def main():
    before = {k: sha_file(p) for k, p in PROTECTED.items()}

    v1 = json.load(open(V1_PROMPT, encoding="utf-8"))
    ctx = json.load(open(CTX_SRC, encoding="utf-8"))
    SYSTEM_V1 = v1["system_prompt"]
    USER = ("Textbook scope and evidence (JSON):\n" + json.dumps(ctx, ensure_ascii=False) +
            "\n\nGenerate questions for this Section now. Output JSON only.")

    pages = v1["pages"]
    acts = v1["activity_nos"]
    cut = SYSTEM_V1.index("Quantity:")
    SYSTEM_V2 = SYSTEM_V1[:cut] + NEW_BLOCK.replace(
        "{PAGES}", ",".join(str(p) for p in pages)).replace(
        "{ACTS}", ",".join(str(a) for a in acts))

    prev = json.load(open(D_REQUEST, encoding="utf-8"))["payload"]
    diffs = []
    for k in sorted(set(prev) | {"model", "temperature", "max_tokens", "messages",
                                 "thinking", "reasoning_effort"}):
        a, b = prev.get(k), {"model": MODEL, "temperature": TEMPERATURE,
                             "max_tokens": MAX_TOKENS,
                             "messages": [{"role": "system", "content": SYSTEM_V2},
                                          {"role": "user", "content": USER}],
                             "thinking": THINKING,
                             "reasoning_effort": REASONING_EFFORT}.get(k)
        if k == "messages":
            if a[1] != b[1]:
                diffs.append({"field": "messages[1](user prompt)", "changed": True})
            if a[0] != b[0]:
                diffs.append({"field": "messages[0](system prompt)", "changed": True,
                              "from_prompt_version": "P1-05-v1", "to_prompt_version": PROMPT_VERSION})
            continue
        if a != b:
            diffs.append({"field": k, "p1_05d": a, "p1_05f": b})

    context_identical = sha(json.dumps(ctx, ensure_ascii=False).encode()) == \
        sha(json.dumps(json.load(open(CTX_SRC, encoding="utf-8")), ensure_ascii=False).encode())

    req_doc = {
        "mode": "TEXTBOOK_FOCUS_VALIDATION",
        "prompt_version": PROMPT_VERSION,
        "sample": v1["section_id"],
        "endpoint": ENDPOINT,
        "payload": {"model": MODEL, "temperature": TEMPERATURE, "max_tokens": MAX_TOKENS,
                    "messages": [{"role": "system", "content": SYSTEM_V2},
                                 {"role": "user", "content": USER}],
                    "thinking": THINKING, "reasoning_effort": REASONING_EFFORT},
        "system_prompt_sha256": sha(SYSTEM_V2.encode()),
        "user_prompt_sha256": sha(USER.encode()),
        "p1_05v1_system_prompt_sha256": sha(SYSTEM_V1.encode()),
        "context_hash": sha(json.dumps(ctx, ensure_ascii=False, sort_keys=True).encode()),
        "context_identical_to_p1_05d": context_identical,
        "prompt_diff_vs_p1_05d": diffs,
        "only_system_prompt_changed": (len(diffs) == 1
                                       and diffs[0]["field"] == "messages[0](system prompt)"),
        "api_calls_allowed": 1,
    }
    dump("p1_05f_request.json", req_doc)
    print("[1] context 相同：%s | 与 P1-05-D 的差异：%s" % (
        context_identical, [d["field"] for d in diffs]))
    if not context_identical or not req_doc["only_system_prompt_changed"]:
        dump("p1_05f_result.json", {"final_status": "P1_05_F_BLOCKED",
                                    "reason": "变量不止 system prompt 或 context 不一致",
                                    "diffs": diffs})
        print("P1_05_F_BLOCKED：变量不单一（未调用 API）")
        return 2
    if DRY_RUN:
        print("[dry-run] 通过，未调用 API")
        return 0

    key = json.load(open(os.path.join(os.environ["USERPROFILE"], ".codex", "auth.json"),
                         encoding="utf-8"))["OPENAI_API_KEY"]
    payload = req_doc["payload"]
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

    dump("p1_05f_response.json", {"mode": "TEXTBOOK_FOCUS_VALIDATION", "endpoint": ENDPOINT,
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

    result = {"mode": "TEXTBOOK_FOCUS_VALIDATION", "prompt_version": PROMPT_VERSION,
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
            dump("p1_05f_parsed.json", parsed)
            qs = parsed.get("questions") or []
            result["questions_count"] = len(qs)
            result["questions_field_present"] = "questions" in parsed
        except Exception as exc:
            result["parse_error"] = str(exc)
            dump("p1_05f_parsed.json", {"parse_failed": True})
    elif verdict["status"] == G.STATUS_TRUNCATED:
        result["note"] = "TRUNCATED：未解析、未入库、不重试"

    after = {k: sha_file(p) for k, p in PROTECTED.items()}
    result["protection"] = {"all_unchanged": before == after,
                            "changed": [k for k in before if before[k] != after[k]]}
    ok = (not api_error and verdict["status"] == G.STATUS_OK and result["json_parseable"]
          and result.get("questions_field_present") and result["protection"]["all_unchanged"])
    result["final_status"] = "P1_05_F_PASS" if ok else "P1_05_F_BLOCKED"
    dump("p1_05f_result.json", result)
    print("[4] 最终状态：%s | 题数=%d | 保护项未变=%s" % (
        result["final_status"], result["questions_count"],
        result["protection"]["all_unchanged"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
