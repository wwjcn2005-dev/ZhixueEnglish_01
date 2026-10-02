#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P7 · 教材价值最大化增量构建（词形变化 / 教材语境词汇 / 附录词形规则 / 固定搭配候选）

在现有正式题库上**增量写入**（只 INSERT，不删除、不修改任何已入库题目）。

修复的识别层问题（P7 §四）：
  * v01 `build_word_forms` 要求「重建句 == 整块文本」；教材一个 content_block 常含多句
    → 26 条已核验词形全部被判“无证据”，题库 form = 0。
  * 本脚本改为「教材句 ⊆ 连续文本段（同页 reading_order 相邻，最多 4 块）」，
    并要求该句在**同 Unit 内只属于唯一段落** → 证据仍可回溯到真实 content_block。

教材价值的利用层次（全部由教材数据证明，不引入教材外内容）：
  1. 词形变化            `vocab_word_form`      —— 教材正文句挖空（规则 A）
  2. 附录词形规则        `vocab_word_form`      —— 附录 “Guide to the language use”
                                                   明确列出的规则与例词（规则 B）
  3. 教材语境词汇        `vocab_context_choice` —— 教材正文句挖空 + 同 Unit 同词性词表干扰项
  4. 正文固定搭配候选    （只记录候选，不生成题目；缺教材释义 → 依 P7 §十二 留候选）

运行：
  python builder\build_questionbank_value_v01.py                 # dry-run（默认，不写库）
  python builder\build_questionbank_value_v01.py --write [--db <path>]
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.util
import json
import re
import sqlite3
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DB_PATH = BASE / "structured" / "questionbank" / "questionbank.db"
CONTENTPACK = BASE / "structured" / "contentpack" / "v5" / "FLTRP-EN-7A-2022CUR.sqlite"
REPORT = BASE / "audit" / "P7_textbook_value_build_report.json"

RUN_ID = "RUN-P7-VALUE-V1"
RULES_VERSION = "questionbank-rules-v4"
PROMPT_VERSION = "p7-textbook-value-v1"
STEP = "builder/build_questionbank_value_v01.py"
UNIT_ORDER = ("Starter", "Unit 1", "Unit 2", "Unit 3", "Unit 4", "Unit 5", "Unit 6")

#: 附录 “Guide to the language use” 词形变化规则页（正文 “Know more about … ⇢ pNN” 指针指向）
RULE_PAGES = (130, 131, 132, 133, 134, 135)
RULE_MARKERS = ("直接加", "变y为i", "变成ves", "不规则变化", "单复数同形", "特殊变化")

#: P7 只读核验得到的 26 条已核验词形（**验收基准**，不是生成规则；生成仍走教材证据）
FORM_BASELINE = (
    ("Starter", "lab", "labs"), ("Unit 1", "thought", "thoughts"), ("Unit 1", "wind", "winds"),
    ("Unit 1", "storm", "storms"), ("Unit 2", "instrument", "instruments"),
    ("Unit 2", "classmate", "classmates"), ("Unit 2", "page", "pages"),
    ("Unit 3", "mountain", "mountains"), ("Unit 3", "serve", "served"),
    ("Unit 3", "carry", "carrying"), ("Unit 3", "hug", "hugs"),
    ("Unit 4", "realise", "realised"), ("Unit 4", "dumpling", "dumplings"),
    ("Unit 4", "balloon", "balloons"), ("Unit 4", "lantern", "lanterns"),
    ("Unit 4", "firework", "fireworks"), ("Unit 5", "human", "humans"),
    ("Unit 5", "adult", "adults"), ("Unit 5", "biscuit", "biscuits"),
    ("Unit 5", "connect", "connecting"), ("Unit 6", "mirror", "mirrors"),
    ("Unit 6", "kilometre", "kilometres"), ("Unit 6", "speed", "speeds"),
    ("Unit 6", "museum", "museums"), ("Unit 6", "arrive", "arrived"),
    ("Unit 6", "hunt", "hunted"),
)

IRREGULAR_PLURAL = {"child": "children", "man": "men", "woman": "women", "foot": "feet",
                    "tooth": "teeth", "mouse": "mice", "person": "people", "knife": "knives",
                    "leaf": "leaves", "life": "lives", "half": "halves", "shelf": "shelves",
                    "tomato": "tomatoes", "potato": "potatoes", "photo": "photos",
                    "hero": "heroes", "radio": "radios", "zoo": "zoos", "piano": "pianos"}
SPECIAL_FORMS = {"be": ("is", "are", "am"), "have": ("has",), "do": ("does",),
                 "go": ("goes",)}
PARTICLES = {"up", "out", "off", "on", "in", "at", "to", "for", "of", "with", "from",
             "about", "into", "over", "through", "by", "as", "after", "before", "around"}

#: 教材排版残留前缀：题号（`2\t` / `5.` / `1 .`）与项目符号（`•`）
LEAD_PREFIX = re.compile(r"^(?:\s*\d{1,2}\s*[.)、]?\s*|\s*[•▪●○*]\s*)+")

#: 教材练习指令句（不是教材内容句）：不作为题目语料
INSTRUCTION_OPENERS = {"match", "read", "complete", "listen", "work", "write", "talk",
                       "discuss", "look", "choose", "answer", "fill", "circle", "tick",
                       "put", "draw", "number", "replace", "retell", "order", "share",
                       "check", "ask", "find", "think", "say", "study", "learn", "practise",
                       "practice", "use", "add", "make", "take", "note", "label", "underline",
                       "correct", "translate", "speak", "tell", "listen", "guess"}

#: 题号/练习选项残留（听力练习等排版残留会混进句子）：命中即不作为题目语料
DIGIT_RESIDUE = (
    r"\([^)]*\d[^)]*\)",                 # 练习选项残留：(900 / 9,000)
    r"\([^)]*[A-Za-z][^)]*\)",           # 练习提示残留：(think / learn)、(try)
    r"\d\s*/\s*\d",                      # 选项残留：120 / 140
    r"\b\d{1,2}\s*[\u201d\u201c\"']?\s+[A-Z]",   # 题号后接大写词：… this.” 9 That’s
    r"\d\s*[!?.,]",                      # 数字后直接接标点：… write 4 !
    r"\b(?:is|are|was|were)\s+\d\b",     # 题号嵌在句中：It is 3 for your health.
)

#: 单个数字后允许紧跟的内容（否则视为混进句子的题号）
DIGIT_TAIL_OK = ("o’clock", "o'clock", "km", "million", "billion", "hundred", "thousand",
                 "minute", "hour", "year", "metre", "meter", "day", "week", "month",
                 "degree", "second", "kg", "%", "percent", "point", "pm", "am")

#: 句首常用词：句中（小写词之后）忽然出现这类大写词 = 两个栏目/句子被排版粘在一起
SENTENCE_STARTERS = {"welcome", "what", "how", "it", "this", "that", "they", "there", "here",
                     "she", "he", "we", "you", "my", "the", "a", "an", "people", "in", "on",
                     "at", "now", "today", "when", "if", "but", "and", "some", "all", "do",
                     "does", "can", "will", "would", "login", "search", "next", "first",
                     "then", "finally", "also", "so", "because", "after", "before", "with",
                     "for", "from", "to", "is", "are", "was", "were", "have", "has", "i",
                     "am", "not", "no", "yes"}

#: 附录 “Language notes” 页范围（教材逐单元语言注释，含教材自带的短语释义）
NOTE_PAGE_RANGE = (115, 129)
#: 短语内容词判定时的功能词（用于把短语归属到学习 Unit）
FUNCTION_WORDS = {"a", "an", "the", "to", "of", "in", "on", "at", "for", "with", "by", "up",
                  "out", "off", "as", "be", "is", "are", "am", "was", "were", "do", "does",
                  "sb", "sth", "it", "more", "than", "and", "or", "but", "not", "no", "one",
                  "oneself", "some", "any", "all", "here", "there", "what", "what's"}
#: 教材释义抽取（“X意为“Y””）
GLOSS_PATTERN = re.compile(r"([A-Za-z][A-Za-z'\u2019\- ]{1,28}?)\s*(?:\u610f\u4e3a|\u610f\u601d\u662f)"
                           r"\s*[\u201c\"](.+?)[\u201d\"]")


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _load_v01():
    p = BASE / "builder" / "build_questionbank_v01.py"
    spec = importlib.util.spec_from_file_location("qb_v01_p7", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _norm(text) -> str:
    t = unicodedata.normalize("NFC", str(text or "")).lower().replace("\u2019", "'")
    t = t.replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    return re.sub(r"\s+", " ", t).strip()


def _forms_for(base: str, pos: str) -> list:
    """候选词形（**只是候选**：必须再经教材文本/教材附录逐字命中才成为题目答案）。"""
    w = (base or "").lower()
    if w in SPECIAL_FORMS:
        return [f for f in SPECIAL_FORMS[w] if f != w]
    out = []
    if pos == "n":
        if w in IRREGULAR_PLURAL and IRREGULAR_PLURAL[w] != w:
            out.append(IRREGULAR_PLURAL[w])
        if w.endswith(("s", "x", "ch", "sh")):
            out.append(w + "es")
        elif w.endswith("y") and len(w) > 2 and w[-2] not in "aeiou":
            out.append(w[:-1] + "ies")
        elif w.endswith("o"):
            out += [w + "es", w + "s"]
        elif w.endswith("fe"):
            out.append(w[:-2] + "ves")
        elif w.endswith("f"):
            out.append(w[:-1] + "ves")
        else:
            out.append(w + "s")
    elif pos == "v":
        out.append(w[:-1] + "ing" if (w.endswith("e") and not w.endswith("ee")) else w + "ing")
        out.append(w + "d" if w.endswith("e") else w + "ed")
        if w.endswith("y") and len(w) > 2 and w[-2] not in "aeiou":
            out.append(w[:-1] + "ies")
        else:
            out.append(w + "es" if w.endswith(("s", "x", "ch", "sh", "o")) else w + "s")
    return list(dict.fromkeys(f for f in out if f and f != w))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--db", default=str(DB_PATH))
    ap.add_argument("--contentpack", default=str(CONTENTPACK))
    ap.add_argument("--report", default="")
    ap.add_argument("--dump", default="", help="dry-run 时把新增题写入 JSON（仅用于核验）")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    db_path = Path(args.db)
    v01 = _load_v01()
    cp = sqlite3.connect("file:%s?mode=ro" % Path(args.contentpack).as_posix(), uri=True)
    cp.row_factory = sqlite3.Row

    units = {r["unit_id"]: dict(r) for r in cp.execute("SELECT * FROM unit")}
    sections = {r["section_id"]: dict(r) for r in cp.execute("SELECT * FROM section")}
    activities = {r["activity_id"]: dict(r) for r in cp.execute("SELECT * FROM activity")}
    blocks = [dict(r) for r in cp.execute(
        "SELECT block_id, page_id, reading_order, text_raw, block_kind, layout_role "
        "FROM content_block")]
    pages = {r["page_id"]: dict(r) for r in cp.execute("SELECT * FROM page")}

    item_unit: dict = {}
    for r in cp.execute("SELECT item_id, source_type, source_id FROM source_ref"):
        if r["source_type"] == "activity" and r["source_id"] in activities:
            sec = sections.get(activities[r["source_id"]]["section_id"]) or {}
            u = units.get(sec.get("unit_id")) or {}
            if u.get("unit_code"):
                item_unit.setdefault(r["item_id"], u["unit_code"])
    for r in cp.execute("""SELECT sr.item_id, p.textbook_page FROM source_ref sr
                           JOIN content_block cb ON cb.block_id = sr.source_id
                           JOIN page p ON p.page_id = cb.page_id
                           WHERE sr.source_type='content_block'
                             AND p.textbook_page IS NOT NULL"""):
        tb = r["textbook_page"]
        for u in units.values():
            if (u.get("textbook_page_start") and u.get("textbook_page_end")
                    and u["textbook_page_start"] <= tb <= u["textbook_page_end"]
                    and u.get("unit_code") in UNIT_ORDER):     # 词表/附录页不算学习 Unit
                item_unit.setdefault(r["item_id"], u["unit_code"])
                break

    def unit_of_page_textbook(tb):
        for u in units.values():
            if (u.get("textbook_page_start") and u.get("textbook_page_end")
                    and u["textbook_page_start"] <= tb <= u["textbook_page_end"]):
                return u.get("unit_code")
        return None

    def unit_blocks(unit_code):
        out = []
        for b in blocks:
            pg = pages.get(b["page_id"]) or {}
            tb = pg.get("textbook_page")
            if tb is None or unit_of_page_textbook(tb) != unit_code:
                continue
            if b["block_kind"] in ("footer_text", "heading") or b["layout_role"] in ("footer", "heading"):
                continue
            out.append(b)
        return out

    def unit_spans(unit_code):
        """教材正文连续文本段：同页、reading_order 相邻的块合并（教材句可能跨文本框排版）。"""
        by_page: dict = defaultdict(list)
        for b in unit_blocks(unit_code):
            by_page[b["page_id"]].append(b)
        spans = []
        for _pid, bs in by_page.items():
            bs.sort(key=lambda x: x.get("reading_order") or 0)
            run = []
            for b in bs:
                run.append(b)
                if len(run) >= 4:
                    spans.append(run)
                    run = []
            if run:
                spans.append(run)
        return spans

    norm_block = {b["block_id"]: _norm(b["text_raw"]) for b in blocks}
    unit_text = {u: " ".join((b["text_raw"] or "") for b in unit_blocks(u)) for u in UNIT_ORDER}
    #: Unit 全量正文（按页 + reading_order 排序），用于「答案/挖空句必须是教材逐字文本」的独立校验
    unit_text_full = {u: _norm(" ".join(
        (b["text_raw"] or "") for b in sorted(
            unit_blocks(u), key=lambda x: ((pages.get(x["page_id"]) or {}).get("textbook_page") or 0,
                                           x.get("reading_order") or 0)))) for u in UNIT_ORDER}

    def sentences(text):
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", text or "").replace("\t", " ")
        # 教材排版残留：句末标点后直接接题号（`…?3 What …`）、或引号收尾后再接下一句时也切开
        parts = re.split(r"(?<=[.!?])\s+|(?<=[.!?])(?=\d)|(?<=[.!?][\u201d\u2019\"'])\s+", text)
        return [s.strip() for s in parts if s.strip()]

    def strip_lead(sent: str) -> str:
        """剥离教材排版残留（题号 / 项目符号）；教材文字与内部空白保持原样（供空隙检测）。"""
        s = (sent or "").replace("\t", " ").strip()
        m = LEAD_PREFIX.match(s)
        if not m:
            return s
        rest = s[m.end():]
        if not rest:
            return s
        # 数字后接小写字母视为教材事实（如 “20 students ...”），不剥离
        if s[:m.end()].strip()[:1].isdigit() and rest[:1].islower():
            return s
        if rest[:1].islower():
            return s
        return rest

    def clean_sentence(sent: str) -> bool:
        """教材“干净单句”：无排版残留、长度适中、以句末标点收尾。"""
        if not (15 <= len(sent) <= 160):
            return False
        if any(ch in sent for ch in ("•", "☐", "▪", "●", "○", "⇢", "\u0007", "\t")):
            return False
        if "  " in sent:
            return False
        if not re.search(r"[.!?]$", sent):
            return False
        if re.search(r"[.!?][A-Za-z0-9]", sent):       # 句号后缺空格/直接接题号 → 解析残留
            return False
        if not re.match(r"^[A-Z\"“'‘]", sent):          # 残缺片段（以逗号/数字开头）
            return False
        if "__" in sent:                               # 教材本身已有挖空 → 再加挖空会双重空格
            return False
        if len(re.findall(r"[A-Za-z]+", sent)) < 5:    # 词数过少的片段（学习价值低）
            return False
        first = re.match(r"^([A-Za-z][A-Za-z'\-]*)", sent)
        if first and first.group(1).lower() in INSTRUCTION_OPENERS:
            return False
        if any(re.search(pat, sent) for pat in DIGIT_RESIDUE):
            return False
        if sent.count("\u201c") != sent.count("\u201d"):     # 引号不成对 → 排版截断
            return False
        if sent.rstrip().endswith(("...", "\u2026")):        # 省略号结尾 → 截断
            return False
        if re.match(r"^[A-Z][a-z]+\s*[\u2013\u2014-]\s*[A-Z]", sent):    # 标签与句子粘连
            return False
        if re.match(r"^(?:[A-Z][a-z]+\s+){3,}", sent):                    # 姓名列表与句子粘连
            return False
        if re.match(r"^[A-Z][a-z]{4,}\s+[a-z]{4,}\s+[A-Z][a-z]+", sent):  # 栏目标签与句子粘连
            return False
        glue = re.search(r"[a-z,]\s+([A-Z][a-z]{2,})\s+[a-z]", sent)
        if glue and glue.group(1).lower() in SENTENCE_STARTERS:           # 两句/两栏粘连
            return False
        for m in re.finditer(r"\b(\d+)\b", sent):            # 单个数字只允许接计量/时间词
            if len(m.group(1)) >= 2:
                continue
            tail = sent[m.end():m.end() + 14].strip().lower()
            if any(tail.startswith(ok) for ok in DIGIT_TAIL_OK):
                continue
            return False
        return True

    # ------------------------------------------------------------- 附录词形规则层（规则 B）
    rule_blocks = []
    for b in blocks:
        pg = pages.get(b["page_id"]) or {}
        if pg.get("textbook_page") not in RULE_PAGES:
            continue
        txt = b["text_raw"] or ""
        if any(m in txt for m in RULE_MARKERS):
            rule_blocks.append(b)
    rule_ids = {b["block_id"] for b in rule_blocks}
    # 规则示例常被排版切到紧邻的 sidebar_tip 里（如 “…f / fe变成ves” + “leaf – leaves”）
    for b in blocks:
        pg = pages.get(b["page_id"]) or {}
        if pg.get("textbook_page") not in RULE_PAGES or b["block_id"] in rule_ids:
            continue
        prev = [x for x in blocks
                if x["page_id"] == b["page_id"]
                and (x["reading_order"] or 0) == (b["reading_order"] or 0) - 1]
        if prev and prev[0]["block_id"] in rule_ids and b["block_kind"] == "sidebar_tip":
            rule_blocks.append(b)
            rule_ids.add(b["block_id"])

    appendix_form_evidence: dict = {}
    for b in rule_blocks:
        quote = re.sub(r"\s+", " ", b["text_raw"] or "").strip()
        for tok in re.findall(r"[A-Za-z][A-Za-z'\-]+", b["text_raw"] or ""):
            t = tok.lower()
            if len(t) >= 3 and t not in ("the", "and", "say", "how", "what"):
                appendix_form_evidence.setdefault(t, (b["block_id"], quote[:160]))

    def _rule_block(page_no, marker):
        """按教材页 + 规则文字定位附录规则行（不硬编码 block_id，避免脆弱引用）。"""
        for b in rule_blocks:
            pg = pages.get(b["page_id"]) or {}
            if pg.get("textbook_page") == page_no and marker in (b["text_raw"] or ""):
                return b
        return None

    def appendix_rule_for(base: str, pos: str):
        """教材附录中与该词形变化对应的规则行（词尾分支由教材自身的规则行决定）。"""
        w = (base or "").lower()
        if pos == "n":
            if w.endswith(("s", "x", "ch", "sh")):
                marker = "直接加-es"
            elif w.endswith("y") and len(w) > 2 and w[-2] not in "aeiou":
                marker = "变y为i"
            elif w.endswith("o"):
                marker = "直接加-es或-s"
            elif w.endswith(("f", "fe")):
                marker = "变成ves"
            elif w in IRREGULAR_PLURAL:
                marker = "不规则变化"
            else:
                marker = "直接加-s"
            page_no = 130
        elif pos == "v":
            if w in SPECIAL_FORMS:
                marker = "特殊变化"
            elif w.endswith(("s", "x", "z", "ch", "sh")):
                marker = "直接加-es"
            elif w.endswith("y") and len(w) > 2 and w[-2] not in "aeiou":
                marker = "变y为i"
            else:
                marker = "直接加-s"
            page_no = 132
        else:
            return None
        b = _rule_block(page_no, marker)
        if not b:
            return None
        return b["block_id"], re.sub(r"\s+", " ", b["text_raw"] or "").strip()[:160]

    vocab = [dict(r) for r in cp.execute(
        "SELECT item_id, canonical_text, part_of_speech, meaning_zh, learning_requirement "
        "FROM learning_item WHERE item_type='vocabulary' ORDER BY item_id")]
    by_unit_vocab: dict = defaultdict(list)
    for v in vocab:
        u = item_unit.get(v["item_id"])
        if u:
            by_unit_vocab[u].append(v)
    # 词汇 → Unit：复用既有正式归属（web/content.py 的 unit 资源视图，与产品侧同一口径）
    try:
        _web = BASE / "web"
        if str(_web) not in sys.path:
            sys.path.insert(0, str(_web))
        import content as content_mod                       # noqa: E402  只读
        by_unit_vocab = defaultdict(list)
        for u in UNIT_ORDER:
            slug = "starter" if u == "Starter" else u.lower().replace(" ", "")
            data = content_mod.list_unit_resources(slug, "vocabulary") or {"items": []}
            for item in data.get("items") or []:
                iid = item.get("item_id")
                if not iid:
                    continue
                by_unit_vocab[u].append({"item_id": iid,
                                         "canonical_text": item.get("text") or "",
                                         "part_of_speech": item.get("part_of_speech") or "",
                                         "meaning_zh": item.get("meaning") or "",
                                         "learning_requirement": "CORE" if item.get("can_study")
                                                                 else "RECOGNITION"})
    except Exception as exc:                                # noqa: BLE001
        print("WARN: 词汇 Unit 归属回退到 contentpack 解析：%r" % (exc,))

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    base_count = conn.execute("SELECT COUNT(*) FROM question").fetchone()[0]
    base_sha = hashlib.sha256(db_path.read_bytes()).hexdigest()[:16]
    hashes = {r[0] for r in conn.execute("SELECT content_hash FROM question")}
    new_rows = []
    stats = Counter()
    baseline_state: dict = {}
    diag: dict = {}

    def add(kind, domain, unit, section, source_item_id, prompt, options, answer, answer_kind,
            assets, source_ref):
        text = prompt.get("text") or prompt.get("instruction") or ""
        chash = v01._content_hash(kind, unit, source_ref, text, answer)
        if chash in hashes:
            return "dup"
        hashes.add(chash)
        new_rows.append({"question_id": v01._qid(kind, unit, source_ref, text), "kind": kind,
                         "domain": domain, "unit": unit, "section": section,
                         "source_item_id": source_item_id, "prompt": prompt, "options": options,
                         "answer": answer, "answer_kind": answer_kind, "assets": assets,
                         "hash": chash})
        return "ok"

    def mark_baseline(unit, base, form, ok, reason):
        key = (unit, base, form)
        if key in {k for k in baseline_state}:
            return
        if ok:
            baseline_state[key] = "COVERED"
        else:
            baseline_state.setdefault(key, reason)

    # ------------------------------------------------- 1+2+3. 词形变化 / 教材语境选词
    #: 同一教材句最多承载 2 道题（不同学习目标=不同挖空词），避免把一句话机械拆成大量题
    MAX_PER_SENTENCE = 2
    used_sentence: Counter = Counter()
    used_rule: set = set()
    for unit in UNIT_ORDER:
        pool = by_unit_vocab.get(unit) or []
        spans = unit_spans(unit)
        span_texts = [" ".join((b["text_raw"] or "") for b in span) for span in spans]
        # 同 Unit / 同词性的正式词表干扰项池（确定性顺序，不含目标词）
        distractor_pool: dict = defaultdict(list)
        _seen_txt: dict = defaultdict(set)
        for x in pool:
            t = (x["canonical_text"] or "").strip()
            px = (x["part_of_speech"] or "").strip()
            if not re.fullmatch(r"[A-Za-z][A-Za-z' -]{1,20}", t) or t.lower() in _seen_txt[px]:
                continue
            _seen_txt[px].add(t.lower())
            distractor_pool[px].append(x)

        def _has_form(v):
            if not re.fullmatch(r"[a-z]{3,}", (v["canonical_text"] or "").lower()):
                return False
            return any(re.search(r"\b%s\b" % re.escape(f), _norm(unit_text[unit]))
                       for f in _forms_for(v["canonical_text"], v["part_of_speech"] or ""))

        # 词形变化优先声明教材句（同一句最多 2 题：词形题 + 语境题）
        for v in sorted(pool, key=lambda x: 0 if _has_form(x) else 1):
            base_word = (v["canonical_text"] or "").strip()
            pos = (v["part_of_speech"] or "").strip()
            if not re.fullmatch(r"[a-z]{3,}", base_word.lower()):
                continue
            forms = _forms_for(base_word, pos)
            surface, is_form = None, False
            for form in forms:
                if re.search(r"\b%s\b" % re.escape(form), _norm(unit_text[unit])):
                    surface, is_form = form, True
                    break
            if surface is None:
                surface = base_word.lower()
            picks = [x for x in distractor_pool.get(pos, []) if x["item_id"] != v["item_id"]][:3]
            picked = None
            seen = Counter()
            for span, span_text in zip(spans, span_texts):
                if not re.search(r"\b%s\b" % re.escape(surface), _norm(span_text)):
                    continue
                seen["span"] += 1
                for raw in sentences(span_text):
                    sent = strip_lead(raw)
                    if not re.search(r"\b%s\b" % re.escape(surface), _norm(sent)):
                        continue
                    seen["sent"] += 1
                    if not clean_sentence(sent):
                        seen["dirty"] += 1
                        continue
                    if len(re.findall(r"\b%s\b" % re.escape(surface), _norm(sent))) != 1:
                        seen["multi"] += 1
                        continue
                    if used_sentence[(unit, _norm(sent))] >= MAX_PER_SENTENCE:
                        seen["used"] += 1
                        continue
                    if not is_form and not picks:
                        seen["no_distractor"] += 1
                        continue
                    if not is_form and len(picks) < 3:      # 语境题统一 4 选 1，避免 2 选 1
                        seen["few_distractor"] += 1
                        continue
                    owners = [x for x in span_texts if _norm(sent) in _norm(x)]
                    if len(owners) != 1:                     # 句子必须只属于一个连续文本段
                        seen["not_unique"] += 1
                        continue
                    owners_blocks = [y["block_id"] for y in span
                                     if _norm(sent)[:20] and _norm(sent)[:20] in norm_block[y["block_id"]]]
                    primary = (owners_blocks or [span[0]["block_id"]])[0]
                    picked = (sent, primary, [b["block_id"] for b in span], picks)
                    break
                if picked:
                    break
            if picked:
                sent, block, evidence_blocks, picks = picked
                used_sentence[(unit, _norm(sent))] += 1
                prompt_text = re.sub(r"\b%s\b" % re.escape(surface), "______", sent,
                                     count=1, flags=re.I)
                assets = [{"asset_kind": "content_block", "asset_id": block, "role": "primary",
                           "evidence_quote": sent[:160]}]
                assets += [{"asset_kind": "content_block", "asset_id": b, "role": "support",
                            "evidence_quote": "同段教材文本框（句子跨框排版）"}
                           for b in evidence_blocks if b != block]
                assets += [{"asset_kind": "learning_item", "asset_id": v["item_id"],
                            "role": "answer_basis",
                            "evidence_quote": "%s（%s）" % (base_word, pos or "-")}]
                if is_form:
                    res = add("vocab_word_form", "vocabulary", unit, None, v["item_id"],
                              {"instruction": "用正确的词形补全教材句子。", "text": prompt_text,
                               "base": base_word, "part_of_speech": pos},
                              [], {"text": surface}, "exact", assets,
                              "p7form:%s:%s" % (v["item_id"], block))
                    stats["vocab_word_form_" + res] += 1
                    mark_baseline(unit, base_word.lower(), surface, True, "dup")
                    continue
                options = [{"key": "abcd"[i], "text": t} for i, t in enumerate(
                    [base_word] + [x["canonical_text"] for x in picks])]
                assets += [{"asset_kind": "learning_item", "asset_id": x["item_id"],
                            "role": "distractor_basis", "evidence_quote": x["canonical_text"]}
                           for x in picks]
                res = add("vocab_context_choice", "vocabulary", unit, None, v["item_id"],
                          {"instruction": "选词填空：用教材这句话里的词补全。",
                           "text": prompt_text},
                          options, {"key": "a", "text": base_word}, "option_key", assets,
                          "p7ctx:%s:%s" % (v["item_id"], block))
                stats["vocab_context_choice_" + res] += 1
                continue

            # 规则 B：教材正文没有可用的完整句 → 用附录明确列出的词形规则与例词（仍逐字来自教材）
            # 规则 C：教材正文逐字出现该词形（句子本身不适合挖空，如同一句出现两次）
            #         + 教材附录给出对应变化规则行
            if is_form:
                rule = appendix_rule_for(base_word, pos)
                blk = next((b for b in unit_blocks(unit)
                            if re.search(r"\b%s\b" % re.escape(surface), _norm(b["text_raw"]))), None)
                if rule and blk and (unit, base_word.lower()) not in used_rule:
                    used_rule.add((unit, base_word.lower()))
                    quote = next((strip_lead(s) for s in sentences(blk["text_raw"] or "")
                                  if re.search(r"\b%s\b" % re.escape(surface), _norm(s))),
                                 re.sub(r"\s+", " ", blk["text_raw"] or "").strip())
                    quote = re.sub(r"\s+", " ", quote).strip()[:160]
                    assets = [{"asset_kind": "content_block", "asset_id": blk["block_id"],
                               "role": "primary",
                               "evidence_quote": "教材正文逐字出现该词形：%s" % quote},
                              {"asset_kind": "content_block", "asset_id": rule[0],
                               "role": "answer_basis", "evidence_quote": rule[1]},
                              {"asset_kind": "learning_item", "asset_id": v["item_id"],
                               "role": "answer_basis",
                               "evidence_quote": "%s（%s）" % (base_word, pos or "-")}]
                    prompt = {"instruction": "按教材附录的词形变化规则写出正确形式。",
                              "text": "%s → ______" % base_word, "base": base_word,
                              "part_of_speech": pos,
                              "rule_source": "教材附录 “Guide to the language use”"}
                    res = add("vocab_word_form", "vocabulary", unit, None, v["item_id"], prompt,
                              [], {"text": surface}, "exact", assets,
                              "p7rulec:%s:%s" % (v["item_id"], blk["block_id"]))
                    stats["vocab_word_form_ruleC_" + res] += 1
                    mark_baseline(unit, base_word.lower(), surface, True, "dup")
                    continue
            for form in forms:
                ev = appendix_form_evidence.get(form)
                if not ev and base_word.lower() in SPECIAL_FORMS:
                    ev = appendix_form_evidence.get(form)
                if not ev:
                    continue
                if re.search(r"\b%s\b" % re.escape(base_word.lower()),
                             _norm(unit_text[unit])) is None:
                    continue
                block_id, quote = ev
                if (unit, base_word.lower()) in used_rule:
                    break
                used_rule.add((unit, base_word.lower()))
                assets = [{"asset_kind": "content_block", "asset_id": block_id, "role": "primary",
                           "evidence_quote": quote},
                          {"asset_kind": "learning_item", "asset_id": v["item_id"],
                           "role": "answer_basis",
                           "evidence_quote": "%s（%s）" % (base_word, pos or "-")}]
                prompt = {"instruction": "按教材附录的词形变化规则写出正确形式。",
                          "text": "%s → ______" % base_word, "base": base_word,
                          "part_of_speech": pos, "rule_source": "教材附录 “Guide to the language use”"}
                res = add("vocab_word_form", "vocabulary", unit, None, v["item_id"], prompt,
                          [], {"text": form}, "exact", assets,
                          "p7rule:%s:%s" % (v["item_id"], form))
                stats["vocab_word_form_rule_" + res] += 1
                mark_baseline(unit, base_word.lower(), form, True, "dup")
                break
            if not picked and not new_rows:
                pass
            if not picked:
                diag[(unit, base_word.lower())] = (
                    "no_span" if not seen["span"] else
                    "no_form_sentence" if not seen["sent"] else
                    "sentence_dirty:%d" % seen["dirty"] if seen["dirty"] and not any(
                        seen[k] for k in ("multi", "used", "not_unique")) else
                    "sentence_multi_occurrence:%d" % seen["multi"] if seen["multi"] else
                    "sentence_reused:%d" % seen["used"] if seen["used"] else
                    "span_not_unique:%d" % seen["not_unique"] if seen["not_unique"] else "no_clean_sentence")

    # ------------------------------------------------- 4. 教材附录 Language notes 短语（教材自带释义）
    glossary = []
    seen_expr = set()
    for b in blocks:
        pg = pages.get(b["page_id"]) or {}
        tb = pg.get("textbook_page")
        if tb is None or not (NOTE_PAGE_RANGE[0] <= tb <= NOTE_PAGE_RANGE[1]):
            continue
        for m in GLOSS_PATTERN.finditer(b["text_raw"] or ""):
            expr = re.sub(r"\s+", " ", m.group(1)).strip(" .,，;；")
            meaning = re.sub(r"\s+", "", m.group(2)).strip("。.,，;；")
            key = expr.lower()
            if " " not in expr or not meaning or key in seen_expr:
                continue
            seen_expr.add(key)
            glossary.append({"expression": expr, "meaning": meaning, "page": tb,
                             "block_id": b["block_id"]})
    existing_phrases = {(r["canonical_text"] or "").lower().strip()
                        for r in cp.execute("SELECT canonical_text FROM learning_item "
                                            "WHERE item_type='phrase'")}
    vocab_by_unit = {u: {(x["canonical_text"] or "").lower().strip()
                         for x in (by_unit_vocab.get(u) or [])} for u in UNIT_ORDER}

    def _base_form(w):
        w = w.lower()
        if w.endswith("ies") and len(w) > 3:
            return w[:-3] + "y"
        if w.endswith("es") and len(w) > 3:
            return w[:-2]
        if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
            return w[:-1]
        return w

    def unit_for_phrase(expr):
        """短语归属学习 Unit：内容词必须唯一落在一个 Unit 的正式词表中，否则不生成题目。"""
        expr_norm = _norm(expr)
        in_text = [u for u in UNIT_ORDER if expr_norm and expr_norm in unit_text_full[u]]
        if len(in_text) == 1:                       # 该短语只在一个 Unit 的正文里出现 → 直接归属
            return in_text[0]
        words = [_base_form(t) for t in re.findall(r"[A-Za-z][A-Za-z'\u2019\-]+", expr)
                 if t.lower() not in FUNCTION_WORDS and len(t) >= 3]
        hits = [u for u in UNIT_ORDER if any(w in vocab_by_unit[u] for w in words)]
        return hits[0] if len(hits) == 1 else None

    gloss_pool, seen_gloss = [], set()
    for item_type in ("phrase", "vocabulary"):          # 干扰项优先取教材短语释义
        for r in cp.execute("SELECT meaning_zh FROM learning_item WHERE item_type=? "
                            "AND meaning_zh IS NOT NULL AND meaning_zh <> '' "
                            "ORDER BY item_id, canonical_text", (item_type,)):
            mz = re.sub(r"\s+", "", r["meaning_zh"])
            if not mz or mz in seen_gloss:
                continue
            seen_gloss.add(mz)
            gloss_pool.append(mz)

    phrase_candidates = []
    for g in glossary:
        unit = unit_for_phrase(g["expression"])
        phrase_candidates.append({"expression": g["expression"], "meaning": g["meaning"],
                                  "textbook_page": g["page"], "block_id": g["block_id"],
                                  "unit": unit,
                                  "in_phrase_table": g["expression"].lower() in existing_phrases})
        if not unit or g["expression"].lower() in existing_phrases:
            continue
        correct = g["meaning"]
        cands = [mz for mz in gloss_pool
                 if mz != correct and correct not in mz and mz not in correct]
        start = int(hashlib.sha1(g["expression"].encode("utf-8")).hexdigest()[:6], 16) \
            % max(1, len(cands))
        dists = (cands[start:] + cands[:start])
        if len(dists) < 3:
            continue
        options = [{"key": "abcd"[i], "text": t} for i, t in enumerate([correct] + dists[:3])]
        assets = [{"asset_kind": "content_block", "asset_id": g["block_id"],
                   "role": "primary",
                   "evidence_quote": "%s意为“%s”（教材附录 p%d）" % (g["expression"], correct,
                                                                    g["page"])}]
        prompt = {"instruction": "选择与教材释义一致的短语。", "text": g["expression"],
                  "learning_requirement": "RECOGNITION",
                  "evidence": "教材附录 Language notes p%d" % g["page"]}
        res = add("phrase_meaning_choice", "vocabulary", unit, None, None, prompt, options,
                  {"key": "a", "text": correct}, "option_key", assets,
                  "p7phrase:%s" % g["block_id"])
        stats["phrase_meaning_choice_" + res] += 1

    # ------------------------------------------------- 5. 正文固定搭配（候选资源，不入题库）
    flat = _norm(" ".join((b["text_raw"] or "") for b in blocks))
    verbs = {v["canonical_text"].lower() for v in vocab if (v["part_of_speech"] or "") == "v"}
    adjs = {v["canonical_text"].lower() for v in vocab if (v["part_of_speech"] or "") == "adj"}
    cand: dict = {}
    for m in re.finditer(r"\b([a-z][a-z'\-]+)\s+([a-z][a-z'\-]+)\b", flat):
        if m.group(1) in verbs and m.group(2) in PARTICLES:
            key = "%s %s" % (m.group(1), m.group(2))
            cand[key] = cand.get(key, 0) + 1
    for m in re.finditer(r"\b(?:am|is|are|was|were)\s+([a-z][a-z'\-]+)\s+([a-z][a-z'\-]+)\b", flat):
        if m.group(1) in adjs and m.group(2) in PARTICLES:
            key = "%s %s" % (m.group(1), m.group(2))
            cand[key] = cand.get(key, 0) + 1
    existing_phrases = {(r["canonical_text"] or "").lower().strip()
                        for r in cp.execute("SELECT canonical_text FROM learning_item "
                                            "WHERE item_type='phrase'")}
    stable = {k: v for k, v in cand.items() if v >= 2 and k not in existing_phrases}
    stats["phrase_candidates"] = len(stable)
    phrase_list = sorted(stable, key=lambda k: (-stable[k], k))
    phrase_examples = []
    for expr in phrase_list:
        for b in blocks:
            hit = [s for s in (strip_lead(x) for x in sentences(b["text_raw"] or ""))
                   if re.search(r"\b%s\b" % re.escape(expr), _norm(s)) and clean_sentence(s)]
            if hit:
                pg = pages.get(b["page_id"]) or {}
                unit = (unit_of_page_textbook(pg.get("textbook_page"))
                        if pg.get("textbook_page") else None)
                phrase_examples.append({"expression": expr, "count": stable[expr],
                                        "unit": unit, "block_id": b["block_id"],
                                        "sentence": hit[0][:140]})
                break
    stats["phrase_candidate_examples"] = len(phrase_examples)

    # ------------------------------------------------- 质量门禁
    problems = []
    for q in new_rows:
        if q["unit"] not in UNIT_ORDER:
            problems.append("%s unit 非法" % q["question_id"])
        if not q["answer"].get("text") and not q["answer"].get("key"):
            problems.append("%s 无答案" % q["question_id"])
        if q["answer_kind"] == "option_key":
            keys = [o["key"] for o in q["options"]]
            texts = [o["text"] for o in q["options"]]
            if (len(q["options"]) < 2 or q["answer"]["key"] not in keys
                    or len(set(texts)) != len(texts)):
                problems.append("%s 选项非法" % q["question_id"])
        if not any(a["role"] in ("primary", "answer_basis") for a in q["assets"]):
            problems.append("%s 缺教材证据" % q["question_id"])
        if not any(a["asset_kind"] == "content_block" for a in q["assets"]):
            problems.append("%s 缺教材块证据" % q["question_id"])
        # 答案/挖空句必须能在教材块原文中逐字还原（不允许出现教材里没有的写法）
        unit_txt = unit_text_full.get(q["unit"], "")
        ans_text = (q["answer"].get("text") or "").strip()
        prompt_text = q["prompt"].get("text") or ""
        rule_style = "rule_source" in q["prompt"]
        if ans_text and "______" in prompt_text and not rule_style:
            restored = _norm(prompt_text.replace("______", ans_text, 1))
            if not (restored and restored in unit_txt):
                problems.append("%s 还原句不在教材块原文中" % q["question_id"])
        elif ans_text:
            blk_txt = _norm(" ".join(norm_block.get(a["asset_id"], "") for a in q["assets"]
                                     if a["asset_kind"] == "content_block"))
            if not re.search(r"[A-Za-z]", ans_text):     # 中文释义型答案（短语释义题）
                expr = _norm(prompt_text)
                if not (expr and expr in blk_txt):
                    problems.append("%s 短语不在教材附录块中" % q["question_id"])
            elif not (re.search(r"\b%s\b" % re.escape(_norm(ans_text)), unit_txt)
                      or re.search(r"\b%s\b" % re.escape(_norm(ans_text)), blk_txt)):
                problems.append("%s 答案词形不在教材块原文中" % q["question_id"])
    if len({q["hash"] for q in new_rows}) != len(new_rows):
        problems.append("content_hash 重复")
    if len({q["question_id"] for q in new_rows}) != len(new_rows):
        problems.append("question_id 重复")

    baseline_missing = [{"unit": u, "base": b, "form": f,
                         "reason": baseline_state.get((u, b, f)) or diag.get((u, b), "NOT_ATTEMPTED")}
                        for u, b, f in FORM_BASELINE
                        if baseline_state.get((u, b, f)) != "COVERED"]
    covered = len(FORM_BASELINE) - len(baseline_missing)
    print("base:", base_count, base_sha)
    print("渠道统计:", dict(stats))
    print("新增:", len(new_rows), dict(Counter(q["kind"] for q in new_rows)))
    print("按 Unit:", dict(Counter(q["unit"] for q in new_rows)))
    print("26 条已核验词形覆盖: %d/%d" % (covered, len(FORM_BASELINE)))
    for m in baseline_missing:
        print("   未覆盖 %-8s %-12s -> %-14s %s" % (m["unit"], m["base"], m["form"], m["reason"]))
    print("附录词形规则证据行:", len(rule_blocks),
          sorted({e[0].split(":")[-1] for e in appendix_form_evidence.values()}))
    print("固定搭配候选:", stats["phrase_candidates"], phrase_list)
    print("质检问题:", len(problems), problems[:5])
    if args.dump:
        Path(args.dump).write_text(json.dumps(
            [{"question_id": q["question_id"], "type": q["kind"], "unit": q["unit"],
              "prompt": q["prompt"], "options": q["options"], "answer": q["answer"],
              "assets": q["assets"]} for q in new_rows], ensure_ascii=False, indent=1),
            encoding="utf-8")
        print("dry-run 明细 →", args.dump)
    for kind in ("vocab_word_form", "vocab_context_choice"):
        rows = [q for q in new_rows if q["kind"] == kind]
        if not rows:
            continue
        print("\n样例 %s（共 %d）:" % (kind, len(rows)))
        for q in rows[:3] + rows[-2:]:
            print("   [%s] %s" % (q["unit"], json.dumps(q["prompt"], ensure_ascii=False)))
            print("        options=%s answer=%s" % (json.dumps(q["options"], ensure_ascii=False),
                                                    json.dumps(q["answer"], ensure_ascii=False)))
    if problems:
        print("STOP：未写库。")
        return 3
    if args.write and not args.dry_run:
        now = _now()
        conn.execute("BEGIN")
        for q in new_rows:
            conn.execute(
                "INSERT INTO question(question_id, question_type, domain, unit_code, section_key, "
                "activity_id, source_item_id, prompt_json, options_json, answer_json, answer_kind, "
                "answer_status, origin, generation_run_id, rules_version, prompt_version, "
                "quality_status, review_status, content_hash, created_at, updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (q["question_id"], q["kind"], q["domain"], q["unit"], q["section"], None,
                 q["source_item_id"], json.dumps(q["prompt"], ensure_ascii=False),
                 json.dumps(q["options"], ensure_ascii=False),
                 json.dumps(q["answer"], ensure_ascii=False), q["answer_kind"], "RELIABLE",
                 "PROGRAM_GENERATED", RUN_ID, RULES_VERSION, PROMPT_VERSION, "PASS",
                 "AUTO_ACCEPTED", q["hash"], now, now))
            for a in q["assets"]:
                conn.execute("INSERT OR REPLACE INTO question_asset(question_id, asset_kind, "
                             "asset_id, role, evidence_quote) VALUES(?,?,?,?,?)",
                             (q["question_id"], a["asset_kind"], a["asset_id"], a["role"],
                              a["evidence_quote"]))
        conn.execute("INSERT OR REPLACE INTO generation_run(run_id, generator, model, "
                     "prompt_version, rules_version, input_digest, ai_calls, started_at, "
                     "finished_at, status) VALUES(?,?,?,?,?,?,?,?,?,?)",
                     (RUN_ID, "deterministic", "none", PROMPT_VERSION, RULES_VERSION,
                      hashlib.sha256(Path(args.contentpack).read_bytes()).hexdigest()[:16], 0,
                      now, now, "PASS"))
        conn.commit()
        after = conn.execute("SELECT COUNT(*) FROM question").fetchone()[0]
        all_types = {r[0]: r[1] for r in conn.execute(
            "SELECT question_type, COUNT(*) FROM question GROUP BY 1 ORDER BY 2 DESC")}
        all_origins = {r[0]: r[1] for r in conn.execute(
            "SELECT origin, COUNT(*) FROM question GROUP BY 1 ORDER BY 2 DESC")}
        print("写入完成:", base_count, "→", after)
        report = {"step": STEP, "run_id": RUN_ID, "generated_at": now, "ai_calls": 0,
                  "base_questions": base_count, "base_sha256_prefix16": base_sha,
                  "new_questions": len(new_rows),
                  "by_type": dict(Counter(q["kind"] for q in new_rows)),
                  "by_unit": dict(Counter(q["unit"] for q in new_rows)),
                  "form_baseline_total": len(FORM_BASELINE),
                  "form_baseline_covered": covered,
                  "form_baseline_missing": baseline_missing,
                  "form_baseline": [{"unit": u, "base": b, "form": f,
                                     "status": baseline_state.get((u, b, f), "MISSING")}
                                    for u, b, f in FORM_BASELINE],
                  "appendix_rule_blocks": [b["block_id"] for b in rule_blocks],
                  "appendix_form_evidence": {k: v[0] for k, v in sorted(appendix_form_evidence.items())},
                  "structural_collocation_candidates": phrase_list,
                  "structural_collocation_frequency": {k: stable[k] for k in phrase_list},
                  "phrase_candidate_examples": phrase_examples,
                  "language_notes_phrases": phrase_candidates,
                  "language_notes_phrase_questions": [
                      q["prompt"]["text"] for q in new_rows
                      if q["kind"] == "phrase_meaning_choice"],
                  "stats": dict(stats), "total_questions": after,
                  "all_question_types_after": all_types,
                  "all_origins_after": all_origins,
                  "sentence_quality_rules": {
                      "max_questions_per_textbook_sentence": MAX_PER_SENTENCE,
                      "min_sentence_length": 15, "max_sentence_length": 160,
                      "min_word_count": 5,
                      "rejected": ["教材指令句", "教材挖空残留", "题号残留", "练习选项残留",
                                   "栏目标签粘连", "引号不成对", "截断句"]},
                  "sample_questions": [{"question_id": q["question_id"], "type": q["kind"],
                                        "unit": q["unit"], "prompt": q["prompt"],
                                        "answer": q["answer"]} for q in new_rows[:5]]}
        out = Path(args.report) if args.report else REPORT
        out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        print("报告 →", out)
    else:
        print("（dry-run，未写库）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
