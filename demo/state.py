#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""智学英语全功能交互 Demo V1.0 —— 状态层（只存在浏览器 Cookie 里）

边界（严格遵守任务书 §八 / §二）：
  * Demo 状态只保存在浏览器 Cookie 中，**不写 learning.db、不建任何数据库、不落盘**。
  * 刷新页面不清零；换 Unit 不影响别的 Unit 已完成的进度。
  * 这里只有纯函数：不导入 web/ 的任何模块，不产生任何副作用。

Cookie 取值格式：base64url(JSON)，短键，尽量小（4KB 以内）。
"""

from __future__ import annotations

import base64
import binascii
import json

#: Cookie 名（与正式 Web 的 zx_demo / zx_wrong 区分开，互不影响）
COOKIE_NAME = "zx_demo10"

#: Demo 的学习入口（顺序即首页顺序，与本轮最终产品结构一致）
STEPS = ("vocab", "listen", "check", "sentences", "reading", "say")
STEP_LABELS = {"vocab": "单词跟读", "listen": "听音辨意", "check": "本课检测",
               "sentences": "短句跟读", "reading": "听音阅读", "say": "课文简答"}

#: 词汇记忆判断的三种结果（孩子自己的判断，不是系统评分）
JUDGEMENTS = ("know", "fuzzy", "forgot")
JUDGEMENT_LABELS = {"know": "记得", "fuzzy": "有点模糊", "forgot": "忘了"}


def blank() -> dict:
    """一份全新的 Demo 状态。"""
    return {
        "u": "",      # 当前 Unit slug
        "l": {},      # 每个 Unit 当前选中的课时：{slug: SECTION_KEY}
        "w": {},      # 词汇判断：{slug: {word_key: "know|fuzzy|forgot"}}
        "a": {},      # 练习作答：{slug: {qid: "1|0"}}（1 = 答对）
        "li": {},     # 听音辨意作答：{slug: {"word": {qid: "a"}, "sentence": {...}}}
        "ps": {},     # 专项/巩固练习作答：{scope: {session: {qid: "a"}}}
        "s": {},      # 已完成环节：{slug: {"vocab": 1, ...}}
        "sp": {},     # 口语：{slug: {"n": 跟读次数, "at": 时间戳}}
        "q": {},      # 课文简答：{slug: {"t": 孩子写的那句话, "n": 加答案几次}}
        "ty": {},     # 输入型作答：{scope: {task_id: 孩子输入的英文}}
        "min": 0,     # 累计学习分钟（演示用轻量计时）
        "at": "",     # 最近学习时间（"09-16 12:30"）
        "last": "",   # 最近访问位置（路径）
    }


def decode(raw: str) -> dict:
    """把 Cookie 值解成状态；无法解析时返回全新状态（绝不抛异常给页面）。"""
    state = blank()
    if not raw:
        return state
    try:
        pad = "=" * (-len(raw) % 4)
        data = json.loads(base64.urlsafe_b64decode(raw + pad).decode("utf-8"))
    except (ValueError, binascii.Error, UnicodeDecodeError):
        return state
    if not isinstance(data, dict):
        return state
    for key in ("u", "at", "last"):
        if isinstance(data.get(key), str):
            state[key] = data[key]
    for key in ("w", "a", "s", "sp", "li", "l", "ps", "q", "ty"):
        if isinstance(data.get(key), dict):
            state[key] = data[key]
    if isinstance(data.get("min"), int) and 0 <= data["min"] <= 100000:
        state["min"] = data["min"]
    return state


def encode(state: dict) -> str:
    """状态 → Cookie 值（base64url，无填充）。"""
    payload = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")


# ---------------------------------------------------------------- 当前 Unit

def set_unit(state: dict, slug: str) -> dict:
    if slug:
        state["u"] = slug
    return state


def set_lesson(state: dict, slug: str, lesson_key: str) -> dict:
    """记下某个 Unit 当前选中的课时（教材板块）。"""
    if slug:
        book = state.setdefault("l", {})
        if not isinstance(book, dict):
            book = {}
            state["l"] = book
        book[slug] = lesson_key or ""
    return state


def lesson_of(state: dict, slug: str) -> str:
    book = state.get("l") or {}
    return (book.get(slug) or "") if isinstance(book, dict) else ""


def current_unit(state: dict, slugs, default: str) -> str:
    """当前 Unit：Cookie 里的值必须仍然存在，否则回退到默认 Unit。"""
    slug = state.get("u") or ""
    if slug in slugs:
        return slug
    if default in slugs:
        return default
    return slugs[0] if slugs else ""


def unit_slot(state: dict, key: str, slug: str) -> dict:
    """取（必要时创建）某个 Unit 的状态小节。"""
    book = state.setdefault(key, {})
    if not isinstance(book, dict):
        book = {}
        state[key] = book
    slot = book.get(slug)
    if not isinstance(slot, dict):
        slot = {}
        book[slug] = slot
    return slot


# ---------------------------------------------------------------- 学习行为

def mark_word(state: dict, slug: str, word_key: str, judgement: str) -> dict:
    """记下一个词汇判断（记得 / 有点模糊 / 忘了）。"""
    if judgement not in JUDGEMENTS:
        return state
    unit_slot(state, "w", slug)[word_key] = judgement
    return state


def word_marks(state: dict, slug: str) -> dict:
    slot = (state.get("w") or {}).get(slug) or {}
    return {k: v for k, v in slot.items() if v in JUDGEMENTS}


def mark_step(state: dict, slug: str, step: str) -> dict:
    """标记某个学习环节已经完成（只记"做过"，不记分数）。"""
    if step in STEPS:
        unit_slot(state, "s", slug)[step] = 1
    return state


def step_done(state: dict, slug: str, step: str) -> bool:
    return bool(((state.get("s") or {}).get(slug) or {}).get(step))


def note_answer(state: dict, slug: str, qid: str, picked: str) -> dict:
    """记下这一题选了哪一项（字母）。对错由题目自己的答案决定，不在这里编。"""
    picked = (picked or "").strip().lower()[:1]
    if picked.isalpha():
        unit_slot(state, "a", slug)[qid] = picked
    return state


def answers(state: dict, slug: str) -> dict:
    slot = (state.get("a") or {}).get(slug) or {}
    out = {}
    for key, value in slot.items():
        text = str(value).strip().lower()[:1]
        if text.isalpha():
            out[key] = text
        elif str(value) in ("0", "1"):          # 兼容早期状态：0/1 → b/a 之外的占位
            out[key] = "a" if str(value) == "1" else "?"
    return out


def clear_answer(state: dict, slug: str, qid: str) -> dict:
    """「再做一次」：只清掉这一题的作答，让孩子重新回答（不写任何数据库）。"""
    slot = (state.get("a") or {}).get(slug)
    if isinstance(slot, dict):
        slot.pop(qid, None)
    return state


# ---------------------------------------------------------------- 课文简答（写一句）

def say_answer(state: dict, slug: str) -> dict:
    """当前课时的课文简答：孩子写的那一句话 + 已经提交过几次（只存 Cookie）。"""
    slot = (state.get("q") or {}).get(slug) or {}
    if not isinstance(slot, dict):
        return {}
    text = str(slot.get("t") or "").strip()
    try:
        n = int(slot.get("n") or 0)
    except (TypeError, ValueError):
        n = 0
    return {"text": text, "n": max(0, n)}


def note_say(state: dict, slug: str, text: str) -> dict:
    """记下孩子这一次写的那句话（只覆盖这一课时的记录，不写任何数据库）。"""
    slot = unit_slot(state, "q", slug)
    slot["t"] = (text or "").strip()[:400]
    slot["n"] = int(slot.get("n") or 0) + 1
    return state


# ---------------------------------------------------------------- 输入型作答（拼写 / 词形 / 阅读简答）

def note_typed(state: dict, scope_key: str, task_id: str, text: str) -> dict:
    """记下孩子这一次输入的英文（听音写词 / 音标写词 / 词形变化 / 阅读简答）。"""
    text = (text or "").strip()[:80]
    if text and task_id:
        unit_slot(state, "ty", scope_key)[task_id] = text
    return state


def typed_answers(state: dict, scope_key: str) -> dict:
    slot = (state.get("ty") or {}).get(scope_key) or {}
    if not isinstance(slot, dict):
        return {}
    return {k: str(v) for k, v in slot.items() if str(v).strip()}


# ---------------------------------------------------------------- 专项/巩固练习（数据层）

def note_practice(state: dict, scope_key: str, session: str, qid: str, picked: str) -> dict:
    """记下专项/巩固练习里这一题选了哪一项（字母）。只存 Cookie。"""
    picked = (picked or "").strip().lower()[:1]
    if not picked.isalpha():
        return state
    book = unit_slot(state, "ps", scope_key)
    sess = book.get(session)
    if not isinstance(sess, dict):
        sess = {}
        book[session] = sess
    sess[qid] = picked
    return state


def practice_answers(state: dict, scope_key: str, session: str) -> dict:
    book = ((state.get("ps") or {}).get(scope_key) or {})
    sess = book.get(session) if isinstance(book, dict) else None
    if not isinstance(sess, dict):
        return {}
    return {k: str(v).strip().lower()[:1] for k, v in sess.items()
            if str(v).strip()[:1].isalpha()}


def has_practice(state: dict, scope_key: str) -> bool:
    """这个课时里有没有真的做过专项/巩固练习（只读 Cookie，用来给入口标"继续 / 未开始"）。"""
    book = ((state.get("ps") or {}).get(scope_key) or {})
    if not isinstance(book, dict):
        return False
    return any(isinstance(sess, dict) and sess for sess in book.values())


def note_speaking(state: dict, slug: str, at: str) -> dict:
    """记一次跟读完成（只记次数与时间，不记任何"发音分数"）。"""
    slot = unit_slot(state, "sp", slug)
    slot["n"] = int(slot.get("n") or 0) + 1
    slot["at"] = at
    return state


def speaking(state: dict, slug: str) -> dict:
    slot = (state.get("sp") or {}).get(slug) or {}
    return {"n": int(slot.get("n") or 0), "at": slot.get("at") or ""}


# ---------------------------------------------------------------- 听音辨意

def note_listen(state: dict, slug: str, mode: str, qid: str, picked: str) -> dict:
    """记下听音辨意这一题选了哪一项（字母）。"""
    picked = (picked or "").strip().lower()[:1]
    if mode in ("word", "sentence") and picked.isalpha():
        slot = unit_slot(state, "li", slug)
        book = slot.get(mode)
        if not isinstance(book, dict):
            book = {}
            slot[mode] = book
        book[qid] = picked
    return state


def listen_answers(state: dict, slug: str, mode: str) -> dict:
    slot = ((state.get("li") or {}).get(slug) or {})
    book = slot.get(mode) if isinstance(slot, dict) else None
    if not isinstance(book, dict):
        return {}
    out = {}
    for key, value in book.items():
        text = str(value).strip().lower()[:1]
        if text.isalpha():
            out[key] = text
    return out


# ---------------------------------------------------------------- 轻量计时 / 位置

def add_minutes(state: dict, minutes: int) -> dict:
    state["min"] = max(0, min(100000, int(state.get("min") or 0) + int(minutes)))
    return state


def touch(state: dict, stamp: str) -> dict:
    state["at"] = stamp
    return state


def set_last(state: dict, path: str) -> dict:
    state["last"] = path or ""
    return state


def last_visit(state: dict) -> dict:
    return {"path": state.get("last") or "", "at": state.get("at") or ""}
