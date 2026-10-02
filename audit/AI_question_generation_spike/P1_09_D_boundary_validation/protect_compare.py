# -*- coding: utf-8 -*-
"""P1-09-D: diff before/after manifests and write protection_manifest.json."""

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
    lib_before, lib_after = b["question_library_state"], a["question_library_state"]
    out = {
        "stage": "P1-09-D",
        "manifest_before": b["manifest_sha256"], "manifest_after": a["manifest_sha256"],
        "file_count_before": b["file_count"], "file_count_after": a["file_count"],
        "added": added, "removed": removed, "modified": modified,
        "changed": added + removed + modified,
        "formal_assets_changed": bool(added or removed or modified),
        "pycache_changes": [k for k in added + modified if "__pycache__" in k],
        "key_hashes_before": b["key_hashes"], "key_hashes_after": a["key_hashes"],
        "question_library": {
            "row_counts_unchanged": lib_before["row_counts"] == lib_after["row_counts"],
            "events_unchanged": lib_before["events"] == lib_after["events"],
            "lifecycle_unchanged": lib_before["lifecycle"] == lib_after["lifecycle"],
            "stale_unchanged": lib_before["stale"] == lib_after["stale"],
            "sha256_unchanged": lib_before["sha256"] == lib_after["sha256"],
            "before": lib_before, "after": lib_after,
        },
    }
    out["all_checks_pass"] = (
        not out["formal_assets_changed"]
        and all(v for k, v in out["question_library"].items() if k.endswith("unchanged")))
    with open(os.path.join(HERE, "protection_manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print("changed:", out["changed"][:10], "| count", len(out["changed"]))
    print("formal_assets_changed:", out["formal_assets_changed"])
    print("question_library:", json.dumps(
        {k: v for k, v in out["question_library"].items() if k.endswith("unchanged")},
        ensure_ascii=False))
    print("all_checks_pass:", out["all_checks_pass"])


if __name__ == "__main__":
    main()
