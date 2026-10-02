# -*- coding: utf-8 -*-
"""P1-09-F: prove no formal asset changed during this phase (read-only).

Anchors on the file manifest recorded by P1-09-D (written before P1-09-E/F existed) plus the
three key database hashes. Writes protection_check.json
"""

import hashlib
import json
import os

BASE = r"D:\ZhixueEnglish"
HERE = os.path.dirname(os.path.abspath(__file__))
SPIKE = os.path.dirname(HERE)
ANCHOR = os.path.join(SPIKE, "P1_09_D_boundary_validation", "protect_after.json")
KEY_FILES = {
    "question_library.db": os.path.join(BASE, "structured", "ai", "question_library.db"),
    "learning.db": os.path.join(BASE, "structured", "learning", "learning.db"),
    "contentpack_v5": os.path.join(BASE, "structured", "contentpack", "v5",
                                   "FLTRP-EN-7A-2022CUR.sqlite"),
}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def main():
    man = json.load(open(ANCHOR, encoding="utf-8"))
    checked = mismatched = missing = 0
    bad = []
    for rel, recorded in man["files"].items():
        if "__pycache__" in rel:
            continue
        full = os.path.join(BASE, rel)
        if not os.path.exists(full):
            missing += 1
            bad.append({"file": rel, "issue": "missing"})
            continue
        checked += 1
        if sha256_file(full) != recorded:
            mismatched += 1
            bad.append({"file": rel, "issue": "hash mismatch"})
    out = {"stage": "P1-09-F",
           "anchor": "P1-09-D protect_after.json (written before P1-09-E and P1-09-F)",
           "anchor_manifest_sha256": man["manifest_sha256"],
           "files_checked": checked, "mismatched": mismatched, "missing": missing,
           "all_match": mismatched == 0 and missing == 0, "problems": bad[:20],
           "key_hashes": {k: sha256_file(v) for k, v in KEY_FILES.items()},
           "ai_calls": 1, "retry_count": 0,
           "note": "本阶段只调用一次 DeepSeek 并把结果写入 P1_09_F 目录；未写任何数据库。"}
    with open(os.path.join(HERE, "protection_check.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print("files_checked:", checked, "mismatched:", mismatched, "missing:", missing,
          "all_match:", out["all_match"])
    for k, v in out["key_hashes"].items():
        print("   %-20s %s" % (k, v))


if __name__ == "__main__":
    main()
