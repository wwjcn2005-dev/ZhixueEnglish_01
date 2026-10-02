"""P0 Spike 第二步：单次 AI 调用 + 确定性校验（只写本目录）。

AI 调用：本地 Ollama /api/chat，模型 qwen3:8b，**仅 1 次**。
"""
import json
import os
import re
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = "qwen3:8b"
OLLAMA = "http://127.0.0.1:11434/api/chat"

ctx = json.load(open(os.path.join(HERE, "input_context.json"), encoding="utf-8"))

SYSTEM = """You generate English practice questions for Chinese Grade 7 students.
You may ONLY use the textbook evidence given by the user.

Hard rules:
1. Use only the provided textbook evidence. Do not use outside knowledge.
2. Never invent textbook facts, textbook quotes, or textbook answers.
3. Never create reading facts that are not in the provided blocks.
4. The correct answer must be determinable from the provided textbook text.
5. If a question cannot be determined from the evidence, do not create it.
6. Do not lower the evidence standard in order to reach 10 questions.
7. Every question must include evidence_block_ids that exist in the provided list.
8. evidence_quote must be an exact substring of the referenced block text.
9. In unit_vocabulary, emphasis=BOLD marks a core textbook word; PLAIN is not core.
10. Output JSON only. No markdown. No comments.

Output schema:
{"questions":[{"question_id":"q1",
 "question_type":"fill|vocab_choice|reading_choice|reading_judge",
 "question":"...","options":["..."],"correct_option":"A",
 "answer":"...","unit":"Unit 3","section":"READING_FOR_WRITING",
 "page":56,"activity":2,
 "evidence_block_ids":["FLTRP-EN-7A-2022CUR:P61:B5"],
 "evidence_quote":"...","explanation":"...",
 "difficulty":"easy|medium","ai_confidence":0.0}]}

Question plan (exactly, if the evidence allows):
- 3 x "fill": take a real textbook sentence, blank out one word or phrase, keep the rest
  unchanged; answer = the exact removed word(s); write the blank as ___.
- 4 x "vocab_choice": use a real textbook sentence with a blank; 4 options; the correct
  option must be a word from unit_vocabulary whose meaning/pos fits that sentence;
  distractors may be other unit_vocabulary words.
- 3 x "reading_choice" or "reading_judge": about explicit facts in the story blocks
  (pages 56-57); answer must be located inside evidence_quote.
page must be one of 56,57,58,59 in the provided blocks; activity must be one of
1,2,4,5 from activity_instructions, or null."""

USER = ("Textbook scope and evidence (JSON):\n" + json.dumps(ctx, ensure_ascii=False) +
        "\n\nGenerate the questions now. Output JSON only.")

payload = {"model": MODEL, "stream": False, "format": "json",
           "messages": [{"role": "system", "content": SYSTEM},
                        {"role": "user", "content": USER}],
           "options": {"temperature": 0.2, "num_ctx": 8192, "num_predict": 4096,
                       "num_gpu": 0}}          # CPU 推理：绕过上一次的 CUDA/PTX 加载失败

req = urllib.request.Request(OLLAMA, data=json.dumps(payload).encode(),
                             headers={"Content-Type": "application/json"})
t0 = time.time()
with urllib.request.urlopen(req, timeout=900) as resp:
    raw = resp.read().decode("utf-8")
elapsed = round(time.time() - t0, 1)
resp_obj = json.loads(raw)
json.dump({"model": MODEL, "elapsed_s": elapsed, "request_options": payload["options"],
           "response": resp_obj},
          open(os.path.join(HERE, "ai_call_raw.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
content = (resp_obj.get("message") or {}).get("content") or ""
print("AI 调用完成 model=%s %.1fs 输出 %d 字符" % (MODEL, elapsed, len(content)))

try:
    parsed = json.loads(content)
except Exception as exc:
    parsed = {"questions": [], "parse_error": str(exc)}
questions = parsed.get("questions") or []
json.dump(parsed, open(os.path.join(HERE, "generated_questions.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("返回题数 %d" % len(questions))

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

rows, fails, fail_class = [], 0, {}
seen_q, seen_quote, type_cnt = {}, {}, {}


def add_fail(code, qid, detail):
    fail_class.setdefault(code, []).append("%s: %s" % (qid, detail))


for i, q in enumerate(questions, 1):
    qid = q.get("question_id") or "q%d" % i
    qtype = q.get("question_type") or "?"
    type_cnt[qtype] = type_cnt.get(qtype, 0) + 1
    issues = []
    if q.get("unit") != "Unit 3" or q.get("section") != "READING_FOR_WRITING":
        issues.append("定位错误")
        add_fail("9 数据结构问题", qid, "unit/section=%s/%s" % (q.get("unit"), q.get("section")))
    if q.get("page") not in pages_ok:
        issues.append("page 非法")
        add_fail("9 数据结构问题", qid, "page=%s" % q.get("page"))
    if q.get("activity") not in acts_ok:
        issues.append("activity 非法")
        add_fail("9 数据结构问题", qid, "activity=%s" % q.get("activity"))
    ids = q.get("evidence_block_ids") or []
    bad_ids = [b for b in ids if b not in blk]
    if not ids or bad_ids:
        issues.append("证据 id 无效")
        add_fail("7 证据引用错误", qid, "bad=%s" % bad_ids)
    quote = q.get("evidence_quote") or ""
    quote_ok = any(norm(quote) and norm(quote) in norm(blk[b]["text"]) for b in ids if b in blk)
    if not quote_ok:
        issues.append("quote 不在原文")
        add_fail("7 证据引用错误", qid, "quote 未命中")
    ans = str(q.get("answer") or "")
    qt = q.get("question") or ""
    if not ans:
        issues.append("缺 answer")
        add_fail("4 答案无法确定", qid, "answer 为空")
    elif qtype == "fill":
        if norm(ans) not in norm(quote):
            issues.append("填空答案不在原文")
            add_fail("4 答案无法确定", qid, "answer 不在 quote")
        if "___" not in qt:
            issues.append("无空位标记")
            add_fail("8 题型规则", qid, "fill 缺空位")
    elif qtype in ("vocab_choice", "reading_choice"):
        opts = q.get("options") or []
        if len(opts) != len({norm(o) for o in opts}) or len(opts) < 3:
            issues.append("选项重复/不足")
            add_fail("6 干扰项有问题", qid, "options=%s" % opts)
        co = str(q.get("correct_option") or "").strip().upper()
        if co not in list("ABCD")[:len(opts)]:
            issues.append("correct_option 非法")
            add_fail("9 数据结构问题", qid, "correct_option=%r" % q.get("correct_option"))
        elif norm(opts["ABCD".index(co)]) != norm(ans):
            issues.append("correct_option 与 answer 不一致")
            add_fail("4 答案无法确定", qid, "correct_option/answer 不一致")
        if not quote_ok or (norm(ans) not in norm(quote)):
            issues.append("答案无原文支持")
            add_fail("4 答案无法确定", qid, "答案与 quote 无对应")
    elif qtype == "reading_judge":
        if ans.strip().lower() not in ("true", "false", "t", "f", "yes", "no"):
            issues.append("判断答案非法")
            add_fail("8 题型规则", qid, "judge=%s" % ans)
    else:
        issues.append("题型不在本次范围")
        add_fail("8 题型规则", qid, "type=%s" % qtype)
    text_all = " ".join([qt, " ".join(q.get("options") or []), ans, q.get("explanation") or ""])
    extra = sorted({w for w in norm(text_all).split() if w not in allow})
    if extra:
        issues.append("疑似超纲词")
        add_fail("5 题目超纲", qid, " ".join(extra[:6]))
    key = norm(qt)
    if key and key in seen_q:
        issues.append("题干重复")
        add_fail("8 题目重复", qid, "与 %s 重复" % seen_q[key])
    seen_q[key] = qid
    qk = norm(quote)[:140]
    seen_quote[qk] = seen_quote.get(qk, 0) + 1
    if issues:
        fails += 1
    rows.append([qid, qtype, "PASS" if not issues else "FAIL", (quote or "")[:70],
                 q.get("page"), " / ".join(issues) or "-"])

dup = {k: v for k, v in seen_quote.items() if v > 1 and k}
if dup:
    add_fail("8 题目重复", "-", "%d 组共用同一 evidence_quote" % len(dup))

out = []
out.append("# Spike 确定性校验报告（程序独立检查，不采信 AI 自报）\n")
out.append("- 执行对象：%s · %s（教材第 %s 页 / pdf %s）" % (
    ctx["textbook_position"]["unit"], ctx["textbook_position"]["section"],
    ctx["textbook_position"]["textbook_pages"], ctx["textbook_position"]["pdf_pages"]))
out.append("- AI：model=%s，调用 **1 次**，用时 %.1fs，输出 %d 字符" % (MODEL, elapsed, len(content)))
out.append("- 请求 10 题，实际返回 %d 题；通过 %d，失败 %d\n" % (
    len(questions), sum(1 for r in rows if r[2] == "PASS"), fails))
out.append("| 题号 | 类型 | 结果 | evidence_quote（截断） | page | 问题 |")
out.append("| --- | --- | --- | --- | --- | --- |")
for r in rows:
    out.append("| %s | %s | %s | %s | %s | %s |" % tuple(str(x) for x in r))
out.append("\n## 题型分布")
out.append("- 期望 fill 3 / vocab_choice 4 / reading 3；实际 %s" % json.dumps(
    type_cnt, ensure_ascii=False))
out.append("\n## 失败分类（10 类口径）")
if fail_class:
    for k in sorted(fail_class):
        out.append("- %s：%d 处 —— %s" % (k, len(fail_class[k]),
                                          "; ".join(fail_class[k])[:260]))
else:
    out.append("- 无")
out.append("\n## 白名单规则")
out.append("- 允许词 = Unit 3 词表词形 ∪ 本 Section 教材文本词 ∪ 常用功能词/题型词（白名单共 %d 词）" % len(allow))

open(os.path.join(HERE, "validation_report.md"), "w", encoding="utf-8").write(
    "\n".join(out) + "\n")
print("通过 %d / 失败 %d" % (sum(1 for r in rows if r[2] == "PASS"), fails))
