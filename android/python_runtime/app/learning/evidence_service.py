#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-6-B2 有效证据服务（只读派生）

把原始 LearningRecord 转成「有效判断证据」，严格遵循规范 V1.2 第二十二章第 4、5 条：

  * `done` / `skipped` / NULL 不计为有效判断证据（自评只陈述事实）
  * 单纯学习/浏览（activity_type=study）不计为有效判断证据
  * 仅自评（response_raw 里只有 self_check，没有实际作答）不计为有效判断证据
  * 同一 (learner_id, item_id, 自然日, task_type) 的重复操作最多贡献 1 个独立证据
  * 无法判断是否属于有效判断的记录 → 标记 not_evaluable，不强行计入

本模块：
  - 只执行 SELECT（绝不写库：无 INSERT / UPDATE / DELETE / DDL）
  - 不调用 AI / 不联网
  - 参数来自 `structured/learning/mastery_rules_v1.json`，不写死在代码里
"""

from __future__ import annotations

import os

import json
import sqlite3
from pathlib import Path

BASE = Path(os.environ.get("ZX_ROOT") or r"D:\ZhixueEnglish")
DEFAULT_LEARNING_DB = BASE / "structured" / "learning" / "learning.db"
DEFAULT_CONTENTPACK_DB = BASE / "structured" / "contentpack" / "v5" / "FLTRP-EN-7A-2022CUR.sqlite"
DEFAULT_RULES = BASE / "structured" / "learning" / "mastery_rules_v1.json"
DEFAULT_EXERCISE_CATALOG = BASE / "structured" / "exercises" / "exercise_catalog_v3.json"

_CATALOG_CACHE = {}


def connect_learning_db(path=DEFAULT_LEARNING_DB) -> sqlite3.Connection:
    """只读打开 learning.db。"""
    conn = sqlite3.connect("file:%s?mode=ro" % Path(path).as_posix(), uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def load_rules(path=DEFAULT_RULES) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _catalog(path=DEFAULT_EXERCISE_CATALOG) -> dict:
    key = str(path)
    if key not in _CATALOG_CACHE:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            _CATALOG_CACHE[key] = {e["exercise_id"]: e for e in data.get("exercises", [])}
        except Exception:
            _CATALOG_CACHE[key] = {}
    return _CATALOG_CACHE[key]


def normalize_task_type(item_id: str, activity_type: str, catalog_path=DEFAULT_EXERCISE_CATALOG) -> str:
    """规范化 task_type（稳定、有限；不凭空创造大量类型）。"""
    ex = _catalog(catalog_path).get(item_id)
    if ex and ex.get("question_type"):
        return str(ex["question_type"])
    if activity_type == "study":
        return "textbook_study"
    if activity_type == "practice":
        return "recall"
    return activity_type or "unknown"


def _self_assessment_only(response_raw: str) -> bool:
    """仅自评（含 self_check 但没有实际作答 q*/m*）→ 不是有效判断证据。"""
    if not response_raw:
        return False
    try:
        payload = json.loads(response_raw)
    except Exception:
        return False
    answers = (payload or {}).get("answers")
    if not isinstance(answers, dict):
        return False
    has_self_check = "self_check" in answers
    has_answers = any((k.startswith("q") or k.startswith("m")) and str(k[1:]).isdigit()
                      for k in answers)
    return has_self_check and not has_answers


def _evidence_date(created_at: str) -> str:
    """自然日：created_at 为带时区偏移的 ISO8601，取本地日期部分。"""
    return (created_at or "")[:10]


def classify_record(record, rules, catalog_path=DEFAULT_EXERCISE_CATALOG) -> dict:
    """单条 LearningRecord → 证据判定（不改库）。"""
    cfg = rules["evidence"]
    result = record["result"]
    activity_type = record["activity_type"]
    task_type = normalize_task_type(record["item_id"], activity_type, catalog_path)
    base = {
        "learner_id": record["learner_id"],
        "item_id": record["item_id"],
        "source_record_id": record["record_id"],
        "activity_type": activity_type,
        "task_type": task_type,
        "result": result,
        "created_at": record["created_at"],
        "evidence_date": _evidence_date(record["created_at"]),
    }
    if result not in cfg["counted_results"]:
        base.update({"is_valid": False, "reason": "result_not_judged"})
    elif activity_type in cfg["contact_only_activity_types"]:
        base.update({"is_valid": False, "reason": "contact_only"})
    elif _self_assessment_only(record["response_raw"]):
        base.update({"is_valid": False, "reason": "self_assessment_only"})
    else:
        base.update({"is_valid": True, "reason": "judged_result"})
    base["dedupe_key"] = tuple(str(base[f]) for f in cfg["dedupe_key"])
    return base


def collect_evidence(conn, learner_id: str, item_id: str = None, rules: dict = None,
                     catalog_path=DEFAULT_EXERCISE_CATALOG) -> dict:
    """收集某学习者（可选某资源）的证据，并执行独立性去重。"""
    rules = rules or load_rules()
    sql = ("SELECT record_id, learner_id, item_id, activity_type, result, response_raw, "
           "created_at FROM learning_record WHERE learner_id=?")
    params = [learner_id]
    if item_id:
        sql += " AND item_id=?"
        params.append(item_id)
    sql += " ORDER BY created_at ASC, record_id ASC"
    rows = [dict(r) for r in conn.execute(sql, params)]

    classified = [classify_record(r, rules, catalog_path) for r in rows]
    valid, invalid, not_evaluable = [], [], []
    for c in classified:
        if c["is_valid"]:
            valid.append(c)
        elif c["reason"] == "result_not_judged":
            invalid.append(c)                      # done / skipped / NULL：事实保留，不作证据
        elif c["reason"] in ("contact_only", "self_assessment_only"):
            not_evaluable.append(c)                # 接触 / 仅自评：不可判定为掌握证据
        else:
            not_evaluable.append(c)

    keep = rules["evidence"].get("dedupe_keep", "latest")
    groups = {}
    for c in valid:
        groups.setdefault(c["dedupe_key"], []).append(c)
    independent = []
    for key, members in groups.items():
        ordered = sorted(members, key=lambda x: (x["created_at"], x["source_record_id"]))
        chosen = ordered[-1] if keep == "latest" else ordered[0]
        chosen_id = chosen["source_record_id"]
        chosen = dict(chosen)
        chosen["deduped_from"] = [m["source_record_id"] for m in ordered
                                  if m["source_record_id"] != chosen_id]
        chosen["independent_count"] = 1
        independent.append(chosen)
    independent.sort(key=lambda x: (x["created_at"], x["source_record_id"]))

    days = sorted({c["evidence_date"] for c in independent})
    task_types = sorted({c["task_type"] for c in independent})
    return {
        "learner_id": learner_id,
        "item_id": item_id,
        "evidence_count": len(independent),
        "evidence": independent,
        "suppressed_count": sum(len(v) - 1 for v in groups.values() if len(v) > 1),
        "not_evaluable": not_evaluable,
        "invalid": invalid,
        "natural_days": days,
        "task_types": task_types,
        "recent_results": [c["result"] for c in independent[-rules["stable"]["recent_attempt_window"]:]],
    }


def summary_by_item(conn, learner_id: str, rules: dict = None) -> dict:
    """按 item_id 汇总证据（供掌握判定批量使用）。"""
    rules = rules or load_rules()
    items = [r["item_id"] for r in conn.execute(
        "SELECT DISTINCT item_id FROM learning_record WHERE learner_id=?", (learner_id,))]
    return {i: collect_evidence(conn, learner_id, i, rules) for i in sorted(items)}
