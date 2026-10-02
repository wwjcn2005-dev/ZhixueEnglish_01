#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P1-03 教材结构解析器 V0.1

目标：把外研版七年级上册 PDF（178 页）解析成“可审核的教材结构结果”，
但本版本不建立正式教材数据库、不导出图片、不写回任何原始教材文件。

设计原则：
  1. 教材是唯一内容依据，所有结构节点都必须能追溯回 PDF 页面与 bbox。
  2. 准确性优先于自动化程度：无法可靠判断时标记 NEED_REVIEW，不猜。
  3. 所有文本先做 NFKC 归一化，解决 fi/fl 连字（U+FB01/U+FB02）问题。
  4. 不信任 page.get_text("blocks") 的原始顺序，按版面类型重建阅读顺序。

运行：
  python D:\\ZhixueEnglish\\parser\\textbook_parser_v01.py
可选：
  --json-out <path>   额外写出结构化结果（默认不写任何文件）
  --focus 19,22,24    只打印这些 PDF 页的详细块顺序
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

import pymupdf

# --------------------------------------------------------------------------
# 常量与路径
# --------------------------------------------------------------------------

BASE_DIR = Path(r"D:\ZhixueEnglish")
SOURCE_DIR = BASE_DIR / "2025年度初一外研版英语教材"
PAGE_OFFSET = 5                     # 教材印刷页码 = PDF 页码 - 5（p.7 起有效）
FRONT_MATTER_LAST_PDF_PAGE = 6      # PDF p.1-6：封面/扉页/前言/目录，无印刷页码
BACK_COVER_PDF_PAGE = 178           # 封底，无印刷页码

SECTION_TITLES = [
    "Get ready",
    "Know your school",
    "Get to know each other",
    "Make a wishing tree",
    "Welcome to junior high",
    "Starting out",
    "Understanding ideas",
    "Developing ideas",
    "Presenting ideas",
    "Reflection",
    "Reading for writing",
    "Phonetics in use",
    "Communication bank",
    "Language notes",
    "Guide to the language use",
    "Words and expressions",
    "Proper nouns",
    "Vocabulary",
    "Pronunciation guide",
    "Appendices",
]

SIDEBAR_PATTERNS = [
    r"^Grammar rules",
    r"^Learning to think",
    r"^Learning to learn",
    r"^Language notes",
    r"^Useful expressions",
    r"^Phonetics",
    r"^注[：:]",
]

BOLD_FONT_HINTS = ("Black", "Heavy", "Bold")

# Activity 编号判定：教材把活动号放在左侧页边，字体为 Black/Heavy/Bold，字号 12 左右
ACTIVITY_MARGIN_RATIO = 0.135     # x0 <= 页宽 * 0.135 视为页边
ACTIVITY_SIZE_MIN = 10.5
ACTIVITY_SIZE_MAX = 21.0
PARAGRAPH_MIN_CHARS = 80          # 阅读课文段落编号的段落长度下限
PARAGRAPH_MIN_COUNT = 3           # 连续段落编号达到该数量即判定为段落编号而非 Activity
PARAGRAPH_MIN_TOTAL_CHARS = 180   # 段落编号组的总字符下限

# 任务指令的典型起始词（用于区分“Activity 指令”与“课文段落/填空小问”）
TASK_START_WORDS = (
    "read", "listen", "work", "choose", "complete", "circle", "answer", "match", "tick",
    "draw", "write", "find", "look", "discuss", "talk", "think", "describe", "guess",
    "point", "say", "repeat", "practise", "practice", "make", "fill", "correct", "put",
    "change", "give", "share", "present", "act", "copy", "retell", "check", "number",
    "label", "order", "use", "imagine", "ask", "tell", "show", "introduce", "prepare",
    "compare", "note", "underline", "translate", "spell", "do", "play", "plan", "design",
    "create", "search", "interview", "vote", "decide", "explain",
    "what", "why", "how", "who", "where", "which", "when",
)


# --------------------------------------------------------------------------
# 数据结构
# --------------------------------------------------------------------------

@dataclass
class SpanModel:
    text: str
    bbox: tuple
    font: str
    size: float
    flags: int


@dataclass
class LineModel:
    bbox: tuple
    spans: list

    @property
    def text(self) -> str:
        return "".join(s.text for s in self.spans)


@dataclass
class TextBlock:
    index: int
    bbox: tuple
    lines: list
    text: str
    raw_text: str
    max_size: float
    fonts: list
    flags: list
    role: str = "body"          # body/header/footer/heading/sidebar/section_title/unit_number/activity_number
    column: int = 0
    order_index: int = -1

    @property
    def x0(self) -> float:
        return self.bbox[0]

    @property
    def y0(self) -> float:
        return self.bbox[1]

    @property
    def x1(self) -> float:
        return self.bbox[2]

    @property
    def y1(self) -> float:
        return self.bbox[3]

    @property
    def width(self) -> float:
        return self.bbox[2] - self.bbox[0]

    @property
    def is_text(self) -> bool:
        return self.role not in ("header", "footer")


@dataclass
class ImageObject:
    xref: int
    width: int
    height: int
    colorspace: str
    filter: str
    tiny_fragment: bool


@dataclass
class ImageBlock:
    bbox: tuple
    width: int
    height: int


@dataclass
class PageModel:
    pdf_page: int
    textbook_page: Optional[int]
    textbook_page_evidence: str
    width: float
    height: float
    text: str
    text_raw: str
    text_chars: int
    blocks: list = field(default_factory=list)
    words: list = field(default_factory=list)
    image_objects: list = field(default_factory=list)
    image_blocks: list = field(default_factory=list)
    layout_type: str = "unknown"
    reading_order_status: str = "UNKNOWN"
    ordered_block_indices: list = field(default_factory=list)
    activity_rejections: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    needs_review: bool = False

    def text_blocks(self, include_footer: bool = False) -> list:
        out = []
        for b in self.blocks:
            if b.role == "footer" and not include_footer:
                continue
            out.append(b)
        return out


@dataclass
class SectionModel:
    unit_id: str
    title: str
    pdf_page_start: int
    textbook_page_start: Optional[int]
    bbox: tuple
    evidence: str
    activity_count: int = 0
    needs_review: bool = False
    notes: list = field(default_factory=list)


@dataclass
class ActivityModel:
    unit_id: str
    section_title: str
    number: int
    kind: str
    pdf_page: int
    textbook_page: Optional[int]
    bbox: tuple
    instruction: str
    boundary_status: str
    sidebar_relation: str = ""
    notes: list = field(default_factory=list)
    audio_candidates: list = field(default_factory=list)


@dataclass
class UnitModel:
    unit_id: str
    toc_title: str
    title: str
    pdf_page_start: int
    pdf_page_end: int
    textbook_page_start: Optional[int]
    textbook_page_end: Optional[int]
    evidence: list = field(default_factory=list)
    sections: list = field(default_factory=list)
    activities: list = field(default_factory=list)
    needs_review: bool = False


# --------------------------------------------------------------------------
# 文本工具
# --------------------------------------------------------------------------

def normalize_text(text: str) -> str:
    """NFKC 归一化并清除非法的旧编码控制字符。"""
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", text)
    # 安全网：个别字体可能仍以控制码表示连字（P0-01 已确认 0x1F=fi, 0x1D=fl）
    t = t.replace("\x1f", "fi").replace("\x1d", "fl")
    return t


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", normalize_text(text)).strip()


def is_bold_font(font: str) -> bool:
    return any(h in font for h in BOLD_FONT_HINTS)


def is_sidebar_text(text: str) -> bool:
    t = compact(text)
    return any(re.match(p, t, re.IGNORECASE) for p in SIDEBAR_PATTERNS)


def match_section_title(text: str) -> Optional[str]:
    t = compact(text)
    t = re.sub(r"^\d{1,2}[\s\u00a0]*", "", t)
    t_low = t.lower()
    for title in SECTION_TITLES:
        name = title.lower()
        if t_low == name:
            return title
        # 教材中标题常与相邻文字合并绘制（如 "Make a profile of an animal.Presenting ideas"）
        if len(t) <= len(title) + 40 and (t_low.startswith(name) or t_low.endswith(name)):
            return title
    return None


def strip_leading_number(text: str) -> tuple[Optional[int], str]:
    m = re.match(r"^(\d{1,2})[\s\u00a0]*(\S.*)$", compact(text))
    if m:
        return int(m.group(1)), m.group(2)
    return None, compact(text)


def is_task_instruction(text: str) -> bool:
    """判断编号后面的文字是否像教材活动指令（而不是课文段落/填空小问）。"""
    _num, rest = strip_leading_number(text)
    if not rest:
        return False
    m = re.match(r"^([A-Za-z’'\-]+)", rest)
    if not m:
        return False
    return m.group(1).lower() in TASK_START_WORDS


QUESTION_START_WORDS = ("what", "why", "how", "who", "where", "which", "when")


def is_question_list_instruction(text: str) -> bool:
    """判断编号块是否是“一问一答/多小问”清单，而不是 Activity 指令。

    特征：编号后直接是疑问句，并且同一块里还出现第二个编号。
    例如：p.45 的 “1 What hobby do the pictures show?2 What can you get…?”
    """
    _num, rest = strip_leading_number(text)
    if not rest:
        return False
    m = re.match(r"^([A-Za-z’'\-]+)", rest)
    if not m or m.group(1).lower() not in QUESTION_START_WORDS:
        return False
    return len(re.findall(r"\d{1,2}[\s\u00a0]+[A-Z“]", rest)) >= 1


# --------------------------------------------------------------------------
# 解析器
# --------------------------------------------------------------------------

class TextbookParser:
    def __init__(self, pdf_path: Path):
        self.pdf_path = pdf_path
        self.doc: Optional[pymupdf.Document] = None
        self.pages: list[PageModel] = []
        self.units: list[UnitModel] = []
        self.sections: list[SectionModel] = []
        self.activities: list[ActivityModel] = []
        self.audio_files: list[dict] = []
        self.review_items: list[dict] = []
        self.quality: dict = {}

    # ---------------- 基础解析 ----------------

    def load(self) -> None:
        self.doc = pymupdf.open(str(self.pdf_path))
        if self.doc.page_count != 178:
            raise RuntimeError(f"页数异常：期望 178，实际 {self.doc.page_count}")

    def parse_pages(self) -> None:
        assert self.doc is not None
        for page_index in range(self.doc.page_count):
            page = self.doc[page_index]
            pdf_page = page_index + 1
            textbook_page, evidence = self.resolve_textbook_page(page, pdf_page)

            text_raw = page.get_text("text")
            text = normalize_text(text_raw)
            text_chars = len(re.sub(r"\s+", "", text))
            blocks = self.build_blocks(page)
            words = self.build_words(page)
            image_objects = self.build_image_objects(page)
            image_blocks = self.build_image_blocks(page)

            pm = PageModel(
                pdf_page=pdf_page,
                textbook_page=textbook_page,
                textbook_page_evidence=evidence,
                width=page.rect.width,
                height=page.rect.height,
                text=text,
                text_raw=text_raw,
                text_chars=text_chars,
                blocks=blocks,
                words=words,
                image_objects=image_objects,
                image_blocks=image_blocks,
            )
            self.classify_layout(pm)
            self.assign_reading_order(pm)
            self.pages.append(pm)

    def resolve_textbook_page(self, page: "pymupdf.Page", pdf_page: int) -> tuple[Optional[int], str]:
        """页码映射：优先用页脚里的实际印刷页码，其次用 pdf-5，特殊页返回 None。"""
        if pdf_page <= FRONT_MATTER_LAST_PDF_PAGE:
            return None, "front_matter"
        if pdf_page >= BACK_COVER_PDF_PAGE:
            return None, "back_cover"

        derived = pdf_page - PAGE_OFFSET
        footer_numbers = []
        for b in page.get_text("dict")["blocks"]:
            if b.get("type") != 0:
                continue
            if b["bbox"][1] < page.rect.height * 0.90:
                continue
            txt = normalize_text("".join(s["text"] for l in b["lines"] for s in l["spans"]))
            footer_numbers += [int(n) for n in re.findall(r"\d{1,3}", txt)]

        if not footer_numbers:
            return None, "no_printed_page_number"
        if derived in footer_numbers:
            return derived, "footer_confirmed"
        return derived, f"derived_only(footer={footer_numbers})"

    def build_blocks(self, page: "pymupdf.Page") -> list:
        blocks = []
        for idx, raw in enumerate(page.get_text("dict")["blocks"]):
            if raw.get("type") != 0:
                continue
            lines = []
            for raw_line in raw.get("lines", []):
                spans = [
                    SpanModel(
                        text=normalize_text(s["text"]),
                        bbox=tuple(round(v, 2) for v in s["bbox"]),
                        font=s["font"],
                        size=round(s["size"], 2),
                        flags=s["flags"],
                    )
                    for s in raw_line.get("spans", [])
                ]
                if spans:
                    lines.append(LineModel(bbox=tuple(round(v, 2) for v in raw_line["bbox"]), spans=spans))
            if not lines:
                continue
            raw_text = "".join(l.text for l in lines)
            text = normalize_text(raw_text)
            sizes = [s.size for l in lines for s in l.spans]
            blocks.append(
                TextBlock(
                    index=len(blocks),
                    bbox=tuple(round(v, 2) for v in raw["bbox"]),
                    lines=lines,
                    text=text,
                    raw_text=raw_text,
                    max_size=max(sizes),
                    fonts=sorted({s.font for l in lines for s in l.spans}),
                    flags=sorted({s.flags for l in lines for s in l.spans}),
                )
            )
        return blocks

    def build_words(self, page: "pymupdf.Page") -> list:
        return [
            {
                "text": normalize_text(w[4]),
                "bbox": tuple(round(v, 2) for v in w[:4]),
                "block": w[5],
                "line": w[6],
                "word_no": w[7],
            }
            for w in page.get_text("words")
        ]

    def build_image_objects(self, page: "pymupdf.Page") -> list:
        out = []
        for im in page.get_images(full=True):
            xref, _smask, width, height, _bpc, cs, _alt, _name, filt, _ref = im[:10]
            out.append(
                ImageObject(
                    xref=xref,
                    width=width,
                    height=height,
                    colorspace=str(cs),
                    filter=str(filt),
                    tiny_fragment=(width < 50 or height < 50),
                )
            )
        return out

    def build_image_blocks(self, page: "pymupdf.Page") -> list:
        out = []
        for raw in page.get_text("dict")["blocks"]:
            if raw.get("type") == 1:
                out.append(
                    ImageBlock(
                        bbox=tuple(round(v, 2) for v in raw["bbox"]),
                        width=int(raw.get("width", 0)),
                        height=int(raw.get("height", 0)),
                    )
                )
        return out

    # ---------------- 角色与版面 ----------------

    def mark_block_roles(self, pm: PageModel) -> None:
        h = pm.height
        for b in pm.blocks:
            text = compact(b.text)
            if not text:
                continue
            if b.y0 >= h * 0.90:
                b.role = "footer"
                continue
            # 侧栏标记要先于页眉判断，否则页面上方的 Grammar/学习提示会被误判成页眉
            if is_sidebar_text(text):
                b.role = "sidebar"
                continue
            if b.y1 <= h * 0.06 and b.max_size <= 11:
                b.role = "header"
                continue
            if re.fullmatch(r"\d{1,2}", text) and b.max_size >= 25:
                b.role = "unit_number"
                continue
            if match_section_title(text):
                b.role = "section_title"
                continue
            # 侧栏：窄块且位于右侧，或明确的侧栏标记
            if b.width <= pm.width * 0.42 and b.x0 >= pm.width * 0.55 and b.max_size <= 12:
                b.role = "sidebar"
                continue
            if b.max_size >= 15:
                b.role = "heading"
                continue
            b.role = "body"

    def classify_layout(self, pm: PageModel) -> None:
        self.mark_block_roles(pm)
        text_blocks = [b for b in pm.blocks if b.role not in ("header", "footer")]
        image_blocks = len(pm.image_blocks)

        if image_blocks >= 150 and len(text_blocks) <= 25:
            pm.layout_type = "dense_visual"
            pm.reading_order_status = "NEED_REVIEW"
            return

        mid = pm.width / 2.0
        left = [b for b in text_blocks if b.x1 <= mid + 8]
        right = [b for b in text_blocks if b.x0 >= mid - 8]
        spanning = [b for b in text_blocks if b not in left and b not in right]

        if len(left) >= 3 and len(right) >= 3 and not spanning:
            pm.layout_type = "two_column"
            pm.reading_order_status = "OK"
            return

        # 单栏正文 + 右侧栏（如 p.24 的 Grammar rules 侧栏）：
        # 侧栏必须是明确的辅助说明，否则不套用该规则
        body = [b for b in text_blocks if b.x0 < pm.width * 0.55]
        side = [b for b in text_blocks if b.x0 >= pm.width * 0.55]
        side_marks = [b for b in side if is_sidebar_text(b.text)]
        # 标题/居中大字号块不代表栏起点，做“单栏判定”时排除
        body_core = [b for b in body if b.role not in ("heading", "section_title")] or body
        if (
            body
            and side
            and side_marks
            and len(side_marks) >= max(1, int(len(side) * 0.8))
            and self.is_single_column_like(body_core, pm)
        ):
            pm.layout_type = "single_column_with_sidebar"
            pm.reading_order_status = "OK_SIDEBAR_LAST"
            pm.notes.append("单栏正文 + 辅助侧栏，侧栏统一排在正文之后")
            return

        if any(b.role == "sidebar" for b in text_blocks):
            pm.layout_type = "mixed"
            pm.reading_order_status = "NEED_REVIEW"
            return

        pm.layout_type = "single_column"
        pm.reading_order_status = "OK"

    @staticmethod
    def is_single_column_like(blocks: list, pm: PageModel) -> bool:
        """判断一组 block 是否属于同一栏：起点 x0 集中且宽度相近。"""
        if len(blocks) < 3:
            return False
        xs = sorted(b.x0 for b in blocks)
        span = xs[-1] - xs[0]
        if span > pm.width * 0.25:
            return False
        widths = sorted(b.width for b in blocks)
        median = widths[len(widths) // 2]
        return median >= pm.width * 0.25

    def assign_reading_order(self, pm: PageModel) -> None:
        text_blocks = [b for b in pm.blocks if b.role not in ("header", "footer")]
        headers = [b for b in pm.blocks if b.role == "header"]
        footers = [b for b in pm.blocks if b.role == "footer"]

        if pm.layout_type == "two_column":
            mid = pm.width / 2.0
            full_width = [b for b in text_blocks if b.width >= pm.width * 0.6]
            column_blocks = [b for b in text_blocks if b not in full_width]
            left = sorted([b for b in column_blocks if b.bbox[0] + b.width / 2 <= mid], key=lambda b: (b.y0, b.x0))
            right = sorted([b for b in column_blocks if b.bbox[0] + b.width / 2 > mid], key=lambda b: (b.y0, b.x0))
            ordered = sorted(full_width, key=lambda b: (b.y0, b.x0)) + left + right
        elif pm.layout_type == "single_column_with_sidebar":
            body = sorted(
                [b for b in text_blocks if b.x0 < pm.width * 0.55], key=lambda b: (b.y0, b.x0)
            )
            side = sorted(
                [b for b in text_blocks if b.x0 >= pm.width * 0.55], key=lambda b: (b.y0, b.x0)
            )
            ordered = body + side
        elif pm.layout_type in ("single_column",):
            ordered = sorted(text_blocks, key=lambda b: (b.y0, b.x0))
        else:
            # 版面复杂：按 y 分带，带内按 x 排序；原始顺序不可信，统一标记待审核
            ordered = self.banded_order(text_blocks)

        ordered = sorted(headers, key=lambda b: (b.y0, b.x0)) + ordered + sorted(footers, key=lambda b: (b.y0, b.x0))
        for pos, b in enumerate(ordered):
            b.order_index = pos
        pm.ordered_block_indices = [b.index for b in ordered]
        if pm.reading_order_status == "NEED_REVIEW":
            pm.needs_review = True
            pm.notes.append(f"layout={pm.layout_type} 阅读顺序需人工复核")

    @staticmethod
    def banded_order(blocks: list, tolerance: float = 12.0) -> list:
        if not blocks:
            return []
        remaining = sorted(blocks, key=lambda b: (b.y0, b.x0))
        bands: list[list] = []
        for b in remaining:
            placed = False
            for band in bands:
                if abs(band[-1].y0 - b.y0) <= tolerance:
                    band.append(b)
                    placed = True
                    break
            if not placed:
                bands.append([b])
        ordered = []
        for band in bands:
            ordered += sorted(band, key=lambda b: b.x0)
        return ordered

    # ---------------- 单元 ----------------

    def detect_units(self) -> None:
        assert self.doc is not None
        toc = self.doc.get_toc()
        entries = []
        for _lvl, title, page in toc:
            unit_id = self.toc_to_unit_id(title)
            if unit_id:
                entries.append((unit_id, title, page))
        entries.sort(key=lambda e: e[2])

        for i, (unit_id, toc_title, start) in enumerate(entries):
            end = entries[i + 1][2] - 1 if i + 1 < len(entries) else BACK_COVER_PDF_PAGE - 1
            printed = [
                self.pages[p - 1].textbook_page
                for p in range(start, end + 1)
                if self.pages[p - 1].textbook_page is not None
            ]
            unit = UnitModel(
                unit_id=unit_id,
                toc_title=toc_title,
                title=self.detect_unit_title(unit_id, start, end),
                pdf_page_start=start,
                pdf_page_end=end,
                textbook_page_start=printed[0] if printed else None,
                textbook_page_end=printed[-1] if printed else None,
                evidence=[f"PDF书签《{toc_title}》→ p.{start}"],
            )
            self.units.append(unit)

    @staticmethod
    def toc_to_unit_id(title: str) -> Optional[str]:
        t = title.strip()
        if "总目录" in t:
            return None
        if re.search(r"starter", t, re.IGNORECASE):
            return "Starter"
        m = re.search(r"7AU(\d)", t, re.IGNORECASE)
        if m:
            return f"Unit {m.group(1)}"
        if "附录" in t:
            return "Appendix"
        return None

    def detect_unit_title(self, unit_id: str, start: int, end: int) -> str:
        """从单元起始页提取标题。

        标题在 PDF 中是“描边 + 填充”两层重复绘制，因此同一行会出现两次。
        这里按位置顺序收集大字号行，去掉相邻重复行与纯数字行后拼接。
        """
        page = self.pages[start - 1]
        lines = []
        for b in page.blocks:
            for line in b.lines:
                size = max((s.size for s in line.spans), default=0)
                text = compact(line.text)
                if size >= 28 and text:
                    lines.append((line.bbox[1], line.bbox[0], size, text))
        if not lines:
            return ""
        lines.sort()
        parts: list[str] = []
        for _y, _x, _size, text in lines:
            if re.fullmatch(r"\d{1,3}", text):
                continue
            if text.lower() in ("unit", "starter"):
                continue
            if parts and parts[-1] == text:
                continue
            parts.append(text)
        return compact(" ".join(parts))

    def unit_for_page(self, pdf_page: int) -> Optional[UnitModel]:
        for u in self.units:
            if u.pdf_page_start <= pdf_page <= u.pdf_page_end:
                return u
        return None

    # ---------------- Section ----------------

    def detect_sections(self) -> None:
        for unit in self.units:
            for pdf_page in range(unit.pdf_page_start, unit.pdf_page_end + 1):
                if pdf_page == 115:
                    continue  # 附录目录页，列出的是目录而非真实 section 起点
                page = self.pages[pdf_page - 1]
                for b in page.blocks:
                    title = match_section_title(b.text)
                    if not title:
                        continue
                    if b.role not in ("section_title", "heading"):
                        continue
                    already = any(
                        s.title == title and s.unit_id == unit.unit_id for s in self.sections
                    )
                    if already:
                        break
                    self.sections.append(
                        SectionModel(
                            unit_id=unit.unit_id,
                            title=title,
                            pdf_page_start=pdf_page,
                            textbook_page_start=page.textbook_page,
                            bbox=b.bbox,
                            evidence=f"p.{pdf_page} 字号{b.max_size} 字体{','.join(f.split('+')[-1] for f in b.fonts[:2])}",
                        )
                    )
                    unit.sections.append(title)
                    break

    # ---------------- Activity ----------------

    def detect_activities(self) -> None:
        for unit in self.units:
            if unit.unit_id == "Appendix":
                # 附录是词汇表/语言注释等参考资料，不是教学活动区
                continue
            scope_cluster_last: dict[tuple, int] = {}
            for pdf_page in range(unit.pdf_page_start, unit.pdf_page_end + 1):
                page = self.pages[pdf_page - 1]
                section_title = self.section_for_page(unit.unit_id, pdf_page)
                if section_title in ("Words and expressions", "Reflection"):
                    # Words and expressions 是词汇表；Reflection 是自我评价清单，
                    # 其中的编号不是教学活动编号，避免误报
                    continue
                candidates = self.find_activity_candidates(page)
                paragraph_group = self.detect_paragraph_numbering(page, candidates)
                if paragraph_group:
                    # 只删除“属于该段落编号组的候选对象”，不能按编号值删除，
                    # 否则同页同号的真实 Activity（页边黑体数字）会被连带删除。
                    rescued = {id(c) for c in paragraph_group if is_task_instruction(c["instruction"])}
                    removed = {id(c) for c in paragraph_group if id(c) not in rescued}
                    numbers = sorted(c["number"] for c in paragraph_group)
                    page.notes.append(
                        f"检测到阅读段落编号 {numbers}，其中 {len(paragraph_group) - len(removed)} 个为任务指令并保留"
                    )
                    for c in paragraph_group:
                        if id(c) in removed:
                            page.activity_rejections.append(
                                {
                                    "number": c["number"],
                                    "pdf_page": pdf_page,
                                    "bbox": c["bbox"],
                                    "reason": "paragraph_numbering",
                                    "text": c["instruction"][:60],
                                }
                            )
                    candidates = [c for c in candidates if id(c) not in removed]

                candidates.sort(key=lambda c: (c["bbox"][1], c["bbox"][0]))
                # “Think and share” 框内的编号是小问题，不是 Activity。
                # 该框有时在右上角、有时在下方，因此用“框区域 bbox”判断，
                # 不能只用 y 坐标，否则会误删左侧页边的真实活动号。
                think_blocks = [
                    b for b in page.blocks
                    if compact(b.text).lower().startswith("think and share")
                ]
                learn_blocks = [
                    b for b in page.blocks
                    if compact(b.text).lower().startswith("learning to think for question")
                ]
                box_region = None
                if think_blocks:
                    tx0 = min(b.x0 for b in think_blocks)
                    tx1 = max(b.x1 for b in think_blocks)
                    ty0 = min(b.y0 for b in think_blocks)
                    lx0 = min((b.x0 for b in learn_blocks), default=tx0)
                    lx1 = max((b.x1 for b in learn_blocks), default=tx1)
                    ly1 = max((b.y1 for b in learn_blocks), default=ty0 + 60)
                    box_region = (min(tx0, lx0) - 12.0, ty0 - 6.0, ly1 + 80.0,
                                  max(tx1, lx1))
                # 同一栏（x0 接近）内 Activity 编号递增；倒退的编号是嵌套编号
                cluster_last: dict[int, int] = {}
                kept = []
                for cand in candidates:
                    cluster = round(cand["bbox"][0] / 6) * 6
                    scope_key = (section_title, cluster)
                    last_no = max(cluster_last.get(cluster, 0), scope_cluster_last.get(scope_key, 0))
                    drop_reason = None
                    if (
                        box_region is not None
                        and cand["bbox"][0] >= box_region[0]
                        and box_region[1] <= cand["bbox"][1] <= box_region[2]
                    ):
                        drop_reason = "inside_think_and_share_box"
                    elif cand["number"] <= last_no:
                        drop_reason = "nested_or_out_of_order"
                    if drop_reason:
                        page.notes.append(
                            f"忽略疑似子问题/嵌套编号 {cand['number']} @y={cand['bbox'][1]:.0f} ({drop_reason})"
                        )
                        page.activity_rejections.append(
                            {
                                "number": cand["number"],
                                "pdf_page": pdf_page,
                                "bbox": cand["bbox"],
                                "reason": drop_reason,
                                "text": cand["instruction"][:60],
                            }
                        )
                        continue
                    kept.append(cand)
                    cluster_last[cluster] = cand["number"]
                    scope_cluster_last[scope_key] = cand["number"]
                candidates = kept
                for i, cand in enumerate(candidates):
                    next_y = candidates[i + 1]["bbox"][1] if i + 1 < len(candidates) else page.height
                    notes = []
                    status = "OK"
                    if not cand["instruction"]:
                        status = "NEED_REVIEW"
                        notes.append("未找到 Activity 指令文本")
                    region_blocks = [
                        b for b in page.blocks
                        if b.role not in ("header", "footer")
                        and b.y0 >= cand["bbox"][1] - 2
                        and b.y1 <= next_y + 2
                    ]
                    nested = [b for b in region_blocks if is_sidebar_text(b.text)]
                    sidebar_relation = ""
                    if nested:
                        instr_bbox = cand.get("instr_bbox")
                        col_x1 = instr_bbox[2] if instr_bbox else page.width
                        separate = all(b.x0 >= col_x1 + 8 for b in nested)
                        if separate:
                            # 侧栏与 Activity 正文列在水平方向不相交 → 属独立区域，
                            # 不计入 Activity 主体，但仍保留 bbox 证据
                            sidebar_relation = "separate_region"
                            notes.append(
                                "辅助侧栏位于独立区域，未并入 Activity："
                                f"{compact(nested[0].text)[:26]!r} bbox={nested[0].bbox}"
                            )
                        else:
                            sidebar_relation = "auxiliary_same_column"
                            status = "NEED_REVIEW"
                            notes.append(
                                "同栏辅助内容边界需人工确认："
                                f"{compact(nested[0].text)[:26]!r} bbox={nested[0].bbox}"
                            )
                    if cand["bbox"][3] >= page.height * 0.88:
                        status = "NEED_REVIEW"
                        notes.append("Activity 抵达页底，可能跨页延续")
                    activity = ActivityModel(
                        unit_id=unit.unit_id,
                        section_title=section_title,
                        number=cand["number"],
                        kind=cand["kind"],
                        pdf_page=pdf_page,
                        textbook_page=page.textbook_page,
                        bbox=cand["bbox"],
                        instruction=cand["instruction"],
                        boundary_status=status,
                        sidebar_relation=sidebar_relation,
                        notes=notes,
                    )
                    unit.activities.append(activity)
                    self.activities.append(activity)
                    if status != "OK":
                        page.needs_review = True
                        self.review_items.append(
                            {
                                "type": "activity",
                                "unit": unit.unit_id,
                                "section": section_title,
                                "activity": cand["number"],
                                "pdf_page": pdf_page,
                                "textbook_page": page.textbook_page,
                                "reason": "; ".join(notes),
                            }
                        )

    def find_activity_candidates(self, page: PageModel) -> list:
        margin_x = page.width * ACTIVITY_MARGIN_RATIO
        out = []
        for b in page.blocks:
            if b.role in ("header", "footer", "unit_number", "section_title"):
                # 特殊情况：部分页面的 Activity 1 与 Section 标题同行绘制
                # （例如 p.29 / p.77 / p.109 的 “1 Reading for writing”）
                if b.role == "section_title" and b.lines and b.lines[0].spans:
                    first = b.lines[0].spans[0]
                    m = re.fullmatch(r"\s*(\d{1,2})\s*", first.text)
                    if (
                        m
                        and ACTIVITY_SIZE_MIN <= first.size <= ACTIVITY_SIZE_MAX
                        and is_bold_font(first.font)
                    ):
                        instr, instr_bbox = self.find_instruction_below(page, b)
                        if instr:
                            out.append(
                                {
                                    "number": int(m.group(1)),
                                    "kind": "section_title_number",
                                    "bbox": b.bbox,
                                    "instruction": instr,
                                    "instr_bbox": instr_bbox,
                                }
                            )
                continue
            text = compact(b.text)
            if not text:
                continue
            if b.x0 > margin_x:
                continue

            # 形式 A：独立数字块（左页边黑体数字，如 p.24 的 5 / 6）
            if re.fullmatch(r"\d{1,2}", text):
                first_span = b.lines[0].spans[0] if b.lines and b.lines[0].spans else None
                number_size = first_span.size if first_span is not None else b.max_size
                if (
                    ACTIVITY_SIZE_MIN <= number_size <= ACTIVITY_SIZE_MAX
                    and any(is_bold_font(f) for f in b.fonts)
                ):
                    instruction, instr_bbox = self.find_instruction_block(page, b)
                    out.append(
                        {
                            "number": int(text),
                            "kind": "standalone_number",
                            "bbox": b.bbox,
                            "instruction": instruction,
                            "instr_bbox": instr_bbox,
                        }
                    )
                continue

            # 形式 B：段首数字 + 指令（数字用黑体单独 span 绘制）
            first = b.lines[0].spans[0] if b.lines and b.lines[0].spans else None
            if first is not None:
                m = re.match(r"^\s*(\d{1,2})\s*$", first.text)
                if (
                    m
                    and ACTIVITY_SIZE_MIN <= first.size <= ACTIVITY_SIZE_MAX
                    and is_bold_font(first.font)
                ):
                    rest = compact("".join(s.text for s in b.lines[0].spans[1:]) + "".join(
                        l.text for l in b.lines[1:]
                    ))
                    if is_question_list_instruction(rest):
                        page.activity_rejections.append(
                            {
                                "number": int(m.group(1)),
                                "pdf_page": page.pdf_page,
                                "bbox": b.bbox,
                                "reason": "question_list",
                                "text": rest[:60],
                            }
                        )
                        continue
                    out.append(
                        {
                            "number": int(m.group(1)),
                            "kind": "inline_bold_number",
                            "bbox": b.bbox,
                            "instruction": rest,
                            "instr_bbox": b.bbox,
                        }
                    )
                    continue

            # 形式 C：数字与指令在同一 span 内
            m = re.match(r"^(\d{1,2})[\s\u00a0]+(\S.*)$", text)
            if (
                m
                and first is not None
                and ACTIVITY_SIZE_MIN <= first.size <= ACTIVITY_SIZE_MAX
                and is_bold_font(first.font)
            ):
                if len(text) <= 120:
                    if is_question_list_instruction(m.group(2)):
                        page.activity_rejections.append(
                            {
                                "number": int(m.group(1)),
                                "pdf_page": page.pdf_page,
                                "bbox": b.bbox,
                                "reason": "question_list",
                                "text": m.group(2)[:60],
                            }
                        )
                        continue
                    out.append(
                        {
                            "number": int(m.group(1)),
                            "kind": "inline_number",
                            "bbox": b.bbox,
                            "instruction": m.group(2),
                            "instr_bbox": b.bbox,
                        }
                    )
            # 形式 D：活动号夹在指令句之后（如 p.21 “Complete the questionnaire.1”）
            prefix = ""
            for si, span in enumerate(b.lines[0].spans):
                if si + 1 >= len(b.lines[0].spans):
                    break
                if not re.fullmatch(r"\s*\d{1,2}\s*", span.text):
                    continue
                if not (ACTIVITY_SIZE_MIN <= span.size <= ACTIVITY_SIZE_MAX):
                    continue
                if not is_bold_font(span.font):
                    continue
                if si == 0:
                    continue
                prefix = compact("".join(s.text for s in b.lines[0].spans[:si]))
                if prefix and is_task_instruction(prefix):
                    number = int(span.text.strip())
                    if not any(c["number"] == number and c["bbox"] == b.bbox for c in out):
                        out.append(
                            {
                                "number": number,
                                "kind": "trailing_number",
                                "bbox": b.bbox,
                                "instruction": prefix,
                                "instr_bbox": b.bbox,
                            }
                        )
                break
        return out

    @staticmethod
    def find_instruction_below(page: PageModel, title_block: TextBlock) -> tuple:
        """取标题块正下方、指令列起点处的最近文本块，作为其 Activity 指令。"""
        best = None
        best_dy = 1e9
        for b in page.blocks:
            if b is title_block or b.role in ("header", "footer", "section_title"):
                continue
            if b.y0 < title_block.y1 - 2:
                continue
            if b.x0 < title_block.x0:
                continue
            dy = b.y0 - title_block.y1
            if dy <= 40 and dy < best_dy:
                best, best_dy = b, dy
        if best is None:
            return "", None
        return compact(best.text), best.bbox

    @staticmethod
    def detect_paragraph_numbering(page: PageModel, candidates: list) -> list:
        """阅读课文常用 1,2,3... 段落编号。

        特征：同一栏起点（x0 接近）、编号连续、整组文字量较大。
        这类编号属于课文段落，不是教材 Activity。
        返回的是“候选对象列表”，调用方按对象删除，避免误删同号的真实 Activity。
        """
        inline = [c for c in candidates if c["kind"].startswith("inline")]
        if len(inline) < PARAGRAPH_MIN_COUNT:
            return []
        groups: dict[int, list] = {}
        for c in inline:
            groups.setdefault(round(c["bbox"][0] / 2) * 2, []).append(c)
        for group in groups.values():
            if len(group) < PARAGRAPH_MIN_COUNT:
                continue
            ordered = sorted(group, key=lambda c: c["bbox"][1])
            numbers = [c["number"] for c in ordered]
            # 段落编号不一定被完整识别（个别编号与正文合并绘制），因此只要求严格递增
            if any(b <= a for a, b in zip(numbers, numbers[1:])):
                continue
            if sum(len(c["instruction"]) for c in group) < PARAGRAPH_MIN_TOTAL_CHARS:
                continue
            if max(len(c["instruction"]) for c in group) < PARAGRAPH_MIN_CHARS:
                continue
            if max(c["bbox"][2] - c["bbox"][0] for c in group) < page.width * 0.45:
                continue
            return group
        return []

    @staticmethod
    def find_instruction_block(page: PageModel, number_block: TextBlock) -> tuple:
        best = None
        best_dist = 1e9
        for b in page.blocks:
            if b is number_block or b.role in ("header", "footer"):
                continue
            if b.x0 < number_block.x1:
                continue
            dy = abs(b.y0 - number_block.y0)
            if dy > 24:
                continue
            dist = dy + (b.x0 - number_block.x1) * 0.1
            if dist < best_dist:
                best, best_dist = b, dist
        if best is None:
            return "", None
        return compact(best.text), best.bbox

    def section_for_page(self, unit_id: str, pdf_page: int) -> str:
        current = ""
        for s in self.sections:
            if s.unit_id != unit_id:
                continue
            if s.pdf_page_start <= pdf_page:
                current = s.title
            else:
                break
        return current or "UNKNOWN"

    def classify_activity_gap(self, unit: "UnitModel", section: str, number: int) -> dict:
        """对某个缺失编号做 PDF 取证，判定属于 A/B/C/D 哪一种情况。

        A：页面确实存在该编号，且文本是任务指令 → 规则漏识别
        B：该 Section 页面范围内找不到该编号的任何文本证据 → 教材中可能没有
        C：存在类似数字，但属于课文段落编号 / 小问编号 / 表格编号 → 不应识别为 Activity
        D：存在编号片段但无法可靠判断 → 保留 NEED_REVIEW
        """
        pages = [
            pg for pg in range(unit.pdf_page_start, unit.pdf_page_end + 1)
            if self.section_for_page(unit.unit_id, pg) == section
        ]
        hits = []
        for pg in pages:
            page = self.pages[pg - 1]
            for b in page.blocks:
                if b.role in ("header", "footer"):
                    continue
                text = compact(b.text)
                if not text:
                    continue
                first = b.lines[0].spans[0] if b.lines and b.lines[0].spans else None
                is_stand = bool(re.fullmatch(str(number), text))
                first_is = bool(first is not None and re.fullmatch(r"\s*%d\s*" % number, first.text))
                starts = bool(re.match(r"^%d[\s\u00a0]" % number, text))
                if is_stand or first_is or starts:
                    hits.append((pg, b))
        if not hits:
            return {
                "case": "B",
                "matches": 0,
                "evidence": f"{section} 页码范围 {pages} 内未出现编号 {number} 的文本证据",
            }
        activity_like = [
            (pg, b) for pg, b in hits
            if self.looks_like_activity_number(self.pages[pg - 1], b)
            and not is_question_list_instruction(b.text)
        ]
        task_hits = [(pg, b) for pg, b in activity_like if is_task_instruction(b.text)]
        if task_hits:
            pg, b = task_hits[0]
            first = b.lines[0].spans[0]
            return {
                "case": "A",
                "matches": len(hits),
                "evidence": (
                    f"p.{pg} 编号 span {first.size:.1f}pt/{first.font.split('+')[-1]} 且为任务指令："
                    f"{compact(b.text)[:44]!r}"
                ),
            }
        if not activity_like:
            pg, b = hits[0]
            first = b.lines[0].spans[0] if b.lines and b.lines[0].spans else None
            typo = f"{first.size:.1f}pt/{first.font.split('+')[-1]}" if first else "无首span"
            return {
                "case": "C",
                "matches": len(hits),
                "evidence": (
                    f"p.{pg} 编号为正文/段落/小问排版（{typo}，非 12pt 黑体活动号）："
                    f"{compact(b.text)[:40]!r}"
                ),
            }
        pg, b = activity_like[0]
        first = b.lines[0].spans[0]
        return {
            "case": "D",
            "matches": len(hits),
            "evidence": (
                f"p.{pg} 编号排版符合活动号（{first.size:.1f}pt/{first.font.split('+')[-1]}）"
                f"但文本不像任务指令，需人工判断：{compact(b.text)[:40]!r}"
            ),
        }

    @staticmethod
    def looks_like_activity_number(page: PageModel, block: TextBlock) -> bool:
        """教材活动号的排版特征：独立数字 span、约 12pt、黑体、位于左侧页边。"""
        first = block.lines[0].spans[0] if block.lines and block.lines[0].spans else None
        if first is None:
            return False
        if not re.fullmatch(r"\s*\d{1,2}\s*", first.text):
            return False
        return (
            ACTIVITY_SIZE_MIN <= first.size <= ACTIVITY_SIZE_MAX
            and is_bold_font(first.font)
            and block.x0 <= page.width * ACTIVITY_MARGIN_RATIO
        )

    # ---------------- 音频候选 ----------------

    def build_audio_candidates(self) -> None:
        mp3_files = sorted(p for p in SOURCE_DIR.glob("*.mp3"))
        for path in mp3_files:
            name = path.name
            parts = name.split("_")
            if len(parts) < 3:
                continue
            seq = parts[0]
            unit_token = parts[1].strip()
            unit_id = "Starter" if unit_token.lower().startswith("starter") else unit_token
            remainder = "_".join(parts[2:])

            section = "UNKNOWN"
            for candidate in (
                "Understanding ideas",
                "Developing ideas",
                "Phonetics in use",
                "Reading for writing",
                "Words and expressions",
            ):
                if candidate in remainder:
                    section = candidate
                    break

            number = None
            tail = remainder.split(section, 1)[1] if section in remainder else remainder
            m = re.match(r"^[\s_]*(\d{1,2})\b", tail)
            if m:
                number = int(m.group(1))

            self.audio_files.append(
                {
                    "file": name,
                    "sequence": seq,
                    "unit_id": unit_id,
                    "section": section,
                    "activity_number": number,
                }
            )

        for audio in self.audio_files:
            if audio["section"] == "Words and expressions":
                continue
            for act in self.activities:
                if (
                    act.unit_id == audio["unit_id"]
                    and act.section_title == audio["section"]
                    and audio["activity_number"] == act.number
                ):
                    act.audio_candidates.append(
                        {
                            "file": audio["file"],
                            "mapping_status": "CANDIDATE",
                            "basis": "文件名中的 Unit/板块/Activity 编号与页面解析结果一致，需人工确认",
                        }
                    )

    # ---------------- 质量检查 ----------------

    def run_quality_checks(self) -> None:
        all_text = "".join(p.text for p in self.pages)

        # 检查1：控制字符
        ctrl_1f = all_text.count("\x1f")
        ctrl_1d = all_text.count("\x1d")

        # 检查2：连字（面向实际 Unicode 内容）
        raw_lig = sum(p.text.count("\ufb01") + p.text.count("\ufb02") for p in self.pages)
        focus_expect = {
            120: "first lesson",
            126: "find a way",
            154: "floor",
        }
        focus_result = {}
        for pdf_page, expect in focus_expect.items():
            t = self.pages[pdf_page - 1].text
            focus_result[pdf_page] = {
                "expect": expect,
                "found": expect in t,
                "broken_rst": "rst lesson" in t,
                "broken_nd": "nd a way" in t,
                "broken_oor": "oor" in t,
            }

        # 检查3：单元完整
        unit_ids = [u.unit_id for u in self.units]
        expected_units = ["Starter"] + [f"Unit {i}" for i in range(1, 7)]
        missing_units = [u for u in expected_units if u not in unit_ids]

        # 检查4：页码映射
        mapping_stats = {"footer_confirmed": 0, "derived_only": 0, "none": 0}
        mapping_mismatch = []
        for p in self.pages:
            if p.textbook_page_evidence == "footer_confirmed":
                mapping_stats["footer_confirmed"] += 1
            elif p.textbook_page_evidence.startswith("derived_only"):
                mapping_stats["derived_only"] += 1
                mapping_mismatch.append(
                    {"pdf_page": p.pdf_page, "evidence": p.textbook_page_evidence}
                )
            else:
                mapping_stats["none"] += 1

        # 检查5：跨单元错位（其它单元标题出现在本单元页范围内）
        cross_unit = []
        title_map = {u.unit_id: u.title for u in self.units if u.title}
        for u in self.units:
            for pdf_page in range(u.pdf_page_start, u.pdf_page_end + 1):
                text = compact(self.pages[pdf_page - 1].text)
                for other_id, title in title_map.items():
                    if other_id == u.unit_id or not title:
                        continue
                    if len(title) >= 6 and title.lower() in text.lower():
                        cross_unit.append(
                            {"unit": u.unit_id, "pdf_page": pdf_page, "foreign_title": title}
                        )

        # 检查6：Activity 编号异常
        numbering_issues = []
        by_scope: dict[tuple, list] = {}
        for act in self.activities:
            by_scope.setdefault((act.unit_id, act.section_title), []).append(act)
        for (unit_id, section), acts in by_scope.items():
            nums = [a.number for a in acts]
            dup = sorted({n for n in nums if nums.count(n) > 1})
            if dup:
                numbering_issues.append(
                    {
                        "unit": unit_id,
                        "section": section,
                        "issue": "duplicate",
                        "numbers": dup,
                        "pages": sorted({a.pdf_page for a in acts if a.number in dup}),
                    }
                )
            if nums and max(nums) > 20:
                numbering_issues.append(
                    {
                        "unit": unit_id,
                        "section": section,
                        "issue": "out_of_range",
                        "numbers": [max(nums)],
                        "pages": sorted({a.pdf_page for a in acts}),
                    }
                )

        # 检查7：Section 内 Activity 编号缺口（提示完整性风险，不直接判错）
        numbering_gaps = []
        by_unit_section: dict[tuple, list] = {}
        for act in self.activities:
            by_unit_section.setdefault((act.unit_id, act.section_title), []).append(act.number)
        for (unit_id, section), nums in by_unit_section.items():
            uniq = sorted(set(nums))
            # Section 内 Activity 编号从 1 开始，因此低于最小已识别编号的前段也要检查
            start = 1 if uniq and uniq[0] > 1 else uniq[0]
            missing = [n for n in range(start, uniq[-1] + 1) if n not in uniq]
            if missing:
                unit = next((u for u in self.units if u.unit_id == unit_id), None)
                details = []
                if unit is not None:
                    for n in missing:
                        d = self.classify_activity_gap(unit, section, n)
                        d["number"] = n
                        details.append(d)
                numbering_gaps.append(
                    {
                        "unit": unit_id,
                        "section": section,
                        "found": uniq,
                        "missing": missing,
                        "details": details,
                    }
                )

        self.quality = {
            "control_chars": {"0x1f": ctrl_1f, "0x1d": ctrl_1d, "status": "PASS" if ctrl_1f == ctrl_1d == 0 else "FAIL"},
            "ligature": {"remaining_ufb01_ufb02": raw_lig, "focus_pages": focus_result,
                         "status": "PASS" if raw_lig == 0 and all(v["found"] for v in focus_result.values()) else "FAIL"},
            "units": {"found": unit_ids, "missing": missing_units,
                      "status": "PASS" if not missing_units else "FAIL"},
            "page_mapping": {"stats": mapping_stats, "mismatch": mapping_mismatch[:20],
                             "status": "PASS" if not mapping_mismatch else "REVIEW"},
            "cross_unit": {"count": len(cross_unit), "items": cross_unit[:20],
                           "status": "PASS" if not cross_unit else "REVIEW"},
            "activity_numbering": {"issues": numbering_issues[:20],
                                   "status": "PASS" if not numbering_issues else "REVIEW"},
            "activity_gaps": {"count": len(numbering_gaps), "items": numbering_gaps[:20],
                              "status": "PASS" if not numbering_gaps else "REVIEW"},
        }

    # ---------------- 主流程 ----------------

    def parse(self) -> None:
        self.load()
        self.parse_pages()
        self.detect_units()
        self.detect_sections()
        self.detect_activities()
        self.build_audio_candidates()
        self.run_quality_checks()

    # ---------------- 报告 ----------------

    def report(self, focus_pages: list[int]) -> None:
        pages = self.pages
        with_text = [p for p in pages if p.text_chars > 0]
        no_text = [p for p in pages if p.text_chars == 0]
        total_chars = sum(p.text_chars for p in pages)
        total_images = sum(len(p.image_objects) for p in pages)
        tiny_images = sum(1 for p in pages for i in p.image_objects if i.tiny_fragment)
        image_blocks = sum(len(p.image_blocks) for p in pages)

        print("=" * 78)
        print("P1-03 教材结构解析器 V0.1 —— 运行结果")
        print("=" * 78)
        print(f"PDF: {self.pdf_path.name}")
        print(f"页数: {len(pages)}")
        print()
        print("【1. 页面解析统计】")
        print(f"  总页数            : {len(pages)}")
        print(f"  有文字页          : {len(with_text)}")
        print(f"  无文字页          : {len(no_text)} {[p.pdf_page for p in no_text]}")
        print(f"  提取字符总数      : {total_chars}")
        print(f"  图片对象总数      : {total_images}（其中疑似碎片 {tiny_images}）")
        print(f"  图片 block 总数   : {image_blocks}")
        layouts: dict[str, int] = {}
        for p in pages:
            layouts[p.layout_type] = layouts.get(p.layout_type, 0) + 1
        print(f"  版面类型分布      : {layouts}")
        need_review_pages = [p.pdf_page for p in pages if p.needs_review]
        print(f"  待审核页面数      : {len(need_review_pages)}")

        print()
        print("【2. Unit 识别结果】")
        print("  %-9s %-26s %-14s %-14s %8s %9s" % ("unit", "title", "pdf_pages", "textbook_pages", "sections", "activities"))
        for u in self.units:
            print(
                "  %-9s %-26s %-14s %-14s %8d %9d"
                % (
                    u.unit_id,
                    (u.title or "-")[:26],
                    f"{u.pdf_page_start}-{u.pdf_page_end}",
                    f"{u.textbook_page_start}-{u.textbook_page_end}",
                    len(u.sections),
                    len(u.activities),
                )
            )

        print()
        print("【3. Section 识别结果】")
        section_counter: dict[str, int] = {}
        for s in self.sections:
            key = f"{s.unit_id} / {s.title}"
            section_counter[key] = section_counter.get(key, 0) + 1
        for key in sorted(section_counter):
            print(f"  {key}")

        print()
        print("【4. Activity 识别结果】")
        act_counter: dict[str, int] = {}
        for a in self.activities:
            key = f"{a.unit_id} / {a.section_title}"
            act_counter[key] = act_counter.get(key, 0) + 1
        for key in sorted(act_counter):
            print(f"  {key}: {act_counter[key]}")
        print(f"  Activity 总数: {len(self.activities)}")
        print()
        print("  Activity 明细（前 45 条）:")
        for a in self.activities[:45]:
            print(
                "    %-9s %-18s A%-3d p.%-4s 教材p.%-4s %-18s %-11s chars=%-4d %r"
                % (
                    a.unit_id,
                    a.section_title[:18],
                    a.number,
                    a.pdf_page,
                    str(a.textbook_page),
                    a.kind,
                    a.boundary_status,
                    len(a.instruction),
                    a.instruction[:38],
                )
            )
        if len(self.activities) > 45:
            print(f"    ... 其余 {len(self.activities) - 45} 条略")

        print()
        print("【5. 重点页面验证】")
        for pno in focus_pages:
            page = self.pages[pno - 1]
            ordered = [page.blocks[i] for i in page.ordered_block_indices if i < len(page.blocks)]
            print(
                "  p.%-4d 教材p.%-4s layout=%-13s order=%-11s 文字块=%-3d 图片块=%-4d 字符=%-5d"
                % (
                    page.pdf_page,
                    str(page.textbook_page),
                    page.layout_type,
                    page.reading_order_status,
                    len(page.blocks),
                    len(page.image_blocks),
                    page.text_chars,
                )
            )
            for b in ordered[:6]:
                print(f"      order#{b.order_index:02d} role={b.role:<13} y0={b.y0:6.1f} | {compact(b.text)[:44]!r}")

        print()
        print("【6. fi/fl 连字检查】")
        lig = self.quality["ligature"]
        print(f"  残留 U+FB01/U+FB02 : {lig['remaining_ufb01_ufb02']}")
        for pno, info in lig["focus_pages"].items():
            print(f"  p.{pno}: 期望 {info['expect']!r} → {'OK' if info['found'] else 'MISSING'}")
        print(f"  状态: {lig['status']}")

        print()
        print("【7. 页码映射检查】")
        pm = self.quality["page_mapping"]
        print(f"  页脚确认: {pm['stats']['footer_confirmed']}  仅推导: {pm['stats']['derived_only']}  无页码: {pm['stats']['none']}")
        if pm["mismatch"]:
            print(f"  需复核: {pm['mismatch'][:6]}")
        print(f"  状态: {pm['status']}")

        print()
        print("【8. 质量检查汇总】")
        for key in ("control_chars", "ligature", "units", "page_mapping", "cross_unit",
                    "activity_numbering", "activity_gaps"):
            print(f"  {key:<20}: {self.quality[key]['status']}")
        print(f"  跨单元标题命中: {self.quality['cross_unit']['count']}")
        print(f"  Activity 编号异常: {len(self.quality['activity_numbering']['issues'])}")
        for issue in self.quality["activity_numbering"]["issues"]:
            print(
                f"    - {issue.get('unit','?')} / {issue.get('section','?')} "
                f"{issue['issue']} {issue['numbers']} @p.{issue.get('pages')}"
            )
        print(f"  Activity 编号缺口: {self.quality['activity_gaps']['count']} 处（需人工确认完整性）")
        case_counter: dict[str, int] = {}
        for gap in self.quality["activity_gaps"]["items"]:
            print(f"    - {gap['unit']} / {gap['section']}: 已识别 {gap['found']}，缺 {gap['missing']}")
            for d in gap.get("details", []):
                case_counter[d["case"]] = case_counter.get(d["case"], 0) + 1
                print(f"        [{d['case']}] #{d['number']} {d['evidence']}")
        if case_counter:
            print(f"    缺口分级统计: {case_counter}（A=规则漏识别 B=教材无此编号 C=非活动编号 D=无法判断）")

        print()
        print("【9. 音频候选映射（CANDIDATE，未确认）】")
        matched = [a for a in self.activities if a.audio_candidates]
        print(f"  有候选的 Activity: {len(matched)} / {len(self.activities)}")
        for a in matched[:12]:
            print(f"  {a.unit_id} / {a.section_title} / Activity {a.number} (p.{a.pdf_page}) → {a.audio_candidates[0]['file'][:52]}")

        print()
        print("【10. NEED_REVIEW 列表】")
        layout_review = [p for p in pages if any(n.startswith("layout=") for n in p.notes)]
        activity_review = [a for a in self.activities if a.boundary_status != "OK"]
        print(f"  待审核页面: {len(need_review_pages)}")
        print(f"    其中版面阅读顺序待复核: {len(layout_review)} 页")
        print(f"    其中 Activity 边界待复核: {len(activity_review)} 个")
        print("  Activity 待审核明细（前 12 条）:")
        for item in self.review_items[:12]:
            print(f"  - {item['unit']} / {item['section']} / Activity {item['activity']} (p.{item['pdf_page']}) : {item['reason']}")
        if len(self.review_items) > 12:
            print(f"  ... 其余 {len(self.review_items) - 12} 条略")
        sep = [a for a in self.activities if a.sidebar_relation == "separate_region"]
        same = [a for a in self.activities if a.sidebar_relation == "auxiliary_same_column"]
        print("  侧栏关系统计:")
        print(f"    独立区域（已自动确认，不并入 Activity）: {len(sep)}")
        print(f"    同栏辅助内容（保留 NEED_REVIEW）      : {len(same)}")
        print()
        print("=" * 78)

    def to_dict(self) -> dict:
        return {
            "pdf": str(self.pdf_path),
            "page_count": len(self.pages),
            "units": [
                {
                    "unit_id": u.unit_id,
                    "title": u.title,
                    "pdf_page_start": u.pdf_page_start,
                    "pdf_page_end": u.pdf_page_end,
                    "textbook_page_start": u.textbook_page_start,
                    "textbook_page_end": u.textbook_page_end,
                    "evidence": u.evidence,
                    "sections": [asdict(s) for s in self.sections if s.unit_id == u.unit_id],
                    "activities": [asdict(a) for a in u.activities],
                }
                for u in self.units
            ],
            "quality": self.quality,
        }


def find_pdf() -> Path:
    pdfs = sorted(SOURCE_DIR.glob("*.pdf"))
    if not pdfs:
        raise FileNotFoundError(f"未在 {SOURCE_DIR} 找到 PDF")
    return pdfs[0]


def main(argv: Optional[list[str]] = None) -> int:
    # Windows 控制台默认 GBK，教材文本含 ⇢ 等字符会导致 UnicodeEncodeError
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="P1-03 教材结构解析器 V0.1")
    ap.add_argument("--json-out", default=None, help="可选：写出结构化结果 JSON（默认不写文件）")
    ap.add_argument("--focus", default="19,22,24,101,120,126,154,155", help="重点验证的 PDF 页，逗号分隔")
    args = ap.parse_args(argv)

    pdf = find_pdf()
    parser = TextbookParser(pdf)
    parser.parse()
    focus_pages = [int(x) for x in args.focus.split(",") if x.strip()]
    parser.report(focus_pages)

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(parser.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"JSON 已写出: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
