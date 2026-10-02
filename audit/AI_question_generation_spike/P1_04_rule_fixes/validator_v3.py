"""P1-04 · validator v3 = validator v2（原样，不放宽） + 一条更严的 fill 结构规则。

设计原则：
  * **不修改** validator_v2.py（它以只读方式被 import，能力原样转出）
  * v3 只**收紧**题型结构规则（problem B），不放宽任何既有规则
  * EXACT 特殊复核规则（problem A）属于**题库侧**规则，不在 validator 内实现，
    见 ql_schema_v2.py 的触发器与 exact_print_risk()
"""
import os
import re
import sys

V2_DIR = os.path.join(r"D:\ZhixueEnglish", "audit", "AI_question_generation_spike",
                      "20260917_1520_validator_fix")
if V2_DIR not in sys.path:
    sys.path.insert(0, V2_DIR)
import validator_v2 as _v2  # noqa: E402

VALIDATOR_VERSION = "v3"
BASE_VALIDATOR_VERSION = "v2"

# ---------------------------------------------------------------- v2 能力原样转出（不放宽）
tokens = _v2.tokens
answer_support = _v2.answer_support
build_whitelist = _v2.build_whitelist
checked_language = _v2.checked_language
out_of_scope = _v2.out_of_scope
FUNC = _v2.FUNC
PRONOUNS = _v2.PRONOUNS
CONTRACTION = _v2.CONTRACTION

PASS_SUPPORT = ("EXACT", "VERIFIABLE_REFERENCE", "VERIFIABLE_REPHRASE")
SELECTABLE_TYPES = ("vocab_choice", "reading_choice")

_WS = re.compile(r"\s+")


def norm_text(text) -> str:
    s = str(text or "")
    for a, b in (("\u2019", "'"), ("\u2018", "'"), ("\u201c", '"'), ("\u201d", '"')):
        s = s.replace(a, b)
    return _WS.sub(" ", s).strip().lower()


# ---------------------------------------------------------------- P1-04 · 题型结构规则
def type_rules(q: dict):
    """P1-04 收紧后的题型结构规则。返回 (ok, reason)。

    `fill` 的正式定义 = **纯填空题**：
      * 题干必须含空位 `___`
      * **不得**携带 options
      * **不得**携带 correct_option
    """
    qtype = str(q.get("type") or q.get("question_type") or "")
    text = str(q.get("question") or q.get("question_text") or "")
    opts = q.get("options") or []
    co = str(q.get("correct_option") or "").strip()

    if qtype == "fill":
        if "___" not in text:
            return False, "fill requires a blank '___'"
        if opts:
            return False, "fill must not carry options (P1-04: fill = 纯填空)"
        if co:
            return False, "fill must not carry correct_option (P1-04: fill = 纯填空)"
        return True, ""
    if qtype in SELECTABLE_TYPES:
        if len(opts) < 3:
            return False, "%s requires >= 3 options" % qtype
        if not co:
            return False, "%s requires correct_option" % qtype
        return True, ""
    if qtype == "reading_judge":
        if str(q.get("answer") or "").strip().lower() not in ("true", "false", "t", "f", "yes", "no"):
            return False, "reading_judge requires a boolean answer"
        return True, ""
    return False, "unknown question_type: %r" % qtype


# ---------------------------------------------------------------- P1-04 · EXACT 特殊复核条件
def exact_print_risk(answer_support_type, options, correct_answer, evidence_quotes):
    """P1-04 修正后的 EXACT 特殊人工复核条件（与数据库触发器保持同一语义）。

    触发当且仅当三者同时成立：
      1. `answer_support_type == 'EXACT'`
      2. 题目是**可选型**（携带 options）——纯填空题由孩子自己写出答案，不存在“照抄可见选项”的风险
      3. **正确答案文本本身出现在教材 evidence_quote 中**
         （即教材原文已直接印出该答案；而不是因为答案恰好是选项之一）

    仅“答案出现在 options 里”**不再**触发（修正 P1-03 的选择题必然误报）。
    仅“错误选项出现在 evidence_quote 里”**不**触发（只看正确答案）。
    """
    if answer_support_type != "EXACT":
        return False
    if not options:
        return False
    a = norm_text(correct_answer)
    if not a:
        return False
    return any(a in norm_text(x) for x in (evidence_quotes or []))


# ---------------------------------------------------------------- 完整 8 项校验
def validate_question(q: dict, *, blocks_by_id, pages_ok, acts_ok, allow,
                      unit_label, section_key, evidence_quotes=()):
    """跑 v2 的 8 项校验，其中第 8 项使用 v3 的收紧规则。"""
    qtype = str(q.get("type") or q.get("question_type") or "?")
    checks = {}
    checks["1_location"] = (q.get("unit") == unit_label and q.get("section") == section_key
                            and q.get("page") in pages_ok and q.get("activity") in acts_ok)
    ids = q.get("evidence_block_ids") or []
    checks["2_evidence_ids"] = bool(ids) and all(b in blocks_by_id for b in ids)
    quote = q.get("evidence_quote") or ""
    checks["3_evidence_quote"] = any(
        tokens(quote) and " ".join(tokens(quote)) in " ".join(tokens(blocks_by_id[b]["text"]))
        for b in ids if b in blocks_by_id)
    support = answer_support(str(q.get("answer") or ""), quote, q.get("question") or "")
    checks["4_answer_support"] = support in PASS_SUPPORT
    extra = out_of_scope(checked_language(q), allow)
    checks["5_vocab_scope"] = not extra
    opts = q.get("options") or []
    if qtype in SELECTABLE_TYPES:
        co = str(q.get("correct_option") or "").strip().upper()
        ok_co = co in list("ABCD")[:len(opts)]
        checks["6_options"] = (len(opts) >= 3 and ok_co and
                               " ".join(tokens(opts["ABCD".index(co) if ok_co else ""]))
                               == " ".join(tokens(str(q.get("answer") or ""))))
    else:
        checks["6_options"] = True
    ok8, reason8 = type_rules(q)
    checks["8_type_rules"] = ok8
    return {"checks": checks, "answer_support_type": support,
            "out_of_scope_tokens": extra, "type_rule_reason": reason8,
            "pass": all(checks.values())}


def validate_batch(questions, *, blocks_by_id, pages_ok, acts_ok, allow,
                   unit_label, section_key):
    """对一批题跑完整 8 项（第 7 项去重需要批次上下文）。"""
    seen_q, seen_quote, rows = {}, {}, []
    for i, q in enumerate(questions, 1):
        r = validate_question(q, blocks_by_id=blocks_by_id, pages_ok=pages_ok,
                              acts_ok=acts_ok, allow=allow, unit_label=unit_label,
                              section_key=section_key)
        key_q = " ".join(tokens(q.get("question") or ""))
        dup = key_q in seen_q
        seen_q[key_q] = i
        kq = " ".join(tokens(q.get("evidence_quote") or ""))[:120]
        dup = dup or seen_quote.get(kq, 0) > 0
        seen_quote[kq] = seen_quote.get(kq, 0) + 1
        r["checks"]["7_dedup"] = not dup
        r["pass"] = all(r["checks"].values())
        r["source_index"] = i
        rows.append(r)
    return rows
