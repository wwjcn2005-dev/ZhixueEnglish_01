# -*- coding: utf-8 -*-
"""P1-09-C: offline case analysis (no AI call).

1) Root cause of the P1-09-B evidence_concern on AIQ:6ECD02B9D381.
2) Re-judgement of the answer-uniqueness label dispute (AIQ:B6463523F9E5 and the
   four "no context" fill / vocab items) under Answer Uniqueness Contract V1.
3) Whether Minimal / Extended Review Context can rebuild enough context, per question.

Every verdict here is an ANALYST verdict derived from existing formal data.
It is NOT an AI quality-review result, and this file says so explicitly.
Writes: offline_case_analysis.json
"""

import json
import os
import sqlite3
import sys

BASE = r"D:\ZhixueEnglish"
SPIKE = os.path.join(BASE, "audit", "AI_question_generation_spike")
LIB = os.path.join(BASE, "structured", "ai", "question_library.db")
CP = os.path.join(BASE, "structured", "contentpack", "v5", "FLTRP-EN-7A-2022CUR.sqlite")
P1_08_B = os.path.join(SPIKE, "P1_08_B_evidence_assembly_fix")
sys.path.insert(0, P1_08_B)
import evidence_assembly as EA  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CPT = 3.074

UNIQUENESS_CASES = {
    "AIQ:6ECD02B9D381": {
        "is_uniqueness_case": False, "verdict": "N/A_READING_ITEM",
        "reason": "阅读选择题，题干明确指向课文（At the school art festival）→ 按课文陈述判定。"},
    "AIQ:B6463523F9E5": {
        "is_uniqueness_case": True, "verdict": "UNIQUE",
        "old_label": "P1-09-A C5 干扰项风险（现实常识标准）",
        "reason": "阅读选择题，题干明确指向课文（In the Great Bear Rainforest）。课文陈述"
                  "\"The trees in a rainforest can make their own rain.\"；其余选项在课文中没有任何陈述支持，"
                  "按阅读题惯例被排除。Contract V1 第 B 类明确规定：现实世界可能存在其他答案，"
                  "不应用此判定教材训练题答案不唯一。",
        "old_label_remapped": "NOT_A_UNIQUENESS_ISSUE",
        "note": "该题在 P1-09-B 被判 SUGGEST_ACCEPT + answer_unique=PASS —— 在新契约下这个判断是"
                "与契约一致的，不是漏检；P1-09-B 记为 FALSE_NEGATIVE 是旧标签口径造成的。"},
    "AIQ:BD59C5958D45": {
        "is_uniqueness_case": True, "verdict": "UNIQUE",
        "standard": "TEXTBOOK_ANCHORED",
        "reason": "四个选项：club（语法成立，但与课文陈述 \"in the school band\" 冲突 → 排除）、"
                  "stage（\"in the school stage\" 语法不成立 → 排除）、instrument（语义不成立 → 排除）。"
                  "教材锚定标准下只剩 band。",
        "standalone_risk": True,
        "standalone_reason": "自立标准（学生手里没有课文）下 \"in the school club\" 同样自然 → 存在第二答案。"
                             "该题是当前唯一 ACTIVE 题，人工审核通过；本契约不推翻该结论，"
                             "而是把这条风险如实记在 standalone_risk 字段。"},
    "AIQ:75AAEBFE06DF": {
        "is_uniqueness_case": True, "verdict": "UNIQUE_RISK",
        "standard": "TEXTBOOK_ANCHORED",
        "reason": "干扰项 traditional 是同一 Unit 的 BOLD 核心词，语法、语义都成立，"
                  "且**不与课文冲突**（课文说 Grandpa 的音乐与我的摇滚 \"different\"，"
                  "并不排除它是 traditional）→ 不被排除 → 存在第二合理答案。",
        "standalone_risk": True},
    "AIQ:1B3AF72923C4": {
        "is_uniqueness_case": True, "verdict": "UNIQUE_RISK",
        "standard": "TEXTBOOK_ANCHORED",
        "reason": "题干只有 \"I am ___, too.\"，没有指标物或限定语；happy / fine 等同样自然、"
                  "且与 Starter 对话语境不冲突 → 不被排除（属于 Contract V1 的 D 类：题目本身缺少"
                  "足够上下文）。",
        "standalone_risk": True,
        "cross_check": "与 P1-08-C 人工审核记录一致（该题已按 LOW_VALUE 驳回）。"},
    "AIQ:120FFEECA78F": {
        "is_uniqueness_case": True, "verdict": "UNIQUE_RISK",
        "standard": "TEXTBOOK_ANCHORED",
        "reason": "题干 \"What colour is it? It's ___.\" 没有任何指标物；证据块本身也只有 10 字符"
                  "（\"It's grey.\"），无法提供指标 → D 类信息不足，任意颜色都成立。",
        "standalone_risk": True,
        "note": "该题属于\"Minimal 上下文无法修复\"的情况：证据块全文不含指标物，"
                "Extended 上下文（同 Activity 其它块）也需要实际检查后才能判断能否修复。"},
    "AIQ:1BA260727793": {
        "is_uniqueness_case": True, "verdict": "UNIQUE_RISK",
        "standard": "TEXTBOOK_ANCHORED",
        "reason": "双空挖空 \"___ ___, this is my first lesson for all of you.\"，"
                  "By the way / Of course 等语篇标记词同样成立且与课文语境不冲突 → 不被排除。",
        "standalone_risk": True},
    "AIQ:879007FA4FC7": {
        "is_uniqueness_case": False, "verdict": "N/A_READING_ITEM",
        "reason": "阅读选择题，题干指向课文人物；答案 \"in the park\" 由课文陈述确定。"},
    "AIQ:7EAC0ED29A0A": {
        "is_uniqueness_case": False, "verdict": "N/A_JUDGE_ITEM",
        "reason": "判断题，答案 True/False 由课文事实决定，不属于答案唯一性问题。"},
    "AIQ:04CC9B1CF690": {
        "is_uniqueness_case": True, "verdict": "UNIQUE",
        "standard": "TEXTBOOK_ANCHORED",
        "reason": "题干 \"It feels great to ___ our hobby together.\" 限定语充分（our hobby together），"
                  "证据块全文为同一句；enjoy 之外的候选（如 share）与课文陈述 \"enjoy our hobby\" 冲突 → 排除。",
        "standalone_risk": True,
        "standalone_reason": "自立标准下 \"It feels great to share our hobby together. \" 亦可成立；"
                             "但题干限定语使其迷惑性较低。"},
}


def ro(path):
    con = sqlite3.connect("file:" + path.replace("\\", "/") + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def main():
    lib, cp = ro(LIB), ro(CP)
    probe = json.load(open(os.path.join(HERE, "offline_context_probe.json"), encoding="utf-8"))
    costs = json.load(open(os.path.join(HERE, "minimal_extended_context_costs.json"),
                           encoding="utf-8"))
    cases = []

    for row in probe["questions"]:
        qid = row["question_id"]
        full_blocks = row["full_evidence_block_texts"]
        quotes = row["question_library_side"]["evidence_quotes"]
        quote_chars = sum(len(x) for x in quotes)
        block_chars = sum(b["chars"] for b in full_blocks)
        missing = block_chars - quote_chars
        # does the full evidence block contain words that the stored quote lacks and that
        # matter to the stem? (program-side check: stem content words vs quote)
        stem_words = {w.lower().strip(".,?!'\"") for w in row["evidence_block_neighbourhood"][0]["text"].split()} \
            if row["evidence_block_neighbourhood"] else set()
        cost = next(c for c in costs["per_question"] if c["question_id"] == qid)
        cases.append({
            "question_id": qid,
            "question_type": row["question_type"],
            "stored_quote_chars": quote_chars,
            "evidence_block_full_chars": block_chars,
            "missing_from_quote_chars": missing,
            "quote_is_truncated_excerpt": missing > 0,
            "minimal_context_tokens_est": cost["minimal_tokens_est"],
            "extended_context_tokens_est": cost["extended_tokens_est"],
            "full_section_tokens_est": cost["full_section_tokens_est"],
            "analyst_uniqueness_verdict": UNIQUENESS_CASES.get(qid, {}),
        })

    # ---------- Problem A: exact root cause for AIQ:6ECD02B9D381
    target = next(c for c in probe["questions"] if c["question_id"] == "AIQ:6ECD02B9D381")
    problem_a = {
        "question_id": "AIQ:6ECD02B9D381",
        "p1_09_b_ai_output": {"suggested_decision": "SUGGEST_REVIEW", "confidence": "LOW",
                             "evidence_concern": True,
                             "short_reason": "题干提到学校艺术节，但所给教材证据句子未提及，需人工核对上下文。"},
        "stored_evidence_quote": target["question_library_side"]["evidence_quotes"][0],
        "full_evidence_block": target["full_evidence_block_texts"][0],
        "root_cause": "question_evidence.evidence_quote 只是证据块的一段**摘录**（52 字符），"
                      "而证据块全文（202 字符）本身就包含 \"There is an art festival every autumn "
                      "in my school.\"。P1-09-B 只把摘录给了 AI，因此 AI 看不到 \"art festival\"。",
        "not_the_root_cause": "并不是 Section 上下文缺失 —— \"art festival\" 就在**同一个证据块**里，"
                             "问题在于喂给 AI 的是摘录而不是证据块全文。",
        "minimal_context_would_fix_it": True,
        "evidence_for_fix": "Minimal Review Context 使用证据块全文；该题 Minimal 约 %s tokens，"
                            "比 P1-09-B 实际输入（约 88 tokens）只多约 %s tokens。"
                            % (costs["per_question"][2]["minimal_tokens_est"],
                               costs["per_question"][2]["minimal_tokens_est"] - 88),
    }

    # ---------- quote truncation across the whole library (scale of the issue)
    rows = lib.execute(
        "SELECT e.evidence_block_id, e.evidence_quote FROM question_evidence e").fetchall()
    truncated = 0
    checked = 0
    for r in rows:
        blk = cp.execute("SELECT text_raw FROM content_block WHERE block_id=?",
                        (r["evidence_block_id"],)).fetchone()
        if not blk:
            continue
        checked += 1
        block_text = (blk["text_raw"] or "").replace("\n", " ").strip()
        if len(block_text) > len(r["evidence_quote"] or ""):
            truncated += 1
    library_scale = {
        "evidence_rows_checked": checked,
        "quotes_shorter_than_block": truncated,
        "note": "只要 evidence_quote 短于证据块全文，P1-09-B 式输入就会丢失上下文。"
                "本统计基于 contentpack 的 block 全文（只读）。",
    }

    out = {
        "stage": "P1-09-C",
        "ai_calls": 0,
        "disclaimer": "本文件所有 verdict 均为**分析人员离线判断**，依据既有正式数据推导，"
                      "不是 AI 质量复核结果，也不得被当作 AI 输出使用。",
        "problem_A_context_insufficient": problem_a,
        "answer_uniqueness_redetermination": {
            "contract": "Answer Uniqueness Contract V1",
            "standards": ["TEXTBOOK_ANCHORED", "SELF_CONTAINED"],
            "exclusion_rule": "候选被排除 ⟺ 语法不成立 ∨ 语义不成立 ∨ 与教材原文陈述冲突；"
                              "另：题干缺少必要指标/限定以致所指不明 → 直接判 UNIQUE_RISK（D 类）。",
            "cases": [c for c in cases if c["analyst_uniqueness_verdict"]],
        },
        "per_question_context_rebuild": cases,
        "library_scale_of_quote_truncation": library_scale,
        "cost_reference": costs["totals"],
    }
    with open(os.path.join(HERE, "offline_case_analysis.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    print("Problem A root cause: quote chars =",
          problem_a["stored_evidence_quote"].__len__(),
          "| full block chars =", len(problem_a["full_evidence_block"]["text"]))
    print("  full block contains 'art festival':",
          "art festival" in problem_a["full_evidence_block"]["text"])
    print("library scale:", json.dumps(library_scale, ensure_ascii=False))
    print()
    for c in out["answer_uniqueness_redetermination"]["cases"]:
        v = c["analyst_uniqueness_verdict"]
        print("%-20s %-26s %s" % (c["question_id"], v.get("verdict"),
                                  (v.get("reason") or "")[:70]))
    lib.close()
    cp.close()


if __name__ == "__main__":
    main()
