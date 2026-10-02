#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""教材音频资源层 v1（确定性构建，AI 调用 = 0）

把 54 个官方教材 MP3 纳入**教材资源体系**，形成可查询、可追溯的资源关系：

    audio_asset → Unit/Section/Activity → 教材正式文本 ID → 对齐证据 → 时间范围 → 学习能力 → 题目生成准备状态

原则（与《AI 教材习题生成与题库入库流程规范》《最高指导原则 V1.3》一致）：
  * **教材正式文本是唯一语义事实来源**；ASR 只作为 alignment evidence 保存，绝不写成正式文本；
  * 复用 P3-06 / P3-07 已验证成果（不重跑实验、不重算匹配）；
  * 只记录**关系 / 证据 / 状态 / 能力 / 可用性**，不复制教材正文、不复制音频；
  * 不确定就标记，绝不猜测（NEED_MANUAL_CONFIRMATION / PARTIAL / NO_TEXT_MATCH）；
  * 本脚本只读正式数据，输出独立资源层文件，不修改 contentpack / learning.db / demo / android。

输入（全部只读）：
  structured/contentpack/v5/FLTRP-EN-7A-2022CUR.sqlite   （audio_asset / audio_mapping / activity / section / unit / content_block / learning_item / audio_sentence_annotation）
  structured/exercises/exercise_catalog_v3.json          （音频→活动/单元/板块）
  structured/audio/derived/word_audio_manifest.json      （官方词表音频→词条 + 精确时间）
  audit/P3-06_au06_verified_sentences.json               （AU06 已核验句）
  audit/P3-07_preview/matched_candidates.json            （960 条 ASR↔教材文本候选）
  audit/P3-07_preview/selected_candidates_final.json     （20 条边界复核通过）

输出：
  structured/audio/resources/audio_resource_v1.json
"""

from __future__ import annotations

import datetime
import hashlib
import json
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
CONTENTPACK = BASE / "structured" / "contentpack" / "v5" / "FLTRP-EN-7A-2022CUR.sqlite"
EXERCISE_CATALOG = BASE / "structured" / "exercises" / "exercise_catalog_v3.json"
WORD_MANIFEST = BASE / "structured" / "audio" / "derived" / "word_audio_manifest.json"
P3_06 = BASE / "audit" / "P3-06_au06_verified_sentences.json"
P3_07_MATCHED = BASE / "audit" / "P3-07_preview" / "matched_candidates.json"
P3_07_SELECTED = BASE / "audit" / "P3-07_preview" / "selected_candidates_final.json"
OUT = BASE / "structured" / "audio" / "resources" / "audio_resource_v1.json"

LAYER = "audio_resource_v1"
VERSION = "v1"
STATUSES = ("VERIFIED", "PARTIAL", "NEED_MANUAL_CONFIRMATION", "NO_TEXT_MATCH")
READINESS = ("READY_DETERMINISTIC", "READY_WITH_PROGRAM_PROCESSING", "NEEDS_TEXT_RELATION")

#: 教材活动 instruction → 学习能力（关键词规则，全部来自教材活动文本本身）
CAPABILITY_RULES = (
    ("choose", "listen_choice"),
    ("complete", "listen_fill"),
    ("fill", "listen_fill"),
    ("order", "listen_order"),
    ("match", "listen_match"),
    ("problem", "listen_information_extraction"),
    ("what", "listen_detail"),
    ("answer", "listen_understanding"),
    ("read", "listen_reading"),
    ("passage", "reading_comprehension"),
    ("story", "reading_comprehension"),
    ("talk", "speaking"),
    ("discuss", "speaking"),
    ("work in pairs", "speaking"),
    ("write", "writing"),
    ("draw", "writing"),
)


def _sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _norm(text) -> str:
    t = unicodedata.normalize("NFC", str(text or ""))
    t = t.replace("\u2019", "'").replace("\u2018", "'")
    return re.sub(r"\s+", " ", t).strip().lower()


def _ro(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect("file:%s?mode=ro" % path.as_posix(), uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _capabilities(resource_type: str, instruction: str, has_exact: bool) -> list:
    """能力标签必须来自教材实际活动；wordlist / phonetics 按其教材板块性质。"""
    out = []
    if resource_type == "wordlist_audio":
        out = ["listen_identification", "dictation", "shadowing", "pronunciation"]
        basis = "教材 Words and expressions 词表音频（官方逐词朗读）"
        return [{"name": c, "basis": basis} for c in out]
    if resource_type == "phonetics_audio":
        basis = "教材板块 Phonetics in use（板块性质；音频↔活动映射未解析）"
        return [{"name": c, "basis": basis} for c in ("pronunciation", "listen_identification")]

    low = (instruction or "").lower()
    seen = []
    for key, cap in CAPABILITY_RULES:
        if key in low and cap not in [x["name"] for x in seen]:
            seen.append({"name": cap, "basis": "教材活动 instruction：%s" % instruction[:80]})
    if has_exact and not any(x["name"] == "shadowing" for x in seen):
        seen.append({"name": "shadowing",
                     "basis": "存在精确时间轴 + 教材文本（可用于跟读/播放区间）"})
    return seen


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cp = _ro(CONTENTPACK)

    assets = {r["audio_id"].split(":")[-1]: dict(r)
              for r in cp.execute("SELECT * FROM audio_asset")}
    units = {r["unit_id"]: dict(r) for r in cp.execute("SELECT * FROM unit")}
    sections = {r["section_id"]: dict(r) for r in cp.execute("SELECT * FROM section")}
    activities = {r["activity_id"]: dict(r) for r in cp.execute("SELECT * FROM activity")}

    mapping: dict = {}
    for r in cp.execute("SELECT * FROM audio_mapping"):
        code = r["audio_id"].split(":")[-1]
        entry = mapping.setdefault(code, {"matched": None, "status": None, "candidates": 0})
        if r["target_id"]:
            entry["matched"] = r["target_id"]
            entry["status"] = r["mapping_status"]
        else:
            entry["candidates"] += 1

    # 音频 → 教材文本 block 的候选（P3-07，权威文本 ID 来自 content_block）
    matched = json.loads(P3_07_MATCHED.read_text(encoding="utf-8"))
    selected = json.loads(P3_07_SELECTED.read_text(encoding="utf-8"))
    p306 = json.loads(P3_06.read_text(encoding="utf-8"))
    word_manifest = json.loads(WORD_MANIFEST.read_text(encoding="utf-8"))
    catalog = json.loads(EXERCISE_CATALOG.read_text(encoding="utf-8"))

    block_text = {r["block_id"]: r["text_raw"] or "" for r in cp.execute("SELECT block_id, text_raw FROM content_block")}
    block_by_text: dict = {}
    for bid, text in block_text.items():
        key = _norm(text)
        if key:
            block_by_text.setdefault(key, []).append(bid)

    # P3-07 已建立的「教材文本 → content_block」关系（用于解析句子级资产，不新造匹配算法）
    candidate_block_by_text: dict = {}
    for m in matched:
        key = _norm(m.get("textbook_text"))
        block = m.get("source_block")
        if key and block:
            candidate_block_by_text.setdefault(key, set()).add(block)

    def resolve_block(sentence_text, page_hint=None):
        """把一句教材句解析到唯一的 content_block；无法唯一确定时返回 None（不猜）。"""
        key = _norm(sentence_text)
        if not key:
            return None
        hits = candidate_block_by_text.get(key) or set()
        if len(hits) == 1:
            return next(iter(hits))
        exact = block_by_text.get(key) or []
        if len(exact) == 1:
            return exact[0]
        return None

    annotations = list(cp.execute("SELECT * FROM audio_sentence_annotation"))
    ex_by_audio: dict = {}
    for e in catalog.get("exercises") or []:
        code = (e.get("audio_id") or "").split(":")[-1].upper()
        if code:
            ex_by_audio.setdefault(code, []).append(e)

    matched_by_code: dict = {}
    for m in matched:
        matched_by_code.setdefault(m["audio_num"], []).append(m)
    selected_by_code: dict = {}
    for s in selected:
        selected_by_code.setdefault(s["audio_file"], []).append(s)
    matched_by_sentence_id = {m["sentence_id"]: m for m in matched}

    word_by_code: dict = {}
    for u in word_manifest.get("units", {}).values():
        code = u["audio_id"].split(":")[-1]
        word_by_code[code] = u

    # 运行时使用情况（与 APP 实际调用链一致；导入失败则标记 unknown）
    runtime_used: dict = {}
    try:
        sys.path.insert(0, str(BASE / "demo"))
        sys.path.insert(0, str(BASE / "web"))
        sys.path.insert(0, str(BASE / "learning"))
        import server as demo_server                      # noqa: E402
        for s in demo_server.sentence_assets():
            code = (s.get("audio_url") or "").rsplit("/", 1)[-1].replace(".mp3", "")
            runtime_used.setdefault(code, set()).add("sentence_assets")
        for u in demo_server.units():
            for lesson in demo_server.lessons(u):
                if not any(lesson["counts"].values()):
                    continue
                for q in (demo_server.listen_questions(u, "sentence", lesson) or []):
                    code = (q.get("audio_url") or "").rsplit("/", 1)[-1].replace(".mp3", "")
                    if code:
                        runtime_used.setdefault(code, set()).add("listen.sentence")
            for seg in (demo_server.reading_segments(u) or []):
                code = (seg.get("audio_url") or "").rsplit("/", 1)[-1].replace(".mp3", "")
                if code:
                    runtime_used.setdefault(code, set()).add("reading_segments")
    except Exception as exc:                              # noqa: BLE001
        print("WARN: 运行时使用情况枚举失败（used_by_app 记为 unknown）：%s" % exc)

    resources = []
    for code in sorted(assets):
        a = assets[code]
        info = mapping.get(code) or {}
        ex = ex_by_audio.get(code) or []
        # ---- 单元 / 板块 / 活动（只用正式来源，猜不到的就不写）
        activity_id = info.get("matched") or (ex[0].get("activity_id") if ex else None)
        unit_code = section_key = None
        unit_source = None
        if activity_id and activity_id in activities:
            sec = sections.get(activities[activity_id]["section_id"]) or {}
            unit = units.get(sec.get("unit_id")) or {}
            unit_code = unit.get("unit_code")
            section_key = sec.get("section_key")
            unit_source = "contentpack: audio_mapping/exercise→activity→section→unit"
        if not unit_code and ex:
            unit_code = ex[0].get("unit")
            section_key = ex[0].get("section")
            unit_source = "contentpack: exercise_catalog_v3"
        if not unit_code and code in word_by_code:
            unit_code = word_by_code[code].get("unit_code")
            section_key = "WORDS_AND_EXPRESSIONS"
            unit_source = "structured/audio/derived/word_audio_manifest.json"
        if not unit_code:
            m = re.match(r"\d+_([^_]+)_(.*)\.mp3$", a["filename"])
            unit_code = (m.group(1) if m else None)
            unit_source = "official filename（候选，未与教材结构确认）"

        if code in word_by_code:
            resource_type = "wordlist_audio"
        elif unit_code and re.search(r"phonetic", a["filename"], re.I):
            resource_type = "phonetics_audio"
        else:
            resource_type = "activity_audio"

        # ---- 教材正式文本 → 音频 的对齐段
        segments = []
        sid = 0

        def add_segment(text_kind, text_id, start, end, timing, method, evidence, confidence, status, artifact):
            nonlocal sid
            sid += 1
            segments.append({
                "segment_id": "AR:%s:S%03d" % (code, sid),
                "text_resource_kind": text_kind,
                "text_resource_id": text_id,
                "start_ms": int(start) if start is not None else None,
                "end_ms": int(end) if end is not None else None,
                "timing_kind": timing,
                "alignment_method": method,
                "alignment_evidence": evidence,
                "confidence": confidence,
                "status": status,
                "source_artifact": artifact,
            })

        # 1) 官方词表音频 → 词条（learning_item）+ 精确时间（离线静音切分，确定性）
        if code in word_by_code:
            for w in word_by_code[code].get("words") or []:
                add_segment("learning_item", w.get("item_id"), w.get("start_ms"), w.get("end_ms"),
                            "exact", "official_wordlist_silence_segmentation",
                            {"source_audio_id": w.get("source_audio_id"), "key": w.get("key"),
                             "wav_path": w.get("path"), "source_sha256": word_by_code[code].get("source_sha256")},
                            "HIGH", "VERIFIED", "structured/audio/derived/word_audio_manifest.json")

        # 2) P3-07 边界复核通过（精确时间；text_resource_id 由 source_block 提供）
        for s in selected_by_code.get(code, []):
            m = matched_by_sentence_id.get(s["sentence_id"]) or {}
            block = m.get("source_block")
            add_segment("content_block", block, s.get("final_start_ms"), s.get("final_end_ms"),
                        "exact", "p3_07_boundary_pass",
                        {"sentence_id": s.get("sentence_id"), "asr_text": s.get("asr_text"),
                         "match_reason": s.get("match_reason"), "boundary_status": s.get("boundary_status"),
                         "reason": s.get("reason")},
                        s.get("match_confidence") or "HIGH",
                        "VERIFIED" if block else "NEED_MANUAL_CONFIRMATION",
                        "audit/P3-07_preview/selected_candidates_final.json")

        # 3) contentpack 人工核验句（VERIFIED；文本与教材 block 精确归一化匹配才写 block id）
        for r in annotations:
            if r["audio_id"].split(":")[-1] != code:
                continue
            block = resolve_block(r["sentence_text"])
            add_segment("content_block", block, r["start_ms"], r["end_ms"], "exact",
                        "contentpack_audio_sentence_annotation",
                        {"sentence_uid": r["sentence_uid"], "annotation_status": r["status"],
                         "origin": r["origin"], "text_ref": r["sentence_text"],
                         "block_match": ("unique" if block else "not_unique"),
                         "has_time": (r["start_ms"] is not None and r["end_ms"] is not None)},
                        "HIGH",
                        "VERIFIED" if (block and r["start_ms"] is not None and r["end_ms"] is not None)
                        else "NEED_MANUAL_CONFIRMATION",
                        "contentpack: audio_sentence_annotation")

        # 4) P3-06 已核验句（AU06；文本与教材 block 精确匹配才写 block id）
        for s in p306.get("sentences") or []:
            if (s.get("audio_id") or "").split(":")[-1] != code:
                continue
            block = resolve_block(s.get("text"))
            add_segment("content_block", block, s.get("start_ms"), s.get("end_ms"), "exact",
                        "p3_06_verified_word_timestamps",
                        {"sentence_index": s.get("sentence_index"), "source": s.get("source"),
                         "status": s.get("status"), "asr_text": s.get("text"),
                         "text_ref": s.get("text"),
                         "block_match": ("unique" if block else "not_unique"),
                         "has_time": (s.get("start_ms") is not None and s.get("end_ms") is not None)},
                        "HIGH",
                        "VERIFIED" if (block and s.get("start_ms") is not None
                                       and s.get("end_ms") is not None)
                        else "NEED_MANUAL_CONFIRMATION",
                        "audit/P3-06_au06_verified_sentences.json")

        # 5) P3-07 高/中置信候选（文本 ID 权威、时间粗糙）→ PARTIAL
        counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "MATCH_UNCERTAIN": 0}
        for m in matched_by_code.get(code, []):
            conf = m.get("match_confidence") or "MATCH_UNCERTAIN"
            counts[conf] = counts.get(conf, 0) + 1
            if conf in ("HIGH", "MEDIUM"):
                add_segment("content_block", m.get("source_block"), m.get("rough_start_ms"), m.get("rough_end_ms"),
                            "rough", "p3_07_asr_word_window_match",
                            {"sentence_id": m.get("sentence_id"), "asr_text": m.get("asr_text"),
                             "match_score": m.get("match_score"), "match_confidence": conf,
                             "textbook_text_ref": m.get("source_block")},
                            conf, "PARTIAL", "audit/P3-07_preview/matched_candidates.json")

        exact = [s for s in segments if s["timing_kind"] == "exact" and s["text_resource_id"]]
        verified_ids = {s["text_resource_id"] for s in exact if s["status"] == "VERIFIED"}
        partial_ids = {s["text_resource_id"] for s in segments
                       if s["status"] == "PARTIAL" and s["text_resource_id"]}
        if any(s["status"] == "VERIFIED" for s in segments) and exact:
            alignment_status = "VERIFIED"
        elif partial_ids:
            alignment_status = "PARTIAL"
        elif segments or info.get("matched") or info.get("candidates"):
            alignment_status = "NEED_MANUAL_CONFIRMATION"
        else:
            alignment_status = "NO_TEXT_MATCH"

        if exact:
            readiness = "READY_DETERMINISTIC"
        elif partial_ids or (info.get("matched") and (ex or annotations)):
            readiness = "READY_WITH_PROGRAM_PROCESSING"
        else:
            readiness = "NEEDS_TEXT_RELATION"

        caps = _capabilities(resource_type, (activities.get(activity_id) or {}).get("instruction")
                             if activity_id else (ex[0].get("instruction") if ex else ""), bool(exact))
        used = runtime_used.get(code)
        resources.append({
            "resource_id": "AR:%s" % code,
            "audio_code": code,
            "audio_asset_id": a["audio_id"],
            "filename": a["filename"],
            "duration_ms": a.get("duration_ms"),
            "sha256": a.get("sha256"),
            "unit_code": unit_code,
            "section_key": section_key,
            "activity_id": activity_id,
            "resource_type": resource_type,
            "identity_source": "contentpack: audio_asset",
            "unit_source": unit_source,
            "alignment_status": alignment_status,
            "confidence": ("HIGH" if alignment_status == "VERIFIED" else
                           "MEDIUM" if alignment_status == "PARTIAL" else "LOW"),
            "capabilities": caps,
            "readiness": readiness,
            "counts": {"exact_segments": len(exact),
                       "partial_segments": sum(1 for s in segments if s["status"] == "PARTIAL"),
                       "text_blocks": len(verified_ids | partial_ids),
                       "candidates": counts, "exercise_links": len(ex),
                       "mapping": info.get("status") or ("CANDIDATE" if info.get("candidates") else None)},
            "used_by_app": {"direct": bool(used), "features": sorted(used) if used else [],
                            "indirect": resource_type == "wordlist_audio"},
            "segments": segments,
            "source_artifacts": sorted({s["source_artifact"] for s in segments}),
            "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
        })

    payload = {
        "layer": LAYER,
        "version": VERSION,
        "status_vocabulary": list(STATUSES),
        "readiness_vocabulary": list(READINESS),
        "principle": "教材正式文本是唯一语义事实来源；ASR 仅作 alignment evidence；不确定即标记，不猜测。",
        "generated_by": "builder/build_audio_resource_layer_v01.py",
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "ai_calls": 0,
        "sources": [{"path": str(p.relative_to(BASE)).replace("\\", "/"), "sha256": _sha256(p)}
                    for p in (CONTENTPACK, EXERCISE_CATALOG, WORD_MANIFEST, P3_06,
                              P3_07_MATCHED, P3_07_SELECTED)],
        "audio_resources": resources,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    stat = {}
    for r in resources:
        stat[r["alignment_status"]] = stat.get(r["alignment_status"], 0) + 1
    ready = {}
    for r in resources:
        ready[r["readiness"]] = ready.get(r["readiness"], 0) + 1
    print("输出 →", OUT)
    print("audio_asset:", len(assets), "| 资源记录:", len(resources))
    print("alignment_status:", stat)
    print("readiness:", ready)
    print("segments 合计:", sum(len(r["segments"]) for r in resources))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
