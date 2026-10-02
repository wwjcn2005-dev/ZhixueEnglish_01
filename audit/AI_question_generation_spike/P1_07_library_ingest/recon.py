"""P1-07 侦察（只读）：fixture 定位、题库现状、只读预演、去重键预演、LO 映射覆盖率。

不修改任何文件（除本目录输出），不调用 AI，不写 question_library.db。
"""
import hashlib
import json
import os
import re
import sqlite3
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = r"D:\ZhixueEnglish"
SPIKE = os.path.join(BASE, "audit", "AI_question_generation_spike")
D6 = os.path.join(SPIKE, "P1_06_batch_stability")
RUNS = os.path.join(SPIKE, "P1_05_real_validation", "runs")
LIB = os.path.join(BASE, "structured", "ai", "question_library.db")
CP = os.path.join(BASE, "structured", "contentpack", "v5", "FLTRP-EN-7A-2022CUR.sqlite")
sys.path.insert(0, os.path.join(SPIKE, "P1_04_rule_fixes"))
import validator_v3 as V3  # noqa: E402

CTX = {"S1": "01_Unit2_UNDERSTANDING_IDEAS_context.json",
       "S2": "03_Unit1_UNDERSTANDING_IDEAS_context.json",
       "S3": "04_Unit5_UNDERSTANDING_IDEAS_context.json",
       "S4": "05_Starter_GET_READY_context.json"}


def sha_file(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest().upper()


def norm(s):
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


def dkey(section, activity, qtype, answer, blocks):
    return hashlib.sha256("\x01".join([section or "", activity or "", qtype or "",
                                       norm(answer), "|".join(sorted(blocks or []))])
                          .encode()).hexdigest().upper()


def main():
    fixtures = {}
    questions = []
    for tag, cf in CTX.items():
        p = os.path.join(D6, "%s_parsed.json" % tag)
        ctx = json.load(open(os.path.join(RUNS, cf), encoding="utf-8"))
        sid = ctx["textbook_position"]["section_id"]
        qs = json.load(open(p, encoding="utf-8")).get("questions") or []
        fixtures[tag] = {"file": os.path.relpath(p, BASE), "sha256": sha_file(p),
                         "questions": len(qs), "section_id": sid}
        allow = V3.build_whitelist(ctx)
        blk = {b["block_id"]: b for b in ctx["textbook_blocks"]}
        pages = set(ctx["textbook_position"]["textbook_pages"])
        acts = set(a["activity_no"] for a in ctx["activity_instructions"]) | {None}
        res = V3.validate_batch(qs, blocks_by_id=blk, pages_ok=pages, acts_ok=acts,
                                allow=allow, unit_label=ctx["textbook_position"]["unit"],
                                section_key=ctx["textbook_position"]["section"])
        for i, (q, r) in enumerate(zip(qs, res), 1):
            act = "%s:A%s" % (sid, q.get("activity")) if q.get("activity") is not None else None
            b = q.get("evidence_block_ids") or []
            questions.append({
                "src": "%s-Q%d" % (tag, i), "section_id": sid, "activity_id": act,
                "type": q.get("type"), "answer": q.get("answer"), "blocks": b,
                "keys": {"dedupe": dkey(sid, act, q.get("type"), q.get("answer"), b)},
                "validator_v3": {"pass": r["pass"],
                                 "failed": [k for k, v in r["checks"].items() if not v],
                                 "answer_support": r["answer_support_type"]},
                "questions_total_in_section": len(qs)})
    # 库内既有题
    conn = sqlite3.connect("file:" + LIB + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    lib_state = {"user_version": conn.execute("PRAGMA user_version").fetchone()[0],
                 "integrity": conn.execute("PRAGMA integrity_check").fetchone()[0],
                 "sha256": sha_file(LIB), "size": os.path.getsize(LIB),
                 "counts": {}, "lifecycle": {}, "existing_questions": []}
    for t in ["generation_run", "ai_question", "question_evidence", "question_learning_object",
              "question_validation", "question_event"]:
        lib_state["counts"][t] = conn.execute("select count(*) from %s" % t).fetchone()[0]
    for st in ["PENDING_REVIEW", "APPROVED", "ACTIVE"]:
        lib_state["lifecycle"][st] = conn.execute(
            "select count(*) from ai_question where lifecycle_status=?", (st,)).fetchone()[0]
    for r in conn.execute("select question_id, question_type, correct_answer, section_id, "
                          "activity_id, lifecycle_status, stale, stale_reason, question_fingerprint "
                          "from ai_question"):
        ebs = [x[0] for x in conn.execute(
            "select evidence_block_id from question_evidence where question_id=?",
            (r["question_id"],))]
        lib_state["existing_questions"].append(
            {**dict(r), "blocks": ebs,
             "keys": {"dedupe": dkey(r["section_id"], r["activity_id"], r["question_type"],
                                     r["correct_answer"], ebs)}})
    conn.close()

    # 去重预演
    groups = defaultdict(list)
    for q in questions:
        groups[q["keys"]["dedupe"]].append(q["src"])
    for r in lib_state["existing_questions"]:
        groups[r["keys"]["dedupe"]].append(r["question_id"])
    dup_groups = {k: v for k, v in groups.items() if len(v) > 1}
    # 与历史轮次的预演（说明该键能捕捉措辞不同的同题）
    u2 = "FLTRP-EN-7A-2022CUR:U2:UNDERSTANDING_IDEAS"
    hist_keys = {}
    for name, path in [("P1-05-D", os.path.join(SPIKE, "P1_05_budget_calibration_v2",
                                                "calibration_parsed.json")),
                       ("P1-05-F", os.path.join(SPIKE, "P1_05_prompt_v2_textbook_focus",
                                                "p1_05f_parsed.json")),
                       ("P1-05-G", os.path.join(SPIKE, "P1_05_prompt_v3_boundary",
                                                "p1_05g_parsed.json"))]:
        for i, q in enumerate(json.load(open(path, encoding="utf-8")).get("questions") or [], 1):
            act = "%s:A%s" % (u2, q.get("activity")) if q.get("activity") is not None else None
            hist_keys[dkey(u2, act, q.get("type"), q.get("answer"),
                           q.get("evidence_block_ids") or [])] = "%s-Q%d" % (name, i)
    counterfactual = [{"fixture": q["src"], "historical": hist_keys[q["keys"]["dedupe"]]}
                      for q in questions if q["keys"]["dedupe"] in hist_keys]

    # LearningObject 映射覆盖率
    c = sqlite3.connect("file:" + CP + "?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    vocab_words = {}
    for r in c.execute("select item_id, surface_form from learning_item where item_type='vocabulary'"):
        head = (r["surface_form"] or "").strip().split("/", 1)[0].strip().lower()
        if head:
            vocab_words[head] = r["item_id"]
    ex_of_act = {}
    for r in c.execute("select li.item_id, sr.source_id from learning_item li "
                       "join source_ref sr on sr.item_id=li.item_id where li.item_type='exercise'"):
        ex_of_act.setdefault(r["source_id"], r["item_id"])
    c.close()
    lo = {}
    for tag, cf in CTX.items():
        ctx = json.load(open(os.path.join(RUNS, cf), encoding="utf-8"))
        sid = ctx["textbook_position"]["section_id"]
        acts = [a["activity_no"] for a in ctx["activity_instructions"]]
        qs = [q for q in questions if q["src"].startswith(tag)]
        lo[tag] = {"section_id": sid,
                   "activities_with_exercise_lo": sum(1 for a in acts
                                                      if ("%s:A%s" % (sid, a)) in ex_of_act),
                   "activities_total": len(acts),
                   "answers_mapping_first_word": sum(
                       1 for q in qs
                       if str(q["answer"] or "").split()[0].strip(".,!?'\u2019\u201d").lower()
                       in vocab_words),
                   "questions_total": len(qs)}

    doc = {
        "stage": "P1-07", "mode": "reconnaissance_only", "ai_calls": 0,
        "fixture": {"dir": os.path.relpath(D6, BASE), "files": fixtures,
                    "total_questions": len(questions), "questions": questions},
        "library_before": lib_state,
        "validator_v3_recheck": {
            "pass": sum(1 for q in questions if q["validator_v3"]["pass"]),
            "fail": sum(1 for q in questions if not q["validator_v3"]["pass"]),
            "failed_questions": [{"src": q["src"], "answer": q["answer"],
                                  "failed": q["validator_v3"]["failed"],
                                  "answer_support": q["validator_v3"]["answer_support"]}
                                 for q in questions if not q["validator_v3"]["pass"]],
            "fail_by_check": dict(Counter(c for q in questions
                                          for c in q["validator_v3"]["failed"])),
        },
        "dedupe_rehearsal": {
            "key_formula": "sha256(section_id \\x01 activity_id \\x01 question_type \\x01 "
                           "normalized_answer \\x01 sorted(evidence_block_ids))",
            "duplicate_groups_within_scope": dup_groups,
            "duplicate_count": len(dup_groups),
            "counterfactual_vs_historical_rounds": counterfactual,
        },
        "learning_object_coverage": lo,
    }
    with open(os.path.join(HERE, "recon_data.json"), "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
    print("已生成 recon_data.json")
    print("  fixture 题数:", len(questions))
    print("  validator v3:", doc["validator_v3_recheck"]["pass"], "PASS /",
          doc["validator_v3_recheck"]["fail"], "FAIL", doc["validator_v3_recheck"]["fail_by_check"])
    print("  去重命中（现库+批次内）:", doc["dedupe_rehearsal"]["duplicate_count"])
    print("  反事实（若历史轮已入库）:", len(counterfactual))
    print("  库状态:", lib_state["counts"], lib_state["lifecycle"])


if __name__ == "__main__":
    main()
