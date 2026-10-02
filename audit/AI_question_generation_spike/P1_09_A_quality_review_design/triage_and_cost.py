# -*- coding: utf-8 -*-
"""P1-09-A: deterministic risk triage (program side, no AI) + review cost model.

Read-only. Writes triage_result.json and cost_model.json.
"""

import json
import os
import re
import sqlite3

BASE = r"D:\ZhixueEnglish"
SPIKE = os.path.join(BASE, "audit", "AI_question_generation_spike")
LIB = os.path.join(BASE, "structured", "ai", "question_library.db")
CP = os.path.join(BASE, "structured", "contentpack", "v5", "FLTRP-EN-7A-2022CUR.sqlite")
P1_06 = os.path.join(SPIKE, "P1_06_batch_stability")
HERE = os.path.dirname(os.path.abspath(__file__))


def ro(path):
    con = sqlite3.connect("file:" + path.replace("\\", "/") + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def dump(name, obj):
    with open(os.path.join(HERE, name), "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)


WORD = re.compile(r"[A-Za-z][A-Za-z'\-]*")


def word_count(text):
    return len(WORD.findall(text or ""))


def load_questions(con):
    qs = []
    for r in con.execute("""
            SELECT q.question_id, q.question_type, q.question_text, q.options_json,
                   q.correct_option, q.correct_answer, q.lifecycle_status, q.stale,
                   q.validator_version FROM ai_question q ORDER BY q.question_id"""):
        q = dict(r)
        q["options"] = json.loads(q["options_json"]) if q["options_json"] else []
        note = con.execute("SELECT note FROM question_validation WHERE question_id=?",
                           (q["question_id"],)).fetchone()
        note = note[0] if note else ""
        m = re.search(r"mechanical_rewrite=(\w+)", note or "")
        q["mechanical_rewrite"] = (m.group(1) == "True") if m else None
        qs.append(q)
    return qs


def vocab_pos(cp):
    out = {}
    for r in cp.execute("SELECT lower(lemma) lemma, part_of_speech pos FROM learning_item"
                        " WHERE item_type='vocabulary'"):
        out.setdefault(r["lemma"], set()).add((r["pos"] or "").strip().lower())
    return out


def triage(questions, pos_map):
    rows = []
    for q in questions:
        stem = (q["question_text"] or "").replace("___", " ")
        flags = []
        if q["question_type"] == "fill" and word_count(stem) < 6:
            flags.append("T1_SHORT_CONTEXT_FILL")
        if q["question_type"] == "fill" and q["question_text"].count("___") >= 2:
            flags.append("T2_MULTI_BLANK_FILL")
        if q["mechanical_rewrite"] and word_count(stem) < 8:
            flags.append("T3_MECHANICAL_SHORT_STEM")
        if q["question_type"] in ("vocab_choice", "reading_choice") and q["options"]:
            ans_pos = pos_map.get(q["correct_answer"].strip().lower(), set())
            same_pos = []
            for o in q["options"]:
                if o.strip().lower() == q["correct_answer"].strip().lower():
                    continue
                o_pos = pos_map.get(o.strip().lower())
                if o_pos and ans_pos and (o_pos & ans_pos):
                    same_pos.append(o)
            if same_pos:
                flags.append("T4_DISTRACTOR_SAME_POS_UNIT_VOCAB")
        if q["question_type"] == "fill" and q["options"]:
            flags.append("T5_FILL_WITH_OPTIONS")
        rows.append({"question_id": q["question_id"], "question_type": q["question_type"],
                     "question_text": q["question_text"], "correct_answer": q["correct_answer"],
                     "stem_word_count_without_blank": word_count(stem),
                     "mechanical_rewrite": q["mechanical_rewrite"],
                     "triage_flags": flags, "needs_ai_quality_review": bool(flags)})
    return rows


def cost_model(triage_rows):
    p106 = json.load(open(os.path.join(P1_06, "p1_06_result.json"), encoding="utf-8"))
    cal = json.load(open(os.path.join(SPIKE, "P1_05_budget_calibration_v2",
                                     "calibration_result.json"), encoding="utf-8"))
    gen = []
    for s in p106["sections"]:
        req = json.load(open(os.path.join(P1_06, "%s_request.json" % s["tag"]), encoding="utf-8"))
        chars = sum(len(m["content"]) for m in req["payload"]["messages"])
        gen.append({"tag": s["tag"], "section_id": s["section_id"],
                    "questions": s["questions_count"],
                    "prompt_tokens": s["prompt_tokens"],
                    "completion_tokens": s["completion_tokens"],
                    "reasoning_tokens": s["reasoning_tokens"],
                    "total_tokens": s["total_tokens"], "latency_ms": s["latency_ms"],
                    "prompt_chars": chars,
                    "chars_per_prompt_token": round(chars / s["prompt_tokens"], 3)})
    ratio = sum(g["chars_per_prompt_token"] for g in gen) / len(gen)

    per_sec, tot_chars, tot_q = {}, 0, 0
    for tag in ("S1", "S2", "S3", "S4"):
        parsed = json.load(open(os.path.join(P1_06, "%s_parsed.json" % tag), encoding="utf-8"))
        items = [{"question_id": q.get("question_id"), "type": q.get("type"),
                  "question": q.get("question"), "options": q.get("options"),
                  "answer": q.get("answer"), "evidence_quote": q.get("evidence_quote")}
                 for q in parsed.get("questions", [])]
        payload = json.dumps({"questions": items}, ensure_ascii=False)
        per_sec[tag] = {"questions": len(items), "review_payload_chars": len(payload),
                        "estimated_prompt_tokens": round(len(payload) / ratio)}
        tot_chars += len(payload)
        tot_q += len(items)

    instr_chars = 2600
    out_per_q = 220
    out_per_sec = out_per_q + 260
    risk_ids = sorted({r["question_id"] for r in triage_rows if r["needs_ai_quality_review"]})
    narrow_ids = sorted({r["question_id"] for r in triage_rows
                         if set(r["triage_flags"]) & {"T1_SHORT_CONTEXT_FILL",
                                                      "T2_MULTI_BLANK_FILL",
                                                      "T3_MECHANICAL_SHORT_STEM",
                                                      "T5_FILL_WITH_OPTIONS"}})
    n_risk, n_narrow = len(risk_ids), len(narrow_ids)

    strategies = [
        {"strategy": "1_per_question_call", "api_calls": tot_q,
         "input_tokens": round((tot_q * instr_chars + tot_chars) / ratio),
         "output_tokens": tot_q * out_per_q,
         "note": "每条题目单独一次调用；instruction 重复 22 次；调用次数最多"},
        {"strategy": "2_per_section_batch_call", "api_calls": len(per_sec),
         "input_tokens": round((len(per_sec) * instr_chars + tot_chars) / ratio),
         "output_tokens": len(per_sec) * out_per_sec,
         "note": "每 Section 一次批量复核，与以 Section 为生成边界一致"},
        {"strategy": "3_only_program_PASS", "api_calls": len(per_sec),
         "input_tokens": round((len(per_sec) * instr_chars + tot_chars) / ratio),
         "output_tokens": len(per_sec) * out_per_sec,
         "note": "本数据集 program PASS=22/22，与方案 2 相同；收益取决于被程序拦下的题数"},
        {"strategy": "4_only_high_risk_triage", "api_calls": 1 if n_risk else 0,
         "input_tokens": round((instr_chars + n_risk * 300) / ratio),
         "output_tokens": n_risk * out_per_q,
         "note": "只批量复核 triage 命中的 %d 题；triage 规则见 triage_result.json" % n_risk},
        {"strategy": "4b_only_high_risk_triage_narrow", "api_calls": 1 if n_narrow else 0,
         "input_tokens": round((instr_chars + n_narrow * 300) / ratio),
         "output_tokens": n_narrow * out_per_q,
         "note": "窄口径 triage（T1/T2/T3/T5，不含 T4）命中 %d 题；T4 会连合格题一起命中" % n_narrow},
    ]

    gen_per_q = p106["total_tokens"] / tot_q
    review_per_q_1 = (strategies[0]["input_tokens"] + strategies[0]["output_tokens"]) / tot_q
    review_per_q_2 = (strategies[1]["input_tokens"] + strategies[1]["output_tokens"]) / tot_q
    per_question_comparison = {
        "generation_tokens_per_question": round(gen_per_q, 1),
        "review_tokens_per_question_strategy1": round(review_per_q_1, 1),
        "review_tokens_per_question_strategy2": round(review_per_q_2, 1),
        "strategy1_pct_of_generation": round(review_per_q_1 / gen_per_q * 100, 1),
        "strategy2_pct_of_generation": round(review_per_q_2 / gen_per_q * 100, 1),
        "note": "以题目为单位比较；调用次数与延迟差异主要来自调用数量而不是 token 总量。",
    }

    return {
        "measurement_basis": {
            "generation": gen,
            "generation_calibration_p1_05d": {
                "section_id": cal["sample"], "questions": cal["questions_count"],
                "prompt_tokens": cal["guard"]["verdict"]["usage"]["prompt_tokens"],
                "completion_tokens": cal["guard"]["verdict"]["usage"]["completion_tokens"],
                "reasoning_tokens": cal["guard"]["verdict"]["usage"]
                ["completion_tokens_details"]["reasoning_tokens"],
                "total_tokens": cal["guard"]["verdict"]["usage"]["total_tokens"],
                "latency_ms": cal["latency_ms"], "max_tokens": 16384},
            "chars_per_prompt_token_mean": round(ratio, 3),
            "note": "chars/token 由 4 次真实 P1-06 请求实测标定，不是假设值。"},
        "review_payload_per_section": per_sec,
        "estimates": {"review_instruction_chars": instr_chars,
                      "output_tokens_per_question": out_per_q,
                      "output_tokens_per_section_batch": out_per_sec,
                      "reasoning_cost": "未单独建模；复核任务远短于生成，实际 reasoning 消耗属 P1-09-B 待实测项"},
        "strategies": strategies,
        "per_question_comparison": per_question_comparison,
        "triage": {"flagged_questions_broad": n_risk, "flagged_ids_broad": risk_ids,
                   "flagged_questions_narrow": n_narrow, "flagged_ids_narrow": narrow_ids,
                   "total_questions": tot_q},
        "totals": {"generation_api_calls_p1_06": 4, "questions_p1_06": tot_q,
                   "generation_total_tokens_p1_06": p106["total_tokens"],
                   "generation_total_latency_ms_p1_06": p106["total_latency_ms"]},
    }


RULE_DOC = {
    "T1_SHORT_CONTEXT_FILL": "fill 去掉空位后英文实词少于 6 个：学生只看题干无法确定唯一答案",
    "T2_MULTI_BLANK_FILL": "fill 有两个以上空位",
    "T3_MECHANICAL_SHORT_STEM": "mechanical_rewrite=true 且去空位后少于 8 词",
    "T4_DISTRACTOR_SAME_POS_UNIT_VOCAB": "选择题干扰项是同一 Unit 词表中与答案同词性的词，"
                                         "语法上同样可填空，只能靠课文排除",
    "T5_FILL_WITH_OPTIONS": "fill 题型却带 options（validator v3 type_rules 必判不合法）",
}


def main():
    con, cp = ro(LIB), ro(CP)
    questions = load_questions(con)
    rows = triage(questions, vocab_pos(cp))
    dump("triage_result.json", {"rule_doc": RULE_DOC, "questions": rows})
    dump("cost_model.json", cost_model(rows))
    con.close()
    cp.close()

    flagged = [r for r in rows if r["needs_ai_quality_review"]]
    print("triage flagged %d/%d" % (len(flagged), len(rows)))
    for r in flagged:
        print("  ", r["question_id"], r["question_type"], r["triage_flags"],
              "|", (r["question_text"] or "")[:60])
    cm = json.load(open(os.path.join(HERE, "cost_model.json"), encoding="utf-8"))
    for s in cm["strategies"]:
        print("  %-28s calls=%-3s in=%-6s out=%-6s" % (s["strategy"], s["api_calls"],
                                                      s["input_tokens"], s["output_tokens"]))


if __name__ == "__main__":
    main()
