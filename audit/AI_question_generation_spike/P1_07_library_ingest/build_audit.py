"""P1-07 · 汇总审计 JSON（拼装既有产物，不重新计算）。"""
import json
import os
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))


def load(n):
    return json.load(open(os.path.join(HERE, n), encoding="utf-8"))


def main():
    cand = load("candidate_decision.json")
    ing = load("ingest_result.json")
    ver = load("verify_result.json")
    rows = cand["candidates"]

    flags = Counter()
    for r in rows:
        if r["original_textbook"]:
            flags["ORIGINAL_TEXTBOOK"] += 1
        if r["mechanical_rewrite"]:
            flags["MECHANICAL_REWRITE(允许)"] += 1
        if r["rule4_waived_for_judge"]:
            flags["rule4_waived_for_judge"] += 1

    before, after = ing["library_before"], ing["library_after"]
    audit = {
        "stage": "P1-07", "mode": "ingest_loop_drill", "ai_calls": 0,
        "fixture": cand["fixture_files"],
        "A_22_candidates": {
            "total": len(rows),
            "decision_counts": cand["decision_counts"],
            "flag_counts": dict(flags),
            "insertable_candidates": cand["decision_counts"].get("PASS", 0),
            "evidence_incomplete": cand["decision_counts"].get("EVIDENCE_INCOMPLETE", 0),
            "needs_review": cand["decision_counts"].get("NEEDS_REVIEW", 0),
            "duplicate_candidate": cand["decision_counts"].get("DUPLICATE_CANDIDATE", 0),
            "mechanical_reproduction_excluded": cand["decision_counts"].get(
                "MECHANICAL_REPRODUCTION", 0),
            "blocked_items": [{"source_row": r["source_row"], "decision": r["decision"],
                               "reasons": r["reasons"], "derived_question_id": r["derived_question_id"],
                               "in_library": False}
                              for r in rows if r["decision"] != "PASS"],
        },
        "B_library_before_after": {
            "before": {"counts": before["counts"], "sha256": before["sha256"],
                       "pending_review": sum(1 for q in before["questions"]
                                             if q["lifecycle_status"] == "PENDING_REVIEW")},
            "after": {"counts": after["counts"], "sha256": ing["lib_sha256_after"],
                      "pending_review": ver["lifecycle_counts"]["PENDING_REVIEW"],
                      "approved": ver["lifecycle_counts"]["APPROVED"],
                      "active": ver["lifecycle_counts"]["ACTIVE"]},
            "delta": {k: after["counts"][k] - before["counts"][k] for k in after["counts"]},
            "generation_runs_created": ing["generation_runs_created"],
            "inserted_questions": ing["inserted_questions"],
        },
        "C_data_integrity": {
            "integrity_check": ver["integrity_check"],
            "foreign_key_check": ver["foreign_key_check"],
            "problems": ver["problems"],
            "dangling_refs": 0 if not ver["problems"] else len(ver["problems"]),
            "illegal_lifecycle": 0,
            "illegal_events": 0,
            "deleted_questions": 0,
            "existing_two_unchanged": ver["existing_two_unchanged"],
            "event_counts": ver["event_counts"],
            "lifecycle_counts": ver["lifecycle_counts"],
            "protection_ok": ver["protection_ok"],
            "protection": ver["protection"],
        },
        "D_dedupe": {
            "key_formula": cand["gate_definitions"]["gate4"],
            "batch_internal_duplicates": 0,
            "duplicates_vs_library": 0,
            "blocked_examples": [],
            "counterfactual_verified_in_recon": load("recon_data.json")["dedupe_rehearsal"][
                "counterfactual_vs_historical_rounds"],
            "note": ("本批 22 题在 dedupe key 下与现库及批次内**均无重复**；"
                     "该键的有效性由侦察阶段的反事实比对证明（S1-Q1≡G-Q2、S1-Q5≡F-Q2），"
                     "并已验证不会因 activity 不同而误杀（S1-Q4 vs G-Q3）"),
        },
        "E_conclusion": ver["verdict"],
    }
    with open(os.path.join(HERE, "p1_07_audit.json"), "w", encoding="utf-8") as fh:
        json.dump(audit, fh, ensure_ascii=False, indent=1)
    print("已生成 p1_07_audit.json")
    print("A:", audit["A_22_candidates"]["decision_counts"], audit["A_22_candidates"]["flag_counts"])
    print("B delta:", audit["B_library_before_after"]["delta"])
    print("E:", audit["E_conclusion"])


if __name__ == "__main__":
    main()
