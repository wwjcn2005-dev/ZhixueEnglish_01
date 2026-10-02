# -*- coding: utf-8 -*-
"""P1-09-B: verify that the AI review did not modify any formal data (read-only checks).

Compares the pre-call snapshot in sample_selection.json against the current
question_library.db, and re-checks the database SHA256.
"""

import hashlib
import json
import os
import sqlite3

BASE = r"D:\ZhixueEnglish"
LIB = os.path.join(BASE, "structured", "ai", "question_library.db")
HERE = os.path.dirname(os.path.abspath(__file__))


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def run_checks():
    sel = json.load(open(os.path.join(HERE, "sample_selection.json"), encoding="utf-8"))
    before = sel["before_state"]
    con = sqlite3.connect("file:" + LIB.replace("\\", "/") + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    per_question, diffs = [], []
    for qid, b in before.items():
        r = cur.execute(
            "SELECT question_text, options_json, correct_answer, correct_option,"
            " lifecycle_status, active FROM ai_question WHERE question_id=?", (qid,)).fetchone()
        a = dict(r) if r else None
        ev = cur.execute("SELECT COUNT(*) FROM question_event WHERE question_id=?",
                         (qid,)).fetchone()[0]
        after = {"question_text": a["question_text"], "options_json": a["options_json"],
                 "correct_answer": a["correct_answer"], "correct_option": a["correct_option"],
                 "lifecycle_status": a["lifecycle_status"], "active": a["active"],
                 "question_event_count": ev}
        d = {k: [b[k], after[k]] for k in b if b[k] != after[k]}
        per_question.append({"question_id": qid, "unchanged": not d, "diff": d})
        if d:
            diffs.append({"question_id": qid, "diff": d})

    tables = ["generation_run", "ai_question", "question_evidence",
              "question_learning_object", "question_validation", "question_event"]
    counts = {t: cur.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0] for t in tables}
    lifecycle = {r[0]: r[1] for r in cur.execute(
        "SELECT lifecycle_status, COUNT(*) n FROM ai_question GROUP BY 1 ORDER BY 1")}
    events = {r[0]: r[1] for r in cur.execute(
        "SELECT event_type, COUNT(*) n FROM question_event GROUP BY 1 ORDER BY 1")}
    integrity = [r[0] for r in cur.execute("PRAGMA integrity_check")]
    fk = cur.execute("PRAGMA foreign_key_check").fetchall()
    con.close()

    sha_now = sha256_file(LIB)
    out = {
        "stage": "P1-09-B",
        "db_sha256_before": sel["source_sha256"],
        "db_sha256_after": sha_now,
        "db_sha256_unchanged": sha_now == sel["source_sha256"],
        "db_size_after": os.path.getsize(LIB),
        "per_question": per_question,
        "questions_changed": diffs,
        "all_sample_questions_unchanged": not diffs,
        "row_counts": counts,
        "lifecycle": lifecycle,
        "events": events,
        "integrity_check": integrity,
        "foreign_key_check": [tuple(r) for r in fk],
    }
    return out


EXPECTED_LIFECYCLE = {"ACTIVE": 1, "PENDING_REVIEW": 19, "REJECTED": 1}
EXPECTED_COUNTS = {"generation_run": 12, "ai_question": 21, "question_evidence": 22,
                   "question_learning_object": 37, "question_validation": 21,
                   "question_event": 44}


def main():
    out = run_checks()
    out["expected"] = {"lifecycle": EXPECTED_LIFECYCLE, "row_counts": EXPECTED_COUNTS}
    out["lifecycle_matches_expected"] = out["lifecycle"] == EXPECTED_LIFECYCLE
    out["row_counts_match_expected"] = out["row_counts"] == EXPECTED_COUNTS
    with open(os.path.join(HERE, "no_change_verification.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    print("db sha before:", out["db_sha256_before"])
    print("db sha after :", out["db_sha256_after"])
    print("sha unchanged:", out["db_sha256_unchanged"])
    print("all 10 sample questions unchanged:", out["all_sample_questions_unchanged"])
    print("lifecycle:", out["lifecycle"], "matches:", out["lifecycle_matches_expected"])
    print("row counts:", out["row_counts"], "matches:", out["row_counts_match_expected"])
    print("events:", out["events"])
    print("integrity:", out["integrity_check"], "fk:", out["foreign_key_check"])
    if out["questions_changed"]:
        print("DIFFS:", json.dumps(out["questions_changed"], ensure_ascii=False))


if __name__ == "__main__":
    main()
