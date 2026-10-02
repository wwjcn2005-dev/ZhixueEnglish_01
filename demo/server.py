#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""智学英语全功能交互 Demo —— 独立 HTTP 服务（第三轮：UI 回归 + 全链路优化）

启动：
    python -B D:\ZhixueEnglish\demo\server.py            # 默认 127.0.0.1:8780
    python -B D:\ZhixueEnglish\demo\server.py --host 0.0.0.0

边界：
  * 只在 `demo/` 内新增文件；不改 `web/`、`learning/`、`structured/`、`android/`、`docs/`、教材。
  * 正式数据一律**只读**：contentpack / 教材 PDF / 官方 MP3 / 派生词音频 / P3-07 ASR 数据。
  * **不使用**正式 Web 的写库路由，不连 learning.db，不调用任何 AI / ASR（AI 调用 = 0）。
  * 不切割音频：教材阅读点读播放**完整官方 MP3**。
  * Demo 状态只存在浏览器 Cookie；服务本身不写任何文件。
"""

from __future__ import annotations

import os

import argparse
import datetime
import hashlib
import html
import json
import re
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.dont_write_bytecode = True

BASE = Path(os.environ.get("ZX_ROOT") or r"D:\ZhixueEnglish")
sys.path.insert(0, str(BASE / "demo"))
sys.path.insert(0, str(BASE / "web"))

import audio as audio_mod          # noqa: E402
import ai_grading                  # noqa: E402
import content as content_mod      # noqa: E402
import demo_content                # noqa: E402
import demo_data                   # noqa: E402
import flow as flow_mod            # noqa: E402
import reading_map                 # noqa: E402

import pages                       # noqa: E402
import practice_v2                 # noqa: E402
import pool_bridge                 # noqa: E402
import say_evidence                # noqa: E402
import sentence_distractors        # noqa: E402
import state as state_mod          # noqa: E402

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8780
SERVICE = "ZhixueEnglish-Demo/1.1"

STEP_MINUTES = {"vocab": 6, "listen": 4, "check": 4, "sentences": 3, "reading": 4, "say": 3}
DEFAULT_UNIT = "unit1"
LISTEN_WORD_N = 8
LISTEN_SENT_N = 6

#: 首页 / Unit 页入口（名称简洁；cls 决定正式 UI 的低饱和配色）
ENTRY_META = (
    ("vocab", "单词跟读", "book", "e-word"),
    ("listen", "听音辨意", "headphones", "e-quiz"),
    ("check", "本课检测", "pen", "e-phrase"),
    ("sentences", "短句跟读", "mic", "e-quiz"),
    ("reading", "听音阅读", "chat", "e-word"),
    ("say", "课文简答", "pen", "e-phrase"),
    # 「自主练习」不是某一种教材资源能力：任何课时都在，只有"未开始 / 继续"两种状态。
    ("practice", "自主练习", "pen", "e-phrase"),
)

#: 首页六个入口（顺序固定）：跟读练习 → 听音辨意 → 音标写词 → 词形变化 → 本课检测 → 自主练习
#: 前五个入口内部包含该能力的多种练习方式；没有对应资源的入口不显示（不伪造）
HOME_ENTRIES = ("read", "listen", "phonetic", "form", "check", "practice")
#: 六排入口：名称/顺序固定；图标六个各不相同，底色三色交替（相邻必不同）
_ENTRY_META = {"read": ("跟读练习", "mic", "e-word"),
               "listen": ("听音辨意", "headphones", "e-quiz"),
               "phonetic": ("音标写词", "book", "e-phrase"),
               "form": ("词形变化", "refresh", "e-word"),
               "check": ("本课检测", "check", "e-quiz"),
               "practice": ("自主练习", "pen", "e-phrase")}
_ENTRY_HREF = {"read": "/unit/%s/vocab",
               "listen": "/unit/%s/listen?mode=word",
               "phonetic": "/unit/%s/phonetic",
               "form": "/unit/%s/form",
               "check": "/unit/%s/check",
               "practice": "/unit/%s/practice"}

#: 输入型词汇练习（数据来自 practice_v2；没有可靠资源的课时不显示）
V2_STEPS = ("phonetic", "form")
_V2_TITLES = {"phonetic": "音标写词", "form": "词形变化"}
_V2_BUILDERS = {"phonetic": practice_v2.phonetic_tasks,
                "form": practice_v2.form_tasks}

_CACHE: dict = {}


def units() -> list:
    if "units" not in _CACHE:
        _CACHE["units"] = [u for u in content_mod.list_units()
                           if (u.get("unit_code") or "").lower() != "appendix"]
    return _CACHE["units"]


def unit_slugs() -> list:
    return [u["slug"] for u in units()]


def unit_by_slug(slug: str):
    for u in units():
        if u["slug"] == slug:
            return u
    return None


# --------------------------------------------------------------------------- 只读数据
def vocab_bundle(unit: dict) -> dict:
    key = "vocab:%s" % unit["unit_code"]
    if key in _CACHE:
        return _CACHE[key]
    data = content_mod.list_unit_resources(unit["slug"], "vocabulary") or {"items": []}
    index = audio_mod.word_audio_index()
    core, extra = [], 0
    for item in data.get("items") or []:
        if not item.get("can_study"):
            extra += 1
            continue
        short = flow_mod.item_key(item["item_id"])
        entry = index.get(short) or {}
        url = entry.get("url") if entry.get("item_id") == item["item_id"] else None
        core.append({"key": short, "text": item["text"], "phonetic": item.get("phonetic"),
                     "part_of_speech": item.get("part_of_speech"),
                     "meaning": item.get("meaning"), "audio_url": url,
                     "page": item.get("page"),
                     "example": demo_content.example_for(unit["unit_code"], item["text"])})
    _CACHE[key] = {"items": core, "extra": extra}
    return _CACHE[key]


def _norm_question(row: dict, qid: str) -> dict:
    letters = "abcdef"
    options = [(letters[i], t) for i, t in enumerate(row.get("options") or [])]
    return {"id": qid, "type": row.get("type") or "选择题", "prompt": row.get("prompt") or "",
            "options": options, "answer": (row.get("answer") or "a").lower(),
            "why": row.get("why") or ""}


def questions(unit: dict) -> list:
    key = "q:%s" % unit["unit_code"]
    if key in _CACHE:
        return _CACHE[key]
    rows = [_norm_question(q, "sp%d" % i)
            for i, q in enumerate(demo_content.short_practice(unit["unit_code"]))]
    rows += [_norm_question(q, "re%d" % i)
             for i, q in enumerate(demo_content.reading_extra(unit["unit_code"]).get("questions") or [])]
    _CACHE[key] = rows
    return rows


_CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def _clean(text: str) -> str:
    text = _CTRL.sub(" ", text or "")
    text = re.sub(r"^\s*\d{1,2}\s*[.)]?\s+", "", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return text.strip()


def _first_sentence(text: str, limit: int = 120) -> str:
    m = re.search(r"^.{15,%d}?[.!?](?=\s|$)" % limit, text or "")
    return m.group(0).strip() if m else (text or "")[:limit].strip()


def blocks(unit: dict) -> list:
    key = "blocks:%s" % unit["unit_code"]
    if key in _CACHE:
        return _CACHE[key]
    out = []
    for b in reading_map.natural_blocks(unit["unit_code"]):
        out.append({"key": b["key"], "audio": b["audio"],
                    "label": reading_map.KIND_LABEL.get(b["kind"], "段落"),
                    "text": _clean(b["text"]), "audio_url": b["audio_url"],
                    "start_ms": int(b["start_ms"]), "end_ms": int(b["end_ms"]),
                    "page": int(b["page"])})
    _CACHE[key] = out
    return out


def reading_segments(unit: dict) -> list:
    """听音阅读段：**一个官方教材 MP3 = 一个阅读段**（不切音频、不做句级同步）。

    文字来自教材解析结果（content_block，已与音频做过一致性复核）；
    同一个 MP3 覆盖的多个教材页正文合并成同一段的多个小节，按教材页顺序显示。
    """
    key = "seg:%s" % unit["unit_code"]
    if key in _CACHE:
        return _CACHE[key]
    per_audio = {}
    for b in blocks(unit):
        per_audio.setdefault(b["audio"], []).append(b)
    tb_pages = content_mod.textbook_pages(content_mod.CONTENTPACK)
    out = []
    for audio_num, items in per_audio.items():
        items.sort(key=lambda x: (x["page"], x["key"]))
        parts = []
        for i in items:
            parts.append({"page": tb_pages.get(i["page"], i["page"]),
                          "label": i["label"], "text": i["text"]})
        out.append({"audio": audio_num, "audio_url": items[0]["audio_url"], "parts": parts,
                    "text": "\n\n".join(i["text"] for i in items),
                    "pages": [i["page"] for i in items],
                    "tb_pages": [p["page"] for p in parts]})
    out.sort(key=lambda s: (s["pages"][0], s["audio"]))
    _CACHE[key] = out
    return out


def listen_pool_sentences(unit: dict) -> list:
    """句子听辨素材：优先已人工核验的教材句子；其它单元用自然段的第一句（整段原声）。"""
    sents = content_mod.unit_audio_resources(unit["unit_code"]).get("sentences") or []
    out = []
    for s in sents:
        out.append({"text": _clean(s["text"]), "audio_url": s["audio_url"],
                    "start_ms": int(s["start_ms"]), "end_ms": int(s["end_ms"])})
    if out:
        return out
    for b in blocks(unit):
        out.append({"text": _first_sentence(b["text"]), "audio_url": b["audio_url"],
                    "start_ms": 0, "end_ms": 0})
    return out


def listen_questions(unit: dict, mode: str, lesson: dict = None) -> list:
    """确定性听辨题：素材与干扰项都来自同一单元的真实教材内容。"""
    key = "listen:%s:%s:%s" % (unit["unit_code"], mode, (lesson or {}).get("key") or "-")
    if key in _CACHE:
        return _CACHE[key]
    letters = "abcd"
    rows = []
    if mode == "word":
        pool = lesson_vocab(unit, lesson) if lesson else vocab_bundle(unit)["items"]
        words = [w for w in pool if w.get("audio_url") and w.get("meaning")][:LISTEN_WORD_N]
        for i, w in enumerate(words):
            others = [x["meaning"] for x in words if x["meaning"] != w["meaning"]]
            distractors = (others[i % max(len(others), 1):] + others)[:2] if others else ["—"]
            options = [w["meaning"]] + distractors[:2]
            # 位置按确定性规则轮换，避免正确答案永远在 A
            pos = i % 3
            options = options[pos:] + options[:pos]
            answer = letters[options.index(w["meaning"])]
            rows.append({"id": "w%d" % i, "prompt": w["text"], "audio_url": w["audio_url"] or "",
                         "start_ms": 0, "end_ms": 0,
                         "options": [(letters[j], t) for j, t in enumerate(options)],
                         "answer": answer, "why": "「%s」的意思是 %s。" % (w["text"], w["meaning"])})
    else:
        pool = lesson_sentences(unit, lesson) if lesson else listen_pool_sentences(unit)
        pool = [s for s in pool if s.get("start_ms") or s.get("audio_url")]
        pool = pool[:LISTEN_SENT_N]
        for i, s in enumerate(pool):
            # AI 智能干扰项：只读缓存（教材资源 + 证据校验后的结果），命中即用；
            # 没有合格缓存 → 回落到原来的"同课时其他教材句子"，不阻塞、不显示未校验结果
            ai = sentence_distractors.cached(unit["unit_code"],
                                             (lesson or {}).get("key") or "", s)
            if ai:
                options = [s["text"]] + [d["text"] for d in ai]
            else:
                others = [x["text"] for x in pool if x["text"] != s["text"]]
                distractors = (others[i % max(len(others), 1):] + others)[:2] if others else ["—"]
                options = [s["text"]] + distractors[:2]
            pos = i % len(options)
            options = options[pos:] + options[:pos]
            answer = letters[options.index(s["text"])]
            rows.append({"id": "s%d" % i, "prompt": s["text"], "audio_url": s["audio_url"],
                         "start_ms": s["start_ms"], "end_ms": s["end_ms"],
                         "options": [(letters[j], t) for j, t in enumerate(options)],
                         "answer": answer, "why": "这句话来自教材原文。"})
    _CACHE[key] = rows
    return rows


# --------------------------------------------------------------------------- 短句时间轴（只读既有资产）
# --------------------------------------------------------------------------- 课时（Lesson = 教材 section）
def _section_rows(unit: dict) -> list:
    """当前 Unit 的真实教材板块（=课时），按教材页顺序；标题就是教材上的板块名。"""
    key = "sections:%s" % unit["unit_code"]
    if key in _CACHE:
        return _CACHE[key]
    conn = content_mod._ro(content_mod.CONTENTPACK)
    try:
        rows = conn.execute(
            "SELECT s.section_id, s.section_key, s.title, s.pdf_page_start, u.unit_code, u.unit_id "
            "FROM section s JOIN unit u ON u.unit_id = s.unit_id "
            "WHERE u.unit_code=? ORDER BY s.pdf_page_start", (unit["unit_code"],)).fetchall()
    finally:
        conn.close()
    out = [{"key": r["section_key"], "title": r["title"], "pdf_start": r["pdf_page_start"]}
           for r in rows]
    _CACHE[key] = out
    return out


def section_of_page(unit: dict, pdf_page) -> dict:
    """教材页 → 课时（取"起始页 <= 本页"的最后一个板块）。"""
    if pdf_page is None:
        return None
    hit = None
    for s in _section_rows(unit):
        if s["pdf_start"] and s["pdf_start"] <= int(pdf_page):
            hit = s
        else:
            break
    return hit


def section_of_audio(unit: dict, audio_code: str) -> dict:
    """官方音频 → 课时（用音频文件名的板块名，和教材目录一致）。"""
    rows = _CACHE.setdefault("audio_sections", {})
    key = "%s:%s" % (unit["unit_code"], audio_code)
    if key in rows:
        return rows[key]
    title = None
    conn = content_mod._ro(content_mod.CONTENTPACK)
    try:
        r = conn.execute("SELECT filename FROM audio_asset WHERE audio_id LIKE ?",
                         ("%:" + audio_code,)).fetchone()
        if r:
            _unit, tail, _instr = audio_mod._filename_parts(r["filename"])
            if tail:
                title = tail.split("_")[0].strip()
    finally:
        conn.close()
    hit = None
    if title:
        for s in _section_rows(unit):
            if s["title"].lower() == title.lower():
                hit = s
                break
    rows[key] = hit
    return hit


def scope(unit: dict, lesson: dict) -> str:
    """Demo 状态键：一个课时一个作用域（Cookie 里用）。"""
    return "%s::%s" % (unit["slug"], (lesson or {}).get("key") or "-")


def _same_word(given: str, want: str) -> bool:
    """输入型答案比较：忽略大小写、首尾标点与多余空格（不做拼写纠错）。"""
    def norm(t):
        t = (t or "").strip().lower().replace("\u2019", "'")
        t = re.sub(r"[^a-z0-9' ]+", " ", t)
        return re.sub(r"\s+", " ", t).strip()
    return bool(norm(want)) and norm(given) == norm(want)


def current_lesson(state: dict, unit: dict) -> dict:
    """当前课时：Cookie 里记着就沿用，否则取第一个"有资源"的课时。"""
    rows = lessons(unit)
    if not rows:
        return {"key": "-", "title": unit["title"], "label": unit["title"], "counts": {}}
    saved = ((state.get("l") or {}).get(unit["slug"]) or "").strip()
    for r in rows:
        if r["key"] == saved:
            return r
    for r in rows:
        if any(r["counts"].values()):
            return r
    return rows[0]


def lessons(unit: dict) -> list:
    """课时列表 + 每个课时真实拥有的资源数量（能力是否显示完全由此决定）。"""
    key = "lessons:%s" % unit["unit_code"]
    if key in _CACHE:
        return _CACHE[key]
    tb_pages = content_mod.textbook_pages(content_mod.CONTENTPACK)
    per_word = {}
    for w in vocab_bundle(unit)["items"]:
        pdf = None
        for p, t in tb_pages.items():
            if t == w.get("page"):
                pdf = p
                break
        sec = section_of_page(unit, pdf)
        if sec:
            per_word.setdefault(sec["key"], []).append(w)
    per_sent = {}
    for s in sentences_of(unit):
        sec = section_of_page(unit, s.get("pdf_page")) or section_of_audio(unit, s["audio"])
        if sec:
            per_sent.setdefault(sec["key"], []).append(s)
    per_read = {}
    for b in blocks(unit):
        sec = section_of_page(unit, b["page"])
        if sec:
            per_read.setdefault(sec["key"], []).append(b)
    out = []
    for s in _section_rows(unit):
        words = per_word.get(s["key"]) or []
        sents = per_sent.get(s["key"]) or []
        reads = per_read.get(s["key"]) or []
        listen_n = len([w for w in words if w.get("audio_url")]) + len(sents)
        check_n = len(lesson_questions(unit, s))
        counts = {"vocab": len(words), "listen": listen_n, "check": check_n,
                  "sentences": len(sents), "reading": len(reads),
                  "say": 1 if (sents or reads) else 0}
        out.append({"key": s["key"], "title": s["title"],
                    "label": "%s · %s" % (unit["unit_code"], s["title"]),
                    "pdf_start": s["pdf_start"], "counts": counts})
    _CACHE[key] = out
    return out


def lesson_by_key(unit: dict, lesson_key: str) -> dict:
    for r in lessons(unit):
        if r["key"] == lesson_key:
            return r
    return {}


def lesson_options(unit: dict, current: dict) -> list:
    """选择器数据：按 Unit 分组，只列出**有资源**的真实课时（教材板块名）。"""
    out = []
    for u in units():
        got = []
        for l in lessons(u):
            if any(l["counts"].values()):
                got.append({"value": "%s@%s" % (u["slug"], l["key"]),
                            "label": "%s · %s" % (u["unit_code"], l["title"]),
                            "selected": (u["slug"] == unit["slug"]
                                         and l["key"] == (current or {}).get("key"))})
        if got:
            out.append({"unit": u, "lessons": got})
    return out


def lesson_vocab(unit: dict, lesson: dict) -> list:
    out = []
    tb_pages = content_mod.textbook_pages(content_mod.CONTENTPACK)
    for w in vocab_bundle(unit)["items"]:
        pdf = next((p for p, t in tb_pages.items() if t == w.get("page")), None)
        sec = section_of_page(unit, pdf)
        if sec and sec["key"] == (lesson or {}).get("key"):
            out.append(w)
    return out


def lesson_sentences(unit: dict, lesson: dict) -> list:
    out = []
    for s in sentences_of(unit):
        sec = section_of_page(unit, s.get("pdf_page")) or section_of_audio(unit, s["audio"])
        if sec and sec["key"] == (lesson or {}).get("key"):
            out.append(s)
    return out


def lesson_reading(unit: dict, lesson: dict) -> list:
    """当前课时的听音阅读段（只看这个板块的教材页）。"""
    segs = reading_view(unit, 0)["segments"]
    out = []
    for seg in segs:
        if any((section_of_page(unit, p) or {}).get("key") == (lesson or {}).get("key")
               for p in seg["pages"]):
            out.append(seg)
    return out


def lesson_questions(unit: dict, lesson: dict) -> list:
    """本课检测：只用这个课时真实拥有的材料出题（词汇 + 该板块教材句子）。

    - 词汇题：本课时的教材重点词（选项/干扰项都来自教材词表释义）
    - 句子题：本课时的教材句子里的词（释义来自教材词表，依据与例句就是该句）
    没有材料就不出题（该课时不显示"本课检测"）。
    """
    if not lesson or not lesson.get("key"):
        return []
    key = "check:%s:%s" % (unit["unit_code"], lesson["key"])
    if key in _CACHE:
        return _CACHE[key]
    letters = "abcd"
    words = lesson_vocab(unit, lesson)
    pool = [w for w in vocab_bundle(unit)["items"] if w.get("meaning")]
    rows = []
    for i, w in enumerate(words[:2]):
        others = [x["meaning"] for x in pool if x["meaning"] != w["meaning"]]
        options = [w["meaning"]] + (others[i:] + others)[:3]
        pos = i % 4
        options = options[pos:] + options[:pos]
        ans = letters[options.index(w["meaning"])]
        ex = w.get("example") or {}
        rows.append({
            "id": "v%d" % i, "type": "词汇", "prompt": "「%s」在这节课里是什么意思？" % w["text"],
            "options": [(letters[j], t) for j, t in enumerate(options)], "answer": ans,
            "why": "这节课的教材词表里 %s 的意思是 %s。" % (w["text"], w["meaning"]),
            "basis_label": "教材词表 · %s" % lesson["title"],
            "basis_text": "%s —— %s" % (w["text"], w["meaning"]),
                    "example_en": ex.get("sentence") or "", "example_zh": ex.get("translation") or "",
                    "example_source": ex.get("source") or "", "focus": w["text"],
                    "answer_label": practice_v2.ANSWER})
    index = 0
    for s in lesson_sentences(unit, lesson):
        if len(rows) >= 4:
            break
        picked = None
        for token in re.findall(r"[A-Za-z']+", s["text"]):
            hit = next((w for w in pool if w["text"].lower() == token.lower()), None)
            if hit:
                picked = hit
                break
        if not picked:
            continue
        others = [x["meaning"] for x in pool if x["meaning"] != picked["meaning"]]
        options = [picked["meaning"]] + (others[index:] + others)[:3]
        pos = (index + 1) % 4
        options = options[pos:] + options[:pos]
        ans = letters[options.index(picked["meaning"])]
        rows.append({
            "id": "s%d" % index, "type": "教材语言使用",
            "prompt": "教材句子「%s」里，%s 的意思是？" % (s["text"], picked["text"]),
            "options": [(letters[j], t) for j, t in enumerate(options)], "answer": ans,
            "why": "这句教材原句里的 %s 的意思是 %s。" % (picked["text"], picked["meaning"]),
            "basis_label": "教材原句 · %s" % lesson["title"], "basis_text": s["text"],
            "example_en": s["text"], "example_zh": "", "example_source": "textbook",
            "focus": picked["text"], "answer_label": practice_v2.ANSWER})
        index += 1
    # 阅读理解（合并进本课检测）：材料 + 选择题 + 简答（都能在教材里核实才加入）
    data = practice_v2.reading_tasks(unit, lesson)
    for i, item in enumerate(data["items"]):
        if item["kind"] == "choice":
            rows.append({"id": "r%d" % i, "type": item["type"], "kind": "choice",
                         "prompt": item["prompt"], "options": item["options"],
                         "answer": item["answer"], "why": item.get("basis") or "",
                         "basis_label": "教材课文", "basis_text": item.get("basis") or "",
                         "example_en": "", "example_zh": "", "example_source": "textbook",
                         "focus": "", "material": data["material"],
                         "answer_label": item.get("answer_label")})
        else:
            rows.append({"id": "rs%d" % i, "type": item["type"], "kind": "short",
                         "prompt": item["prompt"], "options": [], "answer": "",
                         "reference": item.get("reference") or "",
                         "answer_label": item.get("answer_label"),
                         "why": "", "basis_label": "教材课文", "basis_text": "",
                         "example_en": "", "example_zh": "", "example_source": "textbook",
                         "focus": "", "material": data["material"]})
    _CACHE[key] = rows
    return rows


def _norm_sentence(text: str) -> str:
    t = (text or "").lower().replace("\u2019", "'").replace("\u2018", "'")
    t = t.replace("\u201c", '"').replace("\u201d", '"')
    return re.sub(r"[^a-z0-9' ]+", " ", t).strip()


def sentence_assets() -> list:
    """38 条已对齐的教材短句（只读复用审计找回的资产，不重新制作）。

    取信顺序（重复句只保留一个权威版本）：
      1. contentpack.audio_sentence_annotation 中 VERIFIED（HUMAN）
      2. audit/P3-06_au06_verified_sentences.json（VERIFIED）
      3. audit/P3-07_preview/selected_candidates_final.json（BOUNDARY_PASS）
    """
    if "sentences" in _CACHE:
        return _CACHE["sentences"]
    out = []
    tb2pdf = {}
    conn0 = content_mod._ro(content_mod.CONTENTPACK)
    try:
        for r in conn0.execute("SELECT pdf_page, textbook_page FROM page "
                               "WHERE textbook_page IS NOT NULL"):
            tb2pdf[r["textbook_page"]] = r["pdf_page"]
    finally:
        conn0.close()

    def page_from_source(text):
        """教材句子 → 教材页(PDF)：优先文件里的 PDF 页，其次教材印刷页换算。"""
        m = re.search(r"PDF\s*p(\d+)", text or "", re.I)
        if m:
            return int(m.group(1))
        m = re.search(r"p(\d+)", text or "")
        return tb2pdf.get(int(m.group(1))) if m else None

    conn = content_mod._ro(content_mod.CONTENTPACK)
    try:
        for r in conn.execute(
                "SELECT sentence_uid, audio_id, unit, sentence_text, start_ms, end_ms, "
                "source_page, status FROM audio_sentence_annotation "
                "WHERE status='VERIFIED' AND start_ms IS NOT NULL AND end_ms IS NOT NULL "
                "ORDER BY audio_id, start_ms"):
            code = (r["audio_id"] or "").split(":")[-1].upper()
            out.append({"uid": r["sentence_uid"], "audio": code, "unit": r["unit"],
                        "text": r["sentence_text"], "start_ms": int(r["start_ms"]),
                        "end_ms": int(r["end_ms"]),
                        "audio_url": "/audio/official/%s.mp3" % code,
                        "pdf_page": page_from_source(r["source_page"]),
                        "source": "contentpack VERIFIED（人工核验）", "source_rank": 1,
                        "status": r["status"]})
    finally:
        conn.close()
    p6 = BASE / "audit" / "P3-06_au06_verified_sentences.json"
    try:
        data = json.loads(p6.read_text(encoding="utf-8"))
        for s in data.get("sentences") or []:
            code = (data.get("audio_id") or "AU06").split(":")[-1].upper()
            out.append({"uid": "P3-06:%s:%s" % (code, s.get("sentence_index")),
                        "audio": code, "unit": data.get("unit") or "Starter",
                        "text": s.get("text"), "start_ms": int(s.get("start_ms")),
                        "end_ms": int(s.get("end_ms")),
                        "audio_url": data.get("audio_url") or "/audio/official/%s.mp3" % code,
                        "pdf_page": tb2pdf.get(data.get("textbook_page")),
                        "source": "P3-06 已核验（ASR 词级时间）", "source_rank": 2,
                        "status": s.get("status") or "VERIFIED"})
    except (OSError, ValueError):
        pass
    p7 = BASE / "audit" / "P3-07_preview" / "selected_candidates_final.json"
    matched = {}
    try:
        for m in json.loads((BASE / "audit" / "P3-07_preview" / "matched_candidates.json")
                            .read_text(encoding="utf-8")):
            matched[m.get("sentence_id")] = m
    except (OSError, ValueError):
        matched = {}
    try:
        for r in json.loads(p7.read_text(encoding="utf-8")):
            code = (r.get("audio_id") or r.get("audio_file") or "").split(":")[-1].upper()
            src = matched.get(r.get("sentence_id")) or {}
            m = re.search(r"P(\d+)", str(src.get("pdf_page") or ""))
            out.append({"uid": r.get("sentence_id"), "audio": code, "unit": r.get("unit"),
                        "text": r.get("sentence_text"), "start_ms": int(r.get("final_start_ms")),
                        "end_ms": int(r.get("final_end_ms")),
                        "audio_url": "/audio/official/%s.mp3" % code,
                        "pdf_page": int(m.group(1)) if m else None,
                        "source": "P3-07 精选（边界复核）", "source_rank": 3,
                        "status": r.get("boundary_status") or "BOUNDARY_PASS"})
    except (OSError, ValueError):
        pass
    seen, uniq = set(), []
    for row in sorted(out, key=lambda r: (r["source_rank"], r["audio"], r["start_ms"])):
        if not row["text"] or row["start_ms"] is None or row["end_ms"] is None:
            continue
        key = (row["audio"], _norm_sentence(row["text"]))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(row)
    uniq.sort(key=lambda r: (r["unit"], r["audio"], r["start_ms"]))
    _CACHE["sentences"] = uniq
    return uniq


def sentences_of(unit: dict) -> list:
    return [s for s in sentence_assets() if s.get("unit") == unit["unit_code"]]


def sentence_target(unit: dict, index: int = 0) -> dict:
    rows = sentences_of(unit)
    if not rows:
        return {}
    return rows[max(0, min(index, len(rows) - 1))]


# --------------------------------------------------------------------------- 本课检测题库
def check_questions(unit: dict) -> list:
    """本课检测：6 题/单元，全部基于当前 Unit 教材内容，且**每题都有正确答案**。

    词汇题（2）：教材词表释义选择（干扰项来自同一单元真实释义）
    句型/表达题（2）：demo_content.short_practice（教材短语与句型）
    阅读理解题（2）：demo_content.reading_extra（教材课文相关的理解题）
    每题额外带：教材依据（basis_label/basis_text）与教材例句（example_en/example_zh）。
    """
    key = "check:%s" % unit["unit_code"]
    if key in _CACHE:
        return _CACHE[key]
    unit_code = unit["unit_code"]
    words = [w for w in vocab_bundle(unit)["items"] if w.get("meaning")]
    rows = []
    letters = "abcd"
    for i, w in enumerate(words[:2]):
        others = [x["meaning"] for x in words if x["meaning"] != w["meaning"]]
        distractors = (others[i:] + others)[:3]
        options = [w["meaning"]] + distractors
        pos = i % 4
        options = options[pos:] + options[:pos]
        ans = letters[options.index(w["meaning"])]
        example = w.get("example") or {}
        rows.append({
            "id": "v%d" % i, "type": "词汇", "prompt": "「%s」在这个单元里是什么意思？" % w["text"],
            "options": [(letters[j], t) for j, t in enumerate(options)], "answer": ans,
            "why": "教材词表里 %s 的意思是 %s。" % (w["text"], w["meaning"]),
            "basis_label": "教材词表", "basis_text": "%s —— %s" % (w["text"], w["meaning"]),
            "example_en": example.get("sentence") or "",
            "example_zh": example.get("translation") or "",
            "example_source": example.get("source") or "",
            "focus": w["text"]})
    for i, q in enumerate(demo_content.short_practice(unit_code)):
        row = _norm_question(q, "s%d" % i)
        row.update({"basis_label": "教材短语/句型",
                    "basis_text": q.get("why") or "",
                    "example_en": _first_sentence(q.get("why") or "", 120),
                    "example_zh": "", "example_source": "textbook",
                    "focus": (q.get("options") or ["?"])[0]})
        rows.append(row)
    extra = demo_content.reading_extra(unit_code)
    for i, q in enumerate(extra.get("questions") or []):
        row = _norm_question(q, "r%d" % i)
        row.update({"basis_label": "教材课文" if extra.get("source") == "textbook" else "本课阅读材料",
                    "basis_text": q.get("why") or "",
                    "example_en": "", "example_zh": "", "example_source": extra.get("source") or "",
                    "focus": ""})
        rows.append(row)
    _CACHE[key] = rows
    return rows


def question_explain(unit: dict, q: dict, picked: str) -> dict:
    """答错后的「AI 解释（演示）」：确定性生成，但内容必须与这道题和孩子选的答案相关。"""
    chosen = dict(q["options"]).get(picked, "（未选）")
    correct = dict(q["options"]).get(q["answer"], "")
    example = ""
    if q.get("example_en"):
        example = q["example_en"]
    elif q.get("basis_text"):
        example = _first_sentence(q["basis_text"], 120)
    lines = {
        "词汇": "这道题考的是教材词表里的词义：你选的是「%s」，题目问的是「%s」。"
                % (chosen, q.get("focus") or ""),
        "句子补全": "这道题考的是教材里的固定表达，选词要放进句子里读一遍才顺。",
        "中英转换": "这道题考的是教材原句的说法，中文意思对上了，还要看英语的表达方式是否和教材一致。",
        "细节理解": "这类题要从课文里找证据：把题干的问法和课文句子对一遍，再判断选项。",
        "主旨理解": "这类题问的是整段的意思，要抓住课文反复讲的那件事，而不是某一个词。",
    }.get(q.get("type"), "先看清题目问的是什么，再回到教材里找依据。")
    return {
        "why": "你选的是「%s」。%s" % (chosen, lines),
        "right": correct,
        "basis_label": q.get("basis_label") or "教材内容",
        "basis_text": q.get("basis_text") or "",
        "example": example,
        "advice": "如果你愿意，可以先回教材里再看一遍这句话，然后再决定要不要重新做一次。",
    }


# --------------------------------------------------------------------------- 听音阅读（时间轴同步）
def reading_view(unit: dict, index: int = 0) -> dict:
    """听音阅读：一个官方 MP3 = 一段；段内文字按 start_ms/end_ms 跟随播放。

    文字主体 = 教材结构化正文（reading_map 的自然文本块，已与官方音频校准）。
    已核验短句（P3-06 / P3-07 / contentpack VERIFIED）**不再替代整篇正文**：
    它们只用于「短句跟读」页的精细片段与时间轴，不参与本页正文装配。
    """
    key = "reading:%s" % unit["unit_code"]
    if key not in _CACHE:
        per_audio = {}
        for b in blocks(unit):
            per_audio.setdefault(b["audio"], []).append(b)
        tb_pages = content_mod.textbook_pages(content_mod.CONTENTPACK)
        segs = []
        for audio_num, items in per_audio.items():
            items.sort(key=lambda x: (x["page"], x["key"]))
            chunks = [{"text": b["text"], "start_ms": b["start_ms"], "end_ms": b["end_ms"],
                       "kind": "教材正文（自然段时间范围）"} for b in items]
            segs.append({
                "audio": audio_num, "audio_url": items[0]["audio_url"],
                "chunks": chunks,
                "granularity": chunks[0]["kind"] if chunks else "整段",
                "parts": [{"page": tb_pages.get(b["page"], b["page"]), "label": b["label"],
                           "text": b["text"]} for b in items],
                "pages": [b["page"] for b in items],
                "tb_pages": [tb_pages.get(b["page"], b["page"]) for b in items]})
        segs.sort(key=lambda s: (s["pages"][0], s["audio"]))
        _CACHE[key] = segs
    segs = _CACHE[key]
    if not segs:
        return {"segments": [], "index": 0, "segment": None}
    index = max(0, min(index, len(segs) - 1))
    return {"segments": segs, "index": index, "segment": segs[index]}


# --------------------------------------------------------------------------- AI 模拟（0 调用）
_BAND_GOOD = ("较好", "基本稳定", "需要注意")


def _focus_word(text: str, unit: dict) -> str:
    """"具体发现"要落在教材内容上：优先该单元核心词表里的词，否则用句子里最长的词。"""
    words = re.findall(r"[A-Za-z']+", text or "")
    core = {w["text"].lower() for w in vocab_bundle(unit)["items"]}
    hits = [w for w in words if w.lower() in core]
    if hits:
        return min(hits, key=len)
    return max(words, key=len) if words else "the sentence"


def demo_ai(unit: dict, text: str, attempt: int, mode: str = "speaking") -> dict:
    """确定性 AI 模拟：同一句 + 同一次数永远得到同一个结果（4~6 种场景）。"""
    seed = hashlib.sha256(("%s|%s|%d|%s" % (unit["unit_code"], text, attempt, mode))
                          .encode("utf-8")).hexdigest()
    n = int(seed[:8], 16)
    word = _focus_word(text, unit)
    if attempt >= 2:
        choices = (4, 5, 0)
    else:
        choices = (0, 1, 2, 3, 5, 1)
    scene = choices[n % len(choices)]
    if scene == 0:
        row = ("完整", "较好", "流畅",
               "整句读得完整，「%s」的重音位置还可以更自然一点。" % word,
               "如果你愿意，可以再听一遍教材原音，然后按自己的节奏读一次。")
    elif scene == 1:
        row = ("完整", "有一个词需要注意", "基本流畅",
               "「%s」这个词可以再读清楚一些。" % word,
               "如果你愿意，可以先听原音里这个词，再读一遍。")
    elif scene == 2:
        row = ("基本完整", "基本稳定", "停顿稍多",
               "句子中间停顿稍多，特别是在「%s」前后。" % word,
               "如果你愿意，可以先跟着原音读一遍整句的节奏。")
    elif scene == 3:
        row = ("有遗漏", "基本稳定", "基本流畅",
               "这一遍似乎漏掉了「%s」附近的内容。" % word,
               "如果你愿意，可以看着句子再读一次，不着急。")
    elif scene == 4:
        row = ("完整", "较好", "流畅",
               "这一遍比上一次完整，「%s」也清楚多了。" % word,
               "如果你愿意，可以保持现在的节奏再读一遍。")
    else:
        row = ("完整", "表现稳定", "流畅",
               "这一遍整体比较稳定，没有发现需要特别提醒的地方。",
               "如果你愿意，可以继续下一项，也可以再读一次。")
    return {"html": pages._ai_block("AI 朗读分析", (
        ("完整度", row[0]), ("发音表现", row[1]), ("流畅度", row[2]),
        ("具体发现", row[3]), ("建议", row[4]))),
        "completeness": row[0], "pronunciation": row[1], "fluency": row[2],
        "finding": row[3], "advice": row[4], "scene": scene}


def _stat_band(correct: int, total: int) -> str:
    if not total:
        return "还没有开始"
    rate = correct / total
    return "稳定" if rate >= 0.8 else ("基本稳定" if rate >= 0.5 else "需要注意")


# --------------------------------------------------------------------------- 课文简答
def say_task(unit: dict, lesson: dict) -> dict:
    """课文简答：题目只来自当前课时的教材句子或教材正文，不新造教材事实。"""
    sents = lesson_sentences(unit, lesson)
    src = None
    for s in sents:
        text = (s.get("text") or "").strip()
        if text.endswith("?"):
            src = {"text": text, "page": s.get("page"), "kind": "question",
                   "uid": s.get("uid")}
            break
    if not src and sents:
        text = (sents[0].get("text") or "").strip()
        src = {"text": text, "page": sents[0].get("page"), "kind": "pattern",
               "uid": sents[0].get("uid")}
    if not src:
        for seg in lesson_reading(unit, lesson):
            for row in seg.get("chunks") or []:
                for hit in re.finditer(r"[A-Z][^.!?]{12,110}[.!?]", (row.get("text") or "").strip()):
                    cand = hit.group(0).strip()
                    if len(cand) >= 20:
                        src = {"text": cand,
                               "page": (seg.get("tb_pages") or [None])[0],
                               "kind": "reading"}
                        break
                if src:
                    break
            if src:
                break
    if not src:
        return {}
    # 孩子必须一眼看懂这是哪一种任务（不是翻译、不是中文作答）
    if src["kind"] == "question":
        src["task_title"] = "用英文回答课文问题"
        src["task_label"] = "课文问题回答"
        src["ask"] = "用一句完整的英文回答这个问题。"
    else:
        src["task_title"] = "用英文写一句话"
        src["task_label"] = "教材表达迁移"
        src["ask"] = "参考教材的表达方式，写一句关于你自己的话。"
    src["ref_label"] = "参考表达"
    # 「教材说法」= 句子里的实词（去掉句首词、专有名词与常见功能词），只用于具体发现
    raw = re.findall(r"[A-Za-z']+", src["text"])
    stop = {"the", "a", "an", "is", "are", "was", "were", "do", "does", "did", "of", "to",
            "in", "on", "at", "and", "or", "for", "with", "this", "that", "these", "those",
            "we", "you", "your", "our", "it", "its", "he", "she", "they", "them", "his", "her"}
    src["words"] = [w for i, w in enumerate(raw)
                    if i > 0 and len(w) > 3 and not w[:1].isupper() and w.lower() not in stop]
    return src


def say_grading(unit: dict, task: dict, text: str, attempt: int) -> dict:
    """课文简答：批改 → 分析 → 指导。

    规则层复用正式 P2-2 模块 `web/ai_grading.analyze_short_answer`（确定性、不联网、不调用 AI）；
    语言层是**演示用的确定性模拟**——完全由孩子写的这句话与教材原句的确定性比较得出，
    同样的输入永远得到同样的结论；全部为定性描述，不出现伪精确分数，不生成教材之外的事实。
    """
    text = (text or "").strip()
    rule = ai_grading.analyze_short_answer(task.get("text") or "", text)
    words = re.findall(r"[A-Za-z']+", text)
    lower = {w.lower() for w in words}
    used, missing = [], []
    for w in task.get("words") or []:
        (used if w.lower() in lower else missing).append(w)
    complete = len(words) >= 5 and text[-1:] in ".!?"
    carries = bool(used)
    total = len(task.get("words") or [])
    coverage = (len(used) / total) if total else 0.0
    if not words:
        verdict, mark = "还没有写上一句话", "需要再想一想"
    elif carries and coverage >= 0.6 and complete:
        verdict, mark = "这句写得完整，也用上了教材里的说法。", "基本掌握"
    elif carries:
        verdict, mark = "你答到了要点，这一句还可以再补一点。", "需要巩固"
    else:
        verdict, mark = "这句话还没有用上教材里的说法。", "需要巩固"
    if attempt >= 3 and not carries:
        verdict = "这一句试了几次，还没有用上教材里的说法。"
    if attempt >= 2 and carries and coverage >= 0.6 and complete:
        mark = "掌握较稳定"
    if not carries and missing:
        advice = ("先照着教材原句写一遍，再把里面的人或事换成你自己的，"
                  "让句子用上「%s」这样的说法。" % (missing[0],))
    elif not complete or coverage < 0.6:
        advice = "你已经答到了要点，试着把原因或细节补上，让这句话更完整。"
    else:
        advice = "保持这个说法，如果你愿意，可以再用同一句说法写另一件事。"
    return {"verdict": verdict, "mark": mark, "advice": advice,
            "used": used[:3], "missing": missing[:3],
            "word_count": len(words), "complete": complete, "carries": carries,
            "coverage": round(coverage, 2),
            "hints": rule.get("hints") or [], "rule_judgement": rule.get("judgement") or "",
            "ai_status": rule.get("ai_status")}


# --------------------------------------------------------------------------- 学习证据 → 具体发现 → 专项/巩固
def _item_by_word(unit: dict, text: str):
    want = (text or "").strip().lower()
    for w in vocab_bundle(unit)["items"]:
        if (w.get("text") or "").strip().lower() == want:
            return w
    return None


def _key_word_in(unit: dict, sentence: str) -> str:
    pool = {w["text"].lower(): w["text"] for w in vocab_bundle(unit)["items"]}
    for token in re.findall(r"[A-Za-z']+", sentence or ""):
        hit = pool.get(token.lower())
        if hit:
            return hit
    words = re.findall(r"[A-Za-z']+", sentence or "")
    return max(words, key=len) if words else ""


def lesson_evidence(state: dict, unit: dict, lesson: dict) -> list:
    """当前课时**真实产生过的**学习证据 → 具体发现（没有证据就不返回）。"""
    sc = scope(unit, lesson)
    out = []
    answers = state_mod.answers(state, sc)
    for i, q in enumerate(lesson_questions(unit, lesson)):
        picked = answers.get(q["id"])
        if not picked or picked == q["answer"]:
            continue
        point = q.get("focus") or q.get("type")
        out.append({"id": "check:%s" % q["id"], "kind": "词义判断" if q["type"] == "词汇"
                    else "教材语言使用", "point": point,
                    "detail": "本课检测第 %d 题选错：%s" % (i + 1, q["prompt"][:30]),
                    "basis": q.get("basis_text") or "", "source": "本课检测",
                    "strength": "答错", "question": q,
                    "lesson_label": lesson["title"]})
    for mode, src_label in (("word", "听音辨意 · 单词听辨"), ("sentence", "听音辨意 · 句子听辨")):
        picks = state_mod.listen_answers(state, sc, mode)
        for q in listen_questions(unit, mode, lesson):
            picked = picks.get(q["id"])
            if not picked or picked == q["answer"]:
                continue
            if mode == "word":
                point = q["prompt"]
                detail = "听音辨意里这个词的辨认出错过。"
            else:
                point = _key_word_in(unit, q["prompt"])
                detail = "这一句的听力辨认出错过：%s" % q["prompt"][:40]
            out.append({"id": "listen:%s:%s" % (mode, q["id"]), "kind": "听力辨认",
                        "point": point, "detail": detail,
                        "basis": q.get("why") or "", "source": src_label,
                        "strength": "选错", "question": None,
                        "lesson_label": lesson["title"]})
    speak = state_mod.speaking(state, sc)
    sentences = lesson_sentences(unit, lesson)
    if speak["n"] and sentences and len(out) < 3:
        ai = demo_ai(unit, sentences[0]["text"], speak["n"], mode="sentence")
        out.append({"id": "speak:0", "kind": "朗读表现", "point": _key_word_in(unit, sentences[0]["text"]),
                    "detail": ai["finding"], "basis": sentences[0]["text"],
                    "source": "短句跟读（第 %d 次）" % speak["n"], "strength": "演示分析",
                    "question": None, "lesson_label": lesson["title"]})
    # Demo V2：输入型词汇练习写错 → 同样算一条真实学习证据（沿用 Cookie 证据机制）
    typed = state_mod.typed_answers(state, sc)
    for kind, tasks, key_name, src_label in (
            ("音标拼写", practice_v2.phonetic_tasks(unit, lesson), "word", "音标写词"),
            ("词形变化", practice_v2.form_tasks(unit, lesson), "base", "词形变化")):
        for t in tasks:
            got = (typed.get(t["id"]) or "").strip()
            if not got or _same_word(got, t.get(key_name) or ""):
                continue
            out.append({"id": t["id"], "kind": kind, "point": t.get(key_name) or "",
                        "detail": "%s里这个词需要再练（你写的是 %s）" % (src_label, got[:16]),
                        "basis": t.get("meaning") or t.get("prompt") or "",
                        "source": src_label, "strength": "写错",
                        "question": None, "lesson_label": lesson["title"]})
    seen, uniq = set(), []
    for row in out:
        key = (row["kind"], str(row["point"]).lower())
        if key in seen:
            continue
        seen.add(key)
        uniq.append(row)
    return uniq[:3]


def all_lessons() -> list:
    """全局教材顺序的课时表：[(unit, lesson)]。"""
    if "all_lessons" in _CACHE:
        return _CACHE["all_lessons"]
    rows = []
    for u in units():
        for l in lessons(u):
            if any(l["counts"].values()):
                rows.append((u, l))
    _CACHE["all_lessons"] = rows
    return rows


def lesson_has_evidence(state: dict, unit: dict, lesson: dict) -> bool:
    sc = scope(unit, lesson)
    return bool(state_mod.answers(state, sc) or state_mod.listen_answers(state, sc, "word")
                or state_mod.listen_answers(state, sc, "sentence")
                or state_mod.speaking(state, sc)["n"]
                or state_mod.word_marks(state, sc))


#: 正式学习库（只读）：Demo 没有 Cookie 学习证据时，用它判断孩子已进入哪个 Unit
LEARNING_DB = content_mod.LEARNING_DB


def _unit_index(unit: dict) -> int:
    """教材顺序里的下标（Starter = 0；Appendix 不在 units() 里）。"""
    for i, u in enumerate(units()):
        if u["slug"] == unit["slug"]:
            return i
    return -1


def unit_prefix_upto(unit: dict) -> list:
    """从 Starter 到该 Unit 的**连续前缀**（Appendix 永不进入）。"""
    i = _unit_index(unit) if unit else -1
    return units()[:i + 1] if i >= 0 else units()[:1]


def _demo_progress_unit(state: dict):
    """Demo 真实学习证据（课时级）里最靠后的课时所在 Unit；没有证据返回 None。"""
    latest = None
    if state:
        for u, l in all_lessons():
            if lesson_has_evidence(state, u, l):
                latest = u
    return latest


def _formal_progress_unit():
    """正式学习记录里**能明确归属 Unit** 的练习 → 最靠后的 Unit（只读；失败按"无"处理）。

    只采用教材目录里带明确 `unit` 字段的练习（`web.exercises`）。词条级记录不参与：
    词条的 Unit 归属来自书末词表页码，不足以代表"孩子学到哪个单元"。
    """
    try:
        import sqlite3
        import exercises as exercises_mod
        conn = sqlite3.connect("file:%s?mode=ro" % Path(LEARNING_DB).as_posix(), uri=True)
        try:
            item_ids = [row[0] for row in conn.execute(
                "SELECT DISTINCT item_id FROM learning_record")]
        finally:
            conn.close()
    except Exception:                                   # noqa: BLE001 —— 读不到就按"无证据"处理
        return None
    by_code = {(u["unit_code"] or "").strip().lower(): u for u in units()}
    latest = None
    for item_id in item_ids:
        code = ((exercises_mod.get_exercise(item_id) or {}).get("unit") or "").strip().lower()
        unit = by_code.get(code)
        if unit and (latest is None or _unit_index(unit) > _unit_index(latest)):
            latest = unit
    return latest


def progress_unit(state: dict = None):
    """孩子当前学习进度所在 Unit：由真实学习证据决定，**与正在浏览的 Unit 无关**。

    证据（都只用已有数据，不新增记录）：
      1. Demo 学习证据：有真实学习行为的**课时**（course-level，课时属于某个 Unit）；
      2. 正式学习记录：教材目录里能明确归属 Unit 的**练习**记录。
    两者都取最靠后的 Unit，谁更靠后取谁；都没有证据时返回 None（不猜测）。
    """
    candidates = [u for u in (_demo_progress_unit(state), _formal_progress_unit()) if u]
    if not candidates:
        return None
    return max(candidates, key=_unit_index)


def learned_unit_prefix(state: dict = None) -> list:
    """已学教材资源范围 = **Starter + 从教材开始到当前学习进度所在 Unit** 的连续前缀。

    * Appendix 不在 `units()` 里，天然排除；
    * 浏览位置（Cookie `u` / `state["u"]`）不参与判断；
    * 没有任何学习证据时只返回 Starter（固定起点，不伪造进度）。
    """
    return unit_prefix_upto(progress_unit(state))


def studied_before(state: dict, unit: dict, lesson: dict) -> list:
    """当前课时**之前**、而且真的产生过学习记录的课时（不含未来课时）。"""
    rows = all_lessons()
    cur = next((i for i, (u, l) in enumerate(rows)
                if u["slug"] == unit["slug"] and l["key"] == lesson["key"]), None)
    if cur is None:
        return []
    out = []
    for u, l in rows[:cur]:
        if lesson_has_evidence(state, u, l):
            out.append((u, l))
    return out


def studied_lessons(state: dict, unit: dict, lesson: dict) -> list:
    """**所有真实学过**的课时（不按"当前课时之前"截断）——自主练习范围 = 全部已学内容。

    判定"学过"的唯一依据仍是真实学习记录（lesson_has_evidence），
    因此不会把没有学过的课时（哪怕排在前面的单元）拉进来。
    """
    out = []
    for u, l in all_lessons():
        if u["slug"] == unit["slug"] and l["key"] == (lesson or {}).get("key"):
            continue
        if lesson_has_evidence(state, u, l):
            out.append((u, l))
    return out


def _practice_question(unit: dict, row: dict, qid: str) -> dict:
    """把一条"发现"变成一道可做的练习：优先复用原题，其次用教材词表出词义题。"""
    letters = "abcd"
    if row.get("question"):
        q = dict(row["question"])
        return {"id": qid, "type": q["type"], "prompt": q["prompt"], "options": q["options"],
                "answer": q["answer"], "why": q.get("why") or "",
                "basis_label": q.get("basis_label") or "教材内容",
                "basis_text": q.get("basis_text") or "", "point": row.get("point") or ""}
    word = _item_by_word(unit, row.get("point") or "")
    if not word:
        return None
    pool = [w for w in vocab_bundle(unit)["items"] if w.get("meaning")]
    others = [w["meaning"] for w in pool if w["meaning"] != word["meaning"]]
    options = [word["meaning"]] + others[:3]
    ans = letters[options.index(word["meaning"])]
    return {"id": qid, "type": "词汇", "prompt": "「%s」的意思是？" % word["text"],
            "options": [(letters[i], t) for i, t in enumerate(options)], "answer": ans,
            "why": "教材词表里 %s 的意思是 %s。" % (word["text"], word["meaning"]),
            "basis_label": "教材词表 · %s" % row.get("lesson_label", ""),
            "basis_text": "%s —— %s" % (word["text"], word["meaning"]),
            "point": word["text"]}


def special_practice(unit: dict, lesson: dict, finding: dict) -> list:
    """专项练习：只针对这一条具体发现（1–3 题，全部来自教材内容）。"""
    rows = []
    q = _practice_question(unit, finding, "sp0")
    if q:
        rows.append(q)
    word = _item_by_word(unit, finding.get("point") or "")
    if word:
        pool = [w for w in vocab_bundle(unit)["items"] if w.get("meaning")]
        others = [w["meaning"] for w in pool if w["meaning"] != word["meaning"]]
        options = [word["meaning"]] + others[1:4] if len(others) > 1 else [word["meaning"]] + others
        ans = "abcd"[options.index(word["meaning"])]
        rows.append({"id": "sp1", "type": "词汇", "prompt": "再确认一次：「%s」的意思是？" % word["text"],
                     "options": [("abcd"[i], t) for i, t in enumerate(options)], "answer": ans,
                     "why": "教材词表里 %s 的意思是 %s。" % (word["text"], word["meaning"]),
                     "basis_label": "教材词表", "basis_text": "%s —— %s" % (word["text"], word["meaning"]),
                     "point": word["text"]})
    return rows[:3]


def reinforce_practice(state: dict, unit: dict, lesson: dict, covered=()) -> list:
    """巩固练习：当前课时的发现 + **全部已经学过**的课时的发现（自主练习 = 全部已学内容）。

    covered = 已由正式巩固池覆盖的 (unit_slug, lesson_key)：这些课时不再重复出 Cookie 题目
    （正式池优先；只做这一层最小区重，不改任何规则）。
    """
    covered = {(c[0], c[1]) for c in (covered or ())}
    cur_key = (unit["slug"], (lesson or {}).get("key"))
    points = [] if cur_key in covered else [f for f in lesson_evidence(state, unit, lesson)]
    history = []
    for u, l in studied_lessons(state, unit, lesson):
        if (u["slug"], l["key"]) in covered:
            continue
        for f in lesson_evidence(state, u, l):
            history.append((u, f))
    if len(points) + len(history) < 2:
        return []
    rows, seen = [], set()
    for i, f in enumerate(points[:2]):
        q = _practice_question(unit, f, "rp%d" % i)
        if q and q["point"].lower() not in seen:
            seen.add(q["point"].lower())
            rows.append(q)
    for i, (u, f) in enumerate(history[:3]):
        q = _practice_question(u, f, "rh%d" % i)
        if q and q["point"].lower() not in seen:
            q["prompt"] = "%s（%s · %s）" % (q["prompt"], u["unit_code"], f["lesson_label"])
            q["basis_label"] = "%s · %s" % (q["basis_label"], f["lesson_label"])
            seen.add(q["point"].lower())
            rows.append(q)
    return rows[:5]


#: 练习页的返回目标：从首页「自主练习」进来就回自主练习；默认回 AI 随堂助教（原链路不变）。
PRACTICE_BACKS = {"tutor": ("/unit/%s/tutor", "返回 AI 随堂助教", "回到 AI 随堂助教"),
                  "practice": ("/unit/%s/practice", "返回自主练习", "回到自主练习")}


def practice_back_of(value: str) -> str:
    """链接/表单里的来源标记（b=own）→ 练习页返回目标；没有标记就是原链路。"""
    return "practice" if (value or "") == "own" else "tutor"


def practice_back_parts(slug: str, back: str) -> tuple:
    href, back_label, to_label = PRACTICE_BACKS.get(back) or PRACTICE_BACKS["tutor"]
    return href % slug, back_label, to_label


def _practice_href(url: str, back: str) -> str:
    """练习链接带上"从哪进来"：从自主练习进来，做完就回自主练习。"""
    if back != "practice":
        return url
    return url + ("&" if "?" in url else "?") + "b=own"


def ai_tutor(state: dict, unit: dict, lesson: dict, practice_back: str = "",
             covered=()) -> dict:
    """AI 随堂助教：只用**真实学习证据**做具体分析；证据不足就少说。"""
    findings = lesson_evidence(state, unit, lesson)
    history_lessons = studied_before(state, unit, lesson)
    focus, seen = [], set()
    for f in findings:
        label = _focus_label(unit, f)
        if label and label.lower() not in seen:
            seen.add(label.lower())
            focus.append(label)
    advice = _advice_for(findings[0]) if findings else ""
    special = None
    if findings:
        special = {"label": "专项练习 · %s" % (findings[0].get("point") or findings[0]["kind"]),
                   "desc": findings[0]["detail"],
                   "href": _practice_href("/unit/%s/practice/special?p=%s"
                                          % (unit["slug"], urllib.parse.quote(findings[0]["id"])),
                                          practice_back)}
    reinforce = None
    rows = reinforce_practice(state, unit, lesson, covered)
    if rows:
        names = []
        for q in rows:
            if q.get("point") and q["point"] not in names:
                names.append(q["point"])
        reinforce = {"label": "巩固练习 · 本课 + 已学内容",
                     "desc": "、".join(names[:4]),
                     "href": _practice_href("/unit/%s/practice/reinforce" % unit["slug"],
                                            practice_back)}
    return {"findings": findings, "focus": focus, "advice": advice,
            "special": special, "reinforce": reinforce,
            "history": [{"unit": u, "lesson": l, "label": "%s · %s" % (u["unit_code"], l["title"])}
                        for u, l in history_lessons[:4]],
            "has_evidence": bool(findings)}


def _focus_label(unit: dict, finding: dict) -> str:
    word = _item_by_word(unit, finding.get("point") or "")
    if word:
        pos = word.get("part_of_speech") or ""
        return "%s 的意思与用法%s" % (word["text"], ("（%s）" % pos) if pos else "")
    return str(finding.get("point") or "").strip()


def _advice_for(finding: dict) -> str:
    point = finding.get("point") or ""
    if finding["kind"] == "听力辨认":
        return "再听一次这一句的教材原声，听到「%s」时停一下，再选答案。" % point
    if finding["kind"] == "朗读表现":
        return "再听一遍教材原音，跟着读一次「%s」所在的那一句。" % point
    return "先分清「%s」的意思，再用教材里的句子读一遍确认用法。" % point


def ai_summary(state: dict, ctx: dict, title: str = "AI 学习分析") -> dict:
    """AI 随堂助教内容（只用真实学习证据；没有证据就不编结论）。"""
    t = ai_tutor(state, ctx["unit"], ctx["lesson"])
    t["html"] = pages.ai_tutor_block(t, title=title, with_practice=(title != "AI 学习分析"))
    return t


SESSIONS = ("reinforce",)


def session_questions(state: dict, unit: dict, lesson: dict, session: str) -> list:
    """按 session 重新组织练习题目（每次都从当前证据现算，保证与证据一致）。"""
    if session in SESSIONS:
        return reinforce_practice(state, unit, lesson)
    if session.startswith("special:"):
        sid = session.split(":", 1)[1]
        f = next((x for x in lesson_evidence(state, unit, lesson) if x["id"] == sid), None)
        return special_practice(unit, lesson, f) if f else []
    return []


# --------------------------------------------------------------------------- 状态 → 上下文
def _stamp() -> str:
    return datetime.datetime.now().strftime("%m-%d %H:%M")


def unit_ctx(state: dict, unit: dict, lesson: dict = None) -> dict:
    """课时上下文：状态、能力、资源全部以**当前课时**为单位。"""
    lesson = lesson or current_lesson(state, unit)
    sc = scope(unit, lesson)
    counts = lesson.get("counts") or {}
    marks = state_mod.word_marks(state, sc)
    answers = state_mod.answers(state, sc)
    typed = state_mod.typed_answers(state, sc)
    speak = state_mod.speaking(state, sc)
    done = {s: state_mod.step_done(state, sc, s) for s in state_mod.STEPS}

    listen = {}
    for mode in ("word", "sentence"):
        rows = listen_questions(unit, mode, lesson)
        picks = state_mod.listen_answers(state, sc, mode)
        correct = sum(1 for q in rows if picks.get(q["id"]) == q["answer"])
        listen[mode] = {"total": len(picks), "all": len(rows), "correct": correct,
                        "band": _stat_band(correct, len(rows)) if picks else "还没有开始"}
    if counts.get("listen") and listen["word"]["total"] and listen["sentence"]["total"] \
            and not done.get("listen"):
        state_mod.mark_step(state, sc, "listen")
        state_mod.add_minutes(state, STEP_MINUTES["listen"])

    check_rows = lesson_questions(unit, lesson)
    check = {"rows": check_rows,
             "answered": sum(1 for q in check_rows
                             if q["id"] in answers
                             or (q.get("kind") == "short" and q["id"] in typed)),
             "all": len(check_rows),
             "correct": sum(1 for q in check_rows if answers.get(q["id"]) == q["answer"]),
             "wrong": [q for q in check_rows
                       if q["id"] in answers and answers[q["id"]] != q["answer"]]}
    if check_rows and check["answered"] >= check["all"] and not done.get("check"):
        state_mod.mark_step(state, sc, "check")
        state_mod.add_minutes(state, STEP_MINUTES["check"])
    sentence_rows = lesson_sentences(unit, lesson)
    if sentence_rows and speak["n"] and not done.get("sentences"):
        state_mod.mark_step(state, sc, "sentences")
        state_mod.add_minutes(state, STEP_MINUTES["sentences"])

    started = {"vocab": bool(marks), "listen": bool(listen["word"]["total"] or listen["sentence"]["total"]),
               "check": bool(answers), "sentences": speak["n"] > 0,
               "reading": bool(done.get("reading")),
               "say": bool((state_mod.say_answer(state, sc) or {}).get("text"))}
    if started["say"] and not done.get("say"):
        state_mod.mark_step(state, sc, "say")
        state_mod.add_minutes(state, STEP_MINUTES["say"])
    caps = [k for k in ("vocab", "listen", "check", "sentences", "reading", "say")
            if counts.get(k, 0) > 0]
    # Demo V2：新增词汇/阅读练习的题量与作答状态（Cookie，作用域仍是当前课时）
    v2_counts = practice_v2.activity_counts(unit, lesson)
    v2_answered = {k: 0 for k in V2_STEPS}
    for key in typed:
        head = str(key).split(":", 1)[0]
        if head in v2_answered:
            v2_answered[head] += 1
    for key in answers:
        if str(key).startswith("readc:"):
            v2_answered["read"] += 1
    v2_started = {k: v2_answered[k] > 0 for k in v2_answered}
    v2_done = {k: bool(v2_counts.get(k)) and v2_answered[k] >= v2_counts[k]
               for k in v2_answered}
    ctx = {"unit": unit, "lesson": lesson, "scope": sc, "counts": counts, "caps": caps,
           "_state": state,                 # 首页状态提示需要读 Cookie（只读，不写回）
           "steps": state_mod.STEPS, "step_labels": state_mod.STEP_LABELS,
           "done": done, "started": started, "marks": marks, "answers": answers,
           "practiced": state_mod.has_practice(state, sc),
           "typed": typed, "v2_counts": v2_counts, "v2_started": v2_started,
           "v2_done": v2_done,
           "listen": listen, "speaking": speak, "check": check,
           "sentences": sentence_rows,
           "last_sentence": sentence_target(unit, max(0, speak["n"] - 1)) or {},
           "theme": demo_data.UNIT_THEME.get(unit["unit_code"]) or "这一课的内容"}
    ctx["entries"] = entries(ctx)
    ctx["ai"] = ai_summary(state, ctx, title="AI 随堂助教")
    ctx["lesson_options"] = lesson_options(unit, lesson)
    return ctx


def _entry_progress(step: str, ctx: dict):
    """入口进度：(已完成数, 总数)；总数 0 表示这节课没有这个资源。"""
    caps, counts = ctx["caps"], ctx["counts"]
    if step == "read":                       # 跟读练习 = 单词跟读 + 短句跟读
        total = (len(lesson_vocab(ctx["unit"], ctx["lesson"])) if "vocab" in caps else 0)
        done = len(ctx["marks"]) if "vocab" in caps else 0
        if "sentences" in caps:
            n = len(ctx["sentences"])
            total += n
            done += min(ctx["speaking"]["n"], n)
        return done, total
    if step == "listen":                     # 听音辨意 = 单词/句子听辨 + 听音阅读
        done, total = 0, 0
        if "listen" in caps:
            rows = listen_questions(ctx["unit"], "word", ctx["lesson"])
            total += len(rows)
            done += ctx["listen"]["word"]["total"]
            srows = listen_questions(ctx["unit"], "sentence", ctx["lesson"])
            total += len(srows)
            done += ctx["listen"]["sentence"]["total"]
        if "reading" in caps:
            total += 1
            done += 1 if ctx["done"].get("reading") else 0
        return done, total
    if step in V2_STEPS:
        total = int((ctx.get("v2_counts") or {}).get(step) or 0)
        if not total:
            return 0, 0
        head = {"phonetic": "phonetic:", "form": "form:"}[step]
        done = len([k for k in ctx.get("typed") or {} if str(k).startswith(head)])
        return min(done, total), total
    if step == "check":
        total = len(ctx["check"]["rows"]) if "check" in caps else 0
        return min(ctx["check"]["answered"], total), total
    return 0, 0


def _practice_pending(ctx: dict) -> int:
    """自主练习当前可以练的项目数（正式巩固池 + Cookie 证据），用于首页状态提示。"""
    try:
        formal = pool_bridge.formal_reinforce_entries()
    except Exception:                        # noqa: BLE001 —— 池读失败不影响首页
        formal = []
    try:
        cookie = reinforce_practice(ctx.get("_state") or {}, ctx["unit"], ctx["lesson"],
                                    covered=[(e["unit_slug"], e["lesson_key"]) for e in formal])
    except Exception:                        # noqa: BLE001
        cookie = []
    return len(formal) + len(cookie)


def _entry_for(step: str, ctx: dict, slug: str):
    """一条首页入口；这节课没有对应资源就返回 None（不显示空入口）。"""
    label, icon, cls = _ENTRY_META[step]
    done, total = _entry_progress(step, ctx)
    if step == "practice":                   # 自主练习：任何课时都在
        pending = _practice_pending(ctx)
        status = ("有 %d 项需要巩固" % pending) if pending else \
            ("继续" if ctx.get("practiced") else "未开始")
        return {"label": label, "icon": icon, "cls": cls, "done": False,
                "status": status, "href": _ENTRY_HREF[step] % slug}
    if not total:
        return None
    if done >= total:
        status = "已完成"
    elif done:
        status = "还有 %d 题" % (total - done)
    else:
        status = "继续" if ctx.get("practiced") else "未开始"
    return {"label": label, "icon": icon, "cls": cls, "done": done >= total,
            "status": status, "href": _ENTRY_HREF[step] % slug}


def entries(ctx: dict) -> list:
    """首页入口：固定六排（跟读练习 / 听音辨意 / 音标写词 / 词形变化 / 本课检测 / 自主练习）。"""
    slug = ctx["unit"]["slug"]
    return [e for e in (_entry_for(step, ctx, slug) for step in HOME_ENTRIES) if e]


def next_step(ctx: dict) -> str:
    for step in state_mod.STEPS:
        if not ctx["done"].get(step):
            return step
    return "result"


def result_ctx(state: dict, ctx: dict) -> dict:
    unit = ctx["unit"]
    bundle = vocab_bundle(unit)
    marks = ctx["marks"]
    check, listen = ctx["check"], ctx["listen"]
    lesson_words = lesson_vocab(unit, ctx["lesson"])
    summary_rows = []
    if "vocab" in ctx["caps"]:
        summary_rows.append(("单词跟读", ("判断过 %d / %d 个重点词" % (len(marks), len(lesson_words)))
                             if marks else "还没做"))
    if "listen" in ctx["caps"]:
        summary_rows.append(("听音辨意",
                             ("单词 %s，句子 %s"
                              % (_stat_band(listen["word"]["correct"], listen["word"]["all"]),
                                 _stat_band(listen["sentence"]["correct"],
                                            listen["sentence"]["all"])))
                             if (listen["word"]["total"] or listen["sentence"]["total"])
                             else "还没做"))
    if "check" in ctx["caps"]:
        summary_rows.append(("本课检测", ("答对 %d / %d 题" % (check["correct"], check["answered"]))
                             if check["answered"] else "还没做"))
    if "sentences" in ctx["caps"]:
        summary_rows.append(("短句跟读", ("完成 %d 句跟读" % ctx["speaking"]["n"])
                             if ctx["speaking"]["n"] else "还没做"))
    if "reading" in ctx["caps"]:
        summary_rows.append(("听音阅读", "这节课的教材文字已经听过"
                             if ctx["done"].get("reading") else "还没做"))
    if "say" in ctx["caps"]:
        saved = state_mod.say_answer(state, ctx["scope"]) or {}
        summary_rows.append(("课文简答", ("写过 %d 次" % saved["n"]) if saved.get("text")
                             else "还没做"))
    need = [w for w in lesson_words if marks.get(w["key"]) in ("fuzzy", "forgot")]
    need.sort(key=lambda w: (0 if marks.get(w["key"]) == "forgot" else 1, w["text"]))
    ctx.update({"summary_rows": summary_rows, "need_again": [w["text"] for w in need[:5]],
                "ai": ai_summary(state, ctx), "current_step": "result"})
    return ctx


# --------------------------------------------------------------------------- HTTP
class Handler(BaseHTTPRequestHandler):
    server_version = SERVICE
    protocol_version = "HTTP/1.1"

    def _html(self, text: str, code: int = 200, cookie: str = ""):
        self._send(code, text.encode("utf-8"), "text/html; charset=utf-8", cookie)

    def _json(self, payload: dict, code: int = 200, cookie: str = ""):
        self._send(code, json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8", cookie)

    def _send(self, code: int, body: bytes, ctype: str, cookie: str = ""):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if cookie:
            self.send_header("Set-Cookie", "%s=%s; Path=/; Max-Age=2592000; SameSite=Lax"
                             % (state_mod.COOKIE_NAME, cookie))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _redirect(self, location: str, cookie: str = "", code: int = 302):
        self.send_response(code)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        if cookie:
            self.send_header("Set-Cookie", "%s=%s; Path=/; Max-Age=2592000; SameSite=Lax"
                             % (state_mod.COOKIE_NAME, cookie))
        self.end_headers()

    def _state(self) -> dict:
        raw = ""
        for chunk in (self.headers.get("Cookie") or "").split(";"):
            name, _, value = chunk.strip().partition("=")
            if name == state_mod.COOKIE_NAME:
                raw = value
        self._raw_cookie = raw
        return state_mod.decode(raw)

    def _cookie_value(self, state: dict) -> str:
        value = state_mod.encode(state)
        return value if value != (self._raw_cookie or "") else ""

    # ---- 音频 / 教材页图（只读，支持 Range 206） ---------------------------
    AUDIO_MIME = {".mp3": "audio/mpeg", ".wav": "audio/wav"}

    def _audio(self, path: str):
        rel = path[len("/audio/"):]
        target = None
        if rel.startswith("official/"):
            name = rel[len("official/"):]
            if name.endswith(".mp3") and "/" not in name:
                target = audio_mod.resolve_official_audio(name[:-4], content_mod.CONTENTPACK)
        elif rel.startswith("word/"):
            name = rel[len("word/"):]
            if name.endswith(".wav") and "/" not in name:
                target = audio_mod.resolve_word_audio(name[:-4])
        if target is None:
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return
        self._send_file(target)

    def _send_file(self, path):
        try:
            size = path.stat().st_size
        except OSError:
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return
        start, end, code = 0, max(size - 1, 0), 200
        rng = (self.headers.get("Range") or "").strip()
        if rng:
            m = re.match(r"bytes=(\d*)-(\d*)$", rng)
            if m and (m.group(1) or m.group(2)):
                start = int(m.group(1)) if m.group(1) else 0
                end = min(int(m.group(2)), size - 1) if m.group(2) else size - 1
                if start > end or start >= size:
                    self.send_response(416)
                    self.send_header("Content-Range", "bytes */%d" % size)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                code = 206
        length = end - start + 1
        self.send_response(code)
        self.send_header("Content-Type",
                         self.AUDIO_MIME.get(path.suffix.lower(), "application/octet-stream"))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        if code == 206:
            self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        with open(path, "rb") as fh:
            fh.seek(start)
            remaining = length
            while remaining > 0:
                chunk = fh.read(min(1 << 16, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    # ---- 路由 -------------------------------------------------------------
    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        path, query = url.path, urllib.parse.parse_qs(url.query)
        if path.startswith("/audio/"):
            return self._audio(path)
        if path == "/health":
            return self._json({"status": "ok", "service": SERVICE,
                               "port": self.server.server_address[1]})
        if path in ("/", "/index.html"):
            return self._home()
        if path.startswith("/unit/"):
            return self._unit(path, query)
        self._html(pages.not_found_page(path), 404)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode("utf-8") if length else ""
        form = {k: v[0] for k, v in urllib.parse.parse_qs(raw).items()}
        if path == "/switch":
            return self._switch(form)
        if path == "/lesson":
            return self._switch_lesson(form)
        if path.startswith("/unit/"):
            return self._unit_post(path, form)
        self._send(404, b"not found", "text/plain; charset=utf-8")

    # ---- 首页 --------------------------------------------------------------
    def _home(self):
        state = self._state()
        slug = state_mod.current_unit(state, unit_slugs(), DEFAULT_UNIT)
        unit = unit_by_slug(slug) or units()[0]
        state_mod.set_unit(state, unit["slug"])
        state_mod.set_last(state, "/")
        lesson = current_lesson(state, unit)
        state_mod.set_lesson(state, unit["slug"], lesson.get("key") or "")
        ctx = unit_ctx(state, unit, lesson)
        ctx.update({"units": units()})
        self._html(pages.home_page(ctx), cookie=self._cookie_value(state))

    def _switch_lesson(self, form: dict):
        """切换当前课时（若跨 Unit，会一起切过去）。"""
        state = self._state()
        value = (form.get("lesson") or "").strip()
        if "@" in value:
            slug, lesson_key = value.split("@", 1)
            unit = unit_by_slug(slug)
            if unit and lesson_by_key(unit, lesson_key):
                state_mod.set_unit(state, slug)
                state_mod.set_lesson(state, slug, lesson_key)
        back = form.get("back") or "/"
        if not back.startswith("/"):
            back = "/"
        self._redirect(back, self._cookie_value(state))

    def _switch(self, form: dict):
        state = self._state()
        slug = (form.get("u") or "").strip()
        if slug in unit_slugs():
            state_mod.set_unit(state, slug)
        back = form.get("back") or "/"
        if not back.startswith("/"):
            back = "/"
        if back.startswith("/unit/") and slug:
            # 在某个 Unit 页面里切换 Unit：要留在同一个页面，只是换成新 Unit
            rest = back[len("/unit/"):]
            tail = rest.split("/", 1)[1] if "/" in rest else ""
            back = "/unit/%s%s" % (slug, ("/" + tail) if tail else "")
        self._redirect(back, self._cookie_value(state))

    # ---- Unit 路由 ---------------------------------------------------------
    def _unit(self, path, query):
        parts = [p for p in path.split("/") if p]
        slug = parts[1] if len(parts) > 1 else ""
        tail = parts[2:]
        unit = unit_by_slug(slug)
        if unit is None:
            self._html(pages.not_found_page(path), 404)
            return
        state = self._state()
        state_mod.set_unit(state, slug)
        want = (query.get("lesson") or [""])[0].strip()
        if want and lesson_by_key(unit, want):
            state_mod.set_lesson(state, slug, want)
        lesson = current_lesson(state, unit)
        ctx = unit_ctx(state, unit, lesson)

        if not tail:
            state_mod.set_last(state, "/unit/%s" % slug)
            return self._html(pages.unit_page(ctx), cookie=self._cookie_value(state))
        head = tail[0]
        if head == "continue":
            step = next_step(ctx)
            target = "/unit/%s/result" % slug if step == "result" else "/unit/%s/%s" % (slug, step)
            return self._redirect(target, self._cookie_value(state))
        if head == "vocab":
            if len(tail) > 1 and tail[1] == "result":
                return self._vocab_result(state, ctx)
            return self._vocab(state, ctx, query)
        if head == "listen":
            if len(tail) > 1 and tail[1] == "result":
                return self._listen_result(state, ctx, query)
            return self._listen(state, ctx, query)
        if head == "reading":
            segs = lesson_reading(unit, lesson)
            try:
                index = int((query.get("seg") or ["0"])[0])
            except ValueError:
                index = 0
            index = max(0, min(index, len(segs) - 1)) if segs else 0
            view = {"segments": segs, "index": index,
                    "segment": segs[index] if segs else None}
            ctx.update({"segments": view["segments"], "seg_index": view["index"],
                        "segment": view["segment"], "units": units()})
            state_mod.set_last(state, "/unit/%s/reading" % slug)
            return self._html(pages.reading_page(ctx), cookie=self._cookie_value(state))
        if head == "check":
            if len(tail) > 1 and tail[1] == "wrong":
                return self._check_wrong(state, ctx)
            return self._check(state, ctx, query)
        if head == "sentences":
            return self._sentences(state, ctx, query)
        if head == "say":
            return self._say(state, ctx, query)
        if head in _V2_BUILDERS:                 # Demo V2：音标写词 / 词形变化
            return self._typed(state, ctx, query, head)
        if head == "practice":
            if len(tail) > 1 and tail[1] in ("special", "reinforce"):
                return self._practice_session(state, ctx, query, tail[1])
            if len(tail) > 1 and tail[1] == "result":
                return self._practice_result(state, ctx, query)
            if len(tail) > 1:
                return self._redirect("/unit/%s/practice" % slug, self._cookie_value(state))
            # 自主练习：简短学习总结 + 专项 / 巩固练习（孩子自己选）；不调用任何 AI API
            state_mod.set_last(state, "/unit/%s/practice" % slug)
            # 巩固来源 = 正式巩固池（只读，优先） + 原有 Cookie 证据（并存）
            try:
                formal = pool_bridge.formal_reinforce_entries()
            except Exception as exc:          # noqa: BLE001 —— 没有池数据也照常跑
                print("[demo] 正式巩固池读取失败：%r" % (exc,))
                formal = []
            ctx["formal_practice"] = formal
            ctx["ai"] = ai_tutor(state, ctx["unit"], ctx["lesson"], practice_back="practice",
                                 covered=[(e["unit_slug"], e["lesson_key"]) for e in formal])
            return self._html(pages.practice_page(ctx), cookie=self._cookie_value(state))
        if head == "speaking":          # 旧入口兼容：口语 → 短句跟读
            return self._redirect("/unit/%s/sentences" % slug, self._cookie_value(state))
        if head == "result":
            state_mod.set_last(state, "/unit/%s/result" % slug)
            return self._html(pages.result_page(result_ctx(state, ctx)),
                              cookie=self._cookie_value(state))
        if head == "tutor":
            state_mod.set_last(state, "/unit/%s/tutor" % slug)
            ctx["ai"] = ai_summary(state, ctx, title="AI 随堂助教")
            return self._html(pages.tutor_page(ctx), cookie=self._cookie_value(state))
        self._html(pages.not_found_page(path), 404)

    # ---- 词汇 --------------------------------------------------------------
    def _vocab(self, state, ctx, query):
        unit, slug = ctx["unit"], ctx["unit"]["slug"]
        items = lesson_vocab(unit, ctx["lesson"])
        if not items:
            return self._redirect("/unit/%s" % slug, self._cookie_value(state))
        try:
            index = int((query.get("i") or ["0"])[0])
        except ValueError:
            index = 0
        index = max(0, min(index, len(items) - 1)) if items else 0
        ctx.update({"index": index, "total": len(items), "words": items,
                    "word": items[index] if items else {}})
        state_mod.set_last(state, "/unit/%s/vocab" % slug)
        self._html(pages.vocab_page(ctx), cookie=self._cookie_value(state))

    def _vocab_result(self, state, ctx):
        # 单词跟读已经是纯练习页面，不再有"记忆判断/结果"这一类页面
        slug = ctx["unit"]["slug"]
        self._redirect("/unit/%s/vocab" % slug, self._cookie_value(state))

    # ---- 听音辨意 ----------------------------------------------------------
    def _listen(self, state, ctx, query):
        unit, slug = ctx["unit"], ctx["unit"]["slug"]
        mode = (query.get("mode") or ["word"])[0]
        if mode not in ("word", "sentence"):
            mode = "word"
        rows = listen_questions(unit, mode, ctx["lesson"])
        if not rows:
            self._html(pages.error_page("这一课还没有听辨素材", "可以先去教材阅读看看。",
                                        "/unit/%s" % slug), 200)
            return
        picks = state_mod.listen_answers(state, ctx["scope"], mode)
        first_unanswered = next((i for i, q in enumerate(rows) if q["id"] not in picks),
                                len(rows) - 1)
        try:
            index = int((query.get("i") or [str(first_unanswered)])[0])
        except ValueError:
            index = first_unanswered
        index = max(0, min(index, len(rows) - 1))
        q = rows[index]
        feedback, picked = False, ""
        if (query.get("fb") or ["0"])[0] in ("1", "true") and picks.get(q["id"]):
            feedback, picked = True, picks[q["id"]]
        is_last = index == len(rows) - 1
        next_href = ("/unit/%s/listen/result?mode=%s" % (slug, mode)) if (feedback and is_last) \
            else ("/unit/%s/listen?mode=%s&i=%d" % (slug, mode, min(index + 1, len(rows) - 1)))
        ctx.update({"mode": mode, "questions": rows, "index": index, "total": len(rows),
                    "question": q, "feedback": feedback, "picked": picked,
                    "next_href": next_href, "is_last": is_last,
                    "error": "先选一个答案。" if (query.get("err") or ["0"])[0] == "1" else ""})
        state_mod.set_last(state, "/unit/%s/listen" % slug)
        self._html(pages.listen_page(ctx), cookie=self._cookie_value(state))

    def _listen_result(self, state, ctx, query):
        unit, slug = ctx["unit"], ctx["unit"]["slug"]
        ctx = unit_ctx(state, unit, ctx["lesson"])
        ctx["ai"] = ai_summary(state, ctx)
        state_mod.set_last(state, "/unit/%s/listen/result" % slug)
        self._html(pages.listen_result_page(ctx), cookie=self._cookie_value(state))

    # ---- 练习 --------------------------------------------------------------
    # ---- 本课检测 ----------------------------------------------------------
    def _check(self, state, ctx, query):
        unit, slug = ctx["unit"], ctx["unit"]["slug"]
        rows = lesson_questions(unit, ctx["lesson"])
        if not rows:
            self._html(pages.error_page("这一课还没有检测题", "可以先去听音阅读看看。",
                                        "/unit/%s" % slug), 200)
            return
        answers = ctx["answers"]
        first_unanswered = next((i for i, q in enumerate(rows) if q["id"] not in answers),
                                len(rows) - 1)
        try:
            index = int((query.get("i") or [str(first_unanswered)])[0])
        except ValueError:
            index = first_unanswered
        index = max(0, min(index, len(rows) - 1))
        q = rows[index]
        picked = answers.get(q["id"], "")
        is_open = q.get("kind") == "short"
        if is_open:                       # 阅读简答：看输入框里的文本
            picked = (ctx["typed"].get(q["id"]) or "")
        feedback = bool(picked) and (query.get("fb") or ["0"])[0] in ("1", "true")
        is_last = index == len(rows) - 1
        next_href = ("/unit/%s/result" % slug) if (feedback and is_last) \
            else ("/unit/%s/check?i=%d" % (slug, min(index + 1, len(rows) - 1)))
        ctx.update({"questions": rows, "index": index, "total": len(rows), "question": q,
                    "feedback": feedback, "picked": picked, "next_href": next_href,
                    "is_last": is_last,
                    "partial": ctx["check"]["answered"] and ctx["check"]["answered"] < len(rows),
                    "open_answer": is_open,
                    "correct": bool(feedback and not is_open and picked == q["answer"]),
                    "explain": question_explain(unit, q, picked)
                    if (feedback and not is_open and picked != q["answer"]) else {},
                    "error": "先选一个答案。" if (query.get("err") or ["0"])[0] == "1" else ""})
        state_mod.set_last(state, "/unit/%s/check" % slug)
        self._html(pages.check_page(ctx), cookie=self._cookie_value(state))

    def _check_feedback(self, state, ctx, index, picked, text=""):
        unit, slug = ctx["unit"], ctx["unit"]["slug"]
        rows = lesson_questions(unit, ctx["lesson"])
        index = max(0, min(index, len(rows) - 1))
        q = rows[index]
        sc = ctx["scope"]
        if q.get("kind") == "short":          # 阅读简答：记文本，不判对错
            text = (text or "").strip()
            if not text:
                return self._redirect("/unit/%s/check?i=%d&err=1" % (slug, index),
                                      self._cookie_value(state))
            state_mod.note_typed(state, sc, q["id"], text)
        else:
            if picked not in [letter for letter, _ in q["options"]]:
                return self._redirect("/unit/%s/check?i=%d&err=1" % (slug, index),
                                      self._cookie_value(state))
            state_mod.note_answer(state, sc, q["id"], picked)
        fresh = unit_ctx(state, ctx["unit"], ctx["lesson"])
        if all(r["id"] in fresh["answers"] or r["id"] in (fresh.get("typed") or {})
               for r in rows) \
                and not state_mod.step_done(state, sc, "check"):
            state_mod.mark_step(state, sc, "check")
            state_mod.add_minutes(state, STEP_MINUTES["check"])
        state_mod.touch(state, _stamp())
        state_mod.set_last(state, "/unit/%s/check" % slug)
        self._redirect("/unit/%s/check?i=%d&fb=1" % (slug, index), self._cookie_value(state))

    def _check_wrong(self, state, ctx):
        """本课错题：原题 / 我的答案 / 正确答案 / 为什么错 / 教材依据 / 例句 / 再做一次。"""
        unit, slug = ctx["unit"], ctx["unit"]["slug"]
        rows = lesson_questions(unit, ctx["lesson"])
        answers = ctx["answers"]
        items = []
        for i, q in enumerate(rows):
            picked = answers.get(q["id"])
            if picked and picked != q["answer"]:
                items.append({"index": i, "q": q, "picked": picked,
                              "picked_text": dict(q["options"]).get(picked, ""),
                              "answer_text": dict(q["options"]).get(q["answer"], ""),
                              "explain": question_explain(unit, q, picked)})
        ctx.update({"wrong_items": items, "total": len(rows)})
        state_mod.set_last(state, "/unit/%s/check/wrong" % slug)
        self._html(pages.check_wrong_page(ctx), cookie=self._cookie_value(state))

    # ---- 专项 / 巩固练习（只从真实学习证据进入） ---------------------------
    def _practice_session(self, state, ctx, query, kind):
        unit, slug, lesson = ctx["unit"], ctx["unit"]["slug"], ctx["lesson"]
        back = practice_back_of((query.get("b") or [""])[0])
        back_href, back_label, back_to = practice_back_parts(slug, back)
        session = ("special:" + (query.get("p") or [""])[0]) if kind == "special" else "reinforce"
        rows = session_questions(state, unit, lesson, session)
        if not rows:
            return self._redirect(back_href, self._cookie_value(state))
        answers = state_mod.practice_answers(state, ctx["scope"], session)
        first = next((i for i, q in enumerate(rows) if q["id"] not in answers), len(rows) - 1)
        try:
            index = int((query.get("i") or [str(first)])[0])
        except ValueError:
            index = first
        index = max(0, min(index, len(rows) - 1))
        q = rows[index]
        picked = answers.get(q["id"], "")
        feedback = bool(picked) and (query.get("fb") or ["0"])[0] in ("1", "true")
        is_last = index == len(rows) - 1
        ctx.update({"kind": kind, "session": session, "questions": rows, "index": index,
                    "total": len(rows), "question": q, "feedback": feedback, "picked": picked,
                    "correct": bool(feedback and picked == q["answer"]),
                    "is_last": is_last, "back": back,
                    "back_href": back_href, "back_label": back_label, "back_to": back_to,
                    "next_href": _practice_href(
                        ("/unit/%s/practice/result?s=%s" % (slug, urllib.parse.quote(session)))
                        if (feedback and is_last)
                        else ("/unit/%s/practice/%s?%s&i=%d"
                              % (slug, kind,
                                 ("p=%s" % urllib.parse.quote(session.split(":", 1)[1]))
                                 if kind == "special" else "s=1",
                                 min(index + 1, len(rows) - 1))), back)})
        state_mod.set_last(state, "/unit/%s/practice/%s" % (slug, kind))
        self._html(pages.practice_session_page(ctx), cookie=self._cookie_value(state))

    def _practice_answer(self, state, ctx, form):
        unit, slug = ctx["unit"], ctx["unit"]["slug"]
        back = practice_back_of(form.get("b"))
        session = (form.get("s") or "").strip()
        rows = session_questions(state, unit, ctx["lesson"], session)
        if not rows:
            return self._redirect(practice_back_parts(slug, back)[0], self._cookie_value(state))
        try:
            index = int(form.get("i") or 0)
        except ValueError:
            index = 0
        index = max(0, min(index, len(rows) - 1))
        picked = (form.get("opt") or "").strip().lower()
        if picked not in [letter for letter, _ in rows[index]["options"]]:
            return self._redirect(
                _practice_href("/unit/%s/practice/%s?%s&i=%d&err=1"
                               % (slug, "reinforce" if session in SESSIONS else "special",
                                  ("s=1" if session in SESSIONS
                                   else "p=%s" % urllib.parse.quote(session.split(":", 1)[1])),
                                  index), back), self._cookie_value(state))
        state_mod.note_practice(state, ctx["scope"], session, rows[index]["id"], picked)
        state_mod.touch(state, _stamp())
        kind = "reinforce" if session in SESSIONS else "special"
        suffix = "s=1" if session in SESSIONS else "p=%s" % urllib.parse.quote(session.split(":", 1)[1])
        return self._redirect(_practice_href("/unit/%s/practice/%s?%s&i=%d&fb=1"
                                             % (slug, kind, suffix, index), back),
                              self._cookie_value(state))

    def _practice_result(self, state, ctx, query):
        unit, slug = ctx["unit"], ctx["unit"]["slug"]
        back = practice_back_of((query.get("b") or [""])[0])
        back_href, back_label, back_to = practice_back_parts(slug, back)
        session = (query.get("s") or ["reinforce"])[0]
        rows = session_questions(state, unit, ctx["lesson"], session)
        answers = state_mod.practice_answers(state, ctx["scope"], session)
        table = [{"prompt": q["prompt"], "point": q.get("point") or "",
                  "correct": answers.get(q["id"]) == q["answer"],
                  "answered": q["id"] in answers} for q in rows]
        ctx.update({"rows": table, "total": len(rows),
                    "correct": sum(1 for r in table if r["correct"]),
                    "kind": "reinforce" if session in SESSIONS else "special",
                    "back": back, "back_href": back_href, "back_label": back_label,
                    "back_to": back_to})
        state_mod.set_last(state, "/unit/%s/practice/result" % slug)
        self._html(pages.practice_result_page(ctx), cookie=self._cookie_value(state))

    # ---- Demo V2：输入型词汇练习（音标写词 / 词形变化） ---------------------
    def _typed(self, state, ctx, query, kind):
        unit, slug, lesson = ctx["unit"], ctx["unit"]["slug"], ctx["lesson"]
        tasks = _V2_BUILDERS[kind](unit, lesson)
        if not tasks:
            return self._redirect("/unit/%s" % slug, self._cookie_value(state))
        try:
            index = int((query.get("i") or ["0"])[0])
        except ValueError:
            index = 0
        index = max(0, min(index, len(tasks) - 1))
        task = tasks[index]
        answer = (ctx["typed"].get(task["id"]) or "").strip()
        feedback = bool(answer) and (query.get("fb") or ["0"])[0] == "1"
        answer_text = task.get("form") or task.get("word") or ""
        ctx.update({"kind": kind, "title": _V2_TITLES[kind], "tasks": tasks, "index": index,
                    "total": len(tasks), "task": task, "answer": answer,
                    "feedback": feedback,
                    "correct": bool(feedback and _same_word(answer, answer_text)),
                    "answer_text": answer_text, "answer_label": practice_v2.ANSWER,
                    "is_last": index == len(tasks) - 1,
                    "next_href": ("/unit/%s/%s?i=%d" % (slug, kind, index + 1))
                    if index < len(tasks) - 1 else ("/unit/%s/result" % slug)})
        state_mod.set_last(state, "/unit/%s/%s" % (slug, kind))
        self._html(pages.typed_page(ctx), cookie=self._cookie_value(state))

    def _typed_submit(self, state, ctx, form, kind):
        unit, slug, lesson = ctx["unit"], ctx["unit"]["slug"], ctx["lesson"]
        tasks = _V2_BUILDERS[kind](unit, lesson)
        if not tasks:
            return self._redirect("/unit/%s" % slug, self._cookie_value(state))
        try:
            index = int(form.get("i") or 0)
        except ValueError:
            index = 0
        index = max(0, min(index, len(tasks) - 1))
        text = (form.get("text") or "").strip()
        if text:
            state_mod.note_typed(state, ctx["scope"], tasks[index]["id"], text)
            state_mod.touch(state, _stamp())
        state_mod.set_last(state, "/unit/%s/%s" % (slug, kind))
        return self._redirect("/unit/%s/%s?i=%d&fb=1" % (slug, kind, index),
                              self._cookie_value(state))

    # ---- 短句跟读 ----------------------------------------------------------
    def _sentences(self, state, ctx, query):
        unit, slug = ctx["unit"], ctx["unit"]["slug"]
        rows = lesson_sentences(unit, ctx["lesson"])
        if not rows:
            ctx.update({"sentences": [], "sentence": None, "index": 0, "total": 0})
            state_mod.set_last(state, "/unit/%s/sentences" % slug)
            self._html(pages.sentences_page(ctx), cookie=self._cookie_value(state))
            return
        try:
            index = int((query.get("i") or ["0"])[0])
        except ValueError:
            index = 0
        index = max(0, min(index, len(rows) - 1))
        target = rows[index]
        attempts = ctx["speaking"]["n"]
        ctx.update({"sentences": rows, "sentence": target, "index": index, "total": len(rows),
                    "sentence_ai": [demo_ai(unit, s["text"], attempts, mode="sentence")
                                    for s in rows],
                    "show_demo": (query.get("done") or ["0"])[0] in ("1", "true")})
        state_mod.set_last(state, "/unit/%s/sentences" % slug)
        self._html(pages.sentences_page(ctx), cookie=self._cookie_value(state))

    # ---- 课文简答 ----------------------------------------------------------
    def _say(self, state, ctx, query):
        """课文简答：教材句 → 孩子写一句 → 批改 / 分析 / 指导 → 孩子决定是否再写一版。"""
        unit, slug = ctx["unit"], ctx["unit"]["slug"]
        task = say_task(unit, ctx["lesson"])
        if not task:
            self._html(pages.error_page("这一课还没有可以做简答的教材内容",
                                        "可以先去听音阅读看看。", "/unit/%s" % slug), 200)
            return
        saved = state_mod.say_answer(state, ctx["scope"]) or {}
        answer, attempt = (saved.get("text") or "").strip(), int(saved.get("n") or 0)
        feedback = (query.get("fb") or [""])[0] == "1" and bool(answer)
        ctx.update({"task": task, "answer": answer, "attempt": attempt,
                    "feedback": feedback,
                    "grading": say_grading(unit, task, answer, attempt) if feedback else {},
                    "units": units()})
        state_mod.set_last(state, "/unit/%s/say" % slug)
        self._html(pages.say_page(ctx), cookie=self._cookie_value(state))

    # ---- 学习动作（POST） ---------------------------------------------------
    def _unit_post(self, path, form):
        parts = [p for p in path.split("/") if p]
        slug = parts[1] if len(parts) > 1 else ""
        tail = parts[2:]
        unit = unit_by_slug(slug)
        if unit is None:
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return
        state = self._state()
        lesson = current_lesson(state, unit)
        ctx = unit_ctx(state, unit, lesson)
        sc = ctx["scope"]
        if tail[:2] == ["vocab", "judge"]:       # 单词跟读已改为纯跟读：旧动作直接回到页面
            return self._redirect("/unit/%s/vocab" % slug, self._cookie_value(state))
        if tail[:2] == ["listen", "answer"]:
            mode = (form.get("mode") or "word").strip()
            if mode not in ("word", "sentence"):
                mode = "word"
            rows = listen_questions(unit, mode, lesson)
            try:
                index = int(form.get("i") or 0)
            except ValueError:
                index = 0
            index = max(0, min(index, len(rows) - 1))
            picked = (form.get("pick") or "").strip().lower()
            if rows and picked in [letter for letter, _ in rows[index]["options"]]:
                state_mod.note_listen(state, sc, mode, rows[index]["id"], picked)
                state_mod.touch(state, _stamp())
            else:
                return self._redirect("/unit/%s/listen?mode=%s&i=%d&err=1" % (slug, mode, index),
                                      self._cookie_value(state))
            state_mod.set_last(state, "/unit/%s/listen" % slug)
            return self._redirect("/unit/%s/listen?mode=%s&i=%d&fb=1" % (slug, mode, index),
                                  self._cookie_value(state))
        if tail[:2] == ["reading", "done"]:
            if not state_mod.step_done(state, sc, "reading"):
                state_mod.mark_step(state, sc, "reading")
                state_mod.add_minutes(state, STEP_MINUTES["reading"])
            state_mod.touch(state, _stamp())
            state_mod.set_last(state, "/unit/%s/reading" % slug)
            return self._redirect("/unit/%s/check" % slug, self._cookie_value(state))
        if tail[:2] == ["check", "answer"]:
            try:
                index = int(form.get("i") or 0)
            except ValueError:
                index = 0
            return self._check_feedback(state, ctx, index,
                                        (form.get("opt") or "").strip().lower(),
                                        text=(form.get("text") or ""))
        if tail[:2] == ["check", "retry"]:
            qid = (form.get("qid") or "").strip()
            index = 0
            for i, q in enumerate(lesson_questions(unit, lesson)):
                if q["id"] == qid:
                    index = i
                    break
            if qid:
                state_mod.clear_answer(state, sc, qid)
            state_mod.touch(state, _stamp())
            return self._redirect("/unit/%s/check?i=%d" % (slug, index),
                                  self._cookie_value(state))
        if tail[:2] == ["sentences", "done"]:
            try:
                index = int(form.get("i") or 0)
            except ValueError:
                index = 0
            state_mod.note_speaking(state, sc, _stamp())
            if not state_mod.step_done(state, sc, "sentences"):
                state_mod.mark_step(state, sc, "sentences")
                state_mod.add_minutes(state, STEP_MINUTES["sentences"])
            state_mod.touch(state, _stamp())
            return self._redirect("/unit/%s/sentences?i=%d&done=1" % (slug, index),
                                  self._cookie_value(state))
        if tail[:2] == ["say", "submit"]:
            text = (form.get("text") or "").strip()
            if text:
                state_mod.note_say(state, sc, text)
                state_mod.touch(state, _stamp())
                # Spike：模拟 AI 评价 → 正式 LearningRecord（映射不到真实教材 item 就不写）
                task = say_task(unit, lesson)
                if task:
                    try:
                        attempt = int((state_mod.say_answer(state, sc) or {}).get("n") or 0)
                        say_evidence.record_say(unit, task,
                                                say_grading(unit, task, text, attempt))
                    except Exception as exc:      # noqa: BLE001 —— 写记录失败不打断学习页
                        print("[demo] 课文简答写学习记录失败：%r" % (exc,))
            state_mod.set_last(state, "/unit/%s/say" % slug)
            return self._redirect("/unit/%s/say?fb=1" % slug, self._cookie_value(state))
        if tail[:2] in (["phonetic", "submit"], ["form", "submit"]):
            return self._typed_submit(state, ctx, form, tail[0])
        if tail[:2] == ["practice", "answer"]:      # 旧入口兼容
            return self._practice_answer(state, ctx, form)
        if tail[:2] == ["speaking", "done"]:         # 旧入口兼容
            return self._redirect("/unit/%s/sentences" % slug, self._cookie_value(state))
        self._send(404, b"not found", "text/plain; charset=utf-8")

    def log_message(self, fmt, *args):
        return

    def handle_one_request(self):
        try:
            super().handle_one_request()
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            self.close_connection = True


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="智学英语全功能交互 Demo（只读 Demo）")
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = ap.parse_args()
    if not content_mod.CONTENTPACK.exists():
        print("STOP: contentpack v5 不存在：", content_mod.CONTENTPACK)
        return 2
    print("智学英语全功能交互 Demo（独立 Demo，只读正式数据，AI 调用 = 0）")
    print("  contentpack :", content_mod.CONTENTPACK, "（只读）")
    print("  教材音频    :", "官方 MP3（只读，不切割、不重新生成）")
    print("  单元        :", "、".join(u["unit_code"] for u in units()))
    print("  电脑访问    : http://127.0.0.1:%d/" % args.port)
    if args.host not in ("127.0.0.1", "localhost"):
        print("  局域网访问  : http://<本机IPv4>:%d/  （注意：局域网地址下浏览器不允许使用麦克风）"
              % args.port)
    print("  健康检查    : /health    停止：Ctrl+C")
    with ThreadingHTTPServer((args.host, args.port), Handler) as srv:
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("已停止")
    return 0


if __name__ == "__main__":
    sys.exit(main())
