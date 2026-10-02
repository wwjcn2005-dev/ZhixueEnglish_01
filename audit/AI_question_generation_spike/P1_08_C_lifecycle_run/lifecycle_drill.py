# -*- coding: utf-8 -*-
"""P1-08-C: PENDING_REVIEW -> human review -> APPROVED -> explicit enable -> ACTIVE.

Read-only except for the explicitly authorized lifecycle events on a small
number of existing test questions in structured/ai/question_library.db.
No schema change. No new table/column. No API. No AI call.
Refusal tests run inside explicit transactions that always ROLLBACK.
"""

import datetime
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

ACTOR_HUMAN = "human:project-owner"
DRILL = "P1-08-C lifecycle drill (project owner instruction 2026-09-17)"


def now_ts():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def conn_rw():
    con = sqlite3.connect(LIB)
    con.isolation_level = None
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def counts(con):
    out = {}
    for t in ("generation_run", "ai_question", "question_evidence",
              "question_learning_object", "question_validation", "question_event"):
        out[t] = con.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
    out["lifecycle"] = {
        r[0]: r[1]
        for r in con.execute(
            "SELECT lifecycle_status, COUNT(*) FROM ai_question GROUP BY lifecycle_status ORDER BY 1")
    }
    out["events"] = {
        r[0]: r[1]
        for r in con.execute(
            "SELECT event_type, COUNT(*) FROM question_event GROUP BY event_type ORDER BY 1")
    }
    return out


def q_state(con, qid):
    r = con.execute(
        "SELECT question_id, version, lifecycle_status, active, stale, stale_reason,"
        " needs_human_review, updated_at FROM ai_question WHERE question_id=?", (qid,)).fetchone()
    return dict(r) if r else None


def insert_event(con, qid, fp12, suffix, event_type, from_status, to_status,
                 actor, actor_kind, note, reason_code=None):
    con.execute(
        "INSERT INTO question_event (event_id, question_id, version, event_type, from_status,"
        " to_status, event_at, actor, actor_kind, reason_code, note)"
        " VALUES (?,?,1,?,?,?,?,?,?,?,?)",
        ("AIEV:%s:%s" % (fp12, suffix), qid, event_type, from_status, to_status,
         now_ts(), actor, actor_kind, reason_code, note))


def fp_of(con, qid):
    return con.execute("SELECT question_fingerprint FROM ai_question WHERE question_id=?",
                       (qid,)).fetchone()[0]


def attempt(con, label, fn):
    obs = {"test": label, "rolled_back": True}
    try:
        con.execute("BEGIN")
        fn()
        obs["blocked"] = False
        obs["error"] = None
    except sqlite3.Error as exc:
        obs["blocked"] = True
        obs["error"] = "%s: %s" % (type(exc).__name__, exc)
    finally:
        try:
            con.execute("ROLLBACK")
        except sqlite3.Error:
            pass
    return obs


def main():
    report = {"stage": "P1-08-C", "generated_at": now_ts()}
    sha_before = sha256_file(LIB)
    report["db_sha256_before"] = sha_before

    con = conn_rw()
    report["pre_counts"] = counts(con)
    report["journal_mode"] = con.execute("PRAGMA journal_mode").fetchone()[0]
    report["pre_states"] = {q: q_state(con, q) for q in (SAMPLE_A, SAMPLE_B, SAMPLE_C, SAMPLE_E)}

    fp = {q: fp_of(con, q) for q in (SAMPLE_A, SAMPLE_B, SAMPLE_C, SAMPLE_E)}
    report["fingerprints"] = fp
    f12 = {q: v[:12] for q, v in fp.items()}

    refusals = []

    refusals.append(dict(
        id="T1_direct_pending_to_active",
        intent="PENDING_REVIEW -> ACTIVE (no APPROVED step, no REVIEW_APPROVED event)",
        expected="BLOCKED",
        **attempt(con, "T1", lambda: con.execute(
            "UPDATE ai_question SET lifecycle_status='ACTIVE', active=1, updated_at=?"
            " WHERE question_id=? AND version=1", (now_ts(), SAMPLE_C)))))

    def t1b():
        insert_event(con, SAMPLE_C, f12[SAMPLE_C], "AC-TEST", "ACTIVATED",
                     "APPROVED", "ACTIVE", DRILL, "human", "refusal probe")
        con.execute("UPDATE ai_question SET lifecycle_status='ACTIVE', active=1, updated_at=?"
                    " WHERE question_id=? AND version=1", (now_ts(), SAMPLE_C))
    refusals.append(dict(
        id="T1b_canonical_path_without_review",
        intent="insert ACTIVATED event then flip status, with no human REVIEW_APPROVED event",
        expected="BLOCKED",
        **attempt(con, "T1b", t1b)))

    refusals.append(dict(
        id="T12_active_flag_without_active_status",
        intent="UPDATE ai_question SET active=1 while lifecycle_status='PENDING_REVIEW'",
        expected="BLOCKED",
        **attempt(con, "T12", lambda: con.execute(
            "UPDATE ai_question SET active=1, updated_at=? WHERE question_id=? AND version=1",
            (now_ts(), SAMPLE_C)))))

    def t14():
        insert_event(con, SAMPLE_C, f12[SAMPLE_C], "RA-MACHINE", "REVIEW_APPROVED",
                     "PENDING_REVIEW", "APPROVED", "validator_v3", "machine", "forged probe")
    refusals.append(dict(
        id="T14_machine_actor_cannot_approve",
        intent="INSERT REVIEW_APPROVED with actor_kind='machine'",
        expected="BLOCKED",
        **attempt(con, "T14", t14)))

    refusals.append(dict(
        id="T15_illegal_event_type",
        intent="INSERT question_event with event_type='FORCED_APPROVE'",
        expected="BLOCKED",
        **attempt(con, "T15", lambda: con.execute(
            "INSERT INTO question_event (event_id, question_id, version, event_type, from_status,"
            " to_status, event_at, actor, actor_kind, note)"
            " VALUES (?,?,1,'FORCED_APPROVE','PENDING_REVIEW','ACTIVE',?,?, 'human','probe')",
            ("AIEV:PROBE:T15", SAMPLE_C, now_ts(), DRILL)))))

    def t16():
        insert_event(con, SAMPLE_C, f12[SAMPLE_C], "RR-NOREASON", "REVIEW_REJECTED",
                     "PENDING_REVIEW", "REJECTED", DRILL, "human", "probe")
    refusals.append(dict(
        id="T16_reject_without_reason_code",
        intent="INSERT REVIEW_REJECTED without reason_code",
        expected="BLOCKED",
        **attempt(con, "T16", t16)))

    ev_row = con.execute(
        "SELECT event_id FROM question_event ORDER BY event_at LIMIT 1").fetchone()[0]
    report["probe_event_id"] = ev_row
    refusals.append(dict(
        id="T17_event_update_forbidden",
        intent="UPDATE question_event SET note='tampered' WHERE event_id=%s" % ev_row,
        expected="BLOCKED",
        **attempt(con, "T17", lambda: con.execute(
            "UPDATE question_event SET note='tampered' WHERE event_id=?", (ev_row,)))))

    refusals.append(dict(
        id="T18_event_delete_forbidden",
        intent="DELETE FROM question_event WHERE event_id=%s" % ev_row,
        expected="BLOCKED",
        **attempt(con, "T18", lambda: con.execute(
            "DELETE FROM question_event WHERE event_id=?", (ev_row,)))))

    refusals.append(dict(
        id="T19_question_delete_forbidden",
        intent="DELETE FROM ai_question WHERE question_id=%s" % SAMPLE_C,
        expected="BLOCKED",
        **attempt(con, "T19", lambda: con.execute(
            "DELETE FROM ai_question WHERE question_id=?", (SAMPLE_C,)))))

    refusals.append(dict(
        id="T20_insert_active_forbidden",
        intent="INSERT ai_question with lifecycle_status='ACTIVE'",
        expected="BLOCKED",
        **attempt(con, "T20", lambda: con.execute(
            "INSERT INTO ai_question (question_id, version, question_type, question_text,"
            " correct_answer, textbook_id, unit_id, section_id, generation_run_id, generated_at,"
            " question_fingerprint, lifecycle_status, active, created_at, updated_at)"
            " VALUES ('AIQ:PROBE0000000',1,'fill','probe','x','FLTRP-EN-7A-2022CUR','u','s',"
            "'AIRUN:PROBE',?,?, 'ACTIVE',1,?,?)",
            (now_ts(), "0" * 64, now_ts(), now_ts())))))

    report["refusal_tests"] = refusals

    real = {}

    def canonical_step(qid, suffix, event_type, from_status, to_status, note,
                       reason_code=None, actor=DRILL, actor_kind="human", activate=False):
        t = now_ts()
        con.execute("BEGIN")
        try:
            insert_event(con, qid, f12[qid], suffix, event_type, from_status, to_status,
                         actor, actor_kind, note, reason_code)
            if activate:
                con.execute("UPDATE ai_question SET lifecycle_status=?, active=1, updated_at=?"
                            " WHERE question_id=? AND version=1", (to_status, t, qid))
            else:
                con.execute("UPDATE ai_question SET lifecycle_status=?, updated_at=?"
                            " WHERE question_id=? AND version=1", (to_status, t, qid))
            con.execute("COMMIT")
        except sqlite3.Error:
            con.execute("ROLLBACK")
            raise
        return {"event_id": "AIEV:%s:%s" % (f12[qid], suffix), "event_type": event_type,
                "from_status": from_status, "to_status": to_status, "event_at": t,
                "actor": actor, "actor_kind": actor_kind, "reason_code": reason_code}

    real["sample_A_approve"] = canonical_step(
        SAMPLE_A, "RA", "REVIEW_APPROVED", "PENDING_REVIEW", "APPROVED",
        "P1-08-C human review: textbook basis traceable, stem readable, answer directly"
        " supported by the textbook sentence; evidence/learning_object/validation/provenance"
        " complete; decision=APPROVE",
        actor=ACTOR_HUMAN, actor_kind="human")

    real["sample_D_state_after_approval"] = q_state(con, SAMPLE_A)
    real["sample_D_auto_active_check"] = {
        "lifecycle_status": real["sample_D_state_after_approval"]["lifecycle_status"],
        "active": real["sample_D_state_after_approval"]["active"],
        "auto_promoted": bool(real["sample_D_state_after_approval"]["active"])
        or real["sample_D_state_after_approval"]["lifecycle_status"] == "ACTIVE",
    }

    real["sample_A_activate"] = canonical_step(
        SAMPLE_A, "AC", "ACTIVATED", "APPROVED", "ACTIVE",
        "P1-08-C explicit enable: after human approval the project owner explicitly enables"
        " this question (second, separate lifecycle action)",
        actor=ACTOR_HUMAN, actor_kind="human", activate=True)
    real["sample_A_final_state"] = q_state(con, SAMPLE_A)

    real["sample_B_reject"] = canonical_step(
        SAMPLE_B, "RR", "REVIEW_REJECTED", "PENDING_REVIEW", "REJECTED",
        "P1-08-C human reject (LOW_VALUE): the item is a mechanical gap-fill fragment of the"
        " textbook sentence P8:B16 'I am ready, too'; learning increment below the bar; the row"
        " is kept in the library but must never reach ACTIVE",
        reason_code="LOW_VALUE", actor=ACTOR_HUMAN, actor_kind="human")
    real["sample_B_final_state"] = q_state(con, SAMPLE_B)

    def t4():
        insert_event(con, SAMPLE_B, f12[SAMPLE_B], "AC-TEST", "ACTIVATED",
                     "REJECTED", "ACTIVE", DRILL, "human", "refusal probe")
        con.execute("UPDATE ai_question SET lifecycle_status='ACTIVE', active=1, updated_at=?"
                    " WHERE question_id=? AND version=1", (now_ts(), SAMPLE_B))
    report["refusal_tests"].append(dict(
        id="T4_rejected_to_active",
        intent="REJECTED -> ACTIVE with no fresh human approval",
        expected="BLOCKED", **attempt(con, "T4", t4)))

    def t5a():
        insert_event(con, SAMPLE_E, f12[SAMPLE_E], "AC-TEST", "ACTIVATED",
                     "PENDING_REVIEW", "ACTIVE", DRILL, "human", "refusal probe")
        con.execute("UPDATE ai_question SET lifecycle_status='ACTIVE', active=1, updated_at=?"
                    " WHERE question_id=? AND version=1", (now_ts(), SAMPLE_E))
    report["refusal_tests"].append(dict(
        id="T5_stale_to_active_without_review",
        intent="STALE(stale=1, VALIDATOR_CHANGED) -> ACTIVE with no fresh human REVIEW_APPROVED",
        expected="BLOCKED", **attempt(con, "T5", t5a)))

    def t5b():
        insert_event(con, SAMPLE_E, f12[SAMPLE_E], "RA-PROBE", "REVIEW_APPROVED",
                     "PENDING_REVIEW", "APPROVED", DRILL, "human", "re-review probe")
        con.execute("UPDATE ai_question SET lifecycle_status='APPROVED', updated_at=?"
                    " WHERE question_id=? AND version=1", (now_ts(), SAMPLE_E))
        insert_event(con, SAMPLE_E, f12[SAMPLE_E], "AC-PROBE", "ACTIVATED",
                     "APPROVED", "ACTIVE", DRILL, "human", "re-review probe")
        con.execute("UPDATE ai_question SET lifecycle_status='ACTIVE', active=1, updated_at=?"
                    " WHERE question_id=? AND version=1", (now_ts(), SAMPLE_E))
    report["refusal_tests"].append(dict(
        id="T5b_stale_rereview_then_active",
        intent="probe only (rolled back): STALE -> fresh human REVIEW_APPROVED -> ACTIVE",
        expected="INFORMATIONAL (re-review path)",
        **attempt(con, "T5b", t5b)))

    dep_missing = con.execute(
        """
        SELECT q.question_id FROM ai_question q
        WHERE (SELECT COUNT(*) FROM question_evidence e WHERE e.question_id=q.question_id)=0
           OR (SELECT COUNT(*) FROM question_learning_object l WHERE l.question_id=q.question_id)=0
           OR (SELECT COUNT(*) FROM question_validation v WHERE v.question_id=q.question_id)=0
           OR q.generation_run_id IS NULL
           OR q.generation_run_id NOT IN (SELECT run_id FROM generation_run)
        """).fetchall()
    report["dependency_missing_rows"] = [r[0] for r in dep_missing]
    report["T6_status"] = "NOT_TESTED_NO_ELIGIBLE_OBJECT" if not dep_missing else "EXECUTED"

    candidate_query = ("SELECT question_id FROM ai_question WHERE lifecycle_status='ACTIVE'"
                       " AND active=1 AND stale=0")
    report["learning_candidate_query"] = candidate_query
    report["learning_candidate_rows"] = [r[0] for r in con.execute(candidate_query)]
    report["learning_candidate_excluded_probe"] = {
        "PENDING_REVIEW": con.execute(
            "SELECT COUNT(*) FROM ai_question WHERE question_id=? AND lifecycle_status='PENDING_REVIEW'",
            (SAMPLE_C,)).fetchone()[0],
        "APPROVED_not_active_rows": con.execute(
            "SELECT COUNT(*) FROM ai_question WHERE lifecycle_status='APPROVED'").fetchone()[0],
        "REJECTED": con.execute(
            "SELECT COUNT(*) FROM ai_question WHERE question_id=? AND lifecycle_status='REJECTED'",
            (SAMPLE_B,)).fetchone()[0],
        "STALE": con.execute(
            "SELECT COUNT(*) FROM ai_question WHERE question_id=? AND stale=1",
            (SAMPLE_E,)).fetchone()[0],
    }

    report["real_lifecycle"] = real
    report["post_counts"] = counts(con)
    report["post_states"] = {q: q_state(con, q) for q in (SAMPLE_A, SAMPLE_B, SAMPLE_C, SAMPLE_E)}
    report["post_events_for_samples"] = {
        q: [dict(r) for r in con.execute(
            "SELECT event_id, event_type, from_status, to_status, event_at, actor, actor_kind,"
            " reason_code, note FROM question_event WHERE question_id=? ORDER BY version, event_at",
            (q,))]
        for q in (SAMPLE_A, SAMPLE_B, SAMPLE_C, SAMPLE_E)
    }

    report["post_integrity_check"] = [r[0] for r in con.execute("PRAGMA integrity_check")]
    report["post_foreign_key_check"] = [tuple(r) for r in con.execute("PRAGMA foreign_key_check")]
    report["post_active_rows"] = [dict(r) for r in con.execute(
        """
        SELECT q.question_id, q.lifecycle_status, q.active, q.stale,
               (SELECT COUNT(*) FROM question_event e WHERE e.question_id=q.question_id
                 AND e.event_type='REVIEW_APPROVED' AND e.actor_kind='human') AS human_approvals,
               (SELECT COUNT(*) FROM question_event e WHERE e.question_id=q.question_id
                 AND e.event_type='ACTIVATED') AS activations,
               (SELECT COUNT(*) FROM question_evidence e WHERE e.question_id=q.question_id) AS evidence_n,
               (SELECT COUNT(*) FROM question_learning_object l WHERE l.question_id=q.question_id) AS lo_n,
               (SELECT COUNT(*) FROM question_validation v WHERE v.question_id=q.question_id) AS val_n
        FROM ai_question q WHERE q.lifecycle_status='ACTIVE' OR q.active=1 ORDER BY q.question_id
        """)]
    report["post_lifecycle_event_consistency"] = [dict(r) for r in con.execute(
        """
        SELECT q.question_id, q.lifecycle_status,
               (SELECT e.event_type FROM question_event e WHERE e.question_id=q.question_id
                 ORDER BY e.version DESC, e.event_at DESC LIMIT 1) AS last_event_type,
               (SELECT e.to_status FROM question_event e WHERE e.question_id=q.question_id
                 ORDER BY e.version DESC, e.event_at DESC LIMIT 1) AS last_event_to_status
        FROM ai_question q ORDER BY q.question_id
        """)]
    report["post_schema_objects"] = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','trigger','view','index') ORDER BY name")]
    report["post_other_question_states"] = [dict(r) for r in con.execute(
        "SELECT question_id, lifecycle_status, active, stale, updated_at FROM ai_question"
        " WHERE question_id NOT IN (?,?,?,?) ORDER BY question_id",
        (SAMPLE_A, SAMPLE_B, SAMPLE_C, SAMPLE_E))]
    con.close()

    report["db_sha256_after"] = sha256_file(LIB)
    report["db_size_after"] = os.path.getsize(LIB)

    out = os.path.join(HERE, "lifecycle_test_result.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print("wrote", out)
    print("sha_before", sha_before)
    print("sha_after ", report["db_sha256_after"])
    print("pre ", json.dumps(report["pre_counts"], ensure_ascii=False))
    print("post", json.dumps(report["post_counts"], ensure_ascii=False))
    for r in report["refusal_tests"]:
        print("  %-42s blocked=%s  %s" % (r["id"], r.get("blocked"), r.get("error") or ""))
    print("candidate rows", report["learning_candidate_rows"])


if __name__ == "__main__":
    main()
