# -*- coding: utf-8 -*-
"""P1-08-C post-run verification (read-only).

Consumes audit_before.json + lifecycle_test_result.json, re-reads
question_library.db read-only, and writes:
  before_after_db_summary.json
  p1_08_c_audit.json
"""

import hashlib
import json
import os
import sqlite3

BASE = r"D:\ZhixueEnglish"
LIB = os.path.join(BASE, "structured", "ai", "question_library.db")
HERE = os.path.dirname(os.path.abspath(__file__))

SAMPLE_A = "AIQ:BD59C5958D45"
SAMPLE_B = "AIQ:1B3AF72923C4"
SAMPLE_C = "AIQ:75AAEBFE06DF"
SAMPLE_E = "AIQ:7EBCDBC29563"
SAMPLES = [SAMPLE_A, SAMPLE_B, SAMPLE_C, SAMPLE_E]


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def ro():
    con = sqlite3.connect("file:" + LIB.replace("\\", "/") + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def load(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return json.load(fh)


def main():
    before = load("audit_before.json")
    drill = load("lifecycle_test_result.json")
    con = ro()
    cur = con.cursor()

    tables = ["generation_run", "ai_question", "question_evidence",
              "question_learning_object", "question_validation", "question_event"]
    after_counts = {t: cur.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0] for t in tables}
    before_counts = {t: before["row_counts"][t] for t in tables}

    lifecycle = {r[0]: r[1] for r in cur.execute(
        "SELECT lifecycle_status, COUNT(*) FROM ai_question GROUP BY lifecycle_status ORDER BY 1")}
    events = {r[0]: r[1] for r in cur.execute(
        "SELECT event_type, COUNT(*) FROM question_event GROUP BY event_type ORDER BY 1")}

    # per-question diff vs the pre-run audit
    before_q = {q["question_id"]: q for q in before["questions"]}
    after_q_rows = [dict(r) for r in cur.execute(
        """
        SELECT q.question_id, q.version, q.lifecycle_status, q.active, q.stale, q.stale_reason,
               q.needs_human_review, q.validator_version, q.updated_at, q.generation_run_id,
               (SELECT COUNT(*) FROM question_evidence e WHERE e.question_id=q.question_id) AS evidence_n,
               (SELECT COUNT(*) FROM question_learning_object l WHERE l.question_id=q.question_id) AS lo_n,
               (SELECT COUNT(*) FROM question_validation v WHERE v.question_id=q.question_id) AS val_n,
               (SELECT COUNT(*) FROM question_event ev WHERE ev.question_id=q.question_id) AS ev_n
        FROM ai_question q ORDER BY q.question_id
        """)]
    after_q = {q["question_id"]: q for q in after_q_rows}

    changed, untouched = [], []
    for qid, b in before_q.items():
        a = after_q[qid]
        diff = {k: [b[k], a[k]] for k in
                ("lifecycle_status", "active", "stale", "updated_at", "ev_n")
                if b[k] != a[k]}
        if diff:
            changed.append({"question_id": qid, "diff": diff})
        else:
            untouched.append(qid)

    # probe residue check
    probe_events = [dict(r) for r in cur.execute(
        "SELECT event_id, question_id, event_type FROM question_event"
        " WHERE event_id LIKE '%PROBE%' OR event_id LIKE '%-TEST' OR event_id LIKE '%NOREASON%'"
        "    OR event_id LIKE '%MACHINE%' OR question_id LIKE 'AIQ:PROBE%'")]
    probe_questions = [dict(r) for r in cur.execute(
        "SELECT question_id FROM ai_question WHERE question_id LIKE 'AIQ:PROBE%'")]

    # lifecycle / event consistency for every question
    consistency = []
    for qid in sorted(after_q):
        evs = [dict(r) for r in cur.execute(
            "SELECT event_id, event_type, from_status, to_status, event_at, actor, actor_kind,"
            " reason_code FROM question_event WHERE question_id=? ORDER BY version, event_at, rowid",
            (qid,))]
        chain_ok = True
        for i in range(1, len(evs)):
            if evs[i]["from_status"] is not None and evs[i - 1]["to_status"] is not None:
                if evs[i]["from_status"] != evs[i - 1]["to_status"]:
                    chain_ok = False
        if evs and evs[0]["from_status"] not in (None, "GENERATED"):
            chain_ok = False
        consistency.append({
            "question_id": qid,
            "lifecycle_status": after_q[qid]["lifecycle_status"],
            "event_count": len(evs),
            "event_types": [e["event_type"] for e in evs],
            "last_event_to_status": evs[-1]["to_status"] if evs else None,
            "status_matches_last_event": bool(evs) and evs[-1]["to_status"] == after_q[qid]["lifecycle_status"],
            "chain_from_to_continuous": chain_ok,
        })
    inconsistent = [c for c in consistency
                    if not c["status_matches_last_event"] or not c["chain_from_to_continuous"]]

    # ACTIVE provenance / dependency completeness
    active_detail = [dict(r) for r in cur.execute(
        """
        SELECT q.question_id, q.question_type, q.section_id, q.activity_id, q.page,
               q.textbook_id, q.snapshot_id, q.unit_id, q.generation_run_id, q.generated_at,
               q.question_fingerprint, q.correct_answer, q.validator_version,
               r.model, r.prompt_version, r.context_hash, r.provider, r.finish_reason,
               r.context_ref, r.raw_response_ref, r.generated_at AS run_generated_at,
               (SELECT COUNT(*) FROM question_evidence e WHERE e.question_id=q.question_id) AS evidence_n,
               (SELECT COUNT(*) FROM question_learning_object l WHERE l.question_id=q.question_id) AS lo_n,
               (SELECT COUNT(*) FROM question_validation v WHERE v.question_id=q.question_id) AS val_n,
               (SELECT COUNT(*) FROM question_event e WHERE e.question_id=q.question_id
                 AND e.event_type='REVIEW_APPROVED' AND e.actor_kind='human') AS human_approval_events,
               (SELECT COUNT(*) FROM question_event e WHERE e.question_id=q.question_id
                 AND e.event_type='ACTIVATED') AS activation_events
        FROM ai_question q JOIN generation_run r ON r.run_id = q.generation_run_id
        WHERE q.lifecycle_status='ACTIVE' OR q.active=1 ORDER BY q.question_id
        """)]
    for a in active_detail:
        a["provenance_complete"] = all(
            a.get(k) for k in ("generation_run_id", "model", "prompt_version", "context_hash",
                               "generated_at", "question_fingerprint", "validator_version"))
        a["dependencies_complete"] = a["evidence_n"] > 0 and a["lo_n"] > 0 and a["val_n"] > 0
        a["human_approval_present"] = a["human_approval_events"] == 1
        a["activation_present"] = a["activation_events"] == 1

    # learning candidate gate (question_library side)
    candidate_rows = [dict(r) for r in cur.execute(
        """
        SELECT question_id, lifecycle_status, active, stale, section_id, activity_id
        FROM ai_question WHERE lifecycle_status='ACTIVE' AND active=1 AND stale=0
        ORDER BY question_id
        """)]
    non_active_returned = [r for r in candidate_rows
                           if r["lifecycle_status"] != "ACTIVE" or r["active"] != 1]
    active_missing_deps = [a["question_id"] for a in active_detail
                           if not (a["dependencies_complete"] and a["provenance_complete"]
                                   and a["human_approval_present"] and a["activation_present"])]

    # schema identity
    schema_now = {r["name"]: r["sql"] for r in cur.execute(
        "SELECT name, sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type, name")}
    schema_added = [k for k in schema_now if k not in before["schema_sql"]]
    schema_removed = [k for k in before["schema_sql"] if k not in schema_now]
    schema_modified = [k for k in schema_now
                       if k in before["schema_sql"] and schema_now[k] != before["schema_sql"][k]]
    user_version = cur.execute("PRAGMA user_version").fetchone()[0]
    integrity = [r[0] for r in cur.execute("PRAGMA integrity_check")]
    fk_check = cur.execute("PRAGMA foreign_key_check").fetchall()

    orphan = {}
    for name, sql in (
        ("question_evidence", "SELECT COUNT(*) FROM question_evidence WHERE question_id NOT IN (SELECT question_id FROM ai_question)"),
        ("question_learning_object", "SELECT COUNT(*) FROM question_learning_object WHERE question_id NOT IN (SELECT question_id FROM ai_question)"),
        ("question_validation", "SELECT COUNT(*) FROM question_validation WHERE question_id NOT IN (SELECT question_id FROM ai_question)"),
        ("question_event", "SELECT COUNT(*) FROM question_event WHERE question_id NOT IN (SELECT question_id FROM ai_question)"),
        ("generation_run", "SELECT COUNT(*) FROM ai_question WHERE generation_run_id NOT IN (SELECT run_id FROM generation_run)"),
    ):
        orphan[name] = cur.execute(sql).fetchone()[0]

    after_sha = sha256_file(LIB)
    con.close()

    summary = {
        "db_sha256_before": before["db_sha256"],
        "db_sha256_after": after_sha,
        "db_size_before": before["db_size_bytes"],
        "db_size_after": os.path.getsize(LIB),
        "row_counts_before": before_counts,
        "row_counts_after": after_counts,
        "row_count_delta": {t: after_counts[t] - before_counts[t] for t in tables},
        "lifecycle_before": before["lifecycle_distribution"],
        "lifecycle_after": lifecycle,
        "events_before": before["event_distribution"],
        "events_after": events,
        "changed_questions": changed,
        "untouched_question_count": len(untouched),
        "untouched_questions": untouched,
    }

    audit = {
        "stage": "P1-08-C",
        "generated_at_utc_offset": os.environ.get("TZ", "Asia/Shanghai"),
        "db_sha256_before": before["db_sha256"],
        "db_sha256_after": after_sha,
        "schema": {
            "user_version_before": before["user_version"],
            "user_version_after": user_version,
            "objects_added": schema_added,
            "objects_removed": schema_removed,
            "objects_modified": schema_modified,
            "schema_unchanged": not (schema_added or schema_removed or schema_modified),
        },
        "integrity": {"integrity_check": integrity, "foreign_key_check": fk_check,
                      "orphan_counts": orphan},
        "refusal_tests": drill["refusal_tests"],
        "refusal_all_blocked": all(
            r["blocked"] for r in drill["refusal_tests"]
            if r["expected"] == "BLOCKED"),
        "informational_probes": [r for r in drill["refusal_tests"]
                                 if r["expected"] != "BLOCKED"],
        "real_lifecycle": drill["real_lifecycle"],
        "sample_states_final": drill["post_states"],
        "sample_events_final": drill["post_events_for_samples"],
        "active_detail": active_detail,
        "active_questions_missing_requirements": active_missing_deps,
        "learning_candidate_query": drill["learning_candidate_query"],
        "learning_candidate_rows": candidate_rows,
        "learning_candidate_gate_ok": not non_active_returned,
        "exclusion_probe": drill["learning_candidate_excluded_probe"],
        "lifecycle_event_consistency": consistency,
        "lifecycle_event_inconsistent": inconsistent,
        "probe_residue_events": probe_events,
        "probe_residue_questions": probe_questions,
        "probe_residue_free": not probe_events and not probe_questions,
        "T6_dependency_test": {
            "eligible_rows": drill["dependency_missing_rows"],
            "status": drill["T6_status"],
        },
    }

    with open(os.path.join(HERE, "before_after_db_summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    with open(os.path.join(HERE, "p1_08_c_audit.json"), "w", encoding="utf-8") as fh:
        json.dump(audit, fh, ensure_ascii=False, indent=2)

    print(json.dumps(summary["row_count_delta"], ensure_ascii=False))
    print("lifecycle_after", lifecycle)
    print("events_after", events)
    print("changed", [c["question_id"] for c in changed])
    print("untouched", len(untouched))
    print("schema_unchanged", audit["schema"]["schema_unchanged"])
    print("integrity", integrity, "fk", fk_check, "orphans", orphan)
    print("refusal_all_blocked", audit["refusal_all_blocked"])
    print("probe_residue_free", audit["probe_residue_free"])
    print("active_missing", active_missing_deps)
    print("candidate_rows", [r["question_id"] for r in candidate_rows])
    print("gate_ok", audit["learning_candidate_gate_ok"])
    print("inconsistent", [c["question_id"] for c in inconsistent])


if __name__ == "__main__":
    main()
