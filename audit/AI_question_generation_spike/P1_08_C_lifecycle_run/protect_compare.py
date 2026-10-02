# -*- coding: utf-8 -*-
"""P1-08-C: diff protect_before.json vs protect_after.json."""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return json.load(fh)


def main():
    b = load("protect_before.json")
    a = load("protect_after.json")
    bf, af = b["files"], a["files"]
    added = sorted(set(af) - set(bf))
    removed = sorted(set(bf) - set(af))
    modified = sorted(k for k in set(bf) & set(af) if bf[k] != af[k])
    out = {
        "manifest_before": b["manifest_sha256"],
        "manifest_after": a["manifest_sha256"],
        "file_count_before": b["file_count"],
        "file_count_after": a["file_count"],
        "added": added,
        "removed": removed,
        "modified": modified,
        "changed": added + removed + modified,
        "formal_assets_changed": bool(added or removed or modified),
        "question_library_db_excluded": True,
    }
    with open(os.path.join(HERE, "protected_assets_check.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print(json.dumps({k: out[k] for k in
                      ("manifest_before", "manifest_after", "file_count_before",
                       "file_count_after", "added", "removed", "modified",
                       "formal_assets_changed")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
