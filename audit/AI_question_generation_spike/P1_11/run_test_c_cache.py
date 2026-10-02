# -*- coding: utf-8 -*-
"""P1-11 Test C: cache reuse by question_fingerprint + review_context_hash + review_version.

No AI call at all (ai_calls = 0): identical key -> HIT (reuse the saved review record);
changed review_version or review_context_hash -> MISS (a new review would be allowed).
Writes: test_c_result.json
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = r"D:\ZhixueEnglish"
SPIKE = os.path.join(BASE, "audit", "AI_question_generation_spike")
P1_09_D = os.path.join(SPIKE, "P1_09_D_boundary_validation")
sys.path.insert(0, HERE)
import p1_11_pipeline as P  # noqa: E402

FIXTURE_SECTION = {"FIX-C1": "FLTRP-EN-7A-2022CUR:U2:UNDERSTANDING_IDEAS",
                   "FIX-C2": "FLTRP-EN-7A-2022CUR:U1:UNDERSTANDING_IDEAS"}
LETTERS = ["A", "B", "C", "D"]
EFFECTIVE_VERSION = "P1-11-v1"   # the version recorded by the real Test B call


def build_items():
    fx = json.load(open(os.path.join(P1_09_D, "fixtures.json"), encoding="utf-8"))["fixtures"]
    items = []
    for f in fx:
        if f["fixture_id"] not in ("FIX-C1", "FIX-C2"):
            continue
        items.append({"question_id": f["fixture_id"], "question_type": f["question_type"],
                      "question_text": f["question"], "options":
                          [{"option": LETTERS[i], "text": t} for i, t in enumerate(f["options"])],
                      "stored_answer": f["answer"],
                      "textbook_evidence": [{"textbook_page": b["textbook_page"], "text": b["text"]}
                                            for b in f["textbook_context"]],
                      "evidence_quote": f["textbook_context"][0]["text"]})
    return items


def main():
    items = build_items()
    out = {"stage": "P1-11", "test": "C_cache", "ai_calls": 0, "retry_count": 0, "checks": []}
    for it in items:
        qid = it["question_id"]
        fp = P.fingerprint(FIXTURE_SECTION[qid], "", it["question_type"],
                           it["question_text"], it["evidence_quote"])
        ctx_hash = P.review_context_hash([it])
        hit = P.cache_lookup(fp, ctx_hash, EFFECTIVE_VERSION)
        missed_version = P.cache_lookup(fp, ctx_hash, "P1-11-NEXT")
        missed_context = P.cache_lookup(fp, ctx_hash + "-CHANGED", EFFECTIVE_VERSION)
        out["checks"].append({
            "question_id": qid, "question_fingerprint": fp, "review_context_hash": ctx_hash,
            "identical_key": {"hit": hit["hit"], "file": hit["file"], "reason": hit["reason"],
                              "ai_calls_needed": 0 if hit["hit"] else 1,
                              "reused_decision": (hit["record"] or {}).get("suggested_decision"),
                              "reused_answer_unique": (hit["record"] or {}).get("answer_unique"),
                              "reused_status": (hit["record"] or {}).get("answer_unique_status")},
            "changed_review_version": {"hit": missed_version["hit"],
                                       "ai_calls_allowed": 1 if not missed_version["hit"] else 0,
                                       "executed": False,
                                       "note": "仅判定允许重新审核，按成本纪律**未实际调用**"},
            "changed_review_context": {"hit": missed_context["hit"],
                                       "ai_calls_allowed": 1 if not missed_context["hit"] else 0,
                                       "executed": False,
                                       "note": "仅判定允许重新审核，按成本纪律**未实际调用**"},
        })
    out["all_identical_keys_hit"] = all(c["identical_key"]["hit"] for c in out["checks"])
    out["all_changed_keys_miss"] = all(
        (not c["changed_review_version"]["hit"]) and (not c["changed_review_context"]["hit"])
        for c in out["checks"])
    out["ai_calls_performed_in_this_test"] = 0
    with open(os.path.join(HERE, "test_c_result.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
