# -*- coding: utf-8 -*-
"""P1-11 protection verification (read-only). Usage: python verify_protection.py before|after

Checks the P1-11 §13 list: formal assets unchanged, schema unchanged,
existing lifecycle states unchanged, no new question_event, 0-question handling,
no prescreen, no fill candidate pool.
"""

import hashlib
import json
import os
import sqlite3
import sys

BASE = r"D:\ZhixueEnglish"
HERE = os.path.dirname(os.path.abspath(__file__))
SPIKE = os.path.dirname(HERE)
LIB = os.path.join(BASE, "structured", "ai", "question_library.db")
ANCHOR = os.path.join(SPIKE, "P1_09_D_boundary_validation", "protect_after.json")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def db_state():
    con = sqlite3.connect("file:" + LIB.replace("\\", "/") + "?mode=ro", uri=True)
    cur = con.cursor()
    st = {
        "user_version": cur.execute("PRAGMA user_version").fetchone()[0],
        "schema_objects": sorted(r[0] for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','trigger','index')")),
        "row_counts": {t: cur.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
                       for t in ("generation_run", "ai_question", "question_evidence",
                                 "question_learning_object", "question_validation",
                                 "question_event")},
        "lifecycle": {r[0]: r[1] for r in cur.execute(
            "SELECT lifecycle_status, COUNT(*) FROM ai_question GROUP BY 1")},
        "per_question": {r[0]: [r[1], r[2]] for r in cur.execute(
            "SELECT question_id, lifecycle_status, active FROM ai_question")},
        "events": {r[0]: r[1] for r in cur.execute(
            "SELECT event_type, COUNT(*) FROM question_event GROUP BY 1")},
        "run_status": {r[0]: r[1] for r in cur.execute(
            "SELECT status, COUNT(*) FROM generation_run GROUP BY 1")},
        "insufficient_evidence_rows": cur.execute(
            "SELECT COUNT(*) FROM generation_run WHERE insufficient_evidence=1").fetchone()[0],
    }
    con.close()
    return st


def files_state():
    man = json.load(open(ANCHOR, encoding="utf-8"))
    entries, missing = {}, []
    for rel, recorded in man["files"].items():
        if "__pycache__" in rel:
            continue
        p = os.path.join(BASE, rel)
        if not os.path.exists(p):
            missing.append(rel)
            continue
        entries[rel] = sha256_file(p)
    return {"recorded_count": len(man["files"]), "checked": len(entries),
            "missing": missing, "entries": entries}


def main():
    phase = (sys.argv[1] if len(sys.argv) > 1 else "before").lower()
    out = {"stage": "P1-11", "phase": phase, "db": db_state(), "files": files_state(),
           "review_dir_exists": os.path.isdir(
               os.path.join(BASE, "structured", "ai", "quality_review"))}
    with open(os.path.join(HERE, "protection_%s.json" % phase), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print("[%s] user_version=%s chars=%s" % (phase, out["db"]["user_version"],
                                             out["db"]["row_counts"]))
    print("       lifecycle=%s" % json.dumps(out["db"]["lifecycle"], ensure_ascii=False))
    print("       events=%s" % json.dumps(out["db"]["events"], ensure_ascii=False))
    print("       run_status=%s insufficient_rows=%s"
          % (json.dumps(out["db"]["run_status"], ensure_ascii=False),
             out["db"]["insufficient_evidence_rows"]))
    print("       files checked=%s missing=%s" % (out["files"]["checked"],
                                                  len(out["files"]["missing"])))


if __name__ == "__main__":
    main()
