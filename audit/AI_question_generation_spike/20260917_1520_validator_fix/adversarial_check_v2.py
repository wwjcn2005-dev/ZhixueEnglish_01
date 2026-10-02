"""对抗性检查：用 6 个**合成**坏样本验证 v2 校验器仍能拦住问题（不调用 AI）。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validator_v2 as V  # noqa: E402
from regression_v2 import blk, pages_ok, acts_ok, allow  # noqa: E402

BASE = {"unit": "Unit 3", "section": "READING_FOR_WRITING", "page": 56, "activity": 2,
        "evidence_block_ids": ["FLTRP-EN-7A-2022CUR:P61:B5"],
        "evidence_quote": "But Robert has a serious disease and cannot move at all.",
        "type": "fill", "question": "But Robert has a serious ___ and cannot move at all.",
        "options": [], "answer": "disease", "correct_option": ""}

CASES = [
    ("A 教材外词汇出现在选项", {**BASE, "type": "vocab_choice", "options":
                            ["disease", "dinosaur", "trailer", "road"], "correct_option": "A"},
     "5_vocab_scope"),
    ("B 答案无教材支持（世界知识）", {**BASE, "type": "fill",
                             "question": "Bike racing began in ___.", "answer": "France"},
     "4_answer_support"),
    ("C 引用被编造", {**BASE, "evidence_quote": "Robert likes playing computer games at home.",
                 "answer": "disease"}, "3_evidence_quote"),
    ("D 证据 id 不存在", {**BASE, "evidence_block_ids": ["FLTRP-EN-7A-2022CUR:P99:B9"]},
     "2_evidence_ids"),
    ("E fill 题没有空位", {**BASE, "question": "Robert has a serious disease."}, "8_type_rules"),
    ("F correct_option 与答案不一致", {**BASE, "type": "vocab_choice",
                              "options": ["disease", "road", "trailer", "result"],
                              "correct_option": "B", "answer": "disease"}, "6_options"),
]


def check(q):
    """复用回归脚本的 8 项判定（简化：只返回关键项）。"""
    out = {}
    out["1_location"] = (q.get("unit") == "Unit 3" and q.get("section") == "READING_FOR_WRITING"
                         and q.get("page") in pages_ok and q.get("activity") in acts_ok)
    ids = q.get("evidence_block_ids") or []
    out["2_evidence_ids"] = bool(ids) and all(b in blk for b in ids)
    quote = q.get("evidence_quote") or ""
    out["3_evidence_quote"] = any(
        V.tokens(quote) and " ".join(V.tokens(quote)) in " ".join(V.tokens(blk[b]["text"]))
        for b in ids if b in blk)
    support = V.answer_support(str(q.get("answer") or ""), quote, q.get("question") or "")
    out["4_answer_support"] = support in ("EXACT", "VERIFIABLE_REFERENCE", "VERIFIABLE_REPHRASE")
    out["5_vocab_scope"] = not V.out_of_scope(V.checked_language(q), allow)
    qtype = q.get("type")
    opts = q.get("options") or []
    if qtype in ("vocab_choice", "reading_choice"):
        co = str(q.get("correct_option") or "").strip().upper()
        ok_co = co in list("ABCD")[:len(opts)]
        out["6_options"] = bool(ok_co) and (
            " ".join(V.tokens(opts["ABCD".index(co)])) == " ".join(V.tokens(str(q.get("answer")))))
    else:
        out["6_options"] = True
    out["7_dedup"] = True          # 单题场景
    if qtype == "fill":
        out["8_type_rules"] = "___" in (q.get("question") or "")
    else:
        out["8_type_rules"] = len(opts) >= 3 and bool(q.get("correct_option"))
    return out, support


rows = []
for name, q, must_fail in CASES:
    checks, support = check(q)
    caught = checks[must_fail] is False
    rows.append({"case": name, "expect_fail_on": must_fail, "caught": caught,
                 "checks": checks, "answer_support_type": support})
    print("%-28s 期望在 %-18s 拦截 -> %s" % (name, must_fail, "已拦截" if caught else "未拦截(漏检!)"))

json.dump({"note": "全部为合成坏样本，仅用于验证校验器拦截能力；不涉及任何 AI 输出",
           "cases": rows,
           "all_caught": all(r["caught"] for r in rows)},
          open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "adversarial_result.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
