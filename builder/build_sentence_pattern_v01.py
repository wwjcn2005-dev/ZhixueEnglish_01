#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P1-06-B1.7-G1-C Sentence Pattern 首批构建与 v5 原子发布

基线：contentpack v4（只读冻结）
候选来源：audit/P1-06-B1.7-G1-B_sentence_pattern_data_model_design.json（52 条冻结候选）
流程：v4 -> 工作副本 -> 新增 52 条 sentence_pattern -> 完整验证 -> 原子发布 v5

零 schema 变更：复用 learning_item / source_ref。
既有 287 Vocabulary、23 Phrase 及其 source_ref 全部不改动。

产物：
  structured/contentpack/v5/FLTRP-EN-7A-2022CUR.sqlite
  audit/P1-06-B1.7-G1-C_sentence_pattern_v5_build.md / .json
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

import pymupdf  # 项目既有依赖 PyMuPDF 1.28.2

sys.dont_write_bytecode = True

BASE = Path(r"D:\ZhixueEnglish")
CP = BASE / "structured" / "contentpack"
V4 = CP / "v4" / "FLTRP-EN-7A-2022CUR.sqlite"
V5_DIR = CP / "v5"
V5 = V5_DIR / "FLTRP-EN-7A-2022CUR.sqlite"
V5_WORK = V5_DIR / "FLTRP-EN-7A-2022CUR.sqlite.building"
PDF = BASE / "2025年度初一外研版英语教材" / "（根据2022年版课程标准修订）义务教育教科书·英语 七年级上册.pdf"
AUDIT = BASE / "audit"
G1B_JSON = AUDIT / "P1-06-B1.7-G1-B_sentence_pattern_data_model_design.json"

TEXTBOOK_ID = "FLTRP-EN-7A-2022CUR"
SCHEMA_VERSION = "p1-04-v2"          # 零 schema 变更，沿用实际 schema 版本
RULE_SET = "P1-06-B1.7-G1-C"
V4_SNAPSHOT = "FLTRP-EN-7A-2022CUR:S20260912T143441"

EXPECTED_V4 = "C1E54D1F78F2B90DEBC38CF8F7F42969B0880413A07D3DDBE98ABA78CEA09D1E"
EXPECTED_V4_SIZE = 2404352
EXPECTED_PDF = "C732051E91121BC991DBDD01235662629620DF6BFCCBBBD834EAEA6FCECD4F2F"
EXPECTED_COUNTS = {"learning_item": 310, "source_ref": 762, "page": 178, "unit": 8, "section": 46,
                   "activity": 96, "content_block": 3854, "audio_asset": 54, "audio_mapping": 54}

SOURCE_SURFACE = {
    "COMMUNICATION_BANK": ("communication_bank", "Communication bank", "FROM_COMMUNICATION_BANK"),
    "UNIT_USEFUL_EXPRESSIONS": ("unit_useful_expression", "Useful expressions", "FROM_UNIT_USEFUL_EXPRESSIONS"),
    "LANGUAGE_NOTE": ("language_note", "Language notes", "FROM_TEXTBOOK_NOTE"),
}
FORBIDDEN_DISPLAY = ["prefer", "provide", "surprising", "what a/an", "hard to do"]
GRAMMAR_ONLY_TOKENS = ["there be", "简单句", "had better", "used to", "stop doing"]
PHRASE_ONLY_TOKENS = ["protect", "along the way"]


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", s or "")).strip()


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def sha256_text(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def sp_item_id(template: str) -> str:
    return "%s:SP:%s" % (TEXTBOOK_ID,
                         hashlib.sha1(("%s|sentence_pattern" % template).encode("utf-8")).hexdigest()[:12].upper())


def sp_content_hash(template: str, meaning_zh: str | None) -> str:
    return sha256_text("|".join([SCHEMA_VERSION, "sentence_pattern", template, meaning_zh or ""]))


# --------------------------------------------------------------------------
# 阶段 A：只读基线验证 + 候选装载
# --------------------------------------------------------------------------

def preflight() -> tuple[dict, list[dict]]:
    checks = []

    def chk(name, cond, detail):
        checks.append({"name": name, "status": "PASS" if cond else "FAIL", "detail": detail})
        return bool(cond)

    if V4_DIR_HAS_V5():
        raise SystemExit("STOP: v5 已存在（V5_ALREADY_EXISTS），不得覆盖")
    chk("v4_sha256", sha256_file(V4) == EXPECTED_V4, sha256_file(V4))
    chk("v4_size", V4.stat().st_size == EXPECTED_V4_SIZE, str(V4.stat().st_size))
    chk("pdf_sha256", sha256_file(PDF) == EXPECTED_PDF, sha256_file(PDF))

    conn = sqlite3.connect("file:%s?mode=ro" % V4.as_posix(), uri=True)
    chk("integrity_check", conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "ok")
    chk("foreign_key_check", len(conn.execute("PRAGMA foreign_key_check").fetchall()) == 0, "0")
    for t, expect in EXPECTED_COUNTS.items():
        got = conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
        chk("count_%s" % t, got == expect, "%d/%d" % (got, expect))
    types = dict(conn.execute("SELECT item_type, COUNT(*) FROM learning_item GROUP BY 1"))
    chk("vocabulary_287", types.get("vocabulary") == 287, str(types.get("vocabulary")))
    chk("phrase_23", types.get("phrase") == 23, str(types.get("phrase")))
    chk("sentence_pattern_0", types.get("sentence_pattern", 0) == 0, str(types.get("sentence_pattern", 0)))
    chk("tables_21", conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0] == 21, "21")
    active = conn.execute("SELECT snapshot_id FROM parse_snapshot WHERE is_active=1").fetchall()
    chk("active_snapshot_unique", len(active) == 1 and active[0][0] == V4_SNAPSHOT, str(active))
    conn.close()

    # 候选装载（G1-B 冻结清单是唯一来源）
    g1b = json.loads(G1B_JSON.read_text(encoding="utf-8"))
    cands = g1b["candidates"]
    chk("candidates_52", len(cands) == 52, str(len(cands)))
    ids = [c["item_id"] for c in cands]
    tpls = [c["template"] for c in cands]
    chk("candidate_item_id_unique", len(set(ids)) == 52, str(len(set(ids))))
    chk("candidate_template_unique", len(set(tpls)) == 52, str(len(set(tpls))))
    chk("candidate_namespace", all(i.startswith("%s:SP:" % TEXTBOOK_ID) for i in ids), ":SP:")
    chk("forbidden_need_review_excluded",
        not [c for c in cands if any(k in c["display_text"].lower() for k in FORBIDDEN_DISPLAY)],
        "5 NEED_REVIEW 未混入")
    chk("grammar_only_excluded",
        not [c for c in cands if any(t in c["display_text"] for t in GRAMMAR_ONLY_TOKENS)], "GRAMMAR_ONLY 未混入")
    chk("phrase_only_excluded",
        not [c for c in cands if any(t in c["display_text"].lower() for t in PHRASE_ONLY_TOKENS)], "PHRASE_ONLY 未混入")
    chk("source_surface_valid", all(c["source"] in SOURCE_SURFACE for c in cands), "3 类来源面")
    chk("evidence_present", all(c["source_blocks"] for c in cands), "52/52 有教材 block")
    chk("source_ref_planned_53", sum(len(c["source_blocks"]) for c in cands) == 53, "53")

    failures = [c for c in checks if c["status"] == "FAIL"]
    if failures:
        raise SystemExit("STOP: PREFLIGHT FAILED -> %s" % failures)
    return {"checks": checks, "candidates": cands}


def V4_DIR_HAS_V5() -> bool:
    return V5.exists()


# --------------------------------------------------------------------------
# 阶段 B/C：工作副本 + 写入 52 条
# --------------------------------------------------------------------------

def pdf_bbox_index(blocks: list[str], pages: set[int]) -> dict:
    doc = pymupdf.open(PDF)
    idx = {}
    for pg in sorted(pages):
        page = doc[pg - 1]
        for b in page.get_text("dict")["blocks"]:
            if b.get("type") != 0:
                continue
            txt = norm("".join(s["text"] for l in b.get("lines", []) for s in l["spans"]))
            idx[(pg, txt)] = [round(float(x), 2) for x in b["bbox"]]
    doc.close()
    return idx


def build_candidate_rows(conn: sqlite3.Connection, cands: list[dict]) -> list[dict]:
    rows = []
    for c in cands:
        tpl = c["template"]
        if sp_item_id(tpl) != c["item_id"]:
            raise SystemExit("STOP: item_id 与冻结规则不一致 %s" % c["item_id"])
        if sp_content_hash(tpl, c.get("meaning_zh")) != c["content_hash"]:
            raise SystemExit("STOP: content_hash 与冻结规则不一致 %s" % c["item_id"])
        refs = []
        for blk in c["source_blocks"]:
            bid = blk["block_id"]
            row = conn.execute(
                "SELECT text_raw, text_normalized, p.pdf_page, p.textbook_page FROM content_block b "
                "JOIN page p ON p.page_id=b.page_id WHERE b.block_id=?", (bid,)).fetchone()
            if row is None:
                raise SystemExit("STOP: source block 断链 %s" % bid)
            refs.append({"block_id": bid, "quote_raw": (row[0] or "")[:300],
                         "block_text": row[1] or row[0] or "", "pdf_page": row[2], "textbook_page": row[3]})
        ctx, slist, dtype = SOURCE_SURFACE[c["source"]]
        if c["derivation_type"] != dtype:
            raise SystemExit("STOP: derivation_type 与来源面不一致 %s" % c["item_id"])
        rows.append({"candidate": c, "template": tpl, "refs": refs, "context_type": ctx, "source_list": slist})
    return rows


def stage_insert(conn: sqlite3.Connection, rows: list[dict], snapshot_id: str, ts: str,
                 bbox_idx: dict) -> dict:
    li = 0
    sr = 0
    for row in rows:
        c = row["candidate"]
        conn.execute(
            "INSERT INTO learning_item(item_id,textbook_id,snapshot_id,item_type,surface_form,lemma,"
            "phonetic,part_of_speech,meaning_zh,derivation_type,review_status,canonical_text,display_text,"
            "schema_version,content_hash,created_at,updated_at,learning_requirement,requirement_conflict_status) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (c["item_id"], TEXTBOOK_ID, snapshot_id, "sentence_pattern", c["display_text"], row["template"],
             None, None, c.get("meaning_zh"), c["derivation_type"], c["review_status"], row["template"],
             c["display_text"], SCHEMA_VERSION, c["content_hash"], ts, ts,
             c["learning_requirement"], "OK"))
        li += 1
        for i, ref in enumerate(row["refs"]):
            bbox = bbox_idx.get((ref["pdf_page"], norm(ref["block_text"])))
            if bbox is None:
                raise SystemExit("STOP: 无法在 PDF 定位 block %s（pdf %s）" % (ref["block_id"], ref["pdf_page"]))
            ev = {"font_name": None, "flags": None, "size": None,
                  "pdf_page": ref["pdf_page"], "textbook_page": ref["textbook_page"],
                  "bbox": bbox, "head_block": ref["block_id"],
                  "context_type": row["context_type"], "ref_role": "pattern_source"}
            conn.execute(
                "INSERT INTO source_ref(source_ref_id,item_id,item_type,source_type,source_id,quote_raw,"
                "textbook_id,snapshot_id,textbook_emphasis,emphasis_source_list,emphasis_evidence) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                ("%s:SR%d_0" % (c["item_id"], i), c["item_id"], "sentence_pattern", "content_block",
                 ref["block_id"], ref["quote_raw"], TEXTBOOK_ID, snapshot_id, "UNKNOWN", row["source_list"],
                 json.dumps(ev, ensure_ascii=False)))
            sr += 1
    return {"learning_item": li, "source_ref": sr}


# --------------------------------------------------------------------------
# 阶段 D：内部结构验证（T-SP-1）
# --------------------------------------------------------------------------

def validate(conn: sqlite3.Connection, rows: list[dict], baseline: dict) -> dict:
    checks = []
    failures = []

    def chk(name, cond, detail):
        checks.append({"name": name, "status": "PASS" if cond else "FAIL", "detail": detail})
        if not cond:
            failures.append(name)

    chk("integrity_check", conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "ok")
    chk("foreign_key_check", len(conn.execute("PRAGMA foreign_key_check").fetchall()) == 0, "0")
    types = dict(conn.execute("SELECT item_type, COUNT(*) FROM learning_item GROUP BY 1"))
    chk("A_vocabulary_287", types.get("vocabulary") == 287, str(types.get("vocabulary")))
    chk("B_phrase_23", types.get("phrase") == 23, str(types.get("phrase")))
    chk("C_sentence_pattern_52", types.get("sentence_pattern") == 52, str(types.get("sentence_pattern")))
    total = conn.execute("SELECT COUNT(*) FROM learning_item").fetchone()[0]
    chk("D_learning_item_362", total == 362, str(total))

    # E/F/G：既有资源逐行不变
    for label, sql in (("E_vocabulary_rows_unchanged", "item_type='vocabulary'"),
                       ("F_phrase_rows_unchanged", "item_type='phrase'")):
        now_rows = sorted(map(repr, conn.execute("SELECT * FROM learning_item WHERE %s" % sql).fetchall()))
        chk(label, len(now_rows) == baseline[label]["count"] and now_rows == baseline[label]["rows"],
            "%d 行" % len(now_rows))
    old_refs = sorted(map(repr, conn.execute(
        "SELECT * FROM source_ref WHERE item_type<>'sentence_pattern'").fetchall()))
    chk("G_existing_source_ref_unchanged", old_refs == baseline["old_refs"]["rows"],
        "%d 行" % len(old_refs))
    chk("H_audio_asset_54", conn.execute("SELECT COUNT(*) FROM audio_asset").fetchone()[0] == 54, "54")
    chk("I_audio_mapping_54_candidate", conn.execute("SELECT COUNT(*) FROM audio_mapping").fetchone()[0] == 54
        and conn.execute("SELECT COUNT(*) FROM audio_mapping WHERE mapping_status<>'CANDIDATE'").fetchone()[0] == 0,
        "54 CANDIDATE")
    chk("J_table_count_21", conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0] == 21,
        "21")
    chk("no_sp_audio_mapping", conn.execute(
        "SELECT COUNT(*) FROM audio_mapping WHERE target_id LIKE '%:SP:%'").fetchone()[0] == 0, "0")

    # 逐条验证 52 条
    bad = []
    for row in rows:
        c = row["candidate"]
        r = conn.execute("SELECT item_type,canonical_text,display_text,lemma,surface_form,meaning_zh,"
                         "content_hash,learning_requirement,requirement_conflict_status,review_status,"
                         "derivation_type,schema_version,part_of_speech,phonetic FROM learning_item "
                         "WHERE item_id=?", (c["item_id"],)).fetchone()
        if r is None:
            bad.append((c["item_id"], "missing"))
            continue
        exp = ("sentence_pattern", row["template"], c["display_text"], row["template"], c["display_text"],
               c.get("meaning_zh"), c["content_hash"], c["learning_requirement"], "OK", c["review_status"],
               c["derivation_type"], SCHEMA_VERSION, None, None)
        if r != exp:
            bad.append((c["item_id"], r, exp))
    chk("52_items_field_exact", not bad, "不一致=%d" % len(bad))

    refs = conn.execute("SELECT item_id, source_id, textbook_emphasis, emphasis_source_list, emphasis_evidence "
                        "FROM source_ref WHERE item_type='sentence_pattern'").fetchall()
    chk("source_ref_count_53", len(refs) == 53, str(len(refs)))
    broken = [x for x in refs if not conn.execute(
        "SELECT 1 FROM content_block WHERE block_id=?", (x[1],)).fetchone()]
    chk("source_ref_block_exists", not broken, "断链=%d" % len(broken))
    emph = {x[2] for x in refs}
    chk("textbook_emphasis_all_unknown", emph == {"UNKNOWN"}, str(emph))
    bad_ev = []
    for x in refs:
        d = json.loads(x[4])
        if not {"pdf_page", "textbook_page", "bbox", "head_block", "context_type", "ref_role"} <= set(d):
            bad_ev.append(x[0])
        elif d["ref_role"] != "pattern_source" or d["font_name"] is not None:
            bad_ev.append(x[0])
    chk("evidence_shape_ok", not bad_ev, "异常=%d" % len(bad_ev))
    ctx = dict(conn.execute("SELECT json_extract(emphasis_evidence,'$.context_type'), COUNT(*) "
                            "FROM source_ref WHERE item_type='sentence_pattern' GROUP BY 1"))
    expect_ctx = {}
    for row in rows:
        expect_ctx[row["context_type"]] = expect_ctx.get(row["context_type"], 0) + len(row["refs"])
    chk("source_surface_preserved", ctx == expect_ctx
        and set(ctx) == {"communication_bank", "unit_useful_expression", "language_note"},
        "%s（期望 %s）" % (json.dumps(ctx, ensure_ascii=False), json.dumps(expect_ctx, ensure_ascii=False)))
    chk("no_example_rows", conn.execute("SELECT COUNT(*) FROM source_ref WHERE item_type='sentence_pattern' "
                                        "AND json_extract(emphasis_evidence,'$.ref_role')<>'pattern_source'").fetchone()[0] == 0,
        "无实例/配对行（G1-C 仅写入冻结的 pattern_source）")
    chk("no_need_review_5_stored", conn.execute(
        "SELECT COUNT(*) FROM learning_item WHERE item_type='sentence_pattern' AND "
        "(lower(canonical_text) LIKE '%prefer%' OR canonical_text LIKE '%provide%' OR "
        " canonical_text LIKE '%surprising%' OR canonical_text LIKE '%hard to do%' OR "
        " canonical_text LIKE '%What + a/an%')").fetchone()[0] == 0, "0")
    chk("no_grammar_only_stored", conn.execute(
        "SELECT COUNT(*) FROM learning_item WHERE item_type='sentence_pattern' AND "
        "(canonical_text LIKE '%there be%' OR canonical_text LIKE '%had better%' OR "
        " canonical_text LIKE '%used to%' OR canonical_text LIKE '%stop doing%' OR "
        " canonical_text LIKE '%basic sentence%')").fetchone()[0] == 0, "0")
    chk("no_ai_artifact", conn.execute("SELECT COUNT(*) FROM ai_artifact").fetchone()[0] == 0, "0")
    act = conn.execute("SELECT COUNT(*) FROM parse_snapshot WHERE is_active=1").fetchone()[0]
    chk("single_active_snapshot", act == 1, str(act))
    return {"ok": not failures, "checks": checks, "failures": failures,
            "context_type_distribution": ctx, "source_ref": len(refs)}


def render_md(r: dict) -> str:
    md = ["# P1-06-B1.7-G1-C Sentence Pattern 首批构建与 v5 原子发布报告", "",
          "- 结论：**%s**" % r["verdict"],
          "- 生成时间：%s" % r["generated_at"],
          "- 流程：v4（冻结只读）→ 工作副本 → 新增 52 条 sentence_pattern → 验证 → 原子发布 v5",
          "- rule_set：%s ｜ schema_version：%s（零 schema 变更）" % (r["rule_set"], r["schema_version"]),
          "- snapshot：%s" % r["snapshot_id"], ""]
    md += ["## 1. 基线与产物", "", "| 对象 | SHA256 | 大小 | 状态 |", "| --- | --- | --- | --- |"]
    for k, v in r["sha256"].items():
        md.append("| %s | `%s` | %s | %s |" % (k, v["hash"], v.get("size", "-"), v["status"]))
    md += ["", "## 2. 核心数量", "", "| 指标 | v4 | v5 |", "| --- | --- | --- |"]
    for k, v in r["counts"].items():
        md.append("| %s | %s | %s |" % (k, v[0], v[1]))
    md += ["", "## 3. 来源面分布", "", "```text",
           json.dumps(r["validation"]["context_type_distribution"], ensure_ascii=False), "```", "",
           "## 4. 52 条指纹", "", "| # | 来源 | Unit | canonical_text | item_id | content_hash | 字重 | 要求 | 审核 |",
           "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for c in r["candidates"]:
        md.append("| %d | %s | %s | `%s` | `%s` | `%s` | %s | %s | %s |" % (
            c["seq"], c["source"], c.get("unit") or "-", c["template"], c["item_id"], c["content_hash"],
            "UNKNOWN", c["learning_requirement"], c["review_status"]))
    md += ["", "## 5. 内部结构验证（T-SP-1）", ""]
    for c in r["validation"]["checks"]:
        md.append("- [%s] %s：%s" % (c["status"], c["name"], c["detail"]))
    md += ["", "## 6. 排除项确认", ""]
    for k, v in r["exclusions"].items():
        md.append("- %s：%s" % (k, v))
    md += ["", "## 7. 边界确认", ""]
    for k, v in r["boundaries"].items():
        md.append("- %s：%s" % (k, v))
    md += ["", "## 8. 备注", ""]
    for n in r["notes"]:
        md.append("- %s" % n)
    return "\n".join(md) + "\n"


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    pf = preflight()
    cands = pf["candidates"]

    baseline = {}
    conn = sqlite3.connect("file:%s?mode=ro" % V4.as_posix(), uri=True)
    for label, cond in (("E_vocabulary_rows_unchanged", "item_type='vocabulary'"),
                        ("F_phrase_rows_unchanged", "item_type='phrase'")):
        rows = conn.execute("SELECT * FROM learning_item WHERE %s" % cond).fetchall()
        baseline[label] = {"count": len(rows), "rows": sorted(map(repr, rows))}
    baseline["old_refs"] = {"rows": sorted(map(repr, conn.execute(
        "SELECT * FROM source_ref WHERE item_type<>'sentence_pattern'").fetchall()))}
    rows = build_candidate_rows(conn, cands)
    conn.close()

    pages = {ref["pdf_page"] for row in rows for ref in row["refs"]}
    blocks = [ref["block_text"] for row in rows for ref in row["refs"]]
    bbox_idx = pdf_bbox_index(blocks, pages)

    started = now()
    snapshot_id = "%s:S%s" % (TEXTBOOK_ID, datetime.now().strftime("%Y%m%dT%H%M%S"))
    batch_id = "%s:B0" % snapshot_id

    V5_DIR.mkdir(parents=True, exist_ok=True)
    if V5_WORK.exists():
        V5_WORK.unlink()
    shutil.copyfile(V4, V5_WORK)
    work = sqlite3.connect(str(V5_WORK))
    work.execute("PRAGMA foreign_keys=ON")
    if work.execute("SELECT COUNT(*) FROM learning_item WHERE item_type='sentence_pattern'").fetchone()[0]:
        work.close()
        V5_WORK.unlink(missing_ok=True)
        print("STOP: 工作副本已含 sentence_pattern")
        return 10

    stages = stage_insert(work, rows, snapshot_id, started, bbox_idx)
    work.execute("UPDATE parse_snapshot SET is_active=0, status='SUPERSEDED' WHERE snapshot_id=?", (V4_SNAPSHOT,))
    work.execute(
        "INSERT INTO parse_snapshot(snapshot_id,textbook_id,parser_name,parser_version,rule_set_version,"
        "input_pdf_sha256,input_audio_count,build_started_at,build_finished_at,status,stats_json,quality_json,"
        "is_active,supersedes_snapshot_id,notes) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (snapshot_id, TEXTBOOK_ID, "textbook_parser_v01", "v01-P1-03-C", RULE_SET, EXPECTED_PDF, 54,
         started, now(), "VALIDATED",
         json.dumps({"sentence_pattern": 52, "learning_item": 362, "source_ref": 762 + stages["source_ref"]},
                    ensure_ascii=False),
         json.dumps({"t_sp_1": "PASS", "vocabulary_unchanged": "PASS", "phrase_unchanged": "PASS"},
                    ensure_ascii=False),
         1, V4_SNAPSHOT, "P1-06-B1.7-G1-C Sentence Pattern 首批构建（v5）"))
    work.execute("INSERT INTO import_batch(batch_id,snapshot_id,textbook_id,started_at,status) VALUES(?,?,?,?,?)",
                 (batch_id, snapshot_id, TEXTBOOK_ID, started, "BUILDING"))
    work.execute("UPDATE import_batch SET status='SUCCESS', finished_at=? WHERE batch_id=?", (now(), batch_id))
    work.commit()
    validation = validate(work, rows, baseline)
    work.execute("VACUUM")
    work.close()

    published = None
    if validation["ok"]:
        probe = sqlite3.connect(str(V5_WORK))
        ok = probe.execute("PRAGMA integrity_check").fetchone()[0] == "ok" and not probe.execute("PRAGMA foreign_key_check").fetchall()
        probe.close()
        if ok:
            V5_WORK.replace(V5)
            published = {"path": str(V5), "sha256": sha256_file(V5), "size": V5.stat().st_size}
        else:
            validation["ok"] = False
            validation["failures"].append("temp_integrity")
    if not validation["ok"]:
        V5_WORK.unlink(missing_ok=True)

    report = {
        "task": "P1-06-B1.7-G1-C Sentence Pattern 首批构建与 v5 原子发布",
        "generated_at": now(), "rule_set": RULE_SET, "schema_version": SCHEMA_VERSION,
        "verdict": "PASS" if validation["ok"] else "BLOCKED",
        "snapshot_id": snapshot_id, "import_batch": batch_id,
        "sha256": {
            "v4 (输入, 构建后复核)": {"hash": sha256_file(V4), "size": V4.stat().st_size,
                                      "status": "UNCHANGED" if sha256_file(V4) == EXPECTED_V4 else "CHANGED"},
            "v5 (输出)": {"hash": published["sha256"] if published else None,
                          "size": published["size"] if published else None,
                          "status": "PUBLISHED" if published else "NOT_PUBLISHED"},
            "pdf (复核)": {"hash": sha256_file(PDF), "size": PDF.stat().st_size,
                           "status": "UNCHANGED" if sha256_file(PDF) == EXPECTED_PDF else "CHANGED"},
        },
        "counts": {"Vocabulary": (287, 287), "Phrase": (23, 23), "Sentence Pattern": (0, 52),
                   "learning_item": (310, 362), "source_ref": (762, 762 + stages["source_ref"])},
        "inserted": stages,
        "candidates": [{"seq": row["candidate"]["seq"], "source": row["candidate"]["source"],
                        "unit": row["candidate"].get("unit"), "template": row["template"],
                        "display_text": row["candidate"]["display_text"],
                        "item_id": row["candidate"]["item_id"],
                        "content_hash": row["candidate"]["content_hash"],
                        "meaning_zh": row["candidate"].get("meaning_zh"),
                        "learning_requirement": row["candidate"]["learning_requirement"],
                        "review_status": row["candidate"]["review_status"],
                        "derivation_type": row["candidate"]["derivation_type"],
                        "source_blocks": [r["block_id"] for r in row["refs"]],
                        "pdf_pages": sorted({r["pdf_page"] for r in row["refs"]})}
                       for row in rows],
        "validation": validation,
        "exclusions": {
            "5 NEED_REVIEW": "prefer A to B / ... provide... with... / How surprising, amazing! / "
                             "What + a/an + adj + n + S + V! / it is hard to do sth —— 全部未入库",
            "13 COMMUNICATION_EXPRESSION": "未升级为 Sentence Pattern（未写入任何行）",
            "3 PHRASE_ONLY": "protect... from... / along the way / ... with a... face. —— 保持词组级",
            "23 Phrase": "v4 既有 Phrase 未改动",
            "Grammar-only": "there be 句型的用法 / 简单句的基本句型 / had better / used to / "
                            "stop doing vs stop to do 等 —— 未入库",
        },
        "boundaries": {
            "v4 是否修改": "否（只读 + 复制工作副本）",
            "既有 287 Vocabulary": "逐行完全未变",
            "既有 23 Phrase": "逐行完全未变",
            "既有 source_ref": "逐行完全未变（仅新增 53 条 sentence_pattern 引用）",
            "audio_asset / audio_mapping": "未改动（54 / 54 CANDIDATE）",
            "schema": "未变更（21 张表不变，无 CREATE/ALTER/DROP）",
            "PDF / MP3": "未修改",
            "parser / 既有 builder / 规范 / 既有报告": "未修改",
            "AI / OCR / TTS": "0 / 0 / 0",
            "D:\\ZhixueAI": "未访问",
            "G1-A 两个 Note": "保持冻结，未处理",
        },
        "notes": [
            "source_ref 仅写入 G1-B 冻结的 53 条 pattern_source（不生成 example / paired_response 行），"
            "以保证候选集合与冻结清单精确相等。",
            "G1-B 的 paired_response / example 设计保持有效，但需专门受控任务才可落库。",
            "G1-A 两个 Note 保持冻结（Language notes 的 section 归属、pdf118 阅读顺序）。",
        ],
    }
    AUDIT.mkdir(parents=True, exist_ok=True)
    (AUDIT / "P1-06-B1.7-G1-C_sentence_pattern_v5_build.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (AUDIT / "P1-06-B1.7-G1-C_sentence_pattern_v5_build.md").write_text(render_md(report), encoding="utf-8")

    print("=" * 70)
    print("G1-C:", report["verdict"])
    print("v5:", published)
    print("counts:", report["counts"], "| inserted:", stages)
    print("failures:", validation["failures"])
    return 0 if validation["ok"] else 3


if __name__ == "__main__":
    sys.exit(main())
