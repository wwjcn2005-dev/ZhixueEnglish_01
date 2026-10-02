"""用修订后的 validator_v2 对 20260917_1450_deepseek_min3 的原始 3 题做回归。

只读原始输入与原始 AI 输出（不修改、不重新生成、不调用任何 AI）。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validator_v2 as V  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(HERE), "20260917_1450_deepseek_min3")
ctx = json.load(open(os.path.join(SRC, "input_context.json"), encoding="utf-8"))
raw_questions = json.load(open(os.path.join(SRC, "generated_questions.json"), encoding="utf-8"))
questions = raw_questions["questions"]

blk = {b["block_id"]: b for b in ctx["textbook_blocks"]}
pages_ok = {b["page"] for b in ctx["textbook_blocks"]}
acts_ok = {a["activity_no"] for a in ctx["activity_instructions"]} | {None}
allow = V.build_whitelist(ctx)

seen_q, seen_quote = {}, {}
rows = []
for i, q in enumerate(questions, 1):
    qid = q.get("question_id") or "q%d" % i
    qtype = str(q.get("type") or q.get("question_type") or "?")
    checks = {}
    # 1 定位
    checks["1_location"] = (q.get("unit") == "Unit 3"
                            and q.get("section") == "READING_FOR_WRITING"
                            and q.get("page") in pages_ok
                            and q.get("activity") in acts_ok)
    # 2 evidence ids
    ids = q.get("evidence_block_ids") or []
    checks["2_evidence_ids"] = bool(ids) and all(b in blk for b in ids)
    # 3 evidence quote
    quote = q.get("evidence_quote") or ""
    checks["3_evidence_quote"] = any(
        V.tokens(quote) and " ".join(V.tokens(quote)) in " ".join(V.tokens(blk[b]["text"]))
        for b in ids if b in blk)
    # 4 答案支持（新口径）
    support = V.answer_support(str(q.get("answer") or ""), quote, q.get("question") or "")
    checks["4_answer_support"] = support in ("EXACT", "VERIFIABLE_REFERENCE",
                                             "VERIFIABLE_REPHRASE")
    # 5 词汇白名单（新口径：只看题干/选项/答案）
    extra = V.out_of_scope(V.checked_language(q), allow)
    checks["5_vocab_scope"] = not extra
    # 6 选项
    opts = q.get("options") or []
    if qtype in ("vocab_choice", "reading_choice"):
        co = str(q.get("correct_option") or "").strip().upper()
        ok_co = co in list("ABCD")[:len(opts)]
        checks["6_options"] = (len(opts) >= 3
                               and len(opts) == len({" ".join(V.tokens(o)) for o in opts})
                               and ok_co
                               and " ".join(V.tokens(opts["ABCD".index(co)] if ok_co else ""))
                               == " ".join(V.tokens(str(q.get("answer") or ""))))
    else:
        checks["6_options"] = True
    # 7 去重
    key = " ".join(V.tokens(q.get("question")))
    dup = key in seen_q
    seen_q[key] = qid
    qk = " ".join(V.tokens(quote))[:120]
    dup = dup or (seen_quote.get(qk, 0) > 0)
    seen_quote[qk] = seen_quote.get(qk, 0) + 1
    checks["7_dedup"] = not dup
    # 8 题型规则
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
                 "pass": passed,
                 "database_candidate_program": "YES" if passed else "NO"})

summary = {
    "input": {"context": os.path.join(SRC, "input_context.json"),
              "questions": os.path.join(SRC, "generated_questions.json"),
              "questions_unchanged": True},
    "ai_calls": 0,
    "returned": len(questions),
    "pass": sum(1 for r in rows if r["pass"]),
    "fail": sum(1 for r in rows if not r["pass"]),
    "answer_support_types": {r["question_id"]: r["answer_support_type"] for r in rows},
    "whitelist_size": len(allow),
    "rows": rows,
}
json.dump(summary, open(os.path.join(HERE, "validation_result_v2.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

line = ["# 回归结果（validator v2）", "",
        "- 输入：`20260917_1450_deepseek_min3/generated_questions.json`（原始 AI 输出，未修改）",
        "- AI 调用：**0**（仅重新校验）",
        "- 结果：通过 %d / 失败 %d" % (summary["pass"], summary["fail"]), "",
        "| 题号 | 类型 | 1 定位 | 2 证据id | 3 引用 | 4 答案支持 | 5 词汇 | 6 选项 | 7 去重 | 8 题型 | 总判定 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
for r in rows:
    c = r["checks"]
    line.append(
        "| %s | %s | %s | %s | %s | %s（%s） | %s | %s | %s | %s | **%s** |" % (
            r["question_id"], r["type"],
            "PASS" if c["1_location"] else "FAIL",
            "PASS" if c["2_evidence_ids"] else "FAIL",
            "PASS" if c["3_evidence_quote"] else "FAIL",
            "PASS" if c["4_answer_support"] else "FAIL", r["answer_support_type"],
            "PASS" if c["5_vocab_scope"] else "FAIL",
            "PASS" if c["6_options"] else "FAIL",
            "PASS" if c["7_dedup"] else "FAIL",
            "PASS" if c["8_type_rules"] else "FAIL",
            "PASS" if r["pass"] else "FAIL"))
open(os.path.join(HERE, "validation_report_v2.md"), "w", encoding="utf-8").write(
    "\n".join(line) + "\n")

print("回归：通过 %d / 失败 %d" % (summary["pass"], summary["fail"]))
for r in rows:
    print("  %-4s %-14s %-14s %s" % (r["question_id"], r["type"], r["answer_support_type"],
                                     "PASS" if r["pass"] else "FAIL"))
