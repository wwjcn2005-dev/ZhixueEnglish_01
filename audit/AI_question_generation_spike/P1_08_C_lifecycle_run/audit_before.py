# -*- coding: utf-8 -*-
"""P1-08-C stage 1: read-only audit of question_library.db.

Never writes. Opens the database in sqlite3 read-only URI mode.
Outputs audit_before.json.
"""

import hashlib
import json
import os
import sqlite3

DB = r"D:\ZhixueEnglish\structured\ai\question_library.db"
OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def connect_ro():
    uri = "file:" + DB.replace("\\", "/") + "?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    return con


def main():
    con = connect_ro()
    cur = con.cursor()
    result = {}

    result["db_path"] = DB
    result["db_sha256"] = sha256(DB)
    result["db_size_bytes"] = os.path.getsize(DB)
    result["sqlite_version"] = sqlite3.sqlite_version
    result["user_version"] = cur.execute("PRAGMA user_version").fetchone()[0]
    result["integrity_check"] = [
        r[0] for r in cur.execute("PRAGMA integrity_check").fetchall()
    ]
    result["foreign_key_check"] = [
        tuple(r) for r in cur.execute("PRAGMA foreign_key_check").fetchall()
    ]

    tables = [
        r[0]
        for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    result["tables"] = tables
    result["row_counts"] = {
        t: cur.execute('SELECT COUNT(*) FROM "%s"' % t).fetchone()[0] for t in tables
    }

    result["schema_sql"] = {
        r["name"]: r["sql"]
        for r in cur.execute(
            "SELECT name, sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type, name"
        )
    }

    result["lifecycle_distribution"] = {
        r[0]: r[1]
        for r in cur.execute(
            "SELECT lifecycle_status, COUNT(*) FROM ai_question GROUP BY lifecycle_status ORDER BY 1"
        )
    }
    result["active_flag"] = dict(
        (str(r[0]), r[1])
        for r in cur.execute(
            "SELECT active, COUNT(*) FROM ai_question GROUP BY active ORDER BY 1"
        )
    )
    result["stale_distribution"] = {
        str(r[0]): r[1]
        for r in cur.execute(
            "SELECT stale, COUNT(*) FROM ai_question GROUP BY stale ORDER BY 1"
        )
    }
    result["event_distribution"] = {
        r[0]: r[1]
        for r in cur.execute(
            "SELECT event_type, COUNT(*) FROM question_event GROUP BY event_type ORDER BY 1"
        )
    }
    result["actor_kind_distribution"] = {
        r[0]: r[1]
        for r in cur.execute(
            "SELECT actor_kind, COUNT(*) FROM question_event GROUP BY actor_kind ORDER BY 1"
        )
    }

    result["questions"] = [
        dict(r)
        for r in cur.execute(
            """
            SELECT q.question_id, q.version, q.section_id, q.activity_id, q.question_type,
                   q.lifecycle_status, q.active, q.stale, q.stale_reason,
                   q.needs_human_review, q.validator_version, q.question_fingerprint,
                   q.generation_run_id, q.unit_id, q.textbook_id, q.page,
                   q.correct_answer, q.correct_option, q.difficulty,
                   q.question_text, q.options_json,
                   q.generated_at, q.created_at, q.updated_at, q.stale_since,
                   (SELECT COUNT(*) FROM question_evidence e WHERE e.question_id = q.question_id) AS evidence_n,
                   (SELECT COUNT(*) FROM question_learning_object l WHERE l.question_id = q.question_id) AS lo_n,
                   (SELECT COUNT(*) FROM question_validation v WHERE v.question_id = q.question_id) AS val_n,
                   (SELECT COUNT(*) FROM question_event ev WHERE ev.question_id = q.question_id) AS ev_n
            FROM ai_question q
            ORDER BY q.question_id
            """
        )
    ]

    result["events"] = [
        dict(r)
        for r in cur.execute(
            """
            SELECT event_id, question_id, version, event_type, from_status, to_status,
                   event_at, actor, actor_kind, reason_code, note
            FROM question_event
            ORDER BY question_id, version, event_at
            """
        )
    ]

    orphan_evidence = [
        tuple(r)
        for r in cur.execute(
            "SELECT question_id FROM question_evidence WHERE question_id NOT IN (SELECT question_id FROM ai_question)"
        )
    ]
    orphan_lo = [
        tuple(r)
        for r in cur.execute(
            "SELECT question_id FROM question_learning_object WHERE question_id NOT IN (SELECT question_id FROM ai_question)"
        )
    ]
    orphan_val = [
        tuple(r)
        for r in cur.execute(
            "SELECT question_id FROM question_validation WHERE question_id NOT IN (SELECT question_id FROM ai_question)"
        )
    ]
    orphan_ev = [
        tuple(r)
        for r in cur.execute(
            "SELECT question_id FROM question_event WHERE question_id NOT IN (SELECT question_id FROM ai_question)"
        )
    ]
    orphan_run = [
        tuple(r)
        for r in cur.execute(
            "SELECT question_id FROM ai_question WHERE generation_run_id NOT IN (SELECT run_id FROM generation_run)"
        )
    ]
    result["orphans"] = {
        "question_evidence": orphan_evidence,
        "question_learning_object": orphan_lo,
        "question_validation": orphan_val,
        "question_event": orphan_ev,
        "generation_run": orphan_run,
    }

    result["active_rows"] = [
        dict(r)
        for r in cur.execute(
            """
            SELECT q.question_id, q.active, q.lifecycle_status,
                   (SELECT COUNT(*) FROM question_event ev
                     WHERE ev.question_id = q.question_id
                       AND ev.event_type = 'REVIEW_APPROVED'
                       AND ev.actor_kind = 'human') AS human_approvals,
                   (SELECT COUNT(*) FROM question_event ev
                     WHERE ev.question_id = q.question_id
                       AND ev.event_type = 'ACTIVATED') AS activations,
                   (SELECT COUNT(*) FROM question_evidence e WHERE e.question_id = q.question_id) AS evidence_n,
                   (SELECT COUNT(*) FROM question_learning_object l WHERE l.question_id = q.question_id) AS lo_n,
                   (SELECT COUNT(*) FROM question_validation v WHERE v.question_id = q.question_id) AS val_n
            FROM ai_question q
            WHERE q.lifecycle_status = 'ACTIVE' OR q.active = 1
            ORDER BY q.question_id
            """
        )
    ]

    consistency = []
    for q in result["questions"]:
        evs = [e for e in result["events"] if e["question_id"] == q["question_id"]]
        evs_sorted = sorted(
            evs, key=lambda e: (e["version"] is None, e["version"], e["event_at"])
        )
        last_to = evs_sorted[-1]["to_status"] if evs_sorted else None
        consistency.append(
            {
                "question_id": q["question_id"],
                "lifecycle_status": q["lifecycle_status"],
                "event_count": len(evs),
                "last_event_type": evs_sorted[-1]["event_type"] if evs_sorted else None,
                "last_event_to_status": last_to,
                "status_matches_last_event": last_to == q["lifecycle_status"],
                "has_REVIEW_APPROVED_human": any(
                    e["event_type"] == "REVIEW_APPROVED" and e["actor_kind"] == "human"
                    for e in evs
                ),
                "has_ACTIVATED": any(e["event_type"] == "ACTIVATED" for e in evs),
                "has_MARKED_STALE": any(
                    e["event_type"] == "MARKED_STALE" for e in evs
                ),
            }
        )
    result["lifecycle_event_consistency"] = consistency
    result["lifecycle_event_inconsistent"] = [
        c for c in consistency if not c["status_matches_last_event"]
    ]

    con.close()

    out = os.path.join(OUT_DIR, "audit_before.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    print("wrote", out)
    print("row_counts", json.dumps(result["row_counts"], ensure_ascii=False))
    print("lifecycle", json.dumps(result["lifecycle_distribution"], ensure_ascii=False))
    print("events", json.dumps(result["event_distribution"], ensure_ascii=False))
    print("active_rows", len(result["active_rows"]))
    print("inconsistent", len(result["lifecycle_event_inconsistent"]))


if __name__ == "__main__":
    main()
