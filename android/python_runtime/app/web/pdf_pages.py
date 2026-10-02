#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""教材原书页面渲染 + 文字矩形（**全只读**）

职责边界（第五轮起）：
  * 页面图片由**现有教材 PDF 现场渲染**（PyMuPDF，项目已安装，无需新依赖）；
    PDF 本身只读，不修改、不重写、不导出新的教材文件。
  * ``text_rects()``：把一段**教材文字**换算成页面矩形（只用于画区域）。
    只有页面文字层里能找到逐词一致的区域时才返回矩形，否则返回空列表。
    **它不做音频映射** —— 音频与文本的对应关系一律来自
    ``reading_map``（官方 MP3 → ASR → matched_candidates → content_block）。
  * 不含 word-level 对齐、不含逐词热点、不含逐词时间轴。
  * 只缓存已渲染过的页面（内存 LRU），不写 learning.db、不调用 AI。
"""

from __future__ import annotations

import os

import glob
import re
import threading
from pathlib import Path

BASE = Path(os.environ.get("ZX_ROOT") or r"D:\ZhixueEnglish")

#: 教材 PDF（只读；文件名含中文，用 glob 定位，避免硬编码转义问题）
_PDF_CANDIDATES = (r"2025年度初一外研版英语教材\*.pdf",)

PAGE_DPI = 130
PAGE_QUALITY = 78
MAX_CACHED_PAGES = 24

_LOCK = threading.Lock()
_DOC = None
_PAGE_CACHE = {}
_WORDS_CACHE = {}
MAX_CACHED_WORDS = 24


def pdf_path():
    for pattern in _PDF_CANDIDATES:
        hits = sorted(glob.glob(str(BASE / pattern)))
        if hits:
            return Path(hits[0])
    return None


def _doc():
    """打开教材 PDF（只读、进程内复用）。找不到 PDF 时返回 None，由页面自然降级。"""
    global _DOC
    if _DOC is not None:
        return _DOC
    path = pdf_path()
    if path is None:
        return None
    import pymupdf                                   # 项目已有依赖；不新装任何包
    with _LOCK:
        if _DOC is None:
            _DOC = pymupdf.open(str(path))
    return _DOC


def page_count() -> int:
    doc = _doc()
    return doc.page_count if doc else 0


def _page(pdf_page: int):
    doc = _doc()
    if doc is None or not (1 <= pdf_page <= doc.page_count):
        return None
    return doc[pdf_page - 1]


def page_size(pdf_page: int):
    """页面原始尺寸（PDF point），用于把热点坐标换算成百分比。"""
    page = _page(pdf_page)
    if page is None:
        return None
    return page.rect.width, page.rect.height


def render_jpeg(pdf_page: int, dpi: int = PAGE_DPI, quality: int = PAGE_QUALITY):
    """把教材原书页面渲染成 JPEG（内存缓存；只读派生，不触碰原始 PDF）。"""
    page = _page(pdf_page)
    if page is None:
        return None
    key = (pdf_page, dpi, quality)
    cached = _PAGE_CACHE.get(key)
    if cached is not None:
        return cached
    pix = page.get_pixmap(dpi=dpi)
    data = pix.tobytes("jpeg", jpg_quality=quality)
    if len(_PAGE_CACHE) >= MAX_CACHED_PAGES:
        _PAGE_CACHE.pop(next(iter(_PAGE_CACHE)))
    _PAGE_CACHE[key] = data
    return data


def _tokens(text: str) -> list:
    text = (text or "").lower()
    text = (text.replace("\u2019", "'").replace("\u2018", "'")
                .replace("\u201c", '"').replace("\u201d", '"'))
    return [t for t in re.sub(r"[^a-z0-9']+", " ", text).split() if t]


def _lines(pdf_page: int):
    """页面文本层的行（只读、进程内缓存）：[(text, rect)]，按阅读顺序。"""
    page = _page(pdf_page)
    if page is None:
        return []
    cached = _WORDS_CACHE.get(pdf_page)
    if cached is not None:
        return cached
    lines = []
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            text = "".join(span.get("text") or "" for span in line.get("spans", []))
            if text.strip():
                bbox = line.get("bbox")
                lines.append((text, (round(bbox[0], 1), round(bbox[1], 1),
                                     round(bbox[2], 1), round(bbox[3], 1))))
    if len(_WORDS_CACHE) >= MAX_CACHED_WORDS:
        _WORDS_CACHE.pop(next(iter(_WORDS_CACHE)))
    _WORDS_CACHE[pdf_page] = lines
    return lines


def _blocks(pdf_page: int):
    page = _page(pdf_page)
    if page is None:
        return []
    return [((b[4] or ""), (round(b[0], 1), round(b[1], 1),
                            round(b[2], 1), round(b[3], 1)))
            for b in page.get_text("blocks") if (b[4] or "").strip()]


def _words(pdf_page: int):
    """页面文本层的词框（只读；仅用于把**整句**拼成一个矩形区域，不做逐词热点）。"""
    page = _page(pdf_page)
    if page is None:
        return []
    rows = []
    for w in page.get_text("words"):
        rows.append({"rect": (round(w[0], 1), round(w[1], 1), round(w[2], 1), round(w[3], 1)),
                     "norm": _tokens(w[4])[0] if _tokens(w[4]) else "",
                     "block": w[5], "line": w[6], "no": w[7]})
    rows.sort(key=lambda r: (r["block"], r["line"], r["no"]))
    return rows


def text_rects(pdf_page: int, text: str) -> list:
    """教材文字 → 页面矩形（**只用于画区域**，不参与任何音频映射）。

    只有页面文字层里能找到**与 text 逐词一致**的区域时才返回矩形，否则返回空列表。
    返回 [(x0, y0, x1, y1), ...]：跨行的文字会得到每行一个矩形，
    由调用方把这些矩形当作**同一个自然文本块**渲染（一个块，多个矩形）。
    """
    want = _tokens(text)
    if not want or _page(pdf_page) is None:
        return []
    target = " ".join(want)
    for block_text, rect in _blocks(pdf_page):
        if " ".join(_tokens(block_text)) == target:
            return [rect]
    for line_text, rect in _lines(pdf_page):
        if " ".join(_tokens(line_text)) == target:
            return [rect]
    words = _words(pdf_page)
    for start in range(len(words)):
        if words[start]["norm"] != want[0]:
            continue
        if start + len(want) > len(words):
            break
        run = words[start:start + len(want)]
        if [w["norm"] for w in run] != want:
            continue
        if len({w["block"] for w in run}) != 1:
            continue                     # 必须落在同一个教材文本块里
        by_line = {}
        for w in run:
            by_line.setdefault((w["block"], w["line"]), []).append(w["rect"])
        return [(min(r[0] for r in group), min(r[1] for r in group),
                 max(r[2] for r in group), max(r[3] for r in group))
                for _key, group in sorted(by_line.items())]
    return []
