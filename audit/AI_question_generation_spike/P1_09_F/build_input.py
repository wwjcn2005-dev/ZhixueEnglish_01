# -*- coding: utf-8 -*-
"""P1-09-F: build the blind per-candidate input for FIX-C1 / FIX-C2.

Reuses the P1-09-D fixtures verbatim (question / options / answer / textbook_context are copied,
never re-designed). No AI call, no write to any database.

AI-visible fields only: question_id, question_type, question_text, options, current textbook
answer, textbook location, full evidence block, grade context, answer standard.
Never included: hidden_gold, category labels, introduced_defect, gold_reason, validator results,
previous AI answers, generation prompt, lifecycle, question_library state.

Writes: ai_input_snapshot.json, candidate_map.json, input_manifest.json
"""

import hashlib
import json
import os

BASE = r"D:\ZhixueEnglish"
SPIKE = os.path.join(BASE, "audit", "AI_question_generation_spike")
P1_09_D = os.path.join(SPIKE, "P1_09_D_boundary_validation")
HERE = os.path.dirname(os.path.abspath(__file__))

TARGETS = ["FIX-C1", "FIX-C2"]
LETTERS = ["A", "B", "C", "D", "E", "F"]
GRADE = "外研版初中英语 七年级上册（初一第一学期）"

FORBIDDEN_TOKENS = ["hidden_gold", "gold_reason", "introduced_defect", "known_issue", "category",
                    "expected", "validator", "mechanical_rewrite", "lifecycle", "second answer",
                    "第二答案", "P1-09-D", "P1-09-B", "unique"]


def canonical(o):
    return hashlib.sha256(json.dumps(o, ensure_ascii=False, sort_keys=True).encode()).hexdigest().upper()


def main():
    fixtures = json.load(open(os.path.join(P1_09_D, "fixtures.json"), encoding="utf-8"))
    manifest = json.load(open(os.path.join(P1_09_D, "fixture_manifest.json"), encoding="utf-8"))
    src_sha = canonical(fixtures)
    assert src_sha == manifest["fixtures_sha256"], "P1-09-D fixtures changed since it was frozen"

    items, cmap = [], {}
    for f in fixtures["fixtures"]:
        if f["fixture_id"] not in TARGETS:
            continue
        opts = f["options"]
        candidates = [{"option": LETTERS[i], "text": t} for i, t in enumerate(opts)]
        items.append({
            "question_id": f["fixture_id"],
            "question_type": f["question_type"],
            "question_text": f["question"],
            "options": candidates,
            "current_textbook_answer": f["answer"],
            "answer_standard": f["answer_standard"],
            "textbook_location": f["location"],
            "textbook_evidence": [{"textbook_page": b["textbook_page"], "text": b["text"]}
                                  for b in f["textbook_context"]],
        })
        cmap[f["fixture_id"]] = {"options": candidates, "current_answer": f["answer"],
                                 "options_count": len(candidates)}
        assert len(candidates) <= len(LETTERS), "too many options"

    blind = {"review_version": "P1-09-F-v1", "grade_context": GRADE,
             "items": items}
    text = json.dumps(blind, ensure_ascii=False)
    leaked = [t for t in FORBIDDEN_TOKENS if t.lower() in text.lower()]
    assert not leaked, "forbidden token leaked into AI input: %s" % leaked
    # extra guard: no gold-ish values
    for f in fixtures["fixtures"]:
        if f["fixture_id"] in TARGETS:
            assert f["gold"]["gold_reason"] not in text
            assert (f.get("introduced_defect") or "xx") not in text

    with open(os.path.join(HERE, "ai_input_snapshot.json"), "w", encoding="utf-8") as fh:
        json.dump(blind, fh, ensure_ascii=False, indent=2)
    with open(os.path.join(HERE, "candidate_map.json"), "w", encoding="utf-8") as fh:
        json.dump({"stage": "P1-09-F", "candidate_map": cmap}, fh, ensure_ascii=False, indent=2)
    man = {"stage": "P1-09-F",
           "source": "P1_09_D_boundary_validation/fixtures.json (verbatim reuse, not re-designed)",
           "source_fixtures_sha256": src_sha,
           "source_fixtures_sha256_matches_p1_09_d_manifest": True,
           "ai_input_sha256": canonical(blind),
           "ai_input_chars": len(text),
           "fixture_count": len(items),
           "leak_check": "PASS (no hidden_gold / category / defect / validator / unique token)",
           "forbidden_token_scan": {"checked": FORBIDDEN_TOKENS, "found": leaked}}
    with open(os.path.join(HERE, "input_manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(man, fh, ensure_ascii=False, indent=2)

    print("items:", len(items), "| ai_input_chars:", len(text))
    print(json.dumps(man, ensure_ascii=False, indent=1))
    for it in items:
        print("---", it["question_id"], "| current answer:", it["current_textbook_answer"])
        print("   ", it["question_text"])
        print("   options:", [c["option"] + ":" + c["text"] for c in it["options"]])


if __name__ == "__main__":
    main()
