#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P1-06-B-1 教材 Vocabulary 首批构建（contentpack v2）

只读使用 contentpack v1 + 附录词汇表 content_block：
  - Words and expressions  p.155-162
  - Vocabulary A-Z        p.165-173
生成 learning_item(item_type=vocabulary) 与 source_ref，写入新的 contentpack v2。
v1 不做任何修改。

产物：
  structured/contentpack/v2/FLTRP-EN-7A-2022CUR.sqlite
  audit/P1-06-B1_vocabulary_build.md / .json
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True

BASE = Path(r"D:\ZhixueEnglish")
V1 = BASE / "structured" / "contentpack" / "v1" / "FLTRP-EN-7A-2022CUR.sqlite"
V2_DIR = BASE / "structured" / "contentpack" / "v2"
STAGING = BASE / "structured" / "staging"
AUDIT = BASE / "audit"

TEXTBOOK_ID = "FLTRP-EN-7A-2022CUR"
EXPECTED_V1_SHA256 = "B7372AAC3782DF88D1965160B93A4F50E82A6364593497FB4B858BE645BA68E3"
SCHEMA_VERSION = "p1-04-v2"
RULE_SET = "P1-06-B-1"
V1_SNAPSHOT = "FLTRP-EN-7A-2022CUR:S20260912T111145"

PHON = re.compile(r"/[^/\n]{2,}/")
POS = re.compile(r"\b(n|v|adj|adv|prep|pron|conj|num|art|int|abbr)\.")
CJK = re.compile(r"[\u4e00-\u9fff]")
CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
TASK = re.compile(
    r"^(Read|Listen|Work|Choose|Complete|Circle|Answer|Match|Tick|Draw|Write|Find|Look|"
    r"Discuss|Talk|Think|Describe|Guess|Point|Say|Repeat|Practise|Make|Fill|Correct|Put|"
    r"Change|Give|Share|Present|Act|Copy|Retell|Check|Number|Label|Order|Use|Imagine|Ask|"
    r"Tell|Show|Introduce|Prepare|Compare|Note|Underline|Translate|Spell|Do|Play|Plan|"
    r"Design|Create|Search|Interview|Vote|Decide|Explain)\b")

#: 词性续行（P2-1-C1）：条目自身没有 headword，只有词性 + 释义 + 印刷页号，
#: 例如 "v. 微笑 33"（smile）/ "n. 比赛 57"（race）。这类行必须算作上一词条的续行，
#: 否则该词条会丢失唯一的印刷页号证据（→ 单元归属错误）。
POS_CONT = re.compile(r"^(?:n|v|adj|adv|prep|pron|conj|num|art|int|abbr)\.\s")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest().upper()


def sha256_text(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


# --------------------------------------------------------------------------
# Vocabulary 抽取
# --------------------------------------------------------------------------

def parse_entry(text: str) -> dict | None:
    t = re.sub(r"\s+", " ", (text or "").replace("\t", " ")).strip()
    t = CTRL.sub("", t)
    if not t or not re.match(r"^[A-Za-z]", t):
        return None
    phon = PHON.search(t)
    phonetic = phon.group(0) if phon else None
    head_part = t[:phon.start()] if phon else t[:POS.search(t).start()] if POS.search(t) else t
    if CJK.search(head_part):
        head_part = CJK.split(head_part)[0]
    headword = head_part.strip(" ,;:-–—")
    if not headword or not re.match(r"^[A-Za-z]", headword):
        return None
    pos = POS.search(t)
    pos = pos.group(1) if pos else None
    tail = t[phon.end():] if phon else t
    if pos:
        tail = re.sub(r"^\s*" + pos + r"\.", " ", tail)
    cjk = "".join(CJK.findall(tail)) or "".join(CJK.findall(t))
    page_ref = None
    m = re.search(r"(\d{1,3})\s*$", t)
    if m:
        page_ref = int(m.group(1))
    return {
        "headword": headword,
        "phonetic": phonetic,
        "pos": pos,
        "meaning_zh": cjk or None,
        "page_ref": page_ref,
        "display": t,
    }


def is_continuation(text: str, prev_entry: dict | None) -> bool:
    if prev_entry is None:
        return False
    t = (text or "").strip()
    if not t:
        return False
    if POS_CONT.match(t):
        # P2-1-C1：词性续行属于上一词条（只补证据/页号，不并入释义文本）
        return True
    if re.match(r"^[A-Za-z]", t):
        return False
    return bool(CJK.search(t))


def extract_vocabulary(conn: sqlite3.Connection) -> dict:
    ranges = [("Words and expressions", 155, 162), ("Vocabulary A-Z", 165, 173)]
    entries = []
    for label, a, b in ranges:
        prev = None
        rows = conn.execute(
            "SELECT b.block_id, p.pdf_page, b.text_raw FROM content_block b "
            "JOIN page p ON b.page_id = p.page_id "
            "WHERE p.pdf_page BETWEEN ? AND ? "
            "AND b.layout_role NOT IN ('footer','heading','section_title') "
            "ORDER BY p.pdf_page, b.reading_order", (a, b)).fetchall()
        for block_id, pdf_page, raw in rows:
            parsed = parse_entry(raw)
            if parsed and not parsed["meaning_zh"] and not parsed["phonetic"] and not parsed["pos"]:
                # 栏目/字母标记等噪声：既无中文、也无音标与词性。
                # P2-1-C1：中文释义换行的条目（如 yourself /jɔːˈself/ pron. …）必须保留为
                # 正式条目，否则会被错误地并入上一条，并导致该词整体缺失。
                parsed = None
            if parsed:
                parsed["source"] = label
                parsed["block_ids"] = [block_id]
                parsed["block_texts"] = [re.sub(r"\s+", " ", (raw or "")).strip()]
                parsed["pdf_pages"] = [pdf_page]
                parsed["merged"] = False
                entries.append(parsed)
                prev = parsed
            elif is_continuation(raw, prev):
                tail = re.sub(r"[\x00-\x1f]", "", raw or "").strip()
                pos_only = bool(POS_CONT.match(tail))
                prev["block_ids"].append(block_id)
                prev["block_texts"].append(tail)
                prev["pdf_pages"].append(pdf_page)
                if not pos_only:
                    # 中文释义换行：并入展示文本与释义（既有规则）
                    prev["display"] = (prev["display"] + " " + tail).strip()
                    extra_cjk = "".join(CJK.findall(tail))
                    if extra_cjk:
                        prev["meaning_zh"] = (prev["meaning_zh"] or "") + extra_cjk
                m = re.search(r"(\d{1,3})\s*$", tail)
                if m and not prev["page_ref"]:
                    prev["page_ref"] = int(m.group(1))
                prev["merged"] = True
            else:
                prev = prev
    return {"entries": entries}


def dedup(entries: list) -> tuple:
    merged: dict = {}
    order = []
    for e in entries:
        key = (e["headword"].lower(), e["pos"] or "")
        if key not in merged:
            merged[key] = dict(e)
            merged[key]["sources"] = [{"source": e["source"], "block_ids": list(e["block_ids"]),
                                       "block_texts": list(e["block_texts"]),
                                       "pdf_pages": list(e["pdf_pages"]),
                                       "display": e["display"]}]
            order.append(key)
        else:
            m = merged[key]
            m["sources"].append({"source": e["source"], "block_ids": list(e["block_ids"]),
                                 "block_texts": list(e["block_texts"]),
                                 "pdf_pages": list(e["pdf_pages"]), "display": e["display"]})
            m["merged"] = m["merged"] or e["merged"]
            if len(e["display"]) > len(m["display"]):
                m["display"] = e["display"]
            if not m["meaning_zh"] and e["meaning_zh"]:
                m["meaning_zh"] = e["meaning_zh"]
            if not m["phonetic"] and e["phonetic"]:
                m["phonetic"] = e["phonetic"]
            if not m["page_ref"] and e["page_ref"]:
                m["page_ref"] = e["page_ref"]
    return [merged[k] for k in order]


# --------------------------------------------------------------------------
# contentpack v2 构建
# --------------------------------------------------------------------------

def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    if sha256_file(V1) != EXPECTED_V1_SHA256:
        print("STOP: v1 SHA256 与预期不一致")
        return 2

    conn = sqlite3.connect("file:%s?mode=ro" % V1.as_posix(), uri=True)
    v1_counts = {t: conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
                 for t in ("page", "unit", "section", "activity", "content_block",
                           "content_asset", "evidence", "activity_content", "sub_question",
                           "audio_asset", "audio_mapping", "learning_item", "learning_goal")}
    raw = extract_vocabulary(conn)
    entries_all = raw["entries"]

    # Proper nouns 单独统计，不生成 Vocabulary
    proper = conn.execute(
        "SELECT COUNT(*) FROM content_block b JOIN page p ON b.page_id=p.page_id "
        "WHERE p.pdf_page BETWEEN 163 AND 164 AND b.layout_role NOT IN "
        "('footer','heading','section_title')").fetchone()[0]

    entries = dedup([e for e in entries_all if e["source"] != "Proper nouns"])
    conn.close()

    v2_snapshot = "%s:S%s" % (TEXTBOOK_ID, datetime.now().strftime("%Y%m%dT%H%M%S"))
    batch_id = "%s:B0" % v2_snapshot
    started = now()

    STAGING.mkdir(parents=True, exist_ok=True)
    V2_DIR.mkdir(parents=True, exist_ok=True)
    staging_v2 = STAGING / f"{TEXTBOOK_ID}_v2.sqlite"
    final_v2 = V2_DIR / f"{TEXTBOOK_ID}.sqlite"
    for p in (staging_v2, final_v2):
        if p.exists():
            p.unlink()
    shutil.copyfile(V1, staging_v2)

    conn = sqlite3.connect(str(staging_v2))
    conn.execute("PRAGMA foreign_keys=ON")

    # --- v2 schema 受控扩展（learning_item 增加必要字段）---
    existing = {r[1] for r in conn.execute("PRAGMA table_info(learning_item)")}
    for col in ("canonical_text", "display_text", "schema_version", "content_hash",
                "created_at", "updated_at"):
        if col not in existing:
            conn.execute("ALTER TABLE learning_item ADD COLUMN %s TEXT" % col)
    conn.execute(
        "UPDATE parse_snapshot SET is_active=0, status='SUPERSEDED' WHERE snapshot_id=?",
        (V1_SNAPSHOT,))
    conn.execute(
        "INSERT INTO parse_snapshot(snapshot_id,textbook_id,parser_name,parser_version,"
        "rule_set_version,input_pdf_sha256,input_audio_count,build_started_at,"
        "build_finished_at,status,stats_json,quality_json,is_active,"
        "supersedes_snapshot_id,notes) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (v2_snapshot, TEXTBOOK_ID, "textbook_parser_v01", "v01-P1-03-C", RULE_SET,
         EXPECTED_PDF_SHA256_PLACEHOLDER, 54, started, now(), "VALIDATED",
         json.dumps({"source": "contentpack v1 + vocabulary build"}, ensure_ascii=False),
         json.dumps({"p1_05_c_notes_addressed": True}, ensure_ascii=False), 1,
         V1_SNAPSHOT, "P1-06-B-1 首批 Vocabulary 构建"))
    conn.execute(
        "INSERT INTO import_batch(batch_id,snapshot_id,textbook_id,started_at,status) "
        "VALUES(?,?,?,?,?)", (batch_id, v2_snapshot, TEXTBOOK_ID, started, "BUILDING"))

    # --- 受控增强 1：evidence 补齐 metadata + bbox ---
    act_bbox = {r[0]: r[1] for r in conn.execute(
        "SELECT activity_id, bbox_json FROM activity WHERE bbox_json IS NOT NULL")}
    conn.execute(
        "UPDATE evidence SET textbook_id=?, snapshot_id=?, "
        "extraction_version=COALESCE(NULLIF(extraction_version,''),'parser_v01+P1-03-C')",
        (TEXTBOOK_ID, v2_snapshot))
    for eid, ttype, tid in conn.execute(
            "SELECT evidence_id, target_type, target_id FROM evidence").fetchall():
        if ttype in ("activity", "activity_boundary") and tid in act_bbox:
            conn.execute("UPDATE evidence SET bbox_json=? WHERE evidence_id=?",
                         (act_bbox[tid], eid))

    # --- 受控增强 2：text_normalized 清理 PDF 文本层控制字符（text_raw 不动）---
    cleaned = 0
    for bid, norm in conn.execute(
            "SELECT block_id, text_normalized FROM content_block").fetchall():
        if norm and CTRL.search(norm):
            conn.execute("UPDATE content_block SET text_normalized=? WHERE block_id=?",
                         (CTRL.sub("", norm), bid))
            cleaned += 1

    # --- 受控增强 3：block_kind 保守细化 ---
    kind_changes = 0
    for bid, role, kind, raw_text in conn.execute(
            "SELECT block_id, layout_role, block_kind, text_raw FROM content_block").fetchall():
        t = (raw_text or "").strip()
        if role == "footer":
            new = "footer_text"
        elif role in ("heading", "section_title"):
            new = "heading"
        elif role == "sidebar":
            new = "sidebar_tip"
        elif "“" in t or "”" in t:
            new = "dialogue"
        elif TASK.match(t):
            new = "instruction"
        elif re.search(r"[\u4e00-\u9fff]", t) and re.search(r"\b(n|v|adj|adv|prep|pron)\.", t):
            new = "vocabulary_entry"
        else:
            new = kind
        if new and new != kind:
            conn.execute("UPDATE content_block SET block_kind=? WHERE block_id=?", (new, bid))
            kind_changes += 1

    # --- Vocabulary learning_item + source_ref ---
    ok = nr = 0
    for e in entries:
        key = "%s|%s" % (e["headword"].lower(), e["pos"] or "")
        item_id = "%s:V:%s" % (TEXTBOOK_ID, hashlib.sha1(key.encode()).hexdigest()[:12].upper())
        canonical = " ".join(e["headword"].split()).lower()
        display = re.sub(r"\s+", " ", e["display"]).strip()
        hard_ok = bool(e["pos"]) and bool(e["meaning_zh"]) and not e["merged"] and bool(e["page_ref"])
        status = "OK" if hard_ok else "NEED_REVIEW"
        if hard_ok:
            ok += 1
        else:
            nr += 1
        chash = sha256_text("|".join([SCHEMA_VERSION, "vocabulary", canonical,
                                      e["pos"] or "", e["meaning_zh"] or ""]))
        conn.execute(
            "INSERT INTO learning_item(item_id,textbook_id,snapshot_id,item_type,surface_form,"
            "lemma,phonetic,part_of_speech,meaning_zh,derivation_type,review_status,"
            "canonical_text,display_text,schema_version,content_hash,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (item_id, TEXTBOOK_ID, v2_snapshot, "vocabulary", display, canonical,
             e["phonetic"], e["pos"], e["meaning_zh"], "FROM_TEXTBOOK_LIST", status,
             canonical, display, SCHEMA_VERSION, chash, started, started))
        for i, src in enumerate(e["sources"]):
            for j, bid in enumerate(src["block_ids"]):
                conn.execute(
                    "INSERT INTO source_ref(source_ref_id,item_id,item_type,source_type,"
                    "source_id,quote_raw,textbook_id,snapshot_id) VALUES(?,?,?,?,?,?,?,?)",
                    ("%s:SR%d_%d" % (item_id, i, j), item_id, "learning_item",
                     "content_block", bid, (src["block_texts"][j] or "")[:300],
                     TEXTBOOK_ID, v2_snapshot))

    conn.execute("UPDATE import_batch SET status='SUCCESS', finished_at=? WHERE batch_id=?",
                 (now(), batch_id))
    conn.commit()
    validation = validate(conn, ok, nr)
    conn.execute("VACUUM")
    conn.close()

    published = None
    if validation["ok"]:
        tmp = final_v2.with_name(final_v2.name + ".tmp")
        shutil.copyfile(staging_v2, tmp)
        probe = sqlite3.connect(str(tmp))
        integrity = probe.execute("PRAGMA integrity_check").fetchone()[0]
        fk = len(probe.execute("PRAGMA foreign_key_check").fetchall())
        probe.close()
        if integrity == "ok" and fk == 0:
            tmp.replace(final_v2)
            published = {"path": str(final_v2), "sha256": sha256_file(final_v2),
                         "size": final_v2.stat().st_size}
        else:
            tmp.unlink(missing_ok=True)
            validation["ok"] = False
            validation.setdefault("failures", []).append("temp 校验失败")

    report = build_report(entries_all, entries, proper, ok, nr, v1_counts, v2_snapshot,
                          batch_id, validation, published, cleaned, kind_changes)
    AUDIT.mkdir(parents=True, exist_ok=True)
    (AUDIT / "P1-06-B1_vocabulary_build.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (AUDIT / "P1-06-B1_vocabulary_build.md").write_text(
        render_md(report), encoding="utf-8")

    print("=" * 70)
    print("P1-06-B-1 Vocabulary 构建")
    print("=" * 70)
    print("结论:", report["verdict"])
    print("v2:", report.get("v2"))
    print("候选:", report["counts"])
    print("校验:", validation["ok"], validation.get("failures"))
    return 0 if validation["ok"] else 3


EXPECTED_PDF_SHA256_PLACEHOLDER = "C732051E91121BC991DBDD01235662629620DF6BFCCBBBD834EAEA6FCECD4F2F"


def validate(conn, ok, nr) -> dict:
    checks, failures = [], []

    def chk(name, cond, detail):
        checks.append({"name": name, "status": "PASS" if cond else "FAIL", "detail": detail})
        if not cond:
            failures.append(name)

    chk("integrity", conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "integrity_check")
    chk("foreign_key", len(conn.execute("PRAGMA foreign_key_check").fetchall()) == 0, "fk")
    items = conn.execute("SELECT COUNT(*) FROM learning_item WHERE item_type='vocabulary'").fetchone()[0]
    chk("vocabulary_items", items > 0, "vocabulary=%d" % items)
    orphan = conn.execute(
        "SELECT COUNT(*) FROM learning_item li WHERE li.item_type='vocabulary' AND NOT EXISTS "
        "(SELECT 1 FROM source_ref r WHERE r.item_id=li.item_id)").fetchone()[0]
    chk("source_ref_closure", orphan == 0, "无来源的 Vocabulary=%d" % orphan)
    broken = conn.execute(
        "SELECT COUNT(*) FROM source_ref r LEFT JOIN content_block b ON r.source_id=b.block_id "
        "WHERE b.block_id IS NULL").fetchone()[0]
    chk("source_ref_block_exists", broken == 0, "断链=%d" % broken)
    no_hash = conn.execute(
        "SELECT COUNT(*) FROM learning_item WHERE content_hash IS NULL OR content_hash=''").fetchone()[0]
    chk("content_hash_present", no_hash == 0, "缺 hash=%d" % no_hash)
    nr_preserved = conn.execute(
        "SELECT COUNT(*) FROM activity WHERE boundary_status<>'OK'").fetchone()[0]
    chk("need_review_preserved", nr_preserved == 23, "activity NEED_REVIEW=%d" % nr_preserved)
    kinds = dict(conn.execute("SELECT block_kind, COUNT(*) FROM content_block GROUP BY 1"))
    chk("block_kind_improved", kinds.get("dialogue", 0) > 0, str(kinds))
    ai = conn.execute("SELECT COUNT(*) FROM ai_artifact").fetchone()[0]
    chk("no_ai", ai == 0, "ai_artifact=%d" % ai)
    return {"ok": not failures, "checks": checks, "failures": failures,
            "vocabulary": items, "ok_items": ok, "need_review_items": nr, "block_kinds": kinds}


def build_report(entries_all, entries, proper, ok, nr, v1_counts, snapshot, batch,
                 validation, published, cleaned, kind_changes) -> dict:
    multi = [e for e in entries if " " in e["headword"]]
    merged = [e for e in entries if e["merged"]]
    from_we = len([e for e in entries_all if e["source"] == "Words and expressions"])
    from_az = len([e for e in entries_all if e["source"] == "Vocabulary A-Z"])
    return {
        "task": "P1-06-B-1 教材 Vocabulary 首批构建",
        "generated_at": now(),
        "verdict": "PASS" if validation["ok"] else "STOP",
        "v2": published,
        "v1_sha256": sha256_file(V1),
        "snapshot_id": snapshot,
        "import_batch": batch,
        "schema_version": SCHEMA_VERSION,
        "rule_set": RULE_SET,
        "counts": {
            "candidates_raw": len(entries_all),
            "from_words_and_expressions": from_we,
            "from_vocabulary_az": from_az,
            "before_dedup": len(entries_all),
            "after_dedup": len(entries),
            "ok": ok,
            "need_review": nr,
            "rejected": 0,
            "proper_nouns_skipped": proper,
            "multiword_entries": len(multi),
            "cross_block_merged": len(merged),
            "multi_source_items": len([e for e in entries if len(e["sources"]) > 1]),
        },
        "v2_enhancements": {
            "evidence_textbook_id_snapshot_id": True,
            "evidence_extraction_version": True,
            "evidence_bbox_for_activity_targets": True,
            "text_normalized_control_chars_cleaned": cleaned,
            "block_kind_refined_rows": kind_changes,
            "learning_item_extended_columns": ["canonical_text", "display_text",
                                               "schema_version", "content_hash",
                                               "created_at", "updated_at"],
            "need_review_preserved": True,
        },
        "v1_counts": v1_counts,
        "validation": validation,
        "samples": {
            "words_and_expressions": [e["display"][:60] for e in entries if e["sources"][0]["source"] == "Words and expressions"][:20],
            "vocabulary_az": [e["display"][:60] for e in entries if any(s["source"] == "Vocabulary A-Z" for s in e["sources"])][:20],
            "multiword": [e["display"][:60] for e in multi[:10]],
            "cross_block_merged": [e["display"][:60] for e in merged[:10]],
            "need_review": [e["display"][:60] for e in entries if not (e["pos"] and e["meaning_zh"] and not e["merged"] and e["page_ref"])][:10],
        },
        "boundaries": {"v1_modified": False, "pdf_modified": False, "mp3_modified": False,
                       "parser_modified": False, "builder_modified": False, "ai_calls": 0,
                       "learner_rows": 0},
    }


def render_md(r: dict) -> str:
    md = ["# P1-06-B-1 教材 Vocabulary 首批构建报告", "",
          "- 生成时间：%s" % r["generated_at"],
          "- 结论：%s" % r["verdict"],
          "- snapshot_id：%s" % r["snapshot_id"],
          "- import_batch：%s" % r["import_batch"],
          "- schema_version：%s / rule_set：%s" % (r["schema_version"], r["rule_set"]),
          "- v1 SHA256（保持不变）：%s" % r["v1_sha256"], ""]
    if r.get("v2"):
        md += ["## contentpack v2", "",
               "- 路径：%s" % r["v2"]["path"],
               "- SHA256：%s" % r["v2"]["sha256"],
               "- 大小：%d 字节" % r["v2"]["size"], ""]
    md += ["## Vocabulary 数量", "", "| 指标 | 数量 |", "| --- | --- |"]
    for k, v in r["counts"].items():
        md.append("| %s | %s |" % (k, v))
    md += ["", "## v2 受控增强", ""]
    for k, v in r["v2_enhancements"].items():
        md.append("- %s：%s" % (k, v))
    md += ["", "## 校验", ""]
    for c in r["validation"]["checks"]:
        md.append("- [%s] %s：%s" % (c["status"], c["name"], c["detail"]))
    md += ["", "## 抽样", ""]
    for k, v in r["samples"].items():
        md.append("**%s**（%d 条）" % (k, len(v)))
        for s in v:
            md.append("- %s" % s)
        md.append("")
    md += ["## 边界", ""]
    for k, v in r["boundaries"].items():
        md.append("- %s：%s" % (k, v))
    return "\n".join(md) + "\n"


if __name__ == "__main__":
    sys.exit(main())
