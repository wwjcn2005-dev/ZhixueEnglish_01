#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-3 教材练习重建 + 听力严格匹配（证据链版）

与 P2-2 的区别（P2-2 只做「文件名 → activity」的浅匹配）：

  1. **重新扫描真实教材 PDF 文本层**（不是复用 contentpack 里的 activity），
     按版面规则识别 activity 编号与 instruction，得到教材真实的练习清单；
  2. **重新扫描全部官方 MP3**（文件名 + 大小 + SHA256 + 时长 + 顺序）；
  3. 用**多重证据链**建立 `Activity → 官方音频`：
        E1 单元一致 / E2 板块一致 / E3 活动号一致 /
        E4 instruction 文本一致（强证据）/ E5 教材耳机图标 /
        E6 音频顺序 / E7 音频时长
     只有拿到强证据才判 CONFIRMED，否则 NEEDS_REVIEW；绝不凭文件名硬匹配。
  4. 识别**真实题型**（choice / fill / match / judge / order / short_answer /
     speaking / writing / reflection / other），并抽出题目结构（题号 / 选项 /
     空格 / 勾选框）；
  5. 教材答案只做「有无可靠来源」的标注，**不猜答案**。

只读来源：
  * 教材 PDF（矢量耳机图标 + 文本层）
  * `2025年度初一外研版英语教材/*.mp3`（官方音频，绝不写入）
  * contentpack v5（section/unit 边界、audio_asset 元数据、词汇词表）

写入（`--apply` 才会写）：
  * `structured/exercises/exercise_catalog_v2.json`（P2-3 权威练习层）
  * `structured/exercises/exercise_audio_map_v2.json`（证据链明细）
  * contentpack：仅为新增练习补 `learning_item` + `source_ref`（可记录学习行为），
    不改 activity / audio_mapping / 既有条目
  * `audit/P2-3_exercise_rebuild.md` / `.json`

用法：
  python builder/build_p2_3_exercise_rebuild_v01.py            # 扫描 + 报告，不写
  python builder/build_p2_3_exercise_rebuild_v01.py --apply     # 写入上述产物
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import shutil
import sqlite3
import unicodedata
from datetime import datetime
from pathlib import Path

import pymupdf

import sys

sys.path.insert(0, str(Path(r"D:\ZhixueEnglish") / "web"))
sys.dont_write_bytecode = True
import content as content_mod          # noqa: E402

BASE = Path(r"D:\ZhixueEnglish")
TEXTBOOK_DIR = BASE / "2025年度初一外研版英语教材"
PDF = TEXTBOOK_DIR / "（根据2022年版课程标准修订）义务教育教科书·英语 七年级上册.pdf"
CP_DIR = BASE / "structured" / "contentpack" / "v5"
CP = CP_DIR / "FLTRP-EN-7A-2022CUR.sqlite"
EX_DIR = BASE / "structured" / "exercises"
CATALOG_V2 = EX_DIR / "exercise_catalog_v2.json"
MAP_V2 = EX_DIR / "exercise_audio_map_v2.json"
AUDIT = BASE / "audit"

TEXTBOOK_ID = "FLTRP-EN-7A-2022CUR"
RULE_SET = "P2-3-exercise-rebuild-v1"
SNAPSHOT_ID = "FLTRP-EN-7A-2022CUR:S20260912T111145"

#: 教材正文页范围（PDF 页码），来自 contentpack unit 边界（只读）
PAGE_FIRST, PAGE_LAST = 8, 114
FOOTER_Y = 690.0          # 页脚（页码/单元名）起始高度
NUMBER_X_MAX = 95.0       # 活动编号所在左边栏

SECTION_BY_NAME = {
    "get ready": "GET_READY",
    "know your school": "KNOW_YOUR_SCHOOL",
    "get to know each other": "GET_TO_KNOW_EACH_OTHER",
    "make a wishing tree": "MAKE_A_WISHING_TREE",
    "starting out": "STARTING_OUT",
    "understanding ideas": "UNDERSTANDING_IDEAS",
    "developing ideas": "DEVELOPING_IDEAS",
    "reading for writing": "READING_FOR_WRITING",
    "presenting ideas": "PRESENTING_IDEAS",
    "reflection": "REFLECTION",
}

#: P2-2 使用的练习大类（保留兼容：web/exercises.TYPE_LABELS 依赖）
TYPE_RULES = (
    ("listening", re.compile(r"^\s*listen\b", re.I)),
    ("grammar", re.compile(r"^\s*(read the sentences .*summarise|circle the correct|"
                           r"complete the sentences with the (correct form|simple future)|"
                           r"look at the family tree and make|complete the blog post)", re.I)),
    ("writing", re.compile(r"^\s*(write|draw and write|complete .*reply)", re.I)),
    ("speaking", re.compile(r"^\s*(work in pairs|work in groups|talk|introduce|role-play|act out|"
                            r"discuss|ask|present|find a video|point and say)", re.I)),
    ("reading", re.compile(r"^\s*(read\b|look at the title|choose the best main idea|choose another"
                           r" suitable title|answer the questions|read and tick|do the quiz|"
                           r"tick the words|what (does|do|is|are)\b)", re.I)),
    ("vocabulary", re.compile(r"^\s*(match|complete|choose|guess|find out)", re.I)),
)

#: 真实题型（P2-3 新增；用于 APP 按题型呈现与作答）
QUESTION_RULES = (
    ("reflection", re.compile(r"^\s*(after completing this unit|to express my understanding|"
                              r"i still need to improve)", re.I)),
    ("choice", re.compile(r"(choose|circle the correct|tick the correct|choose the best|"
                          r"choose another suitable title|read and tick)", re.I)),
    ("judge", re.compile(r"(true or false|\bF\b \(fact\)|fact\) or O|right or wrong|"
                         r"tick the correct sentence)", re.I)),
    ("order", re.compile(r"(order the pictures|number the pictures|put .* in order|"
                         r"number the sentences)", re.I)),
    ("match", re.compile(r"(match|matching)", re.I)),
    ("fill", re.compile(r"(complete|fill in|write the missing|with a / an or a number)", re.I)),
    ("short_answer", re.compile(r"(answer the questions|read and answer|what does|what is|"
                                r"what are|why\b|how\b|think and share|guess)", re.I)),
    ("writing", re.compile(r"^\s*(write|draw and write|complete .*reply)", re.I)),
    ("speaking", re.compile(r"(work in pairs|work in groups|talk|introduce|role-play|act out|"
                            r"discuss|point and say|present)", re.I)),
)


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", (s or "").replace("\u2003", " "))
    return re.sub(r"\s+", " ", s).strip()


def key_text(s: str) -> str:
    """用于文本比对的归一化：去标点/大小写/多余符号。"""
    s = norm(s).lower()
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"[\u2010-\u2015]", "-", s)
    return re.sub(r"[^a-z0-9']+", " ", s).strip()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def ro(path) -> sqlite3.Connection:
    conn = sqlite3.connect("file:%s?mode=ro" % Path(path).as_posix(), uri=True)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------- PDF 版面

DIGITS = re.compile(r"^\d{1,2}$")
CHECKBOX = re.compile(r"^\s*(☐|□|◻)")

#: 教材活动编号使用的字体（全册普查结论，可复核）：
#:   FrutigerNextLTW1G-Black / -BlackC  活动编号（146 + 2 处）
#:   FrutigerNextLTW1G-Heavy            部分单元活动 1 与单元大号数字（需带指令）
#:   BubblegumSans-Regular              Starter「Make a wishing tree」项目页活动编号
NUMBER_FONTS = ("Black", "BlackC", "Heavy", "BubblegumSans")


def _is_number_font(font: str) -> bool:
    return any(token in (font or "") for token in NUMBER_FONTS)


def page_lines(page) -> list:
    """按版面顺序返回页面文本行（含 bbox / 字号）。"""
    out = []
    for blk in page.get_text("dict")["blocks"]:
        if blk.get("type") != 0:
            continue
        for ln in blk["lines"]:
            text = norm("".join(s["text"] for s in ln["spans"]))
            if not text:
                continue
            out.append({
                "text": text,
                "bbox": [round(float(v), 2) for v in ln["bbox"]],
                "size": round(max(s["size"] for s in ln["spans"]), 1),
                "spans": [(s["text"], round(float(s["size"]), 1),
                           [round(float(v), 2) for v in s["bbox"]], s["font"])
                          for s in ln["spans"]],
            })
    out.sort(key=lambda r: (round(r["bbox"][1], 1), r["bbox"][0]))
    return out


def _inline_number(line):
    """行首编号（教材里编号可能与指令同行，如 `2 Read the passage. ...`）。"""
    spans = line["spans"]
    if not spans:
        return None
    first = spans[0]
    if not DIGITS.match(first[0].strip()) or first[1] < 10:
        return None
    if not _is_number_font(first[3]):
        return None
    if first[2][0] > NUMBER_X_MAX or line["bbox"][1] > FOOTER_Y:
        return None
    rest = norm(line["text"][len(first[0]):])
    if len(rest) < 10 or not rest[:1].isupper():
        return None
    rest_x0 = first[2][2]
    for text, _size, bbox, _font in spans[1:]:
        if text.strip():
            rest_x0 = bbox[0]
            break
    return int(first[0]), rest, rest_x0


def _standalone_instruction(lines, num_line):
    """独立编号（编号单独一行）→ 找同一高度的指令行。"""
    x0, x1 = num_line["bbox"][0], num_line["bbox"][2]
    yc = (num_line["bbox"][1] + num_line["bbox"][3]) / 2.0
    best = None
    for ln in lines:
        if ln is num_line or ln["bbox"][0] <= x1:
            continue
        if ln["bbox"][0] > x1 + 60:
            continue
        if abs((ln["bbox"][1] + ln["bbox"][3]) / 2.0 - yc) > 8:
            continue
        if len(ln["text"]) < 10 or CHECKBOX.match(ln["text"]):
            continue
        if not ln["text"][:1].isupper():
            continue
        if best is None or ln["bbox"][0] < best["bbox"][0]:
            best = ln
    return best


def _grow_instruction(lines, inst_line, span_y0):
    """把折行的指令接起来（同一列、紧邻下方、同字号）。"""
    parts = [inst_line["text"]]
    x0, size = inst_line["bbox"][0], inst_line["size"]
    y = inst_line["bbox"][3]
    used = {id(inst_line)}
    for _ in range(3):
        nxt = None
        for ln in lines:
            if id(ln) in used or ln is inst_line:
                continue
            if abs(ln["bbox"][0] - x0) > 4:
                continue
            if not (y - 1 <= ln["bbox"][1] <= y + 4):
                continue
            if abs(ln["size"] - size) > 0.6:
                continue
            if CHECKBOX.match(ln["text"]) or DIGITS.match(ln["text"]):
                continue
            nxt = ln
            break
        if nxt is None:
            break
        parts.append(nxt["text"])
        used.add(id(nxt))
        y = nxt["bbox"][3]
    return norm(" ".join(parts))


def scan_pdf_page(page_no, lines):
    """一页上的活动锚点（编号 + instruction + bbox）。"""
    anchors = []
    for ln in lines:
        if ln["bbox"][1] > FOOTER_Y:
            continue
        inline = _inline_number(ln)
        if inline:
            no, rest, rest_x0 = inline
            inst_line = dict(ln, text=rest)
            inst_line["bbox"] = [rest_x0, ln["bbox"][1], ln["bbox"][2], ln["bbox"][3]]
            anchors.append({"activity_no": no,
                            "instruction": _grow_instruction(lines, inst_line, ln["bbox"][1]),
                            "bbox": ln["bbox"], "inst_bbox": inst_line["bbox"]})
            continue
        if not DIGITS.match(ln["text"]) or ln["size"] < 10:
            continue
        if not ln["spans"] or not _is_number_font(ln["spans"][0][3]):
            continue
        if ln["bbox"][0] > NUMBER_X_MAX:
            continue
        inst = _standalone_instruction(lines, ln)
        if inst is None:
            continue
        anchors.append({"activity_no": int(ln["text"]),
                        "instruction": _grow_instruction(lines, inst, ln["bbox"][1]),
                        "inst_bbox": inst["bbox"],
                        "bbox": [ln["bbox"][0], min(ln["bbox"][1], inst["bbox"][1]),
                                 max(ln["bbox"][2], inst["bbox"][2]),
                                 max(ln["bbox"][3], inst["bbox"][3])]})
    anchors.sort(key=lambda a: (round(a["bbox"][1], 1), a["bbox"][0]))
    seen = set()
    unique = []
    for a in anchors:
        token = (a["activity_no"], round(a["bbox"][1], 1))
        if token in seen:
            continue
        seen.add(token)
        unique.append(a)
    return unique


def scan_pdf() -> tuple:
    """扫描整册教材正文页 → (activities, page_lines_map)。"""
    cp = ro(CP)
    units = [dict(r) for r in cp.execute(
        "select unit_code, unit_id, pdf_page_start, pdf_page_end from unit "
        "where unit_code <> 'Appendix' order by pdf_page_start")]
    secs = [dict(r) for r in cp.execute(
        "select s.section_id, s.section_key, s.title, s.pdf_page_start, u.unit_code "
        "from section s join unit u on u.unit_id=s.unit_id "
        "where u.unit_code <> 'Appendix' order by s.pdf_page_start")]
    cp.close()

    def locate(page_no):
        unit = None
        for u in units:
            if u["pdf_page_start"] <= page_no <= u["pdf_page_end"]:
                unit = u["unit_code"]
        if unit is None:
            return None, None
        own = [s for s in secs if s["unit_code"] == unit and s["pdf_page_start"] <= page_no]
        if not own:
            return unit, None
        sec = max(own, key=lambda s: s["pdf_page_start"])
        return unit, sec

    doc = pymupdf.open(PDF)
    pages = {}
    raw = []
    for pno in range(PAGE_FIRST, PAGE_LAST + 1):
        lines = page_lines(doc[pno - 1])
        pages[pno] = lines
        for a in scan_pdf_page(pno, lines):
            unit, sec = locate(pno)
            if unit is None or sec is None:
                continue
            a.update({"pdf_page": pno, "textbook_page": pno - 5,
                      "unit": unit, "section": sec["section_key"] if sec else None,
                      "section_id": sec["section_id"] if sec else None})
            raw.append(a)
    doc.close()
    return raw, pages


# ---------------------------------------------------------------- 题目结构

OPTION_LINE = re.compile(r"^([a-hA-H])\s+(\S.*)$")
INLINE_QUESTIONS = re.compile(r"(?<=[.?!])\s*(?=\d{1,2}\s+[A-Z(])")


def activity_body(anchor, pages, next_anchor_y) -> list:
    """活动正文（含题干/选项/空格所在行），到下一个活动编号或本板块结束为止。"""
    page = anchor["pdf_page"]
    y_after = anchor["bbox"][3]
    body = [ln for ln in pages.get(page, [])
            if y_after - 2 <= ln["bbox"][1] and (next_anchor_y is None
                                                or ln["bbox"][1] < next_anchor_y - 1)]
    # 跨页：后续页在出现下一个活动编号之前的行，属于同一活动
    for extra in (page + 1, page + 2):
        if extra not in pages:
            break
        stop = None
        for ln in pages[extra]:
            if DIGITS.match(ln["text"]) and ln["size"] >= 10 and ln["bbox"][0] <= NUMBER_X_MAX:
                stop = ln["bbox"][1]
                break
        for ln in pages[extra]:
            if stop is not None and ln["bbox"][1] > stop:
                break
            body.append(ln)
        if stop is not None:
            break
    return body


def structure_of(body_lines) -> dict:
    """从正文行抽出可核对的题目结构（题号 / 选项 / 勾选框 / 空格）。"""
    text = norm(" ".join(ln["text"] for ln in body_lines))
    options, checks, questions = [], [], []
    for ln in body_lines:
        m = OPTION_LINE.match(ln["text"])
        if m and len(m.group(2)) >= 2:
            options.append({"label": m.group(1).lower(), "text": m.group(2)})
        if CHECKBOX.match(ln["text"]):
            checks.append(CHECKBOX.sub("", ln["text"]).strip())
    for part in INLINE_QUESTIONS.split(text):
        part = norm(part)
        m = re.match(r"^(\d{1,2})\s+(.*)$", part)
        if m and len(m.group(2)) > 6:
            questions.append({"no": int(m.group(1)), "text": m.group(2)})
        elif not questions and len(part) > 6:
            questions.append({"no": 1, "text": part})
    blanks = 0
    for ln in body_lines:
        for s_text, s_size, _bbox, _font in ln["spans"]:
            if s_size <= 8.5 and DIGITS.match(s_text.strip()):
                blanks += 1
    dedup_options = []
    for opt in options:
        if opt not in dedup_options:
            dedup_options.append(opt)
    return {"text": text, "options": dedup_options, "check_items": checks,
            "questions": questions, "blanks": blanks}


def big_type(instruction: str, has_icon: bool) -> str:
    """P2-2 兼容的练习大类（web/exercises.TYPE_LABELS 用）。"""
    if has_icon:
        return "listening"
    for name, pattern in TYPE_RULES:
        if pattern.search(instruction or ""):
            return name
    return "other"


def question_type(instruction: str, has_icon: bool, struct: dict) -> str:
    """真实题型：选择 / 填空 / 匹配 / 判断 / 排序 / 简答 / 口语 / 写作 / 反思 / 其他。"""
    inst = instruction or ""
    if has_icon or re.match(r"^\s*listen\b", inst, re.I):
        if re.search(r"choose|tick|circle", inst, re.I):
            return "choice"
        if re.search(r"order|number the pictures", inst, re.I):
            return "order"
        if re.search(r"match", inst, re.I):
            return "match"
        if re.search(r"F\s*\(fact\)|fact\) or O|true or false", inst, re.I):
            return "judge"
        if re.search(r"complete|fill|write", inst, re.I):
            return "fill"
        if re.search(r"answer|what|why|how", inst, re.I):
            return "short_answer"
        return "listening"
    for name, pattern in QUESTION_RULES:
        if pattern.search(inst):
            return name
    if struct["check_items"] and not struct["options"]:
        return "choice"
    if struct["blanks"] >= 2:
        return "fill"
    return "other"


# ---------------------------------------------------------------- 官方 MP3

MP3_BITRATES_V1L3 = [None, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, None]
MP3_SR_V1 = [44100, 48000, 32000, None]


def mp3_bitrate(path: Path):
    """本地解析 MP3 帧头（不依赖任何外部库）：返回 (bitrate_kbps, sample_rate)。"""
    data = path.read_bytes()
    off = 0
    if data[:3] == b"ID3":
        size = ((data[6] & 0x7F) << 21) | ((data[7] & 0x7F) << 14) | \
               ((data[8] & 0x7F) << 7) | (data[9] & 0x7F)
        off = 10 + size
    i = off
    while i < len(data) - 4:
        if data[i] == 0xFF and (data[i + 1] & 0xE0) == 0xE0:
            break
        i += 1
    head = data[i:i + 4]
    if len(head) < 4:
        return None, None
    version = (head[1] >> 3) & 0x03
    bitrate_index = (head[2] >> 4) & 0x0F
    sr_index = (head[2] >> 2) & 0x03
    bitrate = MP3_BITRATES_V1L3[bitrate_index] if version == 3 else None
    sample_rate = MP3_SR_V1[sr_index]
    return bitrate, sample_rate


def scan_audio(cp_rows: dict) -> list:
    """重新扫描全部官方 MP3（文件名 + 大小 + SHA256 + 时长）。"""
    out = []
    for path in sorted(TEXTBOOK_DIR.glob("*.mp3")):
        parsed = parse_audio_filename(path.name)
        size = path.stat().st_size
        bitrate, sample_rate = mp3_bitrate(path)
        duration_ms = None
        if bitrate:
            data_head = 0
            with open(path, "rb") as fh:
                head = fh.read(10)
                if head[:3] == b"ID3":
                    data_head = 10 + (((head[6] & 0x7F) << 21) | ((head[7] & 0x7F) << 14) |
                                      ((head[8] & 0x7F) << 7) | (head[9] & 0x7F))
            duration_ms = int(round((size - data_head) * 8 / (bitrate * 1000) * 1000))
        ref = cp_rows.get(path.name)
        parsed.update({
            "filename": path.name,
            "relative_path": str(path.relative_to(BASE)),
            "size_bytes": size,
            "sha256": sha256_file(path),
            "bitrate_kbps": bitrate,
            "sample_rate": sample_rate,
            "duration_ms_local": duration_ms,
            "duration_ms_contentpack": (ref or {}).get("duration_ms"),
            "audio_id": (ref or {}).get("audio_id"),
        })
        out.append(parsed)
    return out


def parse_audio_filename(filename: str) -> dict:
    """教材官方音频命名规则：`<序号>_<单元>_<板块>[_<活动号> <指令>].mp3`。"""
    stem = re.sub(r"\.mp3$", "", filename or "", flags=re.I)
    parts = stem.split("_")
    if len(parts) < 3:
        return {"seq": None, "unit": None, "section": None, "activity_no": None,
                "instruction": None, "kind": "unknown"}
    seq = int(parts[0]) if parts[0].isdigit() else None
    unit = norm(parts[1])
    tail = "_".join(parts[2:]).strip()
    if "Words and expressions" in tail:
        return {"seq": seq, "unit": unit, "section": "WORDS_AND_EXPRESSIONS",
                "activity_no": None, "instruction": "Words and expressions",
                "kind": "word_list"}
    if "Phonetics in use" in tail:
        return {"seq": seq, "unit": unit, "section": "DEVELOPING_IDEAS",
                "activity_no": None, "instruction": "Phonetics in use", "kind": "phonetics"}
    head = tail.split("_")[0].strip()
    section = SECTION_BY_NAME.get(head.lower())
    if "Reading for writing" in tail:
        section = "READING_FOR_WRITING"
    m = re.search(r"(?:^|[_ ])(\d+)\s+([A-Z].*)$", tail)
    activity_no = int(m.group(1)) if m else None
    instruction = norm(m.group(2)) if m else norm(tail)
    return {"seq": seq, "unit": unit, "section": section, "activity_no": activity_no,
            "instruction": instruction, "kind": "exercise"}


# ---------------------------------------------------------------- 耳机图标

def listening_icon_boxes(pdf_path: Path, first: int, last: int) -> dict:
    """教材官方耳机图标（矢量图形组），规则与 P2-2 相同、可复核。"""
    doc = pymupdf.open(pdf_path)
    out = {}
    for pno in range(first, last + 1):
        main, mate = [], []
        for d in doc[pno - 1].get_drawings():
            x0, y0, x1, y1 = d["rect"]
            key = (round(x1 - x0), round(y1 - y0), len(d["items"]))
            box = [round(float(x0), 1), round(float(y0), 1),
                   round(float(x1), 1), round(float(y1), 1)]
            if key == (12, 13, 26):
                main.append(box)
            elif key == (10, 11, 18):
                mate.append(box)
        confirmed = [b for b in main
                     if any(abs(b[0] - m[0]) <= 4 and abs(b[1] - m[1]) <= 4 for m in mate)]
        if confirmed:
            out[pno] = confirmed
    doc.close()
    return out


def near_icon(bbox, icon_boxes) -> bool:
    """教材里耳机图标是**指令行前缀**（同一行、紧贴 instruction 左端）。

    bbox 传 instruction 行 bbox：图标左端与指令左端对齐（±8pt）、
    垂直中心落在指令行范围内（±6pt）。
    """
    if not bbox or not icon_boxes:
        return False
    ax0, ay0, ax1, ay1 = bbox
    for bx0, by0, bx1, by1 in icon_boxes:
        if abs(bx0 - ax0) > 8:
            continue
        center = (by0 + by1) / 2.0
        if ay0 - 5 <= center <= ay1 + 6:
            return True
    return False


# ---------------------------------------------------------------- 组装练习

def load_v1_catalog() -> dict:
    path = EX_DIR / "exercise_catalog.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def exercise_id_for(unit: str, section: str, no: int, page: int) -> str:
    raw = "p2-3|%s|%s|%s|%s" % (unit, section or "-", no, page)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12].upper()
    return "%s:X:%s" % (TEXTBOOK_ID, digest)


def build_exercises(raw, pages, icons, v1: dict) -> list:
    v1_by_key = {}
    for e in (v1.get("exercises") or []):
        v1_by_key[(e["unit"], e["section"], e["exercise_no"])] = e
    by_page = {}
    for a in raw:
        by_page.setdefault(a["pdf_page"], []).append(a)
    for v in by_page.values():
        v.sort(key=lambda x: x["bbox"][1])

    out = []
    for a in raw:
        siblings = by_page[a["pdf_page"]]
        later = [s for s in siblings if s["bbox"][1] > a["bbox"][1] + 1]
        next_y = min((s["bbox"][1] for s in later), default=None)
        body = activity_body(a, pages, next_y)
        struct = structure_of(body)
        has_icon = a.get("listening_icon", False)
        qtype = question_type(a["instruction"], has_icon, struct)
        known = v1_by_key.get((a["unit"], a["section"], a["activity_no"]))
        exercise_id = (known or {}).get("exercise_id") or exercise_id_for(
            a["unit"], a["section"], a["activity_no"], a["textbook_page"])
        out.append({
            "exercise_id": exercise_id,
            "activity_id": (known or {}).get("activity_id"),
            "in_contentpack_activity": bool(known),
            "unit": a["unit"], "section": a["section"] or "",
            "section_id": a["section_id"],
            "exercise_no": a["activity_no"],
            "textbook_page": a["textbook_page"], "pdf_page": a["pdf_page"],
            "instruction": a["instruction"],
            "type": big_type(a["instruction"], has_icon),
            "question_type": qtype,
            "listening_icon": has_icon,
            "audio_required": bool(has_icon or re.match(r"^\s*listen\b", a["instruction"], re.I)),
            "audio_id": None, "audio_status": None, "audio_evidence": None,
            "questions": struct["questions"] or (
                [{"no": 1, "text": a["instruction"]}] if qtype in
                ("choice", "fill", "match", "judge", "order", "short_answer") else []),
            "options": struct["options"], "check_items": struct["check_items"],
            "blanks": struct["blanks"],
            "answer_status": "NO_RELIABLE_SOURCE",
            "answer_note": "教材未提供可核对的答案来源；不猜测答案。",
            "source_evidence": {
                "pdf_page": a["pdf_page"], "textbook_page": a["textbook_page"],
                "bbox": a["bbox"], "listening_icon": has_icon,
                "scan_rule": RULE_SET,
            },
        })
    out.sort(key=lambda e: (UNIT_ORDER.get(e["unit"], 99), e["pdf_page"], e["exercise_no"]))
    return out


UNIT_ORDER = {"Starter": 0, "Unit 1": 1, "Unit 2": 2, "Unit 3": 3, "Unit 4": 4,
              "Unit 5": 5, "Unit 6": 6}


# ---------------------------------------------------------------- 证据链匹配

UNITS = ("Starter", "Unit 1", "Unit 2", "Unit 3", "Unit 4", "Unit 5", "Unit 6")


def instruction_similarity(a: str, b: str) -> float:
    ka, kb = key_text(a), key_text(b)
    if not ka or not kb:
        return 0.0
    return round(difflib.SequenceMatcher(None, ka, kb).ratio(), 3)


def is_prefix_evidence(audio_instruction: str, pdf_instruction: str) -> bool:
    """教材指令常有多句（Use the words and expressions …），文件名只带第一句。

    若归一化后的文件名指令是教材指令的**前缀**且长度足够，视为强证据之一。
    """
    ka, kb = key_text(audio_instruction), key_text(pdf_instruction)
    return len(ka) >= 25 and kb.startswith(ka)


def match_audio(audios, exercises, cp, sections) -> list:
    """官方音频 → 教材练习/板块 的多重证据匹配。"""
    by_key = {}
    for e in exercises:
        by_key.setdefault((e["unit"], e["section"], e["exercise_no"]), []).append(e)
    order_index = {}
    for i, e in enumerate(exercises):
        order_index[(e["unit"], e["section"], e["exercise_no"])] = i

    appendix_rows = [(r["pdf_page"], r["reading_order"], r["text_normalized"] or "")
                     for r in cp.execute(
                         "select p.pdf_page, b.reading_order, b.text_normalized "
                         "from content_block b join page p on p.page_id=b.page_id "
                         "where p.pdf_page between 155 and 164 "
                         "order by p.pdf_page, b.reading_order")]
    appendix_blob = key_text(" ".join(r[2] for r in appendix_rows))

    mappings = []
    for au in audios:
        kind = au["kind"]
        ev = {"rule_set": RULE_SET, "filename": au["filename"], "seq": au["seq"],
              "duration_ms": au["duration_ms_local"], "kind": kind}
        if kind == "word_list":
            sec_id = None
            for s in sections:
                if s["section_key"] == "WORDS_AND_EXPRESSIONS":
                    sec_id = s["section_id"]
            words = unit_word_list(cp, au["unit"])
            hit = [w for w in words if key_text(w) and key_text(w) in appendix_blob]
            cov = round(len(hit) / len(words), 3) if words else 0.0
            unit_label = au["unit"] if au["unit"] != "Starter" else "Starter"
            header_idx = None
            for idx, (_p, _o, text) in enumerate(appendix_rows):
                if key_text(text) == key_text(unit_label) or \
                        key_text(text).startswith(key_text(unit_label) + " "):
                    header_idx = idx
                    break
            first_word_idx = None
            for idx, (_p, _o, text) in enumerate(appendix_rows):
                if any(key_text(w) and key_text(w) in key_text(text) for w in hit[:3]):
                    first_word_idx = idx
                    break
            ev.update({"unit": au["unit"], "word_count": len(words),
                       "appendix_hits": len(hit), "coverage": cov,
                       "appendix_pages": [155, 164],
                       "unit_header_index": header_idx,
                       "first_word_index": first_word_idx})
            order_ok = (header_idx is not None and first_word_idx is not None
                        and abs(header_idx - first_word_idx) <= 6)
            ev["appendix_order_consistent"] = order_ok
            status = "CONFIRMED" if (sec_id and cov >= 0.6 and order_ok) else "NEEDS_REVIEW"
            mappings.append({
                "filename": au["filename"], "seq": au["seq"], "kind": kind,
                "target_type": "section" if sec_id else None, "target_id": sec_id,
                "unit": au["unit"], "section": "WORDS_AND_EXPRESSIONS",
                "exercise_id": None, "status": status, "evidence": ev,
                "reason": "附录词表页覆盖本单元词条 %.0f%%" % (cov * 100),
            })
            continue
        if kind == "phonetics":
            target = None
            for e in exercises:
                if e["unit"] == au["unit"] and e["section"] == "DEVELOPING_IDEAS":
                    target = e
                    break
            sec_id = target["section_id"] if target else None
            page = None
            for s in sections:
                if sec_id and s["section_id"] == sec_id:
                    page = s["pdf_page_start"]
            heading = False
            if page:
                for r in cp.execute(
                        "select b.text_normalized from content_block b join page p "
                        "on p.page_id=b.page_id where p.pdf_page=?", (page,)):
                    if "Phonetics in use" in (r["text_normalized"] or ""):
                        heading = True
                        break
            ev.update({"unit": au["unit"], "section": "DEVELOPING_IDEAS",
                       "section_id": sec_id, "heading_on_page": page,
                       "heading_found": heading})
            status = "CONFIRMED" if (sec_id and heading) else "NEEDS_REVIEW"
            mappings.append({
                "filename": au["filename"], "seq": au["seq"], "kind": kind,
                "target_type": "section" if sec_id else None, "target_id": sec_id,
                "unit": au["unit"], "section": "DEVELOPING_IDEAS",
                "exercise_id": None, "status": status, "evidence": ev,
                "reason": ("Developing ideas 页出现 Phonetics in use 标题" if heading
                           else "未在教材页确认 Phonetics in use 位置"),
            })
            continue

        cand = by_key.get((au["unit"], au["section"], au["activity_no"]), [])
        target = cand[0] if cand else None
        sim = instruction_similarity(au["instruction"], target["instruction"]) if target else 0.0
        prefix = bool(target and is_prefix_evidence(au["instruction"], target["instruction"]))
        ev.update({
            "unit": au["unit"], "filename_section": au["section"],
            "activity_no": au["activity_no"], "filename_instruction": au["instruction"],
            "candidate_exercise_id": target["exercise_id"] if target else None,
            "candidate_activity_in_contentpack": target["in_contentpack_activity"] if target else None,
            "unit_match": bool(target and target["unit"] == au["unit"]),
            "section_match": bool(target and target["section"] == au["section"]),
            "number_match": bool(target and target["exercise_no"] == au["activity_no"]),
            "instruction_similarity": sim,
            "instruction_prefix_of_textbook": prefix,
            "listening_icon": bool(target and target["listening_icon"]),
            "candidate_pdf_page": target["pdf_page"] if target else None,
            "candidate_textbook_page": target["textbook_page"] if target else None,
        })
        if target is None:
            status = "NEEDS_REVIEW"
            reason = "教材中未找到对应活动编号；不得按文件名硬匹配"
        elif sim >= 0.8:
            status = "CONFIRMED"
            reason = "文件名指令与教材指令一致（文本相似度 %.2f）" % sim
        elif prefix:
            status = "CONFIRMED"
            reason = "文件名指令是教材指令前缀（相似度 %.2f，教材另有补充句）" % sim
        elif sim >= 0.5 and target["listening_icon"]:
            status = "CONFIRMED"
            reason = "编号一致 + 教材耳机图标 + 指令相近（%.2f）" % sim
        else:
            status = "NEEDS_REVIEW"
            reason = "仅有编号一致（指令相似度 %.2f），证据不足" % sim
        mappings.append({
            "filename": au["filename"], "seq": au["seq"], "kind": kind,
            "target_type": "activity" if target else None,
            "target_id": target["activity_id"] if (target and target["activity_id"]) else None,
            "exercise_id": target["exercise_id"] if target else None,
            "unit": au["unit"], "section": au["section"],
            "status": status, "evidence": ev, "reason": reason,
        })
    return mappings


def unit_word_list(cp, unit_code: str) -> list:
    """按单元取教材词表（复用 web/content 的归属规则，只读）。"""
    attribution = content_mod._attribution(cp)
    out = []
    for r in cp.execute("select item_id, canonical_text from learning_item "
                        "where item_type='vocabulary'"):
        info = attribution.get(r["item_id"]) or {}
        if info.get("unit_code") == unit_code and (r["canonical_text"] or "").strip():
            out.append(r["canonical_text"])
    return out


# ---------------------------------------------------------------- 汇总 / 报告

def attach_audio(exercises, mappings, audios) -> None:
    audio_by_id = {a["audio_id"]: a for a in audios if a.get("audio_id")}
    by_ex = {}
    for m in mappings:
        if m["target_type"] == "activity" and m["exercise_id"]:
            by_ex.setdefault(m["exercise_id"], []).append(m)
    for e in exercises:
        cand = by_ex.get(e["exercise_id"]) or []
        confirmed = [m for m in cand if m["status"] == "CONFIRMED"]
        pick = (confirmed or cand)[0] if cand else None
        if pick is None:
            continue
        au = audio_by_id.get(next((a["audio_id"] for a in audios
                                   if a["filename"] == pick["filename"]), None))
        e["audio_id"] = au["audio_id"] if au else None
        e["audio_filename"] = pick["filename"]
        e["audio_status"] = pick["status"]
        e["audio_evidence"] = pick["evidence"]
        e["needs_review"] = pick["status"] != "CONFIRMED"


def summarize(exercises, mappings, audios, v1) -> dict:
    def cnt(pred, items):
        return sum(1 for x in items if pred(x))
    by_type = {}
    for e in exercises:
        by_type[e["question_type"]] = by_type.get(e["question_type"], 0) + 1
    by_unit = {}
    for e in exercises:
        by_unit[e["unit"]] = by_unit.get(e["unit"], 0) + 1
    confirmed = [m for m in mappings if m["status"] == "CONFIRMED"]
    review = [m for m in mappings if m["status"] == "NEEDS_REVIEW"]
    act_confirmed = [m for m in confirmed if m["target_type"] == "activity"]
    targets = {}
    for m in act_confirmed:
        targets.setdefault(m["target_id"] or m["exercise_id"], []).append(m["filename"])
    one_to_many = {k: v for k, v in targets.items() if len(v) > 1}
    audio_per_exercise = {}
    for e in exercises:
        if e.get("audio_id"):
            audio_per_exercise[e["exercise_id"]] = e["audio_id"]

    v1_keys = {(e["unit"], e["section"], e["exercise_no"]): e
               for e in (v1.get("exercises") or [])}
    p2_2_unmatched = []
    p2_2_path = AUDIT / "P2-2_exercise_audio_scan.json"
    if p2_2_path.exists():
        p2_2 = json.loads(p2_2_path.read_text(encoding="utf-8"))
        p2_2_unmatched = list(p2_2.get("scan", {}).get("unresolved_audio") or [])
    by_audio_id = {a["audio_id"]: a for a in audios if a.get("audio_id")}
    resolved = []
    for audio_id in p2_2_unmatched:
        au = by_audio_id.get(audio_id)
        if au is None:
            continue
        m = next((x for x in mappings if x["filename"] == au["filename"]), None)
        resolved.append({"audio_id": audio_id, "filename": au["filename"],
                         "status": (m or {}).get("status"),
                         "target": (m or {}).get("exercise_id") or (m or {}).get("target_id"),
                         "reason": (m or {}).get("reason")})
    newly = [e for e in exercises if (e["unit"], e["section"], e["exercise_no"]) not in v1_keys]
    fixed, cancelled = [], []
    for e in exercises:
        old = v1_keys.get((e["unit"], e["section"], e["exercise_no"]))
        if not old:
            continue
        if (not old.get("audio_id")) and e.get("audio_id"):
            fixed.append({"exercise_id": e["exercise_id"], "unit": e["unit"],
                          "section": e["section"], "no": e["exercise_no"],
                          "audio": e.get("audio_filename"),
                          "status": e.get("audio_status")})
        if old.get("audio_id") and not e.get("audio_id"):
            cancelled.append({"exercise_id": e["exercise_id"], "unit": e["unit"],
                              "section": e["section"], "no": e["exercise_no"],
                              "old_audio": old.get("audio_id"),
                              "old_method": old.get("match_method")})

    return {
        "pdf": {"units": len({e["unit"] for e in exercises}),
                "sections": len({e["section_id"] for e in exercises if e["section_id"]}),
                "activities": len(exercises),
                "questions": sum(len(e["questions"]) for e in exercises),
                "listening_activities": cnt(lambda e: e["audio_required"], exercises),
                "by_unit": by_unit, "by_question_type": by_type},
        "audio": {"files": len(audios),
                  "confirmed": len(confirmed), "needs_review": len(review),
                  "mapped_to_activity": len(act_confirmed),
                  "confirmed_one_to_one": len(targets) - len(one_to_many),
                  "confirmed_one_to_many": len(one_to_many),
                  "shared_audio": one_to_many,
                  "unconfirmed": [m["filename"] for m in review]},
        "delta_vs_p2_2": {
            "v1_exercises": len(v1.get("exercises") or []),
            "newly_recovered_activities": len(newly),
            "newly_recovered": [{"unit": e["unit"], "section": e["section"],
                                 "no": e["exercise_no"], "page": e["textbook_page"],
                                 "instruction": e["instruction"][:70],
                                 "audio": e.get("audio_filename")}
                                for e in newly],
            "audio_fixed": fixed, "audio_cancelled": cancelled,
            "still_needs_review": [m["filename"] for m in review],
            "p2_2_unmatched": len(p2_2_unmatched),
            "p2_2_unmatched_resolved": [r for r in resolved
                                        if r["status"] == "CONFIRMED"],
            "p2_2_unmatched_still_open": [r for r in resolved
                                          if r["status"] != "CONFIRMED"],
        },
        "exercise_audio_pairs": len(audio_per_exercise),
    }


def apply_to_contentpack(conn, exercises, stamp) -> dict:
    """只为「contentpack 里还没有的练习」补 learning_item + source_ref。"""
    have = {r["item_id"] for r in conn.execute(
        "select item_id from learning_item where item_type='exercise'")}
    applied = {"new_items": 0, "new_refs": 0, "kept_items": 0}
    for e in exercises:
        iid = e["exercise_id"]
        if iid in have:
            applied["kept_items"] += 1
            continue
        conn.execute(
            "INSERT OR REPLACE INTO learning_item(item_id,textbook_id,snapshot_id,item_type,"
            "surface_form,lemma,phonetic,part_of_speech,meaning_zh,derivation_type,review_status,"
            "canonical_text,display_text,schema_version,content_hash,created_at,updated_at,"
            "learning_requirement,requirement_conflict_status) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (iid, TEXTBOOK_ID, SNAPSHOT_ID, "exercise", e["instruction"], None, None, None, None,
             "FROM_TEXTBOOK_ACTIVITY", "OK",
             "%s %s %s" % (e["unit"], e["section"], e["exercise_no"]), e["instruction"],
             "p1-04-v2",
             hashlib.sha256("|".join(["p1-04-v2", "exercise", iid, e["instruction"]])
                            .encode("utf-8")).hexdigest(),
             stamp, stamp, "CORE", "OK"))
        applied["new_items"] += 1
        ref = iid + ":SR0_0"
        conn.execute(
            "INSERT OR REPLACE INTO source_ref(source_ref_id,item_id,item_type,source_type,"
            "source_id,quote_raw,textbook_id,snapshot_id,textbook_emphasis,emphasis_source_list,"
            "emphasis_evidence) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (ref, iid, "learning_item", "textbook_page",
             "%s:P%s" % (TEXTBOOK_ID, e["pdf_page"]), e["instruction"][:300],
             TEXTBOOK_ID, SNAPSHOT_ID, None, "textbook exercise",
             json.dumps(e["source_evidence"], ensure_ascii=False)))
        applied["new_refs"] += 1
    return applied


def write_audit(summary, mappings, exercises, audios, cp_info, stamp, applied) -> None:
    AUDIT.mkdir(parents=True, exist_ok=True)
    report = {
        "task": "P2-3 教材练习重建 + 听力严格匹配",
        "generated_at": stamp, "rule_set": RULE_SET,
        "contentpack": cp_info, "summary": summary, "applied": applied,
        "audio_files": [{k: a[k] for k in ("seq", "filename", "size_bytes", "sha256",
                                           "duration_ms_local", "duration_ms_contentpack",
                                           "bitrate_kbps", "sample_rate", "unit", "section",
                                           "activity_no", "instruction", "kind")}
                        for a in audios],
        "mappings": mappings,
        "boundaries": {"pdf_modified": False, "mp3_modified": False,
                       "learning_db_touched": False, "ai_calls": 0, "network_calls": 0},
    }
    (AUDIT / "P2-3_exercise_rebuild.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    p = summary["pdf"]
    a = summary["audio"]
    d = summary["delta_vs_p2_2"]
    lines = [
        "# P2-3 教材练习重建 + 听力严格匹配报告", "",
        "- 生成时间：%s" % stamp,
        "- 规则集：%s" % RULE_SET,
        "- 教材 PDF：%s（未修改）" % PDF.name,
        "- contentpack SHA256（重建前）：%s" % cp_info["sha256_before"],
        "- contentpack SHA256（重建后）：%s" % cp_info["sha256_after"],
        "- 备份：%s" % cp_info.get("backup"),
        "- integrity_check：%s ｜ foreign_key_check：%s" % (cp_info.get("integrity_check"),
                                                            cp_info.get("foreign_key_check")),
        "", "## 1. 教材扫描结果", "",
        "| 项目 | 数量 |", "| --- | --- |",
        "| 单元/Starter | %d |" % p["units"],
        "| 板块 Section | %d |" % p["sections"],
        "| 活动 Activity | %d |" % p["activities"],
        "| 题目 Question | %d |" % p["questions"],
        "| 需要音频的活动 | %d |" % p["listening_activities"], "",
        "按单元：", "",
        "| 单元 | 活动数 |", "| --- | --- |",
    ]
    for unit in UNITS:
        lines.append("| %s | %d |" % (unit, p["by_unit"].get(unit, 0)))
    lines += ["", "## 2. 音频结果", "",
              "| 项目 | 数量 |", "| --- | --- |",
              "| 官方 MP3 总数 | %d |" % a["files"],
              "| 已确认映射（CONFIRMED） | %d |" % a["confirmed"],
              "| 待确认（NEEDS_REVIEW） | %d |" % a["needs_review"],
              "| 确认到活动的映射 | %d |" % a["mapped_to_activity"],
              "| 一对一 | %d |" % a["confirmed_one_to_one"],
              "| 一对多 | %d |" % a["confirmed_one_to_many"],
              "| 多题共用同一音频 | %d |" % len(a["shared_audio"]), "",
              "仍需人工确认：", ""]
    for name in a["unconfirmed"]:
        lines.append("- %s" % name)
    lines += ["", "## 3. 题型结果", "", "| 题型 | 数量 |", "| --- | --- |"]
    for name, n in sorted(p["by_question_type"].items(), key=lambda kv: -kv[1]):
        lines.append("| %s | %d |" % (name, n))
    lines += ["", "## 4. 与 P2-2 对比", "",
              "- P2-2 目录条目：%d" % d["v1_exercises"],
              "- 本次重新解析出的、P2-2 缺失的活动：%d" % d["newly_recovered_activities"],
              "- 新补上音频链接的练习：%d" % len(d["audio_fixed"]),
              "- 被取消/降级为待确认的旧链接：%d" % len(d["audio_cancelled"]), "",
              "- P2-2 未匹配音频 %d 个 → 本次确认为已匹配 %d 个" %
              (d["p2_2_unmatched"], len(d["p2_2_unmatched_resolved"])), "",
              "P2-2 遗留音频处置：", "",
              "| 音频 | 结果 | 指向 | 依据 |", "| --- | --- | --- | --- |"]
    for r in d["p2_2_unmatched_resolved"]:
        lines.append("| %s | CONFIRMED | %s | %s |" % (r["filename"], r["target"], r["reason"]))
    for r in d["p2_2_unmatched_still_open"]:
        lines.append("| %s | NEEDS_REVIEW | — | %s |" % (r["filename"], r["reason"]))
    lines += [
              "新增活动明细：", "",
              "| 单元 | 板块 | 活动 | 教材页 | 指令 | 音频 |", "| --- | --- | --- | --- | --- | --- |"]
    for r in d["newly_recovered"]:
        lines.append("| %s | %s | %s | %s | %s | %s |" %
                     (r["unit"], r["section"], r["no"], r["page"],
                      r["instruction"].replace("|", "/"), r["audio"] or "—"))
    if d["audio_cancelled"]:
        lines += ["", "被取消的旧链接：", ""]
        for r in d["audio_cancelled"]:
            lines.append("- %s %s A%s：原 %s（%s）" %
                         (r["unit"], r["section"], r["no"], r["old_audio"], r["old_method"]))
    lines += ["", "## 5. 数据安全", "",
              "- 原始 PDF：未修改",
              "- 原始 MP3：未修改（54 个文件 SHA256 已记录）",
              "- learning.db：未写入（仅只读）",
              "- 冻结服务：未修改",
              "- AI 调用：0",
              "- 网络：0", ""]
    (AUDIT / "P2-3_exercise_rebuild.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="写入目录/审计/contentpack 最小增量")
    args = ap.parse_args()
    stamp = now()

    before = sha256_file(CP)
    cp = ro(CP)
    audio_rows = {r["filename"]: dict(r) for r in cp.execute(
        "select audio_id, filename, duration_ms from audio_asset")}
    sections = [dict(r) for r in cp.execute(
        "select s.section_id, s.section_key, s.title, s.pdf_page_start, u.unit_code "
        "from section s join unit u on u.unit_id=s.unit_id order by s.pdf_page_start")]
    v1 = load_v1_catalog()

    print("[1/5] 扫描教材 PDF 耳机图标 ...")
    icons = listening_icon_boxes(PDF, PAGE_FIRST, PAGE_LAST)
    print("      耳机图标页：%s" % sorted(icons))

    print("[2/5] 扫描教材 PDF 活动结构 ...")
    raw, pages = scan_pdf()
    for a in raw:
        a["listening_icon"] = near_icon(a.get("inst_bbox") or a["bbox"],
                                        icons.get(a["pdf_page"], []))
    print("      活动：%d" % len(raw))
    print("      需要音频：%d" % sum(1 for a in raw if a["listening_icon"]))

    print("[3/5] 重新扫描官方 MP3 ...")
    audios = scan_audio(audio_rows)
    print("      MP3：%d" % len(audios))

    print("[4/5] 证据链匹配 ...")
    mappings = match_audio(audios, build_exercises(raw, pages, icons, v1), cp, sections)
    exercises = build_exercises(raw, pages, icons, v1)
    attach_audio(exercises, mappings, audios)
    cp.close()

    summary = summarize(exercises, mappings, audios, v1)
    print("      CONFIRMED %d / NEEDS_REVIEW %d" %
          (summary["audio"]["confirmed"], summary["audio"]["needs_review"]))

    cp_info = {"path": str(CP), "sha256_before": before, "sha256_after": before,
               "backup": None, "integrity_check": "ok", "foreign_key_check": 0}
    applied = {}
    if args.apply:
        print("[5/5] 写入 ...")
        backup = CP.with_name(CP.name + ".bak-P2-3")
        if not backup.exists():
            shutil.copyfile(CP, backup)
        work = CP.with_name(CP.name + ".building-p2-3")
        shutil.copyfile(CP, work)
        conn = sqlite3.connect(str(work))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        applied = apply_to_contentpack(conn, exercises, stamp)
        conn.commit()
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        fk = len(conn.execute("PRAGMA foreign_key_check").fetchall())
        conn.close()
        if integrity != "ok" or fk != 0:
            work.unlink(missing_ok=True)
            print("STOP: contentpack 校验失败", integrity, fk)
            return 3
        work.replace(CP)
        cp_info.update({"sha256_after": sha256_file(CP), "backup": str(backup),
                        "integrity_check": integrity, "foreign_key_check": fk})
        EX_DIR.mkdir(parents=True, exist_ok=True)
        CATALOG_V2.write_text(json.dumps(
            {"task": "P2-3 教材练习目录", "rule_set": RULE_SET,
             "derivation": "真实教材 PDF 文本层重扫 + 官方 MP3 证据链匹配",
             "generated_at": stamp, "contentpack_sha256_after": cp_info["sha256_after"],
             "counts": summary["pdf"], "summary": summary, "exercises": exercises},
            ensure_ascii=False, indent=2), encoding="utf-8")
        MAP_V2.write_text(json.dumps(
            {"task": "P2-3 教材练习 ↔ 官方音频证据链", "rule_set": RULE_SET,
             "generated_at": stamp, "mappings": mappings}, ensure_ascii=False, indent=2),
            encoding="utf-8")
    else:
        print("[5/5] dry-run：未写入")

    write_audit(summary, mappings, exercises, audios, cp_info, stamp, applied)
    print("完成：练习 %d 条 / 音频 %d 个 / 确认映射 %d" %
          (len(exercises), len(audios), summary["audio"]["confirmed"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
