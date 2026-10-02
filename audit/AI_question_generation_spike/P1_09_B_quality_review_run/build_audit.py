# -*- coding: utf-8 -*-
"""P1-09-B: consolidate the phase artifacts into p1_09_b_audit.json."""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return json.load(fh)


def main():
    sel = load("sample_selection.json")
    acc = load("call_accounting.json")
    ai = load("ai_review_output.json")
    cmp_ = load("comparison.json")
    cost = load("review_cost.json")
    noch = load("no_change_verification.json")
    cross = load_json_optional("cross_check_prior_manifests.json")
    prot = load_json_optional("protected_assets_check.json")

    audit = {
        "stage": "P1-09-B",
        "phase_name": "AI 英语质量复核真实小样本验证",
        "ai_calls": acc["api_calls"],
        "retry_count": acc["retry_count"],
        "model": acc["model"],
        "temperature": acc["temperature"],
        "max_tokens": acc["max_tokens"],
        "reasoning_effort": acc["reasoning_effort"],
        "prompt_version": acc["prompt_version"],
        "finish_reason": acc["finish_reason"],
        "status": acc["status"],
        "latency_ms": acc["latency_ms"],
        "usage": {"prompt_tokens": acc["prompt_tokens"],
                  "completion_tokens": acc["completion_tokens"],
                  "reasoning_tokens": acc["reasoning_tokens"],
                  "total_tokens": acc["total_tokens"]},
        "sample_selection": {
            "sample_count": sel["sample_count"],
            "coverage": sel["coverage"],
            "label_class_counts": sel["label_class_counts"],
            "source_sha256_before": sel["source_sha256"],
        },
        "review_output": {
            "review_version_field": ai.get("raw_review_version"),
            "top_level_keys": ai.get("raw_object_keys"),
            "review_count": ai.get("sample_count"),
            "reviews": ai["reviews"],
        },
        "blind_comparison_summary": cmp_["summary"],
        "blind_comparison_matrix": cmp_["matrix"],
        "cost": cost,
        "no_change_verification": {
            "db_sha256_before": noch["db_sha256_before"],
            "db_sha256_after": noch["db_sha256_after"],
            "db_sha256_unchanged": noch["db_sha256_unchanged"],
            "all_sample_questions_unchanged": noch["all_sample_questions_unchanged"],
            "questions_changed": noch["questions_changed"],
            "row_counts": noch["row_counts"],
            "lifecycle": noch["lifecycle"],
            "events": noch["events"],
            "integrity_check": noch["integrity_check"],
            "foreign_key_check": noch["foreign_key_check"],
            "lifecycle_matches_expected": noch["lifecycle_matches_expected"],
            "row_counts_match_expected": noch["row_counts_match_expected"],
        },
        "cross_check_prior_manifests": cross,
        "protected_assets_check": prot,
        "blind_input_contract": {
            "included": ["question_id", "question_type", "question_text", "options",
                         "answer", "textbook_position", "textbook_evidence"],
            "excluded": ["generation explanation", "validator PASS/FAIL",
                         "known-issue labels", "generation prompt",
                         "generation-time model reasoning", "evidence_block_id",
                         "question_fingerprint", "lifecycle_status"],
        },
        "lifecycle_untouched": {
            "auto_approved": 0, "auto_active": 0,
            "question_event_written": 0,
            "note": "AI 复核结果只写入本审计目录，未产生任何 question_event 或状态变化。",
        },
    }
    with open(os.path.join(HERE, "p1_09_b_audit.json"), "w", encoding="utf-8") as fh:
        json.dump(audit, fh, ensure_ascii=False, indent=2)
    s = cmp_["summary"]
    print("wrote p1_09_b_audit.json")
    print("calls=%s retry=%s finish=%s status=%s" % (acc["api_calls"], acc["retry_count"],
                                                     acc["finish_reason"], acc["status"]))
    print("FN=%s FP=%s uniq=%s/%s learn=%s/%s distr=%s/%s"
          % (s["false_negative"], s["false_positive"],
             s["answer_uniqueness_detected"], s["answer_uniqueness_problems_expected"],
             s["low_learning_value_detected"], s["low_learning_value_expected"],
             s["distractor_detected"], s["distractor_problems_expected"]))


def load_json_optional(name):
    path = os.path.join(HERE, name)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


if __name__ == "__main__":
    main()
