#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-6-B4 诊断服务（只读派生，确定性规则，不调用 AI）

最小诊断层级（规范 V1.2 第二十二章第 5 条 + 工程参数）：

  current_error            最近一条有效判断证据为 incorrect —— 只表示“最近出现明确错误”
  suspected_weak           达到重复性（错误 ≥2 次，或错误出现在 ≥2 种任务类型）才允许
  needs_textbook_review    反复 partial 且跨任务类型（≥2 条 partial、≥2 种任务类型）

铁律：**一次错误不等于薄弱**。单次错误最多输出 `current_error`。
所有结论都必须可追溯到具体证据记录（evidence_ids）。

边界：只读；不写库；不自动安排学习；不调用 AI。
"""

from __future__ import annotations

import os

from pathlib import Path

import evidence_service as ev
import mastery_service as mastery
import resource_pool_service as pool

BASE = Path(os.environ.get("ZX_ROOT") or r"D:\ZhixueEnglish")

LEVEL_NONE = "none"
LEVEL_CURRENT_ERROR = "current_error"
LEVEL_SUSPECTED_WEAK = "suspected_weak"
LEVEL_TEXTBOOK_REVIEW = "needs_textbook_review"

LEVEL_LABELS = {
    LEVEL_NONE: "暂无需要处理的内容",
    LEVEL_CURRENT_ERROR: "最近这一次做错了",
    LEVEL_SUSPECTED_WEAK: "同一处反复出错",
    LEVEL_TEXTBOOK_REVIEW: "建议回到教材再看一遍",
}


def diagnose(conn, learner_id: str, item_id: str, rules: dict = None,
             evidence: dict = None) -> dict:
    """单个资源的诊断（只读）。"""
    rules = rules or ev.load_rules()
    dcfg = rules["diagnosis"]
    evd = evidence or ev.collect_evidence(conn, learner_id, item_id, rules)
    valid = evd["evidence"]
    errors = [e for e in valid if e["result"] == "incorrect"]
    partials = [e for e in valid if e["result"] == "partial"]
    error_types = sorted({e["task_type"] for e in errors})
    partial_types = sorted({e["task_type"] for e in partials})
    latest = valid[-1]["result"] if valid else None

    # 冻结池语义（P1-06-C2-A）只作为“最近一次判断的事实”，不用于升级为薄弱
    try:
        pool_status = pool.get_item_pool_status(conn, learner_id, item_id)
        pool_state = (pool_status or {}).get("issue_type")
    except Exception:
        pool_state = None

    level = LEVEL_NONE
    signals = []
    if latest == "incorrect":
        level = LEVEL_CURRENT_ERROR
        signals.append("latest_result=incorrect")

    weak_cfg = dcfg["suspected_weak"]
    if len(errors) >= weak_cfg["minimum_errors"] or len(error_types) >= weak_cfg["or_error_task_types"]:
        if len(errors) >= 1:
            level = LEVEL_SUSPECTED_WEAK
            signals.append("errors=%d task_types=%d" % (len(errors), len(error_types)))

    rev_cfg = dcfg["textbook_review"]
    if (len(partials) >= rev_cfg["minimum_partial_evidence"]
            and len(partial_types) >= rev_cfg["minimum_task_types"]):
        if level in (LEVEL_NONE, LEVEL_CURRENT_ERROR):
            level = LEVEL_TEXTBOOK_REVIEW
        signals.append("partials=%d task_types=%d" % (len(partials), len(partial_types)))

    return {
        "learner_id": learner_id,
        "item_id": item_id,
        "level": level,
        "label": LEVEL_LABELS[level],
        "signals": signals,
        "error_count": len(errors),
        "partial_count": len(partials),
        "error_task_types": error_types,
        "partial_task_types": partial_types,
        "evidence_count": evd["evidence_count"],
        "evidence_ids": [e["source_record_id"] for e in valid],
        "mastery_state": mastery.evaluate(conn, learner_id, item_id, rules, evd)["state"],
        "thresholds": {"suspected_weak": weak_cfg, "textbook_review": rev_cfg},
        "note": "单次错误只标记 current_error，不判定为薄弱。",
        "pool_state": pool_state,
        "pool_note": "pool_state 来自冻结只读池（P1-06-C2-A），只表示最近一次判断的事实。",
    }


def list_attention(conn, learner_id: str, rules: dict = None) -> list:
    """列出需要关注（level != none）的资源，按严重度排序（只读）。"""
    rules = rules or ev.load_rules()
    order = {LEVEL_SUSPECTED_WEAK: 0, LEVEL_TEXTBOOK_REVIEW: 1, LEVEL_CURRENT_ERROR: 2}
    out = []
    for item_id in [r["item_id"] for r in conn.execute(
            "SELECT DISTINCT item_id FROM learning_record WHERE learner_id=?", (learner_id,))]:
        d = diagnose(conn, learner_id, item_id, rules)
        if d["level"] != LEVEL_NONE:
            out.append(d)
    out.sort(key=lambda x: (order.get(x["level"], 9), x["item_id"]))
    return out
