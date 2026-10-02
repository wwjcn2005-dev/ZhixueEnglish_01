#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Demo V2 新增练习的确定性数据构建（只用现有教材 / Demo 数据，不调用 AI）

三类词汇练习 + 阅读练习的数据都从既有资源派生：

  听音写词：当前课时教材词表里有官方音频的词（播放音频 → 写英文）
  音标写词：当前课时教材词表里有音标的词（显示音标 → 写英文）
  词形变化：只做"教材课文里真正出现过该词形"的题——
            名词→规则复数；动词→-ing / -ed（不做有歧义的第三人称 -s）
            词形必须在**本课时教材正文块**里逐字出现，prompt 用那句正文挖空
  阅读练习：材料 = 本课时教材阅读段；选择题 = 既有 demo_content.reading_extra；
            简答题 = Demo 少量确定性示例（参考答案必须在材料里逐字出现，否则不显示）

答案口径（供页面显示）：
  教材词表/教材正文里唯一确定 → 答案
  教材有依据但不是唯一表达     → 参考答案
  开放表达（孩子自己写）        → 参考表达
"""

from __future__ import annotations

import os

import re
import sys
import unicodedata
from pathlib import Path

BASE = Path(os.environ.get("ZX_ROOT") or r"D:\ZhixueEnglish")
for _p in (str(BASE / "demo"), str(BASE / "web")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
sys.dont_write_bytecode = True

ANSWER = "答案"
REFERENCE_ANSWER = "参考答案"
REFERENCE_EXPRESSION = "参考表达"

SPELL_LIMIT = 8
PHONETIC_LIMIT = 8
FORM_LIMIT = 4
READ_MATERIAL_CHARS = 1200          # 教材阅读段整段呈现（最长约 970 字符）

#: 常见不规则复数（只在这些词形确实出现在教材正文时才出题）
IRREGULAR_PLURAL = {"child": "children", "man": "men", "woman": "women", "foot": "feet",
                    "tooth": "teeth", "mouse": "mice", "sheep": "sheep", "fish": "fish"}


def _norm(text) -> str:
    t = unicodedata.normalize("NFC", text or "")
    t = t.replace("\u2019", "'").replace("\u2018", "'")
    t = t.replace("\u201c", '"').replace("\u201d", '"')
    return " ".join(t.split()).lower()


def _server():
    import server as demo_server                 # 延迟导入，避免与 server 循环导入
    return demo_server


# --------------------------------------------------------------------------- 词汇
def spell_tasks(unit: dict, lesson: dict) -> list:
    """听音写词：有官方音频的教材重点词（一个词一个任务）。"""
    out = []
    for i, w in enumerate(_server().lesson_vocab(unit, lesson)):
        word = (w.get("text") or "").strip()
        if not re.fullmatch(r"[A-Za-z][A-Za-z' -]{1,20}", word):
            continue
        if not w.get("audio_url"):
            continue
        out.append({"id": "spell:%d" % i, "word": word, "audio_url": w["audio_url"],
                    "meaning": w.get("meaning") or "", "page": w.get("page")})
        if len(out) >= SPELL_LIMIT:
            break
    return out


def phonetic_tasks(unit: dict, lesson: dict) -> list:
    """音标写词：有音标的教材重点词（只显示音标，不显示中文，避免等于抄答案）。"""
    out = []
    for i, w in enumerate(_server().lesson_vocab(unit, lesson)):
        word = (w.get("text") or "").strip()
        phonetic = (w.get("phonetic") or "").strip()
        if not phonetic or not re.fullmatch(r"[A-Za-z][A-Za-z' -]{1,20}", word):
            continue
        out.append({"id": "phonetic:%d" % i, "word": word, "phonetic": phonetic,
                    "pos": w.get("part_of_speech") or "", "page": w.get("page")})
        if len(out) >= PHONETIC_LIMIT:
            break
    return out


FORM_REASON = {"plural": "这里说的是不止一个，所以用复数形式。",
               "ing": "这里表示“正在……”，所以用 -ing 形式。",
               "ed": "这里说的是已经发生的事，所以用 -ed 形式。"}


def _candidate_forms(word: str, pos: str) -> list:
    """词形变化的候选（只保留不易产生歧义的形式）。"""
    w = word.lower()
    forms = []
    if pos == "n":
        if w in IRREGULAR_PLURAL:
            forms.append(IRREGULAR_PLURAL[w])
        if w.endswith(("s", "x", "ch", "sh")):
            forms.append(w + "es")
        elif w.endswith("y") and len(w) > 2 and w[-2] not in "aeiou":
            forms.append(w[:-1] + "ies")
        else:
            forms.append(w + "s")
    elif pos == "v":
        # 只做 -ing / -ed：第三人称 -s 与名词复数同形，容易判错
        forms.append((w[:-1] + "ing") if w.endswith("e") else (w + "ing"))
        forms.append((w + "d") if w.endswith("e") else (w + "ed"))
    return [f for f in dict.fromkeys(forms) if f and f != w]


def form_tasks(unit: dict, lesson: dict) -> list:
    """词形变化：词形必须在本课时教材正文里逐字出现（教材事实），prompt 用那句正文挖空。"""
    demo_server = _server()
    blocks = [b for b in demo_server.blocks(unit)
              if (demo_server.section_of_page(unit, b.get("page")) or {}).get("key")
              == (lesson or {}).get("key")]
    if not blocks:
        return []
    text = " ".join((b.get("text") or "") for b in blocks)
    flat = _norm(text)
    out, seen = [], set()
    for w in demo_server.lesson_vocab(unit, lesson):
        base = (w.get("text") or "").strip()
        pos = (w.get("part_of_speech") or "").strip()
        if not re.fullmatch(r"[a-z]{3,}", base.lower()) or pos not in ("n", "v"):
            continue
        for form in _candidate_forms(base, pos):
            if not re.search(r"\b%s\b" % re.escape(form), flat):
                continue
            sentence = _sentence_with(text, form)
            if not sentence:
                continue
            prompt = re.sub(r"\b%s\b" % re.escape(form), "______", sentence,
                            count=1, flags=re.I)
            key = (base.lower(), form)
            if key in seen:
                continue
            seen.add(key)
            kind = ("plural" if pos == "n"
                    else ("ing" if form.endswith("ing") else "ed"))
            out.append({"id": "form:%d" % len(out), "base": base, "form": form,
                        "prompt": prompt, "pos": pos, "reason": FORM_REASON[kind]})
            break
        if len(out) >= FORM_LIMIT:
            break
    return out


def _sentence_with(text: str, form: str) -> str:
    """取包含该词形的那一句（教材原文，长度适中）。"""
    for raw in re.split(r"(?<=[.!?])\s+", text or ""):
        s = " ".join((raw or "").split())
        if re.search(r"\b%s\b" % re.escape(form), s, re.I) and 15 <= len(s) <= 180:
            return s
    return ""


# --------------------------------------------------------------------------- 阅读
#: 阅读简答的确定性示例（参考答案必须在阅读材料里逐字出现，否则该题不显示）
READING_SHORT = {
    "Starter": [{"unit": "Starter", "lesson": "KNOW_YOUR_SCHOOL",
                 "question": "What does Ms Wang give everyone?",
                 "reference": "Our English teacher, Ms Wang, gives everyone a textbook."}],
    "Unit 1": [{"unit": "Unit 1", "lesson": "UNDERSTANDING_IDEAS",
                "question": "Why is the sentence on the blackboard not right?",
                "reference": "That sentence is from Confucius, not from Mencius."}],
    "Unit 2": [{"unit": "Unit 2", "lesson": "UNDERSTANDING_IDEAS",
                "question": "What do Grandpa and the writer do after a week's practice?",
                "reference": "After a week's practice, we are on the stage."}],
    "Unit 3": [{"unit": "Unit 3", "lesson": "UNDERSTANDING_IDEAS",
                "question": "What does carrying his father across the river bring back?",
                "reference": "It brings back the father's memory of carrying the son on his back."}],
    "Unit 4": [{"unit": "Unit 4", "lesson": "UNDERSTANDING_IDEAS",
                "question": "What does the round shape of the meatball stand for?",
                "reference": "Its round shape stands for family reunions."}],
    "Unit 5": [{"unit": "Unit 5", "lesson": "UNDERSTANDING_IDEAS",
                "question": "What do workers in the Leaf mix?",
                "reference": "Then workers in the Leaf will mix water, CO2 and sunlight."}],
    "Unit 6": [{"unit": "Unit 6", "lesson": "UNDERSTANDING_IDEAS",
                "question": "Which of these can pigeons do?",
                "reference": "Pigeons can recognise themselves in mirrors."}],
}


def _passage(unit: dict, lesson: dict) -> str:
    """本课时教材阅读段（没有就空串）。"""
    demo_server = _server()
    chunks = []
    for seg in demo_server.lesson_reading(unit, lesson):
        for row in seg.get("chunks") or []:
            chunks.append(row.get("text") or "")
    return " ".join(c for c in chunks if c).strip()


def _english_quotes(text: str) -> list:
    """从「教材依据」里取出英文原句（用于确认这道题属于哪段材料）。"""
    out = []
    for run in re.findall(r"[A-Za-z][A-Za-z0-9,;:'\"()\- ]{14,}", text or ""):
        out.append(_norm(run))
    return out


def reading_material(unit: dict, lesson: dict) -> str:
    """阅读材料：教材正文段优先；Demo 既有固定阅读材料（source=fixed）也可用。"""
    demo_server = _server()
    import demo_content
    extra = demo_content.reading_extra(unit["unit_code"])
    passage = _passage(unit, lesson)
    if extra.get("source") == "fixed":
        fixed = " ".join((extra.get("text") or "").split())
        return fixed[:READ_MATERIAL_CHARS]
    return " ".join(passage.split())[:READ_MATERIAL_CHARS]


def reading_tasks(unit: dict, lesson: dict) -> dict:
    """阅读练习：选择题（既有 Demo 数据）+ 简答题（确定性示例，参考答案可核验）。"""
    material = reading_material(unit, lesson)
    if not material:
        return {"material": "", "items": []}
    import demo_content
    extra = demo_content.reading_extra(unit["unit_code"])
    if extra.get("source") != "fixed":
        # 教材阅读题必须真的属于这一课时的阅读段（依据原句能在这段材料里找到）
        passage = _passage(unit, lesson)
        if not passage:
            return {"material": "", "items": []}
        flat = _norm(passage)
        quotes = [q for x in (extra.get("questions") or [])
                  for q in _english_quotes(x.get("why") or "")]
        if quotes and not any(q in flat for q in quotes):
            return {"material": "", "items": []}
    material = reading_material(unit, lesson)
    flat = _norm(material)
    items = []
    for i, q in enumerate(extra.get("questions") or []):
        if q.get("kind") != "choice":
            continue
        items.append({"id": "readc:%d" % i, "kind": "choice", "type": q.get("type") or "阅读理解",
                      "prompt": q.get("prompt") or "",
                      "options": [(chr(ord("a") + j), t) for j, t in enumerate(q.get("options") or [])],
                      "answer": (q.get("answer") or "a").lower(), "basis": q.get("why") or "",
                      "answer_label": ANSWER})
    for i, row in enumerate(READING_SHORT.get(unit["unit_code"], [])):
        if row.get("lesson") != lesson.get("key"):
            continue
        if _norm(row.get("reference")) not in flat:
            continue                       # 参考答案无法在材料里核实 → 不显示
        items.append({"id": "reads:%d" % i, "kind": "short", "type": "阅读简答",
                      "prompt": row["question"], "reference": row["reference"],
                      "answer_label": REFERENCE_ANSWER})
    return {"material": material, "items": items}


def check_reading_item(unit: dict, lesson: dict):
    """本课检测里要合并的"阅读简答"题（材料里能核实参考答案才返回，否则 None）。"""
    material = reading_material(unit, lesson)
    if not material:
        return None
    flat = _norm(material)
    for i, row in enumerate(READING_SHORT.get(unit["unit_code"], [])):
        if row.get("lesson") != (lesson or {}).get("key"):
            continue
        if _norm(row.get("reference")) not in flat:
            continue
        return {"id": "rs%d" % i, "type": "阅读简答", "kind": "short",
                "prompt": row["question"], "options": [], "answer": "",
                "answer_label": REFERENCE_ANSWER, "reference": row["reference"],
                "why": "", "basis_label": "教材课文", "basis_text": "",
                "focus": "", "material": material}
    return None


def activity_counts(unit: dict, lesson: dict) -> dict:
    """四类新增练习的题量（用于入口状态与完成判定）。"""
    return {"spell": len(spell_tasks(unit, lesson)),
            "phonetic": len(phonetic_tasks(unit, lesson)),
            "form": len(form_tasks(unit, lesson)),
            "read": len(reading_tasks(unit, lesson)["items"])}
