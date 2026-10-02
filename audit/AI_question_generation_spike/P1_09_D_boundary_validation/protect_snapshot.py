# -*- coding: utf-8 -*-
"""P1-09-D: read-only hash manifest of formal assets (before / after the AI call).
Excludes this phase's own directory. Usage: python protect_snapshot.py before|after
"""

import hashlib
import json
import os
import sqlite3
import sys

BASE = r"D:\ZhixueEnglish"
HERE = os.path.dirname(os.path.abspath(__file__))

ROOTS = [
    "structured/learning", "structured/contentpack", "structured/textbook",
    "structured/audio", "structured/exercises", "structured/staging", "structured/ai",
    "docs", "web", "android",
    "audit/AI_question_generation_spike/20260917_1520_validator_fix",
    "audit/AI_question_generation_spike/P1_04_rule_fixes",
    "audit/AI_question_generation_spike/P1_05_prompt_v3_boundary",
    "audit/AI_question_generation_spike/P1_06_batch_stability",
    "audit/AI_question_generation_spike/P1_07_library_ingest",
    "audit/AI_question_generation_spike/P1_08_A_process_baseline",
    "audit/AI_question_generation_spike/P1_08_B_evidence_assembly_fix",
    "audit/AI_question_generation_spike/P1_08_C_lifecycle_run",
    "audit/AI_question_generation_spike/P1_09_A_quality_review_design",
    "audit/AI_question_generation_spike/P1_09_B_quality_review_run",
    "audit/AI_question_generation_spike/P1_09_C_review_contract",
    "audit/AI_question_generation_spike/P0_closeout",
]
ROOT_FILES = ["初中英语AI辅助学习系统_最高指导原则与开发规范_V1.3.docx",
              "初中英语AI辅助学习系统_产品与UI架构总纲_V2.0.docx"]
SKIP = (".db-wal", ".db-shm", ".db-journal")
LIB = os.path.join(BASE, "structured", "ai", "question_library.db")
LEARN = os.path.join(BASE, "structured", "learning", "learning.db")
CP5 = os.path.join(BASE, "structured", "contentpack", "v5", "FLTRP-EN-7A-2022CUR.sqlite")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def library_state():
    con = sqlite3.connect("file:" + LIB.replace("\\", "/") + "?mode=ro", uri=True)
    cur = con.cursor()
    out = {
        "sha256": sha256_file(LIB),
        "size": os.path.getsize(LIB),
        "row_counts": {t: cur.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
                       for t in ("generation_run", "ai_question", "question_evidence",
                                 "question_learning_object", "question_validation",
                                 "question_event")},
        "lifecycle": {r[0]: r[1] for r in cur.execute(
            "SELECT lifecycle_status, COUNT(*) FROM ai_question GROUP BY 1 ORDER BY 1")},
        "events": {r[0]: r[1] for r in cur.execute(
            "SELECT event_type, COUNT(*) FROM question_event GROUP BY 1 ORDER BY 1")},
        "stale": cur.execute("SELECT COUNT(*) FROM ai_question WHERE stale=1").fetchone()[0],
        "integrity": [r[0] for r in cur.execute("PRAGMA integrity_check")],
    }
    con.close()
    return out


def main():
    phase = (sys.argv[1] if len(sys.argv) > 1 else "before").lower()
    entries, missing = {}, []
    targets = [os.path.join(BASE, r.replace("/", os.sep)) for r in ROOTS]
    targets += [os.path.join(BASE, f) for f in ROOT_FILES]
    targets.append(os.path.join(BASE, "2025年度初一外研版英语教材"))
    for t in targets:
        if not os.path.exists(t):
            missing.append(t)
            continue
        if os.path.isfile(t):
            entries[os.path.relpath(t, BASE)] = sha256_file(t)
            continue
        for dirpath, dirnames, filenames in os.walk(t):
            dirnames.sort()
            for name in sorted(filenames):
                if name.endswith(SKIP):
                    continue
                p = os.path.join(dirpath, name)
                entries[os.path.relpath(p, BASE)] = sha256_file(p)
    combined = hashlib.sha256()
    for rel in sorted(entries):
        combined.update(("%s\x00%s\x00" % (rel, entries[rel])).encode("utf-8"))
    out = {"phase": phase, "file_count": len(entries),
           "manifest_sha256": combined.hexdigest().upper(), "missing_roots": missing,
           "key_hashes": {"question_library.db": sha256_file(LIB),
                          "learning.db": sha256_file(LEARN),
                          "contentpack_v5": sha256_file(CP5)},
           "question_library_state": library_state(),
           "files": entries}
    path = os.path.join(HERE, "protect_%s.json" % phase)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print("wrote", path, "| files", len(entries), "| manifest", out["manifest_sha256"])
    print("key hashes:", json.dumps(out["key_hashes"], ensure_ascii=False))
    print("lifecycle:", json.dumps(out["question_library_state"]["lifecycle"], ensure_ascii=False),
          "| events:", json.dumps(out["question_library_state"]["events"], ensure_ascii=False))
    if missing:
        print("missing roots:", missing)


if __name__ == "__main__":
    main()
