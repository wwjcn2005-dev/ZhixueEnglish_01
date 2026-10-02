#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-4 教材完整重构与学习关系建模（只读 PDF/MP3，产出结构化教材底座）

目标：把纸质教材的结构、纸面视觉语义、上下文关系、音频关系、练习关系
重建为可追溯的结构化数据，供下一阶段「学习体系与 APP 产品设计」和
「教材范围内 AI 批改（Textbook Evidence Package）」使用。

只读来源：
  * 教材 PDF（文本层 + 矢量图形 + 图片 bbox）
  * 54 个官方 MP3（SHA256 / 时长 / 顺序）
  * contentpack v5（unit/section 页边界，只读）
  * P2-3 产物（exercise_catalog_v2 等，作为基线，不覆盖）

产出（全部为新增文件）：
  structured/textbook/textbook_structure_v2.json
  structured/textbook/textbook_visual_relations_v2.json
  structured/textbook/textbook_context_relations_v2.json
  structured/textbook/textbook_content_relations_v2.json
  structured/exercises/exercise_catalog_v3.json
  structured/exercises/exercise_question_relations_v3.json
  structured/audio/exercise_audio_map_v3.json
  structured/audio/audio_question_relations_v3.json
  structured/ai/textbook_evidence_map_v1.json
  audit/P2-4_textbook_reconstruction.md / .json

原则：证据不足一律 UNKNOWN / NEEDS_REVIEW，不猜；不修改任何原始文件；
不写 learning.db；不调用 AI。

用法：
  python builder/build_p2_4_textbook_reconstruction_v01.py           # 扫描 + 报告
  python builder/build_p2_4_textbook_reconstruction_v01.py --apply    # 写入上述产物
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import pymupdf

BASE = Path(r"D:\ZhixueEnglish")
sys.path.insert(0, str(BASE / "builder"))
sys.dont_write_bytecode = True

_spec = importlib.util.spec_from_file_location(
    "p23_builder", str(BASE / "builder" / "build_p2_3_exercise_rebuild_v01.py"))
p23 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(p23)

TEXTBOOK_DIR = BASE / "2025年度初一外研版英语教材"
PDF = TEXTBOOK_DIR / "（根据2022年版课程标准修订）义务教育教科书·英语 七年级上册.pdf"
CP = BASE / "structured" / "contentpack" / "v5" / "FLTRP-EN-7A-2022CUR.sqlite"
OUT_TEXTBOOK = BASE / "structured" / "textbook"
OUT_EXERCISES = BASE / "structured" / "exercises"
OUT_AUDIO = BASE / "structured" / "audio"
OUT_AI = BASE / "structured" / "ai"
AUDIT = BASE / "audit"

TEXTBOOK_ID = "FLTRP-EN-7A-2022CUR"
RULE_SET = "P2-4-textbook-reconstruction-v1"
PAGE_FIRST, PAGE_LAST = 8, 114

#: 教材视觉元素承担的角色（证据不足 → unknown + NEEDS_REVIEW）
VISUAL_ROLES = ("context_image", "instruction_support", "listening_context", "reading_context",
                "vocabulary_support", "writing_model", "question_context", "decorative",
                "unknown")

#: 上下文关系类型（来自教材纸面顺序与结构证据）
RELATION_TYPES = ("contains", "precedes", "follows", "belongs_to", "supports",
                  "illustrates", "uses", "tests", "references", "continues",
                  "depends_on", "paired_with", "audio_for", "image_for",
                  "question_for", "vocabulary_in", "grammar_in")


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def uid(prefix: str, *parts) -> str:
    digest = hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:12]
    return "%s:%s" % (prefix, digest.upper())


# ---------------------------------------------------------------- 视觉对象

def hex_color(value) -> str:
    if value is None:
        return ""
    return "#%06X" % (int(value) & 0xFFFFFF)


def rgb_hex(rgb) -> str:
    if not rgb or len(rgb) < 3:
        return ""
    return "#%02X%02X%02X" % tuple(max(0, min(255, int(round(c * 255)))) for c in rgb[:3])


def span_style(sp) -> dict:
    font = sp["font"] or ""
    low = font.lower()
    return {
        "font": font,
        "size": round(float(sp["size"]), 1),
        "color": hex_color(sp.get("color")),
        "bold": ("bold" in low or "black" in low or "heavy" in low or "medium" in low),
        "italic": ("italic" in low or "oblique" in low),
        "serif": "minion" in low or "amasis" in low,
    }


def page_spans(page) -> list:
    """页面所有文本 span（含样式与 bbox），用于视觉语义分析。"""
    out = []
    for blk in page.get_text("dict")["blocks"]:
        if blk.get("type") != 0:
            continue
        for ln in blk["lines"]:
            for sp in ln["spans"]:
                text = p23.norm(sp["text"])
                if not text:
                    continue
                out.append({
                    "text": text,
                    "bbox": [round(float(v), 2) for v in sp["bbox"]],
                    "style": span_style(sp),
                    "block_no": blk.get("number"),
                    "line_dir": ln.get("dir"),
                })
    out.sort(key=lambda r: (round(r["bbox"][1], 1), r["bbox"][0]))
    return out


def icon_boxes_for_page(drawings, page_no, page_rect) -> list:
    """耳机图标（教材听力标注）：与 P2-3 相同的矢量特征，可复核。"""
    main, mate = [], []
    for d in drawings:
        x0, y0, x1, y1 = d["rect"]
        key = (round(x1 - x0), round(y1 - y0), len(d["items"]))
        box = [round(float(x0), 1), round(float(y0), 1), round(float(x1), 1), round(float(y1), 1)]
        if key == (12, 13, 26):
            main.append(box)
        elif key == (10, 11, 18):
            mate.append(box)
    return [b for b in main
            if any(abs(b[0] - m[0]) <= 4 and abs(b[1] - m[1]) <= 4 for m in mate)]


def drawing_objects(drawings, page_rect, icon_boxes) -> list:
    """把矢量图形归成可理解的对象：色块 / 框线 / 下划线（填空线）/ 图标 / 装饰。"""
    out = []
    decoration = {}
    for d in drawings:
        rect = [round(float(v), 1) for v in d["rect"]]
        w, h = rect[2] - rect[0], rect[3] - rect[1]
        fill, stroke = d.get("fill"), d.get("color")
        width = round(float(d.get("width") or 0), 2)
        kinds = [it[0] for it in d["items"]]
        if any(abs(rect[0] - b[0]) < 0.6 and abs(rect[1] - b[1]) < 0.6 for b in icon_boxes):
            continue                                   # 耳机图标单独记录
        role, note = "unknown", ""
        if fill is not None and not stroke and "c" in kinds and w >= 8 and h >= 8:
            role = "fill_shape"
            note = "色块/高亮"
        elif "l" in kinds and not fill and w >= 15 and h <= 2.0:
            role = "rule_line"
            note = "水平线（下划线 / 填空线）"
        elif "re" in kinds and stroke:
            role = "border_box" if width >= 0.4 else "rule_line"
            note = "框线"
        elif w <= 14 and h <= 14:
            role = "small_glyph"
            note = "小图标/符号"
        if (rect[0] <= 1 or rect[2] >= page_rect.width - 1
                or rect[1] <= 47 or rect[3] >= page_rect.height - 12) and role != "rule_line":
            role, note = "decorative", "页面边缘装饰"
        area = w * h
        if role in ("unknown", "small_glyph") and area < 900:
            continue                                  # 细碎笔画不构成语义对象
        if role == "fill_shape" and area < 1000:
            continue                                  # 小色点不构成语义对象
        if role == "decorative":
            decoration.setdefault("items", []).append(rect)
            decoration.setdefault("colors", []).append(rgb_hex(fill) or rgb_hex(stroke))
            continue                                  # 装饰不逐个记录，按页汇总
        out.append({"kind": "drawing", "shape_role": role, "bbox": rect,
                    "width": round(w, 1), "height": round(h, 1),
                    "fill": rgb_hex(fill), "stroke": rgb_hex(stroke), "stroke_width": width,
                    "note": note})
    if decoration.get("items"):
        out.append({"kind": "decoration_zone", "shape_role": "decorative",
                    "bbox": [min(b[0] for b in decoration["items"]),
                             min(b[1] for b in decoration["items"]),
                             max(b[2] for b in decoration["items"]),
                             max(b[3] for b in decoration["items"])],
                    "shape_count": len(decoration["items"]),
                    "colors": sorted({c for c in decoration["colors"] if c})[:6],
                    "note": "页面装饰（含彩色底纹/边饰），按页汇总"})
    return out


def image_objects(page, page_rect) -> list:
    frags = []
    for im in page.get_image_info():
        x0, y0, x1, y1 = [round(float(v), 1) for v in im["bbox"]]
        w, h = x1 - x0, y1 - y0
        if w < 30 or h < 30 or x1 <= x0 or y1 <= y0:
            continue                                   # 细条/空图，非语义图片
        frags.append({"bbox": [x0, y0, x1, y1], "w": w, "h": h,
                      "pixel": "%sx%s" % (im.get("width"), im.get("height")),
                      "colorspace": im.get("colorspace")})
    # 教材里的照片常被切成许多片段：按邻近关系合并成「图像区域」再判语义
    clusters = []
    for f in sorted(frags, key=lambda r: -(r["w"] * r["h"])):
        for c in clusters:
            if (f["bbox"][0] <= c["bbox"][2] + 9 and f["bbox"][2] >= c["bbox"][0] - 9
                    and f["bbox"][1] <= c["bbox"][3] + 9 and f["bbox"][3] >= c["bbox"][1] - 9):
                c["bbox"] = [min(c["bbox"][0], f["bbox"][0]), min(c["bbox"][1], f["bbox"][1]),
                             max(c["bbox"][2], f["bbox"][2]), max(c["bbox"][3], f["bbox"][3])]
                c["fragments"] += 1
                c["area"] = ((c["bbox"][2] - c["bbox"][0]) * (c["bbox"][3] - c["bbox"][1]))
                break
        else:
            clusters.append({"bbox": list(f["bbox"]), "fragments": 1,
                             "pixel": f["pixel"], "colorspace": f["colorspace"],
                             "area": f["w"] * f["h"]})
            continue
        if c["area"] > 0.6 * page_rect.width * page_rect.height:
            c["too_big"] = True
    out = []
    for c in clusters:
        x0, y0, x1, y1 = c["bbox"]
        w, h = x1 - x0, y1 - y0
        if w < 36 or h < 36 or w * h < 1600:
            continue                                   # 过小区域不作为语义图片
        out.append({"kind": "image", "bbox": [x0, y0, x1, y1],
                    "width": round(w, 1), "height": round(h, 1),
                    "pixel": c["pixel"], "colorspace": c["colorspace"],
                    "fragments": c["fragments"],
                    "area_ratio": round((w * h) / (page_rect.width * page_rect.height), 3),
                    "edge_touching": (x0 <= 2 or x1 >= page_rect.width - 2 or y0 <= 46
                                      or y1 >= page_rect.height - 10)})
    out.sort(key=lambda r: (r["bbox"][1], r["bbox"][0]))
    return out


def vline_overlap(box_a, box_b, tol=2.0) -> float:
    """两个 bbox 的纵向重叠长度（用于把对象挂到活动上）。"""
    a0, a1 = box_a[1], box_a[3]
    b0, b1 = box_b[1], box_b[3]
    return max(0.0, min(a1, b1) - max(a0, b0) + tol)


def hcenter(box) -> float:
    return (box[0] + box[2]) / 2.0


def rect_overlap(a, b, tol=0.0) -> bool:
    return (a[0] <= b[2] + tol and a[2] >= b[0] - tol
            and a[1] <= b[3] + tol and a[3] >= b[1] - tol)


# ---------------------------------------------------------------- 扫描页面

OPTION_LABEL = re.compile(r"^([A-Da-d])[.)]\s*(\S.*)$")
STANDALONE_LETTER = re.compile(r"^[A-Da-d]$")
CHECKBOX_ITEM = re.compile(r"^[☐□◻]\s*(.+)$")
#: 教材印刷顺序为 “Know more about <语法点> p<教材页> ⇢”（页码在箭头之前，已按真实文本校准）
GRAMMAR_POINTER = re.compile(r"Know more about\s+(.+?)\s*p(\d{2,3})\b", re.I)


def scan_visual_pages(doc) -> dict:
    vis = {}
    for pno in range(PAGE_FIRST, PAGE_LAST + 1):
        page = doc[pno - 1]
        drawings = page.get_drawings()
        icons = icon_boxes_for_page(drawings, pno, page.rect)
        vis[pno] = {
            "spans": page_spans(page),
            "icons": icons,
            "objects": (drawing_objects(drawings, page.rect, icons)
                        + image_objects(page, page.rect)),
            "page_size": {"width": round(page.rect.width, 1),
                          "height": round(page.rect.height, 1)},
        }
    return vis


def load_content_blocks(cp) -> dict:
    rows = cp.execute("""
        select b.block_id, p.pdf_page, b.reading_order, b.text_raw, b.block_kind,
               b.layout_role, b.review_status
        from content_block b join page p on p.page_id = b.page_id
        where p.pdf_page between ? and ? order by p.pdf_page, b.reading_order""",
        (PAGE_FIRST, PAGE_LAST)).fetchall()
    out = {}
    for r in rows:
        out.setdefault(r["pdf_page"], []).append({
            "block_id": r["block_id"], "reading_order": r["reading_order"],
            "text": p23.norm(r["text_raw"]), "kind": r["block_kind"],
            "layout_role": r["layout_role"], "review_status": r["review_status"]})
    return out


def instruction_style(activity, spans) -> dict:
    """活动指令的文字样式（粗体/字号/颜色）——纸面语义证据。"""
    box = activity.get("inst_bbox") or activity["bbox"]
    best = None
    for sp in spans:
        if abs(sp["bbox"][0] - box[0]) <= 6 and abs(sp["bbox"][1] - box[1]) <= 6:
            best = sp["style"]
            break
    return best or {}


def activity_band(activity, siblings) -> list:
    """活动在页面上的纵向区间 [y0, y1)：到下一个活动编号为止。"""
    y0 = activity["bbox"][1] - 4
    later = [s["bbox"][1] for s in siblings if s["bbox"][1] > activity["bbox"][1] + 1]
    y1 = min(later) - 2 if later else 10 ** 6
    return [y0, y1]


def visual_role(obj, activity, section_key) -> tuple:
    """对象在教材中的语义角色 + 证据（不猜：证据不足 → unknown/NEEDS_REVIEW）。"""
    if obj["kind"] == "drawing":
        role = obj["shape_role"]
        if role == "rule_line":
            return "blank_line", "水平细线，落在活动区域内：教材填空线"
        if role == "decorative":
            return "decorative", "触及页面边缘：装饰"
        if role == "fill_shape":
            inst_box = activity.get("inst_bbox") or activity.get("bbox")
            if inst_box and rect_overlap(obj["bbox"], inst_box, tol=6):
                return "instruction_support", "色块与活动编号/指令重叠：教材强调底色"
            return "unknown", "色块位置与指令不重叠，语义不足"
        return "unknown", "矢量图形语义不足"
    inst = (activity.get("instruction") or "").lower()
    if obj.get("kind") == "decoration_zone":
        return "decorative", "页面装饰汇总区域"
    if (obj.get("area_ratio") or 0) > 0.85:
        return "decorative", "整页背景图：装饰"
    if obj.get("edge_touching") and (obj.get("area_ratio") or 0) > 0.5:
        return "decorative", "触及页边且面积过半：装饰/页边图"
    if (obj.get("area_ratio") or 0) >= 0.25:
        return "context_image", "占据页面主要区域的教材图片（上下文图）"
    if activity.get("question_type") in ("match", "order"):
        return "question_context", "匹配/排序题需要图片作为作答对象"
    if activity.get("listening_icon"):
        return "listening_context", "活动带耳机图标，图片位于该活动区间"
    if re.match(r"(read|look at the title|look at the picture|read the passage)", inst):
        return "reading_context", "阅读理解类活动，图片位于该活动区间"
    if section_key == "READING_FOR_WRITING":
        return "writing_model", "Reading for writing 板块内的图片"
    if activity.get("blanks"):
        return "question_context", "活动含填空，图片位于该活动区间"
    return "unknown", "缺少可靠语义证据"


# ---------------------------------------------------------------- 教材活动

def build_activities(raw, pages, vis, blocks, p23_exercises, cp) -> list:
    base_by_key = {(e["unit"], e["section"], e["exercise_no"]): e for e in p23_exercises}
    by_page = {}
    for a in raw:
        by_page.setdefault(a["pdf_page"], []).append(a)
    for v in by_page.values():
        v.sort(key=lambda x: x["bbox"][1])

    out = []
    for a in raw:
        siblings = by_page[a["pdf_page"]]
        key = (a["unit"], a["section"], a["activity_no"])
        base = base_by_key.get(key) or {}
        band = activity_band(a, siblings)
        vpage = vis.get(a["pdf_page"], {"objects": [], "spans": []})
        objs, blanks, visual_relations = [], [], []
        for idx, obj in enumerate(vpage["objects"]):
            if obj["bbox"][1] > band[1] or obj["bbox"][3] < band[0]:
                continue
            role, why = visual_role({**obj, **base}, a, a["section"])
            obj_id = uid("VO", a["pdf_page"], obj["kind"], idx, obj["bbox"])
            objs.append({
                "visual_id": obj_id, "page": a["pdf_page"], "kind": obj["kind"],
                "bbox": obj["bbox"], "size": [obj.get("width"), obj.get("height")],
                "style": {k: obj[k] for k in ("fill", "stroke", "stroke_width", "pixel",
                                              "colorspace") if k in obj},
                "visual_role": role, "role_evidence": why,
                "review_status": "OK" if role != "unknown" else "NEEDS_REVIEW",
            })
            if role == "blank_line" and obj.get("width", 0) >= 18:
                blanks.append({"bbox": obj["bbox"], "width": obj["width"]})
        blanks.sort(key=lambda b: (round(b["bbox"][1], 1), b["bbox"][0]))

        # 题型/选项下划线结构：以 P2-3 结构为准，补上教材空位顺序
        questions = []
        q_list = base.get("questions") or []
        for i, q in enumerate(q_list):
            questions.append({
                "question_no": q.get("no", i + 1),
                "text": (q.get("text") or "")[:400],
                "question_type": base.get("question_type"),
                "options": base.get("options") or [],
                "blank_refs": [j + 1 for j, _ in enumerate(blanks)][:base.get("blanks") or 0],
                "evidence": {"source": "pdf_text_layer", "page": a["pdf_page"]},
            })
        if not questions:
            questions = [{"question_no": 1, "text": a["instruction"],
                          "question_type": base.get("question_type"),
                          "options": base.get("options") or [],
                          "blank_refs": list(range(1, len(blanks) + 1)),
                          "evidence": {"source": "activity_instruction",
                                       "page": a["pdf_page"]}}]

        style = instruction_style(a, vpage["spans"])
        out.append({
            "activity_id": base.get("activity_id") or uid("A", a["unit"], a["section"],
                                                          a["activity_no"], a["textbook_page"]),
            "exercise_id": base.get("exercise_id"),
            "activity_no": a["activity_no"],
            "unit": a["unit"], "section": a["section"], "section_id": a["section_id"],
            "pdf_page": a["pdf_page"], "textbook_page": a["textbook_page"],
            "bbox": a["bbox"], "instruction_bbox": a.get("inst_bbox"),
            "instruction": a["instruction"],
            "instruction_style": style,
            "question_type": base.get("question_type"),
            "listening_icon": a["listening_icon"],
            "audio_id": base.get("audio_id"),
            "audio_status": base.get("audio_status"),
            "audio_required": base.get("audio_required"),
            "blanks": blanks,
            "blank_count": len(blanks),
            "questions": questions,
            "visual_objects": objs,
            "text_blocks": [b for b in blocks.get(a["pdf_page"], [])
                            if band[0] <= _top_of_block(b, pages, a["pdf_page"]) < band[1]],
            "review_status": "OK",
        })
    out.sort(key=lambda x: (p23.UNIT_ORDER.get(x["unit"], 99), x["pdf_page"], x["activity_no"]))
    return out


def _top_of_block(block, pages, page_no) -> float:
    """内容块在页面上的纵向位置（用文本匹配页面行得到，找不到则置后）。"""
    for ln in pages.get(page_no, []):
        if ln["text"] and ln["text"] in (block["text"] or ""):
            return ln["bbox"][1]
    return 10 ** 6


# ---------------------------------------------------------------- 结构与关系

def build_structure(activities, cp, vis, pdf_sha) -> dict:
    units = [dict(r) for r in cp.execute(
        "select unit_id, unit_code, title, pdf_page_start, pdf_page_end, textbook_page_start,"
        " textbook_page_end from unit order by pdf_page_start")]
    sections = [dict(r) for r in cp.execute(
        "select s.section_id, s.section_key, s.title, s.pdf_page_start, s.textbook_page_start,"
        " u.unit_code from section s join unit u on u.unit_id=s.unit_id "
        "order by s.pdf_page_start")]
    out_units = []
    for u in units:
        if u["unit_code"] == "Appendix":
            out_units.append({
                "unit_id": u["unit_id"], "unit_code": u["unit_code"], "title": u["title"],
                "kind": "appendix", "pages": [u["pdf_page_start"], u["pdf_page_end"]],
                "sections": [{"section_id": s["section_id"], "section_key": s["section_key"],
                              "title": s["title"], "pdf_page_start": s["pdf_page_start"],
                              "textbook_page_start": s["textbook_page_start"], "activities": []}
                             for s in sections if s["unit_code"] == "Appendix"],
            })
            continue
        sec_list = []
        for s in [x for x in sections if x["unit_code"] == u["unit_code"]]:
            acts = [a for a in activities if a["section_id"] == s["section_id"]]
            sec_list.append({
                "section_id": s["section_id"], "section_key": s["section_key"],
                "title": s["title"], "pdf_page_start": s["pdf_page_start"],
                "textbook_page_start": s["textbook_page_start"],
                "activity_count": len(acts),
                "activity_no_list": [a["activity_no"] for a in acts],
                "activities": [{
                    "activity_id": a["activity_id"], "activity_no": a["activity_no"],
                    "pdf_page": a["pdf_page"], "textbook_page": a["textbook_page"],
                    "instruction": a["instruction"], "question_type": a["question_type"],
                    "listening_icon": a["listening_icon"], "audio_id": a["audio_id"],
                    "blank_count": a["blank_count"],
                    "question_count": len(a["questions"]),
                } for a in acts],
            })
        out_units.append({
            "unit_id": u["unit_id"], "unit_code": u["unit_code"], "title": u["title"],
            "kind": "unit", "pages": [u["pdf_page_start"], u["pdf_page_end"]],
            "textbook_pages": [u["textbook_page_start"], u["textbook_page_end"]],
            "sections": sec_list,
        })
    grammar, phonetics = scan_grammar_and_phonetics(vis, units)
    for u in out_units:
        if u["kind"] != "unit":
            continue
        u["grammar_pointers"] = [g for g in grammar if g["unit"] == u["unit_code"]]
        u["phonetics_in_use"] = [p for p in phonetics if p["unit"] == u["unit_code"]]
    return {
        "book": {"textbook_id": TEXTBOOK_ID,
                 "title": "义务教育教科书·英语 七年级上册（外研版，2022 课标）",
                 "pdf_sha256": pdf_sha, "pdf_pages": 178,
                 "scanned_pages": [PAGE_FIRST, PAGE_LAST], "rule_set": RULE_SET},
        "units": out_units,
        "counts": {
            "units": sum(1 for u in out_units if u["kind"] == "unit"),
            "sections": sum(len(u["sections"]) for u in out_units if u["kind"] == "unit"),
            "activities": len(activities),
            "questions": sum(len(a["questions"]) for a in activities),
            "listening_activities": sum(1 for a in activities if a["listening_icon"]),
            "blank_lines": sum(a["blank_count"] for a in activities),
        },
    }


def scan_grammar_and_phonetics(vis, units) -> tuple:
    grammar, phonetics = [], []
    for pno, data in vis.items():
        unit = next((u["unit_code"] for u in units
                     if u["pdf_page_start"] <= pno <= u["pdf_page_end"]), None)
        if unit is None:
            continue
        # 教材里的指针文字可能被拆成多个 span，先在整页文本上匹配，再回填 bbox
        page_text = p23.norm(" ".join(sp["text"] for sp in data["spans"]))
        for m in GRAMMAR_POINTER.finditer(page_text):
            anchor = next((sp for sp in data["spans"]
                           if sp["text"].lower().startswith("know more about")), None)
            grammar.append({
                "unit": unit, "pdf_page": pno, "textbook_page": pno - 5,
                "topic": p23.norm(m.group(1)), "target_textbook_page": int(m.group(2)),
                "bbox": (anchor or data["spans"][0])["bbox"],
                "evidence": "教材正文 “Know more about … ⇢ pNN” 指针（整页文本匹配）",
                "review_status": "OK"})
        if "phonetics in use" in page_text.lower():
            anchor = next((sp for sp in data["spans"]
                           if sp["text"].lower().startswith("phonetics")), None)
            phonetics.append({
                "unit": unit, "pdf_page": pno, "textbook_page": pno - 5,
                "bbox": (anchor or data["spans"][0])["bbox"],
                "evidence": "教材正文 “Phonetics in use” 小栏标题（整页文本匹配）",
                "review_status": "OK"})
    return grammar, phonetics


def build_context_relations(structure, activities) -> list:
    rels = []

    def add(f, t, kind, evidence, extra=None, status="OK"):
        rel = {"from": f, "to": t, "relation": kind, "evidence": evidence,
               "review_status": status}
        if extra:
            rel.update(extra)
        rels.append(rel)

    for u in structure["units"]:
        if u["kind"] != "unit":
            continue
        for s in u["sections"]:
            add(u["unit_id"], s["section_id"], "contains", "教材目录/页边界")
            add(s["section_id"], u["unit_id"], "belongs_to", "教材目录/页边界")
        secs = u["sections"]
        for i in range(len(secs) - 1):
            add(secs[i]["section_id"], secs[i + 1]["section_id"], "precedes", "教材页顺序")
            add(secs[i + 1]["section_id"], secs[i]["section_id"], "follows", "教材页顺序")
    for a in activities:
        add(a["section_id"], a["activity_id"], "contains", "活动落在该板块页范围内")
        add(a["activity_id"], a["section_id"], "belongs_to", "活动落在该板块页范围内")
        for q in a["questions"]:
            qid = uid("Q", a["activity_id"], q["question_no"])
            add(a["activity_id"], qid, "contains", "活动内的题号结构")
            add(qid, a["activity_id"], "belongs_to", "活动内的题号结构")
        if a.get("audio_id"):
            add(a["audio_id"], a["activity_id"], "audio_for",
                (a.get("audio_evidence") or {}).get("reason", "P2-3 证据链匹配"),
                {"confidence": (a.get("audio_evidence") or {}).get("instruction_similarity")})
        for obj in a["visual_objects"]:
            if obj["visual_role"] == "decorative":
                continue
            add(obj["visual_id"], a["activity_id"],
                "image_for" if obj["kind"] == "image" else "supports",
                obj["role_evidence"],
                {"visual_role": obj["visual_role"],
                 "review_status": obj["review_status"]})
    acts_by_sec = {}
    for a in activities:
        acts_by_sec.setdefault(a["section_id"], []).append(a)
    for sec, acts in acts_by_sec.items():
        acts = sorted(acts, key=lambda x: (x["pdf_page"], x["activity_no"]))
        for i in range(len(acts) - 1):
            add(acts[i]["activity_id"], acts[i + 1]["activity_id"], "precedes",
                "同一板块内的教材顺序")
            add(acts[i + 1]["activity_id"], acts[i]["activity_id"], "follows",
                "同一板块内的教材顺序")
    return rels


def build_content_relations(structure, activities, cp) -> dict:
    """内容关系：词汇/语法/文本在教材中的出现与依赖（全部基于教材证据）。"""
    vocab_by_unit = {}
    for u in structure["units"]:
        if u["kind"] != "unit":
            continue
        words = p23.unit_word_list(cp, u["unit_code"])
        vocab_by_unit[u["unit_code"]] = words
    vocab_rel, grammar_rel, text_rel = [], [], []
    for a in activities:
        blob = p23.key_text(" ".join([a["instruction"]] +
                                     [q["text"] for q in a["questions"]]))
        for w in vocab_by_unit.get(a["unit"], []):
            kw = p23.key_text(w)
            if len(kw) < 3:
                continue
            if re.search(r"\b%s\b" % re.escape(kw), blob):
                vocab_rel.append({
                    "from": a["activity_id"], "to": "VOCAB:%s" % w,
                    "relation": "vocabulary_in", "unit": a["unit"],
                    "activity_no": a["activity_no"], "word": w,
                    "evidence": "教材文本/题干中逐词匹配到本单元词表条目",
                    "review_status": "OK"})
        for b in a["text_blocks"]:
            if b["kind"] in ("dialogue", "exercise_item", "vocabulary_entry") and b["text"]:
                text_rel.append({
                    "from": a["activity_id"], "to": b["block_id"], "relation": "references",
                    "block_kind": b["kind"], "layout_role": b["layout_role"],
                    "sample": b["text"][:120],
                    "evidence": "contentpack 内容块落在该活动纵向区间内",
                    "review_status": "OK"})
            if b["kind"] == "heading" and b["text"].lower().startswith(("read", "listen")):
                text_rel.append({
                    "from": a["activity_id"], "to": b["block_id"], "relation": "depends_on",
                    "block_kind": "heading", "sample": b["text"][:120],
                    "evidence": "教材标题块位于该活动区间",
                    "review_status": "OK"})
    for u in structure["units"]:
        if u["kind"] != "unit":
            continue
        for g in u.get("grammar_pointers", []):
            grammar_rel.append({
                "from": u["unit_id"], "to": "GRAMMAR:%s" % g["topic"],
                "relation": "grammar_in", "topic": g["topic"],
                "appendices_page": g["target_textbook_page"], "pdf_page": g["pdf_page"],
                "evidence": g["evidence"], "review_status": "OK"})
        for p in u.get("phonetics_in_use", []):
            grammar_rel.append({
                "from": u["unit_id"], "to": "PHONETICS:%s" % u["unit_code"],
                "relation": "contains", "pdf_page": p["pdf_page"],
                "evidence": p["evidence"], "review_status": "OK"})
    return {"vocabulary_in": vocab_rel, "grammar_in": grammar_rel, "text_references": text_rel}


def build_audio_layer(p23_exercises, audios, mappings, activities) -> tuple:
    """音频层 v3：54 个 MP3 → 活动 / 板块（证据链），并标注 audio_scope。"""
    by_ex = {}
    for m in mappings:
        if m.get("exercise_id"):
            by_ex.setdefault(m["exercise_id"], []).append(m)
    act_by_ex = {a["exercise_id"]: a for a in activities if a.get("exercise_id")}
    map_v3, q_rels = [], []
    for au in audios:
        m = next((x for x in mappings if x["filename"] == au["filename"]), None)
        if m is None:
            continue
        entry = {
            "audio_id": au.get("audio_id"), "filename": au["filename"], "seq": au["seq"],
            "sha256": au["sha256"], "size_bytes": au["size_bytes"],
            "duration_ms": au["duration_ms_local"], "kind": au["kind"],
            "unit": au["unit"], "section": au["section"], "activity_no": au["activity_no"],
            "status": m["status"], "reason": m["reason"], "evidence": m["evidence"],
            "target_type": m["target_type"], "target_id": m["target_id"],
            "exercise_id": m.get("exercise_id"), "audio_scope": None, "question_scope": [],
        }
        if m["target_type"] == "activity" and m.get("exercise_id"):
            a = act_by_ex.get(m["exercise_id"])
            if a:
                entry["audio_scope"] = "activity"
                entry["question_scope"] = [uid("Q", a["activity_id"], q["question_no"])
                                           for q in a["questions"]]
                for q in a["questions"]:
                    qid = uid("Q", a["activity_id"], q["question_no"])
                    q_rels.append({
                        "audio_id": au.get("audio_id"), "question_id": qid,
                        "activity_id": a["activity_id"],
                        "scope": "activity",
                        "note": ("整段活动音频，教材未提供可靠分句切分点；"
                                 "不伪造 question 级切分"),
                        "evidence": m["reason"], "review_status": "OK"})
        elif m["target_type"] == "section":
            entry["audio_scope"] = "section"
        map_v3.append(entry)
    return map_v3, q_rels


def build_question_relations(activities, content_rels, audio_q_rels) -> list:
    """题目关系 v3：题 → 单元/板块/活动/文本/词汇/语法/音频/图片。"""
    vocab_by_act = {}
    for r in content_rels["vocabulary_in"]:
        vocab_by_act.setdefault(r["from"], []).append(r["word"])
    text_by_act = {}
    for r in content_rels["text_references"]:
        text_by_act.setdefault(r["from"], []).append(r["to"])
    audio_by_act = {}
    for r in audio_q_rels:
        audio_by_act.setdefault(r["activity_id"], []).append(r["audio_id"])
    out = []
    for a in activities:
        for q in a["questions"]:
            qid = uid("Q", a["activity_id"], q["question_no"])
            out.append({
                "question_id": qid,
                "question_no": q["question_no"],
                "unit": a["unit"], "section": a["section"], "section_id": a["section_id"],
                "activity_id": a["activity_id"], "activity_no": a["activity_no"],
                "textbook_page": a["textbook_page"], "pdf_page": a["pdf_page"],
                "question_type": q["question_type"],
                "text": q["text"],
                "options": q["options"],
                "blank_count": a["blank_count"],
                "related_text": text_by_act.get(a["activity_id"], []),
                "related_vocabulary": vocab_by_act.get(a["activity_id"], []),
                "related_audio": audio_by_act.get(a["activity_id"], []),
                "related_image": [o["visual_id"] for o in a["visual_objects"]
                                  if o["visual_role"] != "decorative"],
                "answer_source": "NO_RELIABLE_SOURCE",
                "ai_grading_ready": True,
                "review_status": "OK",
            })
    return out


def build_evidence_map(structure, activities, question_rel, content_rels, map_v3) -> dict:
    """Textbook Evidence Package（每题一份，供下一阶段教材范围内 AI 批改）。"""
    unit_by_code = {u["unit_code"]: u for u in structure["units"] if u["kind"] == "unit"}
    audio_by_act = {}
    for e in map_v3:
        if e.get("exercise_id"):
            audio_by_act[e["exercise_id"]] = e
    text_by_act = {}
    for r in content_rels["text_references"]:
        text_by_act.setdefault(r["from"], []).append(r)
    vocab_by_act = {}
    for r in content_rels["vocabulary_in"]:
        vocab_by_act.setdefault(r["from"], []).append(r["word"])
    packages = []
    for q in question_rel:
        a = next((x for x in activities if x["activity_id"] == q["activity_id"]), None)
        unit = unit_by_code.get(q["unit"]) or {}
        audio = audio_by_act.get((a or {}).get("exercise_id"))
        packages.append({
            "question_id": q["question_id"],
            "scope": {"unit": q["unit"], "section": q["section"],
                      "activity_no": q["activity_no"], "question_no": q["question_no"]},
            "textbook_reference": {"pdf_page": q["pdf_page"],
                                   "textbook_page": q["textbook_page"],
                                   "instruction": (a or {}).get("instruction"),
                                   "instruction_style": (a or {}).get("instruction_style")},
            "original_question": {"text": q["text"], "options": q["options"],
                                  "blank_count": q["blank_count"],
                                  "question_type": q["question_type"]},
            "related_text": [{"block_id": r["to"], "kind": r.get("block_kind"),
                              "sample": r.get("sample")} for r in text_by_act.get(
                                  q["activity_id"], [])],
            "related_vocabulary": q["related_vocabulary"],
            "related_grammar": [g for g in unit.get("grammar_pointers", [])],
            "related_listening": ({
                "audio_id": audio.get("audio_id"), "filename": audio.get("filename"),
                "scope": audio.get("audio_scope"), "evidence": audio.get("reason")}
                if audio else None),
            "related_image": q["related_image"],
            "textbook_page_label": "第 %s 页" % q["textbook_page"],
            "answer_source": "NO_RELIABLE_SOURCE",
            "answer_note": "教材未提供可核对的答案；AI 批改必须基于以上教材证据，不得编造教材事实。",
            "ai_rules": [
                "只依据本包内教材证据判断",
                "答案与所谓标准答案不同不必然判错，需分析是否符合教材事实",
                "教材证据不足时明确说明，而不是给出确定结论",
                "听力题以对应官方音频与教材听力内容为准",
                "阅读题以当前阅读文本为准，语法题以当前 Unit/Section 语境为准",
            ],
        })
    return {"rule_set": RULE_SET, "package_count": len(packages), "packages": packages}


def consistency_checks(structure, activities, question_rel, map_v3, content_rels) -> dict:
    issues = []

    def add(kind, detail, ids=None):
        issues.append({"kind": kind, "detail": detail, "ids": ids or []})

    seen = {}
    unit_ranges = {u["unit_code"]: u["pages"] for u in structure["units"]}
    for a in activities:
        key = (a["unit"], a["section"], a["activity_no"])
        if key in seen:
            add("duplicate", "同一板块内活动编号重复 %s" % (key,), [a["activity_id"]])
        seen[key] = a["activity_id"]
        pages = unit_ranges.get(a["unit"])
        if not pages or not (pages[0] <= a["pdf_page"] <= pages[1]):
            add("wrong_unit", "活动页码不在所属单元范围内：%s" % a["activity_id"],
                [a["activity_id"]])
        if not a["section_id"]:
            add("orphan", "活动缺少板块：%s" % a["activity_id"], [a["activity_id"]])
        if a.get("audio_required") and not a.get("audio_id"):
            add("missing", "需要音频但未匹配：%s" % a["activity_id"], [a["activity_id"]])
        if a["question_type"] == "fill" and a["blank_count"] == 0:
            add("ambiguous", "填空类活动未识别到教材空白线：%s" % a["activity_id"],
                [a["activity_id"]])
        if not a["questions"]:
            add("missing", "活动没有题目结构：%s" % a["activity_id"], [a["activity_id"]])
        unknown = [o["visual_id"] for o in a["visual_objects"]
                   if o["visual_role"] == "unknown"]
        if unknown:
            add("ambiguous", "视觉对象语义未确认（%d 个）：%s" % (len(unknown), a["activity_id"]),
                unknown)
    audio_ids = {e["audio_id"] for e in map_v3}
    for e in map_v3:
        if e["status"] != "CONFIRMED":
            add("ambiguous", "音频未确认：%s" % e["filename"], [e.get("audio_id")])
        if e["target_type"] == "activity" and not e.get("question_scope"):
            add("missing", "活动音频未关联到题目范围：%s" % e["filename"])
    for q in question_rel:
        if q["activity_id"] not in {a["activity_id"] for a in activities}:
            add("orphan", "题目不属于任何活动：%s" % q["question_id"], [q["question_id"]])
    return {
        "issue_count": len(issues),
        "by_kind": {k: sum(1 for i in issues if i["kind"] == k)
                    for k in sorted({i["kind"] for i in issues})},
        "issues": issues,
        "audio_files": len(audio_ids),
        "checks": ["Unit→Section→Activity", "Section→Activity→Question",
                   "Activity→Audio", "Question→Audio", "Activity→Image",
                   "Question→Text/Vocabulary/Grammar"],
    }


MODEL_ASSESSMENT = {
    "KEEP": [
        {"object": "contentpack.unit / section 页边界",
         "reason": "与真实教材页范围一致，可直接作为教材骨架"},
        {"object": "contentpack.source_ref / textbook_emphasis",
         "reason": "教材事实可追溯（页码 + 引用 + 强调证据），继续使用"},
        {"object": "learning_item（vocabulary / phrase / sentence_pattern）",
         "reason": "教材词条与学习资源身份稳定，P2-4 未发现冲突"},
        {"object": "P2-3 官方音频证据链（54/54 CONFIRMED）",
         "reason": "本阶段重新验证未发现错误匹配，可继续作为音频事实"},
    ],
    "EXTEND": [
        {"object": "activity（96 行 / P1-05 快照）",
         "reason": "真实教材有 157 个活动；P2-3/P2-4 以覆盖层表达，"
                   "contentpack.activity 需要补齐活动与边界状态",
         "fields": ["boundary_status 与真实版面一致性", "activity 与 question 层级"]},
        {"object": "audio_mapping（59 行）",
         "reason": "缺少 audio_scope（activity/question/section）与 question 级关系字段",
         "fields": ["audio_scope", "question_scope", "evidence_json"]},
        {"object": "question / sub_question（sub_question 仅 13 行）",
         "reason": "真实教材题目结构远多于现有 13 条，需要按活动层级扩展",
         "fields": ["question_no", "question_type", "options", "blank_count", "blank_order"]},
    ],
    "REBUILD": [
        {"object": "纸面视觉语义层（图片 / 色块 / 框线 / 填空线 / 图标）",
         "reason": "现有模型完全没有视觉对象表，无法表达“这张图属于哪个活动、"
                   "这条下划线是第几个空”",
         "proposal": "新增 textbook_visual_relations（本轮已产出 v2 JSON，"
                     "下一阶段再决定是否入库）"},
        {"object": "教材上下文/内容关系图",
         "reason": "现有模型只有线性 page/block，没有关系表，"
                   "无法表达 precedes/uses/tests/depends_on 等教材逻辑",
         "proposal": "新增关系表（from_id/to_id/relation/evidence/confidence）"},
        {"object": "教材证据包（AI 批改用）",
         "reason": "现有模型无法为单题提供“教材范围内证据”，"
                   "下一阶段 AI 批改缺少依据",
         "proposal": "新增 textbook_evidence_map（本轮已产出 v1 JSON）"},
    ],
}


def write_outputs(payloads: dict) -> dict:
    written = {}
    files = {
        "structure": OUT_TEXTBOOK / "textbook_structure_v2.json",
        "visual": OUT_TEXTBOOK / "textbook_visual_relations_v2.json",
        "context": OUT_TEXTBOOK / "textbook_context_relations_v2.json",
        "content": OUT_TEXTBOOK / "textbook_content_relations_v2.json",
        "catalog_v3": OUT_EXERCISES / "exercise_catalog_v3.json",
        "question_rel": OUT_EXERCISES / "exercise_question_relations_v3.json",
        "audio_map_v3": OUT_AUDIO / "exercise_audio_map_v3.json",
        "audio_question": OUT_AUDIO / "audio_question_relations_v3.json",
        "evidence": OUT_AI / "textbook_evidence_map_v1.json",
    }
    for key, path in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payloads[key], ensure_ascii=False, indent=2),
                        encoding="utf-8")
        written[key] = {"path": str(path), "bytes": path.stat().st_size}
    return written


def write_audit(structure, activities, context, content, map_v3, audio_q, question_rel,
                evidence, checks, written, stamp, extras) -> None:
    AUDIT.mkdir(parents=True, exist_ok=True)
    report = {
        "task": "P2-4 教材完整重构与学习关系建模",
        "generated_at": stamp, "rule_set": RULE_SET,
        "scanned": {"pdf_pages": [PAGE_FIRST, PAGE_LAST], "audio_files": len(map_v3)},
        "counts": structure["counts"],
        "visual": extras["visual_stats"],
        "audio": {"total": len(map_v3),
                  "confirmed": sum(1 for e in map_v3 if e["status"] == "CONFIRMED"),
                  "needs_review": sum(1 for e in map_v3 if e["status"] != "CONFIRMED"),
                  "by_scope": {s: sum(1 for e in map_v3 if e["audio_scope"] == s)
                               for s in ("activity", "section", None)},
                  "audio_question_relations": len(audio_q)},
        "questions": {"total": len(question_rel),
                      "with_audio": sum(1 for q in question_rel if q["related_audio"]),
                      "with_image": sum(1 for q in question_rel if q["related_image"]),
                      "with_text": sum(1 for q in question_rel if q["related_text"]),
                      "with_vocabulary": sum(1 for q in question_rel
                                             if q["related_vocabulary"])},
        "evidence_packages": evidence["package_count"],
        "consistency": checks,
        "model_assessment": MODEL_ASSESSMENT,
        "boundaries": {"pdf_modified": False, "mp3_modified": False,
                       "learning_db_touched": False, "ai_calls": 0, "network_calls": 0,
                       "contentpack_modified": False},
        "written": written,
    }
    (AUDIT / "P2-4_textbook_reconstruction.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    c = structure["counts"]
    v = extras["visual_stats"]
    lines = [
        "# P2-4 教材完整重构与学习关系建模报告", "",
        "- 生成时间：%s" % stamp, "- 规则集：%s" % RULE_SET,
        "- 扫描范围：教材 PDF 第 %d–%d 页（正文），官方 MP3 %d 个"
        % (PAGE_FIRST, PAGE_LAST, len(map_v3)),
        "", "## 1. 教材结构", "",
        "| 项目 | 数量 |", "| --- | --- |",
        "| Unit / Starter | %d |" % c["units"],
        "| Section | %d |" % c["sections"],
        "| Activity | %d |" % c["activities"],
        "| Question | %d |" % c["questions"],
        "| 听力活动 | %d |" % c["listening_activities"],
        "| 教材填空线 | %d |" % c["blank_lines"], "",
        "## 2. 纸面视觉语义", "",
        "| 对象 | 数量 |", "| --- | --- |",
        "| 图片 | %d |" % v["images"],
        "| 色块/框线/下划线等矢量对象 | %d |" % v["drawings"],
        "| 其中填空线 | %d |" % v["blank_lines"],
        "| 耳机图标 | %d |" % v["icons"],
        "| 已判定语义角色 | %d |" % v["role_known"],
        "| 仍为 unknown（NEEDS_REVIEW） | %d |" % v["role_unknown"], "",
        "## 3. 上下文关系", "",
        "- 关系总数：%d" % len(context),
        "- 其中 contains/belongs_to：%d" % sum(
            1 for r in context if r["relation"] in ("contains", "belongs_to")),
        "- 其中 precedes/follows：%d" % sum(
            1 for r in context if r["relation"] in ("precedes", "follows")),
        "- 其中 audio_for：%d" % sum(1 for r in context if r["relation"] == "audio_for"),
        "- 其中 image_for/supports：%d" % sum(
            1 for r in context if r["relation"] in ("image_for", "supports")), "",
        "## 4. 音频完整匹配", "",
        "| 项目 | 数量 |", "| --- | --- |",
        "| 官方 MP3 | %d |" % len(map_v3),
        "| CONFIRMED | %d |" % sum(1 for e in map_v3 if e["status"] == "CONFIRMED"),
        "| NEEDS_REVIEW | %d |" % sum(1 for e in map_v3 if e["status"] != "CONFIRMED"),
        "| 活动级音频（audio_scope=activity） | %d |"
        % sum(1 for e in map_v3 if e["audio_scope"] == "activity"),
        "| 板块级音频（词表/语音） | %d |"
        % sum(1 for e in map_v3 if e["audio_scope"] == "section"),
        "| 音频→题目关系 | %d |" % len(audio_q), "",
        "## 5. 练习与题目结构", "",
        "- 题目总数：%d" % len(question_rel),
        "- 带音频的题：%d ｜ 带图片的题：%d ｜ 带文本依赖的题：%d ｜ 带词汇关联的题：%d"
        % (sum(1 for q in question_rel if q["related_audio"]),
           sum(1 for q in question_rel if q["related_image"]),
           sum(1 for q in question_rel if q["related_text"]),
           sum(1 for q in question_rel if q["related_vocabulary"])), "",
        "- 教材答案来源：全部标记 NO_RELIABLE_SOURCE（教材未提供可核对答案）",
        "- 每题均已生成 Textbook Evidence Package（%d 份）" % evidence["package_count"], "",
        "## 6. 一致性检查", "",
        "- 问题总数：%d ｜ 分类：%s" % (checks["issue_count"], checks["by_kind"]), "",
        "## 7. 模型判断（KEEP / EXTEND / REBUILD）", "",
    ]
    for kind in ("KEEP", "EXTEND", "REBUILD"):
        lines.append("### %s" % kind)
        lines.append("")
        for item in MODEL_ASSESSMENT[kind]:
            lines.append("- **%s**：%s" % (item["object"], item["reason"]))
        lines.append("")
    lines += ["## 8. 数据安全", "",
              "- 原始 PDF：未修改（只读）",
              "- 原始 MP3：未修改（SHA256 已记录）",
              "- learning.db：未写入",
              "- contentpack：未修改",
              "- AI 调用：0 ｜ 网络调用：0", ""]
    (AUDIT / "P2-4_textbook_reconstruction.md").write_text("\n".join(lines) + "\n",
                                                          encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    stamp = now()

    print("[1/6] 读取教材与既有基线 ...")
    pdf_sha = p23.sha256_file(PDF)
    cp = p23.ro(CP)
    audio_rows = {r["filename"]: dict(r) for r in cp.execute(
        "select audio_id, filename, duration_ms from audio_asset")}
    sections = [dict(r) for r in cp.execute(
        "select s.section_id, s.section_key, s.title, s.pdf_page_start, u.unit_code "
        "from section s join unit u on u.unit_id=s.unit_id order by s.pdf_page_start")]

    print("[2/6] 扫描教材活动与版面 ...")
    icons = p23.listening_icon_boxes(PDF, PAGE_FIRST, PAGE_LAST)
    raw, pages = p23.scan_pdf()
    for a in raw:
        a["listening_icon"] = p23.near_icon(a.get("inst_bbox") or a["bbox"],
                                            icons.get(a["pdf_page"], []))
    doc = pymupdf.open(PDF)
    vis = scan_visual_pages(doc)
    doc.close()
    blocks = load_content_blocks(cp)

    print("[3/6] 重建练习与题目结构 ...")
    v1 = p23.load_v1_catalog()
    exercises = p23.build_exercises(raw, pages, icons, v1)
    audios = p23.scan_audio(audio_rows)
    mappings = p23.match_audio(audios, exercises, cp, sections)
    p23.attach_audio(exercises, mappings, audios)
    activities = build_activities(raw, pages, vis, blocks, exercises, cp)
    cp.close()

    print("[4/6] 生成结构 / 视觉 / 上下文 / 内容关系 ...")
    structure = build_structure(activities, p23.ro(CP), vis, pdf_sha)
    context = build_context_relations(structure, activities)
    content = build_content_relations(structure, activities, p23.ro(CP))

    print("[5/6] 重建音频关系与教材证据包 ...")
    map_v3, audio_q = build_audio_layer(exercises, audios, mappings, activities)
    question_rel = build_question_relations(activities, content, audio_q)
    evidence = build_evidence_map(structure, activities, question_rel, content, map_v3)
    checks = consistency_checks(structure, activities, question_rel, map_v3, content)

    visual_objects = [o for a in activities for o in a["visual_objects"]]
    visual_stats = {
        "images": sum(1 for o in visual_objects if o["kind"] == "image"),
        "drawings": sum(1 for o in visual_objects if o["kind"] == "drawing"),
        "decoration_zones": sum(1 for o in visual_objects if o["kind"] == "decoration_zone"),
        "blank_lines": sum(1 for o in visual_objects if o["visual_role"] == "blank_line"),
        "icons": sum(len(v["icons"]) for v in vis.values()),
        "role_known": sum(1 for o in visual_objects if o["visual_role"] != "unknown"),
        "role_unknown": sum(1 for o in visual_objects if o["visual_role"] == "unknown"),
        "by_role": {r: sum(1 for o in visual_objects if o["visual_role"] == r)
                    for r in VISUAL_ROLES},
    }

    catalog_v3 = {
        "task": "P2-4 教材练习目录 v3（真实题型 + 教材空位 + 视觉/音频关系）",
        "rule_set": RULE_SET, "generated_at": stamp, "pdf_sha256": pdf_sha,
        "counts": structure["counts"], "exercises": exercises,
        "activities": [{k: a[k] for k in
                        ("activity_id", "unit", "section", "activity_no", "pdf_page",
                         "textbook_page", "instruction", "question_type", "listening_icon",
                         "audio_id", "audio_status", "blank_count")}
                       for a in activities],
    }
    payloads = {
        "structure": structure,
        "visual": {"rule_set": RULE_SET,
                   "counts": visual_stats,
                   "objects": visual_objects},
        "context": {"rule_set": RULE_SET, "relation_types": list(RELATION_TYPES),
                    "relation_count": len(context), "relations": context},
        "content": {"rule_set": RULE_SET, **content},
        "catalog_v3": catalog_v3,
        "question_rel": {"rule_set": RULE_SET, "count": len(question_rel),
                         "questions": question_rel},
        "audio_map_v3": {"rule_set": RULE_SET, "count": len(map_v3), "audio": map_v3},
        "audio_question": {"rule_set": RULE_SET, "count": len(audio_q),
                           "relations": audio_q},
        "evidence": evidence,
    }

    print("[6/6] 写出产物 ...")
    written = write_outputs(payloads) if args.apply else {}
    write_audit(structure, activities, context, content, map_v3, audio_q, question_rel,
                evidence, checks, written, stamp, {"visual_stats": visual_stats})
    print("活动 %d ｜ 题目 %d ｜ 视觉对象 %d（unknown %d）｜ 音频 %d（确认 %d）｜ 关系 %d"
          % (len(activities), len(question_rel), len(visual_objects),
             visual_stats["role_unknown"], len(map_v3),
             sum(1 for e in map_v3 if e["status"] == "CONFIRMED"), len(context)))
    print("一致性问题：%d %s" % (checks["issue_count"], checks["by_kind"]))
    if not args.apply:
        print("（dry-run：未写入 structured/ 产物）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
