# -*- coding: utf-8 -*-
"""P1-09-A: real-question sample matrix for P1-09-B, built from question_library.db.

Read-only. Every question_id below is verified to exist; fields are read from the DB,
never hand-copied. Categories with no real sample are declared as gaps.
"""

import json
import os
import sqlite3

LIB = r"D:\ZhixueEnglish\structured\ai\question_library.db"
HERE = os.path.dirname(os.path.abspath(__file__))

CATEGORIES = [
    ("C1_obviously_acceptable", "明显合格题",
     ["AIQ:BD59C5958D45", "AIQ:04CC9B1CF690"],
     "答案在教材原句中逐字命中；答案为教材 BOLD 核心词；题干语境完整。"),
    ("C2_low_learning_value", "低学习价值题",
     ["AIQ:1B3AF72923C4", "AIQ:1BA260727793"],
     "AIQ:1B3AF72923C4 已在 P1-08-C 被人工驳回（LOW_VALUE）；"
     "AIQ:1BA260727793 为双空挖空的语篇标记词片段。"),
    ("C3_answer_not_unique_risk", "答案不唯一风险题",
     ["AIQ:1B3AF72923C4", "AIQ:120FFEECA78F"],
     "两条题的程序判定都是 EXACT；单看题干时 happy/fine 或任意颜色同样成立，"
     "唯一性依赖学生手上就有教材原句。"),
    ("C4_mechanical_reproduction", "机械挖空题",
     ["AIQ:1BA260727793", "AIQ:1B3AF72923C4", "AIQ:3C02F6486DFF", "AIQ:BD59C5958D45",
      "AIQ:C3E6FD29F680", "AIQ:04CC9B1CF690", "AIQ:E5F4C046FA61"],
     "question_validation.note 中 mechanical_rewrite=True 的真实题（7 条）；"
     "其中包含已在 P1-08-C 审核通过的 AIQ:BD59C5958D45，说明机械挖空本身不等于不合格。"),
    ("C5_distractor_risk", "选择题干扰项风险题",
     ["AIQ:75AAEBFE06DF", "AIQ:3179968E3E74", "AIQ:B6463523F9E5"],
     "AIQ:75AAEBFE06DF 的干扰项 traditional/electric/weak 全部是教材 BOLD 核心词且语法上同样可填空；"
     "AIQ:B6463523F9E5 的干扰项 sugar/oxygen/food 在其他语境下对树木同样成立。"),
    ("C6_reading_comprehension", "阅读理解题",
     ["AIQ:879007FA4FC7", "AIQ:6ECD02B9D381", "AIQ:B6463523F9E5", "AIQ:CD8B21681B4C"],
     "reading_choice 全部 4 条；其中 AIQ:6ECD02B9D381 是 difficulty=medium、"
     "answer_support=VERIFIABLE_REPHRASE 的唯一一条。"),
    ("C7_vocabulary_choice", "vocabulary_choice",
     ["AIQ:BD59C5958D45", "AIQ:75AAEBFE06DF", "AIQ:5B4C80443D5F", "AIQ:A9D1F3EC6020",
      "AIQ:3179968E3E74", "AIQ:6721EC6C5D1F"],
     "vocab_choice 全部 6 条。"),
    ("C8_fill", "fill",
     ["AIQ:1B3AF72923C4", "AIQ:3C02F6486DFF", "AIQ:120FFEECA78F", "AIQ:7EBCDBC29563",
      "AIQ:D976787A0A43", "AIQ:1BA260727793", "AIQ:C3E6FD29F680", "AIQ:E5F4C046FA61",
      "AIQ:04CC9B1CF690"],
     "fill 全部 9 条（其中 AIQ:7EBCDBC29563 是 P1-03 遗留、类型标记为 fill 却带 options，"
     "validator v3 type_rules 判不合法，已标 STALE）。"),
    ("C9_judge", "reading_judge",
     ["AIQ:7EAC0ED29A0A", "AIQ:80F1D28C3101"],
     "reading_judge 全部 2 条；均为 True/False，程序 answer_support 无法直接判定，"
     "P1-07 采用 rule4_waived_for_judge 兼容处理。"),
]

GAPS = [
    {"category": "英语本身存在错误的题", "status": "现有真实样本不足",
     "detail": "21 条真实题中未发现语法/拼写错误的题（全部 difficulty=easy/medium，"
               "程序与人工均未发现语言错误）。要测 AI 复核能否发现真实语言错误，"
               "只能另建人工撰写的 fixture，不得调用 AI 生成。"},
    {"category": "干扰项明显垃圾/荒谬的题", "status": "现有真实样本不足",
     "detail": "现有选择题干扰项全部来自教材词表，没有明显无意义选项，无法覆盖"
               "distractor_quality=poor 的真实样本。"},
    {"category": "难度明显超出初一阶段的题", "status": "现有真实样本不足",
     "detail": "grade_fit 维度没有真实反例；21 条题全部为 easy（除 1 条 medium）。"},
    {"category": "程序层结构非法但未被拦下的题", "status": "部分覆盖",
     "detail": "AIQ:7EBCDBC29563 是唯一一条 validator v3 type_rules 会判不合法的题，"
               "但它在入库时使用的是 validator v2，之后被标 STALE。"},
]


def main():
    con = sqlite3.connect("file:" + LIB.replace("\\", "/") + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    def fetch(qid):
        r = cur.execute("SELECT question_id, question_type, section_id, activity_id, page,"
                        " question_text, options_json, correct_option, correct_answer, difficulty,"
                        " lifecycle_status, stale, stale_reason, validator_version,"
                        " needs_human_review FROM ai_question WHERE question_id=?", (qid,)).fetchone()
        if r is None:
            raise SystemExit("question not found: " + qid)
        q = dict(r)
        q["evidence"] = [dict(e) for e in cur.execute(
            "SELECT evidence_block_id, evidence_quote FROM question_evidence WHERE question_id=?"
            " ORDER BY ordinal", (qid,))]
        v = cur.execute("SELECT validation_result, answer_support_type, note FROM question_validation"
                        " WHERE question_id=?", (qid,)).fetchone()
        q["validation"] = dict(v) if v else None
        return q

    out = {"stage": "P1-09-A", "ai_calls": 0, "source": LIB, "categories": [], "gaps": GAPS}
    for key, label, ids, why in CATEGORIES:
        out["categories"].append({
            "category": key, "label_zh": label, "why": why,
            "questions": [fetch(i) for i in ids],
        })
    con.close()

    with open(os.path.join(HERE, "sample_matrix.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    for c in out["categories"]:
        print("%-30s %-14s %d 题: %s" % (c["category"], c["label_zh"], len(c["questions"]),
                                         ", ".join(q["question_id"] for q in c["questions"])))
    print("gaps:", [g["category"] + "=" + g["status"] for g in GAPS])


if __name__ == "__main__":
    main()
