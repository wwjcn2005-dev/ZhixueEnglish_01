#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P1-08-C1 最小学习行为模型与记录协议

解决的问题：LearningActivity 已经知道“学什么”，这里定义“孩子对它做了什么”，
并统一记录为 LearningRecord。

最小行为集合（P1-08-C1 §六）：
    study    ：孩子主动进行了学习 / 理解活动
    practice ：孩子主动进行了练习或自测

兼容既有协议（§五、§六「除非现有代码已经存在并且必须兼容」）：
    learning_service.ACTIVITY_TYPES 原有 9 值（recognize / read / understand / listen /
    repeat / spell / substitute / produce / review）保持不变并继续有效；
    本任务只**追加** study / practice（见 learning_service.BEHAVIOR_EXTENSION）。

行为与结果分离（§四、§十）：
    行为 = activity_type ；判断结果 = result ∈ {correct, incorrect, partial, done, skipped, NULL}
    - study    ：无对错语义 → 允许 done / skipped / NULL（不产生 correct/incorrect/partial）
    - practice ：可判定 → 允许 correct / incorrect / partial / done / skipped / NULL
    该映射沿用 B1.15 §6 的既有约定（read/listen 类 → done；spell/substitute 类 → correct/incorrect/partial），
    未新增评分或掌握算法。

硬约束（§九、§十二、§十三）：
    - 只有显式调用本模块的记录函数才写 LearningRecord；
      创建 Session / Task / TaskItem、查询 Activity、浏览资源、查看池、AI 建议均不写记录。
    - 完全委托现有 record_learning_event()（不复制其校验与事务逻辑）。
    - 不修改 MasteryState 派生逻辑；不修改 C2-A 池规则；不新增表/字段。
    - 不调用 AI、不联网。
"""

from __future__ import annotations

import os

from pathlib import Path

import learning_service as svc

BASE = Path(os.environ.get("ZX_ROOT") or r"D:\ZhixueEnglish")
DEFAULT_CONTENTPACK_DB = BASE / "structured" / "contentpack" / "v5" / "FLTRP-EN-7A-2022CUR.sqlite"

STUDY = "study"
PRACTICE = "practice"

#: 本阶段最小行为集合（顺序即展示顺序）
BEHAVIOR_TYPES = (STUDY, PRACTICE)

#: 每个行为允许的结果集合（None 表示 result=NULL，总是允许）
BEHAVIOR_RESULTS = {
    STUDY: ("done", "skipped"),
    PRACTICE: ("correct", "incorrect", "partial", "done", "skipped"),
}


def check_behavior(behavior) -> str:
    """校验行为类型属于 P1-08-C1 最小集合。"""
    if behavior not in BEHAVIOR_TYPES:
        raise svc.ValidationError("behavior 必须是 %s 之一（本阶段最小集合）" % (BEHAVIOR_TYPES,))
    return behavior


def check_behavior_result(behavior, result):
    """校验“行为 × 结果”组合合法（None 表示 result=NULL，允许）。"""
    check_behavior(behavior)
    if result is None:
        return result
    if result not in BEHAVIOR_RESULTS[behavior]:
        raise svc.ValidationError(
            "%s 的结果只能是 %s 或 NULL，当前为 %r" % (behavior, BEHAVIOR_RESULTS[behavior], result))
    return result


def record_behavior(conn, learner_id, task_id, item_id, behavior, result=None,
                    response_raw=None, hints_used=0, snapshot_id=None, created_at=None,
                    contentpack_path=DEFAULT_CONTENTPACK_DB) -> dict:
    """记录一次**真实发生**的学习 / 练习行为（完全委托 record_learning_event）。"""
    check_behavior_result(behavior, result)
    return svc.record_learning_event(conn, learner_id, task_id, item_id, behavior,
                                     result=result, response_raw=response_raw,
                                     hints_used=hints_used, snapshot_id=snapshot_id,
                                     created_at=created_at, contentpack_path=contentpack_path)


def record_study(conn, learner_id, task_id, item_id, result="done", **kwargs) -> dict:
    """孩子主动学习 / 理解某个 LearningActivity。"""
    return record_behavior(conn, learner_id, task_id, item_id, STUDY, result=result, **kwargs)


def record_practice(conn, learner_id, task_id, item_id, result=None, **kwargs) -> dict:
    """孩子主动练习 / 自测某个 LearningActivity。"""
    return record_behavior(conn, learner_id, task_id, item_id, PRACTICE, result=result, **kwargs)


def record_activity_behavior(conn, learner_id, activity, behavior, result=None, **kwargs) -> dict:
    """对 P1-07-C2 解析出的 LearningActivity 记录行为（activity 取自 activity_service.resolve_activity）。"""
    if not isinstance(activity, dict) or "task_id" not in activity or "item_id" not in activity:
        raise svc.ValidationError("activity 必须是 activity_service.resolve_activity 的返回结果")
    return record_behavior(conn, learner_id, activity["task_id"], activity["item_id"],
                           behavior, result=result, **kwargs)


def list_behaviors() -> tuple:
    """本阶段支持的最小行为集合。"""
    return BEHAVIOR_TYPES
