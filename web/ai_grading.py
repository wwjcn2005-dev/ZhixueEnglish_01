#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-2 AI 批改入口（数据接口 + 规则预检；本阶段不真实调用 AI）

原则（任务书 §十七 / §十八 / §十九 / §二十五）：
  * 选择题 / 判断题 / 拼写 / 固定答案 → **规则判断**，不调用 AI（见 exercises.grade）；
  * 只有简答、开放性回答才走本模块的 AI 分析入口；
  * 输出是**分析 + 提示**，不是"正确答案"；孩子自己决定怎么改；
  * 本阶段只建立接口与最小闭环：`AI_PROVIDER = None`，**AI 调用次数 = 0**。

本模块的规则预检是完全确定性的（不联网、不调用模型），因此即使 AI 尚未接入，
孩子仍然能得到具体、可核对的提示。`ai_status` 只用于开发/报告，不渲染给孩子。
"""

from __future__ import annotations

import re

#: AI 提供方（本阶段未接入；接入时在此注入实现，调用点集中在 analyze_short_answer）
AI_PROVIDER = None
AI_STATUS_NOT_CONNECTED = "not_connected"

_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "do", "does", "did", "of", "to", "in", "on",
    "at", "and", "or", "for", "with", "what", "where", "who", "when", "why", "how", "which",
    "you", "your", "it", "its", "this", "that", "these", "those", "they", "them", "he", "she",
}

#: 常见主谓一致错误（确定性规则，仅提示，不替孩子改）
_BE_AGREEMENT = (
    (re.compile(r"\bi\s+(is|are)\b", re.I), "主语是 I 的时候，be 动词用 am。"),
    (re.compile(r"\b(he|she|it)\s+are\b", re.I), "主语是 he / she / it 的时候，be 动词用 is。"),
    (re.compile(r"\b(they|we|you)\s+is\b", re.I), "主语是 they / we / you 的时候，be 动词用 are。"),
)


def _content_words(text: str) -> list:
    return [w for w in re.findall(r"[A-Za-z']+", (text or "").lower())
            if len(w) > 2 and w not in _STOPWORDS]


def analyze_short_answer(question: str, answer: str) -> dict:
    """对一条简答做确定性预检，并预留 AI 语义分析入口。"""
    q = (question or "").strip()
    a = (answer or "").strip()
    hints, checks = [], []

    if not a:
        return {"status": "empty", "judgement": "还没有作答",
                "hints": ["先按自己的想法写一句，不用担心写错。"], "checks": [],
                "ai_status": AI_STATUS_NOT_CONNECTED}

    words = re.findall(r"[A-Za-z']+", a)
    checks.append({"name": "word_count", "value": len(words)})
    if len(words) < 3:
        hints.append("回答可以再完整一点：写出你想要表达的主要意思。")
    if q.lower().startswith("why") and not re.search(r"\bbecause\b|\bto\b", a, re.I):
        hints.append("题目问的是原因，回答里可以试着说明“为什么”。")
    if a[0].islower():
        hints.append("句子开头可以用大写字母。")
    if a[-1] not in ".!?":
        hints.append("句末可以加上标点。")
    q_words = set(_content_words(q))
    a_words = set(_content_words(a))
    if q_words and not (q_words & a_words):
        hints.append("回答里似乎没有用到题目中的关键词，可以对照题目再想一想。")
    for pattern, tip in _BE_AGREEMENT:
        if pattern.search(a):
            hints.append(tip)
            break

    judgement = "基本完整" if len(words) >= 5 else "还可以写得更完整"
    if not hints:
        judgement = "读起来比较完整"
    return {"status": "rule_precheck", "judgement": judgement, "hints": hints,
            "checks": checks, "word_count": len(words),
            "ai_status": AI_STATUS_NOT_CONNECTED,
            # AI 接入点：provider 提供 answer 的语义分析（是否回答问题 / 表达是否自然 / 错误类型）
            "ai_available": AI_PROVIDER is not None}


def ai_configured() -> bool:
    return AI_PROVIDER is not None
