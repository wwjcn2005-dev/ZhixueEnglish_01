#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3-07 full-textbook preview: scan audio assets and textbook sentence candidates."""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path


BASE = Path(r"D:\ZhixueEnglish")
OUT = BASE / "audit" / "P3-07_preview"
CONTENTPACK = BASE / "structured" / "contentpack" / "v5" / "FLTRP-EN-7A-2022CUR.sqlite"
AUDIO_DIR = BASE / "2025年度初一外研版英语教材"


def norm_sentence(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text


def split_english_sentences(text: str) -> list:
    text = re.sub(r"[\x00-\x1f\x7f]", " ", text or "")
    text = re.sub(r"\s+", " ", text or "").strip()
    text = re.sub(r"\b(Mr|Mrs|Ms|Dr)\.", r"\1<DOT>", text)
    text = re.sub(r"(?<=[.!?])(?=[A-Z])", " ", text)
    parts = re.split(r"(?<=[.!?])\s*", text)
    out = []
    for p in parts:
        p = p.replace("<DOT>", ".").strip()
        p = re.sub(r"^[•\-\*]+\s*", "", p)
        p = re.sub(r"^[0-9]+\s*", "", p)
        p = re.sub(r"^[A-Z][A-Za-z .'-]{0,24}:\s*", "", p)  # speaker label
        if len(re.findall(r"[A-Za-z]", p)) < 4:
            continue
        if re.search(r"[\u4e00-\u9fff]", p):
            continue
        if p.isupper():
            continue
        if p[-1] not in ".!?":
            continue
        if p[0].islower():
            continue
        if len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", p)) < 2:
            continue
        out.append(p)
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(f"file:{CONTENTPACK}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    assets = [dict(r) for r in con.execute(
        "SELECT * FROM audio_asset ORDER BY audio_id")]
    sections = {r["section_id"]: dict(r) for r in con.execute("SELECT * FROM section")}
    pages = [dict(r) for r in con.execute("SELECT * FROM page")]
    blocks = [dict(r) for r in con.execute(
        "SELECT * FROM content_block ORDER BY page_id, reading_order, block_id")]
    exercises = {}
    try:
        catalog = json.loads((BASE / "structured" / "exercises" / "exercise_catalog_v3.json").read_text(encoding="utf-8"))
        for e in catalog.get("exercises", []):
            if e.get("audio_id"):
                exercises[e["audio_id"].split(":")[-1]] = e
    except Exception:
        catalog = {}

    audio_index = []
    for a in assets:
        code = a["audio_id"].split(":")[-1]
        if int(code[2:]) >= 48:
            continue
        e = exercises.get(code, {})
        pdf_pages = []
        if e.get("pdf_page"):
            pdf_pages = [int(e["pdf_page"])]
        else:
            fn = a["filename"]
            unit_match = re.search(r"(Starter|Unit \d)", fn)
            sec_match = re.search(r"_(Understanding ideas|Developing ideas|Reading for writing|Get ready|Know your school|Get to know each other)", fn)
            if unit_match and sec_match:
                sec_key = {
                    "Understanding ideas": "UNDERSTANDING_IDEAS",
                    "Developing ideas": "DEVELOPING_IDEAS",
                    "Reading for writing": "READING_FOR_WRITING",
                    "Get ready": "GET_READY",
                    "Know your school": "KNOW_YOUR_SCHOOL",
                    "Get to know each other": "GET_TO_KNOW_EACH_OTHER",
                }[sec_match.group(1)]
                for s in sections.values():
                    title = (s.get("title") or "").lower().replace(" ", "")
                    target = sec_match.group(1).lower().replace(" ", "")
                    if title == target:
                        pdf_pages = [int(s["pdf_page_start"])]
                        break
        if not pdf_pages:
            continue
        page_set = set(pdf_pages)
        page_set.add(min(178, pdf_pages[0] + 1))
        audio_index.append({
            "audio_id": a["audio_id"],
            "audio_num": code,
            "filename": a["filename"],
            "relative_path": a["relative_path"],
            "absolute_path": str(AUDIO_DIR / Path(a["filename"]).name),
            "duration_ms": a["duration_ms"],
            "sha256": a["sha256"],
            "unit": e.get("unit") or "",
            "section": e.get("section") or "",
            "activity_no": e.get("exercise_no"),
            "instruction": e.get("instruction") or "",
            "pdf_pages": sorted(page_set),
        })

    by_page = {}
    for b in blocks:
        by_page.setdefault(b["page_id"], []).append(b)
    candidates = []
    for ai in audio_index:
        page_ids = ["FLTRP-EN-7A-2022CUR:P%d" % p for p in ai["pdf_pages"]]
        seen = set()
        for pid in page_ids:
            for b in by_page.get(pid, []):
                for sent in split_english_sentences(b.get("text_raw") or ""):
                    key = norm_sentence(sent).lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    candidates.append({
                        "sentence_id": "PREVIEW:%s:S%04d" % (ai["audio_num"], len(candidates) + 1),
                        "audio_id": ai["audio_id"],
                        "audio_num": ai["audio_num"],
                        "textbook_text": sent,
                        "unit": ai["unit"],
                        "section": ai["section"],
                        "activity_no": ai["activity_no"],
                        "pdf_page": b.get("page_id"),
                        "source_block": b.get("block_id"),
                        "source_kind": "content_block",
                    })

    (OUT / "audio_index.json").write_text(
        json.dumps(audio_index, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "textbook_candidates.json").write_text(
        json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "audio_assets_total": len(assets),
        "activity_audio_scanned": len(audio_index),
        "vocabulary_audio_excluded": len(assets) - len(audio_index),
        "textbook_candidates": len(candidates),
        "by_audio": {},
    }
    for ai in audio_index:
        summary["by_audio"][ai["audio_num"]] = sum(
            1 for c in candidates if c["audio_num"] == ai["audio_num"])
    (OUT / "scan_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
