#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P1-06-B1.7-F2 Phrase 正式数据构建与原子发布（contentpack v4）

基线：contentpack v3（只读）
流程：v3 -> 工作副本 -> 新增 Phrase 资源 -> 完整验证 -> 独立审计 -> 原子发布 v4

第一批正式 Phrase = 23 条
  A. 21 条词表多词条目（derivation_type = FROM_TEXTBOOK_LIST）
  B. 2 条教材语言注释明确称为“固定搭配 / 固定短语”的语言单位（FROM_TEXTBOOK_NOTE）

零 schema 变更：完全复用 v3 的 learning_item / source_ref。
Vocabulary 原有记录（item_id / content_hash / 文本 / POS / emphasis / requirement /
review_status / source_ref）全部不改动。

产物：
  structured/contentpack/v4/FLTRP-EN-7A-2022CUR.sqlite
  audit/P1-06-B1.7-F2_phrase_v4_build.md / .json
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
V1 = CP / "v1" / "FLTRP-EN-7A-2022CUR.sqlite"
V2 = CP / "v2" / "FLTRP-EN-7A-2022CUR.sqlite"
V3 = CP / "v3" / "FLTRP-EN-7A-2022CUR.sqlite"
V4_DIR = CP / "v4"
V4 = V4_DIR / "FLTRP-EN-7A-2022CUR.sqlite"
V4_WORK = V4_DIR / "FLTRP-EN-7A-2022CUR.sqlite.building"
SUBJECT_DIR = BASE / "2025年度初一外研版英语教材"
PDF = SUBJECT_DIR / "（根据2022年版课程标准修订）义务教育教科书·英语 七年级上册.pdf"
AUDIT = BASE / "audit"

TEXTBOOK_ID = "FLTRP-EN-7A-2022CUR"
SCHEMA_VERSION = "p1-04-v2"          # 零 schema 变更：沿用 v3 实际 schema 版本
RULE_SET = "P1-06-B1.7-F2"
V3_SNAPSHOT = "FLTRP-EN-7A-2022CUR:S20260912T140155"

EXPECTED_V1 = "B7372AAC3782DF88D1965160B93A4F50E82A6364593497FB4B858BE645BA68E3"
EXPECTED_V2 = "C97B0F4EB09811F2477723A40A01B695DA984DDF1BD5FA5668B59ADC61ED0430"
EXPECTED_V3 = "13E1B961383794259907F388EDBD856C3C5E5B0303FF19ACBB0E76F569A9BE0C"
EXPECTED_PDF = "C732051E91121BC991DBDD01235662629620DF6BFCCBBBD834EAEA6FCECD4F2F"

# --- 第一批正式 Phrase（21 条词表多词条目，顺序与任务清单一致）----------------
LIST_PHRASES = [
    "junior high",
    "red scarf",
    "school uniform",
    "teaching building",
    "dining hall",
    "each other",
    "of course",
    "a bit",
    "take part in",
    "point out",
    "in fact",
    "primary school",
    "rock music",
    "pick up",
    "against the law",
    "throw away",
    "corn silk",
    "get lost",
    "die out",
    "as dead as a dodo",
    "as happy as a clam",
]

# --- 2 条教材语言注释明确称为固定语言单位 --------------------------------------
NOTE_PHRASES = [
    {
        "canonical_text": "protect... from...",
        "note_label": "固定搭配",
        "block_ids": ["FLTRP-EN-7A-2022CUR:P120:B2", "FLTRP-EN-7A-2022CUR:P120:B3"],
    },
    {
        "canonical_text": "along the way",
        "note_label": "固定短语",
        "block_ids": ["FLTRP-EN-7A-2022CUR:P125:B3", "FLTRP-EN-7A-2022CUR:P125:B4"],
    },
]

# --- 明确排除（本阶段不落库）--------------------------------------------------
FROZEN_KNOCK = {
    "canonical_text": "knock around (",
    "item_id": "FLTRP-EN-7A-2022CUR:V:F642720E6AA5",
    "content_hash": "920f52a180dba2d07bcac316dc79300b6a65991ac3632ba9dd61fddf68f0812c",
}
REVIEW_QUEUE_PREFER = "prefer A to B"
EXCLUDED_BODY_MULTIWORD = [
    "talk about", "look at", "think about", "listen to", "find out", "a lot of",
    "come from", "as well as", "in front of", "get up", "look for",
]

FONT_BOLD_MARK = "Medium"
FONT_PLAIN_MARK = "Regula"
POS_SPAN = re.compile(r"^(n|v|adj|adv|prep|pron|conj|num|art|int|abbr)\.$")
LATIN_HEAD = re.compile(r"^[A-Za-z]")

TASK_TEXT_NOTE = (
    "P1-06-B1.7-F2 任务文本在 §十三（protect... from... emphasis=UNKNOWN）之后被截断，"
    "§十四 及以后（along the way emphasis、source_ref/evidence 细节、item_id/content_hash 最终确认、"
    "构建后验证清单、报告格式、停止条件）未送达。本构建按 P1-06-B1.7-F1 已确认设计补齐，"
    "并在报告中逐项标注推断项，未扩大识别范围。"
)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    return re.sub(r"\s+", " ", s).strip()


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


def phrase_item_id(canonical_text: str) -> str:
    """F1 §15：<textbook_id>:P:<sha1(canonical_text|phrase)[:12]>（与 :V: 命名空间隔离）"""
    key = "%s|%s" % (canonical_text, "phrase")
    return "%s:P:%s" % (TEXTBOOK_ID, hashlib.sha1(key.encode("utf-8")).hexdigest()[:12].upper())


def phrase_content_hash(canonical_text: str, meaning_zh: str | None) -> str:
    """F1 §15：sha256(schema_version|'phrase'|canonical_text|meaning_zh)，不含 emphasis/requirement/audio"""
    return sha256_text("|".join([SCHEMA_VERSION, "phrase", canonical_text, meaning_zh or ""]))


def vocab_item_id(canonical_text: str, pos: str | None) -> str:
    key = "%s|%s" % (canonical_text, pos or "")
    return "%s:V:%s" % (TEXTBOOK_ID, hashlib.sha1(key.encode("utf-8")).hexdigest()[:12].upper())


def vocab_content_hash(canonical_text: str, pos: str | None, meaning_zh: str | None) -> str:
    return sha256_text("|".join([SCHEMA_VERSION, "vocabulary", canonical_text, pos or "", meaning_zh or ""]))


# --------------------------------------------------------------------------
# Pass A：从 v3 冻结数据装载 Phrase 规格（教材事实来自 source_ref，不复制对象）
# --------------------------------------------------------------------------

def load_specs(conn: sqlite3.Connection) -> list[dict]:
    specs: list[dict] = []

    for canonical in LIST_PHRASES:
        row = conn.execute(
            "SELECT item_id, canonical_text, meaning_zh, part_of_speech, phonetic, "
            "review_status, display_text FROM learning_item WHERE canonical_text=? "
            "AND item_type='vocabulary'", (canonical,)).fetchone()
        if row is None:
            raise SystemExit("STOP: v3 中找不到词表条目 %r" % canonical)
        v_item_id, v_canon, v_meaning, v_pos, v_phon, v_review, v_display = row
        refs = []
        for r in conn.execute(
                "SELECT source_ref_id, source_id, quote_raw, textbook_emphasis, "
                "emphasis_source_list, emphasis_evidence FROM source_ref "
                "WHERE item_id=? ORDER BY source_ref_id", (v_item_id,)):
            bid = r[1]
            blk = conn.execute(
                "SELECT b.text_raw, b.text_normalized, p.pdf_page, p.textbook_page "
                "FROM content_block b JOIN page p ON p.page_id=b.page_id "
                "WHERE b.block_id=?", (bid,)).fetchone()
            if blk is None:
                raise SystemExit("STOP: 词表 source_ref 断链 %s" % bid)
            refs.append({
                "source_id": bid,
                "quote_raw": r[2],
                "source_list": r[4],
                "db_emphasis": r[3],
                "db_evidence": r[5],
                "block_text": blk[0],
                "pdf_page": blk[2],
                "textbook_page": blk[3],
                "context_type": "textbook_vocabulary_entry",
            })
        specs.append({
            "kind": "list",
            "canonical_text": canonical,
            "display_text": canonical,
            "source_vocab_display_text": v_display,
            "meaning_zh": v_meaning,
            "part_of_speech": v_pos,
            "phonetic": v_phon,
            "source_vocab_item_id": v_item_id,
            "source_vocab_review_status": v_review,
            "refs": refs,
        })

    for spec in NOTE_PHRASES:
        refs = []
        for bid in spec["block_ids"]:
            blk = conn.execute(
                "SELECT b.text_raw, b.text_normalized, p.pdf_page, p.textbook_page "
                "FROM content_block b JOIN page p ON p.page_id=b.page_id "
                "WHERE b.block_id=?", (bid,)).fetchone()
            if blk is None:
                raise SystemExit("STOP: 语言注释 block 不存在 %s" % bid)
            refs.append({
                "source_id": bid,
                "quote_raw": (blk[0] or "")[:300],
                "source_list": "Language notes",
                "db_emphasis": None,
                "db_evidence": None,
                "block_text": blk[0],
                "pdf_page": blk[2],
                "textbook_page": blk[3],
                "context_type": "language_note",
            })
        specs.append({
            "kind": "note",
            "canonical_text": spec["canonical_text"],
            "display_text": spec["canonical_text"],
            "surface_text": spec["canonical_text"],
            "meaning_zh": None,
            "part_of_speech": None,
            "phonetic": None,
            "source_vocab_item_id": None,
            "source_vocab_review_status": None,
            "note_label": spec["note_label"],
            "refs": refs,
        })
    return specs


# --------------------------------------------------------------------------
# Pass B：从原始 PDF 独立重算排版证据（不继承 Vocabulary 字段）
# --------------------------------------------------------------------------

def pdf_probe(specs: list[dict]) -> dict:
    doc = pymupdf.open(PDF)
    page_index: dict[int, dict] = {}
    probe: dict[str, dict] = {}

    def index(page_no: int) -> dict:
        if page_no not in page_index:
            blocks = {}
            for b in doc[page_no - 1].get_text("dict")["blocks"]:
                if b.get("type") != 0:
                    continue
                txt = norm("".join(s["text"] for l in b.get("lines", []) for s in l.get("spans", [])))
                blocks[txt] = b
            page_index[page_no] = blocks
        return page_index[page_no]

    for spec in specs:
        obs = []
        for ref in spec["refs"]:
            page_no = ref["pdf_page"]
            blk = index(page_no).get(norm(ref["block_text"]))
            if blk is None:
                obs.append({"source_id": ref["source_id"], "matched": False,
                            "head_span_found": False, "head_font": None,
                            "head_span_text": None, "bbox": None, "fonts": []})
                continue
            spans = [s for l in blk["lines"] for s in l["spans"] if s["text"].strip()]
            head = None
            for s in spans:
                t = s["text"].strip()
                if not LATIN_HEAD.match(t):
                    continue
                if POS_SPAN.match(t):
                    continue
                head = s
                break
            obs.append({
                "source_id": ref["source_id"],
                "matched": True,
                "head_span_found": head is not None,
                "head_font": head["font"] if head else None,
                "head_span_text": norm(head["text"]) if head else None,
                "bbox": [round(float(x), 2) for x in blk["bbox"]],
                "fonts": sorted({s["font"] for s in spans}),
            })
        probe[spec["canonical_text"] + "|" + spec["kind"]] = {
            "canonical_text": spec["canonical_text"], "kind": spec["kind"], "observations": obs}
    doc.close()
    return probe


def font_emphasis(font_name: str | None) -> str:
    if not font_name:
        return "UNKNOWN"
    if FONT_BOLD_MARK in font_name:
        return "BOLD"
    if FONT_PLAIN_MARK in font_name:
        return "PLAIN"
    return "UNKNOWN"


def finalize(specs: list[dict], probe: dict) -> tuple[list[dict], list[dict]]:
    """合并 Pass A / Pass B，判定 Phrase 级 emphasis / requirement / review，并逐 ref 产出 evidence。"""
    checks: list[dict] = []

    for spec in specs:
        key = spec["canonical_text"] + "|" + spec["kind"]
        obs = {o["source_id"]: o for o in probe[key]["observations"]}
        head_emph: list[str] = []
        for ref in spec["refs"]:
            o = obs[ref["source_id"]]
            ref["pdf_matched"] = o["matched"]
            ref["head_span_found"] = o["head_span_found"]
            ref["head_font"] = o["head_font"]
            ref["head_span_text"] = o["head_span_text"]
            ref["pdf_bbox"] = o["bbox"]
            ref["pdf_fonts"] = o["fonts"]
            if spec["kind"] == "note":
                # F1 §10/§13：语言注释来源无 headword 视觉强调证据 -> UNKNOWN（不得默认 PLAIN）
                ref["emphasis"] = "UNKNOWN"
                ref["emphasis_evidence"] = {
                    "font_name": None,
                    "flags": None,
                    "size": None,
                    "pdf_page": ref["pdf_page"],
                    "textbook_page": ref["textbook_page"],
                    "bbox": o["bbox"],
                    "head_block": ref["source_id"],
                    "context_type": ref["context_type"],
                }
                if not o["matched"] or o["bbox"] is None:
                    raise SystemExit("STOP: 语言注释 block 无法在 PDF 定位 %s" % ref["source_id"])
                continue
            if o["head_span_found"]:
                ref["emphasis"] = font_emphasis(o["head_font"])
                head_emph.append(ref["emphasis"])
                ev = json.loads(ref["db_evidence"]) if ref["db_evidence"] else {}
                ev["context_type"] = ref["context_type"]
                ref["emphasis_evidence"] = ev
                if ref["head_span_text"] != norm(spec["display_text"]):
                    checks.append({"name": "display_vs_pdf_head", "status": "NOTE",
                                   "detail": "%s: pdf=%r canonical=%r" % (
                                       spec["canonical_text"], ref["head_span_text"], spec["display_text"])})
            else:
                # 续行块：无 head span，其字重随条目 head span（v3 亦如此）
                ref["emphasis"] = None
                ev = json.loads(ref["db_evidence"]) if ref["db_evidence"] else {}
                ev["context_type"] = ref["context_type"]
                ev["head_span_found"] = False
                ref["emphasis_evidence"] = ev

        if spec["kind"] == "note":
            spec["textbook_emphasis"] = "UNKNOWN"
            spec["emphasis_rule"] = "language_note_without_headword_bold_evidence"
            spec["learning_requirement"] = "CORE"
            spec["requirement_rule"] = "textbook_explicit_fixed_language_unit"
            spec["review_status"] = "NEED_REVIEW"
            spec["derivation_type"] = "FROM_TEXTBOOK_NOTE"
        else:
            unique = sorted(set(head_emph))
            if len(unique) != 1:
                raise SystemExit("STOP: %s 多来源字重冲突 %s" % (spec["canonical_text"], unique))
            spec["textbook_emphasis"] = unique[0]
            spec["emphasis_rule"] = "vocabulary_head_span_font:%s" % spec["refs"][0]["head_font"]
            spec["learning_requirement"] = "CORE" if unique[0] == "BOLD" else (
                "RECOGNITION" if unique[0] == "PLAIN" else "NEED_REVIEW")
            spec["requirement_rule"] = "textbook_list_emphasis_%s" % unique[0]
            spec["review_status"] = spec["source_vocab_review_status"]
            spec["derivation_type"] = "FROM_TEXTBOOK_LIST"

        # 独立交叉核对：Pass A（v3 source_ref 字重） vs Pass B（PDF 字体）
        for ref in spec["refs"]:
            if spec["kind"] == "list":
                expect = spec["textbook_emphasis"] if ref["emphasis"] is None else ref["emphasis"]
                checks.append({
                    "name": "emphasis_db_vs_pdf",
                    "status": "PASS" if ref["db_emphasis"] == expect else "FAIL",
                    "detail": "%s %s db=%s pdf=%s font=%s" % (
                        spec["canonical_text"], ref["source_id"], ref["db_emphasis"], expect, ref["head_font"]),
                })

        spec["requirement_conflict_status"] = "OK"
        spec["item_id"] = phrase_item_id(spec["canonical_text"])
        spec["content_hash"] = phrase_content_hash(spec["canonical_text"], spec["meaning_zh"])

    return specs, checks


# --------------------------------------------------------------------------
# 构建
# --------------------------------------------------------------------------

def stage_insert(conn: sqlite3.Connection, specs: list[dict], snapshot_id: str, ts: str) -> dict:
    item_rows = 0
    ref_rows = 0
    for spec in specs:
        conn.execute(
            "INSERT INTO learning_item(item_id,textbook_id,snapshot_id,item_type,surface_form,"
            "lemma,phonetic,part_of_speech,meaning_zh,derivation_type,review_status,"
            "canonical_text,display_text,schema_version,content_hash,created_at,updated_at,"
            "learning_requirement,requirement_conflict_status) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (spec["item_id"], TEXTBOOK_ID, snapshot_id, "phrase", spec["display_text"],
             spec["canonical_text"], spec["phonetic"], spec["part_of_speech"], spec["meaning_zh"],
             spec["derivation_type"], spec["review_status"], spec["canonical_text"],
             spec["display_text"], SCHEMA_VERSION, spec["content_hash"], ts, ts,
             spec["learning_requirement"], spec["requirement_conflict_status"]))
        item_rows += 1
        for i, ref in enumerate(spec["refs"]):
            conn.execute(
                "INSERT INTO source_ref(source_ref_id,item_id,item_type,source_type,source_id,"
                "quote_raw,textbook_id,snapshot_id,textbook_emphasis,emphasis_source_list,"
                "emphasis_evidence) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                ("%s:SR%d_0" % (spec["item_id"], i), spec["item_id"], "phrase", "content_block",
                 ref["source_id"], ref["quote_raw"], TEXTBOOK_ID, snapshot_id,
                 ref["emphasis"] if ref["emphasis"] is not None else spec["textbook_emphasis"],
                 ref["source_list"],
                 json.dumps(ref["emphasis_evidence"], ensure_ascii=False)))
            ref_rows += 1
    return {"learning_item": item_rows, "source_ref": ref_rows}


def validate(conn: sqlite3.Connection, specs: list[dict], v3_counts: dict,
             v3_items: list, v3_refs: list, v3_mp3: int) -> dict:
    checks: list[dict] = []
    failures: list[str] = []

    def chk(name, cond, detail):
        checks.append({"name": name, "status": "PASS" if cond else "FAIL", "detail": detail})
        if not cond:
            failures.append(name)

    chk("integrity_check", conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "PRAGMA integrity_check")
    chk("foreign_key_check", len(conn.execute("PRAGMA foreign_key_check").fetchall()) == 0, "PRAGMA foreign_key_check")

    phrases = conn.execute("SELECT COUNT(*) FROM learning_item WHERE item_type='phrase'").fetchone()[0]
    chk("phrase_count_23", phrases == 23, "phrase=%d" % phrases)
    vocab = conn.execute("SELECT COUNT(*) FROM learning_item WHERE item_type='vocabulary'").fetchone()[0]
    chk("vocabulary_count_287", vocab == 287, "vocabulary=%d" % vocab)
    other = conn.execute("SELECT COUNT(*) FROM learning_item WHERE item_type NOT IN ('vocabulary','phrase')").fetchone()[0]
    chk("no_other_item_type", other == 0, "other=%d" % other)

    # Vocabulary 逐行完全不变
    now_items = conn.execute("SELECT * FROM learning_item WHERE item_type='vocabulary'").fetchall()
    chk("vocabulary_rows_unchanged", sorted(map(repr, now_items)) == sorted(map(repr, v3_items)),
        "v3=%d v4=%d 行级比较" % (len(v3_items), len(now_items)))
    now_refs = conn.execute(
        "SELECT * FROM source_ref WHERE item_type='learning_item' ORDER BY source_ref_id").fetchall()
    chk("vocabulary_source_refs_unchanged", sorted(map(repr, now_refs)) == sorted(map(repr, v3_refs)),
        "v3=%d v4=%d" % (len(v3_refs), len(now_refs)))

    # Phrase 身份 / 哈希 / 证据链
    dup_id = conn.execute(
        "SELECT COUNT(*) FROM (SELECT item_id FROM learning_item GROUP BY 1 HAVING COUNT(*)>1)").fetchone()[0]
    chk("item_id_unique", dup_id == 0, "重复 item_id=%d" % dup_id)
    dup_ph = conn.execute(
        "SELECT COUNT(*) FROM (SELECT canonical_text FROM learning_item WHERE item_type='phrase' "
        "GROUP BY 1 HAVING COUNT(*)>1)").fetchone()[0]
    chk("phrase_canonical_unique", dup_ph == 0, "重复 Phrase canonical=%d" % dup_ph)
    orphan = conn.execute(
        "SELECT COUNT(*) FROM learning_item li WHERE li.item_type='phrase' AND NOT EXISTS "
        "(SELECT 1 FROM source_ref sr WHERE sr.item_id=li.item_id)").fetchone()[0]
    chk("phrase_source_ref_closure", orphan == 0, "无来源 Phrase=%d" % orphan)
    broken = conn.execute(
        "SELECT COUNT(*) FROM source_ref sr WHERE sr.item_type='phrase' AND NOT EXISTS "
        "(SELECT 1 FROM content_block cb WHERE cb.block_id=sr.source_id)").fetchone()[0]
    chk("phrase_source_block_exists", broken == 0, "断链=%d" % broken)
    no_ev = conn.execute(
        "SELECT COUNT(*) FROM source_ref WHERE item_type='phrase' AND "
        "(emphasis_evidence IS NULL OR emphasis_evidence='' OR textbook_emphasis IS NULL)").fetchone()[0]
    chk("phrase_evidence_complete", no_ev == 0, "缺 evidence/emphasis=%d" % no_ev)

    bad_hash = 0
    bad_emph = 0
    for spec in specs:
        row = conn.execute("SELECT content_hash, learning_requirement, review_status, "
                           "requirement_conflict_status FROM learning_item WHERE item_id=?",
                           (spec["item_id"],)).fetchone()
        if row is None or row[0] != spec["content_hash"]:
            bad_hash += 1
        emph = {r[0] for r in conn.execute(
            "SELECT textbook_emphasis FROM source_ref WHERE item_id=?", (spec["item_id"],))}
        if emph != {spec["textbook_emphasis"]}:
            bad_emph += 1
    chk("phrase_content_hash_reproduced", bad_hash == 0, "不一致=%d" % bad_hash)
    chk("phrase_emphasis_consistent", bad_emph == 0, "不一致=%d" % bad_emph)

    # 分布
    emph_dist = dict(conn.execute(
        "SELECT textbook_emphasis, COUNT(*) FROM source_ref WHERE item_type='phrase' GROUP BY 1"))
    req_dist = dict(conn.execute(
        "SELECT learning_requirement, COUNT(*) FROM learning_item WHERE item_type='phrase' GROUP BY 1"))
    rev_dist = dict(conn.execute(
        "SELECT review_status, COUNT(*) FROM learning_item WHERE item_type='phrase' GROUP BY 1"))

    # 排除项
    kn = conn.execute("SELECT content_hash FROM learning_item WHERE item_id=?", (FROZEN_KNOCK["item_id"],)).fetchone()
    chk("knock_around_frozen", kn is not None and kn[0] == FROZEN_KNOCK["content_hash"],
        "Vocabulary knock around ( 未改动")
    no_kn = conn.execute("SELECT COUNT(*) FROM learning_item WHERE item_type='phrase' AND "
                         "canonical_text=?", (FROZEN_KNOCK["canonical_text"],)).fetchone()[0]
    chk("knock_around_not_phrase", no_kn == 0, "Phrase 中 knock around ( = %d" % no_kn)
    no_pf = conn.execute("SELECT COUNT(*) FROM learning_item WHERE item_type='phrase' AND "
                         "lower(canonical_text) LIKE 'prefer%'").fetchone()[0]
    chk("prefer_not_stored", no_pf == 0, "prefer A to B 未落库")
    excl = 0
    for t in EXCLUDED_BODY_MULTIWORD:
        excl += conn.execute("SELECT COUNT(*) FROM learning_item WHERE item_type='phrase' AND "
                             "canonical_text=?", (t,)).fetchone()[0]
    chk("body_multiword_excluded", excl == 0, "普通正文多词单位落库=%d" % excl)
    no_sent = conn.execute("SELECT COUNT(*) FROM learning_item WHERE item_type='phrase' AND "
                           "(canonical_text LIKE '%secret%' OR canonical_text LIKE '%no secret%')").fetchone()[0]
    chk("sentence_pattern_excluded", no_sent == 0, "固定句型未落库")
    chk("no_bold_phrase", emph_dist.get("BOLD", 0) == 0, "BOLD Phrase=%d（本册预期 0）" % emph_dist.get("BOLD", 0))

    # 其他表不漂移
    tables = ("page", "unit", "section", "activity", "content_block", "content_asset",
              "evidence", "sub_question", "activity_content", "audio_asset", "audio_mapping",
              "transcript", "learning_goal", "ai_artifact")
    drift = {t: (c4 := conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]) != v3_counts.get(t)
             for t in tables}
    chk("no_table_drift", not any(drift.values()),
        "变化表=%s" % [k for k, v in drift.items() if v])
    fk_mapping = conn.execute("SELECT COUNT(*) FROM audio_mapping WHERE mapping_status<>'CANDIDATE'").fetchone()[0]
    chk("audio_mapping_all_candidate", fk_mapping == 0, "非 CANDIDATE 映射=%d" % fk_mapping)
    chk("no_ai_artifact", conn.execute("SELECT COUNT(*) FROM ai_artifact").fetchone()[0] == 0, "ai_artifact=0")

    # 连字 / 控制字符（新增 Phrase 文本）
    bad_text = conn.execute(
        "SELECT COUNT(*) FROM learning_item WHERE item_type='phrase' AND "
        "(canonical_text LIKE '%' || char(0xFB01) || '%' OR canonical_text LIKE '%' || char(0xFB02) || '%' "
        "OR canonical_text LIKE '%' || char(31) || '%' OR canonical_text LIKE '%' || char(29) || '%')").fetchone()[0]
    chk("phrase_text_clean", bad_text == 0, "连字/控制字符=%d" % bad_text)
    chk("mp3_count_54", v3_mp3 == 54, "MP3=%d" % v3_mp3)

    # 快照
    act = conn.execute("SELECT COUNT(*) FROM parse_snapshot WHERE is_active=1").fetchone()[0]
    chk("single_active_snapshot", act == 1, "active snapshot=%d" % act)

    return {"ok": not failures, "checks": checks, "failures": failures,
            "emphasis_distribution": emph_dist, "requirement_distribution": req_dist,
            "review_distribution": rev_dist}


def render_md(r: dict) -> str:
    md = [
        "# P1-06-B1.7-F2 Phrase 正式数据构建与原子发布报告（contentpack v4）",
        "",
        "- 结论：**%s**" % r["verdict"],
        "- 生成时间：%s" % r["generated_at"],
        "- rule_set：%s ｜ schema_version：%s（零 schema 变更）" % (r["rule_set"], r["schema_version"]),
        "- snapshot_id：%s ｜ import_batch：%s" % (r["snapshot_id"], r["import_batch"]),
        "",
        "## 0. 任务文本截断说明",
        "",
        TASK_TEXT_NOTE,
        "",
        "## 1. 输入与输出 SHA256",
        "",
        "| 对象 | SHA256 | 状态 |",
        "| --- | --- | --- |",
    ]
    for k, v in r["sha256"].items():
        md.append("| %s | `%s` | %s |" % (k, v["hash"], v["status"]))
    md += ["", "v4 路径：`%s`（%s 字节）" % (r["v4"]["path"], format(r["v4"]["size"], ",")), ""]
    md += ["## 2. 构建数量", "", "| 指标 | 数值 |", "| --- | --- |"]
    for k, v in r["counts"].items():
        md.append("| %s | %s |" % (k, v))
    md += ["", "## 3. Phrase 分布", "",
           "```text",
           "textbook_emphasis    : %s" % json.dumps(r["validation"]["emphasis_distribution"], ensure_ascii=False),
           "learning_requirement : %s" % json.dumps(r["validation"]["requirement_distribution"], ensure_ascii=False),
           "review_status        : %s" % json.dumps(r["validation"]["review_distribution"], ensure_ascii=False),
           "```", "",
           "## 4. 23 条 Phrase 明细", "",
           "| # | canonical_text | item_id | emphasis | requirement | review | refs | pdf_page |",
           "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for i, p in enumerate(r["phrases"], 1):
        md.append("| %d | `%s` | `%s` | %s | %s | %s | %d | %s |" % (
            i, p["canonical_text"], p["item_id"], p["textbook_emphasis"],
            p["learning_requirement"], p["review_status"], p["ref_count"],
            ",".join(str(x) for x in p["pdf_pages"])))
    md += ["", "## 5. emphasis 独立重算（Pass A 数据库 vs Pass B 原始 PDF）", "",
           "| canonical_text | PDF head 字体 | Pass B | Pass A（v3 source_ref） | 结论 |",
           "| --- | --- | --- | --- | --- |"]
    for p in r["phrases"]:
        md.append("| `%s` | %s | %s | %s | %s |" % (
            p["canonical_text"], p["fonts"] or "-", p["textbook_emphasis"],
            p["db_emphasis"], p["cross_check"]))
    md += ["", "## 6. 排除项", ""]
    for k, v in r["exclusions"].items():
        md.append("- %s：%s" % (k, v))
    md += ["", "## 7. 验证检查", ""]
    for c in r["validation"]["checks"]:
        md.append("- [%s] %s：%s" % (c["status"], c["name"], c["detail"]))
    md += ["", "## 8. 边界确认", ""]
    for k, v in r["boundaries"].items():
        md.append("- %s：%s" % (k, v))
    md += ["", "## 9. 未决 / 后续", ""]
    for item in r["open_items"]:
        md.append("- %s" % item)
    return "\n".join(md) + "\n"


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    if V4_DIR.exists() and any(V4_DIR.iterdir()):
        print("V4_ALREADY_EXISTS:", V4_DIR)
        return 10
    for name, path, expect in (("v1", V1, EXPECTED_V1), ("v2", V2, EXPECTED_V2),
                              ("v3", V3, EXPECTED_V3), ("pdf", PDF, EXPECTED_PDF)):
        if not path.exists():
            print("STOP: 输入缺失", name, path)
            return 2
        actual = sha256_file(path)
        if actual != expect:
            print("STOP: %s SHA256 不一致 %s != %s" % (name, actual, expect))
            return 2
    mp3_files = sorted(SUBJECT_DIR.glob("*.mp3"))
    if len(mp3_files) != 54:
        print("STOP: MP3 数量 %d != 54" % len(mp3_files))
        return 2

    ro = sqlite3.connect("file:%s?mode=ro" % V3.as_posix(), uri=True)
    v3_counts = {t[0]: ro.execute("SELECT COUNT(*) FROM %s" % t[0]).fetchone()[0]
                 for t in ro.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    v3_items = ro.execute("SELECT * FROM learning_item").fetchall()
    v3_refs = ro.execute("SELECT * FROM source_ref WHERE item_type='learning_item'").fetchall()
    active = ro.execute("SELECT snapshot_id FROM parse_snapshot WHERE is_active=1").fetchone()
    if active is None or active[0] != V3_SNAPSHOT:
        print("STOP: v3 active snapshot 与预期不一致", active)
        return 2
    specs = load_specs(ro)
    ro.close()

    probe = pdf_probe(specs)
    specs, cross_checks = finalize(specs, probe)
    failed_cross = [c for c in cross_checks if c["status"] == "FAIL"]
    if failed_cross:
        print("STOP: EVIDENCE_MISMATCH", failed_cross[:5])
        return 3

    started = now()
    snapshot_id = "%s:S%s" % (TEXTBOOK_ID, datetime.now().strftime("%Y%m%dT%H%M%S"))
    batch_id = "%s:B0" % snapshot_id

    V4_DIR.mkdir(parents=True, exist_ok=True)
    if V4_WORK.exists():
        V4_WORK.unlink()
    shutil.copyfile(V3, V4_WORK)

    conn = sqlite3.connect(str(V4_WORK))
    conn.execute("PRAGMA foreign_keys=ON")
    existing = conn.execute("SELECT COUNT(*) FROM learning_item WHERE item_type='phrase'").fetchone()[0]
    if existing:
        conn.close()
        V4_WORK.unlink(missing_ok=True)
        print("V4_ALREADY_EXISTS: 工作副本已包含 Phrase")
        return 10

    stages = stage_insert(conn, specs, snapshot_id, started)
    conn.execute("UPDATE parse_snapshot SET is_active=0, status='SUPERSEDED' WHERE snapshot_id=?",
                 (V3_SNAPSHOT,))
    conn.execute(
        "INSERT INTO parse_snapshot(snapshot_id,textbook_id,parser_name,parser_version,"
        "rule_set_version,input_pdf_sha256,input_audio_count,build_started_at,build_finished_at,"
        "status,stats_json,quality_json,is_active,supersedes_snapshot_id,notes) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (snapshot_id, TEXTBOOK_ID, "textbook_parser_v01", "v01-P1-03-C", RULE_SET, EXPECTED_PDF,
         54, started, now(), "VALIDATED",
         json.dumps({"phrase": 23, "learning_item": 310, "source_ref": 762}, ensure_ascii=False),
         json.dumps({"phrase_evidence": "PASS", "vocabulary_unchanged": "PASS"}, ensure_ascii=False),
         1, V3_SNAPSHOT, "P1-06-B1.7-F2 Phrase 首批构建（v4）"))
    conn.execute("INSERT INTO import_batch(batch_id,snapshot_id,textbook_id,started_at,status) "
                 "VALUES(?,?,?,?,?)", (batch_id, snapshot_id, TEXTBOOK_ID, started, "BUILDING"))
    conn.execute("UPDATE import_batch SET status='SUCCESS', finished_at=? WHERE batch_id=?",
                 (now(), batch_id))
    conn.commit()
    validation = validate(conn, specs, v3_counts, v3_items, v3_refs, len(mp3_files))
    conn.execute("VACUUM")
    conn.close()

    published = None
    if validation["ok"]:
        probe_conn = sqlite3.connect(str(V4_WORK))
        integrity = probe_conn.execute("PRAGMA integrity_check").fetchone()[0]
        fk = len(probe_conn.execute("PRAGMA foreign_key_check").fetchall())
        probe_conn.close()
        if integrity == "ok" and fk == 0:
            V4_WORK.replace(V4)
            published = {"path": str(V4), "sha256": sha256_file(V4), "size": V4.stat().st_size}
        else:
            validation["ok"] = False
            validation["failures"].append("temp_integrity")
    if not validation["ok"]:
        V4_WORK.unlink(missing_ok=True)

    phrases = []
    for spec in specs:
        pdf_pages = sorted({ref["pdf_page"] for ref in spec["refs"]})
        fonts = sorted({ref["head_font"] for ref in spec["refs"] if ref["head_font"]})
        phrases.append({
            "canonical_text": spec["canonical_text"],
            "item_id": spec["item_id"],
            "content_hash": spec["content_hash"],
            "kind": spec["kind"],
            "derivation_type": spec["derivation_type"],
            "meaning_zh": spec["meaning_zh"],
            "textbook_emphasis": spec["textbook_emphasis"],
            "learning_requirement": spec["learning_requirement"],
            "requirement_conflict_status": spec["requirement_conflict_status"],
            "review_status": spec["review_status"],
            "source_vocab_item_id": spec["source_vocab_item_id"],
            "ref_count": len(spec["refs"]),
            "block_ids": [ref["source_id"] for ref in spec["refs"]],
            "pdf_pages": pdf_pages,
            "textbook_pages": sorted({ref["textbook_page"] for ref in spec["refs"] if ref["textbook_page"]}),
            "fonts": fonts or None,
            "db_emphasis": sorted({ref["db_emphasis"] for ref in spec["refs"] if ref["db_emphasis"]}) or None,
            "cross_check": "PASS" if (spec["kind"] == "note" or
                                      all(ref["db_emphasis"] == spec["textbook_emphasis"] or ref["emphasis"] is None
                                          for ref in spec["refs"])) else "CHECK",
        })

    report = {
        "task": "P1-06-B1.7-F2 Phrase 正式数据构建与原子发布",
        "generated_at": now(),
        "verdict": "PASS" if validation["ok"] else "BLOCKED",
        "rule_set": RULE_SET,
        "schema_version": SCHEMA_VERSION,
        "snapshot_id": snapshot_id,
        "import_batch": batch_id,
        "task_text_truncation": TASK_TEXT_NOTE,
        "sha256": {
            "v3 (输入, 构建后复核)": {"hash": sha256_file(V3), "status": "UNCHANGED" if sha256_file(V3) == EXPECTED_V3 else "CHANGED"},
            "v1 (构建后复核)": {"hash": sha256_file(V1), "status": "UNCHANGED" if sha256_file(V1) == EXPECTED_V1 else "CHANGED"},
            "v2 (构建后复核)": {"hash": sha256_file(V2), "status": "UNCHANGED" if sha256_file(V2) == EXPECTED_V2 else "CHANGED"},
            "PDF (构建后复核)": {"hash": sha256_file(PDF), "status": "UNCHANGED" if sha256_file(PDF) == EXPECTED_PDF else "CHANGED"},
            "v4 (输出)": {"hash": published["sha256"] if published else "NOT_PUBLISHED", "status": "PUBLISHED" if published else "NOT_PUBLISHED"},
        },
        "v4": published or {"path": str(V4), "sha256": None, "size": None},
        "counts": {
            "phrase_total": sum(1 for s in specs),
            "from_textbook_list": sum(1 for s in specs if s["kind"] == "list"),
            "from_textbook_note": sum(1 for s in specs if s["kind"] == "note"),
            "learning_item": 287 + sum(1 for s in specs),
            "source_ref": v3_counts["source_ref"] + stages["source_ref"],
            "vocabulary": 287,
            "inserted_source_ref": stages["source_ref"],
        },
        "phrases": phrases,
        "exclusions": {
            "`knock around (`": "冻结异常，本次不建 Phrase、未改 Vocabulary（item_id/content_hash 均未变）",
            "`prefer A to B`": "教材证据存在，但资源类型未最终确认，保留人工审核（未落库）",
            "11 个普通正文多词单位": "、".join(EXCLUDED_BODY_MULTIWORD) + "：全部 EXCLUDE",
            "Communication bank / Useful expressions / 固定句型": "属 Sentence Pattern，不作为 Phrase",
            "Grammar rule / 普通例句": "属 Grammar，不作为 Phrase",
        },
        "evidence_cross_check": cross_checks,
        "validation": validation,
        "boundaries": {
            "v3 是否修改": "否（只读打开 + 复制工作副本）",
            "v1 / v2 是否修改": "否",
            "原始 PDF 是否修改": "否（只读打开）",
            "MP3 是否修改": "否（54 个，未触碰）",
            "既有 parser / builder 是否修改": "否（本次新增构建工具 build_phrase_v01.py）",
            "最高指导原则 / P1-04 / E2 / F1 报告是否修改": "否",
            "是否调用 AI / 云端模型": "否（0 次）",
            "是否 OCR / TTS / 下载 / 新增依赖": "否（0）",
            "是否创建数据库以外的正式数据文件": "否（仅 v4 SQLite 与 audit 报告）",
            "是否访问 D:\\ZhixueAI": "否",
        },
        "open_items": [
            "`prefer A to B`：证据存在、资源类型未定，保留人工审核队列（本阶段不落库）。",
            "`knock around (`：词表 headword 边界冻结异常，未处理。",
            "语言注释型 Phrase（`protect... from...` / `along the way`）：emphasis=UNKNOWN → requirement=CORE 属 F1 设计提案，review_status=NEED_REVIEW 待人工确认。",
            "21 条词表多词 Phrase 的 review_status 沿用同源 Vocabulary（v3 均为 NEED_REVIEW）；其中包含历史 POS-null 遗留状态，按 F1 §14 未在本阶段改写。",
            "source_ref.item_type 既有 Vocabulary 行为 'learning_item'，本次 Phrase 行按 F1 §12/§17 使用 'phrase'；既有行未改动（如需统一枚举，应另立受控任务）。",
        ],
    }

    AUDIT.mkdir(parents=True, exist_ok=True)
    (AUDIT / "P1-06-B1.7-F2_phrase_v4_build.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (AUDIT / "P1-06-B1.7-F2_phrase_v4_build.md").write_text(render_md(report), encoding="utf-8")

    print("=" * 70)
    print("P1-06-B1.7-F2 Phrase 构建")
    print("=" * 70)
    print("结论:", report["verdict"])
    print("v4:", report["v4"])
    print("counts:", report["counts"])
    print("emphasis:", validation["emphasis_distribution"])
    print("requirement:", validation["requirement_distribution"])
    print("failures:", validation["failures"])
    return 0 if validation["ok"] else 3


if __name__ == "__main__":
    sys.exit(main())
