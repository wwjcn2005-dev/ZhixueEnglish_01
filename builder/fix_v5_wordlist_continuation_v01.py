#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-1-C1 数据修正：contentpack v5 词表续行缺失修正（yourself / smile）

背景（P2-01 报告 C1-02）：
  * 教材 Starter 词表存在 `yourself`，但 v5 里没有这条 learning_item；
  * Unit 2 词表的 `smile` 被错误归属到 Appendix。

根因（builder/build_vocabulary_v01.py 的词表抽取规则）：
  1. 条目行若自身没有中文（中文释义换到下一行），会被当作噪声丢弃
     —— `yourself /jɔːˈself/ pron. (pl. yourselves)` 就是这样丢的；
     紧随其后的续行 `你自己 9` 又被并入上一条 `introduce`，污染了它的释义与展示文本；
  2. 只有词性标记的续行（`v. 微笑 33` / `n. 比赛 57`）既不是条目、也不被当作续行，
     于是 `smile` 失去了唯一的印刷页号证据，只能退回 PDF 页 → 被归到 Appendix。

本脚本只做**最小、可追溯**的数据修正（不改 schema、不动其它行）：
  1. 新增 `yourself`（BOLD → CORE，词性/音标/释义/页号全部来自教材原件）；
  2. 修正 `introduce` / `yard` 被错误并入的 `你自己 9`；
  3. 给 `smile` 补上属于它自己的续行 source_ref（`v. 微笑 33`），恢复 Unit 2 归属。

用法：
  python builder/fix_v5_wordlist_continuation_v01.py            # 只计算并打印修正计划
  python builder/fix_v5_wordlist_continuation_v01.py --apply     # 应用（先备份，再原子发布）

产物：
  structured/contentpack/v5/FLTRP-EN-7A-2022CUR.sqlite               （修正后）
  structured/contentpack/v5/FLTRP-EN-7A-2022CUR.sqlite.bak-P2-1-C1   （修正前备份）
  audit/P2-1-C1_contentpack_wordlist_fix.md / .json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

import pymupdf

sys.dont_write_bytecode = True

BASE = Path(r"D:\ZhixueEnglish")
V5 = BASE / "structured" / "contentpack" / "v5" / "FLTRP-EN-7A-2022CUR.sqlite"
PDF = BASE / "2025年度初一外研版英语教材" / "（根据2022年版课程标准修订）义务教育教科书·英语 七年级上册.pdf"
AUDIT = BASE / "audit"

EXPECTED_V5_SHA256 = "FF3FD568F4DA5348DB1F9DE7D68818CBEFD6A7E36A67C68EEF7F8386F4CE452A"
TEXTBOOK_ID = "FLTRP-EN-7A-2022CUR"
SCHEMA_VERSION = "p1-04-v2"
RULE_SET = "P2-1-C1"
BATCH_ID = "FLTRP-EN-7A-2022CUR:S20260912T151307:B1"
SNAPSHOT_ID = "FLTRP-EN-7A-2022CUR:S20260912T151307"

FONT_BOLD_MARK = "Medium"
FONT_PLAIN_MARK = "Regula"
POS_SPAN = re.compile(r"^(?:n|v|adj|adv|prep|pron|conj|num|art|int|abbr)\.$")
LATIN_HEAD = re.compile(r"^[A-Za-z]")


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


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", s or "")).strip()


def item_id_for(headword: str, pos: str | None) -> str:
    key = "%s|%s" % (headword.lower(), pos or "")
    return "%s:V:%s" % (TEXTBOOK_ID, hashlib.sha1(key.encode()).hexdigest()[:12].upper())


def content_hash_for(canonical: str, pos: str | None, meaning: str | None) -> str:
    return sha256_text("|".join([SCHEMA_VERSION, "vocabulary", canonical, pos or "",
                                 meaning or ""]))


def block_text(conn: sqlite3.Connection, block_id: str) -> str:
    row = conn.execute("SELECT text_raw FROM content_block WHERE block_id=?", (block_id,)).fetchone()
    if row is None:
        raise SystemExit("STOP: 找不到 block %s" % block_id)
    return (row[0] or "")


def block_page(conn: sqlite3.Connection, block_id: str) -> tuple[int, int | None]:
    row = conn.execute(
        "SELECT p.pdf_page, p.textbook_page FROM content_block b JOIN page p ON p.page_id=b.page_id "
        "WHERE b.block_id=?", (block_id,)).fetchone()
    if row is None:
        raise SystemExit("STOP: 找不到 block 页面 %s" % block_id)
    return row[0], row[1]


def head_span_evidence(pdf_page: int, text: str) -> dict:
    """按 v3 的同一条规则读取 head span 字体证据（Medium=BOLD，Regula=PLAIN）。"""
    doc = pymupdf.open(PDF)
    try:
        target = norm(text)
        for b in doc[pdf_page - 1].get_text("dict")["blocks"]:
            if b.get("type") != 0:
                continue
            t = norm("".join(s["text"] for l in b.get("lines", []) for s in l.get("spans", [])))
            if t != target:
                continue
            for s in [s for l in b.get("lines", []) for s in l.get("spans", []) if s["text"].strip()]:
                st = norm(s["text"])
                if not LATIN_HEAD.match(st) or POS_SPAN.match(st):
                    continue
                font = s["font"]
                emph = ("BOLD" if FONT_BOLD_MARK in font
                        else "PLAIN" if FONT_PLAIN_MARK in font else "UNKNOWN")
                return {"font_name": font, "flags": int(s["flags"]),
                        "size": round(float(s["size"]), 1),
                        "span_bbox": [round(float(x), 1) for x in s["bbox"]],
                        "emphasis": emph}
            raise SystemExit("STOP: PDF 中找不到 head span：%s" % target)
    finally:
        doc.close()
    raise SystemExit("STOP: PDF 中找不到 block：pdf=%d %r" % (pdf_page, text))


def build_plan(conn: sqlite3.Connection) -> dict:
    """计算修正计划（只读，不改任何东西）。"""
    plan = {"operations": [], "new_item": None, "evidence": {}}

    # ---- 1. yourself：教材原件证据 ----
    we_head = "FLTRP-EN-7A-2022CUR:P155:B30"
    we_cont = "FLTRP-EN-7A-2022CUR:P155:B31"
    az_head = "FLTRP-EN-7A-2022CUR:P173:B17"
    az_cont = "FLTRP-EN-7A-2022CUR:P173:B18"
    for bid in (we_head, we_cont, az_head, az_cont):
        if conn.execute("SELECT 1 FROM content_block WHERE block_id=?", (bid,)).fetchone() is None:
            raise SystemExit("STOP: 缺少教材 block %s" % bid)

    if conn.execute("SELECT 1 FROM learning_item WHERE item_id=? OR canonical_text='yourself'",
                    (item_id_for("yourself", "pron"),)).fetchone():
        raise SystemExit("STOP: yourself 已存在，本修正不重复执行")

    we_text = norm(block_text(conn, we_head))
    az_text = norm(block_text(conn, az_head))
    we_ev = head_span_evidence(block_page(conn, we_head)[0], we_text)
    az_ev = head_span_evidence(block_page(conn, az_head)[0], az_text)
    if we_ev["emphasis"] != az_ev["emphasis"]:
        raise SystemExit("STOP: yourself 两个来源字重冲突 %s / %s"
                         % (we_ev["emphasis"], az_ev["emphasis"]))

    display = (we_text + " " + norm(block_text(conn, we_cont))).strip()
    plan["new_item"] = {
        "item_id": item_id_for("yourself", "pron"),
        "canonical_text": "yourself",
        "surface_form": display,
        "display_text": display,
        "lemma": "yourself",
        "phonetic": "/jɔːˈself/",
        "part_of_speech": "pron",
        "meaning_zh": "你自己",
        "from_block": we_head,
        "page_ref": 9,
        "textbook_emphasis": we_ev["emphasis"],
        "learning_requirement": "CORE" if we_ev["emphasis"] == "BOLD" else (
            "RECOGNITION" if we_ev["emphasis"] == "PLAIN" else "NEED_REVIEW"),
        "review_status": "NEED_REVIEW",   # 与同规则跨行条目（如 together）一致：跨块合并标记
        "requirement_conflict_status": "OK",
    }
    plan["evidence"]["yourself"] = {"we": we_ev, "az": az_ev}

    # ---- 2. 被污染的条目 ----
    for canonical, block_id, cont_block in (("introduce", "FLTRP-EN-7A-2022CUR:P155:B29", we_cont),
                                            ("yard", "FLTRP-EN-7A-2022CUR:P161:B7", az_cont)):
        row = conn.execute("SELECT item_id, meaning_zh, display_text, surface_form FROM learning_item "
                           "WHERE canonical_text=? AND item_type='vocabulary'", (canonical,)).fetchone()
        if row is None:
            raise SystemExit("STOP: 找不到条目 %s" % canonical)
        raw = norm(block_text(conn, block_id))
        clean_meaning = "".join(re.findall(r"[\u4e00-\u9fff]", raw))
        plan["operations"].append({
            "op": "update_item",
            "item_id": row[0], "canonical_text": canonical,
            "part_of_speech": conn.execute(
                "SELECT part_of_speech FROM learning_item WHERE item_id=?",
                (row[0],)).fetchone()[0],
            "old": {"meaning_zh": row[1], "display_text": row[2], "surface_form": row[3]},
            "new": {"meaning_zh": clean_meaning, "display_text": raw, "surface_form": raw},
            "drop_ref_to": cont_block,
        })

    # ---- 3. smile：补回属于它的续行 ref（恢复教材页号证据） ----
    smile = conn.execute("SELECT item_id FROM learning_item WHERE canonical_text='smile' AND "
                         "item_type='vocabulary'").fetchone()
    if smile is None:
        raise SystemExit("STOP: 找不到 smile")
    plan["operations"].append({
        "op": "add_ref",
        "item_id": smile[0], "canonical_text": "smile",
        "refs": [("SR0_1", "FLTRP-EN-7A-2022CUR:P157:B15", "Words and expressions"),
                 ("SR1_1", "FLTRP-EN-7A-2022CUR:P171:B46", "Vocabulary A-Z")],
    })
    plan["smile_item_id"] = smile[0]
    return plan


def ref_evidence(ev: dict, head_block: str, pdf_page: int, textbook_page: int,
                 bbox: list) -> str:
    payload = {
        "font_name": ev["font_name"],
        "flags": ev["flags"],
        "size": ev["size"],
        "pdf_page": pdf_page,
        "textbook_page": textbook_page,
        "bbox": bbox,
        "head_block": head_block,
        "context_type": "textbook_vocabulary_entry",
    }
    return json.dumps(payload, ensure_ascii=False)


def apply_plan(conn: sqlite3.Connection, plan: dict, stamp: str) -> dict:
    applied = {"inserted_items": [], "updated_items": [], "inserted_refs": [],
               "deleted_refs": []}

    # 1) yourself
    ni = plan["new_item"]
    conn.execute(
        "INSERT INTO learning_item(item_id,textbook_id,snapshot_id,item_type,surface_form,lemma,"
        "phonetic,part_of_speech,meaning_zh,derivation_type,review_status,canonical_text,"
        "display_text,schema_version,content_hash,created_at,updated_at,learning_requirement,"
        "requirement_conflict_status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (ni["item_id"], TEXTBOOK_ID, "FLTRP-EN-7A-2022CUR:S20260912T113441", "vocabulary",
         ni["surface_form"], ni["lemma"], ni["phonetic"], ni["part_of_speech"], ni["meaning_zh"],
         "FROM_TEXTBOOK_LIST", ni["review_status"], ni["canonical_text"], ni["display_text"],
         SCHEMA_VERSION, content_hash_for(ni["canonical_text"], ni["part_of_speech"],
                                          ni["meaning_zh"]),
         stamp, stamp, ni["learning_requirement"], ni["requirement_conflict_status"]))
    applied["inserted_items"].append(ni["item_id"])

    we_ev = plan["evidence"]["yourself"]["we"]
    az_ev = plan["evidence"]["yourself"]["az"]
    we_page, we_tb = block_page(conn, "FLTRP-EN-7A-2022CUR:P155:B30")
    az_page, az_tb = block_page(conn, "FLTRP-EN-7A-2022CUR:P173:B17")
    refs = [
        ("SR0_0", "FLTRP-EN-7A-2022CUR:P155:B30", "Words and expressions", we_ev,
         "FLTRP-EN-7A-2022CUR:P155:B30", we_page, we_tb, we_ev["span_bbox"]),
        ("SR0_1", "FLTRP-EN-7A-2022CUR:P155:B31", "Words and expressions", we_ev,
         "FLTRP-EN-7A-2022CUR:P155:B30", we_page, we_tb, we_ev["span_bbox"]),
        ("SR1_0", "FLTRP-EN-7A-2022CUR:P173:B17", "Vocabulary A-Z", az_ev,
         "FLTRP-EN-7A-2022CUR:P173:B17", az_page, az_tb, az_ev["span_bbox"]),
        ("SR1_1", "FLTRP-EN-7A-2022CUR:P173:B18", "Vocabulary A-Z", az_ev,
         "FLTRP-EN-7A-2022CUR:P173:B17", az_page, az_tb, az_ev["span_bbox"]),
    ]
    for suffix, block_id, listing, ev, head_block, pdf_page, tb_page, bbox in refs:
        sid = "%s:%s" % (ni["item_id"], suffix)
        conn.execute(
            "INSERT INTO source_ref(source_ref_id,item_id,item_type,source_type,source_id,"
            "quote_raw,textbook_id,snapshot_id,textbook_emphasis,emphasis_source_list,"
            "emphasis_evidence) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (sid, ni["item_id"], "learning_item", "content_block", block_id,
             norm(block_text(conn, block_id))[:300], TEXTBOOK_ID,
             "FLTRP-EN-7A-2022CUR:S20260912T113441", ev["emphasis"], listing,
             ref_evidence(ev, head_block, pdf_page, tb_page, bbox)))
        applied["inserted_refs"].append(sid)

    # 2) introduce / yard
    for op in plan["operations"]:
        if op["op"] != "update_item":
            continue
        conn.execute(
            "UPDATE learning_item SET meaning_zh=?, display_text=?, surface_form=?, "
            "content_hash=?, updated_at=? WHERE item_id=?",
            (op["new"]["meaning_zh"], op["new"]["display_text"], op["new"]["surface_form"],
             content_hash_for(op["canonical_text"], op["part_of_speech"],
                              op["new"]["meaning_zh"]), stamp, op["item_id"]))
        applied["updated_items"].append(op["item_id"])
        cur = conn.execute("DELETE FROM source_ref WHERE item_id=? AND source_id=?",
                           (op["item_id"], op["drop_ref_to"]))
        if cur.rowcount:
            applied["deleted_refs"].append("%s -> %s" % (op["item_id"], op["drop_ref_to"]))

    # 3) smile 续行证据
    for op in plan["operations"]:
        if op["op"] != "add_ref":
            continue
        head_emph = conn.execute(
            "SELECT textbook_emphasis FROM source_ref WHERE item_id=? ORDER BY source_ref_id LIMIT 1",
            (op["item_id"],)).fetchone()[0]
        for suffix, block_id, listing in op["refs"]:
            sid = "%s:%s" % (op["item_id"], suffix)
            if conn.execute("SELECT 1 FROM source_ref WHERE source_ref_id=?", (sid,)).fetchone():
                continue
            head_block = conn.execute(
                "SELECT source_id, emphasis_evidence FROM source_ref WHERE item_id=? "
                "ORDER BY source_ref_id LIMIT 1", (op["item_id"],)).fetchone()
            ev = json.loads(head_block[1]) if head_block[1] else {}
            pdf_page, tb_page = block_page(conn, block_id)
            ev["pdf_page"], ev["textbook_page"] = pdf_page, tb_page
            ev["head_block"] = head_block[0]
            conn.execute(
                "INSERT INTO source_ref(source_ref_id,item_id,item_type,source_type,source_id,"
                "quote_raw,textbook_id,snapshot_id,textbook_emphasis,emphasis_source_list,"
                "emphasis_evidence) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (sid, op["item_id"], "learning_item", "content_block", block_id,
                 norm(block_text(conn, block_id))[:300], TEXTBOOK_ID,
                 "FLTRP-EN-7A-2022CUR:S20260912T113441", head_emph, listing,
                 json.dumps(ev, ensure_ascii=False)))
            applied["inserted_refs"].append(sid)

    # 4) import_batch 记录（可追溯）
    conn.execute(
        "INSERT INTO import_batch(batch_id,snapshot_id,textbook_id,started_at,finished_at,status) "
        "VALUES(?,?,?,?,?,?)",
        (BATCH_ID, SNAPSHOT_ID, TEXTBOOK_ID, stamp, stamp, "SUCCESS"))
    applied["import_batch"] = BATCH_ID
    return applied


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="P2-1-C1 contentpack v5 词表续行修正")
    ap.add_argument("--apply", action="store_true", help="应用修正（默认只打印计划）")
    args = ap.parse_args(argv)

    before = sha256_file(V5)
    if before != EXPECTED_V5_SHA256:
        print("STOP: v5 SHA256 与预期基线不一致")
        print("  期望:", EXPECTED_V5_SHA256)
        print("  实际:", before)
        return 2

    ro = sqlite3.connect("file:%s?mode=ro" % V5.as_posix(), uri=True)
    plan = build_plan(ro)
    counts_before = {t: ro.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
                     for t in ("learning_item", "source_ref", "content_block", "audio_asset",
                               "import_batch")}
    ro.close()

    print("=" * 74)
    print("P2-1-C1 contentpack v5 词表续行修正")
    print("=" * 74)
    print("v5 SHA256（修正前）:", before)
    print("新增条目 :", plan["new_item"]["item_id"], plan["new_item"]["canonical_text"],
          plan["new_item"]["textbook_emphasis"], plan["new_item"]["learning_requirement"])
    for op in plan["operations"]:
        if op["op"] == "update_item":
            print("修正条目 :", op["canonical_text"], "|",
                  op["old"]["meaning_zh"], "->", op["new"]["meaning_zh"])
        else:
            print("补来源   :", op["canonical_text"], [r[1] for r in op["refs"]])
    if not args.apply:
        print("\n（dry-run：未写入任何内容；加 --apply 才会应用）")
        return 0

    stamp = now()
    work = V5.with_name(V5.name + ".building-p2-1-c1")
    backup = V5.with_name(V5.name + ".bak-P2-1-C1")
    if work.exists():
        work.unlink()
    shutil.copyfile(V5, work)

    conn = sqlite3.connect(str(work))
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        applied = apply_plan(conn, plan, stamp)
        conn.commit()
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        fk = len(conn.execute("PRAGMA foreign_key_check").fetchall())
        counts_after = {t: conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
                        for t in counts_before}
        # 只允许计划内的行发生变化（修正前后 learning_item 全表逐行比较）
        base = sqlite3.connect("file:%s?mode=ro" % V5.as_posix(), uri=True)
        old_rows = {r[0]: r[1:] for r in base.execute(
            "SELECT item_id, meaning_zh, display_text, surface_form, content_hash, updated_at "
            "FROM learning_item")}
        base.close()
        changed = []
        for r in conn.execute("SELECT item_id, meaning_zh, display_text, surface_form, "
                              "content_hash, updated_at FROM learning_item ORDER BY item_id"):
            prev = old_rows.get(r[0])
            if prev is None:
                changed.append((r[0], "ADDED"))
            elif tuple(prev) != tuple(r[1:]):
                changed.append((r[0], "UPDATED"))
        allowed = {plan["new_item"]["item_id"]} | {op["item_id"] for op in plan["operations"]
                                                   if op["op"] == "update_item"}
        unexpected = [c for c in changed if c[0] not in allowed]
        conn.execute("VACUUM")
    finally:
        conn.close()

    if integrity != "ok" or fk != 0 or unexpected:
        work.unlink(missing_ok=True)
        print("STOP: 校验失败", integrity, fk, unexpected)
        return 3

    if not backup.exists():
        shutil.copyfile(V5, backup)
    work.replace(V5)
    after = sha256_file(V5)
    result = {
        "task": "P2-1-C1 contentpack v5 词表续行修正",
        "generated_at": now(),
        "rule_set": RULE_SET,
        "v5_path": str(V5),
        "sha256_before": before,
        "sha256_after": after,
        "backup": str(backup),
        "snapshot_id": SNAPSHOT_ID,
        "import_batch": BATCH_ID,
        "plan": plan,
        "applied": applied,
        "counts_before": counts_before,
        "counts_after": counts_after,
        "changed_rows": changed,
        "unexpected_changes": unexpected,
        "integrity_check": integrity,
        "foreign_key_check": fk,
        "pdf": str(PDF),
        "boundaries": {"schema_changed": False, "pdf_modified": False, "mp3_modified": False,
                       "learning_db_touched": False, "ai_calls": 0},
    }
    AUDIT.mkdir(parents=True, exist_ok=True)
    (AUDIT / "P2-1-C1_contentpack_wordlist_fix.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# P2-1-C1 contentpack v5 词表续行修正报告", "",
             "- 生成时间：%s" % result["generated_at"],
             "- 规则集：%s" % RULE_SET,
             "- v5 SHA256（前）：%s" % before,
             "- v5 SHA256（后）：%s" % after,
             "- 备份：%s" % backup,
             "- integrity_check：%s ｜ foreign_key_check：%s" % (integrity, fk), "",
             "## 行数变化", "", "| 表 | 前 | 后 |", "| --- | --- | --- |"]
    for t in counts_before:
        lines.append("| %s | %s | %s |" % (t, counts_before[t], counts_after[t]))
    lines += ["", "## 变更行", ""]
    for c in changed:
        lines.append("- %s：%s" % (c[0], c[1]))
    lines += ["", "## 边界", ""]
    for k, v in result["boundaries"].items():
        lines.append("- %s：%s" % (k, v))
    (AUDIT / "P2-1-C1_contentpack_wordlist_fix.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")

    print("\n应用完成")
    print("  v5 SHA256（后）:", after)
    print("  备份           :", backup)
    print("  行数变化       :", {t: (counts_before[t], counts_after[t]) for t in counts_before})
    print("  变更行         :", changed)
    print("  integrity/fk   :", integrity, fk)
    return 0


if __name__ == "__main__":
    sys.exit(main())
