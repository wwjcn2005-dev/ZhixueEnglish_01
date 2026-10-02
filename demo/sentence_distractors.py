#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""句子听辨：AI 智能干扰项（教材资源理解 → 语义组合 → 规则校验 → 缓存复用）

链路（与项目既有 AI 能力口径一致：不做实时调用、只读正式资源、确定性可复现）：

    教材句子（教材原声 + 原文 + 页/块 evidence）
      → AI 资源理解：这句用到的教材词汇 / 短语 / 句型（learning_item + source_ref + evidence map）
      → AI 语义组合：生成"像正确答案、但确实错误"的候选
            A 同单元最容易混的教材原句（按实词重合度挑）
            B 用教材词汇替换原句某一个实词得到的近似句（同词性、不同义、教材里出现过）
      → 确定性校验（重复 / 空值 / 异常文本 / 证据边界 / 错误性 / 阶段适配 / 置信度）
      → 结构化结果 + 证据 + confidence + reason
      → 缓存（按 教材版本 + 单元/课时 + 句子 + prompt/rules 版本 生成稳定键）

边界：
  * 只读：contentpack、structured/ai、教材句子资产一律只读；本模块不写正式数据库；
  * 不实时调用：`cached()` 只读缓存；生成只在显式运行（CLI）时进行；
  * 正确答案不由本模块改写；distractors 只是候选，必须通过校验才会被 `cached()` 返回；
  * 演示口径：AI 部分为**确定性模拟**（不联网、0 真实 API 调用），与项目其他 Demo AI 一致；
    真实模型接入时只需替换 `candidates_for()` 这一层，校验 / 缓存 / 消费接口不变。
"""

from __future__ import annotations

import os

import hashlib
import json
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

BASE = Path(os.environ.get("ZX_ROOT") or r"D:\ZhixueEnglish")
for _p in (str(BASE / "demo"), str(BASE / "web")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
sys.dont_write_bytecode = True

CONTENTPACK = BASE / "structured" / "contentpack" / "v5" / "FLTRP-EN-7A-2022CUR.sqlite"
EVIDENCE_MAP = BASE / "structured" / "ai" / "textbook_evidence_map_v1.json"
TEXTBOOK_ID = "FLTRP-EN-7A-2022CUR"

PROMPT_VERSION = "sentence-distractor-v1"
RULES_VERSION = "rules-v3"          # rules-v3：修复当前 Unit 教材资源边界（条目分词 / 词形与撇号归一化）
MODEL = "deterministic-textbook-composer"          # 确定性模拟 AI（0 真实调用）
CACHE_FILE = Path(__file__).resolve().parent / "ai_cache" / "sentence_distractors.json"

MAX_DISTRACTORS = 3                                 # 有多少合格就用多少（1–3，不固定）
MIN_CONFIDENCE = 0.6
MAX_TEXT_CHARS = 120
#: "正确句 + 追加"允许的追加词数上限（超过就不算"少量追加"）
MAX_APPEND_WORDS = 3

#: 真实 AI 调用器（与项目既有 AI 管线同一口径：DeepSeek 端点 + Codex 配置的 key）。
#: 默认 None → 仍然使用下面的确定性模拟（Demo 页面默认行为不变）；
#: Spike / 离线生成时显式注入调用器即可走真实 AI，其余环节（校验/缓存/消费）完全不变。
AI_CALLER = None

AI_SYSTEM_PROMPT = (
    "你是初中英语（外研版 七年级上册）句子听辨题的干扰项设计助手。\n"
    "严格规则：\n"
    "1. 只允许使用我给你的教材资源（教材句子 / 教材词汇 / 短语 / 句型及其 evidence id），"
    "不得引入教材以外的知识、词汇或事实。\n"
    "2. 给定句子是正确答案（孩子听到的教材原声）；你要为它设计 0–3 个干扰项："
    "语义或听觉上与正确答案接近、容易混淆，但明确错误。\n"
    "3. 干扰项的长度、格式、复杂程度要与正确答案接近，不能一眼排除，也不能超纲。\n"
    "4. 每个干扰项必须写出来源 evidence_ids（只能取自我给的清单）；"
    "证据不足就少给甚至给 0 个，不要凑数。\n"
    "5. 禁止把「正确答案 + 句首/句尾少量词」当作主要干扰项做法（例如在正确句末尾加 here / for you、"
    "在开头加一个称呼），这类只做长度堆叠的选项会被过滤。\n"
    "6. 优先使用：教材词汇替换、教材句子中的成分替换、同 Unit 里容易混淆的教材表达、"
    "与原句结构相近但关键信息不同的表达。\n"
    "7. 只输出严格 JSON，不要解释、不要 Markdown：\n"
    '{"items":[{"sentence_index":0,"distractors":[{"text":"...","confidence":0.0,'
    '"reason":"...","evidence_ids":["..."]}]}]}\n'
)


#: 教材里本来就有、可作功能词的常见虚词（不参与"实词替换"）
FUNCTION_WORDS = frozenset({
    "a", "an", "the", "is", "are", "am", "was", "were", "be", "do", "does", "did", "of", "to",
    "in", "on", "at", "and", "or", "for", "with", "but", "so", "as", "it", "its", "i", "you",
    "he", "she", "we", "they", "them", "his", "her", "our", "your", "my", "me", "us", "this",
    "that", "these", "those", "there", "here", "not", "no", "yes", "please", "thank", "very",
    "too", "also", "then", "now", "what", "how", "why", "who", "when", "where", "which",
})

#: 明显不是"教材句子"的输出（AI 说明文字 / 占位符）
META_MARKERS = ("ai", "提示", "选项", "题干", "答案", "注意", "抱歉", "无法", "json", "—")

_CACHE_MEM = {}
_EVIDENCE_INDEX = None


# --------------------------------------------------------------------------- 只读数据
def _norm(text) -> str:
    t = unicodedata.normalize("NFC", str(text or ""))
    t = t.replace("\u2019", "'").replace("\u2018", "'")
    t = t.replace("\u201c", '"').replace("\u201d", '"')
    return re.sub(r"\s+", " ", t).strip().lower()


def _apostrophes(text) -> str:
    """撇号归一化：Let’s / Let's、students’ / students' 视为同一种写法。"""
    t = str(text or "")
    for ch in ("\u2019", "\u2018", "\u02bc", "`", "\u00b4"):
        t = t.replace(ch, "'")
    return t


def _words(text) -> list:
    return [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z'\-]*", _apostrophes(text))]


def _variant_keys(word) -> set:
    """一个词面的"正常表面形式"键集合：大小写 / 撇号 / 所有格 / 单复数 / -ing。

    只做最小归并（不做激进词干化）：返回的键仅用于和教材词面比对，
    不会把教材里没有出现过的词带进来。
    """
    w = _apostrophes(str(word or "").strip().lower()).rstrip("'")
    keys = {w} if w else set()
    if w.endswith("'s") and len(w) > 2:
        keys.add(w[:-2])
    for v in list(keys):
        if v.endswith("ing") and len(v) > 5:
            stem = v[:-3]
            keys.add(stem)
            if len(stem) >= 3 and stem[-1] == stem[-2] and stem[-1] not in "aeiou":
                keys.add(stem[:-1])                 # running → run（同时保留 runn，避免吞掉 missing → miss）
        if v.endswith("es") and len(v) > 4:
            keys.add(v[:-2])                        # boxes → box
        if v.endswith("s") and not v.endswith("ss") and len(v) > 3:
            keys.add(v[:-1])                        # storms → storm
    return keys


def _ro(path) -> sqlite3.Connection:
    conn = sqlite3.connect("file:%s?mode=ro" % Path(path).as_posix(), uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _evidence_packs() -> list:
    if "packs" not in _CACHE_MEM:
        try:
            _CACHE_MEM["packs"] = json.loads(EVIDENCE_MAP.read_text(encoding="utf-8"))["packages"]
        except Exception:                       # noqa: BLE001 —— 证据文件缺失时按"无证据"处理
            _CACHE_MEM["packs"] = []
    return _CACHE_MEM["packs"]


def _evidence_index() -> dict:
    """词 → 该词出现过的 evidence pack（question_id + 教材块），用于证明干扰项来源。"""
    global _EVIDENCE_INDEX
    if _EVIDENCE_INDEX is None:
        idx = {}
        for pack in _evidence_packs():
            qid = pack.get("question_id") or ""
            ref = pack.get("textbook_reference") or {}
            for word in pack.get("related_vocabulary") or []:
                idx.setdefault(_norm(word), []).append({"pack": qid,
                                                         "textbook_page": ref.get("textbook_page")})
        _EVIDENCE_INDEX = idx
    return _EVIDENCE_INDEX


def unit_resources(unit_code: str) -> dict:
    """当前 Unit 的教材词条（词汇 / 短语 / 句型）→ 词面、词性、中文意思、来源块/页。"""
    key = "res:%s" % unit_code
    if key in _CACHE_MEM:
        return _CACHE_MEM[key]
    sys.path.insert(0, str(BASE / "web"))
    import content as content_mod
    conn = _ro(CONTENTPACK)
    out = {}
    try:
        attr = content_mod._attribution(conn)
        pages = {}
        for row in conn.execute(
                "SELECT sr.item_id AS item_id, MIN(p.pdf_page) AS pdf_page FROM source_ref sr "
                "JOIN content_block b ON b.block_id = sr.source_id "
                "JOIN page p ON p.page_id = b.page_id GROUP BY sr.item_id"):
            pages[row["item_id"]] = row["pdf_page"]
        for row in conn.execute(
                "SELECT item_id, item_type, canonical_text, meaning_zh, part_of_speech "
                "FROM learning_item WHERE item_type IN ('vocabulary','phrase','sentence_pattern')"):
            info = attr.get(row["item_id"]) or {}
            if info.get("unit_code") != unit_code:
                continue
            word = _norm(row["canonical_text"])
            if not word:
                continue
            out[word] = {"item_id": row["item_id"], "item_type": row["item_type"],
                         "text": row["canonical_text"], "meaning": row["meaning_zh"] or "",
                         "pos": (row["part_of_speech"] or "").strip(),
                         "pdf_page": pages.get(row["item_id"])}
    finally:
        conn.close()
    _CACHE_MEM[key] = out
    return out


def _unit_sentences(unit_code: str) -> list:
    """该 Unit 全部教材句子（含 audio 资产）：AI 组合干扰项的素材范围。"""
    key = "sents:%s" % unit_code
    if key in _CACHE_MEM:
        return _CACHE_MEM[key]
    import server as demo_server                   # 延迟导入，避免与 server 循环导入
    unit = next((u for u in demo_server.units() if u["unit_code"] == unit_code), None)
    out = []
    if unit is not None:
        seen = set()
        for lesson in demo_server.lessons(unit):
            for s in demo_server.lesson_sentences(unit, lesson) or []:
                text = (s.get("text") or "").strip()
                if text and _norm(text) not in seen:
                    seen.add(_norm(text))
                    out.append({"uid": s.get("uid"), "text": text,
                                "pdf_page": s.get("pdf_page")})
        for s in demo_server.listen_pool_sentences(unit):     # 兜底：课时外的整单元句子
            text = (s.get("text") or "").strip()
            if text and _norm(text) not in seen:
                seen.add(_norm(text))
                out.append({"uid": s.get("uid"), "text": text, "pdf_page": s.get("pdf_page")})
    _CACHE_MEM[key] = out
    return out


def unit_vocabulary_words(unit_code: str) -> set:
    """当前 Unit 词条（词汇 / 短语 / 句型）里出现过的单词。

    修复点：不再把 `canonical_text` 整条当成一个 token —— `teaching building`、
    `primary school` 这样的短语里，每个词都属于当前 Unit 的教材资源。
    """
    key = "vocab_words:%s" % unit_code
    if key in _CACHE_MEM:
        return _CACHE_MEM[key]
    words = set()
    for info in unit_resources(unit_code).values():
        words.update(_words(info.get("text") or ""))
    _CACHE_MEM[key] = words
    return words


def unit_allowed_keys(unit_code: str) -> set:
    """允许出现的词形键：通用功能词 + **已学教材资源范围**里的词（含正常词形变化）。

    资源范围 = 孩子的学习进度前缀（Starter → 当前已学 Unit）∪ 当前题所在 Unit
    —— 见 `learned_unit_codes()`；未来 Unit 不进入，Appendix 不进入。
    "条目整串 / 分词 / 单复数 / 所有格 / -ing / 大小写 / 撇号"造成的表面差异继续归一化。
    """
    key = "allowed:%s" % unit_code
    if key in _CACHE_MEM:
        return _CACHE_MEM[key]
    surface = set(FUNCTION_WORDS)
    for code in learned_unit_codes(unit_code):
        surface |= unit_vocabulary_words(code)
        surface |= {w for s in _unit_sentences(code) for w in _words(s["text"])}
    keys = set()
    for word in surface:
        keys |= _variant_keys(word)
    _CACHE_MEM[key] = keys
    return keys


def learned_unit_codes(unit_code: str) -> list:
    """干扰项可以使用的 Unit 集合 = 学习进度前缀 ∪ 当前题所在 Unit。

    * 学习进度由 `demo/server.py::learned_unit_prefix()` 给出（真实学习证据，非浏览位置）；
    * 当前题所在 Unit 必须包含（题目自身的教材上下文；否则该题的语言会被判成教材外）；
    * 未来 Unit 不进入；Appendix 不进入（`units()` 已排除）。
    """
    key = "units_allowed:%s" % unit_code
    if key in _CACHE_MEM:
        return _CACHE_MEM[key]
    codes = []
    try:
        import server as demo_server                   # 延迟导入，避免与 server 循环导入
        codes = [u["unit_code"] for u in demo_server.learned_unit_prefix()]
    except Exception:                                   # noqa: BLE001 —— 取不到进度就只保留当前 Unit
        codes = []
    if not codes:
        codes = [unit_code]
    elif unit_code not in codes:
        codes = codes + [unit_code]
    _CACHE_MEM[key] = codes
    return codes


# --------------------------------------------------------------------------- AI（确定性模拟）
def candidates_for(target: dict, unit_code: str) -> list:
    """候选生成层：注入了真实 AI 调用器就走真实 AI，否则用确定性模拟。"""
    if AI_CALLER is not None:
        return ai_candidates_for(target, unit_code)
    return simulated_candidates_for(target, unit_code)


def evidence_catalogue(unit_code: str) -> list:
    """给 AI 的"允许使用"教材资源清单（句子 + 词汇，各带 evidence id 与教材页）。

    范围与校验一致：孩子已学的教材资源（前缀）∪ 当前题所在 Unit。
    """
    out, seen = [], set()
    for code in learned_unit_codes(unit_code):
        for s in _unit_sentences(code):
            if s.get("uid") and s["uid"] not in seen:
                seen.add(s["uid"])
                out.append({"kind": "textbook_sentence", "id": s["uid"], "text": s["text"],
                            "textbook_page": s.get("pdf_page")})
    for code in learned_unit_codes(unit_code):
        for word, info in unit_resources(code).items():
            if info["item_id"] in seen:
                continue
            seen.add(info["item_id"])
            out.append({"kind": info["item_type"], "id": info["item_id"], "text": info["text"],
                        "meaning": info.get("meaning") or "", "pos": info.get("pos") or "",
                        "textbook_page": info.get("pdf_page")})
    return out


def build_ai_batch_prompt(samples: list) -> tuple:
    """一次调用覆盖一批句子的 prompt（system, user）；samples: [{sentence_index, text, unit}]。"""
    blocks = []
    for s in samples:
        lines = ["单元 %s 的教材资源（evidence_ids 只能取这里的 id）：" % s["unit"]]
        for e in evidence_catalogue(s["unit"]):
            if e["kind"] == "textbook_sentence":
                lines.append("[%s] 句子：%s" % (e["id"], e["text"]))
            else:
                lines.append("[%s] %s %s %s"
                             % (e["id"], e["text"], e.get("pos") or "",
                                e.get("meaning") or ""))
        blocks.append('[sentence_index %d] 正确答案：%s\n%s'
                      % (int(s["sentence_index"]), json.dumps(s["text"], ensure_ascii=False),
                         "\n".join(lines)))
    user = ("年级：初一第一学期（外研版七年级上册）\n\n"
            + "\n\n".join(blocks)
            + "\n\n请按 system 规定的 JSON 结构，为上面每一个 sentence_index 输出它的干扰项（0–3 个）。")
    return AI_SYSTEM_PROMPT, user


def _parse_ai_json(text: str) -> dict:
    """容错解析 AI 输出（去掉 ```json 包裹 / 前后说明，取第一个完整 JSON 对象）。"""
    raw = str(text or "").strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.M).strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        return json.loads(raw[start:end + 1])
    except Exception:                                     # noqa: BLE001
        return {}


def ai_candidates_batch(response: dict, samples: list) -> dict:
    """把 AI 的结构化输出还原成候选（按 sentence_index 分组），并解析 evidence_ids。"""
    catalogues = {s["unit"]: {e["id"]: e for e in evidence_catalogue(s["unit"])} for s in samples}
    unit_of = {int(s["sentence_index"]): s["unit"] for s in samples}
    out = {}
    for item in (response or {}).get("items") or []:
        try:
            idx = int(item.get("sentence_index"))
        except (TypeError, ValueError):
            continue
        unit_code = unit_of.get(idx)
        if unit_code is None:
            continue
        catalogue = catalogues[unit_code]
        kept = []
        for d in item.get("distractors") or []:
            ev = []
            for eid in d.get("evidence_ids") or []:
                e = catalogue.get(eid)
                if e:                                      # 只认教材清单里的 id（证据边界）
                    ev.append({"kind": e["kind"], "id": e["id"],
                               "textbook_page": e.get("textbook_page"),
                               "quote": (e.get("text") or "")[:80]})
            kept.append({"text": str(d.get("text") or "").strip(), "origin": "ai",
                         "confidence": d.get("confidence", 0),
                         "reason": str(d.get("reason") or "")[:120],
                         "source_evidence": ev})
        out[idx] = kept
    return out


def ai_candidates_for(target: dict, unit_code: str) -> list:
    """真实 AI 生成候选（单句 = 批量 1 句；调用次数由调用方控制）。"""
    sample = {"sentence_index": int(target.get("sentence_index") or 0),
              "text": target["text"], "unit": unit_code}
    system, user = build_ai_batch_prompt([sample])
    response = AI_CALLER(system, user) if AI_CALLER else {}
    return ai_candidates_batch(response, [sample]).get(sample["sentence_index"], [])


def simulated_candidates_for(target: dict, unit_code: str) -> list:
    """AI 资源理解 + 语义组合（确定性模拟）：返回候选干扰项（未校验，带证据与置信度）。"""
    text = target["text"]
    target_words = _words(text)
    target_norm = _norm(text)
    items = unit_resources(unit_code)
    packs = _evidence_index()
    sentences = _unit_sentences(unit_code)
    attested = {w for s in sentences for w in _words(s["text"])}
    cands = []

    # A. 同单元"最容易混"的教材原句：按实词重合度排序（重合越多越像，越容易混）
    scored = []
    for s in sentences:
        other = _norm(s["text"])
        if not other or other == target_norm:
            continue
        overlap = len(set(_words(s["text"])) & set(target_words))
        if overlap <= 0:
            continue                                    # 没有任何共同实词 → 一眼排除，不要
        scored.append((overlap, len(s["text"]), s, other))
    scored.sort(key=lambda x: (-x[0], x[1], x[3]))
    for overlap, _n, s, other in scored[:2]:
        cands.append({
            "text": s["text"], "origin": "textbook_sentence",
            "confidence": round(min(0.95, 0.62 + 0.08 * overlap), 2),
            "reason": "同单元教材原句，与本句共用 %d 个实词，听觉上最容易混" % overlap,
            "source_evidence": [{"kind": "textbook_sentence", "id": s.get("uid"),
                                 "textbook_page": s.get("pdf_page"),
                                 "quote": s["text"][:80]}]})

    # B. 用教材词汇替换原句中的一个实词（同词性、不同义、教材里出现过）
    for i, token in enumerate(target_words):
        base = items.get(token)
        if not base or token in FUNCTION_WORDS or not base.get("pos"):
            continue
        for word, info in items.items():
            if word == token or info.get("pos") != base["pos"]:
                continue
            if _norm(info.get("meaning")) in ("", _norm(base.get("meaning"))):
                continue
            if word not in attested:
                continue                                # 替换词必须在教材句子里出现过（已学范围）
            raw = re.findall(r"[A-Za-z][A-Za-z'\-]*", text)
            if len(raw) != len(target_words):
                break
            variant = " ".join(raw[:i] + [info["text"]] + raw[i + 1:])
            ev = [{"kind": "textbook_sentence", "id": target.get("uid"),
                   "textbook_page": target.get("pdf_page"), "quote": text[:80]},
                  {"kind": "vocabulary", "id": info["item_id"], "textbook_page": info.get("pdf_page"),
                   "quote": "%s —— %s" % (info["text"], info.get("meaning") or "")}]
            ev += (packs.get(word) or [])[:1]
            cands.append({
                "text": variant, "origin": "textbook_word_swap",
                "confidence": 0.72 if len(word) == len(token) else 0.65,
                "reason": "把教材原句里的「%s」换成同词性的教材词「%s」，其余不变" % (token, info["text"]),
                "source_evidence": ev})
        if len(cands) >= 6:
            break
    return cands


# --------------------------------------------------------------------------- 校验
def _is_meta(text: str) -> bool:
    low = text.lower()
    return any(marker in low for marker in META_MARKERS) or re.search(r"[<>{}\[\]]", text) is not None


def is_append_pattern(target_text: str, cand_text: str) -> bool:
    """候选项是否只是"正确答案 + 句首/句尾少量词"（核心结构与信息没有实质变化）。

    确定性词级判断（不引入 NLP）：把两句拆成词序列（忽略大小写与标点），
    若候选完整保留了正确答案的整段词序列，且只在开头/结尾多出 ≤ MAX_APPEND_WORDS 个词 → 命中。
    "教材词汇替换 / 句子成分替换"会改变词序列中的某个位置 → 不会命中，仍可保留。
    """
    t, c = _words(target_text), _words(cand_text)
    if len(t) < 2 or len(c) <= len(t) or (len(c) - len(t)) > MAX_APPEND_WORDS:
        return False
    return c[:len(t)] == t or c[-len(t):] == t


def validate(cand: dict, target: dict, unit_code: str, seen: set) -> tuple:
    """确定性校验：不合格返回 (False, 原因)；合格返回 (True, "")。"""
    text = str((cand or {}).get("text") or "").strip()
    norm = _norm(text)
    if not text or norm in ("—", "-", "n/a"):
        return False, "empty"
    if _is_meta(text):
        return False, "meta_or_abnormal_text"
    if len(text) > MAX_TEXT_CHARS or len(_words(text)) < 2:
        return False, "abnormal_length"
    if norm == _norm(target["text"]):
        return False, "same_as_answer"
    if norm in seen:
        return False, "duplicate"
    if is_append_pattern(target.get("text") or "", text):
        return False, "appended_tail_or_prefix"
    evidence = cand.get("source_evidence") or []
    if not any(e.get("id") or e.get("pack") for e in evidence):
        return False, "no_evidence"
    allowed_keys = unit_allowed_keys(unit_code)
    extra = [w for w in _words(text) if not (_variant_keys(w) & allowed_keys)]
    if extra:
        return False, "out_of_stage:%s" % ",".join(extra[:2])
    if float(cand.get("confidence") or 0) < MIN_CONFIDENCE:
        return False, "low_confidence"
    return True, ""


def build_entry(unit_code: str, lesson_key: str, sentence: dict) -> dict:
    """一个句子题的完整结构化结果：正确答案保持不变，只有候选干扰项来自 AI。"""
    target = {"text": sentence.get("text") or "", "uid": sentence.get("uid"),
              "pdf_page": sentence.get("pdf_page")}
    seen = {_norm(target["text"])}
    kept = []
    for cand in candidates_for(target, unit_code):
        ok, _reason = validate(cand, target, unit_code, seen)
        if not ok:
            continue
        seen.add(_norm(cand["text"]))
        kept.append({"text": cand["text"], "confidence": cand["confidence"],
                     "reason": cand["reason"], "origin": cand["origin"],
                     "source_evidence": cand["source_evidence"]})
        if len(kept) >= MAX_DISTRACTORS:
            break
    return {"context_hash": context_hash(unit_code, lesson_key, target["text"]),
            "question_item": {"textbook_id": TEXTBOOK_ID, "unit": unit_code,
                              "lesson": lesson_key, "sentence_uid": target["uid"]},
            "correct_answer": target["text"],
            "distractors": kept,
            "model": MODEL, "prompt_version": PROMPT_VERSION, "rules_version": RULES_VERSION,
            "ai_called": False}


def context_hash(unit_code: str, lesson_key: str, sentence_text: str) -> str:
    raw = "|".join([TEXTBOOK_ID, unit_code, lesson_key, _norm(sentence_text),
                    PROMPT_VERSION, RULES_VERSION])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------- 缓存
def load_cache(path=None) -> dict:
    p = Path(path or CACHE_FILE)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:                                # noqa: BLE001 —— 没有缓存文件就是空缓存
        return {"version": RULES_VERSION, "prompt_version": PROMPT_VERSION, "entries": {}}


def save_cache(data: dict, path=None) -> None:
    p = Path(path or CACHE_FILE)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def cached(unit_code: str, lesson_key: str, sentence: dict, path=None) -> list:
    """请求期只读缓存：命中且校验通过才返回（不生成、不调用 AI、不阻塞页面）。"""
    entry = (load_cache(path).get("entries") or {}).get(
        context_hash(unit_code, lesson_key, sentence.get("text") or ""))
    if not entry:
        return []
    out, seen = [], {_norm(sentence.get("text"))}
    for cand in entry.get("distractors") or []:
        ok, _reason = validate(cand, {"text": sentence.get("text")}, unit_code, seen)
        if ok:
            seen.add(_norm(cand["text"]))
            out.append(cand)
    return out[:MAX_DISTRACTORS]


def generate(unit_codes=None, path=None) -> dict:
    """离线生成 + 校验 + 缓存（CLI 用；页面打开时不会走到这里）。"""
    import server as demo_server
    data = load_cache(path)
    entries = data.setdefault("entries", {})
    stats = {"sentences": 0, "with_1": 0, "with_2": 0, "with_3": 0, "with_0": 0}
    for unit in demo_server.units():
        if unit_codes and unit["unit_code"] not in unit_codes:
            continue
        for lesson in demo_server.lessons(unit):
            if not any(lesson["counts"].values()):
                continue
            for sentence in (demo_server.lesson_sentences(unit, lesson) or []):
                entry = build_entry(unit["unit_code"], lesson["key"], sentence)
                entries[entry["context_hash"]] = entry
                stats["sentences"] += 1
                n = len(entry["distractors"])
                stats["with_%d" % n if n <= 3 else "with_3"] = \
                    stats.get("with_%d" % n if n <= 3 else "with_3", 0) + 1
    data["version"] = RULES_VERSION
    data["prompt_version"] = PROMPT_VERSION
    save_cache(data, path)
    return stats
