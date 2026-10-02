#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""J1 · 题目 → 教材证据包 的只读解析服务。

**职责**：把题库中的一道题（`questionbank.question`）关联到 `textbook_evidence_map_v1.json`
里的**一个**证据包，并给出**证据粒度**（`activity` / `section` / `None`）。

为什么需要它（实测事实，2026-09-29）：
  * `textbook_evidence_map_v1.json` 的 `question_id`（337 个）与
    `questionbank.db` 的 `question_id`（1831 个）**交集为 0** —— 两套数据没有主键关联；
  * 但存在**可用的间接关联键**：`questionbank.question.activity_id` 与
    `contentpack.activity.activity_id` 同源；证据包的 `scope.{unit, section, activity_no}`
    经 `contentpack` 可解析为同一个 `activity_id`；
  * 实测：有 `activity_id` 的 241 道 `ai_eval` 题 **137 道 100% 命中**证据包；
    剩余 104 道（`activity_id` 为空）**无活动线索**，只能降级到 Section 级。

粒度语义（决定 AI 判“答题要求”的可靠度）：
  * `activity` —— 活动级：证据包含**该活动的原题指令**（`textbook_reference.instruction`）；
  * `section`  —— Section 级降级：同一 Section 的**代表证据**，**不含 per-activity 指令**，证据更弱；
  * `None`     —— 无证据（Appendix / Unit 级词表 / 该 Section 无证据包）——**如实返回，不伪造**。

⚠️ 题型必须用 `prompt_json.question_type`（细粒度 = match/fill/choice/…），
**不能**用 `questionbank.question.question_type`（粗粒度，ai_eval 题一律 `textbook_native`）。
实测教训（2026-09-29）：用粗粒度口径会让 241/241 全部误判为“类型不匹配”。

严格只读：本模块不写任何数据库、不新增表 / 字段、不修改任何正式资产。
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]

#: 证据包（P2-4 产物，正式资产，只读）
DEFAULT_EVIDENCE_MAP = BASE / "structured" / "ai" / "textbook_evidence_map_v1.json"
#: 正式内容库（只读）
DEFAULT_CONTENTPACK = BASE / "structured" / "contentpack" / "v5" / "FLTRP-EN-7A-2022CUR.sqlite"

GRANULARITY_ACTIVITY = "activity"
GRANULARITY_SECTION = "section"

#: Appendix 不是教学 Unit（与 study_call_service.APPENDIX_UNIT 同义）
APPENDIX_UNIT = "Appendix"

#: 证据粒度所依赖的文本类字段（与 Android 侧 AiContract.EVIDENCE_FIELDS 同源）
EVIDENCE_TEXT_FIELDS = (
    "related_text", "related_vocabulary", "related_grammar", "related_listening",
)

#: 证据包 text 被 P2-4 生成时截断到 400 字符（实测 9/41 个活动可见）
EVIDENCE_TEXT_TRUNCATE = 400

#: 进程内缓存（按文件 mtime 失效）
_CP_CACHE: dict = {}
_MAP_CACHE: dict = {}


# --------------------------------------------------------------------------- 工具

def _norm(text) -> str:
    return re.sub(r"[\s\u00a0]+", " ", str(text or "").strip().lower())


def _prefix_len(a, b) -> int:
    """两个字符串的公共前缀长度（规范化后比较）。"""
    x, y = _norm(a), _norm(b)
    n = 0
    for ca, cb in zip(x, y):
        if ca != cb:
            break
        n += 1
    return n


def _pkg_text(pkg: dict) -> str:
    return ((pkg.get("original_question") or {}).get("text")) or ""


def _pkg_type(pkg: dict) -> str:
    return _norm((pkg.get("original_question") or {}).get("question_type"))


def _scope(pkg: dict, key: str):
    return (pkg.get("scope") or {}).get(key)


def _is_non_empty(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) > 0
    return True


def count_evidence_fields(pkg: dict | None) -> int:
    """按文本类字段统计证据条数（与 Android 侧 `AiContract.countEvidence` 同口径）。

    **排除 `related_image`**：实测它在 344/360 个包里非空，若计入则条数永远 ≥1，
    `confidence_rule` 的 `<2` 分支几乎不会触发（闸门形同虚设）；且图片不是可引用的文本证据。
    """
    if not pkg:
        return 0
    return sum(1 for f in EVIDENCE_TEXT_FIELDS if _is_non_empty(pkg.get(f)))


def _log(msg: str) -> None:
    print("[evidence] %s" % msg)


# --------------------------------------------------------------------------- 索引

def _load_evidence_map(path=DEFAULT_EVIDENCE_MAP) -> list:
    """加载证据包（按 (path, mtime) 缓存）。"""
    p = Path(path)
    try:
        mtime = p.stat().st_mtime
    except OSError:
        mtime = None
    if _MAP_CACHE.get("path") == str(p) and _MAP_CACHE.get("mtime") == mtime:
        return _MAP_CACHE["data"]
    data = json.loads(p.read_text(encoding="utf-8")).get("packages") or []
    _MAP_CACHE.update({"path": str(p), "mtime": mtime, "data": data})
    return data


def _cp_index(contentpack_path=DEFAULT_CONTENTPACK) -> dict:
    """从 contentpack 建两个索引（按 (path, mtime) 缓存）：

      * `(unit_code, section_key, activity_number) → activity_id`
      * `activity_id → (unit_code, section_key)`
    """
    p = Path(contentpack_path)
    try:
        mtime = p.stat().st_mtime
    except OSError:
        mtime = None
    if _CP_CACHE.get("path") == str(p) and _CP_CACHE.get("mtime") == mtime:
        return _CP_CACHE["data"]
    conn = sqlite3.connect("file:%s?mode=ro" % p.as_posix(), uri=True)
    conn.row_factory = sqlite3.Row
    try:
        by_number, by_activity = {}, {}
        rows = conn.execute(
            "SELECT a.activity_id, a.activity_number, s.section_key, u.unit_code "
            "FROM activity a JOIN section s ON s.section_id = a.section_id "
            "JOIN unit u ON u.unit_id = s.unit_id"
        ).fetchall()
        for r in rows:
            by_number[(r["unit_code"], r["section_key"], r["activity_number"])] = r["activity_id"]
            by_activity[r["activity_id"]] = (r["unit_code"], r["section_key"])
    finally:
        conn.close()
    data = {"by_number": by_number, "by_activity": by_activity}
    _CP_CACHE.update({"path": str(p), "mtime": mtime, "data": data})
    return data


def build_package_index(packages=None, contentpack_path=DEFAULT_CONTENTPACK) -> dict:
    """证据包索引：

      * `by_activity`: activity_id → [pkg, …]
      * `by_section`:  (unit_code, section_key) → [pkg, …]
    """
    pkgs = _load_evidence_map() if packages is None else packages
    cp = _cp_index(contentpack_path)
    by_number = cp["by_number"]
    by_activity: dict = {}
    by_section: dict = {}
    for pkg in pkgs:
        unit = _scope(pkg, "unit")
        section = _scope(pkg, "section")
        if unit and section:
            by_section.setdefault((unit, section), []).append(pkg)
        aid = by_number.get((unit, section, _scope(pkg, "activity_no")))
        if aid:
            by_activity.setdefault(aid, []).append(pkg)
    return {"by_activity": by_activity, "by_section": by_section, "cp": cp}


# --------------------------------------------------------------------------- 选包

def select_package(packages, question_text, question_type=None):
    """在同一层级（同一 activity 或同一 Section）的多个证据包中挑 **1 个**。

    规则（按用户裁定）：
      1. 先按 `question_type` 过滤（**必须相等**）；
      2. 若过滤后为空，说明“证据包与题不同类” —— **返回 None 并记录日志**
         （给出错误类型的证据比“无证据”更糟；实测 41/41 满足相等，此分支预期不触发）；
      3. 前缀匹配度最高者优先（兼容证据包 text 被截断到 400 字符的情形）；
      4. 前缀匹配度为 0 时，取 `(activity_no, question_no)` 最小者（确定性排序）。
    """
    cand = list(packages or [])
    if not cand:
        return None
    if question_type is not None:
        want = _norm(question_type)
        typed = [p for p in cand if _pkg_type(p) == want]
        if not typed:
            _log("类型不匹配：题库 type=%s，候选包 type=%s（返回 None，不用错误类型的证据）"
                 % (want, sorted({_pkg_type(p) for p in cand})))
            return None
        cand = typed
    best = max(cand, key=lambda p: _prefix_len(_pkg_text(p), question_text))
    if _prefix_len(_pkg_text(best), question_text) > 0:
        return best
    return min(cand, key=lambda p: (_scope(p, "activity_no") or 0, _scope(p, "question_no") or 0))


# --------------------------------------------------------------------------- 主入口

def resolve_question_evidence(question, packages=None, contentpack_path=DEFAULT_CONTENTPACK) -> dict:
    """把一道题解析到证据包。

    `question` 为 `questionbank.question` 的行（dict / sqlite3.Row），需含
    `question_id` / `question_type` / `unit_code` / `section_key` / `activity_id` / `prompt_json`。

    返回（**任何字段都不谎言**）：
      {
        "granularity": "activity" | "section" | None,
        "package": dict | None,              # 选中的证据包
        "package_question_id": str | None,   # 证据包自带的 question_id（便于审计）
        "resolved_via": "activity_id" | "activity_ref" | "section_fallback" | None,
        "candidates": int,                   # 该层级的候选包数（审计用）
      }
    """
    def _q(key, default=None):
        try:
            return question[key]
        except (KeyError, IndexError, TypeError):
            return default

    empty = {"granularity": None, "package": None, "package_question_id": None,
             "resolved_via": None, "candidates": 0}
    unit = (_q("unit_code") or "").strip()
    section = _q("section_key")
    if not unit or unit == APPENDIX_UNIT:
        return empty                       # Appendix / 无 Unit：非教学范围，不给证据

    # ⚠️ 题型必须用 prompt_json 里的**细粒度** question_type。
    # `questionbank.question.question_type` 列是粗粒度的：全部 241 道 ai_eval 题都是
    # "textbook_native"，而证据包的 original_question.question_type 是细粒度的
    # （match / fill / choice / judge / short_answer / speaking / writing / order / other）。
    # 实测（2026-09-29）：用细粒度口径比较，41/41 个共同 activity 的题型集合完全相等；
    # 用粗粒度口径则 0/41 命中（会把全部题误判为“类型不匹配”）。
    qtext = ""
    qtype = _q("question_type")
    try:
        pj = json.loads(_q("prompt_json") or "{}") or {}
    except (ValueError, TypeError):
        pj = {}
    if isinstance(pj, dict):
        qtext = pj.get("text") or ""
        if pj.get("question_type"):
            qtype = pj["question_type"]
    idx = build_package_index(packages, contentpack_path)

    # ---- 第 1 优先：activity_id（与 contentpack 同源）
    aid = (_q("activity_id") or "").strip()
    via = "activity_id" if aid else None
    if not aid:
        # 次选：prompt_json.source_activity_ref（仅完整 activity_id 形式可用）
        ref = ""
        if isinstance(pj, dict):
            ref = (pj.get("source_activity_ref") or "").strip()
        if ref.startswith("FLTRP-"):
            aid, via = ref, "activity_ref"
        elif ref:
            # 实测：形如 "A:<hash>" 的短引用在 contentpack 中 0/27 命中，属另一个 id-space
            _log("短 activity 引用不可解析（%s），降级 Section 级：%s" % (ref, _q("question_id")))
    if aid:
        cands = idx["by_activity"].get(aid) or []
        pkg = select_package(cands, qtext, qtype)
        if pkg is not None:
            return {"granularity": GRANULARITY_ACTIVITY, "package": pkg,
                    "package_question_id": pkg.get("question_id"),
                    "resolved_via": via, "candidates": len(cands)}

    # ---- 第 2 优先：Section 级降级（**必须带 unit_code**：section_key 不是唯一键）
    if not section:
        return empty                       # Unit 级词表题（section_key 为空）不属任何 Section
    cands = idx["by_section"].get((unit, section)) or []
    pkg = select_package(cands, qtext, qtype)
    if pkg is None:
        return empty                       # 该 Section 无包 / 类型不匹配：如实返回无证据
    return {"granularity": GRANULARITY_SECTION, "package": pkg,
            "package_question_id": pkg.get("question_id"),
            "resolved_via": "section_fallback", "candidates": len(cands)}


def evidence_count_for_gate(resolution: dict | None, granularity: str | None = None) -> int:
    """证据条数的**上报口径**（决定闸门 `confidence_rule` 是否触发）：

      * `activity` —— 按 `count_evidence_fields()` **实际计数**（通常 ≥2）；
      * `section`  —— **强制 1**：Section 级证据不含 per-activity 指令，判“答题要求”更弱；
                      若按实际字段数计数（实测 ≈1–2）会以“证据充足”的名义放行较弱判断，
                      故强制 1 让它落入保守分支（`confidence ≤ medium` 且 `need_intervention != need_now`）；
      * `None` / 无包 —— **0**。
    """
    res = resolution or {}
    g = granularity if granularity is not None else res.get("granularity")
    pkg = res.get("package")
    if g == GRANULARITY_ACTIVITY:
        return count_evidence_fields(pkg)
    if g == GRANULARITY_SECTION:
        return 1 if pkg else 0
    return 0


if __name__ == "__main__":       # 手工自检（只读）
    qb = BASE / "structured" / "questionbank" / "questionbank.db"
    conn = sqlite3.connect("file:%s?mode=ro" % qb.as_posix(), uri=True)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT question_id, question_type, unit_code, section_key, activity_id, prompt_json "
        "FROM question WHERE answer_kind='ai_eval'"
    ).fetchall()
    stat = {"activity": 0, "section": 0, "None": 0}
    for r in rows:
        res = resolve_question_evidence(r)
        stat[str(res["granularity"])] += 1
    conn.close()
    print("ai_eval 共 %d 题；粒度分布 = %s" % (len(rows), stat))
    sys.exit(0)
