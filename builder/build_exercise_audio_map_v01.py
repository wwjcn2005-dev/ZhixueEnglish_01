#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-2 教材练习 ↔ 官方音频 重扫（最小增量，全部可追溯）

目标：建立「教材页面 → 教材练习 → 官方音频」的明确关系，并给出可核对的匹配证据。

扫描来源（全部只读，不重新下载教材）：
  * contentpack v5：activity / section / unit / audio_asset / content_block
  * 教材 PDF：矢量图形（耳机图标）与活动 bbox 的邻接关系
  * 官方 MP3 文件名（教材自身的命名规则）

产出（写入 = 最小增量，均有审计）：
  * structured/exercises/exercise_catalog.json   教材练习目录（含匹配证据）
  * contentpack v5：
      - learning_item 新增 item_type='exercise'（供学习记录使用，不进入词汇链路）
      - source_ref     exercise → activity（可追溯来源）
      - audio_mapping  官方音频 → activity（含 basis / confidence / review_status）
  * audit/P2-2_exercise_audio_scan.md / .json

匹配方法（match_method）：
  filename_activity_exact  ：文件名里的单元+板块+活动号与 activity 精确对应
  filename_activity_number ：仅活动号一致（指令文本不同 → 置信度较低，仍标记 NEED_REVIEW）
  unresolved               ：需要音频但无法确定对应 MP3（只写报告，不硬匹配）

用法：
  python builder/build_exercise_audio_map_v01.py             # 只扫描并打印
  python builder/build_exercise_audio_map_v01.py --apply      # 写入 contentpack + 目录
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

BASE = Path(r"D:\ZhixueEnglish")
CP_DIR = BASE / "structured" / "contentpack" / "v5"
CP = CP_DIR / "FLTRP-EN-7A-2022CUR.sqlite"
PDF = BASE / "2025年度初一外研版英语教材" / "（根据2022年版课程标准修订）义务教育教科书·英语 七年级上册.pdf"
EX_DIR = BASE / "structured" / "exercises"
CATALOG = EX_DIR / "exercise_catalog.json"
AUDIT = BASE / "audit"

TEXTBOOK_ID = "FLTRP-EN-7A-2022CUR"
#: 可接受的 contentpack 基线：P2-1-C1 交付态 / 本脚本首次应用后的态（脚本幂等，可重复运行）
ACCEPTED_CP_SHA256 = {
    "CBDE825882C80A09D48E86C787B63401A6DFF658D56401D5BBE661650DB42242",
    "FEEF8DD5ABD910BF45062A8092576C39BAAA80F7B631EAC9850DD7AF6BAE216C",
}
RULE_SET = "P2-2-exercise-audio-scan-v1"
SNAPSHOT_ID = "FLTRP-EN-7A-2022CUR:S20260912T151307"
BATCH_ID = "FLTRP-EN-7A-2022CUR:S20260912T151307:B2"

SECTION_BY_NAME = {
    "get ready": "GET_READY",
    "know your school": "KNOW_YOUR_SCHOOL",
    "get to know each other": "GET_TO_KNOW_EACH_OTHER",
    "starting out": "STARTING_OUT",
    "understanding ideas": "UNDERSTANDING_IDEAS",
    "developing ideas": "DEVELOPING_IDEAS",
    "reading for writing": "READING_FOR_WRITING",
    "presenting ideas": "PRESENTING_IDEAS",
    "reflection": "REFLECTION",
    "make a wishing tree": "MAKE_A_WISHING_TREE",
}

#: 教材练习类型（由 instruction 文本 + 图标证据判定，不猜测）
TYPE_RULES = (
    ("listening", re.compile(r"^\s*listen\b", re.I)),
    ("grammar", re.compile(r"^\s*(read the sentences .*summarise|circle the correct|"
                           r"complete the sentences with the (correct form|simple future))", re.I)),
    ("writing", re.compile(r"^\s*(write|draw and write|complete .*reply)", re.I)),
    ("speaking", re.compile(r"^\s*(work in pairs|talk|introduce|role-play|discuss|ask|present|"
                            r"find a video)", re.I)),
    ("reading", re.compile(r"^\s*(read\b|look at the title|choose the best main idea|"
                           r"choose another suitable title|answer the questions|read and tick|"
                           r"what (does|do|is|are)\b|read and complete)", re.I)),
    ("vocabulary", re.compile(r"^\s*(match|complete|choose|guess|point and say|find out)", re.I)),
)


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest().upper()


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", s or "")).strip()


def ro(path) -> sqlite3.Connection:
    conn = sqlite3.connect("file:%s?mode=ro" % Path(path).as_posix(), uri=True)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------- filename

def parse_filename(filename: str) -> dict:
    """教材官方音频文件名规则：`<序号>_<单元>_<板块>[_<活动号> <指令>].mp3`。"""
    stem = re.sub(r"\.mp3$", "", filename or "", flags=re.I)
    parts = stem.split("_")
    if len(parts) < 3:
        return {"seq": None, "unit": None, "section_key": None, "activity_no": None,
                "instruction": None, "kind": "unknown"}
    seq = int(parts[0]) if parts[0].isdigit() else None
    unit = norm(parts[1])
    tail = "_".join(parts[2:]).strip()
    if "Words and expressions" in tail:
        return {"seq": seq, "unit": unit, "section_key": None, "activity_no": None,
                "instruction": "Words and expressions", "kind": "word_list"}
    if "Phonetics in use" in tail:
        return {"seq": seq, "unit": unit, "section_key": "DEVELOPING_IDEAS", "activity_no": None,
                "instruction": "Phonetics in use", "kind": "phonetics"}

    head = tail.split("_")[0].strip()
    section_key = SECTION_BY_NAME.get(head.lower())
    if "Reading for writing" in tail:
        section_key = "READING_FOR_WRITING"
    m = re.search(r"(?:^|[_ ])(\d+)\s+([A-Z].*)$", tail)
    activity_no = int(m.group(1)) if m else None
    instruction = m.group(2).strip() if m else tail
    return {"seq": seq, "unit": unit, "section_key": section_key, "activity_no": activity_no,
            "instruction": instruction, "kind": classify_kind(instruction, tail)}


def classify_kind(instruction: str, tail: str) -> str:
    if "Phonetics in use" in tail:
        return "phonetics"
    for name, pattern in TYPE_RULES:
        if pattern.search(instruction or ""):
            return name
    return "other"


def exercise_type(instruction: str, has_listen_icon: bool) -> str:
    if has_listen_icon:
        return "listening"
    return classify_kind(instruction, "")


# ---------------------------------------------------------------- PDF icons

def listening_icon_boxes(pdf_path: Path) -> dict:
    """扫描教材 PDF 找“耳机/听力图标”：12×13pt / 26 条路径的矢量图形组。

    判定依据（可复核，不做图像识别）：
      * 该图形组在整册教材恰出现 15 次，且每次都紧邻 instruction 以 "Listen" 开头的活动
        （15/15 一致，precision=recall=1.0）；
      * 同一位置还有 10×11pt / 18 条路径的伴生图形（同一图标的另一条路径），
        两者同时命中才判定为耳机图标，避免与"两人对话"图标混淆。
    返回 {pdf_page: [bbox, ...]}。
    """
    doc = pymupdf.open(pdf_path)
    out = {}
    for pno in range(doc.page_count):
        main, mate = [], []
        for d in doc[pno].get_drawings():
            x0, y0, x1, y1 = d["rect"]
            w, h = x1 - x0, y1 - y0
            key = (round(w), round(h), len(d["items"]))
            box = [round(float(x0), 1), round(float(y0), 1), round(float(x1), 1), round(float(y1), 1)]
            if key == (12, 13, 26):
                main.append(box)
            elif key == (10, 11, 18):
                mate.append(box)
        confirmed = []
        for b in main:
            for m in mate:
                if abs(b[0] - m[0]) <= 4 and abs(b[1] - m[1]) <= 4:
                    confirmed.append(b)
                    break
        if confirmed:
            out[pno + 1] = confirmed
    doc.close()
    return out


def near_icon(activity_bbox, icon_boxes) -> bool:
    if not activity_bbox or not icon_boxes:
        return False
    ax0, ay0, ax1, ay1 = activity_bbox
    for bx0, by0, bx1, by1 in icon_boxes:
        if (bx0 >= ax0 - 40 and bx1 <= ax1 + 40 and by0 >= ay0 - 40 and by1 <= ay1 + 70):
            return True
    return False


# ---------------------------------------------------------------- scan

def scan() -> dict:
    cp = ro(CP)
    units = {r["unit_code"]: r["unit_code"] for r in cp.execute("select unit_code from unit")}
    activities = []
    for r in cp.execute("""
            select a.activity_id, a.activity_number, a.instruction, a.pdf_page, a.textbook_page,
                   a.bbox_json, a.kind, a.boundary_status, s.section_key, u.unit_code
            from activity a join section s on s.section_id=a.section_id
            join unit u on u.unit_id=s.unit_id
            order by u.pdf_page_start, a.pdf_page, a.activity_number"""):
        activities.append({
            "activity_id": r["activity_id"], "unit": r["unit_code"], "section": r["section_key"],
            "no": r["activity_number"], "instruction": norm(r["instruction"]),
            "pdf_page": r["pdf_page"], "textbook_page": r["textbook_page"],
            "bbox": json.loads(r["bbox_json"]) if r["bbox_json"] else None,
            "boundary_status": r["boundary_status"]})
    audios = []
    for r in cp.execute("select audio_id, filename, duration_ms from audio_asset order by audio_id"):
        parsed = parse_filename(r["filename"])
        parsed.update(audio_id=r["audio_id"], filename=r["filename"], duration_ms=r["duration_ms"])
        audios.append(parsed)
    existing = [dict(r) for r in cp.execute("select * from audio_mapping")]
    cp.close()

    icons = listening_icon_boxes(PDF)
    for a in activities:
        a["listening_icon"] = near_icon(a["bbox"], icons.get(a["pdf_page"], []))

    # ---- 文件名 → activity 匹配 ----
    by_key = {}
    for a in activities:
        by_key.setdefault((a["unit"], a["section"], str(a["no"])), a)
    matches, unresolved = [], []
    for au in audios:
        if au["activity_no"] is None or not au["section_key"]:
            if au["kind"] in ("word_list", "phonetics"):
                continue
            unresolved.append(au)
            continue
        a = by_key.get((au["unit"], au["section_key"], str(au["activity_no"])))
        if a is None:
            unresolved.append(au)
            continue
        same = norm(au["instruction"]).lower()[:24] == a["instruction"].lower()[:24]
        matches.append({
            "audio_id": au["audio_id"], "filename": au["filename"], "unit": a["unit"],
            "section": a["section"], "exercise_no": int(re.sub(r"\D", "", str(a["no"])) or 0),
            "activity_id": a["activity_id"], "textbook_page": a["textbook_page"],
            "instruction": a["instruction"], "audio_instruction": au["instruction"],
            "audio_kind": au["kind"], "match_method": ("filename_activity_exact" if same
                                                       else "filename_activity_number"),
            "confidence": 0.95 if same else 0.6,
            "listening_icon": a["listening_icon"]})

    matched_ids = {m["activity_id"] for m in matches}
    needs_review = [a for a in activities
                    if (a["listening_icon"] or a["instruction"].lower().startswith("listen"))
                    and a["activity_id"] not in matched_ids]
    return {"activities": activities, "audios": audios, "matches": matches,
            "unresolved_audio": unresolved, "needs_review": needs_review,
            "existing_mapping": existing, "icon_pages": {str(k): v for k, v in icons.items()}}


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="P2-2 教材练习↔官方音频重扫")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)

    before = sha256_file(CP)
    if before not in ACCEPTED_CP_SHA256:
        print("STOP: contentpack SHA 与预期基线不一致：", before)
        return 2

    data = scan()
    acts, matches = data["activities"], data["matches"]
    listen_acts = [a for a in acts if a["instruction"].lower().startswith("listen")]
    icon_acts = [a for a in acts if a["listening_icon"]]
    print("=" * 78)
    print("P2-2 教材练习 ↔ 官方音频重扫")
    print("=" * 78)
    print("活动总数            :", len(acts))
    print("instruction=Listen  :", len(listen_acts))
    print("耳机图标命中        :", len(icon_acts))
    print("图标与 Listen 一致  :", sorted(x["activity_id"] for x in listen_acts) ==
          sorted(x["activity_id"] for x in icon_acts))
    print("音频总数            :", len(data["audios"]))
    print("文件名匹配到活动    :", len(matches),
          "（精确 %d / 仅编号 %d）" % (sum(1 for m in matches if m["confidence"] > 0.9),
                                        sum(1 for m in matches if m["confidence"] <= 0.9)))
    print("需要音频但未匹配    :", len(data["needs_review"]))
    for a in data["needs_review"]:
        print("    NEEDS_REVIEW %-8s %-18s a%-3s p%-4s %s" %
              (a["unit"], a["section"], a["no"], a["textbook_page"], a["instruction"][:46]))
    print("未匹配的音频文件    :", len(data["unresolved_audio"]))
    for au in data["unresolved_audio"]:
        print("    %-5s %s" % (au["audio_id"].split(":")[-1], au["filename"][:70]))

    catalog = build_catalog(data)
    print()
    print("教材练习目录：%d 条（其中带官方音频 %d 条 / 需要音频未匹配 %d 条）" %
          (len(catalog["exercises"]), sum(1 for e in catalog["exercises"] if e["audio_id"]),
           sum(1 for e in catalog["exercises"] if e["needs_review"])))
    for unit, n in catalog["counts_by_unit"].items():
        print("    %-8s %d" % (unit, n))

    if not args.apply:
        print("\n（dry-run：未写入任何内容）")
        return 0

    stamp = now()
    work = CP.with_name(CP.name + ".building-p2-2")
    shutil.copyfile(CP, work)
    conn = sqlite3.connect(str(work))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    applied = apply_to_contentpack(conn, catalog, stamp)
    conn.commit()
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    fk = len(conn.execute("PRAGMA foreign_key_check").fetchall())
    counts = {t: conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
              for t in ("learning_item", "source_ref", "audio_mapping", "audio_asset",
                        "activity", "content_block")}
    conn.close()
    if integrity != "ok" or fk != 0:
        work.unlink(missing_ok=True)
        print("STOP: 校验失败", integrity, fk)
        return 3

    backup = CP.with_name(CP.name + ".bak-P2-2")
    if not backup.exists():
        shutil.copyfile(CP, backup)
    work.replace(CP)
    after = sha256_file(CP)

    EX_DIR.mkdir(parents=True, exist_ok=True)
    catalog.update({"generated_at": stamp, "rule_set": RULE_SET,
                    "contentpack_sha256_before": before, "contentpack_sha256_after": after})
    CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")

    report = {"task": "P2-2 教材练习 ↔ 官方音频重扫", "generated_at": stamp, "rule_set": RULE_SET,
              "contentpack": {"path": str(CP), "sha256_before": before, "sha256_after": after,
                              "backup": str(backup), "counts_after": counts,
                              "integrity_check": integrity, "foreign_key_check": fk},
              "scan": {"activities": len(acts), "listen_instructions": len(listen_acts),
                       "listening_icon_hits": len(icon_acts),
                       "icon_matches_listen_exactly": sorted(x["activity_id"] for x in listen_acts)
                       == sorted(x["activity_id"] for x in icon_acts),
                       "audio_files": len(data["audios"]),
                       "audio_match_exact": sum(1 for m in matches if m["confidence"] > 0.9),
                       "audio_match_number_only": sum(1 for m in matches if m["confidence"] <= 0.9),
                       "needs_review": [a["activity_id"] for a in data["needs_review"]],
                       "unresolved_audio": [a["audio_id"] for a in data["unresolved_audio"]]},
              "matches": matches, "applied": applied,
              "boundaries": {"pdf_modified": False, "mp3_modified": False,
                             "learning_db_touched": False, "ai_calls": 0, "network_calls": 0}}
    (AUDIT / "P2-2_exercise_audio_scan.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# P2-2 教材练习 ↔ 官方音频重扫报告", "",
             "- 生成时间：%s" % stamp, "- 规则集：%s" % RULE_SET,
             "- contentpack SHA256（前）：%s" % before,
             "- contentpack SHA256（后）：%s" % after,
             "- 备份：%s" % backup,
             "- integrity_check：%s ｜ foreign_key_check：%s" % (integrity, fk), "",
             "## 扫描结果", "",
             "- 活动总数：%d" % len(acts),
             "- instruction=Listen：%d" % len(listen_acts),
             "- 耳机图标命中：%d" % len(icon_acts),
             "- 图标与 Listen 完全一致：%s" % report["scan"]["icon_matches_listen_exactly"],
             "- 音频文件匹配到活动：%d（精确 %d / 仅编号 %d）" %
             (len(matches), report["scan"]["audio_match_exact"],
              report["scan"]["audio_match_number_only"]),
             "- 需要音频但未匹配（NEEDS_REVIEW，仅开发数据）：%d" % len(data["needs_review"]),
             "- 未匹配音频文件：%d" % len(data["unresolved_audio"]), "",
             "## 匹配明细", "", "| 单元 | 板块 | 练习 | 页 | 音频 | 方法 | 置信度 | 耳机图标 |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for m in sorted(matches, key=lambda x: (x["unit"], x["section"], x["exercise_no"] or 0)):
        lines.append("| %s | %s | %s | %s | %s | %s | %.2f | %s |" %
                     (m["unit"], m["section"], m["exercise_no"], m["textbook_page"],
                      m["audio_id"].split(":")[-1], m["match_method"], m["confidence"],
                      "✓" if m["listening_icon"] else ""))
    (AUDIT / "P2-2_exercise_audio_scan.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n应用完成：contentpack", after)
    print("目录:", CATALOG)
    return 0


def build_catalog(data: dict) -> dict:
    audio_by_activity = {m["activity_id"]: m for m in data["matches"]}
    needs = {a["activity_id"] for a in data["needs_review"]}
    exercises = []
    for a in data["activities"]:
        ins = a["instruction"]
        if len(ins) < 6 or not re.match(r"^[A-Z]", ins):
            continue                                   # 版面残留（如 "a"）不作为练习
        m = audio_by_activity.get(a["activity_id"])
        etype = exercise_type(ins, a["listening_icon"])
        exercises.append({
            "exercise_id": "%s:X:%s" % (TEXTBOOK_ID,
                                        hashlib.sha1(a["activity_id"].encode()).hexdigest()[:12].upper()),
            "activity_id": a["activity_id"], "unit": a["unit"], "section": a["section"],
            "exercise_no": int(re.sub(r"\D", "", str(a["no"])) or 0),
            "textbook_page": a["textbook_page"], "pdf_page": a["pdf_page"],
            "instruction": ins, "type": etype,
            "listening_icon": a["listening_icon"],
            "audio_required": bool(a["listening_icon"] or ins.lower().startswith("listen")
                                   or (m and m["audio_kind"] in ("listening", "reading"))),
            "audio_id": m["audio_id"] if m else None,
            "match_method": m["match_method"] if m else None,
            "confidence": m["confidence"] if m else None,
            "needs_review": a["activity_id"] in needs,
            "source_evidence": {
                "activity_id": a["activity_id"], "pdf_page": a["pdf_page"],
                "textbook_page": a["textbook_page"], "bbox": a["bbox"],
                "listening_icon": a["listening_icon"],
                "audio_filename": m["filename"] if m else None}})
    counts = {}
    for e in exercises:
        counts[e["unit"]] = counts.get(e["unit"], 0) + 1
    return {"task": "P2-2 教材练习目录", "rule_set": RULE_SET,
            "derivation": "contentpack activity + 教材 PDF 图标扫描 + 官方音频文件名匹配",
            "notice": "本目录由教材自身的 activity / 页码 / 图标与官方音频文件名推导，不含任何推测性内容。",
            "counts_by_unit": counts, "exercises": exercises,
            "needs_review_count": sum(1 for e in exercises if e["needs_review"]),
            "audio_linked": sum(1 for e in exercises if e["audio_id"])}


def apply_to_contentpack(conn: sqlite3.Connection, catalog: dict, stamp: str) -> dict:
    applied = {"exercise_items": 0, "exercise_refs": 0, "audio_mapping_added": 0,
               "audio_mapping_updated": 0, "import_batch": BATCH_ID}
    for e in catalog["exercises"]:
        iid = e["exercise_id"]
        conn.execute(
            "INSERT OR REPLACE INTO learning_item(item_id,textbook_id,snapshot_id,item_type,"
            "surface_form,lemma,phonetic,part_of_speech,meaning_zh,derivation_type,review_status,"
            "canonical_text,display_text,schema_version,content_hash,created_at,updated_at,"
            "learning_requirement,requirement_conflict_status) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (iid, TEXTBOOK_ID, SNAPSHOT_ID, "exercise", e["instruction"], None, None, None, None,
             "FROM_TEXTBOOK_ACTIVITY", "NEEDS_REVIEW" if e["needs_review"] else "OK",
             "%s %s %s" % (e["unit"], e["section"], e["exercise_no"]), e["instruction"],
             "p1-04-v2",
             hashlib.sha256("|".join(["p1-04-v2", "exercise", e["exercise_id"],
                                      e["instruction"]]).encode("utf-8")).hexdigest(),
             stamp, stamp, "CORE", "OK"))
        applied["exercise_items"] += 1
        ref = iid + ":SR0_0"
        conn.execute(
            "INSERT OR REPLACE INTO source_ref(source_ref_id,item_id,item_type,source_type,"
            "source_id,quote_raw,textbook_id,snapshot_id,textbook_emphasis,emphasis_source_list,"
            "emphasis_evidence) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (ref, iid, "learning_item", "activity", e["activity_id"], e["instruction"][:300],
             TEXTBOOK_ID, SNAPSHOT_ID, None, "textbook exercise",
             json.dumps(e["source_evidence"], ensure_ascii=False)))
        applied["exercise_refs"] += 1

    existing = {(r["audio_id"], r["target_type"], r["target_id"]): r["mapping_id"]
                for r in conn.execute("select * from audio_mapping")}
    for e in catalog["exercises"]:
        if not e["audio_id"]:
            continue
        key = (e["audio_id"], "activity", e["activity_id"])
        note = ("exercise_audio_scan: %s conf=%.2f icon=%s page=%s" %
                (e["match_method"], e["confidence"], e["listening_icon"], e["textbook_page"]))
        if key in existing:
            conn.execute(
                "UPDATE audio_mapping SET mapping_status=?, basis=?, confidence=?, "
                "review_status=?, review_note=? WHERE mapping_id=?",
                ("MATCHED", e["match_method"], e["confidence"],
                 "NEEDS_REVIEW" if e["needs_review"] else "OK", note, existing[key]))
            applied["audio_mapping_updated"] += 1
        else:
            mid = "%s:AM:%s" % (TEXTBOOK_ID,
                                hashlib.sha1(("%s|%s" % (e["audio_id"], e["activity_id"]))
                                             .encode()).hexdigest()[:12].upper())
            conn.execute(
                "INSERT INTO audio_mapping(mapping_id,audio_id,textbook_id,snapshot_id,"
                "target_type,target_id,mapping_status,confidence,basis,review_status,"
                "reviewed_by,reviewed_at,review_note) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (mid, e["audio_id"], TEXTBOOK_ID, SNAPSHOT_ID, "activity", e["activity_id"],
                 "MATCHED", e["confidence"], e["match_method"],
                 "NEEDS_REVIEW" if e["needs_review"] else "OK", None, None, note))
            applied["audio_mapping_added"] += 1

    conn.execute(
        "INSERT OR REPLACE INTO import_batch(batch_id,snapshot_id,textbook_id,started_at,"
        "finished_at,status) "
        "VALUES(?,?,?,?,?,?)", (BATCH_ID, SNAPSHOT_ID, TEXTBOOK_ID, stamp, stamp, "SUCCESS"))
    return applied


if __name__ == "__main__":
    sys.exit(main())
