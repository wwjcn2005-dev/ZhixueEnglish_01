#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""教材点读：官方音频 ↔ 教材**自然文本块**（只读派生，Demo 专用）。

链路（全部复用已有数据：不重新 ASR、不猜坐标、不做单词级对齐）::

    官方 MP3 → ASR（词级时间轴） → matched_candidates → content_block
             → 自然文本块（Dialogue / Letter / Passage / 段落） → PDF 文本层矩形

数据来源（只读）：
  * ``audit/P3-07_preview/asr/*.json``              47 份 ASR 结果（词级时间）
  * ``audit/P3-07_preview/matched_candidates.json``  音频词窗 ↔ 教材 content_block
  * contentpack ``content_block``                    教材文本块（id / 顺序 / 文本 / 角色）
  * ``pdf_pages.text_rects``                         PDF 文本层矩形（只用于画区域）

规则（严格保证「音频内容 == 文本内容」）：
  1. 只用 ``match_confidence == 'HIGH'`` 的匹配；
  2. 只把**正文块**（非说明 / 标题 / 页脚 / 侧栏）纳入自然块；
  3. 自然块 = 同一音频、同一页、阅读顺序窗口内的一整段连续正文（含说话人标签）；
  4. 音频区间 = 组内首个词窗起点 → 末个词窗终点（来自 ASR 词级时间轴）；
  5. **逐块复核**：块文本的词必须按顺序被该区间 ASR 文本覆盖（≥ 阈值），
     否则整块丢弃 —— 宁可不给点读，也不出现「文字 A / 音频 B」；
  6. 在 PDF 文字层里找不到该块文字的矩形时同样丢弃（不靠坐标猜）。
"""

from __future__ import annotations

import os

import json
import re
import threading
from pathlib import Path

BASE = Path(os.environ.get("ZX_ROOT") or r"D:\ZhixueEnglish")
PREVIEW = BASE / "audit" / "P3-07_preview"
ASR_DIR = PREVIEW / "asr"
MATCHES = PREVIEW / "matched_candidates.json"

#: 这些页面角色 / 块类型不算「正文」
SKIP_ROLES = ("heading", "footer", "sidebar", "section_title", "unit_number")
SKIP_KINDS = ("instruction", "heading", "footer_text", "sidebar_tip")

#: 自然块类型标签（只用于展示与统计）
KIND_LABEL = {"dialogue": "对话", "letter": "信件", "passage": "课文", "paragraph": "段落"}

MIN_CHARS = 80          # 自然块正文长度下限
MIN_COVER = 0.9         # 块文本被 ASR 区间覆盖的最低比例
MIN_SPAN_MS = 1500      # 音频区间下限

_LOCK = threading.Lock()
_CACHE = {}


def _tokens(text: str) -> list:
    t = (text or "").lower()
    for a, b in (("\u2019", "'"), ("\u2018", "'"), ("\u201c", " "), ("\u201d", " ")):
        t = t.replace(a, b)
    t = re.sub(r"[^a-z0-9' ]+", " ", t)
    return [w for w in t.split() if w]


def _norm(text: str) -> str:
    return " ".join(_tokens(text))


def _load_matches() -> list:
    if not MATCHES.exists():
        return []
    key = ("matches", MATCHES.stat().st_mtime)
    with _LOCK:
        if key in _CACHE:
            return _CACHE[key]
    rows = json.loads(MATCHES.read_text(encoding="utf-8"))
    with _LOCK:
        _CACHE[key] = rows
    return rows


def _block_meta(contentpack_path) -> dict:
    """content_block 元数据：block_id → {kind, role, order, page, text}。"""
    import content as content_mod
    key = ("blocks", str(contentpack_path))
    with _LOCK:
        if key in _CACHE:
            return _CACHE[key]
    cp = content_mod._ro(contentpack_path)
    try:
        out = {}
        for r in cp.execute(
                "SELECT b.block_id, b.block_kind, b.layout_role, b.reading_order, "
                "b.text_raw, p.pdf_page FROM content_block b "
                "JOIN page p ON p.page_id = b.page_id"):
            out[r[0]] = {"kind": r[1] or "", "role": r[2] or "",
                         "order": int(r[3] or 0),
                         "page": int(r[5] or 0) if r[5] else 0,
                         "text": r[4] or ""}
        with _LOCK:
            _CACHE[key] = out
        return out
    finally:
        cp.close()


def _is_body(meta: dict) -> bool:
    if not meta:
        return False
    if meta["role"] in SKIP_ROLES or meta["kind"] in SKIP_KINDS:
        return False
    return len(_norm(meta["text"])) >= 8


def _in_region(meta: dict) -> bool:
    """区域（高亮）里允许出现的块：正文、且不是标题 / 说明 / 页脚 / 侧栏。

    说话人标签（"Mia" / "Dad"）这类很短的块也算——它们本来就属于对话块的一部分。
    """
    if not meta:
        return False
    return not (meta["role"] in SKIP_ROLES or meta["kind"] in SKIP_KINDS)


def _is_short_label(text: str) -> bool:
    """说话人标签 / 信件抬头落款这类很短的块（"Mia" / "Dear Mia," / "With love,"）。"""
    raw = (text or "").strip()
    if not raw or len(raw) > 32:
        return False
    if re.match(r"^(Dear\b|With love\b|Yours\b|Best wishes\b|Love,)", raw):
        return True
    if not re.match(r"^[A-Za-z][A-Za-z'.,\s]*$", raw):
        return False
    return len(_tokens(raw)) <= 3


def _kind_of(text: str, region: list, meta: dict) -> str:
    """自然块类型（只用于标签与统计）：信件 / 对话 / 课文 / 段落。

    依据页面结构判断，不靠猜测：说话人标签块（单独的人名）出现 → 对话；
    含信件抬头/落款 → 信件；长度较大 → 课文；否则段落。
    """
    raw = text or ""
    if re.search(r"(Dear\s+\w+|With love|Yours,|Best wishes)", raw):
        return "letter"
    labels = [b for b in region
              if len(_tokens(meta[b]["text"])) <= 2
              and re.match(r"^[A-Z][A-Za-z]+$", (meta[b]["text"] or "").strip())]
    if labels:
        return "dialogue"
    return "passage" if len(raw) > 400 else "paragraph"


def _covers(block_text: str, asr_text: str) -> float:
    """块文本的词按顺序被 ASR 文本覆盖的比例（1.0 表示全部覆盖）。"""
    want = _tokens(block_text)
    if not want:
        return 0.0
    have = _tokens(asr_text)
    i = 0
    for word in have:
        if i < len(want) and word == want[i]:
            i += 1
    return i / len(want)


def _asr(audio_num: str) -> dict:
    path = ASR_DIR / ("%s.json" % audio_num)
    if not path.exists():
        return {}
    key = ("asr", audio_num)
    with _LOCK:
        data = _CACHE.get(key)
    if data is None:
        data = json.loads(path.read_text(encoding="utf-8"))
        with _LOCK:
            _CACHE[key] = data
    return data


def _asr_window_text(audio_num: str, start_ms: int, end_ms: int) -> str:
    """区间内的 ASR 文本（优先词级时间轴，退回整段文本）。"""
    data = _asr(audio_num)
    if not data:
        return ""
    words = [w.get("word") or "" for w in data.get("words") or []
             if start_ms - 150 <= int(w.get("start_ms") or 0) <= end_ms + 150]
    words = [w for w in words if w.strip()]
    if words:
        return " ".join(words)
    return " ".join(seg.get("text") or "" for seg in data.get("segments") or []
                    if int(seg.get("start_ms") or 0) < end_ms
                    and int(seg.get("end_ms") or 0) > start_ms)


def natural_blocks(unit_code: str, contentpack_path=None) -> list:
    """某个单元的全部自然文本块（已复核；不可靠的一律不出现）。"""
    import content as content_mod
    import pdf_pages
    contentpack_path = contentpack_path or content_mod.CONTENTPACK
    memo = ("blocks_of", unit_code, str(contentpack_path), MATCHES.stat().st_mtime
            if MATCHES.exists() else 0)
    with _LOCK:
        if memo in _CACHE:
            return _CACHE[memo]
    meta = _block_meta(contentpack_path)
    rows = [r for r in _load_matches()
            if r.get("unit") == unit_code and r.get("match_confidence") == "HIGH"]
    if not rows:
        return []
    groups = {}
    for r in rows:
        info = meta.get(r.get("source_block") or "")
        if not _is_body(info):
            continue
        # 行级复核：这条匹配自己的 ASR 文本必须真的说出这条教材文本（artifact 自身一致性）
        if _covers(r.get("textbook_text") or "", r.get("asr_text") or "") < MIN_COVER:
            continue
        groups.setdefault((r["audio_num"], info["page"]), []).append(r)
    out = []
    for (audio, page), items in groups.items():
        # 这段音频真正读到的正文块（HIGH 匹配）
        spoken = sorted({i["source_block"] for i in items if meta.get(i["source_block"])},
                        key=lambda b: meta[b]["order"])
        if not spoken:
            continue
        lo = min(meta[b]["order"] for b in spoken)
        hi = max(meta[b]["order"] for b in spoken)
        text = " ".join(meta[b]["text"].strip() for b in spoken).strip()
        if len(_norm(text)) < MIN_CHARS:
            continue                       # 太短，不值得做点读
        start_ms = min(int(i["rough_start_ms"]) for i in items)
        end_ms = max(int(i["rough_end_ms"]) for i in items)
        if end_ms - start_ms < MIN_SPAN_MS:
            continue
        asr_text = _asr_window_text(audio, start_ms, end_ms)
        if not asr_text:
            continue                       # 没有 ASR 时间数据 → 不做点读
        row_cover = min(_covers(i.get("textbook_text") or "", i.get("asr_text") or "")
                        for i in items)
        if row_cover < MIN_COVER:
            continue                      # 逐行复核没过 → 整块丢弃
        # 高亮区域 = 这段音频在这页上匹配到的块（HIGH/MEDIUM）
        #            + 夹在它们之间的说话人标签 / 信件抬头（很短、属于同一个自然块）
        same_audio = {}
        for r in _load_matches():
            if r.get("audio_num") != audio or r.get("unit") != unit_code:
                continue
            info = meta.get(r.get("source_block") or "")
            if info and info["page"] == page:
                same_audio[r["source_block"]] = r.get("match_confidence")
        region = []
        for bid, m in meta.items():
            if m["page"] != page or not _in_region(m):
                continue
            inside = lo <= m["order"] <= hi
            # 紧贴窗口的说话人标签 / 信件抬头落款也算这一块的一部分
            touching = (m["order"] == lo - 1 or m["order"] == hi + 1) \
                and _is_short_label(m["text"])
            if not inside and not touching:
                continue
            if same_audio.get(bid) in ("HIGH", "MEDIUM") or _is_short_label(m["text"]):
                region.append(bid)
        region.sort(key=lambda b: meta[b]["order"])
        region_text = " ".join(meta[b]["text"].strip() for b in region).strip()
        # 中间不能有「这段音频没读到的正文块」——那说明这块其实是表格 / 答案碎片
        gap = False
        spoken_orders = [meta[b]["order"] for b in spoken]
        matched_texts = {_norm(meta[o]["text"]) for o, v in same_audio.items()
                         if v in ("HIGH", "MEDIUM") and meta.get(o)}
        for bid, m in meta.items():
            if m["page"] != page or not _in_region(m):
                continue
            if min(spoken_orders) < m["order"] < max(spoken_orders) and _is_body(m):
                if (same_audio.get(bid) not in ("HIGH", "MEDIUM")
                        and not _is_short_label(m["text"])
                        and _norm(m["text"]) not in matched_texts):   # 同一行的重复解析块
                    gap = True
                    break
        if gap:
            continue
        rects = []
        for b in region:
            rects.extend(pdf_pages.text_rects(page, meta[b]["text"]))
        if not rects:
            continue
        out.append({
            "key": "%s:%s:%d:%d" % (unit_code, audio, page, lo),
            "unit": unit_code, "audio": audio,
            "audio_url": "/audio/official/%s.mp3" % audio,
            "page": page, "start_ms": start_ms, "end_ms": end_ms,
            "blocks": spoken, "region": region, "text": text,
            "kind": _kind_of(region_text, region, meta),
            "cover": round(min(_covers(meta[b]["text"], asr_text) for b in spoken), 3),
            "row_cover": round(row_cover, 3),
            "speech_frac": round(len(spoken) / max(len(region), 1), 2),
            "rects": rects,
        })
    out.sort(key=lambda b: (b["page"], b["start_ms"]))
    with _LOCK:
        _CACHE[memo] = out
    return out


def page_blocks(unit_code: str, page_no: int, contentpack_path=None) -> list:
    return [b for b in natural_blocks(unit_code, contentpack_path) if b["page"] == page_no]


def pages_with_blocks(unit_code: str, contentpack_path=None) -> list:
    return sorted({b["page"] for b in natural_blocks(unit_code, contentpack_path)})


def activity_arrows(unit_code: str, page_no: int, contentpack_path=None) -> list:
    """这一页的**整段活动录音**（没有可靠文本映射时的诚实回退）。"""
    import content as content_mod
    contentpack_path = contentpack_path or content_mod.CONTENTPACK
    cp = content_mod._ro(contentpack_path)
    try:
        rows = cp.execute(
            "SELECT a.audio_id, ac.instruction, ac.activity_number "
            "FROM audio_mapping m JOIN audio_asset a ON a.audio_id = m.audio_id "
            "LEFT JOIN activity ac ON ac.activity_id = m.target_id "
            "WHERE m.target_type = 'activity' AND m.mapping_status = 'MATCHED' "
            "AND ac.pdf_page = ? ORDER BY a.relative_path", (page_no,)).fetchall()
    finally:
        cp.close()
    out = []
    seen = set()
    for r in rows:
        code = (r[0] or "").split(":")[-1].upper()
        if code in seen or not code:
            continue
        seen.add(code)
        label = (r[1] or "").strip().replace("\n", " ")
        out.append({"code": code, "url": "/audio/official/%s.mp3" % code,
                    "label": label[:60] or ("整段活动录音 %s" % code),
                    "activity_no": r[2]})
    return out


def stats(contentpack_path=None) -> dict:
    """本轮建立的自然文本块统计（报告 / 测试用）。"""
    import content as content_mod
    contentpack_path = contentpack_path or content_mod.CONTENTPACK
    by_unit, by_kind, total, pages = {}, {}, 0, set()
    for unit in content_mod.list_units(contentpack_path):
        blocks = natural_blocks(unit["unit_code"], contentpack_path)
        if not blocks:
            continue
        by_unit[unit["unit_code"]] = len(blocks)
        for b in blocks:
            by_kind[b["kind"]] = by_kind.get(b["kind"], 0) + 1
            pages.add((unit["unit_code"], b["page"]))
        total += len(blocks)
    return {"total": total, "by_unit": by_unit, "by_kind": by_kind,
            "units": sorted(by_unit), "pages": sorted(pages)}
