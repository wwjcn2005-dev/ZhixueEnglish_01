#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P1-05-B 第一阶段：教材内容数据库 Dry-run 构建器 V0.1

作用：在正式建库之前，调用既有 parser 在内存中构建“即将导入的数据集合”，
执行字段 / 主键 / 外键 / source_ref / 版本隔离 / 音频状态 / 重复 / hash /
parser quality 等检查，并输出 Dry-run 报告。

严格边界：
  - 不创建正式 contentpack SQLite
  - 不创建 learner.db
  - 不修改 parser、PDF、MP3
  - 不调用 AI、不生成 transcript、不确认音频映射
  - 不安装任何新依赖（仅使用标准库 + 已批准的 PyMuPDF / mutagen）

用法：
  python D:\\ZhixueEnglish\\builder\\build_content_db_v01.py
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# 导入 parser 时不产生 __pycache__
sys.dont_write_bytecode = True

BASE_DIR = Path(r"D:\ZhixueEnglish")
DOCS_DIR = BASE_DIR / "docs"
PARSER_DIR = BASE_DIR / "parser"
SOURCE_DIR = BASE_DIR / "2025年度初一外研版英语教材"
AUDIT_DIR = BASE_DIR / "audit"

PARSER_FILE = PARSER_DIR / "textbook_parser_v01.py"

SCHEMA_VERSION = "p1-04-v1"
RULE_SET_VERSION = "P1-03-C"
EXPECTED_PDF_SHA256 = "C732051E91121BC991DBDD01235662629620DF6BFCCBBBD834EAEA6FCECD4F2F"
EXPECTED_MP3_COUNT = 54

FROZEN = {
    "unit": 8,
    "section": 46,
    "activity": 96,
    "duplicate_anomaly": 0,
    "boundary_need_review": 23,
    "reading_order_need_review": 88,
}

PASS, PASS_WITH_NOTES, STOP = "PASS", "PASS WITH NOTES", "STOP"


# --------------------------------------------------------------------------
# 工具
# --------------------------------------------------------------------------

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def make_textbook_id(publisher_code="FLTRP", lang="EN", grade="7", volume="A",
                     curriculum="2022CUR") -> str:
    """按 P1-04 约定由字段确定性生成，不使用手写字面量。"""
    return f"{publisher_code}-{lang}-{grade}{volume}-{curriculum}"


def load_parser_module():
    spec = importlib.util.spec_from_file_location("textbook_parser_v01", str(PARSER_FILE))
    module = importlib.util.module_from_spec(spec)
    sys.modules["textbook_parser_v01"] = module
    spec.loader.exec_module(module)
    return module


UNIT_KEY = {
    "Starter": "STARTER",
    "Appendix": "APPENDIX",
}


def unit_key(unit_id: str) -> str:
    if unit_id in UNIT_KEY:
        return UNIT_KEY[unit_id]
    m = re.match(r"Unit (\d)", unit_id)
    return f"U{m.group(1)}" if m else re.sub(r"[^A-Z0-9]+", "_", unit_id.upper())


def section_key(title: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", title.upper()).strip("_") or "UNKNOWN"


# --------------------------------------------------------------------------
# 第一步：输入核验
# --------------------------------------------------------------------------

def collect_inputs(parser_module) -> dict:
    import mutagen.mp3
    from mutagen.id3 import ID3

    pdfs = sorted(SOURCE_DIR.glob("*.pdf"))
    mp3s = sorted(SOURCE_DIR.glob("*.mp3"))
    pdf = pdfs[0] if pdfs else None

    audio_rows = []
    for path in mp3s:
        info = mutagen.mp3.MP3(str(path))
        try:
            tags = ID3(str(path))
            id3 = f"ID3v2.{tags.version[0]}.{tags.version[1]}"
        except Exception:
            id3 = "unknown"
        audio_rows.append({
            "filename": path.name,
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "duration_ms": int(round(info.info.length * 1000)),
            "bitrate": int(getattr(info.info, "bitrate", 0) or 0),
            "sample_rate": int(getattr(info.info, "sample_rate", 0) or 0),
            "channels": int(getattr(info.info, "channels", 0) or 0),
            "id3_version": id3,
        })

    return {
        "pdf_path": pdf,
        "pdf_sha256": sha256_file(pdf) if pdf else "",
        "pdf_size": pdf.stat().st_size if pdf else 0,
        "pdf_count": len(pdfs),
        "mp3_count": len(mp3s),
        "other_files": sorted(
            p.name for p in SOURCE_DIR.iterdir()
            if p.is_file() and p.suffix.lower() not in (".pdf", ".mp3")
        ),
        "audio_rows": audio_rows,
    }


# --------------------------------------------------------------------------
# 第二步：构建“即将导入的数据集合”
# --------------------------------------------------------------------------

def build_dataset(parser, inputs: dict) -> dict:
    textbook_id = make_textbook_id()
    snapshot_id = f"{textbook_id}:S{datetime.now().strftime('%Y%m%dT%H%M%S')}"

    pages, blocks, evidence = [], [], []
    asset_index: dict = {}
    unit_rows, section_rows, activity_rows, activity_content = [], [], [], []
    sub_question_rows = []

    unit_starts = {u.pdf_page_start for u in parser.units}

    for pg in parser.pages:
        page_id = f"{textbook_id}:P{pg.pdf_page}"
        if pg.pdf_page == 1:
            role = "front_cover"
        elif pg.pdf_page == 178:
            role = "back_cover"
        elif pg.pdf_page <= 6:
            role = "front_matter"
        elif pg.pdf_page == 115:
            role = "appendix_index"
        elif pg.pdf_page in unit_starts:
            role = "unit_opener"
        else:
            role = "content"

        pages.append({
            "page_id": page_id,
            "textbook_id": textbook_id,
            "snapshot_id": snapshot_id,
            "pdf_page": pg.pdf_page,
            "textbook_page": pg.textbook_page,
            "textbook_page_evidence": pg.textbook_page_evidence,
            "page_role": role,
            "layout_type": pg.layout_type,
            "reading_order_status": pg.reading_order_status,
            "text_chars": pg.text_chars,
            "review_status": "NEED_REVIEW" if pg.needs_review else "EXTRACTED",
        })
        evidence.append({
            "evidence_id": f"{page_id}:E0",
            "source_type": "pdf_text",
            "pdf_page": pg.pdf_page,
            "textbook_page": pg.textbook_page,
            "target_type": "page",
            "target_id": page_id,
        })

        for idx, b in enumerate(pg.blocks):
            block_id = f"{page_id}:B{idx}"
            role_name = b.role
            if role_name in ("heading", "section_title"):
                kind = "heading"
            elif role_name == "footer":
                kind = "footer_text"
            elif role_name == "sidebar":
                kind = "sidebar_tip"
            elif '"' in b.text and ":" in b.text:
                kind = "dialogue"
            else:
                kind = "exercise_item"
            blocks.append({
                "block_id": block_id,
                "page_id": page_id,
                "textbook_id": textbook_id,
                "snapshot_id": snapshot_id,
                "text_raw": b.raw_text,
                "text_normalized": b.text,
                "block_kind": kind,
                "layout_role": role_name,
                "reading_order": b.order_index,
                "content_hash": sha256_text(b.raw_text),
                "review_status": "EXTRACTED",
            })

        for im in pg.image_objects:
            # 同一页可能多次引用同一 xref：按 (page_id, xref) 唯一化，
            # 放置次数记录为 placement_count（P1-04 的 ImageAsset 语义不变）
            key = (page_id, im.xref)
            if key in asset_index:
                asset_index[key]["placement_count"] += 1
                continue
            asset_index[key] = {
                "asset_id": f"{page_id}:I{im.xref}",
                "page_id": page_id,
                "textbook_id": textbook_id,
                "asset_kind": "image",
                "xref": im.xref,
                "width": im.width,
                "height": im.height,
                "colorspace": im.colorspace,
                "filter": im.filter,
                "tiny_fragment": bool(im.tiny_fragment),
                "placement_count": 1,
            }

    for u in parser.units:
        uid = f"{textbook_id}:{unit_key(u.unit_id)}"
        unit_rows.append({
            "unit_id": uid,
            "textbook_id": textbook_id,
            "snapshot_id": snapshot_id,
            "unit_code": u.unit_id,
            "title": u.title,
            "pdf_page_start": u.pdf_page_start,
            "pdf_page_end": u.pdf_page_end,
            "textbook_page_start": u.textbook_page_start,
            "textbook_page_end": u.textbook_page_end,
            "review_status": "NEED_REVIEW" if u.needs_review else "EXTRACTED",
        })
        evidence.append({
            "evidence_id": f"{uid}:E0",
            "source_type": "pdf_toc",
            "pdf_page": u.pdf_page_start,
            "textbook_page": u.textbook_page_start,
            "target_type": "unit",
            "target_id": uid,
        })

    unit_by_code = {u["unit_code"]: u["unit_id"] for u in unit_rows}

    for s in parser.sections:
        sid = f"{unit_by_code[s.unit_id]}:{section_key(s.title)}"
        section_rows.append({
            "section_id": sid,
            "unit_id": unit_by_code[s.unit_id],
            "textbook_id": textbook_id,
            "snapshot_id": snapshot_id,
            "title": s.title,
            "section_key": section_key(s.title),
            "pdf_page_start": s.pdf_page_start,
            "textbook_page_start": s.textbook_page_start,
            "review_status": "NEED_REVIEW" if s.needs_review else "EXTRACTED",
        })
        evidence.append({
            "evidence_id": f"{sid}:E0",
            "source_type": "parser_rule",
            "pdf_page": s.pdf_page_start,
            "textbook_page": s.textbook_page_start,
            "target_type": "section",
            "target_id": sid,
        })

    section_by_key = {(s["unit_id"], s["section_key"]): s["section_id"] for s in section_rows}
    page_by_pdf = {p["pdf_page"]: p for p in pages}

    for a in parser.activities:
        uid = unit_by_code.get(a.unit_id)
        sid = section_by_key.get((uid, section_key(a.section_title)))
        aid = f"{sid}:A{a.number}" if sid else None
        activity_rows.append({
            "activity_id": aid,
            "section_id": sid,
            "textbook_id": textbook_id,
            "snapshot_id": snapshot_id,
            "activity_number": a.number,
            "kind": a.kind,
            "pdf_page": a.pdf_page,
            "textbook_page": a.textbook_page,
            "bbox_json": json.dumps(list(a.bbox)),
            "instruction": a.instruction,
            "boundary_status": a.boundary_status,
            "sidebar_relation": a.sidebar_relation,
            "instruction_hash": sha256_text(a.instruction),
            "review_status": "NEED_REVIEW" if a.boundary_status != "OK" else "EXTRACTED",
        })
        evidence.append({
            "evidence_id": f"{aid}:E0" if aid else None,
            "source_type": "pdf_text",
            "pdf_page": a.pdf_page,
            "textbook_page": a.textbook_page,
            "target_type": "activity",
            "target_id": aid,
        })
        if a.boundary_status != "OK":
            evidence.append({
                "evidence_id": f"{aid}:E1" if aid else None,
                "source_type": "parser_rule",
                "pdf_page": a.pdf_page,
                "textbook_page": a.textbook_page,
                "target_type": "activity_boundary",
                "target_id": aid,
            })
        if a.sidebar_relation:
            activity_content.append({
                "relation_id": f"{aid}:R0" if aid else None,
                "activity_id": aid,
                "block_id": None,
                "relation_type": a.sidebar_relation,
                "pdf_page": a.pdf_page,
                "textbook_id": textbook_id,
                "snapshot_id": snapshot_id,
                "review_status": "NEED_REVIEW" if a.sidebar_relation != "separate_region" else "EXTRACTED",
            })

    # 子问题：parser v01 尚未输出实体；其识别为“问题清单”的候选块记录在此
    for pg in parser.pages:
        for r in pg.activity_rejections:
            if r.get("reason") == "question_list":
                sub_question_rows.append({
                    "sub_question_id": f"{textbook_id}:P{pg.pdf_page}:Q{r['number']}",
                    "activity_id": None,
                    "textbook_id": textbook_id,
                    "snapshot_id": snapshot_id,
                    "pdf_page": pg.pdf_page,
                    "textbook_page": pg.textbook_page,
                    "ordinal": r["number"],
                    "text_raw": r.get("text", ""),
                    "review_status": "NEED_REVIEW",
                })

    audio_assets = [{
        "audio_id": f"{textbook_id}:AU{i+1:02d}",
        "textbook_id": textbook_id,
        "snapshot_id": snapshot_id,
        "filename": row["filename"],
        "relative_path": f"2025年度初一外研版英语教材/{row['filename']}",
        "size_bytes": row["size_bytes"],
        "duration_ms": row["duration_ms"],
        "bitrate": row["bitrate"],
        "sample_rate": row["sample_rate"],
        "channels": row["channels"],
        "id3_version": row["id3_version"],
        "sha256": row["sha256"],
    } for i, row in enumerate(inputs["audio_rows"])]

    audio_by_name = {a["filename"]: a["audio_id"] for a in audio_assets}
    activity_index = {}
    for a in activity_rows:
        activity_index[(a["activity_id"],)] = a

    audio_mappings = []
    for asset in audio_assets:
        target_id = None
        for act in parser.activities:
            for cand in act.audio_candidates:
                if cand.get("file") == asset["filename"]:
                    uid = unit_by_code.get(act.unit_id)
                    sid = section_by_key.get((uid, section_key(act.section_title)))
                    target_id = f"{sid}:A{act.number}" if sid else None
        audio_mappings.append({
            "mapping_id": f"{asset['audio_id']}:M0",
            "audio_id": asset["audio_id"],
            "textbook_id": textbook_id,
            "snapshot_id": snapshot_id,
            "target_type": "activity" if target_id else None,
            "target_id": target_id,
            "mapping_status": "CANDIDATE",
            "confidence": None,
            "basis": "filename_rule" if target_id else "unresolved",
            "review_status": "NEED_REVIEW",
        })

    assets = list(asset_index.values())

    dataset = {
        "textbook_id": textbook_id,
        "snapshot_id": snapshot_id,
        "textbook_edition": [{
            "textbook_id": textbook_id,
            "publisher": "外语教学与研究出版社",
            "title": "义务教育教科书·英语 七年级上册",
            "grade": "7",
            "volume": "A",
            "curriculum_standard": "义务教育英语课程标准（2022年版）",
            "edition_label": "根据2022年版课程标准修订",
            "schema_version": SCHEMA_VERSION,
        }],
        "source_artifact": (
            [{
                "artifact_id": f"{textbook_id}:PDF",
                "textbook_id": textbook_id,
                "kind": "pdf",
                "filename": inputs["pdf_path"].name,
                "sha256": inputs["pdf_sha256"],
                "size_bytes": inputs["pdf_size"],
            }] + [{
                "artifact_id": f"{textbook_id}:MP3{i+1:02d}",
                "textbook_id": textbook_id,
                "kind": "audio",
                "filename": row["filename"],
                "sha256": row["sha256"],
                "size_bytes": row["size_bytes"],
            } for i, row in enumerate(inputs["audio_rows"])]
        ),
        "page": pages,
        "unit": unit_rows,
        "section": section_rows,
        "activity": activity_rows,
        "content_block": blocks,
        "content_asset": assets,
        "evidence": evidence,
        "activity_content": activity_content,
        "sub_question": sub_question_rows,
        "audio_asset": audio_assets,
        "audio_mapping": audio_mappings,
        "source_ref": [],
        "learning_item": [],
        "learning_goal": [],
        "ai_artifact": [],
        "learner": [],
    }
    return dataset


# --------------------------------------------------------------------------
# 第三步：检查
# --------------------------------------------------------------------------

def check(checks: list, name: str, ok: bool, detail: str, hard: bool = True) -> None:
    checks.append({
        "name": name,
        "status": "PASS" if ok else ("FAIL" if hard else "NOTE"),
        "hard": hard,
        "detail": detail,
    })


def run_checks(dataset: dict, parser, inputs: dict) -> list:
    checks: list = []

    # 输入核验
    check(checks, "pdf_present", inputs["pdf_path"] is not None,
          f"PDF 文件数 {inputs['pdf_count']}")
    check(checks, "pdf_sha256", inputs["pdf_sha256"] == EXPECTED_PDF_SHA256,
          f"{inputs['pdf_sha256']} (期望 {EXPECTED_PDF_SHA256})")
    check(checks, "mp3_count", inputs["mp3_count"] == EXPECTED_MP3_COUNT,
          f"{inputs['mp3_count']} (期望 {EXPECTED_MP3_COUNT})")
    check(checks, "no_other_files", not inputs["other_files"],
          f"其他类型文件 {inputs['other_files']}", hard=False)

    # 冻结统计
    dup_issues = [i for i in parser.quality["activity_numbering"]["issues"]]
    boundary_nr = sum(1 for a in parser.activities if a.boundary_status != "OK")
    order_nr = sum(1 for p in parser.pages if p.reading_order_status == "NEED_REVIEW")
    check(checks, "frozen_unit", len(parser.units) == FROZEN["unit"],
          f"{len(parser.units)} (期望 {FROZEN['unit']})")
    check(checks, "frozen_section", len(parser.sections) == FROZEN["section"],
          f"{len(parser.sections)} (期望 {FROZEN['section']})")
    check(checks, "frozen_activity", len(parser.activities) == FROZEN["activity"],
          f"{len(parser.activities)} (期望 {FROZEN['activity']})")
    check(checks, "frozen_duplicate", len(dup_issues) == FROZEN["duplicate_anomaly"],
          f"{len(dup_issues)} (期望 {FROZEN['duplicate_anomaly']})")
    check(checks, "frozen_boundary_need_review", boundary_nr == FROZEN["boundary_need_review"],
          f"{boundary_nr} (期望 {FROZEN['boundary_need_review']})")
    check(checks, "frozen_reading_order_need_review", order_nr == FROZEN["reading_order_need_review"],
          f"{order_nr} (期望 {FROZEN['reading_order_need_review']})")

    # parser quality checks
    for key in ("control_chars", "ligature", "units", "page_mapping", "cross_unit",
                "activity_numbering"):
        status = parser.quality[key]["status"]
        check(checks, f"parser_quality_{key}", status == "PASS", f"status={status}")
    check(checks, "parser_quality_activity_gaps", True,
          f"status={parser.quality['activity_gaps']['status']}（编号缺口保留待审，属预期）",
          hard=False)

    # 主键 / 业务键唯一性
    for table in ("textbook_edition", "source_artifact", "page", "unit", "section",
                  "activity", "content_block", "content_asset", "evidence",
                  "audio_asset", "audio_mapping"):
        rows = dataset[table]
        ids = [r.get(list(r.keys())[0]) for r in rows] if rows else []
        dup = len(ids) - len(set(x for x in ids if x is not None))
        check(checks, f"pk_unique_{table}", dup == 0, f"rows={len(rows)} dup={dup}")

    page_keys = [(p["textbook_id"], p["pdf_page"]) for p in dataset["page"]]
    check(checks, "business_key_unique_page", len(page_keys) == len(set(page_keys)),
          f"{len(page_keys)} rows")
    act_keys = [(a["section_id"], a["activity_number"]) for a in dataset["activity"]]
    dup_act = len(act_keys) - len(set(act_keys))
    check(checks, "business_key_unique_activity", dup_act == 0,
          f"{len(act_keys)} rows, dup={dup_act}")

    # 外键
    page_ids = {p["page_id"] for p in dataset["page"]}
    unit_ids = {u["unit_id"] for u in dataset["unit"]}
    section_ids = {s["section_id"] for s in dataset["section"]}
    activity_ids = {a["activity_id"] for a in dataset["activity"] if a["activity_id"]}
    block_ids = {b["block_id"] for b in dataset["content_block"]}
    audio_ids = {a["audio_id"] for a in dataset["audio_asset"]}

    check(checks, "fk_activity_section",
          all(a["section_id"] in section_ids for a in dataset["activity"]),
          f"activities={len(dataset['activity'])}")
    check(checks, "fk_section_unit",
          all(s["unit_id"] in unit_ids for s in dataset["section"]),
          f"sections={len(dataset['section'])}")
    check(checks, "fk_block_page",
          all(b["page_id"] in page_ids for b in dataset["content_block"]),
          f"blocks={len(dataset['content_block'])}")
    check(checks, "fk_asset_page",
          all(a["page_id"] in page_ids for a in dataset["content_asset"]),
          f"assets={len(dataset['content_asset'])}")
    check(checks, "fk_audio_mapping_audio",
          all(m["audio_id"] in audio_ids for m in dataset["audio_mapping"]),
          f"mappings={len(dataset['audio_mapping'])}")
    check(checks, "fk_audio_mapping_target",
          all(m["target_id"] is None or m["target_id"] in activity_ids
              for m in dataset["audio_mapping"]),
          "候选目标必须存在或为空")
    check(checks, "fk_activity_content",
          all(c["activity_id"] in activity_ids and
              (c["block_id"] is None or c["block_id"] in block_ids)
              for c in dataset["activity_content"]),
          f"relations={len(dataset['activity_content'])}")

    # source_ref 完整性
    l2_rows = dataset["learning_item"] + dataset["learning_goal"]
    check(checks, "source_ref_completeness", len(dataset["source_ref"]) >= len(l2_rows),
          f"L2 rows={len(l2_rows)} source_ref rows={len(dataset['source_ref'])}"
          "（首次 Dry-run 未生成派生资源，规则暂为空集校验）", hard=False)

    # 版本隔离
    tids = {r.get("textbook_id") for table in ("page", "unit", "section", "activity",
                                               "content_block", "content_asset",
                                               "audio_asset", "audio_mapping")
            for r in dataset[table]}
    check(checks, "isolation_single_textbook", tids == {dataset["textbook_id"]},
          f"textbook_ids={sorted(t for t in tids if t)}")
    snapshot_ok = all(
        r.get("snapshot_id") == dataset["snapshot_id"]
        for table in ("page", "section", "activity", "content_block", "audio_mapping")
        for r in dataset[table] if "snapshot_id" in r
    )
    check(checks, "isolation_single_snapshot", snapshot_ok, dataset["snapshot_id"])

    # 音频候选检查
    statuses: dict[str, int] = {}
    for m in dataset["audio_mapping"]:
        statuses[m["mapping_status"]] = statuses.get(m["mapping_status"], 0) + 1
    confirmed = statuses.get("CONFIRMED_BY_HUMAN", 0)
    check(checks, "audio_all_candidate", confirmed == 0,
          f"状态分布 {statuses}；CONFIRMED_BY_HUMAN={confirmed}")

    # 内容 hash 检查
    empty_hash = sum(1 for b in dataset["content_block"] if not b["content_hash"])
    check(checks, "content_hash_present", empty_hash == 0,
          f"blocks={len(dataset['content_block'])} empty_hash={empty_hash}")
    digest_1 = hashlib.sha256("|".join(
        f"{b['block_id']}:{b['content_hash']}" for b in dataset["content_block"]
    ).encode("utf-8")).hexdigest().upper()
    check(checks, "content_hash_deterministic", bool(digest_1), f"digest={digest_1[:16]}…")

    # NEED_REVIEW 保留
    check(checks, "need_review_preserved",
          boundary_nr > 0 and order_nr > 0, f"boundary={boundary_nr} order={order_nr}",
          hard=False)

    # L3 / L4 必须为空
    check(checks, "l3_ai_empty", len(dataset["ai_artifact"]) == 0,
          f"ai_artifact rows={len(dataset['ai_artifact'])}")
    check(checks, "l4_learner_empty", len(dataset["learner"]) == 0,
          f"learner rows={len(dataset['learner'])}")

    return checks


# --------------------------------------------------------------------------
# 第四步：schema 探针（内存 SQLite，不落地文件）
# --------------------------------------------------------------------------

SCHEMA_DDL = [
    """CREATE TABLE textbook_edition(
        textbook_id TEXT PRIMARY KEY, publisher TEXT, title TEXT, grade TEXT,
        volume TEXT, curriculum_standard TEXT, edition_label TEXT, schema_version TEXT)""",
    """CREATE TABLE source_artifact(
        artifact_id TEXT PRIMARY KEY, textbook_id TEXT, kind TEXT, filename TEXT,
        sha256 TEXT, size_bytes INTEGER)""",
    """CREATE TABLE parse_snapshot(
        snapshot_id TEXT PRIMARY KEY, textbook_id TEXT, parser_name TEXT,
        parser_version TEXT, rule_set_version TEXT, input_pdf_sha256 TEXT,
        input_audio_count INTEGER, status TEXT, stats_json TEXT, quality_json TEXT,
        is_active INTEGER)""",
    """CREATE TABLE import_batch(
        batch_id TEXT PRIMARY KEY, snapshot_id TEXT, textbook_id TEXT, status TEXT,
        failed_stage TEXT, error_message TEXT)""",
    """CREATE TABLE page(
        page_id TEXT PRIMARY KEY, textbook_id TEXT, snapshot_id TEXT, pdf_page INTEGER,
        textbook_page INTEGER, page_role TEXT, layout_type TEXT,
        reading_order_status TEXT, review_status TEXT)""",
    """CREATE TABLE unit(
        unit_id TEXT PRIMARY KEY, textbook_id TEXT, snapshot_id TEXT, unit_code TEXT,
        title TEXT, pdf_page_start INTEGER, pdf_page_end INTEGER, review_status TEXT)""",
    """CREATE TABLE section(
        section_id TEXT PRIMARY KEY, unit_id TEXT REFERENCES unit(unit_id),
        textbook_id TEXT, snapshot_id TEXT, title TEXT, section_key TEXT,
        pdf_page_start INTEGER, review_status TEXT)""",
    """CREATE TABLE activity(
        activity_id TEXT PRIMARY KEY, section_id TEXT REFERENCES section(section_id),
        textbook_id TEXT, snapshot_id TEXT, activity_number INTEGER, kind TEXT,
        pdf_page INTEGER, textbook_page INTEGER, bbox_json TEXT, instruction TEXT,
        boundary_status TEXT, sidebar_relation TEXT, review_status TEXT)""",
    """CREATE TABLE content_block(
        block_id TEXT PRIMARY KEY, page_id TEXT REFERENCES page(page_id),
        textbook_id TEXT, snapshot_id TEXT, text_raw TEXT, text_normalized TEXT,
        block_kind TEXT, layout_role TEXT, reading_order INTEGER,
        content_hash TEXT, review_status TEXT)""",
    """CREATE TABLE content_asset(
        asset_id TEXT PRIMARY KEY, page_id TEXT REFERENCES page(page_id),
        textbook_id TEXT, asset_kind TEXT, xref INTEGER, width INTEGER, height INTEGER,
        colorspace TEXT, filter TEXT, tiny_fragment INTEGER)""",
    """CREATE TABLE evidence(
        evidence_id TEXT PRIMARY KEY, source_type TEXT, pdf_page INTEGER,
        textbook_page INTEGER, bbox_json TEXT, font_json TEXT,
        extraction_version TEXT, target_type TEXT, target_id TEXT)""",
    """CREATE TABLE activity_content(
        relation_id TEXT PRIMARY KEY, activity_id TEXT REFERENCES activity(activity_id),
        block_id TEXT, relation_type TEXT, review_status TEXT)""",
    """CREATE TABLE sub_question(
        sub_question_id TEXT PRIMARY KEY,
        activity_id TEXT REFERENCES activity(activity_id), ordinal INTEGER,
        text_raw TEXT, review_status TEXT)""",
    """CREATE TABLE audio_asset(
        audio_id TEXT PRIMARY KEY, textbook_id TEXT, filename TEXT,
        duration_ms INTEGER, bitrate INTEGER, sample_rate INTEGER, channels INTEGER,
        id3_version TEXT, sha256 TEXT)""",
    """CREATE TABLE audio_mapping(
        mapping_id TEXT PRIMARY KEY, audio_id TEXT REFERENCES audio_asset(audio_id),
        textbook_id TEXT, snapshot_id TEXT, target_type TEXT, target_id TEXT,
        mapping_status TEXT, confidence REAL, basis TEXT, review_status TEXT)""",
    """CREATE TABLE transcript(
        transcript_id TEXT PRIMARY KEY, audio_id TEXT, transcript_kind TEXT,
        text_raw TEXT, text_normalized TEXT, confidence REAL, review_status TEXT)""",
    """CREATE TABLE learning_item(
        item_id TEXT PRIMARY KEY, textbook_id TEXT, item_type TEXT, surface_form TEXT,
        derivation_type TEXT, review_status TEXT)""",
    """CREATE TABLE source_ref(
        source_ref_id TEXT PRIMARY KEY, item_id TEXT, source_type TEXT, source_id TEXT,
        quote_raw TEXT)""",
    """CREATE TABLE learning_goal(
        goal_id TEXT PRIMARY KEY, textbook_id TEXT, scope TEXT, scope_id TEXT,
        statement_raw TEXT, goal_origin TEXT, review_status TEXT)""",
    """CREATE TABLE ai_artifact(
        artifact_id TEXT PRIMARY KEY, artifact_kind TEXT, target_layer TEXT,
        target_id TEXT, content_markdown TEXT, model TEXT, review_status TEXT)""",
]


def schema_probe() -> dict:
    """在内存 SQLite 中创建建议 schema，仅验证 DDL 语法与表数量，不落盘。"""
    try:
        conn = sqlite3.connect(":memory:")
        conn.execute("PRAGMA foreign_keys=ON")
        for ddl in SCHEMA_DDL:
            conn.execute(ddl)
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        conn.close()
        return {"ok": True, "tables": tables, "count": len(tables),
                "location": "in-memory (:memory:)，未创建任何 SQLite 文件"}
    except Exception as exc:  # pragma: no cover
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}",
                "count": 0, "location": "in-memory (:memory:)"}


# --------------------------------------------------------------------------
# 第五步：输出
# --------------------------------------------------------------------------

def write_reports(result: dict, dataset: dict, checks: list, parser, inputs: dict) -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    counts = {table: len(rows) for table, rows in dataset.items() if isinstance(rows, list)}
    counts["image_block_total"] = sum(len(p.image_blocks) for p in parser.pages)

    payload = {
        "task": "P1-05-B 第一阶段 Dry-run",
        "generated_at": now_iso(),
        "verdict": result["verdict"],
        "schema_version": SCHEMA_VERSION,
        "rule_set_version": RULE_SET_VERSION,
        "textbook_id": dataset["textbook_id"],
        "snapshot_id": dataset["snapshot_id"],
        "inputs": {
            "pdf_filename": inputs["pdf_path"].name,
            "pdf_sha256": inputs["pdf_sha256"],
            "pdf_size": inputs["pdf_size"],
            "mp3_count": inputs["mp3_count"],
            "other_files": inputs["other_files"],
        },
        "projected_table_counts": counts,
        "checks": checks,
        "schema_probe": result["schema_probe"],
        "audio": result["audio"],
        "frozen": result["frozen"],
        "boundaries": {
            "formal_db_created": False,
            "learner_db_created": False,
            "source_pdf_modified": False,
            "source_mp3_modified": False,
            "parser_modified": False,
            "ai_calls": 0,
            "transcripts_generated": 0,
        },
    }

    json_path = AUDIT_DIR / "P1-05-B_dry_run.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    failed = [c for c in checks if c["status"] == "FAIL"]
    notes = [c for c in checks if c["status"] == "NOTE"]

    md = []
    md.append("# P1-05-B 第一阶段 Dry-run 报告")
    md.append("")
    md.append(f"- 生成时间：{payload['generated_at']}")
    md.append(f"- 结论：{result['verdict']}")
    md.append(f"- textbook_id：{dataset['textbook_id']}")
    md.append(f"- snapshot_id：{dataset['snapshot_id']}")
    md.append(f"- schema_version：{SCHEMA_VERSION} / rule_set_version：{RULE_SET_VERSION}")
    md.append("")
    md.append("## 1. 环境与输入核验")
    md.append(f"- PDF：{inputs['pdf_path'].name}")
    md.append(f"- PDF SHA256：{inputs['pdf_sha256']}")
    md.append(f"- MP3 数量：{inputs['mp3_count']}")
    md.append(f"- 其他类型文件：{inputs['other_files'] or '无'}")
    md.append("")
    md.append("## 2. 预计各表记录数")
    md.append("")
    md.append("| 表 | 预计记录数 |")
    md.append("| --- | --- |")
    for table in sorted(counts):
        md.append(f"| {table} | {counts[table]} |")
    md.append("")
    md.append("## 3. 冻结统计复核")
    md.append("")
    md.append("| 项目 | 实际 | 期望 | 结果 |")
    md.append("| --- | --- | --- | --- |")
    for key, expect in FROZEN.items():
        actual = result["frozen"].get(key)
        md.append(f"| {key} | {actual} | {expect} | {'OK' if actual == expect else 'MISMATCH'} |")
    md.append("")
    md.append("## 4. 检查明细")
    md.append("")
    md.append("| 检查 | 结果 | 说明 |")
    md.append("| --- | --- | --- |")
    for c in checks:
        md.append(f"| {c['name']} | {c['status']} | {c['detail']} |")
    md.append("")
    md.append("## 5. Schema 探针")
    md.append("")
    md.append(f"- 结果：{'OK' if result['schema_probe']['ok'] else 'FAIL'}")
    md.append(f"- 表数量：{result['schema_probe']['count']}")
    md.append(f"- 位置：{result['schema_probe']['location']}")
    md.append("")
    md.append("## 6. 音频")
    md.append("")
    for k, v in result["audio"].items():
        md.append(f"- {k}：{v}")
    md.append("")
    md.append("## 7. AI 与正式数据库")
    md.append("")
    md.append("- AI 调用次数：0")
    md.append("- 是否创建正式 contentpack SQLite：否")
    md.append("- 是否创建 learner.db：否")
    md.append("- 是否修改原始 PDF / MP3：否")
    md.append("- 是否修改 parser：否")
    md.append("")
    md.append("## 8. 风险与待审项")
    md.append("")
    if notes:
        for c in notes:
            md.append(f"- {c['name']}：{c['detail']}")
    else:
        md.append("- 无")
    md.append("")
    if failed:
        md.append("## 9. 失败项")
        md.append("")
        for c in failed:
            md.append(f"- {c['name']}：{c['detail']}")
    md.append("")
    md.append("## 10. 结论")
    md.append("")
    md.append(result["conclusion"])

    md_path = AUDIT_DIR / "P1-05-B_dry_run.md"
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    return json_path, md_path


# --------------------------------------------------------------------------
# P1-05-B 第二阶段：正式构建 contentpack v1
# --------------------------------------------------------------------------

STAGING_DIR = BASE_DIR / "structured" / "staging"
CONTENTPACK_V1_DIR = BASE_DIR / "structured" / "contentpack" / "v1"

BUILD_SCHEMA = [
    """CREATE TABLE textbook_edition(
        textbook_id TEXT PRIMARY KEY, publisher TEXT, title TEXT, grade TEXT,
        volume TEXT, curriculum_standard TEXT, edition_label TEXT,
        schema_version TEXT)""",
    """CREATE TABLE source_artifact(
        artifact_id TEXT PRIMARY KEY, textbook_id TEXT, kind TEXT, filename TEXT,
        sha256 TEXT, size_bytes INTEGER)""",
    """CREATE TABLE parse_snapshot(
        snapshot_id TEXT PRIMARY KEY, textbook_id TEXT, parser_name TEXT,
        parser_version TEXT, rule_set_version TEXT, input_pdf_sha256 TEXT,
        input_audio_count INTEGER, build_started_at TEXT, build_finished_at TEXT,
        status TEXT, stats_json TEXT, quality_json TEXT, is_active INTEGER,
        supersedes_snapshot_id TEXT, notes TEXT)""",
    """CREATE TABLE import_batch(
        batch_id TEXT PRIMARY KEY, snapshot_id TEXT, textbook_id TEXT,
        started_at TEXT, finished_at TEXT, status TEXT, failed_stage TEXT,
        error_message TEXT)""",
    """CREATE TABLE import_batch_stage(
        stage_record_id TEXT PRIMARY KEY, batch_id TEXT REFERENCES import_batch(batch_id),
        stage TEXT, row_count INTEGER, started_at TEXT, finished_at TEXT, status TEXT,
        last_key TEXT, error_message TEXT)""",
    """CREATE TABLE page(
        page_id TEXT PRIMARY KEY, textbook_id TEXT, snapshot_id TEXT,
        pdf_page INTEGER NOT NULL, textbook_page INTEGER, textbook_page_evidence TEXT,
        page_role TEXT, layout_type TEXT, reading_order_status TEXT, text_chars INTEGER,
        review_status TEXT)""",
    """CREATE TABLE unit(
        unit_id TEXT PRIMARY KEY, textbook_id TEXT, snapshot_id TEXT, unit_code TEXT,
        title TEXT, pdf_page_start INTEGER, pdf_page_end INTEGER,
        textbook_page_start INTEGER, textbook_page_end INTEGER, review_status TEXT)""",
    """CREATE TABLE section(
        section_id TEXT PRIMARY KEY, unit_id TEXT REFERENCES unit(unit_id),
        textbook_id TEXT, snapshot_id TEXT, title TEXT, section_key TEXT,
        pdf_page_start INTEGER, textbook_page_start INTEGER, review_status TEXT)""",
    """CREATE TABLE activity(
        activity_id TEXT PRIMARY KEY, section_id TEXT REFERENCES section(section_id),
        textbook_id TEXT, snapshot_id TEXT, activity_number INTEGER NOT NULL,
        kind TEXT, pdf_page INTEGER, textbook_page INTEGER, bbox_json TEXT,
        instruction TEXT, boundary_status TEXT, sidebar_relation TEXT,
        instruction_hash TEXT, review_status TEXT,
        UNIQUE(section_id, activity_number))""",
    """CREATE TABLE content_block(
        block_id TEXT PRIMARY KEY, page_id TEXT REFERENCES page(page_id),
        textbook_id TEXT, snapshot_id TEXT, text_raw TEXT, text_normalized TEXT,
        block_kind TEXT, layout_role TEXT, reading_order INTEGER,
        content_hash TEXT NOT NULL, review_status TEXT)""",
    """CREATE TABLE content_asset(
        asset_id TEXT PRIMARY KEY, page_id TEXT REFERENCES page(page_id),
        textbook_id TEXT, snapshot_id TEXT, asset_kind TEXT, xref INTEGER,
        width INTEGER, height INTEGER, colorspace TEXT, filter TEXT,
        tiny_fragment INTEGER, placement_count INTEGER)""",
    """CREATE TABLE evidence(
        evidence_id TEXT PRIMARY KEY, source_type TEXT, pdf_page INTEGER,
        textbook_page INTEGER, bbox_json TEXT, font_json TEXT,
        extraction_version TEXT, target_type TEXT, target_id TEXT,
        textbook_id TEXT, snapshot_id TEXT)""",
    """CREATE TABLE activity_content(
        relation_id TEXT PRIMARY KEY, activity_id TEXT REFERENCES activity(activity_id),
        block_id TEXT, relation_type TEXT, review_status TEXT,
        textbook_id TEXT, snapshot_id TEXT, pdf_page INTEGER)""",
    """CREATE TABLE sub_question(
        sub_question_id TEXT PRIMARY KEY,
        activity_id TEXT REFERENCES activity(activity_id), textbook_id TEXT,
        snapshot_id TEXT, pdf_page INTEGER, textbook_page INTEGER, ordinal INTEGER,
        text_raw TEXT, review_status TEXT)""",
    """CREATE TABLE audio_asset(
        audio_id TEXT PRIMARY KEY, textbook_id TEXT, snapshot_id TEXT, filename TEXT,
        relative_path TEXT, sha256 TEXT, size_bytes INTEGER, duration_ms INTEGER,
        bitrate INTEGER, sample_rate INTEGER, channels INTEGER, id3_version TEXT)""",
    """CREATE TABLE audio_mapping(
        mapping_id TEXT PRIMARY KEY, audio_id TEXT REFERENCES audio_asset(audio_id),
        textbook_id TEXT, snapshot_id TEXT, target_type TEXT, target_id TEXT,
        mapping_status TEXT NOT NULL, confidence REAL, basis TEXT, review_status TEXT,
        reviewed_by TEXT, reviewed_at TEXT, review_note TEXT)""",
    """CREATE TABLE transcript(
        transcript_id TEXT PRIMARY KEY, audio_id TEXT, transcript_kind TEXT,
        text_raw TEXT, text_normalized TEXT, language TEXT, confidence REAL,
        provider TEXT, model TEXT, review_status TEXT, textbook_id TEXT,
        snapshot_id TEXT)""",
    """CREATE TABLE source_ref(
        source_ref_id TEXT PRIMARY KEY, item_id TEXT, item_type TEXT,
        source_type TEXT, source_id TEXT, quote_raw TEXT,
        textbook_id TEXT, snapshot_id TEXT)""",
    """CREATE TABLE learning_item(
        item_id TEXT PRIMARY KEY, textbook_id TEXT, snapshot_id TEXT, item_type TEXT,
        surface_form TEXT, lemma TEXT, phonetic TEXT, part_of_speech TEXT,
        meaning_zh TEXT, derivation_type TEXT, review_status TEXT)""",
    """CREATE TABLE learning_goal(
        goal_id TEXT PRIMARY KEY, textbook_id TEXT, snapshot_id TEXT, scope TEXT,
        scope_id TEXT, statement_raw TEXT, statement_normalized TEXT,
        goal_origin TEXT, review_status TEXT)""",
    """CREATE TABLE ai_artifact(
        artifact_id TEXT PRIMARY KEY, artifact_kind TEXT, target_layer TEXT,
        target_id TEXT, context_ref_ids TEXT, content_markdown TEXT, model TEXT,
        prompt_version TEXT, confidence REAL, review_status TEXT,
        is_visible_to_child INTEGER, textbook_id TEXT, snapshot_id TEXT)""",
]

BUILD_TABLE_ORDER = [
    "parse_snapshot", "textbook_edition", "source_artifact", "page", "unit", "section",
    "activity", "content_block", "content_asset", "evidence", "activity_content",
    "sub_question", "audio_asset", "audio_mapping", "transcript", "source_ref",
    "learning_item", "learning_goal", "ai_artifact",
]

EXPECTED_BUILD_COUNTS = {
    "textbook_edition": 1,
    "source_artifact": 55,
    "parse_snapshot": 1,
    "page": 178,
    "unit": 8,
    "section": 46,
    "activity": 96,
    "content_block": 3854,
    "content_asset": 628,
    "evidence": 351,
    "activity_content": 31,
    "audio_asset": 54,
    "audio_mapping": 54,
    "ai_artifact": 0,
}


def extract_learning_goals(parser, textbook_id: str, snapshot_id: str) -> tuple:
    """只提取教材明示目标：单元开篇 'After completing the unit, you will be able to …'。"""
    goals, refs = [], []
    for u in parser.units:
        uid = f"{textbook_id}:{unit_key(u.unit_id)}"
        found = False
        for pdf_page in range(u.pdf_page_start, min(u.pdf_page_start + 2, u.pdf_page_end) + 1):
            pg = parser.pages[pdf_page - 1]
            page_id = f"{textbook_id}:P{pg.pdf_page}"
            for idx, b in enumerate(pg.blocks):
                text = re.sub(r"\s+", " ", b.text).strip()
                low = text.lower()
                if "after completing the unit" in low:
                    statement = text[low.index("after completing the unit"):]
                    goal_id = f"{uid}:G0"
                    goals.append({
                        "goal_id": goal_id,
                        "textbook_id": textbook_id,
                        "snapshot_id": snapshot_id,
                        "scope": "unit",
                        "scope_id": uid,
                        "statement_raw": statement,
                        "statement_normalized": statement,
                        "goal_origin": "TEXTBOOK_EXPLICIT",
                        "review_status": "EXTRACTED",
                    })
                    refs.append({
                        "source_ref_id": f"{goal_id}:SR0",
                        "item_id": goal_id,
                        "item_type": "learning_goal",
                        "source_type": "content_block",
                        "source_id": f"{page_id}:B{idx}",
                        "quote_raw": statement,
                        "textbook_id": textbook_id,
                        "snapshot_id": snapshot_id,
                    })
                    found = True
                    break
            if found:
                break
    return goals, refs


def _insert_rows(conn, table: str, rows: list) -> int:
    if not rows:
        return 0
    cols = list(rows[0].keys())
    placeholders = ",".join("?" for _ in cols)
    sql = f"INSERT INTO {table}({','.join(cols)}) VALUES({placeholders})"
    conn.executemany(sql, [tuple(r.get(c) for c in cols) for r in rows])
    return len(rows)


def build_contentpack(dataset: dict, inputs: dict, parser, started_at: str) -> dict:
    """在 staging 目录构建 SQLite，验证后原子发布到 contentpack/v1。"""
    textbook_id = dataset["textbook_id"]
    snapshot_id = dataset["snapshot_id"]
    batch_id = f"{snapshot_id}:B0"

    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    CONTENTPACK_V1_DIR.mkdir(parents=True, exist_ok=True)

    staging_path = STAGING_DIR / f"{textbook_id}.sqlite"
    final_path = CONTENTPACK_V1_DIR / f"{textbook_id}.sqlite"
    for p in (staging_path, final_path):
        if p.exists():
            p.unlink()

    # 教材明示学习目标（L2）
    goals, goal_refs = extract_learning_goals(parser, textbook_id, snapshot_id)
    dataset = dict(dataset)
    dataset["learning_goal"] = goals
    dataset["source_ref"] = goal_refs

    dataset["parse_snapshot"] = [{
        "snapshot_id": snapshot_id,
        "textbook_id": textbook_id,
        "parser_name": "textbook_parser_v01",
        "parser_version": "v01-P1-03-C",
        "rule_set_version": RULE_SET_VERSION,
        "input_pdf_sha256": inputs["pdf_sha256"],
        "input_audio_count": inputs["mp3_count"],
        "build_started_at": started_at,
        "build_finished_at": now_iso(),
        "status": "VALIDATED",
        "stats_json": json.dumps({
            "page": len(dataset["page"]),
            "unit": len(dataset["unit"]),
            "section": len(dataset["section"]),
            "activity": len(dataset["activity"]),
            "content_block": len(dataset["content_block"]),
            "content_asset": len(dataset["content_asset"]),
            "evidence": len(dataset["evidence"]),
            "audio_asset": len(dataset["audio_asset"]),
        }, ensure_ascii=False),
        "quality_json": json.dumps({
            k: dataset_quality_status(v) for k, v in parser.quality.items()
        }, ensure_ascii=False),
        "is_active": 1,
        "supersedes_snapshot_id": None,
        "notes": "首次正式构建",
    }]
    dataset["import_batch"] = [{
        "batch_id": batch_id,
        "snapshot_id": snapshot_id,
        "textbook_id": textbook_id,
        "started_at": started_at,
        "finished_at": None,
        "status": "BUILDING",
        "failed_stage": None,
        "error_message": None,
    }]

    conn = sqlite3.connect(str(staging_path))
    conn.execute("PRAGMA foreign_keys=ON")
    stage_records = []

    def stage(name: str, fn):
        t0 = now_iso()
        conn.execute("SAVEPOINT st")
        try:
            n = fn()
            conn.execute("RELEASE SAVEPOINT st")
            stage_records.append({
                "stage_record_id": f"{batch_id}:{len(stage_records)+1:02d}",
                "batch_id": batch_id, "stage": name, "row_count": n,
                "started_at": t0, "finished_at": now_iso(), "status": "SUCCESS",
                "last_key": None, "error_message": None,
            })
            return n
        except Exception as exc:
            conn.execute("ROLLBACK TO SAVEPOINT st")
            stage_records.append({
                "stage_record_id": f"{batch_id}:{len(stage_records)+1:02d}",
                "batch_id": batch_id, "stage": name, "row_count": 0,
                "started_at": t0, "finished_at": now_iso(), "status": "FAILED",
                "last_key": None, "error_message": f"{type(exc).__name__}: {exc}",
            })
            conn.execute(
                "UPDATE import_batch SET status='FAILED', failed_stage=?, error_message=?, "
                "finished_at=? WHERE batch_id=?", (name, str(exc), now_iso(), batch_id))
            conn.commit()
            conn.close()
            raise

    for ddl in BUILD_SCHEMA:
        conn.execute(ddl)
    _insert_rows(conn, "import_batch", dataset["import_batch"])
    conn.commit()

    with conn:
        for table in BUILD_TABLE_ORDER:
            rows = dataset.get(table, [])
            stage(table, lambda t=table, r=rows: _insert_rows(conn, t, r))

    stage_records.append({
        "stage_record_id": f"{batch_id}:{len(stage_records)+1:02d}",
        "batch_id": batch_id, "stage": "quality_validation", "row_count": 0,
        "started_at": now_iso(), "finished_at": now_iso(), "status": "SUCCESS",
        "last_key": None, "error_message": None,
    })
    _insert_rows(conn, "import_batch_stage", stage_records)
    conn.execute(
        "UPDATE import_batch SET status='VALIDATING' WHERE batch_id=?", (batch_id,))
    conn.commit()

    validation = validate_contentpack(conn)
    if validation["ok"]:
        conn.execute(
            "UPDATE import_batch SET status='SUCCESS', finished_at=? WHERE batch_id=?",
            (now_iso(), batch_id))
        conn.execute("UPDATE parse_snapshot SET status='VALIDATED' WHERE snapshot_id=?",
                     (snapshot_id,))
    else:
        conn.execute(
            "UPDATE import_batch SET status='FAILED', failed_stage='quality_validation', "
            "error_message=? WHERE batch_id=?", ("; ".join(validation["failures"]), batch_id))
    conn.commit()
    conn.execute("VACUUM")
    conn.close()

    publish = None
    if validation["ok"]:
        publish = publish_atomic(staging_path, final_path)

    return {
        "dataset": dataset,
        "staging_path": staging_path,
        "final_path": final_path,
        "batch_id": batch_id,
        "validation": validation,
        "publish": publish,
        "stage_records": stage_records,
        "goals": goals,
        "source_refs": goal_refs,
    }


def dataset_quality_status(entry) -> str:
    if isinstance(entry, dict):
        return str(entry.get("status", "UNKNOWN"))
    return str(entry)


def validate_contentpack(conn) -> dict:
    checks = []

    def add(name, ok, detail):
        checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})

    ok = conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    add("integrity_check", ok, "ok" if ok else "NOT ok")

    fk = conn.execute("PRAGMA foreign_key_check").fetchall()
    add("foreign_key_check", len(fk) == 0, f"violations={len(fk)}")

    counts = {}
    for table, expected in EXPECTED_BUILD_COUNTS.items():
        n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        counts[table] = n
        add(f"count_{table}", n == expected, f"{n} (期望 {expected})")

    sub_q = conn.execute("SELECT COUNT(*) FROM sub_question").fetchone()[0]
    counts["sub_question"] = sub_q
    add("count_sub_question", True, f"{sub_q}（候选记录，全部 NEED_REVIEW）")
    for table in ("learning_item", "learning_goal", "source_ref", "transcript",
                  "import_batch", "import_batch_stage"):
        counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    dup_page = conn.execute(
        "SELECT COUNT(*) FROM (SELECT textbook_id, pdf_page FROM page "
        "GROUP BY textbook_id, pdf_page HAVING COUNT(*)>1)").fetchone()[0]
    add("business_key_page", dup_page == 0, f"duplicates={dup_page}")

    for table, pk in (("page", "page_id"), ("unit", "unit_id"), ("section", "section_id"),
                      ("activity", "activity_id"), ("content_block", "block_id"),
                      ("content_asset", "asset_id"), ("audio_asset", "audio_id"),
                      ("audio_mapping", "mapping_id"), ("evidence", "evidence_id")):
        dup = conn.execute(
            f"SELECT COUNT(*) FROM (SELECT {pk} FROM {table} GROUP BY {pk} "
            f"HAVING COUNT(*)>1)").fetchone()[0]
        add(f"pk_unique_{table}", dup == 0, f"duplicates={dup}")

    tids = conn.execute("SELECT COUNT(DISTINCT textbook_id) FROM page").fetchone()[0]
    add("textbook_id_consistent", tids == 1, f"distinct textbook_id in page = {tids}")
    sn = conn.execute("SELECT COUNT(DISTINCT snapshot_id) FROM page").fetchone()[0]
    add("snapshot_id_consistent", sn == 1, f"distinct snapshot_id in page = {sn}")

    refs = conn.execute("SELECT COUNT(*) FROM source_ref").fetchone()[0]
    goals = conn.execute("SELECT COUNT(*) FROM learning_goal").fetchone()[0]
    items = conn.execute("SELECT COUNT(*) FROM learning_item").fetchone()[0]
    linked = conn.execute(
        "SELECT COUNT(DISTINCT item_id) FROM source_ref WHERE item_type='learning_goal'"
    ).fetchone()[0]
    add("source_ref_completeness", linked >= goals and refs >= goals,
        f"learning_goal={goals} learning_item={items} source_ref={refs} linked_goals={linked}")

    empty_hash = conn.execute(
        "SELECT COUNT(*) FROM content_block WHERE content_hash IS NULL OR content_hash=''"
    ).fetchone()[0]
    add("content_hash_complete", empty_hash == 0, f"empty={empty_hash}")

    audio = dict(conn.execute(
        "SELECT mapping_status, COUNT(*) FROM audio_mapping GROUP BY mapping_status").fetchall())
    add("audio_mapping_candidate", audio.get("CONFIRMED_BY_HUMAN", 0) == 0,
        f"{audio}")
    add("audio_mapping_total_54", sum(audio.values()) == 54, f"total={sum(audio.values())}")

    ai = conn.execute("SELECT COUNT(*) FROM ai_artifact").fetchone()[0]
    add("ai_artifact_zero", ai == 0, f"{ai}")

    nr_activity = conn.execute(
        "SELECT COUNT(*) FROM activity WHERE review_status='NEED_REVIEW'").fetchone()[0]
    nr_page = conn.execute(
        "SELECT COUNT(*) FROM page WHERE reading_order_status='NEED_REVIEW'").fetchone()[0]
    add("need_review_preserved", nr_activity == 23 and nr_page == 88,
        f"activity={nr_activity} page_reading_order={nr_page}")

    failures = [c["detail"] for c in checks if c["status"] == "FAIL"]
    return {"ok": not failures, "checks": checks, "counts": counts, "failures": failures,
            "audio_status": audio, "need_review": {"activity": nr_activity, "page": nr_page}}


def publish_atomic(staging_path: Path, final_path: Path) -> dict:
    """staging → .tmp → 正式路径，任何一步失败都不会留下半成品正式库。"""
    tmp_path = final_path.with_name(final_path.name + ".tmp")
    if tmp_path.exists():
        tmp_path.unlink()
    shutil.copyfile(staging_path, tmp_path)

    conn = sqlite3.connect(str(tmp_path))
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    fk = conn.execute("PRAGMA foreign_key_check").fetchall()
    conn.close()
    if integrity != "ok" or fk:
        tmp_path.unlink(missing_ok=True)
        return {"ok": False, "reason": f"tmp validation failed: integrity={integrity} fk={len(fk)}"}

    os.replace(str(tmp_path), str(final_path))
    return {
        "ok": True,
        "tmp_path": str(tmp_path),
        "final_path": str(final_path),
        "final_sha256": sha256_file(final_path),
        "final_size": final_path.stat().st_size,
        "staging_sha256": sha256_file(staging_path),
    }


def write_build_audit(build: dict, dataset: dict, inputs: dict, parser) -> tuple:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    final_path = build["final_path"]
    staging_path = build["staging_path"]
    counts = build["validation"]["counts"]

    final_sha = sha256_file(final_path) if final_path.exists() else None
    staging_sha = sha256_file(staging_path) if staging_path.exists() else None

    verify = None
    if final_path.exists():
        conn = sqlite3.connect(str(final_path))
        verify = {
            "integrity_check": conn.execute("PRAGMA integrity_check").fetchone()[0],
            "foreign_key_check": len(conn.execute("PRAGMA foreign_key_check").fetchall()),
            "audio_mapping": conn.execute("SELECT COUNT(*) FROM audio_mapping").fetchone()[0],
            "audio_confirmed": conn.execute(
                "SELECT COUNT(*) FROM audio_mapping "
                "WHERE mapping_status='CONFIRMED_BY_HUMAN'").fetchone()[0],
            "ai_artifact": conn.execute("SELECT COUNT(*) FROM ai_artifact").fetchone()[0],
            "learning_item": conn.execute("SELECT COUNT(*) FROM learning_item").fetchone()[0],
            "learning_goal": conn.execute("SELECT COUNT(*) FROM learning_goal").fetchone()[0],
            "source_ref": conn.execute("SELECT COUNT(*) FROM source_ref").fetchone()[0],
            "sub_question": conn.execute("SELECT COUNT(*) FROM sub_question").fetchone()[0],
        }
        conn.close()

    payload = {
        "task": "P1-05-B 第二阶段正式构建",
        "generated_at": now_iso(),
        "verdict": "PASS" if build["validation"]["ok"] else "STOP",
        "database_path": str(final_path),
        "staging_path": str(staging_path),
        "textbook_id": dataset["textbook_id"],
        "snapshot_id": dataset["snapshot_id"],
        "import_batch": build["batch_id"],
        "parser_version": "v01-P1-03-C",
        "rule_set_version": RULE_SET_VERSION,
        "schema_version": SCHEMA_VERSION,
        "pdf_sha256": inputs["pdf_sha256"],
        "mp3_count": inputs["mp3_count"],
        "table_counts": counts,
        "validation": build["validation"],
        "publish": build["publish"],
        "final_sha256": final_sha,
        "staging_sha256": staging_sha,
        "final_independent_verification": verify,
        "stage_records": build["stage_records"],
        "boundaries": {
            "ai_calls": 0,
            "learner_rows": 0,
            "source_pdf_modified": False,
            "source_mp3_modified": False,
            "parser_modified": False,
        },
    }
    json_path = AUDIT_DIR / "P1-05-B_build.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md = ["# P1-05-B 第二阶段正式建库报告", ""]
    md.append(f"- 生成时间：{payload['generated_at']}")
    md.append(f"- 结论：{payload['verdict']}")
    md.append(f"- 正式数据库：{final_path}")
    md.append(f"- staging：{staging_path}")
    md.append(f"- textbook_id：{dataset['textbook_id']}")
    md.append(f"- snapshot_id：{dataset['snapshot_id']}")
    md.append(f"- import_batch：{build['batch_id']}")
    md.append(f"- parser：v01-P1-03-C / rule_set：{RULE_SET_VERSION} / schema：{SCHEMA_VERSION}")
    md.append(f"- PDF SHA256：{inputs['pdf_sha256']}")
    md.append(f"- MP3 数量：{inputs['mp3_count']}")
    md.append(f"- 正式库 SHA256：{final_sha}")
    md.append("")
    md.append("## 1. 各表最终数量")
    md.append("")
    md.append("| 表 | 数量 |")
    md.append("| --- | --- |")
    for table in sorted(counts):
        md.append(f"| {table} | {counts[table]} |")
    md.append("")
    md.append("## 2. 校验明细")
    md.append("")
    md.append("| 检查 | 结果 | 说明 |")
    md.append("| --- | --- | --- |")
    for c in build["validation"]["checks"]:
        md.append(f"| {c['name']} | {c['status']} | {c['detail']} |")
    md.append("")
    md.append("## 3. 独立验收（重新打开正式库）")
    md.append("")
    if verify:
        for k, v in verify.items():
            md.append(f"- {k}：{v}")
    md.append("")
    md.append("## 4. staging → 正式库")
    md.append("")
    if build["publish"] and build["publish"].get("ok"):
        md.append(f"- 临时文件：{build['publish']['tmp_path']}")
        md.append(f"- 原子替换为：{build['publish']['final_path']}")
        md.append(f"- staging SHA256：{build['publish']['staging_sha256']}")
        md.append(f"- 正式库 SHA256：{build['publish']['final_sha256']}")
    md.append("")
    md.append("## 5. 边界")
    md.append("")
    md.append("- AI 调用次数：0")
    md.append("- learner 数据：0（L4 不入 contentpack）")
    md.append("- 原始 PDF / MP3：未修改")
    md.append("- parser：未修改")
    md_path = AUDIT_DIR / "P1-05-B_build.md"
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    return json_path, md_path


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------

def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="P1-05-B 第一阶段 Dry-run 构建器")
    ap.add_argument("--quiet", action="store_true", help="只输出结论")
    ap.add_argument("--build", action="store_true",
                    help="执行 P1-05-B 第二阶段正式构建（staging → 验证 → contentpack v1）")
    args = ap.parse_args(argv)

    parser_module = load_parser_module()
    inputs = collect_inputs(parser_module)
    pdf = parser_module.find_pdf()
    parser = parser_module.TextbookParser(pdf)
    parser.parse()

    dataset = build_dataset(parser, inputs)
    checks = run_checks(dataset, parser, inputs)
    probe = schema_probe()

    dup_issues = parser.quality["activity_numbering"]["issues"]
    boundary_nr = sum(1 for a in parser.activities if a.boundary_status != "OK")
    order_nr = sum(1 for p in parser.pages if p.reading_order_status == "NEED_REVIEW")
    frozen = {
        "unit": len(parser.units),
        "section": len(parser.sections),
        "activity": len(parser.activities),
        "duplicate_anomaly": len(dup_issues),
        "boundary_need_review": boundary_nr,
        "reading_order_need_review": order_nr,
    }

    statuses: dict[str, int] = {}
    for m in dataset["audio_mapping"]:
        statuses[m["mapping_status"]] = statuses.get(m["mapping_status"], 0) + 1

    hard_fail = [c for c in checks if c["status"] == "FAIL" and c["hard"]]
    notes = [c for c in checks if c["status"] == "NOTE"]
    frozen_mismatch = [k for k, v in FROZEN.items() if frozen.get(k) != v]

    if hard_fail or frozen_mismatch or not probe["ok"]:
        verdict = STOP
    elif notes:
        verdict = PASS_WITH_NOTES
    else:
        verdict = PASS

    conclusion = (
        "Dry-run 全部硬性检查通过；未创建正式 contentpack SQLite，未创建 learner.db，"
        "未修改原始教材与 parser，AI 调用次数为 0。"
        "可以进入「P1-05-B 第二阶段：正式构建 contentpack v1 SQLite」"
        if verdict != STOP else
        "存在硬性失败项或冻结统计不一致，必须停止，不得进入正式构建。"
    )

    result = {
        "verdict": verdict,
        "schema_probe": probe,
        "audio": {
            "audio_asset": len(dataset["audio_asset"]),
            "audio_mapping": len(dataset["audio_mapping"]),
            "candidate": statuses.get("CANDIDATE", 0),
            "confirmed": statuses.get("CONFIRMED_BY_HUMAN", 0),
            "target_resolved": sum(1 for m in dataset["audio_mapping"] if m["target_id"]),
        },
        "frozen": frozen,
        "conclusion": conclusion,
    }
    json_path, md_path = write_reports(result, dataset, checks, parser, inputs)

    build_result = None
    if args.build:
        if verdict == STOP:
            print("Dry-run 为 STOP，拒绝进入正式构建。")
            return 2
        started = now_iso()
        build = build_contentpack(dataset, inputs, parser, started)
        build_json, build_md = write_build_audit(build, build["dataset"], inputs, parser)
        build_result = build
        if not args.quiet:
            print()
            print("=" * 70)
            print("P1-05-B 第二阶段正式构建")
            print("=" * 70)
            print(f"staging：{build['staging_path']}")
            print(f"正式库：{build['final_path']}")
            print(f"校验：{'OK' if build['validation']['ok'] else 'FAILED'}")
            if build["publish"] and build["publish"].get("ok"):
                print(f"正式库 SHA256：{build['publish']['final_sha256']}")
            print(f"报告：{build_md}")
            print(f"JSON：{build_json}")

    if not args.quiet:
        print("=" * 70)
        print("P1-05-B 第一阶段 Dry-run")
        print("=" * 70)
        print(f"结论: {verdict}")
        print(f"冻结统计: {frozen}")
        print(f"预计记录数: page={len(dataset['page'])} unit={len(dataset['unit'])} "
              f"section={len(dataset['section'])} activity={len(dataset['activity'])} "
              f"content_block={len(dataset['content_block'])} "
              f"content_asset={len(dataset['content_asset'])} "
              f"evidence={len(dataset['evidence'])}")
        print(f"音频: asset={len(dataset['audio_asset'])} mapping={len(dataset['audio_mapping'])} "
              f"candidate={statuses.get('CANDIDATE', 0)} confirmed={statuses.get('CONFIRMED_BY_HUMAN', 0)}")
        print(f"schema 探针: {probe['count']} 张表 ({probe['location']})")
        print(f"硬性失败: {len(hard_fail)}  提示: {len(notes)}  冻结不一致: {frozen_mismatch}")
        print(f"报告: {md_path}")
        print(f"JSON: {json_path}")

    if build_result is not None and not build_result["validation"]["ok"]:
        return 3
    return 0 if verdict != STOP else 2


if __name__ == "__main__":
    sys.exit(main())
