# -*- coding: utf-8 -*-
"""P1-09-E: prove nothing changed during this phase by re-hashing every file recorded in
earlier phases' manifests (anchors were written BEFORE P1-09-E started).

AI = 0. Read-only. Writes protection_check.json
"""

import hashlib
import json
import os

BASE = r"D:\ZhixueEnglish"
HERE = os.path.dirname(os.path.abspath(__file__))
SPIKE = os.path.dirname(HERE)

ANCHORS = [
    ("P1-09-D protect_after.json (written before P1-09-E)",
     os.path.join(SPIKE, "P1_09_D_boundary_validation", "protect_after.json")),
    ("P1-09-C protect_after.json",
     os.path.join(SPIKE, "P1_09_C_review_contract", "protect_after.json")),
]
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
    out = {"stage": "P1-09-E", "ai_calls": 0, "anchors": [],
           "key_hashes": {k: sha256_file(v) for k, v in KEY_FILES.items()}}
    for label, path in ANCHORS:
        if not os.path.exists(path):
            out["anchors"].append({"anchor": label, "status": "MISSING"})
            continue
        man = json.load(open(path, encoding="utf-8"))
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
        out["anchors"].append({"anchor": label, "manifest_sha256": man["manifest_sha256"],
                               "files_checked": checked, "mismatched": mismatched,
                               "missing": missing,
                               "all_match": mismatched == 0 and missing == 0,
                               "problems": bad[:20]})
    out["all_anchors_match"] = all(a.get("all_match") for a in out["anchors"])
    with open(os.path.join(HERE, "protection_check.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print("key hashes:")
    for k, v in out["key_hashes"].items():
        print("   %-20s %s" % (k, v))
    for a in out["anchors"]:
        print("   %-52s checked=%-5s mismatched=%-3s missing=%-3s all_match=%s"
              % (a["anchor"][:50], a.get("files_checked"), a.get("mismatched"),
                 a.get("missing"), a.get("all_match")))
    print("all_anchors_match:", out["all_anchors_match"])


if __name__ == "__main__":
    main()
