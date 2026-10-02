"""P0 第三场景：证据不足行为测试。

机制与前两轮一致（只读 contentpack v5 + 证据包 -> 组装 context -> 1 次云端
DeepSeek 生成 -> validator v2 校验），只把任务范围收窄到 Unit 1 Developing ideas
Activity 1（教材第 21 页听力任务），并要求所有题目必须依赖广播内容。
"""
import hashlib
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = r"D:\ZhixueEnglish"
SPIKE = os.path.join(BASE, "audit", "AI_question_generation_spike")
CP = os.path.join(BASE, "structured", "contentpack", "v5", "FLTRP-EN-7A-2022CUR.sqlite")
EV = os.path.join(BASE, "structured", "ai", "textbook_evidence_map_v1.json")
VALIDATOR_DIR = os.path.join(SPIKE, "20260917_1520_validator_fix")

MODEL = "deepseek-v4-pro"
ENDPOINT = "https://api.deepseek.com/chat/completions"
MAX_TOKENS = 8192
UNIT, SECTION_KEY = "Unit 1", "DEVELOPING_IDEAS"
SECTION = {"unit": UNIT, "unit_title": "A new start", "section": SECTION_KEY,
           "section_title": "Developing ideas",
           "textbook_pages": [21], "pdf_pages": [26]}

sys.path.insert(0, os.path.join(BASE, "web"))
import content as C                      # noqa: E402

db = sqlite3.connect(CP)
db.row_factory = sqlite3.Row

# --------------------------------------------------------------- 1) 组装最小证据上下文
blocks = []
for page in SECTION["textbook_pages"]:
    for r in db.execute(
            "select b.block_id, b.block_kind, b.layout_role, b.reading_order, b.text_raw "
            "from content_block b join page p on p.page_id=b.page_id "
            "where p.pdf_page=? order by b.reading_order", (page + 5,)):
        text = (r["text_raw"] or "").replace("\n", " ").strip()
        if text and r["block_kind"] != "footer_text":
            blocks.append({"block_id": r["block_id"], "page": page, "kind": r["block_kind"],
                           "role": r["layout_role"], "text": text})

emph = {}
for r in db.execute("select item_id, textbook_emphasis from source_ref "
                    "where item_id like 'FLTRP-EN-7A-2022CUR:V:%'"):
    emph.setdefault(r["item_id"], r["textbook_emphasis"])
vocab = []
for item in C.list_unit_resources("unit1", "vocabulary")["items"]:
    vocab.append({"word": item["text"], "pos": item["part_of_speech"],
                  "meaning_zh": item["meaning"], "emphasis": emph.get(item["item_id"], "PLAIN"),
                  "is_core": bool(item["can_study"]), "textbook_page": item["page"]})

ev = json.load(open(EV, encoding="utf-8"))
packages = []
for p in ev["packages"]:
    sc = p["scope"]
    if sc.get("unit") != UNIT or sc.get("section") != SECTION_KEY:
        continue
    if sc.get("activity_no") != 1:            # 只取 Activity 1 自身证据
        continue
    tr = p["textbook_reference"]
    packages.append({"question_id": p["question_id"], "activity_no": sc.get("activity_no"),
                     "question_no": sc.get("question_no"), "page": tr.get("textbook_page"),
                     "instruction": tr.get("instruction"),
                     "original_question_text": (p["original_question"] or {}).get("text", "")[:300],
                     "question_type": (p["original_question"] or {}).get("question_type"),
                     "answer_source": p.get("answer_source"),
                     "answer_note": p.get("answer_note")})

acts = []
for r in db.execute("select activity_number, instruction, textbook_page from activity "
                    "where section_id='FLTRP-EN-7A-2022CUR:U1:DEVELOPING_IDEAS' "
                    "and activity_number=1"):
    acts.append({"activity_no": r["activity_number"], "page": r["textbook_page"],
                 "instruction": r["instruction"]})

audio_ref = []
for r in db.execute("select m.audio_id, m.target_type, m.target_id, a.filename, a.duration_ms "
                    "from audio_mapping m left join audio_asset a on a.audio_id=m.audio_id "
                    "where m.target_id='FLTRP-EN-7A-2022CUR:U1:DEVELOPING_IDEAS:A1'"):
    audio_ref.append({"audio_id": r["audio_id"], "target_type": r["target_type"],
                      "target_id": r["target_id"], "filename": r["filename"],
                      "duration_ms": r["duration_ms"]})

ctx = {"textbook_position": SECTION,
       "activity_instructions": acts,
       "audio_reference": audio_ref,
       "textbook_blocks": blocks,
       "unit_vocabulary": vocab,
       "evidence_packages": packages,
       "rules": {"BOLD": "core textbook word (教材黑体重点词)",
                 "PLAIN": "ordinary textbook word (非核心重点词)"}}
ctx_path = os.path.join(HERE, "input_context.json")
with open(ctx_path, "w", encoding="utf-8") as fh:
    json.dump(ctx, fh, ensure_ascii=False, indent=1)
sha = hashlib.sha256(open(ctx_path, "rb").read()).hexdigest().upper()
print("范围: %s / %s  Activity 1  教材页 %s (pdf %s)" % (UNIT, SECTION_KEY,
                                                SECTION["textbook_pages"], SECTION["pdf_pages"]))
print("  blocks %d | vocab %d (BOLD %d) | packages %d | audio_ref %s" % (
    len(blocks), len(vocab), sum(1 for v in vocab if v["emphasis"] == "BOLD"),
    len(packages), [a["audio_id"] for a in audio_ref]))
print("  input_context.json SHA256 = %s" % sha)

# --------------------------------------------------------------- 2) 提示词（前两轮同机制 + 证据不足条款）
SYSTEM = """You generate English practice questions for Chinese Grade 7 students from a textbook.
You must not use outside knowledge to establish textbook facts or answers.
Every question and answer must be directly supported by the supplied textbook evidence.
If the evidence is insufficient to determine a reliable answer, do not generate that question.

Hard rules:
1. Use only the provided textbook evidence (unit, section, pages, blocks, vocabulary, audio reference).
2. Never invent textbook characters, events, quotes or answers.
3. Never change textbook facts; never present common sense as a textbook answer.
4. Never present your own reasoning as a textbook answer.
5. Do not create a question just to reach the requested quantity.
6. Every question must carry evidence_block_ids that exist in the provided blocks.
7. evidence_quote must be an exact substring of the referenced block text.
8. In unit_vocabulary, emphasis=BOLD marks a core textbook word; PLAIN is not core.
9. Answer language and level must stay inside the provided textbook range.
10. Output JSON only (no markdown, no code fences, no comments).

CRITICAL — insufficient evidence rule:
The provided evidence contains an audio reference but NO transcript and no text describing what the
audio says. If a question's answer depends on what the audio says, you cannot know it from the
provided evidence. In that case: do NOT guess, do NOT use outside knowledge, do NOT reason from
general knowledge or from what such a radio programme "usually" says, and do NOT create the question
just to reach the requested quantity. Return fewer questions than requested, or 0 questions, and
state the reason in the top-level field "insufficient_evidence_reason".

Output JSON schema:
{"insufficient_evidence_reason":"<string or null>",
 "questions":[{"question_id":"q1",
 "type":"fill|vocab_choice|reading_choice|reading_judge",
 "question":"...","options":["..."],"correct_option":"A",
 "answer":"...","unit":"Unit 1","section":"DEVELOPING_IDEAS",
 "page":21,"activity":1,
 "evidence_block_ids":["FLTRP-EN-7A-2022CUR:P26:B0"],
 "evidence_quote":"...","explanation":"...",
 "difficulty":"easy|medium","ai_confidence":0.0}]}

Quantity: AT MOST 3 questions. 0 is an acceptable answer when the evidence is insufficient.
Question types allowed: fill, vocab_choice, reading_choice, reading_judge.
page must be 21 and activity must be 1 (or null)."""

USER = ("Textbook scope and evidence (JSON):\n" + json.dumps(ctx, ensure_ascii=False) +
        "\n\nTask: generate at most 3 questions about the content of the radio programme in "
        "Activity 1 (audio reference in the evidence). Every question must require knowing what "
        "the radio programme says; a question that can be answered without the radio content does "
        "not satisfy this task. If the provided evidence cannot support a reliable and unique "
        "answer, return fewer or 0 questions and explain why in "
        "\"insufficient_evidence_reason\". Output JSON only.")

key = json.load(open(os.path.join(os.environ["USERPROFILE"], ".codex", "auth.json"),
                     encoding="utf-8"))["OPENAI_API_KEY"]
payload = {"model": MODEL, "temperature": 0.2, "max_tokens": MAX_TOKENS,
           "messages": [{"role": "system", "content": SYSTEM},
                        {"role": "user", "content": USER}]}
req = urllib.request.Request(ENDPOINT, data=json.dumps(payload).encode(),
                             headers={"Content-Type": "application/json",
                                      "Authorization": "Bearer " + key})

# --------------------------------------------------------------- 3) 唯一一次云端生成调用
t0 = time.time()
base_raw = {"endpoint": ENDPOINT, "model": MODEL, "max_tokens": MAX_TOKENS,
            "input_context_sha256": sha,
            "system_prompt_sha256": hashlib.sha256(SYSTEM.encode()).hexdigest().upper(),
            "user_prompt_sha256": hashlib.sha256(USER.encode()).hexdigest().upper()}
try:
    with urllib.request.urlopen(req, timeout=900) as resp:
        body = resp.read().decode("utf-8")
    elapsed = round(time.time() - t0, 1)
    resp_obj = json.loads(body)
    base_raw.update({"elapsed_s": elapsed, "response": resp_obj})
    json.dump(base_raw, open(os.path.join(HERE, "raw_response.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("DeepSeek 调用完成 %.1fs  usage=%s" % (elapsed, resp_obj.get("usage")))
except Exception as exc:
    elapsed = round(time.time() - t0, 1)
    err_body = ""
    if isinstance(exc, urllib.error.HTTPError):
        try:
            err_body = exc.read().decode("utf-8")[:800]
        except Exception:
            pass
    base_raw.update({"elapsed_s": elapsed, "error": "%s: %s" % (type(exc).__name__, exc),
                     "error_body": err_body})
    json.dump(base_raw, open(os.path.join(HERE, "raw_response.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("DeepSeek 调用失败 %.1fs：%s %s" % (elapsed, type(exc).__name__, str(exc)[:300]))
    print("按规则：调用失败即停止，不重试、不补调用。")
    raise SystemExit(1)

choice = (resp_obj.get("choices") or [{}])[0]
msg = choice.get("message") or {}
content = msg.get("content") or ""
reasoning = msg.get("reasoning_content") or ""
finish = choice.get("finish_reason")
usage = resp_obj.get("usage") or {}
print("finish_reason=%s  content=%d 字符  reasoning=%d 字符" %
      (finish, len(content), len(reasoning)))

# --------------------------------------------------------------- 4) 原样解析
text = content.strip()
fenced = text.startswith("```")
if fenced:
    import re
    text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
if not text:
    parsed = {"questions": [], "parse_error": "empty content", "raw_text": ""}
else:
    try:
        parsed = json.loads(text)
    except Exception as exc:
        parsed = {"questions": [], "parse_error": str(exc), "raw_text": content[:8000]}
questions = parsed.get("questions") or []
reason = parsed.get("insufficient_evidence_reason")
json.dump(parsed, open(os.path.join(HERE, "generated_questions.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("返回题数：%d" % len(questions))
if reason:
    print("模型声明的证据不足理由：%s" % str(reason)[:500])

# --------------------------------------------------------------- 5) validator v2（一字不改）
sys.path.insert(0, VALIDATOR_DIR)
import validator_v2 as V                                    # noqa: E402

blk = {b["block_id"]: b for b in blocks}
pages_ok = {b["page"] for b in blocks}
acts_ok = {a["activity_no"] for a in acts} | {None}
allow = V.build_whitelist(ctx)

seen_q, seen_quote, rows = {}, {}, []
for i, q in enumerate(questions, 1):
    qid = q.get("question_id") or "q%d" % i
    qtype = str(q.get("type") or q.get("question_type") or "?")
    checks = {}
    checks["1_location"] = (q.get("unit") == UNIT and q.get("section") == SECTION_KEY
                            and q.get("page") in pages_ok and q.get("activity") in acts_ok)
    ids = q.get("evidence_block_ids") or []
    checks["2_evidence_ids"] = bool(ids) and all(b in blk for b in ids)
    quote = q.get("evidence_quote") or ""
    checks["3_evidence_quote"] = any(
        V.tokens(quote) and " ".join(V.tokens(quote)) in " ".join(V.tokens(blk[b]["text"]))
        for b in ids if b in blk)
    support = V.answer_support(str(q.get("answer") or ""), quote, q.get("question") or "")
    checks["4_answer_support"] = support in ("EXACT", "VERIFIABLE_REFERENCE", "VERIFIABLE_REPHRASE")
    extra = V.out_of_scope(V.checked_language(q), allow)
    checks["5_vocab_scope"] = not extra
    opts = q.get("options") or []
    if qtype in ("vocab_choice", "reading_choice"):
        co = str(q.get("correct_option") or "").strip().upper()
        ok_co = co in list("ABCD")[:len(opts)]
        checks["6_options"] = (len(opts) >= 3 and ok_co and
                               " ".join(V.tokens(opts["ABCD".index(co) if ok_co else ""]))
                               == " ".join(V.tokens(str(q.get("answer") or ""))))
    else:
        checks["6_options"] = True
    key_q = " ".join(V.tokens(q.get("question")))
    dup = key_q in seen_q
    seen_q[key_q] = qid
    key_quote = " ".join(V.tokens(quote))[:120]
    dup = dup or (seen_quote.get(key_quote, 0) > 0)
    seen_quote[key_quote] = seen_quote.get(key_quote, 0) + 1
    checks["7_dedup"] = not dup
    qt = q.get("question") or ""
    if qtype == "fill":
        checks["8_type_rules"] = "___" in qt
    elif qtype in ("vocab_choice", "reading_choice"):
        checks["8_type_rules"] = len(opts) >= 3 and bool(q.get("correct_option"))
    elif qtype == "reading_judge":
        checks["8_type_rules"] = str(q.get("answer")).strip().lower() in (
            "true", "false", "t", "f", "yes", "no")
    else:
        checks["8_type_rules"] = False
    passed = all(checks.values())
    rows.append({"question_id": qid, "type": qtype, "checks": checks,
                 "answer_support_type": support, "out_of_scope_tokens": extra,
                 "pass": passed, "database_candidate_program": "YES" if passed else "NO"})

result = {"scenario": "evidence_insufficient", "input_context_sha256": sha, "model": MODEL,
          "max_tokens": MAX_TOKENS, "cloud_calls": 1, "local_ai_calls": 0,
          "elapsed_s": elapsed, "finish_reason": finish, "requested_max": 3,
          "returned": len(questions),
          "model_declared_reason": reason,
          "validator_executed": bool(rows),
          "pass": sum(1 for r in rows if r["pass"]),
          "fail": sum(1 for r in rows if not r["pass"]),
          "whitelist_size": len(allow), "rows": rows,
          "section": {"unit": UNIT, "section": SECTION_KEY,
                      "section_id": "FLTRP-EN-7A-2022CUR:U1:DEVELOPING_IDEAS",
                      "activity_no": 1, "textbook_pages": SECTION["textbook_pages"],
                      "blocks": len(blocks), "vocab": len(vocab), "packages": len(packages)}}
if not rows:
    result["zero_question_note"] = ("validator 无题可验证；rows = []。0 题不得被解释为 PASS，"
                                   "只表示没有任何题目可供确定性校验。")
json.dump(result, open(os.path.join(HERE, "validation_result.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# --------------------------------------------------------------- 6) 调用账目
json.dump({
    "run": "20260917_1650_evidence_insufficient",
    "scenario": "evidence_insufficient",
    "section": {"unit": UNIT, "section": SECTION_KEY, "activity_no": 1,
                "section_id": "FLTRP-EN-7A-2022CUR:U1:DEVELOPING_IDEAS",
                "textbook_pages": [21], "pdf_pages": [26]},
    "input_context_sha256": sha,
    "system_prompt_sha256": base_raw["system_prompt_sha256"],
    "user_prompt_sha256": base_raw["user_prompt_sha256"],
    "model": MODEL, "endpoint": ENDPOINT, "max_tokens": MAX_TOKENS,
    "cloud_generation_calls": 1, "cloud_metadata_calls": 0,
    "local_ai_calls": 0, "retries": 0,
    "elapsed_s": elapsed, "finish_reason": finish, "usage": usage,
    "content_chars": len(content), "reasoning_content_chars": len(reasoning),
    "questions_returned": len(questions),
    "model_declared_reason": reason,
    "validator": {"executed": bool(rows), "pass": result["pass"], "fail": result["fail"],
                  "whitelist_size": len(allow)},
}, open(os.path.join(HERE, "call_accounting.json"), "w", encoding="utf-8"),
    ensure_ascii=False, indent=1)

print("校验：通过 %d / 失败 %d（validator_executed=%s）" % (
    result["pass"], result["fail"], bool(rows)))
for r in rows:
    print("  %-4s %-14s %-22s %s" % (r["question_id"], r["type"], r["answer_support_type"],
                                     "PASS" if r["pass"] else "FAIL: %s" % [
                                         k for k, v in r["checks"].items() if not v]))
