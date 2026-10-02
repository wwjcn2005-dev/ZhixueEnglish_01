#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-6-B3 掌握判定服务（只读派生，不写库）

严格按规范 V1.2 第二十二章第 4 条与当前工程参数（`mastery_rules_v1.json`）判定：

  条件 1  有效判断证据 ≥ minimum_valid_evidence（默认 3）
  条件 2  有效证据来自 ≥ minimum_task_types 种任务类型（默认 2）
  条件 3  有效证据跨 ≥ minimum_natural_days 个自然日（默认 2）
  条件 4  最近 recent_attempt_window 次有效判断中 ≥ recent_correct_minimum 次正确（默认 3 / 2）
          —— 不足 3 次时该条件不满足
  条件 5  不存在未处理的当前错误（最近一条有效判断证据不是 incorrect）

五项全部满足才是 `stable`（对外语言：掌握较稳定）。否则保持更保守的状态。

边界：
  * 只执行 SELECT，绝不写库（不修改 LearningRecord / MasteryState）
  * 不向孩子输出等级/分数/排名；本模块只产出系统内部状态 + 判定依据
  * 不调用 AI
"""

from __future__ import annotations

import os

import sqlite3
from pathlib import Path

import evidence_service as ev

BASE = Path(os.environ.get("ZX_ROOT") or r"D:\ZhixueEnglish")
DEFAULT_RULES = BASE / "structured" / "learning" / "mastery_rules_v1.json"

#: 系统内部状态（不新增等级体系；与 V1.2 第十章状态名保持一致的保守映射）
STATE_NOT_STARTED = "not_started"          # 未学习
STATE_LEARNING = "learning"                # 正在学习（有记录但未达稳定）
STATE_NEEDS_REVIEW = "needs_review"        # 需要再次巩固（存在未处理当前错误）
STATE_STABLE = "stable"                    # 掌握较稳定（五项条件全部满足）

DISPLAY = {
    STATE_NOT_STARTED: "未学习",
    STATE_LEARNING: "正在学习",
    STATE_NEEDS_REVIEW: "需要再次巩固",
    STATE_STABLE: "掌握较稳定",
}


def evaluate(conn, learner_id: str, item_id: str, rules: dict = None,
             evidence: dict = None) -> dict:
    """判定单个资源的掌握状态（只读）。"""
    rules = rules or ev.load_rules()
    cfg = rules["stable"]
    evd = evidence or ev.collect_evidence(conn, learner_id, item_id, rules)

    count = evd["evidence_count"]
    task_types = evd["task_types"]
    days = evd["natural_days"]
    recent = evd["recent_results"]
    recent_correct = sum(1 for r in recent if r == "correct")
    latest = recent[-1] if recent else None
    has_error = latest == "incorrect"

    conditions = {
        "minimum_valid_evidence": {
            "required": cfg["minimum_valid_evidence"],
            "actual": count,
            "met": count >= cfg["minimum_valid_evidence"],
        },
        "minimum_task_types": {
            "required": cfg["minimum_task_types"],
            "actual": len(task_types),
            "met": len(task_types) >= cfg["minimum_task_types"],
            "observed": task_types,
        },
        "minimum_natural_days": {
            "required": cfg["minimum_natural_days"],
            "actual": len(days),
            "met": len(days) >= cfg["minimum_natural_days"],
            "observed": days,
        },
        "recent_correct_minimum": {
            "window": cfg["recent_attempt_window"],
            "required": cfg["recent_correct_minimum"],
            "actual": recent_correct,
            "attempts": len(recent),
            "met": (len(recent) >= cfg["recent_attempt_window"]
                    and recent_correct >= cfg["recent_correct_minimum"]),
            "observed": recent,
        },
        "no_unresolved_current_error": {
            "required": cfg["require_no_unresolved_current_error"],
            "actual": has_error,
            "met": not has_error,
            "latest_result": latest,
        },
    }
    all_met = all(c["met"] for c in conditions.values())

    if count == 0:
        state = STATE_NOT_STARTED
    elif has_error:
        state = STATE_NEEDS_REVIEW
    elif all_met:
        state = STATE_STABLE
    else:
        state = STATE_LEARNING

    unmet = [name for name, c in conditions.items() if not c["met"]]
    return {
        "learner_id": learner_id,
        "item_id": item_id,
        "state": state,
        "display": DISPLAY[state],
        "stable": state == STATE_STABLE,
        "conditions": conditions,
        "unmet_conditions": unmet,
        "evidence_count": count,
        "task_types": task_types,
        "natural_days": days,
        "recent_results": recent,
        "suppressed_count": evd["suppressed_count"],
        "evidence_ids": [e["source_record_id"] for e in evd["evidence"]],
        "reason": ("五项条件全部满足" if state == STATE_STABLE
                   else "未满足条件：" + ("、".join(unmet) if unmet else "（无记录）")),
    }


def evaluate_many(conn, learner_id: str, item_ids=None, rules: dict = None) -> dict:
    """批量判定（只读）。item_ids 为空时对存在记录的资源全部判定。"""
    rules = rules or ev.load_rules()
    if item_ids is None:
        item_ids = [r["item_id"] for r in conn.execute(
            "SELECT DISTINCT item_id FROM learning_record WHERE learner_id=?",
            (learner_id,))]
    out = {}
    for item_id in dict.fromkeys(item_ids):
        out[item_id] = evaluate(conn, learner_id, item_id, rules)
    return out


def display_text(result: dict) -> str:
    """给 UI 的合规文案：只陈述证据次数；只有真 stable 才允许出现“掌握较稳定”。"""
    if result["stable"]:
        return "掌握较稳定（有效证据 %d 次 · %d 种任务 · %d 个学习日）" % (
            result["evidence_count"], len(result["task_types"]), len(result["natural_days"]))
    return "学习证据 %d 次（不代表掌握）" % result["evidence_count"]
