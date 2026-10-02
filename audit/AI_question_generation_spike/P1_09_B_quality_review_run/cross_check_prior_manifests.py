# -*- coding: utf-8 -*-
"""P1-09-B: cross-check current file hashes against manifests recorded by earlier phases.

Anchors: P1-09-A protect_after.json (recorded BEFORE this phase's AI call) and
P1-08-C protect_after.json. Any mismatch means a frozen artifact changed.
"""

import hashlib
import json
import os

BASE = r"D:\ZhixueEnglish"
HERE = os.path.dirname(os.path.abspath(__file__))
SPIKE = os.path.dirname(HERE)

ANCHORS = [
    ("P1-09-A protect_after.json (recorded before the P1-09-B AI call)",
     os.path.join(SPIKE, "P1_09_A_quality_review_design", "protect_after.json")),
    ("P1-08-C protect_after.json",
     os.path.join(SPIKE, "P1_08_C_lifecycle_run", "protect_after.json")),
]


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def main():
    out = {"stage": "P1-09-B", "anchors": []}
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
        out["anchors"].append({
            "anchor": label, "manifest_sha256": man["manifest_sha256"],
            "files_checked": checked, "mismatched": mismatched, "missing": missing,
            "all_match": (mismatched == 0 and missing == 0), "problems": bad[:20],
        })
    with open(os.path.join(HERE, "cross_check_prior_manifests.json"), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    for a in out["anchors"]:
        print("%-70s checked=%s mismatched=%s missing=%s all_match=%s"
              % (a["anchor"][:68], a.get("files_checked"), a.get("mismatched"),
                 a.get("missing"), a.get("all_match")))


if __name__ == "__main__":
    main()
