#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""本地教材题库 v1 · 确定性层（AI 调用 = 0）

输入（全部只读，均为已冻结的正式资源）：
  structured/audio/resources/audio_resource_v1.json   教材音频资源层（54 MP3 → 文本 → 时间 → 能力）
  structured/contentpack/v5/…sqlite                   教材正式数据（词汇/短语/句型/文本块/活动/练习）
  structured/exercises/exercise_catalog_v3.json       教材原生练习（157 条，无可靠答案）
  structured/exercises/exercise_question_relations_v3.json  教材重建题（360 条，无可靠答案）
  demo/practice_v2.py（只读复用）                      既有确定性题型生成（听音写词/音标写词/词形变化）

输出：
  structured/questionbank/questionbank.db             独立题库（与 learning.db 分离）

原则：
  * 只用教材正式资源 + 明确规则生成题目；**不调用 AI**（ai_calls = 0）；
  * 没有可靠答案的教材原生习题照原样入库，answer_status=NO_RELIABLE_SOURCE，绝不伪造答案；
  * 每道题必须有 primary 教材证据（question_asset.role=primary）；
  * 有多少可靠资源就生成多少题，不设数量指标，不为凑题型而造题。
"""

from __future__ import annotations

import datetime
import hashlib
import json
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
CONTENTPACK = BASE / "structured" / "contentpack" / "v5" / "FLTRP-EN-7A-2022CUR.sqlite"
AUDIO_LAYER = BASE / "structured" / "audio" / "resources" / "audio_resource_v1.json"
EXERCISE_CATALOG = BASE / "structured" / "exercises" / "exercise_catalog_v3.json"
REBUILT_QUESTIONS = BASE / "structured" / "exercises" / "exercise_question_relations_v3.json"
DB_PATH = BASE / "structured" / "questionbank" / "questionbank.db"

RULES_VERSION = "questionbank-rules-v1"
PROMPT_VERSION = "none-deterministic-v1"
RUN_ID = "RUN-DETERMINISTIC-V1"

DOMAIN_BY_TYPE = {
    "vocab_listen_write": "vocabulary",
    "vocab_phonetic_write": "vocabulary",
    "vocab_meaning_choice": "vocabulary",
    "vocab_word_form": "vocabulary",
    "sentence_listen_write": "listening",
    "textbook_native": "textbook",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS question(
  question_id TEXT PRIMARY KEY, question_type TEXT NOT NULL, domain TEXT NOT NULL,
  unit_code TEXT, section_key TEXT, activity_id TEXT, source_item_id TEXT,
  prompt_json TEXT NOT NULL, options_json TEXT, answer_json TEXT,
  answer_kind TEXT NOT NULL, answer_status TEXT NOT NULL, origin TEXT NOT NULL,
  generation_run_id TEXT, rules_version TEXT, prompt_version TEXT,
  quality_status TEXT NOT NULL, review_status TEXT NOT NULL, content_hash TEXT NOT NULL UNIQUE,
  created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS question_asset(
  question_id TEXT NOT NULL, asset_kind TEXT NOT NULL, asset_id TEXT NOT NULL,
  role TEXT NOT NULL, evidence_quote TEXT,
  PRIMARY KEY(question_id, asset_kind, asset_id, role));
CREATE TABLE IF NOT EXISTS generation_run(
  run_id TEXT PRIMARY KEY, generator TEXT, model TEXT, prompt_version TEXT, rules_version TEXT,
  input_digest TEXT, ai_calls INTEGER, started_at TEXT, finished_at TEXT, status TEXT);
CREATE TABLE IF NOT EXISTS quality_review(
  review_id TEXT PRIMARY KEY, question_id TEXT, layer TEXT, verdict TEXT,
  reasons_json TEXT, reviewer TEXT, reviewed_at TEXT);
CREATE TABLE IF NOT EXISTS supplement_task(
  task_id TEXT PRIMARY KEY, kind TEXT, unit_code TEXT, resource_ref TEXT,
  reason TEXT, status TEXT, created_at TEXT);
CREATE INDEX IF NOT EXISTS idx_question_unit ON question(unit_code);
CREATE INDEX IF NOT EXISTS idx_question_type ON question(question_type);
CREATE INDEX IF NOT EXISTS idx_asset_question ON question_asset(question_id);
"""


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _norm(text) -> str:
    t = unicodedata.normalize("NFC", str(text or ""))
    t = t.replace("\u2019", "'").replace("\u2018", "'")
    return re.sub(r"\s+", " ", t).strip().lower()


def _qid(kind: str, unit: str, source: str, prompt: str) -> str:
    raw = "|".join([kind, unit or "", source or "", _norm(prompt)])
    return "Q:" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12].upper()


def _content_hash(kind: str, unit: str, source: str, prompt: str, answer) -> str:
    raw = "|".join([kind, unit or "", source or "", _norm(prompt), _norm(json.dumps(answer, ensure_ascii=False))])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


class Bank:
    """题库写入器：内部按 content_hash 去重，并记录质量检查结果。"""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.hashes: set = set()
        self.questions: list = []
        self.assets: dict = {}
        self.notes: list = []
        self.dup = 0

    def add(self, *, kind: str, unit: str, section: str, activity_id, source_item_id,
            prompt: dict, options, answer, answer_kind: str, answer_status: str, origin: str,
            assets: list, quality_status="PASS", review_status="AUTO_ACCEPTED",
            source_ref: str = "") -> bool:
        prompt_text = prompt.get("text") or prompt.get("instruction") or ""
        chash = _content_hash(kind, unit, source_ref or (str(source_item_id) or ""), prompt_text, answer)
        if chash in self.hashes:
            self.dup += 1
            self.notes.append(("duplicate", kind, unit, prompt_text[:60]))
            return False
        self.hashes.add(chash)
        qid = _qid(kind, unit, source_ref or (str(source_item_id) or ""), prompt_text)
        now = _now()
        self.conn.execute(
            "INSERT OR REPLACE INTO question(question_id, question_type, domain, unit_code, section_key, "
            "activity_id, source_item_id, prompt_json, options_json, answer_json, answer_kind, "
            "answer_status, origin, generation_run_id, rules_version, prompt_version, quality_status, "
            "review_status, content_hash, created_at, updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (qid, kind, DOMAIN_BY_TYPE.get(kind, "other"), unit, section, activity_id, source_item_id,
             json.dumps(prompt, ensure_ascii=False), json.dumps(options or [], ensure_ascii=False),
             json.dumps(answer, ensure_ascii=False) if answer is not None else None,
             answer_kind, answer_status, origin, RUN_ID, RULES_VERSION, PROMPT_VERSION,
             quality_status, review_status, chash, now, now))
        self.assets[qid] = assets
        self.questions.append({"question_id": qid, "question_type": kind, "unit_code": unit,
                               "prompt": prompt_text, "answer": answer, "answer_kind": answer_kind,
                               "answer_status": answer_status, "origin": origin,
                               "options": options or [], "assets": assets})
        return True

    def add_supplement(self, kind: str, unit: str, ref: str, reason: str) -> None:
        tid = "ST:" + hashlib.sha1(("|".join([kind, unit or "", ref, reason])).encode("utf-8")).hexdigest()[:12].upper()
        self.conn.execute(
            "INSERT OR REPLACE INTO supplement_task(task_id, kind, unit_code, resource_ref, reason, "
            "status, created_at) VALUES(?,?,?,?,?,?,?)",
            (tid, kind, unit, ref, reason, "AI_SUPPLEMENT_REQUIRED", _now()))

    def flush_assets(self) -> None:
        for qid, assets in self.assets.items():
            for a in assets:
                self.conn.execute(
                    "INSERT OR REPLACE INTO question_asset(question_id, asset_kind, asset_id, role, "
                    "evidence_quote) VALUES(?,?,?,?,?)",
                    (qid, a.get("asset_kind"), a.get("asset_id"), a.get("role"), a.get("evidence_quote")))


def build_vocabulary(conn, bank: Bank) -> None:
    """词汇确定性题：听音写词 / 音标写词 / 词义选择（全部由正式数据可判定）。"""
    cp = sqlite3.connect("file:%s?mode=ro" % CONTENTPACK.as_posix(), uri=True)
    cp.row_factory = sqlite3.Row
    layer = json.loads(AUDIO_LAYER.read_text(encoding="utf-8"))
    # 词条 → 官方词表音频段（learning_item 资源）
    word_seg: dict = {}
    for r in layer["audio_resources"]:
        if r["resource_type"] != "wordlist_audio":
            continue
        for s in r["segments"]:
            if s["text_resource_kind"] == "learning_item" and s["text_resource_id"]:
                word_seg[s["text_resource_id"]] = {
                    "audio_code": r["audio_code"], "audio_asset_id": r["audio_asset_id"],
                    "audio_url": "/audio/official/%s.mp3" % r["audio_code"],
                    "wav_url": "/audio/word/%s.wav" % (s["alignment_evidence"] or {}).get("key", ""),
                    "start_ms": s["start_ms"], "end_ms": s["end_ms"],
                    "wav_path": (s["alignment_evidence"] or {}).get("wav_path")}

    rows = list(cp.execute(
        "SELECT item_id, canonical_text, meaning_zh, phonetic, part_of_speech, learning_requirement "
        "FROM learning_item WHERE item_type='vocabulary' ORDER BY item_id"))
    attr = {}
    try:
        sys.path.insert(0, str(BASE / "web"))
        import content as content_mod                    # noqa: E402
        attr = content_mod._attribution(cp)
    except Exception:                                    # noqa: BLE001
        attr = {}

    by_unit: dict = {}
    for r in rows:
        unit = (attr.get(r["item_id"]) or {}).get("unit_code")
        by_unit.setdefault(unit, []).append(r)

    for r in rows:
        item_id = r["item_id"]
        word = (r["canonical_text"] or "").strip()
        unit = (attr.get(item_id) or {}).get("unit_code")
        meaning = (r["meaning_zh"] or "").strip()
        phonetic = (r["phonetic"] or "").strip()
        seg = word_seg.get(item_id)
        if not word:
            continue

        # 1) 听音写词：官方词表音频段 + 教材词形（normalized）
        if seg and seg.get("wav_url") and not seg["wav_url"].endswith("/.wav"):
            bank.add(kind="vocab_listen_write", unit=unit, section="WORDS_AND_EXPRESSIONS",
                     activity_id=None, source_item_id=item_id,
                     prompt={"instruction": "听音写词：写出你听到的单词。", "audio_url": seg["wav_url"],
                             "audio_source_code": seg["audio_code"], "start_ms": seg["start_ms"],
                             "end_ms": seg["end_ms"]},
                     options=[], answer={"text": word}, answer_kind="normalized",
                     answer_status="RELIABLE", origin="PROGRAM_GENERATED",
                     assets=[{"asset_kind": "learning_item", "asset_id": item_id, "role": "primary",
                              "evidence_quote": word},
                             {"asset_kind": "audio", "asset_id": seg["audio_asset_id"],
                              "role": "audio_source",
                              "evidence_quote": "%d-%d ms" % (seg["start_ms"] or 0, seg["end_ms"] or 0)}],
                     source_ref=item_id)

        # 2) 音标写词：仅在有正式音标时（不凭空补音标）
        if phonetic and unit:
            bank.add(kind="vocab_phonetic_write", unit=unit, section="WORDS_AND_EXPRESSIONS",
                     activity_id=None, source_item_id=item_id,
                     prompt={"instruction": "看音标写单词。", "phonetic": phonetic,
                             "part_of_speech": r["part_of_speech"] or ""},
                     options=[], answer={"text": word}, answer_kind="normalized",
                     answer_status="RELIABLE", origin="PROGRAM_GENERATED",
                     assets=[{"asset_kind": "learning_item", "asset_id": item_id, "role": "primary",
                              "evidence_quote": "%s %s" % (word, phonetic)}],
                     source_ref=item_id)

        # 3) 词义选择：干扰项来自同一 Unit 的其它教材词释义（可靠、同阶段）
        pool = [x for x in (by_unit.get(unit) or []) if x["item_id"] != item_id
                and (x["meaning_zh"] or "").strip() and (x["meaning_zh"] or "").strip() != meaning]
        if meaning and len(pool) >= 2:
            opts = [(item_id, meaning)] + [(x["item_id"], x["meaning_zh"].strip()) for x in pool[:3]]
            letters = "abcd"
            options = [{"key": letters[i], "text": t, "asset_id": aid} for i, (aid, t) in enumerate(opts)]
            bank.add(kind="vocab_meaning_choice", unit=unit, section="WORDS_AND_EXPRESSIONS",
                     activity_id=None, source_item_id=item_id,
                     prompt={"instruction": "选择与教材词表一致的词义。", "text": word},
                     options=options, answer={"key": "a", "text": meaning}, answer_kind="option_key",
                     answer_status="RELIABLE", origin="PROGRAM_GENERATED",
                     assets=[{"asset_kind": "learning_item", "asset_id": item_id, "role": "primary",
                              "evidence_quote": "%s —— %s" % (word, meaning)}]
                     + [{"asset_kind": "learning_item", "asset_id": aid, "role": "distractor_basis",
                         "evidence_quote": t} for aid, t in opts[1:]],
                     source_ref=item_id)
    cp.close()


def build_word_forms(conn, bank: Bank) -> None:
    """词形变化：复用 Demo 既有确定性规则（教材原句挖空 + 教材词形为答案）。"""
    sys.path.insert(0, str(BASE / "demo"))
    sys.path.insert(0, str(BASE / "web"))
    import server as demo_server                        # noqa: E402
    import practice_v2 as p2                            # noqa: E402

    cp = sqlite3.connect("file:%s?mode=ro" % CONTENTPACK.as_posix(), uri=True)
    cp.row_factory = sqlite3.Row
    blocks = {}
    for r in cp.execute("SELECT block_id, text_raw FROM content_block"):
        key = _norm(r["text_raw"])
        if key:
            blocks.setdefault(key, set()).add(r["block_id"])
    cp.close()

    for unit in demo_server.units():
        for lesson in demo_server.lessons(unit):
            if not any(lesson["counts"].values()):
                continue
            for task in (p2.form_tasks(unit, lesson) or []):
                form = (task.get("form") or "").strip()
                prompt = (task.get("prompt") or "").strip()
                if not form or "______" not in prompt:
                    continue
                sentence = prompt.replace("______", form)
                hits = blocks.get(_norm(sentence)) or set()
                if len(hits) != 1:
                    continue                              # 无唯一教材依据 → 不入库
                block = next(iter(hits))
                bank.add(kind="vocab_word_form", unit=unit["unit_code"], section=lesson["key"],
                         activity_id=None, source_item_id=task.get("base"),
                         prompt={"instruction": "用正确的词形补全教材句子。", "text": prompt,
                                 "base": task.get("base"), "part_of_speech": task.get("pos") or ""},
                         options=[], answer={"text": form}, answer_kind="exact",
                         answer_status="RELIABLE", origin="PROGRAM_GENERATED",
                         assets=[{"asset_kind": "content_block", "asset_id": block, "role": "primary",
                                  "evidence_quote": sentence[:120]}],
                         source_ref=block)


def build_sentence_dictation(conn, bank: Bank) -> dict:
    """句子听写：只用音频资源层的 VERIFIED 句级段（精确时间 + 教材文本 block）。"""
    stats = {"added": 0, "skipped_not_single_sentence": 0, "skipped_length": 0}
    layer = json.loads(AUDIO_LAYER.read_text(encoding="utf-8"))
    cp = sqlite3.connect("file:%s?mode=ro" % CONTENTPACK.as_posix(), uri=True)
    cp.row_factory = sqlite3.Row
    block_text = {r["block_id"]: (r["text_raw"] or "") for r in cp.execute("SELECT block_id, text_raw FROM content_block")}
    cp.close()

    for res in layer["audio_resources"]:
        for s in res["segments"]:
            if s["status"] != "VERIFIED" or s["text_resource_kind"] != "content_block":
                continue
            block = s["text_resource_id"]
            text = (block_text.get(block) or "").strip()
            # 只接受"干净的单句教材文本"：排除页码/编号残留、多句拼接、对话块
            if re.match(r"^\d+\b", text) or re.search(r"[.!?]\s+[A-Z\"']", text):
                stats["skipped_not_single_sentence"] += 1
                continue
            words = re.findall(r"[A-Za-z][A-Za-z'\-]*", text)
            if not text or not (4 <= len(words) <= 40) or len(text) > 200:
                stats["skipped_length"] += 1
                continue                                  # 过短/过长都不做听写题
            added = bank.add(
                kind="sentence_listen_write", unit=res.get("unit_code"),
                section=res.get("section_key"), activity_id=res.get("activity_id"),
                source_item_id=None,
                prompt={"instruction": "听音写句：写出你听到的教材句子。",
                        "audio_url": "/audio/official/%s.mp3" % res["audio_code"],
                        "start_ms": s["start_ms"], "end_ms": s["end_ms"]},
                options=[], answer={"text": text}, answer_kind="normalized",
                answer_status="RELIABLE", origin="PROGRAM_GENERATED",
                assets=[{"asset_kind": "content_block", "asset_id": block, "role": "primary",
                         "evidence_quote": text[:120]},
                        {"asset_kind": "audio", "asset_id": res["audio_asset_id"],
                         "role": "audio_source",
                         "evidence_quote": "%d-%d ms" % (s["start_ms"] or 0, s["end_ms"] or 0)}],
                source_ref="%s:%s" % (res["audio_code"], block))
            if added:
                stats["added"] += 1
    return stats


def import_textbook_native(conn, bank: Bank) -> dict:
    """教材原生习题入库：结构照搬，答案不伪造（answer_status=NO_RELIABLE_SOURCE）。"""
    stats = {"catalog": 0, "rebuilt": 0, "no_evidence": 0, "excluded_no_primary": 0,
             "invalid_activity_ref": 0}
    cp = sqlite3.connect("file:%s?mode=ro" % CONTENTPACK.as_posix(), uri=True)
    valid_activity = {r[0] for r in cp.execute("SELECT activity_id FROM activity")}
    valid_block = {r[0] for r in cp.execute("SELECT block_id FROM content_block")}
    valid_section = {r[0] for r in cp.execute("SELECT section_id FROM section")}
    cp.close()

    def assets_for(activity_id, related_text, section_id=None):
        """只用真实存在的正式 ID 作证据；找不到 primary 证据就整题不入库。"""
        out = []
        if activity_id and activity_id in valid_activity:
            out.append({"asset_kind": "activity", "asset_id": activity_id, "role": "primary",
                        "evidence_quote": ""})
        if not out and section_id and section_id in valid_section:
            out.append({"asset_kind": "section", "asset_id": section_id, "role": "primary",
                        "evidence_quote": "教材板块级证据"})
        extra = [b for b in (related_text or []) if b in valid_block]
        for i, bid in enumerate(extra):
            role = "primary" if not out and i == 0 else "support"
            out.append({"asset_kind": "content_block", "asset_id": bid, "role": role,
                        "evidence_quote": ""})
        return out

    catalog = json.loads(EXERCISE_CATALOG.read_text(encoding="utf-8"))
    for e in catalog.get("exercises") or []:
        q = (e.get("questions") or [{}])[0]
        text = (q.get("text") or e.get("instruction") or "").strip()
        if not text:
            stats["no_evidence"] += 1
            continue
        activity_id = e.get("activity_id")
        if activity_id and activity_id not in valid_activity:
            stats["invalid_activity_ref"] += 1
            activity_id = None
        assets = assets_for(activity_id, [], e.get("section_id"))
        if not any(a["role"] == "primary" for a in assets):
            stats["excluded_no_primary"] += 1
            continue
        options = e.get("options") or []
        kind = (e.get("question_type") or e.get("type") or "other")
        open_like = kind in ("short_answer", "writing", "speaking", "reflection", "other")
        if bank.add(kind="textbook_native", unit=e.get("unit"), section=e.get("section"),
                    activity_id=activity_id, source_item_id=e.get("exercise_id"),
                    prompt={"instruction": e.get("instruction") or "", "text": text,
                            "question_type": kind, "in_contentpack_activity": e.get("in_contentpack_activity")},
                    options=options, answer=None,
                    answer_kind="self_assess" if open_like else "ai_eval",
                    answer_status="NO_RELIABLE_SOURCE", origin="TEXTBOOK_NATIVE",
                    assets=assets, quality_status="PASS", review_status="PENDING_REVIEW",
                    source_ref=e.get("exercise_id") or ""):
            stats["catalog"] += 1

    rebuilt = json.loads(REBUILT_QUESTIONS.read_text(encoding="utf-8"))
    for q in rebuilt.get("questions") or []:
        text = (q.get("text") or "").strip()
        if not text:
            stats["no_evidence"] += 1
            continue
        activity_id = q.get("activity_id")
        if activity_id and activity_id not in valid_activity:
            stats["invalid_activity_ref"] += 1
            activity_id = None                       # 该 id 不在正式教材结构中：不写入 activity_id
        assets = assets_for(activity_id, q.get("related_text"), q.get("section_id"))
        if not any(a["role"] == "primary" for a in assets):
            stats["excluded_no_primary"] += 1
            continue
        kind = q.get("question_type") or "other"
        open_like = kind in ("short_answer", "writing", "speaking", "reflection", "other")
        if bank.add(kind="textbook_native", unit=q.get("unit"), section=q.get("section"),
                    activity_id=activity_id, source_item_id=q.get("question_id"),
                    prompt={"text": text, "question_type": kind, "blank_count": q.get("blank_count"),
                            "source_activity_ref": q.get("activity_id"),
                            "source_section_id": q.get("section_id")},
                    options=q.get("options") or [], answer=None,
                    answer_kind="self_assess" if open_like else "ai_eval",
                    answer_status="NO_RELIABLE_SOURCE", origin="TEXTBOOK_NATIVE",
                    assets=assets, quality_status="PASS", review_status="PENDING_REVIEW",
                    source_ref=q.get("question_id") or ""):
            stats["rebuilt"] += 1
    return stats


def record_gaps(conn, bank: Bank, sentence_stats: dict = None) -> dict:
    """把确定性层无法解决的缺口写成待 AI 补足任务（本轮不调用 AI）。"""
    layer = json.loads(AUDIO_LAYER.read_text(encoding="utf-8"))
    catalog = json.loads(EXERCISE_CATALOG.read_text(encoding="utf-8"))
    gaps = {"sentence_distractors": 0, "listening_understanding": 0, "open_answer": 0,
            "writing_speaking": 0, "phonetics_text": 0, "reading_comprehension": 0}
    for res in layer["audio_resources"]:
        if res["resource_type"] == "phonetics_audio":
            bank.add_supplement("phonetics_text", res.get("unit_code"), res["audio_code"],
                                "Phonetics in use 无结构化教材文本与活动映射，无法确定性出题")
            gaps["phonetics_text"] += 1
            continue
        caps = [c["name"] for c in res.get("capabilities") or []]
        if res["alignment_status"] == "PARTIAL" and any(
                c in caps for c in ("listen_fill", "listen_order", "listen_understanding",
                                    "listen_detail", "listen_information_extraction")):
            bank.add_supplement("listening_understanding", res.get("unit_code"), res["audio_code"],
                                "仅有 ASR 粗定位，理解/补全/排序题需 AI 在教材文本边界内补足")
            gaps["listening_understanding"] += 1
        if res["alignment_status"] in ("VERIFIED", "PARTIAL") and "shadowing" in caps:
            bank.add_supplement("sentence_distractors", res.get("unit_code"), res["audio_code"],
                                "句子听辨/选择需要合格干扰项（本轮不生成）")
            gaps["sentence_distractors"] += 1
    for e in catalog.get("exercises") or []:
        kind = (e.get("question_type") or e.get("type") or "")
        if kind in ("short_answer", "other", "reflection"):
            gaps["open_answer"] += 1
        if kind in ("writing", "speaking"):
            gaps["writing_speaking"] += 1
        if kind in ("listening", "choice"):
            gaps["reading_comprehension"] += 1
    if gaps["open_answer"]:
        bank.add_supplement("open_answer", None, "exercise_catalog_v3",
                            "教材原生开放题无可靠答案：需 AI 评价或自评（%d 条）" % gaps["open_answer"])
    if gaps["writing_speaking"]:
        bank.add_supplement("writing_speaking", None, "exercise_catalog_v3",
                            "教材写作/口语活动需 AI 评价（%d 条）" % gaps["writing_speaking"])
    if gaps["reading_comprehension"]:
        bank.add_supplement("reading_comprehension", None, "exercise_catalog_v3",
                            "听力/阅读选择题无可靠答案：需 AI 在教材文本边界内补足（%d 条）" % gaps["reading_comprehension"])
    if sentence_stats:
        skipped = sentence_stats.get("skipped_not_single_sentence", 0) + sentence_stats.get("skipped_length", 0)
        if skipped:
            bank.add_supplement("sentence_segmentation", None, "audio_resource_v1",
                                "已验证句级资源中有 %d 段是多句/对话/超长文本，需程序切分或 AI 在教材文本边界内加工"
                                % skipped)
            gaps["sentence_segmentation"] = skipped
    return gaps


def quality_check(conn: sqlite3.Connection) -> dict:
    """题库自动质量检查（§十六）：引用真实性、evidence、答案、重复、选项、长度。"""
    conn.row_factory = sqlite3.Row
    cp = sqlite3.connect("file:%s?mode=ro" % CONTENTPACK.as_posix(), uri=True)
    valid = {
        "content_block": {r[0] for r in cp.execute("SELECT block_id FROM content_block")},
        "learning_item": {r[0] for r in cp.execute("SELECT item_id FROM learning_item")},
        "activity": {r[0] for r in cp.execute("SELECT activity_id FROM activity")},
        "section": {r[0] for r in cp.execute("SELECT section_id FROM section")},
        "audio": {r[0] for r in cp.execute("SELECT audio_id FROM audio_asset")},
    }
    cp.close()
    layer = json.loads(AUDIO_LAYER.read_text(encoding="utf-8"))
    valid["audio_layer_code"] = {r["audio_code"] for r in layer["audio_resources"]}

    report = {"questions": 0, "missing_primary_evidence": [], "missing_answer": [],
              "fake_answer_on_unreliable": [], "invalid_reference": [], "invalid_choice": [],
              "abnormal_length": [], "duplicate_content_hash": [], "by_unit": {}, "by_domain": {},
              "by_type": {}, "by_answer_status": {}, "by_origin": {}}
    seen_hash = {}
    for q in conn.execute("SELECT * FROM question"):
        report["questions"] += 1
        qid = q["question_id"]
        report["by_unit"][q["unit_code"]] = report["by_unit"].get(q["unit_code"], 0) + 1
        report["by_domain"][q["domain"]] = report["by_domain"].get(q["domain"], 0) + 1
        report["by_type"][q["question_type"]] = report["by_type"].get(q["question_type"], 0) + 1
        report["by_answer_status"][q["answer_status"]] = report["by_answer_status"].get(q["answer_status"], 0) + 1
        report["by_origin"][q["origin"]] = report["by_origin"].get(q["origin"], 0) + 1
        if q["content_hash"] in seen_hash:
            report["duplicate_content_hash"].append(qid)
        seen_hash[q["content_hash"]] = qid

        assets = list(conn.execute("SELECT * FROM question_asset WHERE question_id=?", (qid,)))
        if not any(a["role"] == "primary" for a in assets):
            report["missing_primary_evidence"].append(qid)
        for a in assets:
            if a["asset_kind"] == "audio":
                if a["asset_id"] not in valid["audio"]:
                    report["invalid_reference"].append([qid, a["asset_kind"], a["asset_id"]])
            elif a["asset_kind"] in valid and a["asset_id"] not in valid[a["asset_kind"]]:
                if a["asset_id"]:
                    report["invalid_reference"].append([qid, a["asset_kind"], a["asset_id"]])

        answer = json.loads(q["answer_json"]) if q["answer_json"] else None
        if q["answer_status"] == "RELIABLE":
            if not answer:
                report["missing_answer"].append(qid)
        elif answer:                                      # 无可靠来源却写了答案 = 伪造风险
            report["fake_answer_on_unreliable"].append(qid)
        if q["answer_kind"] == "option_key":
            options = json.loads(q["options_json"] or "[]")
            keys = [o.get("key") for o in options]
            texts = [_norm(o.get("text")) for o in options]
            if (len(options) < 2 or answer is None or answer.get("key") not in keys
                    or len(set(texts)) != len(texts)):
                report["invalid_choice"].append(qid)
        prompt = json.loads(q["prompt_json"] or "{}")
        text = (prompt.get("text") or prompt.get("instruction") or "")
        limit = 2000 if q["origin"] == "TEXTBOOK_NATIVE" else 600
        if len(text) > limit or len(text) < 3:
            report["abnormal_length"].append(qid)
    return report


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if DB_PATH.exists():
        DB_PATH.unlink()                                  # 每次重建为确定性产物（不删任何上游资源）
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.executescript(SCHEMA)
    started = _now()
    digest = hashlib.sha256()
    for p in (AUDIO_LAYER, CONTENTPACK, EXERCISE_CATALOG, REBUILT_QUESTIONS):
        digest.update(p.read_bytes())
    conn.execute("INSERT OR REPLACE INTO generation_run(run_id, generator, model, prompt_version, "
                 "rules_version, input_digest, ai_calls, started_at, finished_at, status) "
                 "VALUES(?,?,?,?,?,?,?,?,?,?)",
                 (RUN_ID, "deterministic", "none", PROMPT_VERSION, RULES_VERSION,
                  digest.hexdigest()[:16], 0, started, "", "running"))

    bank = Bank(conn)
    build_vocabulary(conn, bank)
    build_word_forms(conn, bank)
    sentence_stats = build_sentence_dictation(conn, bank)
    stats = import_textbook_native(conn, bank)
    gaps = record_gaps(conn, bank, sentence_stats)
    bank.flush_assets()
    conn.execute("UPDATE generation_run SET finished_at=?, status=? WHERE run_id=?",
                 (_now(), "PASS", RUN_ID))

    report = quality_check(conn)
    for key in ("missing_primary_evidence", "missing_answer", "fake_answer_on_unreliable",
                "invalid_reference", "invalid_choice", "abnormal_length", "duplicate_content_hash"):
        verdict = "PASS" if not report[key] else "ISSUE"
        conn.execute("INSERT OR REPLACE INTO quality_review(review_id, question_id, layer, verdict, "
                     "reasons_json, reviewer, reviewed_at) VALUES(?,?,?,?,?,?,?)",
                     ("QR:%s" % key, None, "deterministic", verdict,
                      json.dumps(report[key][:50], ensure_ascii=False), "builder", _now()))
    conn.commit()

    print("题库 →", DB_PATH)
    print("总题目:", report["questions"], "| 去重丢弃:", bank.dup)
    print("origin:", report["by_origin"])
    print("domain:", report["by_domain"])
    print("类型:", report["by_type"])
    print("答案状态:", report["by_answer_status"])
    print("按 Unit:", report["by_unit"])
    print("教材原生导入:", stats)
    print("质量检查:", {k: len(v) for k, v in report.items() if isinstance(v, list)})
    print("待 AI 补足:", gaps)
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
