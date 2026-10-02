# -*- coding: utf-8 -*-
"""P1-09-A: diff protect_before.json vs protect_after.json."""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    b = json.load(open(os.path.join(HERE, "protect_before.json"), encoding="utf-8"))
    a = json.load(open(os.path.join(HERE, "protect_after.json"), encoding="utf-8"))
    bf, af = b["files"], a["files"]
    added = sorted(set(af) - set(bf))
    removed = sorted(set(bf) - set(af))
    modified = sorted(k for k in set(bf) & set(af) if bf[k] != af[k])
    out = {
        "stage": "P1-09-A",
        "manifest_before": b["manifest_sha256"],
        "manifest_after": a["manifest_sha256"],
        "file_count_before": b["file_count"],
        "file_count_after": a["file_count"],
        "added": added,
        "removed": removed,
        "modified": modified,
        "changed": added + removed + modified,
        "formal_assets_changed": bool(added or removed or modified),
        "pycache_changes": [k for k in added + modified if "__pycache__" in k],
    }
    with open(os.path.join(HERE, "protected_assets_check.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
