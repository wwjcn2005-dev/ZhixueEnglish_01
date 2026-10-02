"""P0 Spike · 云端 DeepSeek 最小生成验证（1 次调用 + 8 项确定性校验）。

边界：只读本目录 input_context.json（与 1410 版字节一致）；
      只调用 Codex 已配置的 DeepSeek 云端一次（https://api.deepseek.com/chat/completions）；
      只写本目录。
"""
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = "deepseek-v4-pro"
ENDPOINT = "https://api.deepseek.com/chat/completions"
EXPECT_CTX_SHA = "D8C57F28100018191C98C1E2D19E6032C38680D1DA007EBE6ED0D0265F2AE8EA"

ctx_path = os.path.join(HERE, "input_context.json")
raw_ctx = open(ctx_path, "rb").read()
sha = hashlib.sha256(raw_ctx).hexdigest().upper()
assert sha == EXPECT_CTX_SHA, "input_context.json 与 1410 版不一致：%s" % sha
ctx = json.loads(raw_ctx.decode("utf-8"))
print("input_context.json SHA256 校验通过：%s" % sha)

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
 "answer":"...","unit":"Unit 3","section":"READING_FOR_WRITING",
 "page":56,"activity":2,
 "evidence_block_ids":["FLTRP-EN-7A-2022CUR:P61:B5"],
 "evidence_quote":"...","explanation":"...",
 "difficulty":"easy|medium","ai_confidence":0.0}]}

Quantity: AT MOST 3 questions. Fewer is acceptable; 0 is acceptable if evidence is insufficient.
Prefer this distribution when the evidence allows: 1 fill, 1 vocab_choice, 1 reading_choice/reading_judge.
  - fill: a real textbook sentence with one word/phrase replaced by ___ ; answer = the exact removed word(s);
    the rest of the sentence must stay unchanged.
  - vocab_choice: a real textbook sentence with a blank and 4 options; the correct option must be a word from
    unit_vocabulary whose meaning/part of speech fits the sentence; distractors may be other unit words.
  - reading_choice / reading_judge: about explicit facts in the story blocks (pages 56-57); the answer must be
    located inside evidence_quote. No open interpretation, no outside knowledge.
page must be one of 56,57,58,59 and activity must be one of 1,2,4,5 (or null)."""

USER = ("Textbook scope and evidence (JSON):\n" + json.dumps(ctx, ensure_ascii=False) +
        "\n\nGenerate at most 3 questions now. Output JSON only.")

key = json.load(open(os.path.join(os.environ["USERPROFILE"], ".codex", "auth.json"),
                     encoding="utf-8"))["OPENAI_API_KEY"]
payload = {"model": MODEL, "temperature": 0.2, "max_tokens": 4096,
           "messages": [{"role": "system", "content": SYSTEM},
                        {"role": "user", "content": USER}]}
req = urllib.request.Request(
    ENDPOINT, data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})

t0 = time.time()
try:
    with urllib.request.urlopen(req, timeout=600) as resp:
        raw = resp.read().decode("utf-8")
    elapsed = round(time.time() - t0, 1)
    resp_obj = json.loads(raw)
    json.dump({"endpoint": ENDPOINT, "model": MODEL, "elapsed_s": elapsed,
               "response": resp_obj},
              open(os.path.join(HERE, "raw_response.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    content = (resp_obj.get("choices") or [{}])[0].get("message", {}).get("content", "")
    usage = resp_obj.get("usage")
    print("DeepSeek 调用成功 %.1fs  输出 %d 字符  usage=%s" % (elapsed, len(content), usage))
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
if text.startswith("```"):
    text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    print("（说明：模型输出带代码围栏，解析时已剥离围栏，题目内容未改动）")
try:
    parsed = json.loads(text)
except Exception as exc:
    parsed = {"questions": [], "parse_error": str(exc), "raw_text": content[:4000]}
questions = parsed.get("questions") or []
json.dump(parsed, open(os.path.join(HERE, "generated_questions.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("返回题数：%d" % len(questions))

# --------------------------------------------------------------------------- 8 项确定性校验
blocks = ctx["textbook_blocks"]
blk = {b["block_id"]: b for b in blocks}
pages_ok = {b["page"] for b in blocks}
acts_ok = {a["activity_no"] for a in ctx["activity_instructions"]} | {None}


def norm(s):
    s = (s or "").lower().replace("\u2019", "'").replace("\u201c", " ").replace("\u201d", " ")
    return " ".join(re.sub(r"[^a-z0-9' ]+", " ", s).split())


FUNC = set("""a an the is are was were be been am do does did done have has had
i you he she it we they me him her us them my your his its our their this that these those
what which who whose when where why how in on at to of for from with by as and or but not no
yes true false both each other others all some any many much more most few less least very
too also only just still yet even than then there here now next first second third last
about into over under between after before during because so if while such same different
can could will would should may might must shall one two three four five six seven eight nine
ten question answer choose correct option options blank blanks sentence sentences word words
story passage paragraph according following below above example examples write fill does
what's doesn't didn't isn't aren't wasn't weren't there's""".split())
allow = set(FUNC)
for b in blocks:
    allow |= set(norm(b["text"]).split())
for v in ctx["unit_vocabulary"]:
    allow |= set(norm(v["word"]).split())

results, seen_q, seen_quote = [], {}, {}


def add(issue, code):
    issues.append(issue)
    codes.append(code)


for i, q in enumerate(questions, 1):
    qid = q.get("question_id") or "q%d" % i
    qtype = str(q.get("type") or q.get("question_type") or "?")
    issues, codes = [], []

    # 1 定位
    if q.get("unit") != "Unit 3" or q.get("section") != "READING_FOR_WRITING":
        add("定位错误", "9")
    if q.get("page") not in pages_ok:
        add("page 非法(%s)" % q.get("page"), "9")
    if q.get("activity") not in acts_ok:
        add("activity 非法(%s)" % q.get("activity"), "9")
    # 2 evidence ids
    ids = q.get("evidence_block_ids") or []
    bad = [b for b in ids if b not in blk]
    if not ids or bad:
        add("证据 id 无效 %s" % bad, "7")
    # 3 evidence_quote
    quote = q.get("evidence_quote") or ""
    quote_ok = any(norm(quote) and norm(quote) in norm(blk[b]["text"]) for b in ids if b in blk)
    if not quote_ok:
        add("quote 未命中原文", "7")
    # 4 答案
    ans = str(q.get("answer") or "")
    qt = q.get("question") or ""
    if not ans:
        add("缺 answer", "4")
    elif qtype == "fill":
        if norm(ans) not in norm(quote):
            add("填空答案不在原文", "4")
        if "___" not in qt:
            add("fill 无空位", "8")
    elif qtype in ("vocab_choice", "reading_choice"):
        if not quote_ok or norm(ans) not in norm(quote):
            add("答案无原文支持", "4")
    elif qtype == "reading_judge":
        if ans.strip().lower() not in ("true", "false", "t", "f", "yes", "no"):
            add("judge 答案非法", "8")
    else:
        add("题型不在本次范围(%s)" % qtype, "8")
    # 5 词汇白名单
    text_all = " ".join([qt, " ".join(q.get("options") or []), ans, q.get("explanation") or ""])
    extra = sorted({w for w in norm(text_all).split() if w not in allow})
    if extra:
        add("疑似超纲词: %s" % " ".join(extra[:6]), "5")
    # 6 选项
    if qtype in ("vocab_choice", "reading_choice"):
        opts = q.get("options") or []
        if len(opts) < 3 or len(opts) != len({norm(o) for o in opts}):
            add("选项不足/重复", "6")
        co = str(q.get("correct_option") or "").strip().upper()
        if co not in list("ABCD")[:len(opts)]:
            add("correct_option 非法(%r)" % q.get("correct_option"), "9")
        elif norm(opts["ABCD".index(co)]) != norm(ans):
            add("correct_option 与 answer 不一致", "4")
    # 7 去重
    key = norm(qt)
    if key and key in seen_q:
        add("与 %s 题干重复" % seen_q[key], "8")
    seen_q[key] = qid
    qk = norm(quote)[:140]
    seen_quote[qk] = seen_quote.get(qk, 0) + 1
    if seen_quote[qk] > 1:
        add("evidence_quote 与其它题重复", "8")
    # 8 题型规则（本段已覆盖空位/选项/判断）
    ok = not issues
    results.append({"question_id": qid, "type": qtype, "pass": ok, "issues": issues,
                    "codes": codes, "page": q.get("page"), "activity": q.get("activity"),
                    "evidence_block_ids": ids, "evidence_quote": quote,
                    "question": qt, "options": q.get("options") or [],
                    "correct_option": q.get("correct_option"), "answer": ans,
                    "explanation": q.get("explanation"),
                    "database_candidate_program": "YES" if ok else "NO"})

summary = {
    "endpoint": ENDPOINT, "model": MODEL, "cloud_calls": 1, "local_ai_calls": 0,
    "elapsed_s": elapsed, "requested_max": 3, "returned": len(questions),
    "pass": sum(1 for r in results if r["pass"]),
    "fail": sum(1 for r in results if not r["pass"]),
    "candidate_yes_program": sum(1 for r in results if r["database_candidate_program"] == "YES"),
    "context_sha256": sha, "whitelist_size": len(allow),
    "results": results}
json.dump(summary, open(os.path.join(HERE, "validation_result.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("校验：通过 %d / 失败 %d" % (summary["pass"], summary["fail"]))
for r in results:
    print("  %-6s %-14s %s %s" % (r["question_id"], r["type"],
                                  "PASS" if r["pass"] else "FAIL", r["issues"] or ""))
