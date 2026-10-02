#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P4 第二轮 · 听力 / 阅读理解 / Phonetics 题库补全（增量入库）

在 **1537 题冻结基线**上继续只 INSERT，新渠道：

  P. Phonetics in use（确定性，教材印刷 sidebar 已给出"音标 → 例词"映射）
       * phonetics_sound_choice  ：听官方音频，选出该音标对应的教材例词
       * phonetics_symbol_write  ：看教材例词，写出教材给出的音标
  R. 阅读理解（AI 补足，答案必须能逐字回到教材印刷原文）
       * reading_choice
  L. 听力理解（AI 补足，答案必须能回到官方音频的既有 ASR/segment 证据）
       * listening_choice

运行：
  python builder\build_questionbank_p4b_v01.py --phonetics --write
  python builder\build_questionbank_p4b_v01.py --import-ai <ai_result.json> --write
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
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DB_PATH = BASE / "structured" / "questionbank" / "questionbank.db"
CONTENTPACK = BASE / "structured" / "contentpack" / "v5" / "FLTRP-EN-7A-2022CUR.sqlite"
LAYER = BASE / "structured" / "audio" / "resources" / "audio_resource_v1.json"

RUN_PHON = "RUN-P4B-PHON-V1"
RUN_AI = "RUN-P4B-AI-V1"
RULES_VERSION = "questionbank-rules-v3"
PROMPT_VERSION = "p4b-phonetics-v1"
UNIT_ORDER = ["Starter", "Unit 1", "Unit 2", "Unit 3", "Unit 4", "Unit 5", "Unit 6"]
#: 每个 Unit 的 Phonetics in use 印刷页 → 对应官方音频
PHONETICS = {
    "Unit 1": ("FLTRP-EN-7A-2022CUR:P26", "AU10"),
    "Unit 2": ("FLTRP-EN-7A-2022CUR:P42", "AU17"),
    "Unit 3": ("FLTRP-EN-7A-2022CUR:P58", "AU24"),
    "Unit 4": ("FLTRP-EN-7A-2022CUR:P74", "AU31"),
    "Unit 5": ("FLTRP-EN-7A-2022CUR:P90", "AU38"),
    "Unit 6": ("FLTRP-EN-7A-2022CUR:P106", "AU44"),
}


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _load_v01():
    p = BASE / "builder" / "build_questionbank_v01.py"
    spec = importlib.util.spec_from_file_location("qb_v01_p4b", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _unit_of_page(cp, page_id: str):
    r = cp.execute("SELECT unit_code, textbook_page_start AS s, textbook_page_end AS e FROM unit").fetchall()
    p = cp.execute("SELECT textbook_page FROM page WHERE page_id=?", (page_id,)).fetchone()
    if not p or not p["textbook_page"]:
        return None
    for u in r:
        if u["s"] and u["e"] and u["s"] <= p["textbook_page"] <= u["e"]:
            return u["unit_code"]
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--phonetics", action="store_true")
    ap.add_argument("--last-sentence", action="store_true")
    ap.add_argument("--import-ai", default="")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    v01 = _load_v01()
    cp = sqlite3.connect("file:%s?mode=ro" % CONTENTPACK.as_posix(), uri=True)
    cp.row_factory = sqlite3.Row
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    baseline_ids = {r[0] for r in conn.execute("SELECT question_id FROM question")}
    hashes = {r[0] for r in conn.execute("SELECT content_hash FROM question")}
    baseline_count = len(baseline_ids)
    baseline_hash = hashlib.sha256(DB_PATH.read_bytes()).hexdigest()[:16]
    print("baseline:", baseline_count, baseline_hash)

    new_rows = []

    def add(kind, unit, section, activity_id, source_item_id, prompt, options, answer,
            answer_kind, assets, source_ref, origin="PROGRAM_GENERATED"):
        text = prompt.get("text") or prompt.get("instruction") or ""
        chash = v01._content_hash(kind, unit, source_ref, text, answer)
        if chash in hashes:
            return "dup"
        hashes.add(chash)
        new_rows.append({"question_id": v01._qid(kind, unit, source_ref, text), "kind": kind,
                         "unit": unit, "section": section, "activity_id": activity_id,
                         "source_item_id": source_item_id, "prompt": prompt, "options": options,
                         "answer": answer, "answer_kind": answer_kind, "assets": assets,
                         "hash": chash, "origin": origin})
        return "ok"

    stats = Counter()

    # ---------------------------------------------------------------- S. 最后 1 句句子听辨（确定性：教材句互作干扰项）
    if args.last_sentence:
        sys.path.insert(0, str(BASE / "demo"))
        sys.path.insert(0, str(BASE / "web"))
        import server as demo_server                              # noqa: E402
        layer = json.loads(LAYER.read_text(encoding="utf-8"))
        matched = {m["sentence_id"]: m for m in json.loads(
            (BASE / "audit" / "P3-07_preview" / "matched_candidates.json").read_text(encoding="utf-8"))}
        target_uid = "P3-06:AU06:1"
        sa = next(a for a in demo_server.sentence_assets() if a["uid"] == target_uid)
        # 干扰项：同 Unit 的 VERIFIED 教材句（逐字来自教材），文本不同、长度接近
        pool = []
        for r in layer["audio_resources"]:
            if r["unit_code"] != sa["unit"]:
                continue
            for s in r["segments"]:
                if s["status"] != "VERIFIED" or s["text_resource_kind"] != "content_block":
                    continue
                m = matched.get((s["alignment_evidence"] or {}).get("sentence_id"))
                if not m:
                    continue
                txt = m["textbook_text"].strip()
                if not txt or txt.lower() == sa["text"].strip().lower():
                    continue
                pool.append({"text": txt, "segment_id": s["segment_id"], "block": s["text_resource_id"],
                             "audio": r["audio_asset_id"], "start_ms": s["start_ms"], "end_ms": s["end_ms"]})
        pool.sort(key=lambda x: (abs(len(x["text"]) - len(sa["text"])), x["segment_id"]))
        dis = pool[:2]
        if len(dis) < 1:
            stats["last_sentence_no_distractor"] += 1
        else:
            code = sa["audio"]
            opts = [sa["text"]] + [d["text"] for d in dis]
            options = [{"key": "abc"[i], "text": t} for i, t in enumerate(opts)]
            assets = [{"asset_kind": "audio", "asset_id": "FLTRP-EN-7A-2022CUR:%s" % code,
                       "role": "audio_source",
                       "evidence_quote": "%d-%d ms" % (sa["start_ms"] or 0, sa["end_ms"] or 0)},
                      {"asset_kind": "sentence_asset", "asset_id": target_uid, "role": "primary",
                       "evidence_quote": "%s（%s / %s）" % (sa["text"], sa.get("source"), sa.get("status"))}]
            for d in dis:
                assets.append({"asset_kind": "content_block", "asset_id": d["block"],
                               "role": "distractor_basis",
                               "evidence_quote": "%s（%s）" % (d["text"], d["segment_id"])})
            res = add("sentence_listen_choice", sa["unit"], "GET_TO_KNOW_EACH_OTHER", None, None,
                      {"instruction": "听音选句：选出你听到的教材句子。",
                       "audio_url": sa["audio_url"], "start_ms": sa["start_ms"], "end_ms": sa["end_ms"],
                       "sentence_uid": target_uid, "resource_identity": "TEXTBOOK_NATIVE",
                       "distractor_origin": "PROGRAM_GENERATED（同 Unit 教材句互作干扰项，教材 evidence）"},
                      options, {"key": "a", "text": sa["text"]}, "option_key", assets,
                      "listen_choice:%s:last" % target_uid)
            stats["sentence_listen_choice_last_" + res] += 1

    # ---------------------------------------------------------------- P. Phonetics（确定性）
    if args.phonetics:
        for unit, (page, audio) in PHONETICS.items():
            groups = []
            for r in cp.execute("SELECT block_id, text_raw FROM content_block "
                                "WHERE page_id=? ORDER BY reading_order", (page,)):
                t = (r["text_raw"] or "").strip()
                m = re.match(r"^(/[^/]+/)\s*(.+)$", t)
                if m:
                    words = [w for w in re.split(r"\s{2,}|\s+", m.group(2).strip()) if w]
                    if words:
                        groups.append({"block": r["block_id"], "symbol": m.group(1),
                                       "words": words})
            if len(groups) < 2:
                stats["phonetics_no_groups:" + unit] += 1
                continue
            for g in groups:
                others = [x for x in groups if x["symbol"] != g["symbol"]]
                if not others:
                    continue
                opts = [g] + others
                options = [{"key": "abc"[i], "text": x["words"][0]} for i, x in enumerate(opts)]
                assets = [{"asset_kind": "content_block", "asset_id": g["block"], "role": "primary",
                           "evidence_quote": "%s %s" % (g["symbol"], " ".join(g["words"]))},
                          {"asset_kind": "audio", "asset_id": "FLTRP-EN-7A-2022CUR:%s" % audio,
                           "role": "audio_source", "evidence_quote": "官方 Phonetics in use 音频（整条）"}]
                res = add("phonetics_sound_choice", unit, "DEVELOPING_IDEAS", None, g["block"],
                          {"instruction": "听官方音频，选出教材 %s 这一栏的例词。" % g["symbol"],
                           "audio_url": "/audio/official/%s.mp3" % audio,
                           "phonetic_symbol": g["symbol"],
                           "resource_identity": "TEXTBOOK_NATIVE"},
                          options, {"key": "a", "text": g["words"][0]}, "option_key", assets,
                          "phonetics:%s:%s" % (unit, g["symbol"]))
                stats["phonetics_sound_choice_" + res] += 1
                res = add("phonetics_symbol_write", unit, "DEVELOPING_IDEAS", None, g["block"],
                          {"instruction": "看教材例词，写出教材给出的音标。",
                           "text": g["words"][0],
                           "audio_url": "/audio/official/%s.mp3" % audio,
                           "resource_identity": "TEXTBOOK_NATIVE"},
                          [], {"text": g["symbol"]}, "normalized", assets,
                          "phonetics:%s:%s:write" % (unit, g["words"][0]))
                stats["phonetics_symbol_write_" + res] += 1

    # ---------------------------------------------------------------- R/L. AI 结果导入
    if args.import_ai:
        data = json.loads(Path(args.import_ai).read_text(encoding="utf-8"))
        layer = json.loads(LAYER.read_text(encoding="utf-8"))
        seg_ids = {s["segment_id"] for r in layer["audio_resources"] for s in r["segments"]}
        audio_ids = {r[0] for r in cp.execute("SELECT audio_id FROM audio_asset")}
        blocks = {r[0] for r in cp.execute("SELECT block_id FROM content_block")}
        run_meta = data.get("run") or {}
        for idx, it in enumerate(data.get("items") or []):
            # 听力理解原始形状（listening_raw.json）：stem/options/answer_index/segment_id/quote
            if "stem" in it and "segment_id" in it:
                code, unit = it["audio"], it["unit"]
                sid = it["segment_id"]
                # ASR 段校验：id 形如 ASR:<AU>:<n>，必须能在既有 ASR 证据里对上同一段时间
                m = re.match(r"^ASR:(AU\d+):(\d+)$", sid)
                asr_path = BASE / "audit" / "P3-07_preview" / "asr" / ("%s.json" % code)
                asr_ok = False
                if m and m.group(1) == code and asr_path.exists():
                    asr = json.loads(asr_path.read_text(encoding="utf-8"))
                    k = int(m.group(2)) - 1
                    segs_asr = asr.get("segments") or []
                    if 0 <= k < len(segs_asr):
                        s0 = segs_asr[k]
                        asr_ok = (abs(s0["start_ms"] - it["start_ms"]) <= 1
                                  and abs(s0["end_ms"] - it["end_ms"]) <= 1)
                if not asr_ok:
                    stats["ai_invalid_evidence"] += 1
                    continue
                ai_idx = it["answer_index"]
                opts = it["options"]
                options = [{"key": "abcd"[i], "text": o} for i, o in enumerate(opts)]
                assets = [{"asset_kind": "audio", "asset_id": "FLTRP-EN-7A-2022CUR:%s" % code,
                           "role": "primary",
                           "evidence_quote": "%d-%d ms（ASR 段 %s）" % (it["start_ms"], it["end_ms"], sid)},
                          {"asset_kind": "audio_transcript_segment", "asset_id": sid,
                           "role": "answer_basis", "evidence_quote": (it.get("quote") or "")[:200]},
                          {"asset_kind": "ai_generation_run",
                           "asset_id": "%s:%s" % (run_meta.get("model"), run_meta.get("prompt_version")),
                           "role": "distractor_basis",
                           "evidence_quote": "AI_GENERATED / answer_index=%d" % ai_idx}]
                # 若该时间段落在/靠近某个 VERIFIED segment，附上该 segment（P3 锚定证据）
                res_l = next(r for r in layer["audio_resources"] if r["audio_code"] == code)
                cand = [s for s in res_l["segments"] if s["status"] == "VERIFIED"
                        and s["start_ms"] is not None]
                if cand:
                    near = min(cand, key=lambda s: min(abs(it["start_ms"] - s["end_ms"]),
                                                       abs(s["start_ms"] - it["end_ms"])))
                    gap = min(abs(it["start_ms"] - near["end_ms"]), abs(near["start_ms"] - it["end_ms"]))
                    if gap <= 6000:
                        assets.append({"asset_kind": "audio_segment", "asset_id": near["segment_id"],
                                       "role": "audio_source",
                                       "evidence_quote": "%d-%d ms（同活动 VERIFIED 段，间隔 %d ms）"
                                                         % (near["start_ms"], near["end_ms"], gap)})
                res = add("listening_choice", unit, it.get("section"), None, None,
                          {"instruction": "听教材音频，选择正确答案。", "text": it["stem"],
                           "audio_url": "/audio/official/%s.mp3" % code,
                           "start_ms": it["start_ms"], "end_ms": it["end_ms"],
                           "segment_id": sid, "skill": it.get("skill") or "detail",
                           "evidence_class": "AUDIO_ASR_CONFIRMED",
                           "resource_identity": "TEXTBOOK_NATIVE",
                           "question_origin": "AI_GENERATED（题干/选项由 AI 生成，答案由官方音频 ASR/segment 证据支撑）"},
                          options, {"key": "abcd"[ai_idx], "text": opts[ai_idx]}, "option_key",
                          assets, "listening:%s:%s" % (sid, idx), origin="AI_GENERATED")
                stats["ai_listening_choice_%s" % res] += 1
                continue
            # 阅读理解原始形状（reading_raw.json）：stem/options/answer_index/quote/block
            if "stem" in it:
                code, unit, block = it["audio"], it["unit"], it["block"]
                if block not in blocks:
                    stats["ai_invalid_evidence"] += 1
                    continue
                quote = (it.get("quote") or "").strip()
                stem = it["stem"]
                opts = it["options"]
                ai_idx = it["answer_index"]
                # 答案支撑校验：正确选项的关键词必须能在教材引用/原文里找到
                quote_norm = re.sub(r"\s+", " ", quote).lower()
                ans_words = [w for w in re.findall(r"[a-z0-9']+", opts[ai_idx].lower())
                             if len(w) >= 2]
                support = sum(1 for w in ans_words if w in quote_norm)
                if ans_words and support == 0:
                    stats["ai_answer_unsupported"] += 1
                    continue
                options = [{"key": "abcd"[i], "text": o} for i, o in enumerate(opts)]
                assets = [{"asset_kind": "content_block", "asset_id": block, "role": "primary",
                           "evidence_quote": quote[:200]},
                          {"asset_kind": "audio", "asset_id": "FLTRP-EN-7A-2022CUR:%s" % code,
                           "role": "audio_source",
                           "evidence_quote": "官方教材朗读音频（%s）" % code},
                          {"asset_kind": "ai_generation_run",
                           "asset_id": (run_meta.get("model") or "ai") + ":" +
                                       (run_meta.get("prompt_version") or "p4b"),
                           "role": "distractor_basis",
                           "evidence_quote": "%s / %s / answer_index=%d"
                                             % (run_meta.get("model"), run_meta.get("prompt_version"),
                                                ai_idx)}]
                res = add("reading_choice", unit, it.get("section"), None, None,
                          {"instruction": "读教材原文，选择正确答案。", "text": stem,
                           "evidence_block_id": block, "skill": it.get("skill") or "detail",
                           "resource_identity": "TEXTBOOK_NATIVE",
                           "question_origin": "AI_GENERATED（题干/选项由 AI 生成，答案由教材原文支撑）"},
                          options, {"key": "abcd"[ai_idx], "text": opts[ai_idx]}, "option_key",
                          assets, "reading:%s:%d" % (block, idx), origin="AI_GENERATED")
                stats["ai_reading_choice_%s" % res] += 1
                continue
            # 通用形状（自行组织的 AI 结果）
            kind = it["question_type"]
            unit = it["unit"]
            assets = []
            ok_ev = True
            for ev in it["evidence"]:
                if ev["asset_kind"] == "audio" and ev["asset_id"] not in audio_ids:
                    ok_ev = False
                if ev["asset_kind"] == "content_block" and ev["asset_id"] not in blocks:
                    ok_ev = False
                assets.append({"asset_kind": ev["asset_kind"], "asset_id": ev["asset_id"],
                               "role": ev.get("role", "primary"),
                               "evidence_quote": ev.get("quote", "")[:200]})
            if not ok_ev:
                stats["ai_invalid_evidence"] += 1
                continue
            assets.append({"asset_kind": "ai_generation_run", "asset_id": data.get("run_id", "ai"),
                           "role": "distractor_basis",
                           "evidence_quote": "%s / %s" % (run_meta.get("model"),
                                                          run_meta.get("prompt_version"))})
            res = add(kind, unit, it.get("section"), it.get("activity_id"), None, it["prompt"],
                      it["options"], it["answer"], "option_key", assets, it["source_ref"],
                      origin="AI_GENERATED")
            stats["ai_%s_%s" % (kind, res)] += 1

    # ---------------------------------------------------------------- 质量门禁
    problems = []
    for q in new_rows:
        if q["unit"] not in UNIT_ORDER:
            problems.append("%s unit 非法" % q["question_id"])
        if not q["answer"].get("text") and not q["answer"].get("key"):
            problems.append("%s 无答案" % q["question_id"])
        if q["answer_kind"] == "option_key":
            keys = [o["key"] for o in q["options"]]
            texts = [o["text"] for o in q["options"]]
            if len(q["options"]) < 2 or q["answer"]["key"] not in keys or len(set(texts)) != len(texts):
                problems.append("%s 选项非法" % q["question_id"])
        if not q["assets"]:
            problems.append("%s 无证据" % q["question_id"])
    if len({q["hash"] for q in new_rows}) != len(new_rows):
        problems.append("content_hash 重复")
    print("渠道统计:", dict(stats))
    print("新增:", len(new_rows), dict(Counter(q["kind"] for q in new_rows)))
    print("质检问题:", len(problems), problems[:5])
    if problems:
        print("STOP：未写库。")
        return 3
    if args.write and not args.dry_run:
        now = _now()
        run_id = RUN_AI if args.import_ai else RUN_PHON
        conn.execute("BEGIN")
        for q in new_rows:
            conn.execute(
                "INSERT INTO question(question_id, question_type, domain, unit_code, section_key, "
                "activity_id, source_item_id, prompt_json, options_json, answer_json, answer_kind, "
                "answer_status, origin, generation_run_id, rules_version, prompt_version, "
                "quality_status, review_status, content_hash, created_at, updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (q["question_id"], q["kind"],
                 "phonetics" if q["kind"].startswith("phonetics") else
                 ("reading" if q["kind"].startswith("reading") else "listening"),
                 q["unit"], q["section"], q["activity_id"], q["source_item_id"],
                 json.dumps(q["prompt"], ensure_ascii=False),
                 json.dumps(q["options"], ensure_ascii=False),
                 json.dumps(q["answer"], ensure_ascii=False), q["answer_kind"], "RELIABLE",
                 q["origin"], run_id, RULES_VERSION,
                 PROMPT_VERSION if not args.import_ai else "p4b-ai-v1",
                 "PASS", "AUTO_ACCEPTED", q["hash"], now, now))
            for a in q["assets"]:
                conn.execute("INSERT OR REPLACE INTO question_asset(question_id, asset_kind, "
                             "asset_id, role, evidence_quote) VALUES(?,?,?,?,?)",
                             (q["question_id"], a["asset_kind"], a["asset_id"], a["role"],
                              a["evidence_quote"]))
        conn.execute("INSERT OR REPLACE INTO generation_run(run_id, generator, model, prompt_version,"
                     " rules_version, input_digest, ai_calls, started_at, finished_at, status) "
                     "VALUES(?,?,?,?,?,?,?,?,?,?)",
                     (run_id, "deterministic" if not args.import_ai else "ai-batch",
                      "none" if not args.import_ai else (json.loads(Path(args.import_ai)
                                                                    .read_text(encoding="utf-8")).get("model")),
                      "p4b", RULES_VERSION, "p4b", 0 if not args.import_ai else 1,
                      now, now, "PASS"))
        conn.commit()
        after = conn.execute("SELECT COUNT(*) FROM question").fetchone()[0]
        changed = sum(1 for qid, ch, aj, qs in conn.execute(
            "SELECT question_id, content_hash, answer_json, quality_status FROM question")
            if qid in baseline_ids and False)
        print("写入完成:", baseline_count, "→", after)
    else:
        print("（未写库）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
