# -*- coding: utf-8 -*-
"""P1-09-A protection snapshot: read-only hash manifest (before/after).

Usage: python protect_snapshot.py before|after
The P1_09_A audit directory itself is excluded; everything else listed is hashed.
"""

import hashlib
import json
import os
import sys

BASE = r"D:\ZhixueEnglish"
HERE = os.path.dirname(os.path.abspath(__file__))

ROOTS = [
    "structured/learning",
    "structured/contentpack",
    "structured/textbook",
    "structured/audio",
    "structured/exercises",
    "structured/staging",
    "docs",
    "web",
    "android",
    "structured/ai",
    "audit/AI_question_generation_spike/20260917_1520_validator_fix",
    "audit/AI_question_generation_spike/P1_04_rule_fixes",
    "audit/AI_question_generation_spike/P1_05_prompt_v3_boundary",
    "audit/AI_question_generation_spike/P1_06_batch_stability",
    "audit/AI_question_generation_spike/P1_07_library_ingest",
    "audit/AI_question_generation_spike/P1_08_A_process_baseline",
    "audit/AI_question_generation_spike/P1_08_B_evidence_assembly_fix",
    "audit/AI_question_generation_spike/P1_08_C_lifecycle_run",
    "audit/AI_question_generation_spike/P0_closeout",
]

ROOT_FILES = [
    "初中英语AI辅助学习系统_最高指导原则与开发规范_V1.3.docx",
    "初中英语AI辅助学习系统_产品与UI架构总纲_V2.0.docx",
]

SKIP_SUFFIX = (".db-wal", ".db-shm", ".db-journal")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def walk(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            if name.endswith(SKIP_SUFFIX):
                continue
            yield os.path.join(dirpath, name)


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
        for p in walk(t):
            entries[os.path.relpath(p, BASE)] = sha256_file(p)

    combined = hashlib.sha256()
    for rel in sorted(entries):
        combined.update(("%s\x00%s\x00" % (rel, entries[rel])).encode("utf-8"))

    out = {"phase": phase, "file_count": len(entries),
           "manifest_sha256": combined.hexdigest().upper(),
           "missing_roots": missing, "files": entries}
    path = os.path.join(HERE, "protect_%s.json" % phase)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print("wrote", path, "files", len(entries), "manifest", out["manifest_sha256"])
    if missing:
        print("missing roots:", missing)


if __name__ == "__main__":
    main()
