#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""教材音频资源层 · 只读查询服务（audio_resource_v1）

资源层文件：`structured/audio/resources/audio_resource_v1.json`
（由 `builder/build_audio_resource_layer_v01.py` 确定性生成；AI 调用 = 0）

本模块只读：
  * 不写任何文件、不改 contentpack / learning.db / demo / android；
  * 对外提供"Unit → 可用官方音频 → 教材文本 → 时间段 → 学习能力 → 题目生成准备状态"的查询链；
  * 供后续本地教材题库建设直接调用（题库生成阶段按此取资源）。
"""

from __future__ import annotations

import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
LAYER_PATH = BASE / "structured" / "audio" / "resources" / "audio_resource_v1.json"

VERIFIED = "VERIFIED"
PARTIAL = "PARTIAL"
NEED_MANUAL_CONFIRMATION = "NEED_MANUAL_CONFIRMATION"
NO_TEXT_MATCH = "NO_TEXT_MATCH"
STATUSES = (VERIFIED, PARTIAL, NEED_MANUAL_CONFIRMATION, NO_TEXT_MATCH)

READY_DETERMINISTIC = "READY_DETERMINISTIC"
READY_WITH_PROGRAM_PROCESSING = "READY_WITH_PROGRAM_PROCESSING"
NEEDS_TEXT_RELATION = "NEEDS_TEXT_RELATION"

_CACHE: dict = {}


def load(path=None) -> dict:
    """读取资源层（进程内缓存；文件缺失返回空结构，不抛异常）。"""
    p = Path(path or LAYER_PATH)
    key = str(p)
    if key not in _CACHE:
        try:
            _CACHE[key] = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _CACHE[key] = {"layer": "audio_resource_v1", "version": None, "audio_resources": []}
    return _CACHE[key]


def list_resources(path=None) -> list:
    return list(load(path).get("audio_resources") or [])


def get_by_audio(audio_code: str, path=None) -> dict:
    """按 AUxx 取资源；找不到返回 {}。"""
    code = (audio_code or "").strip().upper()
    for r in list_resources(path):
        if (r.get("audio_code") or "").upper() == code:
            return r
    return {}


def resources_for_unit(unit_code: str, path=None, include: tuple = STATUSES) -> list:
    """某 Unit 的官方音频资源（默认返回全部状态，可按需过滤）。"""
    want = (unit_code or "").strip().lower()
    return [r for r in list_resources(path)
            if (r.get("unit_code") or "").strip().lower() == want
            and r.get("alignment_status") in include]


def segments(audio_code: str, path=None, status: str = None, timing_kind: str = None) -> list:
    """该音频的对齐段（可选按状态/时间精度过滤）。"""
    out = []
    for s in (get_by_audio(audio_code, path).get("segments") or []):
        if status and s.get("status") != status:
            continue
        if timing_kind and s.get("timing_kind") != timing_kind:
            continue
        out.append(s)
    return out


def text_resources(audio_code: str, path=None, verified_only: bool = True) -> list:
    """该音频对应的**正式教材文本 ID**（content_block / learning_item）。"""
    out, seen = [], set()
    for s in (get_by_audio(audio_code, path).get("segments") or []):
        if verified_only and s.get("status") != VERIFIED:
            continue
        tid = s.get("text_resource_id")
        if not tid or tid in seen:
            continue
        seen.add(tid)
        out.append({"text_resource_kind": s.get("text_resource_kind"), "text_resource_id": tid,
                    "start_ms": s.get("start_ms"), "end_ms": s.get("end_ms"),
                    "timing_kind": s.get("timing_kind")})
    return out


def capabilities(audio_code: str, path=None) -> list:
    return [c.get("name") for c in (get_by_audio(audio_code, path).get("capabilities") or [])]


def readiness(audio_code: str, path=None) -> str:
    return get_by_audio(audio_code, path).get("readiness") or ""


def generation_ready(unit_code: str, path=None) -> dict:
    """题库生成取资源入口：按 Unit 分组给出三类可用资源。"""
    rows = resources_for_unit(unit_code, path)
    out = {READY_DETERMINISTIC: [], READY_WITH_PROGRAM_PROCESSING: [], NEEDS_TEXT_RELATION: []}
    for r in rows:
        out.setdefault(r.get("readiness") or NEEDS_TEXT_RELATION, []).append({
            "audio_code": r.get("audio_code"), "activity_id": r.get("activity_id"),
            "section_key": r.get("section_key"), "resource_type": r.get("resource_type"),
            "capabilities": capabilities(r["audio_code"], path),
            "verified_text_resources": len(text_resources(r["audio_code"], path)),
            "alignment_status": r.get("alignment_status")})
    return out


def summary(path=None) -> dict:
    """54/54 完整性与状态汇总。"""
    rows = list_resources(path)
    stat = {s: 0 for s in STATUSES}
    ready = {READY_DETERMINISTIC: 0, READY_WITH_PROGRAM_PROCESSING: 0, NEEDS_TEXT_RELATION: 0}
    for r in rows:
        stat[r.get("alignment_status")] = stat.get(r.get("alignment_status"), 0) + 1
        ready[r.get("readiness")] = ready.get(r.get("readiness"), 0) + 1
    return {"layer": load(path).get("layer"), "version": load(path).get("version"),
            "audio_assets": len(rows), "alignment_status": stat, "readiness": ready,
            "segments": sum(len(r.get("segments") or []) for r in rows),
            "used_by_app_direct": sum(1 for r in rows if (r.get("used_by_app") or {}).get("direct")),
            "used_by_app_indirect": sum(1 for r in rows if (r.get("used_by_app") or {}).get("indirect"))}


def integrity_check(path=None) -> dict:
    """只读自检：身份完整、状态合法、VERIFIED 段必须有正式文本 ID + 时间；不改数据。"""
    problems = []
    rows = list_resources(path)
    if len(rows) != 54:
        problems.append("资源数不是 54：%d" % len(rows))
    if len({r.get("audio_code") for r in rows}) != len(rows):
        problems.append("audio_code 有重复")
    for r in rows:
        code = r.get("audio_code")
        for field in ("resource_id", "audio_asset_id", "filename", "alignment_status", "readiness"):
            if not r.get(field):
                problems.append("%s 缺少 %s" % (code, field))
        if r.get("alignment_status") not in STATUSES:
            problems.append("%s 状态非法：%s" % (code, r.get("alignment_status")))
        for s in r.get("segments") or []:
            if s.get("status") == VERIFIED:
                if not s.get("text_resource_id"):
                    problems.append("%s 有 VERIFIED 段但无正式文本 ID" % code)
                if s.get("start_ms") is None or s.get("end_ms") is None:
                    problems.append("%s 有 VERIFIED 段但无时间范围" % code)
                if not s.get("alignment_evidence"):
                    problems.append("%s 有 VERIFIED 段但无对齐证据" % code)
    return {"ok": not problems, "problems": problems, "summary": summary(path)}


def sources_intact(path=None) -> bool:
    """确认资源层记录的上游文件仍与生成时一致（只读比对 sha256）。"""
    import hashlib
    for item in load(path).get("sources") or []:
        p = BASE / item["path"]
        try:
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
        except OSError:
            return False
        if digest != item.get("sha256"):
            return False
    return True
