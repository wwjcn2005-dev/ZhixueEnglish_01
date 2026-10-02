#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-1-C1「教材之声」—— 官方音频目录 + 派生词音频（只读）

职责：
  * 从 contentpack v5 的 `audio_asset` / `audio_mapping` 读出官方音频，并按**教材文件名**
    归类到单元（词表音频 / 语音 / 阅读 / 听力 / 教材活动）；
  * 读取派生词音频清单（`structured/audio/derived/word_audio_manifest.json`）；
  * 把音频 id / 词条 key 解析为本地文件路径（**只允许清单与数据库里出现的值**）。

边界：
  - 只读；不写 learning.db、不写 contentpack、不改原始 MP3；
  - 派生词音频一律标注 `derived_from_official_unit_audio`，
    绝不描述为"官方独立单词音频"；
  - 不调用 AI、不联网、不做任何解码（解码只发生在离线构建脚本里）。
"""

from __future__ import annotations

import os

import json
import re
from pathlib import Path

BASE = Path(os.environ.get("ZX_ROOT") or r"D:\ZhixueEnglish")
CONTENTPACK = BASE / "structured" / "contentpack" / "v5" / "FLTRP-EN-7A-2022CUR.sqlite"
WORD_AUDIO_MANIFEST = BASE / "structured" / "audio" / "derived" / "word_audio_manifest.json"

#: 官方音频所在目录（原始教材音频，只读）
OFFICIAL_AUDIO_DIRS = (BASE / "2025年度初一外研版英语教材",)

DERIVATION_TAG = "derived_from_official_unit_audio"

WORD_LIST = "word_list"
PHONETICS = "phonetics"
READING = "reading"
LISTENING = "listening"
ACTIVITY = "activity"


def _ro(path) -> "object":
    import sqlite3
    conn = sqlite3.connect("file:%s?mode=ro" % Path(path).as_posix(), uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _short(text: str, limit: int = 28) -> str:
    text = re.sub(r"\s+", " ", (text or "")).strip()
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _filename_parts(filename: str) -> tuple:
    """教材音频文件名规则：`<序号>_<单元>_<板块>_<活动号> <活动指令>.mp3`。

    返回 (单元, 板块及之后全部文本, 活动指令)；文件名不符合规则时返回 (None, "", "")。
    说明：`Reading for writing` 会嵌套在 `Developing ideas` 之后，因此这里保留完整后缀文本。
    """
    stem = re.sub(r"\.mp3$", "", filename or "", flags=re.I)
    parts = stem.split("_")
    if len(parts) < 3:
        return None, "", ""
    unit = parts[1].strip()
    tail = "_".join(parts[2:]).strip()
    m = re.search(r"(?:^|[_ ])(\d+)\s+([A-Z].*)$", tail)
    instruction = m.group(2).strip() if m else tail
    return unit, tail, instruction


def classify(filename: str) -> str:
    """教材官方音频归类（规则只依赖教材自己的文件名，可追溯）。

    * Words and expressions 板块 → 整单元词表音频
    * Phonetics in use 板块       → 语音音频
    * Understanding ideas / Reading for writing 板块中的朗读活动 → 阅读朗读
    * Developing ideas 板块中以 Listen 开头的活动 → 听力
    * 其余 → 教材活动音频
    """
    _, tail, instruction = _filename_parts(filename)
    if "Words and expressions" in tail:
        return WORD_LIST
    if "Phonetics in use" in tail:
        return PHONETICS
    if "Understanding ideas" in tail or "Reading for writing" in tail:
        # 阅读朗读：活动指令以 Read 开头，或"先看图再读课文"（Look at … Now read …）
        if instruction.startswith("Read") or re.search(r"Now read\b", tail):
            return READING
    if "Developing ideas" in tail and instruction.startswith("Listen"):
        return LISTENING
    return ACTIVITY


def _unit_of_filename(filename: str) -> str | None:
    unit, _, _ = _filename_parts(filename)
    if not unit:
        return None
    return re.sub(r"\s+", " ", unit)


def unit_audio(unit_code: str, contentpack_path=CONTENTPACK) -> list:
    """某个单元可听的官方音频（按 词表 → 语音 → 阅读 → 听力 → 活动 排序）。

    每项：{"kind", "label", "audio_id", "url", "note"}
    """
    cp = _ro(contentpack_path)
    try:
        rows = cp.execute(
            "SELECT audio_id, filename, duration_ms FROM audio_asset ORDER BY audio_id").fetchall()
        mapping = {r["audio_id"]: r["target_id"] for r in cp.execute(
            "SELECT audio_id, target_id FROM audio_mapping WHERE target_type='activity'")}
        instructions = {}
        for r in cp.execute("SELECT activity_id, instruction FROM activity"):
            instructions[r["activity_id"]] = r["instruction"] or ""
    finally:
        cp.close()

    picked = {}
    acts = []
    for r in rows:
        code = (r["audio_id"] or "").split(":")[-1]
        fn = r["filename"] or ""
        if _unit_of_filename(fn) != unit_code:
            continue
        kind = classify(fn)
        item = {"kind": kind, "audio_id": code,
                "url": "/audio/official/%s.mp3" % code,
                "duration_ms": r["duration_ms"],
                "instruction": instructions.get(mapping.get(r["audio_id"])) or None}
        if kind == WORD_LIST:
            item["label"] = "听本单元词汇"
            item["note"] = "官方整单元词汇音频"
            picked.setdefault(WORD_LIST, item)
        elif kind == PHONETICS:
            item["label"] = "语音 · Phonetics in use"
            item["note"] = "官方语音音频"
            picked.setdefault(PHONETICS, item)
        elif kind == READING:
            item["label"] = "听课文朗读"
            item["note"] = "官方阅读音频"
            picked.setdefault(READING, item)
        elif kind == LISTENING:
            item["label"] = "听力 · " + _short(item["instruction"] or "教材听力", 22)
            item["note"] = "官方听力音频"
            picked.setdefault(LISTENING, item)
        else:
            acts.append(item)

    out = [picked[k] for k in (WORD_LIST, PHONETICS, READING, LISTENING) if k in picked]
    if not out:                        # 没有词表/语音/阅读/听力的单元（如 Starter）：列教材活动音频
        for item in acts:
            item["label"] = "教材活动 · " + _short(item["instruction"] or "听听看", 22)
            item["note"] = "官方教材活动音频"
            out.append(item)
    return out


def resolve_official_audio(code: str, contentpack_path=CONTENTPACK):
    """`/audio/official/<CODE>.mp3` → 本地文件（只认数据库里登记的 audio_id / 文件名）。"""
    code = (code or "").strip().upper()
    if not re.fullmatch(r"AU\d{1,3}", code):
        return None
    cp = _ro(contentpack_path)
    try:
        row = cp.execute("SELECT audio_id, filename FROM audio_asset").fetchall()
    finally:
        cp.close()
    target = None
    for r in row:
        if (r["audio_id"] or "").split(":")[-1].upper() == code:
            target = r["filename"]
            break
    if not target:
        return None
    name = Path(target).name
    for base in OFFICIAL_AUDIO_DIRS:
        cand = (base / name).resolve()
        if cand.is_file() and cand.parent == base.resolve():
            return cand
    return None


def word_audio_manifest(path=WORD_AUDIO_MANIFEST) -> dict:
    """清单读取（按 mtime 缓存，避免列表页重复读盘）。"""
    global _MANIFEST_CACHE
    try:
        mtime = Path(path).stat().st_mtime
    except OSError:
        return {}
    if _MANIFEST_CACHE.get("path") == str(path) and _MANIFEST_CACHE.get("mtime") == mtime:
        return _MANIFEST_CACHE["data"]
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        data = {}
    _MANIFEST_CACHE = {"path": str(path), "mtime": mtime, "data": data}
    return data


_MANIFEST_CACHE: dict = {}
_INDEX_CACHE: dict = {}


def word_audio_index(path=WORD_AUDIO_MANIFEST) -> dict:
    """{公开短键: 派生音频条目}（清单缺失时返回空表——页面自动不显示播放器）。"""
    global _INDEX_CACHE
    try:
        mtime = Path(path).stat().st_mtime
    except OSError:
        return {}
    if _INDEX_CACHE.get("path") == str(path) and _INDEX_CACHE.get("mtime") == mtime:
        return _INDEX_CACHE["data"]
    out = {}
    for unit in (word_audio_manifest(path).get("units") or {}).values():
        for item in unit.get("words") or []:
            if item.get("key"):
                out[item["key"]] = item
    _INDEX_CACHE = {"path": str(path), "mtime": mtime, "data": out}
    return out


def word_audio_url(item_id: str, key: str, path=WORD_AUDIO_MANIFEST):
    """某词条是否有派生发音音频；有则返回页面 URL，否则 None（不显示播放器）。"""
    item = word_audio_index(path).get(key)
    if not item or item.get("item_id") != item_id:
        return None
    return item.get("url")


def resolve_word_audio(key: str, path=WORD_AUDIO_MANIFEST):
    """`/audio/word/<key>.wav` → 本地派生音频文件（只认清单里的 key）。"""
    item = word_audio_index(path).get((key or "").strip().lower())
    if not item:
        return None
    rel = item.get("path") or ""
    if not rel or rel.startswith("/") or ".." in rel:
        return None
    root = Path(path).parent.resolve()
    cand = (root / rel).resolve()
    if cand.is_file() and str(cand).startswith(str(root)):
        return cand
    return None
