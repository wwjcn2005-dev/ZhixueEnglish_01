#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the P3-07 sentence screening manifest (read-only inputs)."""
from __future__ import annotations

import json
from pathlib import Path


BASE = Path(r"D:\ZhixueEnglish")
OUT = BASE / "p3_07_audio_annotation_spike" / "data" / "candidates.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def context_excerpt(text: str, limit: int = 320) -> str:
    text = " ".join((text or "").split())
    return text[:limit]


def main() -> int:
    step9 = load(BASE / "audit" / "P3-06_step9_fulltext_incomplete_audio_complete_candidates.json")
    step10a = load(BASE / "audit" / "P3-06_step10A_fulltext_recovery_candidates.json")
    step10b2 = load(BASE / "audit" / "P3-06_step10B2_AU11_recovery_candidates.json")
    step8c = load(BASE / "audit" / "P3-06_step8C_AU13_practice_candidates.json")
    au06 = load(BASE / "audit" / "P3-06_au06_verified_sentences.json")

    s9 = {c["candidate_id"]: c for c in step9["B_candidates"]}
    s10a = {c["candidate_id"]: c for c in step10a["candidates"]}
    s10b2 = {c["candidate_id"]: c for c in step10b2["candidates"]}
    rows = []

    for cid in sorted(s9):
        src = s9[cid]
        frag = s10a.get(cid, {})
        b2 = s10b2.get(cid)
        sentence = b2.get("learning_text") if b2 else None
        rows.append({
            "sentence_id": cid,
            "candidate_id": cid,
            "kind": "B_SLOT",
            "module": src.get("module"),
            "unit": src.get("unit"),
            "chapter": src.get("module") or src.get("unit"),
            "activity": src.get("activity"),
            "page": src.get("page"),
            "textbook_page": src.get("textbook_page"),
            "audio_id": src.get("audio_id"),
            "audio_num": (src.get("audio_id") or "").split(":")[-1],
            "original_audio_filename": src.get("original_audio_filename"),
            "original_audio_path": src.get("original_audio_path"),
            "prompt_text": frag.get("recovered_fragment") or src.get("source_text"),
            "sentence_text": sentence,
            "source_text": src.get("source_text"),
            "context_text": context_excerpt(src.get("source_text")),
            "text_status": "COMPLETE" if sentence else "FRAGMENT_REQUIRES_TEACHER",
            "existing_sentence_timing": ({
                "start_ms": b2.get("start_ms"),
                "end_ms": b2.get("end_ms"),
                "timing_status": b2.get("timing_status"),
                "source": "P3-06_step10B2",
            } if b2 else None),
            "selection_reason": None,
            "reject_reason": None,
            "pattern_key": None,
            "function_tag": None,
            "duplicate_of": None,
            "screening_status": "CANDIDATE",
            "status": "CANDIDATE",
            "blank_index": src.get("blank_index"),
        })

    # Sentence-level dedupe: one printed sentence with several blanks is one task.
    merged = {}
    for r in rows:
        key = (r["audio_id"], r.get("sentence_text") or r.get("prompt_text"))
        if key not in merged:
            r["source_candidate_ids"] = [r["candidate_id"]]
            r["blank_indexes"] = [r["blank_index"]] if r.get("blank_index") else []
            merged[key] = r
        else:
            merged[key]["source_candidate_ids"].append(r["candidate_id"])
            if r.get("blank_index"):
                merged[key]["blank_indexes"].append(r["blank_index"])
    rows = list(merged.values())

    for r in step8c["candidate_exercise_resources"]:
        timing = None
        if r.get("start_ms") is not None and r.get("end_ms") is not None:
            timing = {
                "start_ms": r.get("start_ms"),
                "end_ms": r.get("end_ms"),
                "timing_status": r.get("timing_status"),
                "source": "P3-06_step8C",
            }
        rows.append({
            "sentence_id": r["resource_id"],
            "candidate_id": r["resource_id"],
            "kind": "AU13_DIALOGUE" if r["resource_id"].startswith("AU13-DLG") else "AU13_LETTER",
            "module": "Unit 1",
            "unit": "Unit 1",
            "chapter": "Unit 1",
            "activity": r.get("activity"),
            "page": "PDF p29-p30",
            "textbook_page": r.get("source_page"),
            "audio_id": r.get("audio_id"),
            "audio_num": (r.get("audio_id") or "").split(":")[-1],
            "original_audio_filename": Path(r.get("original_audio_path", "")).name,
            "original_audio_path": r.get("original_audio_path"),
            "prompt_text": r.get("textbook_text"),
            "sentence_text": r.get("learning_text") or r.get("textbook_text"),
            "source_text": r.get("source_text") or r.get("textbook_text"),
            "context_text": context_excerpt(r.get("source_text") or r.get("textbook_text")),
            "text_status": "COMPLETE",
            "existing_sentence_timing": timing,
            "selection_reason": None,
            "reject_reason": None,
            "pattern_key": None,
            "function_tag": None,
            "duplicate_of": None,
            "screening_status": "CANDIDATE",
            "status": "CANDIDATE",
            "blank_index": None,
        })

    payload = {
        "phase": "P3-07",
        "status": "CANDIDATE",
        "direction": "sentence_review_then_interval_review",
        "candidate_total_before_verified_filter": len(rows) + len(au06.get("sentences") or []),
        "excluded_existing_verified": len(au06.get("sentences") or []),
        "actual_screening_candidates": len(rows),
        "pilot_10": [
            "AU01-B01", "AU02-B01", "AU03-B01", "AU11-B01", "AU12-B01",
            "AU19-B01", "AU25-B01", "AU32-B01", "AU39-B01", "AU13-DLG-01",
        ],
        "candidates": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: payload[k] for k in (
        "candidate_total_before_verified_filter", "excluded_existing_verified",
        "actual_screening_candidates")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
