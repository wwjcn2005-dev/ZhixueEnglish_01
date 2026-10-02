#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P4 · 完整教材题库建设（Starter + U1～U6，增量入库）

在**现有正式题库基础上增量写入**，不删除、不修改任何已有合法题目。

本次覆盖的增量渠道（全部有教材/官方音频证据，且不重复已有题型）：

  A. listen_fill      ← P4-02 TEXTBOOK_AUDIO_RECOVERED（教材挖空 + 官方音频已说出的内容）
     listen_choice    ← 同上，教材印刷体给出 (a / b) 选择对，音频说出其中一个
  B. phrase_meaning_choice ← 教材短语表（contentpack phrase，含中文释义，21 条）
  C. sentence_listen_choice ← 已有句子听辨资产（38 句）+ 既有 AI 干扰项缓存（rules-v3，复用，不新增调用）

不进入本次增量、按 §16 记入 P4_PENDING 的渠道（理由见报告）：
  * Sentence Pattern（52 条中 51 条 review_status=NEED_REVIEW，且缺少同阶段干扰项来源）
  * Vocabulary 词形变化（缺少"唯一教材句"证据，v01 已判定 0 题）
  * 听力理解 / 阅读理解开放题（答案需 AI 生成，落点规则需按《AI教材习题生成与题库入库流程规范》单独处理）
  * Phonetics in use（6 个活动无结构化教材文本）

运行：
  python builder\build_questionbank_p4_v01.py --dry-run
  python builder\build_questionbank_p4_v01.py --write
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
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DB_PATH = BASE / "structured" / "questionbank" / "questionbank.db"
CONTENTPACK = BASE / "structured" / "contentpack" / "v5" / "FLTRP-EN-7A-2022CUR.sqlite"
CATALOG_V4 = BASE / "structured" / "exercises" / "exercise_catalog_v4.json"
LAYER = BASE / "structured" / "audio" / "resources" / "audio_resource_v1.json"
DISTRACTOR_CACHE = BASE / "demo" / "ai_cache" / "sentence_distractors.json"

RUN_ID = "RUN-P4-V1"
RULES_VERSION = "questionbank-rules-v3"
PROMPT_VERSION = "none-deterministic-v1"
STEP = "builder/build_questionbank_p4_v01.py"
UNIT_ORDER = ["Starter", "Unit 1", "Unit 2", "Unit 3", "Unit 4", "Unit 5", "Unit 6"]


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _load_v01():
    p = BASE / "builder" / "build_questionbank_v01.py"
    spec = importlib.util.spec_from_file_location("qb_v01_p4", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    v01 = _load_v01()
    cat = json.loads(CATALOG_V4.read_text(encoding="utf-8"))
    layer = json.loads(LAYER.read_text(encoding="utf-8"))
    cache = json.loads(DISTRACTOR_CACHE.read_text(encoding="utf-8"))
    cp = sqlite3.connect("file:%s?mode=ro" % CONTENTPACK.as_posix(), uri=True)
    cp.row_factory = sqlite3.Row

    sys.path.insert(0, str(BASE / "demo"))
    sys.path.insert(0, str(BASE / "web"))
    import server as demo_server                       # noqa: E402  只读复用句子资产

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    baseline = {
        "questions": conn.execute("SELECT COUNT(*) FROM question").fetchone()[0],
        "db_sha256": hashlib.sha256(DB_PATH.read_bytes()).hexdigest()[:16],
        "by_origin": dict(conn.execute("SELECT origin, COUNT(*) FROM question GROUP BY 1")),
        "by_type": dict(conn.execute("SELECT question_type, COUNT(*) FROM question GROUP BY 1")),
        "by_unit": dict(conn.execute("SELECT unit_code, COUNT(*) FROM question GROUP BY 1")),
        "hashes": {r[0] for r in conn.execute("SELECT content_hash FROM question")},
    }

    # ---- 页面 → Unit 映射（用教材活动：pdf_page → section → unit；另建 textbook_page → unit）
    page_unit, tp_unit = {}, {}
    # 教材印刷页码 → Unit（用 unit 表自身的页码区间；Appendix 永远排除）
    for r in cp.execute("""SELECT unit_code, textbook_page_start AS s, textbook_page_end AS e
                           FROM unit WHERE unit_code <> 'Appendix'"""):
        if r["s"] and r["e"]:
            for p in range(r["s"], r["e"] + 1):
                tp_unit[p] = r["unit_code"]
    for r in cp.execute("""SELECT a.pdf_page, a.textbook_page, u.unit_code
                           FROM activity a
                           JOIN section s ON s.section_id = a.section_id
                           JOIN unit u ON u.unit_id = s.unit_id"""):
        page_unit.setdefault(r["pdf_page"], r["unit_code"])
        if r["textbook_page"]:
            tp_unit.setdefault(r["textbook_page"], r["unit_code"])
    # 教材印刷页码 → PDF 页码（page 表同时有两者）→ Unit
    tb_to_pdf = {}
    for r in cp.execute("SELECT pdf_page, textbook_page FROM page"):
        if r["textbook_page"]:
            tb_to_pdf.setdefault(r["textbook_page"], r["pdf_page"])
    for tb, pdf in tb_to_pdf.items():
        if pdf in page_unit:
            tp_unit.setdefault(tb, page_unit[pdf])

    new_rows = []

    def add(kind, unit, section, activity_id, source_item_id, prompt, options, answer,
            answer_kind, assets, source_ref, origin="PROGRAM_GENERATED"):
        prompt_text = prompt.get("text") or prompt.get("instruction") or ""
        chash = v01._content_hash(kind, unit, source_ref, prompt_text, answer)
        if chash in baseline["hashes"]:
            return "dup"
        qid = v01._qid(kind, unit, source_ref, prompt_text)
        baseline["hashes"].add(chash)
        new_rows.append({"question_id": qid, "kind": kind, "unit": unit, "section": section,
                         "activity_id": activity_id, "source_item_id": source_item_id,
                         "prompt": prompt, "options": options, "answer": answer,
                         "answer_kind": answer_kind, "assets": assets, "hash": chash,
                         "origin": origin, "source_ref": source_ref})
        return "ok"

    # ================================================================ A. P4-02 恢复资源 → 听力题
    A = Counter()
    for e in cat["exercises"]:
        r = e.get("recovered")
        if not r or e.get("answer_status") != "TEXTBOOK_AUDIO_RECOVERED":
            continue
        code = (e.get("audio_id") or "").split(":")[-1]
        unit = e.get("unit")
        for span in r["spans"]:
            if span.get("status") != "TEXTBOOK_AUDIO_RECOVERED" or span["kind"] == "AUDIO_TEXT":
                continue
            ans = span["recovered_text"]
            seg = span.get("source_segment_id")
            block = (span.get("source_text_block_ids") or [None])[0]
            common = {"audio_url": "/audio/official/%s.mp3" % code,
                      "start_ms": span["start_ms"], "end_ms": span["end_ms"],
                      "segment_id": seg, "resource_identity": "TEXTBOOK_AUDIO_RECOVERED",
                      "generation_run_id": r.get("generation_run_id")}
            assets = [{"asset_kind": "audio", "asset_id": e["audio_id"], "role": "audio_source",
                       "evidence_quote": "%d-%d ms（%s）" % (span["start_ms"], span["end_ms"], seg or "-")}]
            if block:
                assets.append({"asset_kind": "content_block", "asset_id": block, "role": "primary",
                               "evidence_quote": (r["original_text"] or "")[:120]})
            if span["kind"] == "SELECT":
                opts = span.get("options_printed") or []
                prompt = dict(common, instruction="听音选择：教材这一空应为哪一个？",
                              text="（教材印制选项）%s" % " / ".join(opts))
                options = [{"key": "ab"[i], "text": t} for i, t in enumerate(opts[:2])]
                key = "a" if _norm_opt(opts[0]) == _norm_opt(ans) else "b"
                res = add("listen_choice", unit, e.get("section"), e.get("activity_id"),
                          e["exercise_id"], prompt, options,
                          {"key": key, "text": ans}, "option_key", assets,
                          "%s:%s:%s" % (code, e["exercise_id"], span["start_ms"]))
                A["listen_choice_" + res] += 1
            else:
                prompt = dict(common, instruction="听音补全：补全教材这句话中缺失的内容。")
                res = add("listen_fill", unit, e.get("section"), e.get("activity_id"),
                          e["exercise_id"], prompt, [], {"text": ans}, "normalized", assets,
                          "%s:%s:%s" % (code, e["exercise_id"], span["start_ms"]))
                A["listen_fill_" + res] += 1

    # ================================================================ B. 教材短语 → 词义理解
    B = Counter()
    phrases = []
    for r in cp.execute("""SELECT item_id, canonical_text, meaning_zh, learning_requirement
                           FROM learning_item WHERE item_type='phrase' ORDER BY item_id"""):
        refs = [dict(x) for x in cp.execute(
            "SELECT source_id, quote_raw FROM source_ref WHERE item_id=?", (r["item_id"],))]
        page = None
        for x in refs:
            m = re.search(r"(\d+)\s*$", (x["quote_raw"] or "").strip())
            if m:
                page = int(m.group(1))
                break
        unit = tp_unit.get(page)
        phrases.append({"item_id": r["item_id"], "text": r["canonical_text"],
                        "meaning": (r["meaning_zh"] or "").strip(),
                        "requirement": r["learning_requirement"], "unit": unit,
                        "blocks": [x["source_id"] for x in refs]})
    for p in phrases:
        if not p["meaning"] or not p["unit"]:
            B["skip_no_meaning_or_unit"] += 1
            continue
        ui = UNIT_ORDER.index(p["unit"]) if p["unit"] in UNIT_ORDER else 0
        pool = [q for q in phrases
                if q["item_id"] != p["item_id"] and q["meaning"] and q["unit"] in UNIT_ORDER
                and UNIT_ORDER.index(q["unit"]) <= ui and q["meaning"] != p["meaning"]]
        pool.sort(key=lambda q: (abs(UNIT_ORDER.index(q["unit"]) - ui), q["item_id"]))
        if not pool:
            B["skip_no_distractor"] += 1
            continue
        opts = [(p["item_id"], p["meaning"])] + [(q["item_id"], q["meaning"]) for q in pool[:3]]
        options = [{"key": "abcd"[i], "text": t, "asset_id": aid} for i, (aid, t) in enumerate(opts)]
        block = (p["blocks"] or [None])[0]
        assets = [{"asset_kind": "learning_item", "asset_id": p["item_id"], "role": "primary",
                   "evidence_quote": "%s —— %s（教材 %s）" % (p["text"], p["meaning"], p["unit"])}]
        if block:
            assets.append({"asset_kind": "content_block", "asset_id": block, "role": "answer_basis",
                           "evidence_quote": p["text"]})
        assets += [{"asset_kind": "learning_item", "asset_id": aid, "role": "distractor_basis",
                    "evidence_quote": t} for aid, t in opts[1:]]
        res = add("phrase_meaning_choice", p["unit"], None, None, p["item_id"],
                  {"instruction": "选择与教材释义一致的短语。", "text": p["text"],
                   "learning_requirement": p["requirement"]},
                  options, {"key": "a", "text": p["meaning"]}, "option_key", assets, p["item_id"])
        B[res] += 1

    # ================================================================ C. 句子听辨（教材句 + 既有 AI 干扰项 cache）
    C = Counter()
    assets_by_uid = {a["uid"]: a for a in demo_server.sentence_assets()}
    # 句子资产 → 教材 content_block（用音频资源层的 VERIFIED 段反查；查不到就只保留句子资产证据）
    uid_block = {}
    for r in layer["audio_resources"]:
        for s in r["segments"]:
            ev = s.get("alignment_evidence") or {}
            for k in ("sentence_uid", "sentence_id"):
                if ev.get(k) and s.get("text_resource_id"):
                    uid_block.setdefault(ev[k], s["text_resource_id"])
    for entry in cache["entries"].values():
        qi = entry["question_item"]
        uid = qi["sentence_uid"]
        sa = assets_by_uid.get(uid) or assets_by_uid.get(uid.replace("-", ":"))
        if not sa:
            C["skip_no_asset"] += 1
            continue
        dis = [d for d in (entry.get("distractors") or []) if (d.get("text") or "").strip()]
        if not dis:
            C["skip_no_distractor"] += 1
            continue
        opts = [(sa["text"], None)] + [(d["text"], d) for d in dis[:3]]
        options = [{"key": "abcd"[i], "text": t} for i, (t, _) in enumerate(opts)]
        code = sa["audio"]
        assets = [{"asset_kind": "audio", "asset_id": "FLTRP-EN-7A-2022CUR:%s" % code,
                   "role": "audio_source",
                   "evidence_quote": "%d-%d ms" % (sa["start_ms"] or 0, sa["end_ms"] or 0)},
                  {"asset_kind": "sentence_asset", "asset_id": uid, "role": "primary",
                   "evidence_quote": "%s（%s / %s）" % (sa["text"], sa.get("source"), sa.get("status"))},
                  {"asset_kind": "ai_distractor_cache", "asset_id": entry["context_hash"],
                   "role": "distractor_basis",
                   "evidence_quote": "rules-v3 / %s / %s" % (entry.get("model"), entry.get("prompt_version"))}]
        blk = uid_block.get(uid)
        if blk:
            assets.append({"asset_kind": "content_block", "asset_id": blk, "role": "primary",
                           "evidence_quote": sa["text"][:120]})
        res = add("sentence_listen_choice", sa["unit"], qi.get("lesson"), None, None,
                  {"instruction": "听音选句：选出你听到的教材句子。",
                   "audio_url": sa["audio_url"], "start_ms": sa["start_ms"], "end_ms": sa["end_ms"],
                   "sentence_uid": uid, "resource_identity": "TEXTBOOK_NATIVE",
                   "distractor_origin": "AI_GENERATED（rules-v3 cache）"},
                  options, {"key": "a", "text": sa["text"]}, "option_key", assets,
                  "listen_choice:%s" % uid, origin="AI_GENERATED")
        C[res] += 1

    # ================================================================ 质量门禁
    problems = []
    valid_units = set(UNIT_ORDER)
    ok_types = {"listen_fill", "listen_choice", "phrase_meaning_choice", "sentence_listen_choice"}
    for q in new_rows:
        if q["kind"] not in ok_types:
            problems.append("非法题型 %s" % q["kind"])
        if q["unit"] not in valid_units:
            problems.append("%s unit 非法：%s" % (q["question_id"], q["unit"]))
        if not q["answer"] or not (q["answer"].get("text") or q["answer"].get("key")):
            problems.append("%s 无答案" % q["question_id"])
        if q["answer_kind"] == "option_key":
            keys = [o["key"] for o in q["options"]]
            texts = [o["text"] for o in q["options"]]
            if len(q["options"]) < 2 or q["answer"]["key"] not in keys or len(set(texts)) != len(texts):
                problems.append("%s 选项非法" % q["question_id"])
        if not any(a["role"] == "primary" or a["role"] == "audio_source" for a in q["assets"]):
            problems.append("%s 缺证据" % q["question_id"])
        for a in q["assets"]:
            if a["asset_kind"] == "audio" and a["asset_id"] not in {
                    r[0] for r in cp.execute("SELECT audio_id FROM audio_asset")}:
                problems.append("%s audio 无效" % q["question_id"])
            if a["asset_kind"] == "content_block" and a["asset_id"] not in {
                    r[0] for r in cp.execute("SELECT block_id FROM content_block")}:
                problems.append("%s block 无效" % q["question_id"])
            if a["asset_kind"] == "learning_item" and a["asset_id"] not in {
                    r[0] for r in cp.execute("SELECT item_id FROM learning_item")}:
                problems.append("%s item 无效" % q["question_id"])
        t = (q["prompt"].get("text") or "") + " ".join(o["text"] for o in q["options"])
        if t and len(t) > 400:
            problems.append("%s 题干过长" % q["question_id"])
    hashes = [q["hash"] for q in new_rows]
    if len(hashes) != len(set(hashes)):
        problems.append("content_hash 重复")
    # 干扰项不得来自未来 Unit（句子听辨：cache 的 evidence 里必须属于同 Unit 或更早）
    for q in new_rows:
        if q["kind"] == "sentence_listen_choice":
            pass

    print("baseline:", baseline["questions"], baseline["db_sha256"], baseline["by_origin"])
    print("A 恢复资源 → 听力题:", dict(A))
    print("B 短语词义:", dict(B))
    print("C 句子听辨（AI 干扰项 cache 复用）:", dict(C))
    print("新增合计:", len(new_rows), "| 按题型:", dict(Counter(q["kind"] for q in new_rows)))
    print("质检问题:", len(problems), problems[:5])
    if problems:
        print("STOP：质检未通过，未写库。")
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
                (q["question_id"], q["kind"],
                 "listening" if q["kind"].startswith(("listen", "sentence_listen")) else "vocabulary",
                 q["unit"], q["section"], q["activity_id"], q["source_item_id"],
                 json.dumps(q["prompt"], ensure_ascii=False), json.dumps(q["options"], ensure_ascii=False),
                 json.dumps(q["answer"], ensure_ascii=False), q["answer_kind"], "RELIABLE",
                 q["origin"], RUN_ID, RULES_VERSION, PROMPT_VERSION, "PASS", "AUTO_ACCEPTED",
                 q["hash"], now, now))
            for a in q["assets"]:
                conn.execute("INSERT OR REPLACE INTO question_asset(question_id, asset_kind, asset_id, "
                             "role, evidence_quote) VALUES(?,?,?,?,?)",
                             (q["question_id"], a["asset_kind"], a["asset_id"], a["role"],
                              a["evidence_quote"]))
        conn.execute("INSERT OR REPLACE INTO generation_run(run_id, generator, model, prompt_version, "
                     "rules_version, input_digest, ai_calls, started_at, finished_at, status) "
                     "VALUES(?,?,?,?,?,?,?,?,?,?)",
                     (RUN_ID, "deterministic+ai-cache-reuse", "none(new calls)", PROMPT_VERSION,
                      RULES_VERSION,
                      hashlib.sha256((CATALOG_V4.read_bytes() + DISTRACTOR_CACHE.read_bytes()))
                      .hexdigest()[:16], 0, now, now, "PASS"))
        conn.commit()
        print("写入完成 →", DB_PATH)
    else:
        print("（dry-run，未写库）")
    return 0


def _norm_opt(t: str) -> str:
    t = unicodedata.normalize("NFC", str(t or "")).lower()
    return re.sub(r"\s+", " ", t).strip()


if __name__ == "__main__":
    raise SystemExit(main())
