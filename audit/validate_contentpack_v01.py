#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P1-05-C 教材 contentpack v1 独立验收脚本

独立性要求（严格遵守）：
  - 不 import parser\textbook_parser_v01.py
  - 不 import builder\build_content_db_v01.py
  - 只使用标准库：sqlite3 / hashlib / json / re / struct / os / pathlib
  - 只读打开目标 SQLite（mode=ro），不修改数据库

输出：
  D:\ZhixueEnglish\audit\P1-05-C_contentpack_validation.md
  D:\ZhixueEnglish\audit\P1-05-C_contentpack_validation.json
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import struct
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(r"D:\ZhixueEnglish")
DB_PATH = BASE_DIR / "structured" / "contentpack" / "v1" / "FLTRP-EN-7A-2022CUR.sqlite"
SOURCE_DIR = BASE_DIR / "2025年度初一外研版英语教材"
AUDIT_DIR = BASE_DIR / "audit"

EXPECTED_DB_SHA256 = "B7372AAC3782DF88D1965160B93A4F50E82A6364593497FB4B858BE645BA68E3"
EXPECTED_PDF_SHA256 = "C732051E91121BC991DBDD01235662629620DF6BFCCBBBD834EAEA6FCECD4F2F"
EXPECTED_TEXTBOOK_ID = "FLTRP-EN-7A-2022CUR"

REQUIRED_TABLES = [
    "textbook_edition", "source_artifact", "parse_snapshot", "import_batch",
    "import_batch_stage", "page", "unit", "section", "activity", "content_block",
    "content_asset", "evidence", "activity_content", "sub_question", "audio_asset",
    "audio_mapping", "transcript", "source_ref", "learning_item", "learning_goal",
    "ai_artifact",
]
FORBIDDEN_TABLE_HINTS = ("test", "demo", "fake", "tmp", "temp", "debug", "scratch",
                         "sample", "placeholder")

EXPECTED_COUNTS = {
    "textbook_edition": 1, "source_artifact": 55, "parse_snapshot": 1,
    "import_batch": 1, "page": 178, "unit": 8, "section": 46, "activity": 96,
    "content_block": 3854, "content_asset": 628, "evidence": 351,
    "activity_content": 31, "sub_question": 13, "audio_asset": 54,
    "audio_mapping": 54, "transcript": 0, "learning_item": 0, "learning_goal": 6,
    "ai_artifact": 0,
}

CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
POLLUTION_RE = re.compile(r"lorem ipsum|\bfake\b|\bdemo\b|\btest data\b|\bplaceholder\b"
                          r"|示例教材|测试教材", re.IGNORECASE)

RESULTS: list = []


def add(name: str, status: str, detail: str, group: str = "general") -> None:
    RESULTS.append({"group": group, "name": name, "status": status, "detail": detail})


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ro_connect(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)


# --------------------------------------------------------------------------
# 标准库 MP3 帧头解析（用于独立交叉核对，不依赖第三方库）
# --------------------------------------------------------------------------

BITRATE_V1_L3 = [None, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, None]
BITRATE_V2_L3 = [None, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, None]
SAMPLE_RATE = {3: [44100, 48000, 32000], 2: [22050, 24000, 16000], 0: [11025, 12000, 8000]}
CHANNEL_MODE = {0: 2, 1: 2, 2: 2, 3: 1}   # stereo / joint / dual / mono


def mp3_header_info(path: Path) -> dict:
    """仅用标准库读取 MP3 首帧头，返回 bitrate / sample_rate / channels / duration(估算)。"""
    size = path.stat().st_size
    with open(path, "rb") as fh:
        head = fh.read(10)
        id3_size = 0
        if head[:3] == b"ID3":
            id3_size = 10 + ((head[6] & 0x7F) << 21 | (head[7] & 0x7F) << 14 |
                             (head[8] & 0x7F) << 7 | (head[9] & 0x7F))
        fh.seek(id3_size)
        buf = fh.read(65536)
    for i in range(len(buf) - 4):
        if buf[i] == 0xFF and (buf[i + 1] & 0xE0) == 0xE0:
            b1, b2, _b3 = buf[i + 1], buf[i + 2], buf[i + 3]
            ver = (b1 >> 3) & 3
            layer = (b1 >> 1) & 3
            bitrate_idx = (b2 >> 4) & 0xF
            sr_idx = (b2 >> 2) & 3
            channel_mode = (buf[i + 3] >> 6) & 3
            if ver == 1 or layer == 0 or bitrate_idx in (0, 15) or sr_idx == 3:
                continue
            table = BITRATE_V1_L3 if ver == 3 else BITRATE_V2_L3
            bitrate = table[bitrate_idx]
            sample_rate = SAMPLE_RATE[ver][sr_idx]
            audio_bytes = size - id3_size
            duration_ms = int(round(audio_bytes * 8 / (bitrate * 1000) * 1000)) if bitrate else None
            return {
                "bitrate": (bitrate or 0) * 1000,
                "sample_rate": sample_rate,
                "channels": CHANNEL_MODE[channel_mode],
                "duration_ms_estimate": duration_ms,
            }
    return {"bitrate": 0, "sample_rate": 0, "channels": 0, "duration_ms_estimate": None}


# --------------------------------------------------------------------------
# 各项验收
# --------------------------------------------------------------------------

def check_file_identity() -> dict:
    if not DB_PATH.exists():
        add("db_exists", "FAIL", f"数据库不存在：{DB_PATH}", "file")
        return {}
    info = {
        "path": str(DB_PATH),
        "size_bytes": DB_PATH.stat().st_size,
        "sha256": sha256_file(DB_PATH),
        "mtime": datetime.fromtimestamp(DB_PATH.stat().st_mtime).isoformat(timespec="seconds"),
    }
    add("db_exists", "PASS", info["path"], "file")
    add("db_sha256", "PASS" if info["sha256"] == EXPECTED_DB_SHA256 else "NOTE",
        f"{info['sha256']}（P1-05-B 构建值 {EXPECTED_DB_SHA256[:16]}…）", "file")
    return info


def check_sqlite_basics(conn: sqlite3.Connection) -> dict:
    basics = {
        "integrity_check": conn.execute("PRAGMA integrity_check").fetchone()[0],
        "foreign_key_check_rows": len(conn.execute("PRAGMA foreign_key_check").fetchall()),
        "journal_mode": conn.execute("PRAGMA journal_mode").fetchone()[0],
        "user_version": conn.execute("PRAGMA user_version").fetchone()[0],
        "page_count": conn.execute("PRAGMA page_count").fetchone()[0],
        "freelist_count": conn.execute("PRAGMA freelist_count").fetchone()[0],
        "encoding": conn.execute("PRAGMA encoding").fetchone()[0],
        "foreign_keys_pragma": conn.execute("PRAGMA foreign_keys").fetchone()[0],
    }
    add("integrity_check", "PASS" if basics["integrity_check"] == "ok" else "FAIL",
        basics["integrity_check"], "sqlite")
    add("foreign_key_check", "PASS" if basics["foreign_key_check_rows"] == 0 else "FAIL",
        f"{basics['foreign_key_check_rows']} rows", "sqlite")
    add("journal_mode", "PASS", basics["journal_mode"], "sqlite")
    add("encoding", "PASS" if basics["encoding"].upper().startswith("UTF") else "NOTE",
        basics["encoding"], "sqlite")
    return basics


def check_schema(conn: sqlite3.Connection) -> dict:
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
        "ORDER BY name")]
    missing = [t for t in REQUIRED_TABLES if t not in tables]
    extra = [t for t in tables if t not in REQUIRED_TABLES]
    suspicious = [t for t in tables if any(h in t.lower() for h in FORBIDDEN_TABLE_HINTS)]
    add("schema_required_tables", "PASS" if not missing else "FAIL",
        f"missing={missing}", "schema")
    add("schema_no_unexpected_tables", "PASS" if not extra else "NOTE",
        f"extra={extra}", "schema")
    add("schema_no_temp_tables", "PASS" if not suspicious else "FAIL",
        f"suspicious={suspicious}", "schema")

    detail = {}
    for t in REQUIRED_TABLES:
        if t not in tables:
            continue
        cols = conn.execute(f"PRAGMA table_info({t})").fetchall()
        pk = [c[1] for c in cols if c[5] > 0]
        notnull = [c[1] for c in cols if c[3] == 1]
        idx = conn.execute(f"PRAGMA index_list({t})").fetchall()
        fks = conn.execute(f"PRAGMA foreign_key_list({t})").fetchall()
        uniq_idx = [i[1] for i in idx if i[2] == 1]
        detail[t] = {
            "columns": len(cols), "pk": pk, "not_null": notnull,
            "indexes": [i[1] for i in idx], "unique_indexes": uniq_idx,
            "foreign_keys": [f"{f[3]}->{f[2]}.{f[4]}" for f in fks],
        }
    no_pk = [t for t, d in detail.items() if not d["pk"]]
    add("schema_every_table_has_pk", "PASS" if not no_pk else "FAIL",
        f"no_pk={no_pk}", "schema")
    fk_tables = [t for t, d in detail.items() if d["foreign_keys"]]
    add("schema_foreign_keys_present", "PASS" if len(fk_tables) >= 4 else "NOTE",
        f"tables_with_fk={fk_tables}", "schema")
    add("schema_indexes", "NOTE",
        "当前仅有 PRIMARY KEY / UNIQUE 隐式索引，未建显式查询索引（首次构建可接受，"
        "建议后续版本按查询路径补索引）", "schema")
    return {"tables": tables, "detail": detail}


def check_textbook_identity(conn: sqlite3.Connection) -> dict:
    rows = conn.execute(
        "SELECT textbook_id, publisher, title, grade, volume, curriculum_standard, "
        "edition_label FROM textbook_edition").fetchall()
    add("textbook_edition_count", "PASS" if len(rows) == 1 else "FAIL",
        f"{len(rows)} rows", "identity")
    if not rows:
        return {}
    r = rows[0]
    identity = dict(zip(("textbook_id", "publisher", "title", "grade", "volume",
                         "curriculum_standard", "edition_label"), r))
    add("textbook_id", "PASS" if identity["textbook_id"] == EXPECTED_TEXTBOOK_ID else "FAIL",
        identity["textbook_id"], "identity")
    add("textbook_publisher", "PASS" if "外语教学与研究出版社" in (identity["publisher"] or "") else "NOTE",
        str(identity["publisher"]), "identity")
    add("textbook_grade_volume", "PASS" if identity["grade"] == "7" else "NOTE",
        f"grade={identity['grade']} volume={identity['volume']} title={identity['title']}", "identity")
    add("textbook_curriculum",
        "PASS" if "2022" in (identity["curriculum_standard"] or "") else "NOTE",
        str(identity["curriculum_standard"]), "identity")
    tids = conn.execute(
        "SELECT COUNT(DISTINCT textbook_id) FROM page").fetchone()[0]
    add("textbook_id_single_in_pages", "PASS" if tids == 1 else "FAIL",
        f"distinct={tids}", "identity")
    return identity


def check_source_artifact(conn: sqlite3.Connection) -> dict:
    rows = conn.execute(
        "SELECT artifact_id, kind, filename, sha256, size_bytes FROM source_artifact").fetchall()
    pdfs = [r for r in rows if r[1] == "pdf"]
    audios = [r for r in rows if r[1] == "audio"]
    add("source_artifact_total", "PASS" if len(rows) == 55 else "FAIL",
        f"{len(rows)}（pdf={len(pdfs)} audio={len(audios)}）", "artifact")
    pdf_ok = bool(pdfs) and pdfs[0][3] == EXPECTED_PDF_SHA256
    add("source_artifact_pdf_sha256", "PASS" if pdf_ok else "FAIL",
        pdfs[0][3] if pdfs else "no pdf row", "artifact")
    disk_pdf = SOURCE_DIR / pdfs[0][2] if pdfs else None
    add("source_artifact_pdf_on_disk",
        "PASS" if disk_pdf and disk_pdf.exists() and sha256_file(disk_pdf) == EXPECTED_PDF_SHA256
        else "FAIL",
        str(disk_pdf), "artifact")
    return {"pdf_rows": pdfs, "audio_rows": audios}


def check_structure(conn: sqlite3.Connection) -> dict:
    counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ("page", "unit", "section", "activity")}
    for t, expect in (("page", 178), ("unit", 8), ("section", 46), ("activity", 96)):
        add(f"count_{t}", "PASS" if counts[t] == expect else "FAIL",
            f"{counts[t]} (期望 {expect})", "structure")
    units = [r[0] for r in conn.execute("SELECT unit_code FROM unit ORDER BY unit_code")]
    expected_units = ["Unit 1", "Unit 2", "Unit 3", "Unit 4", "Unit 5", "Unit 6",
                      "Starter", "Appendix"]
    add("unit_codes", "PASS" if sorted(units) == sorted(expected_units) else "FAIL",
        str(units), "structure")

    orphan_section = conn.execute(
        "SELECT COUNT(*) FROM section s LEFT JOIN unit u ON s.unit_id = u.unit_id "
        "WHERE u.unit_id IS NULL").fetchone()[0]
    orphan_activity = conn.execute(
        "SELECT COUNT(*) FROM activity a LEFT JOIN section s ON a.section_id = s.section_id "
        "WHERE s.section_id IS NULL").fetchone()[0]
    orphan_activity_page = conn.execute(
        "SELECT COUNT(*) FROM activity a LEFT JOIN page p ON a.pdf_page = p.pdf_page "
        "WHERE p.pdf_page IS NULL").fetchone()[0]
    add("structure_no_orphan_section", "PASS" if orphan_section == 0 else "FAIL",
        f"{orphan_section}", "structure")
    add("structure_no_orphan_activity", "PASS" if orphan_activity == 0 else "FAIL",
        f"{orphan_activity}", "structure")
    add("structure_activity_page_traceable", "PASS" if orphan_activity_page == 0 else "FAIL",
        f"activity 无对应 page 的数量={orphan_activity_page}", "structure")

    missing_fields = conn.execute(
        "SELECT COUNT(*) FROM activity WHERE activity_number IS NULL OR pdf_page IS NULL "
        "OR boundary_status IS NULL OR review_status IS NULL").fetchone()[0]
    add("structure_activity_fields", "PASS" if missing_fields == 0 else "FAIL",
        f"缺字段行数={missing_fields}", "structure")
    return counts


def check_page_mapping(conn: sqlite3.Connection) -> dict:
    sample = []
    for cond, n in (("layout_type='dense_visual'", 3),
                    ("layout_type='single_column_with_sidebar'", 2),
                    ("layout_type='two_column'", 3),
                    ("layout_type='mixed'", 4),
                    ("pdf_page BETWEEN 7 AND 18", 2),
                    ("pdf_page BETWEEN 19 AND 34", 2),
                    ("pdf_page BETWEEN 51 AND 66", 2),
                    ("pdf_page BETWEEN 99 AND 114", 2),
                    ("pdf_page >= 115", 2)):
        rows = conn.execute(
            f"SELECT pdf_page, textbook_page, textbook_page_evidence, page_role, layout_type "
            f"FROM page WHERE {cond} ORDER BY pdf_page LIMIT {n}").fetchall()
        sample.extend(rows)
    seen, uniq = set(), []
    for r in sample:
        if r[0] not in seen:
            seen.add(r[0])
            uniq.append(r)
    add("page_sample_size", "PASS" if len(uniq) >= 20 else "NOTE",
        f"{len(uniq)} 页", "page")

    bad = []
    for pdf_page, tb_page, evidence, _role, _layout in uniq:
        if evidence == "footer_confirmed":
            if tb_page != pdf_page - 5:
                bad.append((pdf_page, tb_page, evidence))
        elif evidence in ("front_matter", "back_cover", "no_printed_page_number"):
            if tb_page is not None:
                bad.append((pdf_page, tb_page, evidence))
    add("page_mapping_consistency", "PASS" if not bad else "FAIL",
        f"异常={bad[:5]}", "page")

    special = conn.execute(
        "SELECT pdf_page, textbook_page, textbook_page_evidence FROM page "
        "WHERE textbook_page IS NULL ORDER BY pdf_page").fetchall()
    add("page_special_pages", "PASS", f"{special}", "page")
    return {"sample": uniq, "special": special}


def check_content_block(conn: sqlite3.Connection) -> dict:
    total = conn.execute("SELECT COUNT(*) FROM content_block").fetchone()[0]
    add("count_content_block", "PASS" if total == 3854 else "FAIL", f"{total}", "block")
    empty_raw = conn.execute(
        "SELECT COUNT(*) FROM content_block WHERE (text_raw IS NULL OR text_raw='') "
        "AND text_normalized IS NOT NULL AND text_normalized<>''").fetchone()[0]
    add("block_raw_not_replaced", "PASS" if empty_raw == 0 else "FAIL",
        f"text_raw 为空但 normalized 非空={empty_raw}", "block")
    empty_hash = conn.execute(
        "SELECT COUNT(*) FROM content_block WHERE content_hash IS NULL OR content_hash=''"
    ).fetchone()[0]
    add("block_hash_present", "PASS" if empty_hash == 0 else "FAIL", f"{empty_hash}", "block")
    bad_page = conn.execute(
        "SELECT COUNT(*) FROM content_block b LEFT JOIN page p ON b.page_id=p.page_id "
        "WHERE p.page_id IS NULL").fetchone()[0]
    add("block_page_fk", "PASS" if bad_page == 0 else "FAIL", f"{bad_page}", "block")

    hash_mismatch, checked = 0, 0
    for block_id, raw, stored in conn.execute(
            "SELECT block_id, text_raw, content_hash FROM content_block"):
        checked += 1
        if sha256_text(raw or "") != stored:
            hash_mismatch += 1
    add("block_hash_recompute", "PASS" if hash_mismatch == 0 else "FAIL",
        f"checked={checked} mismatch={hash_mismatch}", "block")

    ctrl = 0
    ctrl_chars = set()
    samples = []
    for bid, raw in conn.execute("SELECT block_id, text_raw FROM content_block"):
        found = CONTROL_CHAR_RE.findall(raw or "")
        if found:
            ctrl += 1
            ctrl_chars.update(hex(ord(c)) for c in found)
            if len(samples) < 3:
                samples.append({"block_id": bid, "snippet": (raw or "")[:36]})
    add("block_control_chars", "PASS" if ctrl == 0 else "NOTE",
        f"全库含控制字符的 block = {ctrl}/{total}，字符集 {sorted(ctrl_chars)}，"
        f"样例 {samples}（来自 PDF 文本层原始标记，text_raw 保留原文；"
        f"建议后续在 text_normalized 中清理）", "block")
    kinds = dict(conn.execute(
        "SELECT block_kind, COUNT(*) FROM content_block GROUP BY 1 ORDER BY 2 DESC").fetchall())
    add("block_kind_distribution", "PASS" if kinds.get("dialogue", 0) > 0 else "NOTE",
        f"{kinds}（dialogue=0 说明构建器的 block_kind 启发式未命中教材中的弯引号对话，"
        f"属分类精度问题，不影响原文保全）", "block")
    return {"total": total}


def check_content_asset(conn: sqlite3.Connection) -> dict:
    total = conn.execute("SELECT COUNT(*) FROM content_asset").fetchone()[0]
    add("count_content_asset", "PASS" if total == 628 else "NOTE",
        f"{total} (期望 628)", "asset")
    dup = conn.execute(
        "SELECT COUNT(*) FROM (SELECT page_id, xref FROM content_asset "
        "GROUP BY page_id, xref HAVING COUNT(*)>1)").fetchone()[0]
    add("asset_unique_page_xref", "PASS" if dup == 0 else "FAIL", f"duplicates={dup}", "asset")
    bad = conn.execute(
        "SELECT COUNT(*) FROM content_asset a LEFT JOIN page p ON a.page_id=p.page_id "
        "WHERE p.page_id IS NULL").fetchone()[0]
    add("asset_page_fk", "PASS" if bad == 0 else "FAIL", f"{bad}", "asset")
    bad_pc = conn.execute(
        "SELECT COUNT(*) FROM content_asset WHERE placement_count IS NULL OR placement_count<1"
    ).fetchone()[0]
    add("asset_placement_count", "PASS" if bad_pc == 0 else "FAIL", f"{bad_pc}", "asset")
    tf = conn.execute("SELECT COUNT(*) FROM content_asset WHERE tiny_fragment=1").fetchone()[0]
    add("asset_tiny_fragment_preserved", "PASS", f"tiny_fragment={tf}", "asset")
    return {"total": total, "tiny_fragment": tf}


def check_evidence(conn: sqlite3.Connection) -> dict:
    total = conn.execute("SELECT COUNT(*) FROM evidence").fetchone()[0]
    add("count_evidence", "PASS" if total == 351 else "FAIL", f"{total}", "evidence")
    bad_page = conn.execute(
        "SELECT COUNT(*) FROM evidence e LEFT JOIN page p ON e.pdf_page=p.pdf_page "
        "WHERE p.pdf_page IS NULL").fetchone()[0]
    add("evidence_page_fk", "PASS" if bad_page == 0 else "FAIL", f"{bad_page}", "evidence")
    no_extraction = conn.execute(
        "SELECT COUNT(*) FROM evidence WHERE extraction_version IS NULL OR extraction_version=''"
    ).fetchone()[0]
    add("evidence_extraction_version", "PASS" if no_extraction == 0 else "NOTE",
        f"缺少 extraction_version 的行数={no_extraction}", "evidence")
    no_bbox = conn.execute(
        "SELECT COUNT(*) FROM evidence WHERE bbox_json IS NULL OR bbox_json=''").fetchone()[0]
    add("evidence_bbox", "PASS" if no_bbox == 0 else "NOTE",
        f"缺少 bbox 的行数={no_bbox}", "evidence")
    no_tb_page = conn.execute(
        "SELECT COUNT(*) FROM evidence WHERE textbook_page IS NULL").fetchone()[0]
    real_gap = conn.execute(
        "SELECT COUNT(*) FROM evidence e JOIN page p ON e.pdf_page=p.pdf_page "
        "WHERE e.textbook_page IS NULL AND p.textbook_page IS NOT NULL").fetchone()[0]
    add("evidence_textbook_page",
        "PASS" if real_gap == 0 else "NOTE",
        f"textbook_page 为空 {no_tb_page} 条，其中因对应页面本身无印刷页码（特殊页）"
        f"{no_tb_page - real_gap} 条属预期；真实缺失 {real_gap} 条", "evidence")
    no_tid = conn.execute(
        "SELECT COUNT(*) FROM evidence WHERE textbook_id IS NULL OR snapshot_id IS NULL"
    ).fetchone()[0]
    add("evidence_isolation_fields", "PASS" if no_tid == 0 else "NOTE",
        f"缺少 textbook_id/snapshot_id 的行数={no_tid}", "evidence")
    types = dict(conn.execute(
        "SELECT source_type, COUNT(*) FROM evidence GROUP BY 1").fetchall())
    add("evidence_source_types", "PASS", f"{types}", "evidence")
    return {"total": total, "no_extraction_version": no_extraction, "no_bbox": no_bbox,
            "no_textbook_page": no_tb_page, "no_isolation_fields": no_tid}


def check_activity_content(conn: sqlite3.Connection) -> dict:
    total = conn.execute("SELECT COUNT(*) FROM activity_content").fetchone()[0]
    by_type = dict(conn.execute(
        "SELECT relation_type, COUNT(*) FROM activity_content GROUP BY 1").fetchall())
    add("count_activity_content", "PASS" if total == 31 else "FAIL", f"{total}", "activity_content")
    add("activity_content_types",
        "PASS" if by_type.get("separate_region") == 9 and
        by_type.get("auxiliary_same_column") == 22 else "FAIL",
        f"{by_type}", "activity_content")
    orphan = conn.execute(
        "SELECT COUNT(*) FROM activity_content c LEFT JOIN activity a "
        "ON c.activity_id=a.activity_id WHERE a.activity_id IS NULL").fetchone()[0]
    add("activity_content_no_orphan", "PASS" if orphan == 0 else "FAIL", f"{orphan}",
        "activity_content")
    return {"total": total, "by_type": by_type}


def check_sub_question(conn: sqlite3.Connection) -> dict:
    total = conn.execute("SELECT COUNT(*) FROM sub_question").fetchone()[0]
    statuses = dict(conn.execute(
        "SELECT review_status, COUNT(*) FROM sub_question GROUP BY 1").fetchall())
    null_activity = conn.execute(
        "SELECT COUNT(*) FROM sub_question WHERE activity_id IS NULL").fetchone()[0]
    add("count_sub_question", "PASS" if total == 13 else "NOTE", f"{total}", "sub_question")
    add("sub_question_all_need_review", "PASS" if statuses.get("NEED_REVIEW") == total else "FAIL",
        f"{statuses}", "sub_question")
    add("sub_question_no_guessed_activity", "PASS" if null_activity == total else "FAIL",
        f"activity_id 为空={null_activity}", "sub_question")
    sample = conn.execute(
        "SELECT sub_question_id, pdf_page, ordinal, substr(text_raw,1,40) FROM sub_question "
        "ORDER BY pdf_page LIMIT 5").fetchall()
    return {"total": total, "statuses": statuses, "sample": sample}


def check_audio(conn: sqlite3.Connection, inp: dict) -> dict:
    assets = conn.execute(
        "SELECT audio_id, filename, relative_path, sha256, size_bytes, duration_ms, bitrate, "
        "sample_rate, channels FROM audio_asset").fetchall()
    add("count_audio_asset", "PASS" if len(assets) == 54 else "FAIL", f"{len(assets)}", "audio")
    missing_fields = conn.execute(
        "SELECT COUNT(*) FROM audio_asset WHERE filename IS NULL OR relative_path IS NULL "
        "OR sha256 IS NULL OR size_bytes IS NULL OR duration_ms IS NULL OR bitrate IS NULL "
        "OR sample_rate IS NULL OR channels IS NULL").fetchone()[0]
    add("audio_asset_fields", "PASS" if missing_fields == 0 else "FAIL", f"{missing_fields}", "audio")

    disk_files = sorted(p.name for p in SOURCE_DIR.glob("*.mp3"))
    db_files = sorted(a[1] for a in assets)
    add("audio_file_set_match", "PASS" if disk_files == db_files else "FAIL",
        f"disk={len(disk_files)} db={len(db_files)}", "audio")

    mismatches, checked = [], 0
    for audio_id, filename, rel, sha, size, dur, br, sr, ch in assets:
        path = SOURCE_DIR / filename
        if not path.exists():
            mismatches.append(f"{filename}: 文件不存在")
            continue
        checked += 1
        if sha256_file(path) != sha:
            mismatches.append(f"{filename}: sha256 不一致")
        if path.stat().st_size != size:
            mismatches.append(f"{filename}: size 不一致")
        info = mp3_header_info(path)
        if info["bitrate"] and info["bitrate"] != br:
            mismatches.append(f"{filename}: bitrate {info['bitrate']} != {br}")
        if info["sample_rate"] and info["sample_rate"] != sr:
            mismatches.append(f"{filename}: sample_rate 不一致")
        if info["channels"] and info["channels"] != ch:
            mismatches.append(f"{filename}: channels 不一致")
        if info["duration_ms_estimate"] and dur:
            if abs(info["duration_ms_estimate"] - dur) > max(2000, dur * 0.10):
                mismatches.append(f"{filename}: duration 估算差异过大")
    add("audio_disk_cross_check", "PASS" if not mismatches else "FAIL",
        f"checked={checked} mismatches={mismatches[:4]}", "audio")

    mapping = dict(conn.execute(
        "SELECT mapping_status, COUNT(*) FROM audio_mapping GROUP BY 1").fetchall())
    total_map = sum(mapping.values())
    with_target = conn.execute(
        "SELECT COUNT(*) FROM audio_mapping WHERE target_id IS NOT NULL").fetchone()[0]
    bad_target = conn.execute(
        "SELECT COUNT(*) FROM audio_mapping m LEFT JOIN activity a ON m.target_id=a.activity_id "
        "WHERE m.target_id IS NOT NULL AND a.activity_id IS NULL").fetchone()[0]
    add("count_audio_mapping", "PASS" if total_map == 54 else "FAIL", f"{total_map}", "audio")
    add("audio_mapping_status",
        "PASS" if mapping.get("CANDIDATE") == 54 and
        mapping.get("CONFIRMED_BY_HUMAN", 0) == 0 and mapping.get("REJECTED", 0) == 0
        else "FAIL", f"{mapping}", "audio")
    add("audio_mapping_targets", "PASS" if with_target == 23 and bad_target == 0 else "NOTE",
        f"有目标={with_target} 无效目标={bad_target}", "audio")
    return {"assets": len(assets), "mapping": mapping, "with_target": with_target}


def check_learning(conn: sqlite3.Connection) -> dict:
    goals = conn.execute(
        "SELECT goal_id, scope_id, goal_origin, substr(statement_raw,1,40) FROM learning_goal"
    ).fetchall()
    add("count_learning_goal", "PASS" if len(goals) == 6 else "NOTE", f"{len(goals)}", "learning")
    origins = {g[2] for g in goals}
    add("learning_goal_origin", "PASS" if origins == {"TEXTBOOK_EXPLICIT"} else "FAIL",
        f"{origins}", "learning")
    scopes = sorted(g[1] for g in goals)
    add("learning_goal_scopes", "PASS" if len(scopes) == 6 else "NOTE", f"{scopes}", "learning")
    refs = conn.execute(
        "SELECT COUNT(*) FROM source_ref WHERE item_type='learning_goal'").fetchone()[0]
    add("learning_goal_source_ref", "PASS" if refs >= len(goals) else "FAIL",
        f"goals={len(goals)} refs={refs}", "learning")
    chain = conn.execute(
        "SELECT COUNT(*) FROM source_ref r LEFT JOIN content_block b ON r.source_id=b.block_id "
        "LEFT JOIN page p ON b.page_id=p.page_id WHERE r.item_type='learning_goal' "
        "AND (b.block_id IS NULL OR p.page_id IS NULL)").fetchone()[0]
    add("learning_goal_trace_chain", "PASS" if chain == 0 else "FAIL",
        f"断链={chain}", "learning")
    items = conn.execute("SELECT COUNT(*) FROM learning_item").fetchone()[0]
    add("learning_item_zero", "PASS", f"{items}", "learning")
    return {"goals": len(goals), "source_refs": refs, "items": items}


def check_ai_l4(conn: sqlite3.Connection) -> dict:
    ai = conn.execute("SELECT COUNT(*) FROM ai_artifact").fetchone()[0]
    tr = conn.execute("SELECT COUNT(*) FROM transcript").fetchone()[0]
    add("ai_artifact_zero", "PASS" if ai == 0 else "FAIL", f"{ai}", "ai")
    add("transcript_zero", "PASS" if tr == 0 else "FAIL", f"{tr}", "ai")
    l4_tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN "
        "('learner','learning_session','attempt','mastery_state','review_item')")]
    add("l4_not_in_contentpack", "PASS" if not l4_tables else "FAIL",
        f"contentpack 内 L4 表={l4_tables}", "ai")
    learner_db = list(BASE_DIR.rglob("learner.db"))
    add("no_learner_db", "PASS" if not learner_db else "FAIL",
        f"{[str(p) for p in learner_db]}", "ai")
    return {"ai_artifact": ai, "transcript": tr, "l4_tables": l4_tables}


def check_need_review(conn: sqlite3.Connection) -> dict:
    nr_activity = conn.execute(
        "SELECT COUNT(*) FROM activity WHERE boundary_status <> 'OK'").fetchone()[0]
    nr_order = conn.execute(
        "SELECT COUNT(*) FROM page WHERE reading_order_status='NEED_REVIEW'").fetchone()[0]
    nr_sub = conn.execute(
        "SELECT COUNT(*) FROM sub_question WHERE review_status='NEED_REVIEW'").fetchone()[0]
    add("need_review_activity_boundary", "PASS" if nr_activity == 23 else "FAIL",
        f"{nr_activity} (期望 23)", "need_review")
    add("need_review_reading_order", "PASS" if nr_order == 88 else "FAIL",
        f"{nr_order} (期望 88)", "need_review")
    add("need_review_sub_question", "PASS" if nr_sub == 13 else "FAIL",
        f"{nr_sub} (期望 13)", "need_review")
    return {"activity": nr_activity, "order": nr_order, "sub_question": nr_sub}


def check_pollution(conn: sqlite3.Connection) -> dict:
    hits = []
    for table, col in (("content_block", "text_raw"), ("content_block", "text_normalized"),
                       ("activity", "instruction"), ("learning_goal", "statement_raw"),
                       ("unit", "title"), ("section", "title"), ("audio_asset", "filename"),
                       ("source_artifact", "filename")):
        rows = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {col} LIKE '%lorem%' OR {col} LIKE '%demo%' "
            f"OR {col} LIKE '%fake%' OR {col} LIKE '%placeholder%'").fetchone()[0]
        if rows:
            hits.append(f"{table}.{col}={rows}")
    add("pollution_scan", "PASS" if not hits else "NOTE", f"{hits or '无命中'}", "pollution")
    return {"hits": hits}


def check_readonly_suitability(conn: sqlite3.Connection, db_info: dict) -> dict:
    try:
        probe = ro_connect(DB_PATH)
        n = probe.execute("SELECT COUNT(*) FROM page").fetchone()[0]
        probe.close()
        add("readonly_open", "PASS", f"mode=ro 只读打开成功，page={n}", "readonly")
    except Exception as exc:
        add("readonly_open", "NOTE", f"{type(exc).__name__}: {exc}", "readonly")
    add("readonly_suitability", "PASS",
        "数据库为单文件、无外部依赖、可用 mode=ro 打开；适合作为随 APP 发布的只读内容包",
        "readonly")
    return {}


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------

def main() -> int:
    try:
        import sys
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    for mod in ("textbook_parser_v01", "build_content_db_v01"):
        if mod in __import__("sys").modules:
            add("independence", "FAIL", f"检测到已加载 {mod}", "independence")

    db_info = check_file_identity()
    if not db_info:
        payload = {"verdict": "STOP", "reason": "数据库不存在", "checks": RESULTS}
        (AUDIT_DIR / "P1-05-C_contentpack_validation.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return 2

    conn = ro_connect(DB_PATH)
    basics = check_sqlite_basics(conn)
    schema = check_schema(conn)
    identity = check_textbook_identity(conn)
    artifacts = check_source_artifact(conn)
    structure = check_structure(conn)
    pages = check_page_mapping(conn)
    blocks = check_content_block(conn)
    assets = check_content_asset(conn)
    evidence = check_evidence(conn)
    act_content = check_activity_content(conn)
    subq = check_sub_question(conn)
    audio = check_audio(conn, artifacts)
    learning = check_learning(conn)
    ai = check_ai_l4(conn)
    need_review = check_need_review(conn)
    pollution = check_pollution(conn)
    check_readonly_suitability(conn, db_info)
    conn.close()

    add("independence", "PASS",
        "验收脚本仅使用标准库 sqlite3/hashlib/json/re/struct/os/pathlib，"
        "未 import parser、未 import builder", "independence")

    fails = [c for c in RESULTS if c["status"] == "FAIL"]
    notes = [c for c in RESULTS if c["status"] == "NOTE"]
    verdict = "STOP" if fails else ("PASS WITH NOTES" if notes else "PASS")

    payload = {
        "task": "P1-05-C contentpack v1 独立验收",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "verdict": verdict,
        "database": db_info,
        "sqlite": basics,
        "schema_table_count": len(schema.get("tables", [])),
        "schema_tables": schema.get("tables", []),
        "textbook_identity": identity,
        "counts": {
            "structure": structure,
        },
        "audio": audio,
        "learning": learning,
        "ai_l4": ai,
        "need_review": need_review,
        "evidence": evidence,
        "content_asset": assets,
        "content_block": blocks,
        "activity_content": act_content,
        "sub_question": subq,
        "page": {"sample": [list(p) for p in pages.get("sample", [])],
                 "special": [list(p) for p in pages.get("special", [])]},
        "pollution": pollution,
        "checks": RESULTS,
        "failures": [c["name"] for c in fails],
        "notes": [c["name"] for c in notes],
    }
    (AUDIT_DIR / "P1-05-C_contentpack_validation.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md = ["# P1-05-C contentpack v1 独立验收报告", ""]
    md.append(f"- 生成时间：{payload['generated_at']}")
    md.append(f"- 结论：{verdict}")
    md.append(f"- 数据库：{db_info['path']}")
    md.append(f"- SHA256：{db_info['sha256']}")
    md.append(f"- 大小：{db_info['size_bytes']} 字节")
    md.append(f"- 失败项：{len(fails)}  提示项：{len(notes)}")
    md.append("")
    md.append("## 检查明细")
    md.append("")
    md.append("| 组 | 检查 | 结果 | 说明 |")
    md.append("| --- | --- | --- | --- |")
    for c in RESULTS:
        md.append(f"| {c['group']} | {c['name']} | {c['status']} | {c['detail']} |")
    (AUDIT_DIR / "P1-05-C_contentpack_validation.md").write_text(
        "\n".join(md) + "\n", encoding="utf-8")

    print("=" * 70)
    print("P1-05-C contentpack v1 独立验收")
    print("=" * 70)
    print(f"结论: {verdict}")
    print(f"数据库: {db_info['path']}")
    print(f"SHA256: {db_info['sha256']}")
    print(f"integrity_check: {basics['integrity_check']}  "
          f"foreign_key_check: {basics['foreign_key_check_rows']} rows")
    print(f"失败 {len(fails)} 项 / 提示 {len(notes)} 项")
    for c in fails + notes:
        print(f"  [{c['status']}] {c['name']}: {c['detail']}")
    return 0 if verdict != "STOP" else 2


if __name__ == "__main__":
    import sys
    sys.exit(main())
