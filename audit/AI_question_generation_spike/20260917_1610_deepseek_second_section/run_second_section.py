"""P0 第二 Section（Unit 1 · Understanding ideas）云端 DeepSeek 生成 + validator v2 校验。

机制与第一轮完全一致：只读 contentpack v5 + 证据包 → 组装 input_context.json
→ **1 次**云端 DeepSeek 生成（最多 3 题）→ 复用 validator_v2 的 8 项校验。
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
CP = os.path.join(BASE, "structured", "contentpack", "v5", "FLTRP-EN-7A-2022CUR.sqlite")
EV = os.path.join(BASE, "structured", "ai", "textbook_evidence_map_v1.json")
MODEL = "deepseek-v4-pro"
ENDPOINT = "https://api.deepseek.com/chat/completions"

sys.path.insert(0, os.path.join(BASE, "web"))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "20260917_1520_validator_fix"))
import content as C                      # noqa: E402
import validator_v2 as V                 # noqa: E402   ← 复用上一轮已确认有效的校验器

db = sqlite3.connect(CP)
db.row_factory = sqlite3.Row

# --------------------------------------------------------------------------- 1) 上下文（与第一轮同一机制）
UNIT, SECTION_KEY = "Unit 1", "UNDERSTANDING_IDEAS"
SECTION = {"unit": UNIT, "unit_title": "A new start", "section": SECTION_KEY,
           "section_title": "Understanding ideas",
           "textbook_pages": [16, 17, 18, 19, 20], "pdf_pages": [21, 22, 23, 24, 25]}

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
    tr = p["textbook_reference"]
    packages.append({"question_id": p["question_id"], "activity_no": sc.get("activity_no"),
                     "page": tr.get("textbook_page"), "instruction": tr.get("instruction"),
                     "original_question_text": (p["original_question"] or {}).get("text", "")[:300],
                     "answer_source": p.get("answer_source"),
                     "answer_note": p.get("answer_note")})

acts = []
for r in db.execute("select activity_number, instruction, textbook_page from activity "
                    "where section_id='FLTRP-EN-7A-2022CUR:U1:UNDERSTANDING_IDEAS' "
                    "order by activity_number"):
    acts.append({"activity_no": r["activity_number"], "page": r["textbook_page"],
                 "instruction": r["instruction"]})

ctx = {"textbook_position": SECTION, "activity_instructions": acts,
       "textbook_blocks": blocks, "unit_vocabulary": vocab,
       "evidence_packages": packages,
       "rules": {"BOLD": "core textbook word (教材黑体重点词)",
                 "PLAIN": "ordinary textbook word (非核心重点词)"}}
ctx_path = os.path.join(HERE, "input_context.json")
with open(ctx_path, "w", encoding="utf-8") as fh:
    json.dump(ctx, fh, ensure_ascii=False, indent=1)
sha = hashlib.sha256(open(ctx_path, "rb").read()).hexdigest().upper()
print("输入范围: %s / %s  教材页 %s (pdf %s)" % (UNIT, SECTION_KEY,
                                          SECTION["textbook_pages"], SECTION["pdf_pages"]))
print("  content_block %d｜activity %s｜Unit 词汇 %d（BOLD %d）｜证据包 %d" % (
    len(blocks), [a["activity_no"] for a in acts], len(vocab),
    sum(1 for v in vocab if v["emphasis"] == "BOLD"), len(packages)))
print("  input_context.json SHA256 = %s（%d 字符）" % (sha, len(json.dumps(ctx, ensure_ascii=False))))

# --------------------------------------------------------------------------- 2) 提示词（与第一轮同机制，只换本 Section 参数）
SYSTEM = """You generate English practice questions for Chinese Grade 7 students from a textbook.
You must not use outside knowledge to establish textbook facts or answers.
Every question and answer must be directly supported by the supplied textbook evidence.
If the evidence is insufficient to determine a reliable answer, do not generate that question.

Hard rules:
1. Use only the provided textbook evidence (unit, section, pages, blocks, vocabulary).
2. Never invent textbook characters, events, quotes or answers.
3. Never change textbook facts; never present common sense as a textbook answer.
4. Never present your own reasoning as a textbook answer.
5. Do not create a question just to reach the requested quantity.
6. Every question must carry evidence_block_ids that exist in the provided blocks.
7. evidence_quote must be an exact substring of the referenced block text.
8. In unit_vocabulary, emphasis=BOLD marks a core textbook word; PLAIN is not core.
9. Answer language and level must stay inside the provided textbook range.
10. Output JSON only (no markdown, no code fences, no comments).

Output JSON schema:
{"questions":[{"question_id":"q1",
 "type":"fill|vocab_choice|reading_choice|reading_judge",
 "question":"...","options":["..."],"correct_option":"A",
 "answer":"...","unit":"Unit 1","section":"UNDERSTANDING_IDEAS",
 "page":17,"activity":2,
 "evidence_block_ids":["FLTRP-EN-7A-2022CUR:P22:B0"],
 "evidence_quote":"...","explanation":"...",
 "difficulty":"easy|medium","ai_confidence":0.0}]}

Quantity: AT MOST 3 questions. Fewer is acceptable; 0 is acceptable if the evidence is insufficient.
Prefer this distribution when the evidence allows: 1 fill, 1 vocab_choice, 1 reading_choice/reading_judge.
  - fill: a real textbook sentence with one word/phrase replaced by ___ ; answer = the exact removed word(s);
    the rest of the sentence must stay unchanged.
  - vocab_choice: a real textbook sentence with a blank and 4 options; the correct option must be a word from
    unit_vocabulary whose meaning/part of speech fits the sentence; distractors may be other unit words.
  - reading_choice / reading_judge: about explicit facts in the story blocks (page 17); the answer must be
    located inside evidence_quote. No open interpretation, no outside knowledge.
page must be one of 16,17,18,19,20 and activity must be one of 2,3,4,5,6,8 (or null)."""

USER = ("Textbook scope and evidence (JSON):\n" + json.dumps(ctx, ensure_ascii=False) +
        "\n\nGenerate at most 3 questions now. Output JSON only.")

key = json.load(open(os.path.join(os.environ["USERPROFILE"], ".codex", "auth.json"),
                     encoding="utf-8"))["OPENAI_API_KEY"]
payload = {"model": MODEL, "temperature": 0.2, "max_tokens": 4096,
           "messages": [{"role": "system", "content": SYSTEM},
                        {"role": "user", "content": USER}]}
req = urllib.request.Request(ENDPOINT, data=json.dumps(payload).encode(),
                             headers={"Content-Type": "application/json",
                                      "Authorization": "Bearer " + key})

# --------------------------------------------------------------------------- 3) 唯一一次云端生成调用
t0 = time.time()
try:
    with urllib.request.urlopen(req, timeout=600) as resp:
        raw = resp.read().decode("utf-8")
    elapsed = round(time.time() - t0, 1)
    resp_obj = json.loads(raw)
    json.dump({"endpoint": ENDPOINT, "model": MODEL, "elapsed_s": elapsed,
               "input_context_sha256": sha, "response": resp_obj},
              open(os.path.join(HERE, "raw_response.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    content = (resp_obj.get("choices") or [{}])[0].get("message", {}).get("content", "")
    print("DeepSeek 调用成功 %.1fs  usage=%s" % (elapsed, resp_obj.get("usage")))
except Exception as exc:
    elapsed = round(time.time() - t0, 1)
    body = ""
    if isinstance(exc, urllib.error.HTTPError):
        try:
            body = exc.read().decode("utf-8")[:600]
        except Exception:
            pass
    json.dump({"endpoint": ENDPOINT, "model": MODEL, "elapsed_s": elapsed,
               "error": "%s: %s" % (type(exc).__name__, exc), "error_body": body},
              open(os.path.join(HERE, "raw_response.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("DeepSeek 调用失败 %.1fs：%s %s" % (elapsed, type(exc).__name__, str(exc)[:200]))
    raise SystemExit(1)

text = content.strip()
fenced = text.startswith("```")
if fenced:
    import re
    text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
try:
    parsed = json.loads(text)
except Exception as exc:
    parsed = {"questions": [], "parse_error": str(exc), "raw_text": content[:4000]}
questions = parsed.get("questions") or []
json.dump(parsed, open(os.path.join(HERE, "generated_questions.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("返回题数：%d%s" % (len(questions), "（输出带代码围栏，仅剥离围栏解析）" if fenced else ""))

# --------------------------------------------------------------------------- 4) 复用 validator v2 做 8 项校验
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

result = {"input_context_sha256": sha, "model": MODEL, "cloud_calls": 1, "local_ai_calls": 0,
          "elapsed_s": elapsed, "requested_max": 3, "returned": len(questions),
          "pass": sum(1 for r in rows if r["pass"]),
          "fail": sum(1 for r in rows if not r["pass"]),
          "whitelist_size": len(allow), "rows": rows,
          "section": {"unit": UNIT, "section": SECTION_KEY, "pages": SECTION["textbook_pages"],
                      "blocks": len(blocks), "vocab": len(vocab), "packages": len(packages)}}
json.dump(result, open(os.path.join(HERE, "validation_result.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("校验：通过 %d / 失败 %d" % (result["pass"], result["fail"]))
for r in rows:
    print("  %-4s %-14s %-22s %s" % (r["question_id"], r["type"], r["answer_support_type"],
                                     "PASS" if r["pass"] else "FAIL: %s" % [
                                         k for k, v in r["checks"].items() if not v]))
