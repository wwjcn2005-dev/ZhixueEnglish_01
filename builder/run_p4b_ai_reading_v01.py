#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P4 第二轮 · 阅读理解 AI 批量生成（一个活动 = 一次调用）

输入证据（全部正式、只读）：教材印刷原文（contentpack content_block，带 block_id）+
官方音频 audio_id + 活动 instruction / unit / section。

输出：audit/P4B_ai_batch/reading_<AU>.json（原始响应 + usage）、reading_raw.json（可入库题目）、
reading_run_report.json（调用与校验统计）。

规则：只生成选择题；每题必须给出逐字来自教材印刷原文的 evidence_quote；答案必须由该引用支持；
校验不通过直接丢弃，不猜、不补。

运行：python builder\run_p4b_ai_reading_v01.py
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sqlite3
import sys
import time
import unicodedata
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
CONTENTPACK = BASE / "structured" / "contentpack" / "v5" / "FLTRP-EN-7A-2022CUR.sqlite"
LAYER = BASE / "structured" / "audio" / "resources" / "audio_resource_v1.json"
OUT = BASE / "audit" / "P4B_ai_batch"
ENDPOINT = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-v4-pro"
MAX_TOKENS = 8192
TEMPERATURE = 0.3
PROMPT_VERSION = "p4b-reading-v1"

READING = [("AU05", "Starter"), ("AU07", "Unit 1"), ("AU11", "Unit 1"), ("AU13", "Unit 1"),
           ("AU21", "Unit 3"), ("AU27", "Unit 3"), ("AU34", "Unit 4"), ("AU35", "Unit 5"),
           ("AU41", "Unit 5"), ("AU42", "Unit 6"), ("AU47", "Unit 6")]

SYSTEM = (
    "You generate English reading-comprehension questions for Chinese junior-high grade 7 "
    "students, using ONLY the supplied textbook passage. Output strict JSON.\n\n"
    "HARD RULES\n"
    "1. Every question must be answerable from the passage alone.\n"
    "2. evidence_quote MUST be copied verbatim from one supplied block.\n"
    "3. evidence_block_id MUST be the id of the block containing that quote.\n"
    "4. Options must be short, mutually exclusive, exactly one correct.\n"
    "5. Never use facts or content that is not in the passage.\n"
    "6. Ask about information retrieval, detail, relationships, simple inference, simple gist. "
    "Grade-7 level, no exam tricks.\n"
    "7. 2 to 3 questions per passage; fewer if the passage cannot support them.\n\n"
    "OUTPUT JSON\n"
    '{"questions":[{"stem":"...","options":["...","..."],"answer_index":0,'
    '"evidence_block_id":"...","evidence_quote":"...","skill":"detail"}]}\n'
)


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFC", str(t or "")).replace("\u2019", "'")
    t = t.replace("\u201c", '"').replace("\u201d", '"')
    return re.sub(r"\s+", " ", t).strip().lower()


def _key() -> str:
    p = Path(os.path.expanduser("~")) / ".codex" / "auth.json"
    return json.loads(p.read_text(encoding="utf-8"))["OPENAI_API_KEY"]


def _passage(cp, layer, code: str):
    res = next(r for r in layer["audio_resources"] if r["audio_code"] == code)
    pages = set()
    for s in res["segments"]:
        if s["text_resource_kind"] == "content_block" and s["text_resource_id"]:
            row = cp.execute("SELECT page_id FROM content_block WHERE block_id=?",
                             (s["text_resource_id"],)).fetchone()
            if row:
                pages.add(row[0])
    blocks = []
    for p in sorted(pages):
        for r in cp.execute("""SELECT block_id, text_raw, block_kind, layout_role
                               FROM content_block WHERE page_id=? ORDER BY reading_order""", (p,)):
            t = (r["text_raw"] or "").strip()
            if not t or r["block_kind"] in ("footer_text", "heading") or len(t) < 12:
                continue
            if not re.search(r"[A-Za-z]{3}", t):
                continue
            blocks.append({"block_id": r["block_id"], "text": t,
                           "kind": r["block_kind"], "layout": r["layout_role"]})
    return res, pages, blocks


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=99)
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    OUT.mkdir(parents=True, exist_ok=True)
    key = _key()
    cp = sqlite3.connect("file:%s?mode=ro" % CONTENTPACK.as_posix(), uri=True)
    cp.row_factory = sqlite3.Row
    layer = json.loads(LAYER.read_text(encoding="utf-8"))
    want = {c for c in args.only.split(",") if c}

    items, calls = [], 0
    usage_total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    report = {"run": "P4B reading comprehension", "model": MODEL, "prompt_version": PROMPT_VERSION,
              "started_at": datetime.datetime.now().isoformat(timespec="seconds"), "tasks": []}
    for code, unit in READING:
        if want and code not in want:
            continue
        if calls >= args.limit:
            break
        res, pages, blocks = _passage(cp, layer, code)
        text = "\n".join("[%s] %s" % (b["block_id"], b["text"]) for b in blocks)
        user = ("UNIT: %s\nSECTION: %s\nACTIVITY_INSTRUCTION: %s\n"
                "PASSAGE BLOCKS (id + verbatim textbook text):\n%s\n\n"
                "Write 2-3 multiple-choice reading questions about this passage."
                % (unit, res.get("section_key"), res.get("filename"), text))
        payload = {"model": MODEL, "temperature": TEMPERATURE, "max_tokens": MAX_TOKENS,
                   "response_format": {"type": "json_object"},
                   "messages": [{"role": "system", "content": SYSTEM},
                                {"role": "user", "content": user}]}
        req = urllib.request.Request(ENDPOINT, data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json",
                                              "Authorization": "Bearer " + key})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                body = json.loads(r.read().decode("utf-8"))
            calls += 1
            content = body["choices"][0]["message"]["content"]
            usage = body.get("usage") or {}
            for k in usage_total:
                usage_total[k] += usage.get(k, 0)
            parsed = json.loads(content)
            (OUT / ("reading_%s.json" % code)).write_text(
                json.dumps({"request_user": user, "content": content, "usage": usage},
                           ensure_ascii=False, indent=1), encoding="utf-8")
            kept, dropped = [], []
            block_text = {b["block_id"]: b["text"] for b in blocks}
            for q in parsed.get("questions") or []:
                opts = [str(o).strip() for o in (q.get("options") or []) if str(o).strip()]
                bi = q.get("evidence_block_id")
                quote = (q.get("evidence_quote") or "").strip()
                stem = (q.get("stem") or "").strip()
                ai = q.get("answer_index")
                bad = None
                if len(opts) < 2 or len(set(opts)) != len(opts):
                    bad = "options_invalid"
                elif not isinstance(ai, int) or not (0 <= ai < len(opts)):
                    bad = "answer_index"
                elif bi not in block_text:
                    bad = "block_id"
                elif _norm(quote) not in _norm(block_text.get(bi, "")):
                    bad = "quote_not_in_passage"
                elif not stem or len(stem) > 200:
                    bad = "stem_length"
                if bad:
                    dropped.append({"reason": bad, "stem": stem[:80]})
                    continue
                kept.append({"audio": code, "unit": unit, "section": res.get("section_key"),
                             "block": bi, "stem": stem, "options": opts, "answer_index": ai,
                             "quote": quote, "skill": q.get("skill") or "detail"})
            items += kept
            report["tasks"].append({"audio_code": code, "unit": unit, "blocks": len(blocks),
                                    "chars": len(text), "kept": len(kept), "dropped": dropped,
                                    "usage": usage, "elapsed_s": round(time.time() - t0, 1)})
            print("[%s] blocks=%d kept=%d dropped=%d tokens=%s %.0fs"
                  % (code, len(blocks), len(kept), len(dropped), usage.get("total_tokens"),
                     time.time() - t0), flush=True)
        except Exception as exc:                                        # noqa: BLE001
            report["tasks"].append({"audio_code": code,
                                    "error": "%s: %s" % (type(exc).__name__, str(exc)[:200])})
            print("[%s] ERROR %s" % (code, exc), flush=True)

    report["calls"] = calls
    report["usage_total"] = usage_total
    report["kept"] = len(items)
    report["finished_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    (OUT / "reading_run_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1),
                                                 encoding="utf-8")
    (OUT / "reading_raw.json").write_text(json.dumps({"items": items}, ensure_ascii=False, indent=1),
                                          encoding="utf-8")
    print("calls=%d kept=%d usage=%s" % (calls, len(items), usage_total))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
