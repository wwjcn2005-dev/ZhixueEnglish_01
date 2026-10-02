#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P4-01 · 题库确定性增量建设（P3-08 VERIFIED 句段 → 正式题库，AI 调用 = 0）

本脚本在**现有正式题库基础上增量写入**，不重建、不覆盖、不删除任何已有题目。

资源边界（严格）：
  * 只用 `alignment_status = VERIFIED` 音频资源里 **P3-08 新增的精确句段**
    （`alignment_method = p3_07_deep_review_boundary_pass`，时间边界已核对）；
  * 不用 rough/PARTIAL 段，不用 PARTIAL 音频（AU25），不用 6 个 Phonetics（NEED_MANUAL_CONFIRMATION）；
  * 不用 ASR 转写当答案：答案文本必须能在正式 contentpack `content_block.text_raw` 中定位；
  * 不跨 Unit 取资源。

只生成“能确定判定”的题型（见 ALLOWED_TYPES）。本次实际产生增量的题型：
  A. sentence_listen_write —— 官方音频 + P3-08 精确句段 + 教材原文可直接判定
其余题型（fill / choice / judge / order / match / information / main_idea）
因教材未提供可核对答案来源，本次保持 0 题（逐条理由写进报告）。

复用（不重造）：
  * 题目 id / content_hash / 文本归一化：`builder/build_questionbank_v01.py` 的 `_qid` / `_content_hash` / `_norm`
  * 句段来源与边界：P3-07 matched_candidates + P3-08 边界加工（不重算、不重跑 ASR）
  * 教材句切分：`audit/P3-07_preview/scan_preview_inputs.py::split_english_sentences` 的产物（matched.textbook_text）

运行：
  python D:\ZhixueEnglish\builder\build_questionbank_audio_increment_v01.py
"""

from __future__ import annotations

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
LAYER = BASE / "structured" / "audio" / "resources" / "audio_resource_v1.json"
MATCHED = BASE / "audit" / "P3-07_preview" / "matched_candidates.json"
CONTENTPACK = BASE / "structured" / "contentpack" / "v5" / "FLTRP-EN-7A-2022CUR.sqlite"
CATALOG = BASE / "structured" / "exercises" / "exercise_catalog_v3.json"
REPORT = BASE / "audit" / "P4-01_questionbank_audio_increment_report.json"

STEP = "builder/build_questionbank_audio_increment_v01.py"
RUN_ID = "RUN-AUDIO-INCREMENT-V1"
RULES_VERSION = "questionbank-rules-v2"          # 新增句级听写规则集（v1 题目保持不动）
PROMPT_VERSION = "none-deterministic-v1"
DEEP_METHOD = "p3_07_deep_review_boundary_pass"

ALLOWED_TYPES = ("sentence_listen_write", "listening_fill", "listening_choice", "listening_judge",
                 "listening_order", "listening_match", "listening_information", "listening_main_idea")
DOMAIN = {"sentence_listen_write": "listening", "listening_fill": "listening",
          "listening_choice": "listening", "listening_judge": "listening",
          "listening_order": "listening", "listening_match": "listening",
          "listening_information": "listening", "listening_main_idea": "listening"}

#: 答案不能以这些虚词/功能词结尾 —— 说明教材这里是“写作框/未完成句”，不是完整句子
DANGLING_TAIL = {"to", "in", "about", "of", "for", "with", "and", "but", "or", "the", "a", "an",
                 "my", "your", "his", "her", "their", "our", "its", "is", "are", "be", "at", "on",
                 "by", "from", "that", "this", "have", "has", "do", "does"}
ALLOWED_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 "
                    ".,!?'\u2019\u2018-:\u2013\u2014\u201c\u201d()")


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _load_v01():
    """复用 v01 的 id / content_hash / 归一化实现（不复制、不改写）。"""
    path = BASE / "builder" / "build_questionbank_v01.py"
    spec = importlib.util.spec_from_file_location("qb_v01_for_increment", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _norm(text) -> str:
    t = unicodedata.normalize("NFC", str(text or ""))
    t = t.replace("\u2019", "'").replace("\u2018", "'")
    return re.sub(r"\s+", " ", t).strip().lower()


def _words(text: str) -> list:
    return re.findall(r"[A-Za-z][A-Za-z'\-]*", text or "")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    v01 = _load_v01()
    layer = json.loads(LAYER.read_text(encoding="utf-8"))
    matched = {m["sentence_id"]: m for m in json.loads(MATCHED.read_text(encoding="utf-8"))}
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))

    cp = sqlite3.connect("file:%s?mode=ro" % CONTENTPACK.as_posix(), uri=True)
    cp.row_factory = sqlite3.Row
    blocks = {r["block_id"]: dict(r) for r in cp.execute(
        "SELECT block_id, text_raw, block_kind, layout_role FROM content_block")}
    activities = {r["activity_id"]: (r["instruction"] or "") for r in cp.execute(
        "SELECT activity_id, instruction FROM activity")}
    valid_audio = {r[0] for r in cp.execute("SELECT audio_id FROM audio_asset")}
    valid_block = set(blocks)

    # 每个音频的正式活动 instruction（contentpack activity + 教材练习目录），用于识别“活动指令句”
    instruction_pool: dict = defaultdict(set)
    for e in catalog.get("exercises") or []:
        if not e.get("audio_id"):
            continue
        code = e["audio_id"].split(":")[-1]
        instruction_pool[code].add(e.get("instruction") or "")
        if e.get("activity_id") in activities:
            instruction_pool[code].add(activities[e["activity_id"]])
    for r in layer["audio_resources"]:
        if r.get("activity_id") in activities:
            instruction_pool[r["audio_code"]].add(activities[r["activity_id"]])

    # ---------------------------------------------------------------- 现有题库快照（只读）
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    before = {
        "questions": conn.execute("SELECT COUNT(*) FROM question").fetchone()[0],
        "hashes": {r[0] for r in conn.execute("SELECT content_hash FROM question")},
        "signature": hashlib.sha256("".join(
            "%s|%s|%s|%s|%s\n" % (r["question_id"], r["content_hash"], r["answer_json"],
                                  r["prompt_json"], r["question_type"])
            for r in conn.execute("SELECT question_id, content_hash, answer_json, prompt_json, "
                                  "question_type FROM question ORDER BY question_id")
        ).encode("utf-8")).hexdigest(),
        # 已有句级听写的 (unit, 归一化答案) —— 用于避免与旧题重复
        "sentence_answers": set(),
        # 已被题目引用的 (audio_code, start_ms, end_ms)
        "covered_segments": set(),
    }
    for r in conn.execute("SELECT unit_code, answer_json FROM question "
                          "WHERE question_type='sentence_listen_write' AND answer_json IS NOT NULL"):
        try:
            txt = (json.loads(r["answer_json"]) or {}).get("text")
        except ValueError:
            txt = None
        if txt:
            before["sentence_answers"].add((r["unit_code"], _norm(txt)))
    for r in conn.execute("SELECT prompt_json FROM question WHERE prompt_json LIKE '%/audio/official/%'"):
        try:
            p = json.loads(r["prompt_json"]) or {}
        except ValueError:
            continue
        code = (p.get("audio_url") or "").rsplit("/", 1)[-1].replace(".mp3", "")
        if code:
            before["covered_segments"].add((code, p.get("start_ms"), p.get("end_ms")))

    # ---------------------------------------------------------------- 候选计算（题型 A：句子听写）
    reject = Counter()
    reject_examples = defaultdict(list)
    candidates = []
    p308_segments = []

    def _rej(reason: str, code: str, text: str):
        reject[reason] += 1
        if len(reject_examples[reason]) < 3:
            reject_examples[reason].append({"audio_code": code, "text": (text or "")[:90]})

    for res in layer["audio_resources"]:
        if res.get("alignment_status") != "VERIFIED":
            continue                       # 只处理 VERIFIED 音频（PARTIAL / Phonetics 一律不用）
        pool = {_norm(x) for x in instruction_pool.get(res["audio_code"], set()) if x}
        for s in res["segments"]:
            if s.get("alignment_method") != DEEP_METHOD:
                continue                   # 本次只加工 P3-08 新增精确句段
            p308_segments.append((res, s))
            sid = (s.get("alignment_evidence") or {}).get("sentence_id")
            row = matched.get(sid)
            text = (row or {}).get("textbook_text") or ""
            code = res["audio_code"]
            blk = blocks.get(s.get("text_resource_id")) or {}
            block_text = _norm(blk.get("text_raw"))
            norm_text = _norm(text)

            # 1) 教材原文可追溯（答案必须能在正式 content_block 中定位）
            if not norm_text or norm_text not in block_text:
                _rej("answer_not_in_textbook_text", code, text)
                continue
            pos = block_text.find(norm_text)
            if block_text[pos + len(norm_text):pos + len(norm_text) + 1] in (".", "\u2026"):
                _rej("textbook_ellipsis_frame", code, text)      # 教材写作框（…）
                continue
            # 2) 只取教材正文块（排除活动指令块 / 标题 / 侧栏提示）
            if blk.get("block_kind") not in ("exercise_item", "dialogue") \
                    or blk.get("layout_role") != "body":
                _rej("non_content_block:%s" % blk.get("block_kind"), code, text)
                continue
            # 3) 干净单句（沿用 v01 结构规则）
            if re.match(r"^\d+\b", text) or re.search(r"[.!?]\s+[A-Z\"']", text):
                _rej("multi_sentence_or_numbered", code, text)
                continue
            if not (4 <= len(_words(text)) <= 40) or len(text) > 200:
                _rej("abnormal_length", code, text)
                continue
            # 4) 教材印刷体里的“选项对/填空框”不能当答案
            if re.search(r"\([^)]*/[^)]*\)", text) or ": ." in text:
                _rej("printed_alternatives_or_blank_frame", code, text)
                continue
            # 5) 文本完整性（非教材字符 / 单元格粘连 / 引号不配对 / 未完成句）
            if set(text) - ALLOWED_CHARS:
                _rej("textbook_glyph_artifact", code, text)
                continue
            if re.search(r"[a-z][A-Z]", text):
                _rej("merged_table_cells", code, text)
                continue
            if _words(text) and _words(text)[-1].lower() in DANGLING_TAIL:
                _rej("incomplete_writing_frame", code, text)
                continue
            if text.count("\u201c") != text.count("\u201d") or text.startswith("\u201d"):
                _rej("unbalanced_quote", code, text)
                continue
            # 6) 活动指令不是学习内容
            if any(x and norm_text in x for x in pool):
                _rej("activity_instruction_sentence", code, text)
                continue
            candidates.append({"res": res, "seg": s, "row": row, "text": text, "block": s["text_resource_id"]})

    # 同一 Unit 内同句只保留最早出现的一条（避免重复题）
    unique, seen = [], set()
    for c in sorted(candidates, key=lambda x: (x["res"]["unit_code"], x["seg"]["start_ms"] or 0)):
        key = (c["res"]["unit_code"], _norm(c["text"]))
        if key in seen:
            reject["duplicate_sentence_in_unit"] += 1
            if len(reject_examples["duplicate_sentence_in_unit"]) < 3:
                reject_examples["duplicate_sentence_in_unit"].append(
                    {"audio_code": c["res"]["audio_code"], "text": c["text"][:90]})
            continue
        seen.add(key)
        unique.append(c)

    # ---------------------------------------------------------------- 其余题型的证据探测（本次全部为 0，理由留证）
    type_probe = {}
    ex_by_type = defaultdict(list)
    for e in catalog.get("exercises") or []:
        if (e.get("audio_id") or "").split(":")[-1] in {r["audio_code"] for r in layer["audio_resources"]
                                                        if r["alignment_status"] == "VERIFIED"}:
            ex_by_type[e.get("question_type") or "other"].append(e)
    no_answer = "教材未提供可核对答案来源（exercise_catalog_v3.answer_status=NO_RELIABLE_SOURCE）；" \
                "答案只能来自 ASR 或常识推断 → 禁止生成"
    for qtype, task in (("fill", "listening_fill"), ("choice", "listening_choice"),
                        ("judge", "listening_judge"), ("order", "listening_order"),
                        ("match", "listening_match")):
        rows = ex_by_type.get(qtype) or []
        type_probe[task] = {"candidates": len(rows), "accepted": 0, "rejected": len(rows),
                            "reason": no_answer}
    q_rows = [e for e in (catalog.get("exercises") or [])
              if "?" in (e.get("instruction") or "") or (e.get("question_type") == "short_answer")]
    type_probe["listening_information"] = {
        "candidates": len(q_rows), "accepted": 0, "rejected": len(q_rows),
        "reason": "教材只提出问题、未提供答案文本；答案需语义生成 → 属于 AI 补足池（supplement_task: listening_understanding）"}
    type_probe["listening_main_idea"] = {
        "candidates": len([e for e in (catalog.get("exercises") or [])
                           if re.search(r"what is (it|the (passage|story)) about", (e.get("instruction") or ""), re.I)]),
        "accepted": 0, "rejected": 0,
        "reason": "教材无标准答案；不得自行制造主旨题并假装教材已有依据"}

    # ---------------------------------------------------------------- 组装新题（题型 A）
    new_rows, new_assets = [], []
    dup_existing = 0
    for c in unique:
        res, seg, row = c["res"], c["seg"], c["row"]
        text = c["text"]
        if (res["unit_code"], _norm(text)) in before["sentence_answers"]:
            dup_existing += 1
            continue
        prompt = {"instruction": "听音写句：写出你听到的教材句子。",
                  "audio_url": "/audio/official/%s.mp3" % res["audio_code"],
                  "start_ms": seg["start_ms"], "end_ms": seg["end_ms"],
                  "segment_id": seg["segment_id"],                 # 可追溯到资源层句段
                  "boundary_method": DEEP_METHOD}
        answer = {"text": text}
        source_ref = "%s:%s" % (res["audio_code"], seg["segment_id"])
        chash = v01._content_hash("sentence_listen_write", res["unit_code"], source_ref,
                                  prompt["instruction"], answer)
        if chash in before["hashes"]:
            dup_existing += 1
            continue
        qid = v01._qid("sentence_listen_write", res["unit_code"], source_ref, prompt["instruction"])
        assets = [{"asset_kind": "content_block", "asset_id": c["block"], "role": "primary",
                   "evidence_quote": text[:120]},
                  {"asset_kind": "audio", "asset_id": res["audio_asset_id"], "role": "audio_source",
                   "evidence_quote": "%d-%d ms（%s）" % (seg["start_ms"], seg["end_ms"], seg["segment_id"])}]
        new_rows.append({"question_id": qid, "question_type": "sentence_listen_write",
                         "domain": DOMAIN["sentence_listen_write"], "unit_code": res["unit_code"],
                         "section_key": res.get("section_key"), "activity_id": res.get("activity_id"),
                         "source_item_id": None, "prompt": prompt, "answer": answer,
                         "content_hash": chash, "assets": assets,
                         "segment_id": seg["segment_id"], "text_resource_id": c["block"],
                         "audio_asset_id": res["audio_asset_id"], "text": text})

    # ---------------------------------------------------------------- 写入（事务内先写入后门禁，任一不过即回滚）
    now = _now()
    conn.execute("BEGIN")
    for r in new_rows:
        conn.execute(
            "INSERT INTO question(question_id, question_type, domain, unit_code, section_key, "
            "activity_id, source_item_id, prompt_json, options_json, answer_json, answer_kind, "
            "answer_status, origin, generation_run_id, rules_version, prompt_version, "
            "quality_status, review_status, content_hash, created_at, updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (r["question_id"], r["question_type"], r["domain"], r["unit_code"], r["section_key"],
             r["activity_id"], r["source_item_id"], json.dumps(r["prompt"], ensure_ascii=False),
             json.dumps([], ensure_ascii=False), json.dumps(r["answer"], ensure_ascii=False),
             "normalized", "RELIABLE", "PROGRAM_GENERATED", RUN_ID, RULES_VERSION, PROMPT_VERSION,
             "PASS", "AUTO_ACCEPTED", r["content_hash"], now, now))
        for a in r["assets"]:
            conn.execute("INSERT OR REPLACE INTO question_asset(question_id, asset_kind, asset_id, "
                         "role, evidence_quote) VALUES(?,?,?,?,?)",
                         (r["question_id"], a["asset_kind"], a["asset_id"], a["role"],
                          a["evidence_quote"]))
    conn.execute("INSERT OR REPLACE INTO generation_run(run_id, generator, model, prompt_version, "
                 "rules_version, input_digest, ai_calls, started_at, finished_at, status) "
                 "VALUES(?,?,?,?,?,?,?,?,?,?)",
                 (RUN_ID, "deterministic", "none", PROMPT_VERSION, RULES_VERSION,
                  hashlib.sha256((LAYER.read_bytes() + DB_PATH.read_bytes())).hexdigest()[:16],
                  0, now, now, "PASS"))

    # ---------------------------------------------------------------- 质量门禁（§10，16 项）
    gate = {}
    qids = [r["question_id"] for r in new_rows]
    if qids:
        marks = ",".join("?" * len(qids))
        gate["1_primary_evidence"] = conn.execute(
            "SELECT COUNT(*) FROM question q WHERE q.question_id IN (%s) AND NOT EXISTS "
            "(SELECT 1 FROM question_asset a WHERE a.question_id=q.question_id AND a.role='primary')"
            % marks, qids).fetchone()[0] == 0
        gate["3_segment_id_valid"] = all(
            r["segment_id"] in {s["segment_id"] for x in layer["audio_resources"] for s in x["segments"]}
            for r in new_rows)
        gate["4_text_id_valid"] = all(r["text_resource_id"] in valid_block for r in new_rows)
        gate["5_unit_range"] = all(
            next(x for x in layer["audio_resources"] if x["audio_asset_id"] == r["audio_asset_id"])
            ["unit_code"] == r["unit_code"] for r in new_rows)
        gate["6_answer_executable"] = conn.execute(
            "SELECT COUNT(*) FROM question WHERE question_id IN (%s) AND answer_status='RELIABLE' "
            "AND answer_kind IN ('normalized','exact','option_key','check_items')" % marks,
            qids).fetchone()[0] == len(qids)
        gate["7_question_type_legal"] = all(r["question_type"] in ALLOWED_TYPES for r in new_rows)
        gate["12_no_partial_segment"] = all(
            r["segment_id"] not in {s["segment_id"] for x in layer["audio_resources"]
                                    for s in x["segments"] if s["status"] != "VERIFIED"} for r in new_rows)
        gate["13_no_manual_confirmation_audio"] = all(
            next(x for x in layer["audio_resources"] if x["audio_asset_id"] == r["audio_asset_id"])
            ["alignment_status"] != "NEED_MANUAL_CONFIRMATION" for r in new_rows)
        gate["14_no_future_unit"] = all(
            next(x for x in layer["audio_resources"] if x["audio_asset_id"] == r["audio_asset_id"])
            ["unit_code"] == r["unit_code"] for r in new_rows)
        gate["15_no_outside_fact"] = all(
            _norm(r["text"]) in _norm(blocks[r["text_resource_id"]]["text_raw"]) for r in new_rows)
        gate["16_origin_complete"] = conn.execute(
            "SELECT COUNT(*) FROM question WHERE question_id IN (%s) AND origin='PROGRAM_GENERATED' "
            "AND generation_run_id=? AND rules_version=?" % marks, tuple(qids) + (RUN_ID, RULES_VERSION)
        ).fetchone()[0] == len(qids)
    gate["2_audio_id_valid"] = all(r["audio_asset_id"] in valid_audio for r in new_rows)
    gate["8_option_count"] = True          # 本次无选择题
    gate["9_single_correct_option"] = True  # 本次无选择题
    gate["10_no_duplicate_hash"] = conn.execute(
        "SELECT COUNT(*) FROM (SELECT content_hash FROM question GROUP BY content_hash HAVING "
        "COUNT(*)>1)").fetchone()[0] == 0
    gate["11_no_existing_duplicate"] = all(h not in before["hashes"] for h in (r["content_hash"] for r in new_rows))

    failed = [k for k, v in gate.items() if not v]
    if failed:
        conn.rollback()
        print("STOP: 质量门禁未通过，已回滚，题库保持原样：%s" % failed)
        return 3
    conn.commit()

    # ---------------------------------------------------------------- 覆盖统计
    covered_now = {(r["audio_asset_id"].split(":")[-1], r["prompt"]["start_ms"], r["prompt"]["end_ms"])
                   for r in new_rows}
    p308_list = [{"audio_code": x["audio_code"], "segment_id": s["segment_id"],
                  "start_ms": s["start_ms"], "end_ms": s["end_ms"]}
                 for x, s in p308_segments]
    covered_before = [x for x in p308_list
                      if (x["audio_code"], x["start_ms"], x["end_ms"]) in before["covered_segments"]]
    covered_after = [x for x in p308_list if (x["audio_code"], x["start_ms"], x["end_ms"]) in covered_now]
    still_open = [x for x in p308_list if x not in covered_after and x not in covered_before]

    after = {
        "questions": conn.execute("SELECT COUNT(*) FROM question").fetchone()[0],
        "signature_existing": hashlib.sha256("".join(
            "%s|%s|%s|%s|%s\n" % (r["question_id"], r["content_hash"], r["answer_json"],
                                  r["prompt_json"], r["question_type"])
            for r in conn.execute("SELECT question_id, content_hash, answer_json, prompt_json, "
                                  "question_type FROM question WHERE generation_run_id IS NOT "
                                  "'%s' OR generation_run_id IS NULL ORDER BY question_id" % RUN_ID)
        ).encode("utf-8")).hexdigest(),
    }
    by_unit = dict(Counter(r["unit_code"] for r in new_rows))
    by_unit["（合计）"] = len(new_rows)
    report = {
        "step": STEP, "generated_at": now, "ai_calls": 0, "run_id": RUN_ID,
        "rules_version": RULES_VERSION,
        "baseline_questions": before["questions"], "new_questions": len(new_rows),
        "total_questions": after["questions"],
        "existing_rows_signature_before": before["signature"],
        "existing_rows_signature_after": after["signature_existing"],
        "existing_rows_unchanged": before["signature"] == after["signature_existing"],
        "by_type": {"sentence_listen_write": {"candidates": len(candidates), "accepted": len(new_rows),
                                              "rejected": sum(reject.values()) + dup_existing}},
        "other_types": type_probe,
        "by_unit": by_unit,
        "by_origin": {"PROGRAM_GENERATED": len(new_rows), "AI_GENERATED": 0},
        "p308_segment_coverage": {
            "total": len(p308_list), "covered_before": len(covered_before),
            "covered_by_this_run": len(covered_after), "still_uncovered": len(still_open)},
        "rejection_counts": dict(reject), "rejection_examples": dict(reject_examples),
        "quality_gates": gate,
        "segments": [{"question_id": r["question_id"], "unit_code": r["unit_code"],
                      "audio_asset_id": r["audio_asset_id"], "segment_id": r["segment_id"],
                      "start_ms": r["prompt"]["start_ms"], "end_ms": r["prompt"]["end_ms"],
                      "text_resource_id": r["text_resource_id"], "answer_text": r["text"]}
                     for r in new_rows],
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    print("题库 →", DB_PATH)
    print("报告 →", REPORT)
    print("原题数:", before["questions"], "| 新增:", len(new_rows), "| 新总数:", after["questions"])
    print("新增 Unit 分布:", by_unit)
    print("P3-08 句段覆盖: 总 %d | 本次覆盖 %d | 仍无题 %d"
          % (len(p308_list), len(covered_after), len(still_open)))
    print("其余题型:", {k: v["accepted"] for k, v in type_probe.items()})
    print("原有题目未变:", before["signature"] == after["signature_existing"])
    print("质量门禁:", "全部 PASS" if not failed else failed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
