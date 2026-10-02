# -*- coding: utf-8 -*-
"""P1-09-A read-only audit: question_library.db v2 + validator capability + cost model.

No AI call. No write to any database. Everything read-only.
"""

import hashlib
import json
import os
import re
import sqlite3
import sys

BASE = r"D:\ZhixueEnglish"
SPIKE = os.path.join(BASE, "audit", "AI_question_generation_spike")
LIB = os.path.join(BASE, "structured", "ai", "question_library.db")
HERE = os.path.dirname(os.path.abspath(__file__))
V2_DIR = os.path.join(SPIKE, "20260917_1520_validator_fix")
V3_DIR = os.path.join(SPIKE, "P1_04_rule_fixes")
P1_06 = os.path.join(SPIKE, "P1_06_batch_stability")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def ro(path):
    con = sqlite3.connect("file:" + path.replace("\\", "/") + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def dump(name, obj):
    with open(os.path.join(HERE, name), "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)
    return name


def read_questions(con):
    out = []
    for r in con.execute("""
            SELECT q.question_id, q.version, q.question_type, q.question_text, q.options_json,
                   q.correct_option, q.correct_answer, q.explanation, q.difficulty,
                   q.textbook_id, q.snapshot_id, q.unit_id, q.section_id, q.activity_id, q.page,
                   q.generation_run_id, q.generated_at, q.question_fingerprint,
                   q.lifecycle_status, q.active, q.stale, q.stale_reason, q.validator_version,
                   q.needs_human_review, q.created_at, q.updated_at
            FROM ai_question q ORDER BY q.section_id, q.activity_id, q.question_id"""):
        q = dict(r)
        q["options"] = json.loads(q["options_json"]) if q["options_json"] else []
        q["evidence"] = [dict(e) for e in con.execute(
            "SELECT ordinal, evidence_block_id, evidence_quote, is_primary FROM question_evidence"
            " WHERE question_id=? ORDER BY ordinal", (q["question_id"],))]
        q["learning_objects"] = [dict(e) for e in con.execute(
            "SELECT item_id, is_primary FROM question_learning_object WHERE question_id=?"
            " ORDER BY is_primary DESC, item_id", (q["question_id"],))]
        q["validation"] = [dict(e) for e in con.execute(
            "SELECT validator_version, validation_result, validated_at, answer_support_type,"
            " checks_json, out_of_scope_tokens_json, needs_human_review, note"
            " FROM question_validation WHERE question_id=?", (q["question_id"],))]
        q["events"] = [dict(e) for e in con.execute(
            "SELECT event_id, event_type, from_status, to_status, event_at, actor, actor_kind,"
            " reason_code FROM question_event WHERE question_id=? ORDER BY version, event_at",
            (q["question_id"],))]
        note = (q["validation"][0]["note"] or "") if q["validation"] else ""
        m = re.search(r"mechanical_rewrite=(\w+)", note)
        q["mechanical_rewrite_from_note"] = (m.group(1) == "True") if m else None
        m2 = re.search(r"original_textbook=(\w+)", note)
        q["original_textbook_from_note"] = (m2.group(1) == "True") if m2 else None
        q["run"] = dict(con.execute(
            "SELECT run_id, model, prompt_version, context_hash, provider, max_tokens,"
            " finish_reason, usage_json, elapsed_ms, status, generated_at, context_ref, raw_response_ref"
            " FROM generation_run WHERE run_id=?", (q["generation_run_id"],)).fetchone() or {})
        out.append(q)
    return out


def validator_capability(questions):
    """Recompute validator v2/v3 judgements on the stored questions (read-only, no AI)."""
    sys.dont_write_bytecode = True
    sys.path.insert(0, V3_DIR)
    sys.path.insert(0, V2_DIR)
    import validator_v2 as v2  # noqa: E402
    import validator_v3 as v3  # noqa: E402

    rows = []
    for q in questions:
        quote = " ".join(e["evidence_quote"] for e in q["evidence"])
        support_v2 = v2.answer_support(q["correct_answer"], quote, q["question_text"])
        support_v3 = v3.answer_support(q["correct_answer"], quote, q["question_text"])
        tr_ok, tr_reason = v3.type_rules({"type": q["question_type"], "question": q["question_text"],
                                          "options": q["options"],
                                          "correct_option": q["correct_option"],
                                          "answer": q["correct_answer"]})
        stored = q["validation"][0]["answer_support_type"] if q["validation"] else None
        rows.append({
            "question_id": q["question_id"],
            "question_type": q["question_type"],
            "question_text": q["question_text"],
            "correct_answer": q["correct_answer"],
            "options": q["options"],
            "evidence_quote": quote,
            "validator_v2_answer_support": support_v2,
            "validator_v3_answer_support": support_v3,
            "stored_answer_support_type": stored,
            "recompute_matches_stored": (support_v3 == stored) and support_v3 is not None,
            "v3_type_rules_ok": tr_ok,
            "v3_type_rules_reason": tr_reason,
        })
    return rows


REVIEW_CHECKS_V3 = [
    "1_location", "2_evidence_ids", "3_evidence_quote", "4_answer_support",
    "5_vocab_scope", "6_options", "7_dedup", "8_type_rules",
]


def cost_model(questions):
    """Real measurements from P1-05-D / P1-06 + a program-side review payload size estimate."""
    p106 = json.load(open(os.path.join(P1_06, "p1_06_result.json"), encoding="utf-8"))
    cal = json.load(open(os.path.join(SPIKE, "P1_05_budget_calibration_v2", "calibration_result.json"),
                         encoding="utf-8"))

    gen = []
    for s in p106["sections"]:
        tag = s["tag"]
        req = json.load(open(os.path.join(P1_06, "%s_request.json" % tag), encoding="utf-8"))
        msgs = req["payload"]["messages"]
        chars = sum(len(m["content"]) for m in msgs)
        gen.append({
            "tag": tag, "section_id": s["section_id"],
            "questions": s["questions_count"],
            "prompt_tokens": s["prompt_tokens"], "completion_tokens": s["completion_tokens"],
            "reasoning_tokens": s["reasoning_tokens"], "total_tokens": s["total_tokens"],
            "latency_ms": s["latency_ms"],
            "prompt_chars": chars,
            "chars_per_prompt_token": round(chars / s["prompt_tokens"], 3),
        })
    cal_rec = {
        "section_id": cal["sample"], "questions": cal["questions_count"],
        "prompt_tokens": cal["guard"]["verdict"]["usage"]["prompt_tokens"],
        "completion_tokens": cal["guard"]["verdict"]["usage"]["completion_tokens"],
        "reasoning_tokens": cal["guard"]["verdict"]["usage"]["completion_tokens_details"]["reasoning_tokens"],
        "total_tokens": cal["guard"]["verdict"]["usage"]["total_tokens"],
        "latency_ms": cal["latency_ms"], "max_tokens": 16384,
    }

    ratio = sum(g["chars_per_prompt_token"] for g in gen) / len(gen)

    # program-side review payload: per question, the parts a reviewer would need
    per_section = {}
    for tag in ("S1", "S2", "S3", "S4"):
        parsed = json.load(open(os.path.join(P1_06, "%s_parsed.json" % tag), encoding="utf-8"))
        items = []
        for q in parsed.get("questions", []):
            items.append({
                "question_id_local": q.get("question_id"),
                "type": q.get("type"),
                "question": q.get("question"),
                "options": q.get("options"),
                "correct_option": q.get("correct_option"),
                "answer": q.get("answer"),
                "evidence_block_ids": q.get("evidence_block_ids"),
                "evidence_quote": q.get("evidence_quote"),
                "mechanical_rewrite_flag": None,
            })
        payload = json.dumps({"section_id": None, "questions": items}, ensure_ascii=False)
        per_section[tag] = {
            "questions": len(items),
            "review_payload_chars_no_instruction": len(payload),
            "estimated_prompt_tokens": round(len(payload) / ratio),
        }

    instruction_chars = 2600  # reviewer system prompt + output schema + evidence rules (design estimate)
    strategies = []
    tot_q = sum(v["questions"] for v in per_section.values())
    tot_in = sum(v["review_payload_chars_no_instruction"] for v in per_section.values())
    # (1) per-question calls
    q_tokens = [v["review_payload_chars_no_instruction"] / v["questions"] for v in per_section.values()]
    in1 = sum((instruction_chars + t) for t in q_tokens)
    strategies.append({"strategy": "1_per_question_call", "api_calls": tot_q,
                       "input_tokens": round(in1 / ratio),
                       "note": "instruction 每条题目都要重复一次"})
    # (2) per-Section batch call
    in2 = len(per_section) * instruction_chars + tot_in
    strategies.append({"strategy": "2_per_section_batch_call", "api_calls": len(per_section),
                       "input_tokens": round(in2 / ratio),
                       "note": "instruction 每个 Section 重复一次"})
    # (3) only program-PASS questions -> in this dataset all 22 were PASS, so identical to (2)
    strategies.append({"strategy": "3_only_program_PASS", "api_calls": len(per_section),
                       "input_tokens": round(in2 / ratio),
                       "note": "本数据集 program PASS = 22/22，故与方案 2 相同；过滤能力取决于被拦题数"})
    # (4) only high-risk questions (deterministic triage): fill blanked from a sentence with no
    #     supporting context / vocab_choice whose distractors are same-part-of-speech unit words
    risk_ids = ["S1#2(different)", "S3#?", "S4#4(ready-like)"]
    strategies.append({"strategy": "4_only_high_risk_triage", "api_calls": len(risk_ids),
                       "input_tokens": round((len(risk_ids) * instruction_chars + tot_in / 4) / ratio),
                       "note": "需先有确定性 triage 规则；本轮只给出估算口径"})

    return {
        "generation_measurements": gen,
        "generation_calibration_p1_05d": cal_rec,
        "chars_per_prompt_token_mean": round(ratio, 3),
        "review_payload_per_section": per_section,
        "review_instruction_chars_estimate": instruction_chars,
        "strategies": strategies,
        "totals": {"generation_api_calls_p1_06": 4, "questions_p1_06": tot_q,
                   "generation_total_tokens_p1_06": p106["total_tokens"]},
    }


def main():
    con = ro(LIB)
    cur = con.cursor()
    audit = {"stage": "P1-09-A", "read_only": True, "ai_calls": 0}

    audit["question_library"] = {
        "path": LIB,
        "sha256": sha256_file(LIB),
        "size_bytes": os.path.getsize(LIB),
        "user_version": cur.execute("PRAGMA user_version").fetchone()[0],
        "integrity_check": [r[0] for r in cur.execute("PRAGMA integrity_check")],
        "foreign_key_check": [tuple(r) for r in cur.execute("PRAGMA foreign_key_check")],
        "objects": {r[0]: r[1] for r in cur.execute(
            "SELECT name, type FROM sqlite_master WHERE type IN ('table','trigger','view','index')"
            " ORDER BY type, name")},
        "row_counts": {t: cur.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0] for t in
                       ("generation_run", "ai_question", "question_evidence",
                        "question_learning_object", "question_validation", "question_event")},
        "lifecycle": {r[0]: r[1] for r in cur.execute(
            "SELECT lifecycle_status, COUNT(*) n FROM ai_question GROUP BY 1 ORDER BY 1")},
        "events": {r[0]: r[1] for r in cur.execute(
            "SELECT event_type, COUNT(*) n FROM question_event GROUP BY 1 ORDER BY 1")},
        "question_type_distribution": {r[0]: r[1] for r in cur.execute(
            "SELECT question_type, COUNT(*) n FROM ai_question GROUP BY 1 ORDER BY 1")},
        "validator_version_distribution": {r[0]: r[1] for r in cur.execute(
            "SELECT validator_version, COUNT(*) n FROM ai_question GROUP BY 1 ORDER BY 1")},
        "answer_support_distribution": {r[0]: r[1] for r in cur.execute(
            "SELECT answer_support_type, COUNT(*) n FROM question_validation GROUP BY 1 ORDER BY 1")},
        "stale_rows": [dict(r) for r in cur.execute(
            "SELECT question_id, lifecycle_status, stale, stale_reason, stale_since"
            " FROM ai_question WHERE stale=1")],
        "columns_by_table": {t: [c[1] for c in cur.execute("PRAGMA table_info(%s)" % t)] for t in
                             ("generation_run", "ai_question", "question_evidence",
                              "question_learning_object", "question_validation", "question_event")},
    }

    questions = read_questions(con)
    audit["questions"] = questions
    con.close()

    audit["validator_checks_reference"] = {
        "v3_eight_checks": REVIEW_CHECKS_V3,
        "v2_file_sha256": sha256_file(os.path.join(V2_DIR, "validator_v2.py")),
        "v3_file_sha256": sha256_file(os.path.join(V3_DIR, "validator_v3.py")),
        "six_db_triggers": [r for r, t in audit["question_library"]["objects"].items()
                            if t == "trigger"],
        "note": "8 项校验全部是结构/证据/词汇/去重类确定性判断；无任何维度判断英语质量、"
                "答案唯一性或学习价值。",
    }
    audit["validator_capability_recheck"] = validator_capability(questions)
    audit["cost_model_ref"] = "cost_model.json (written by triage_and_cost.py)"

    dump("validator_capability_check.json", audit["validator_capability_recheck"])
    dump("p1_09_a_audit.json", audit)

    ql = audit["question_library"]
    print("question_library sha", ql["sha256"], "size", ql["size_bytes"],
          "user_version", ql["user_version"])
    print("counts", json.dumps(ql["row_counts"], ensure_ascii=False))
    print("lifecycle", json.dumps(ql["lifecycle"], ensure_ascii=False))
    print("events", json.dumps(ql["events"], ensure_ascii=False))
    print("types", json.dumps(ql["question_type_distribution"], ensure_ascii=False))
    print("answer_support", json.dumps(ql["answer_support_distribution"], ensure_ascii=False))
    print("integrity", ql["integrity_check"], "fk", ql["foreign_key_check"])
    n = len(audit["validator_capability_recheck"])
    ok = sum(1 for r in audit["validator_capability_recheck"] if r["recompute_matches_stored"])
    print("validator recheck: %d/%d recompute == stored" % (ok, n))


if __name__ == "__main__":
    main()
