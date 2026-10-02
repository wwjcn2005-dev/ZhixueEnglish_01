#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P4 第二轮 · 听力理解 AI 批量生成（纯音频材料，一个活动 = 一次调用）

这些活动教材只印了活动指令/残缺框架，听力材料本身在官方 MP3 里。
按已冻结口径（《教材文本、官方音频与播放处理开发依据 V1.1》§6、《最高指导原则》六·9），
使用**已有的 ASR 词级时间 + 已验证 segment** 作为该音频"实际说了什么"的证据，
不新建 transcript 体系、不重跑 ASR。

证据与校验：
  * 题目必须基于给定 ASR 文本逐字可引用的原句（evidence_quote 必须能在该段 ASR 文本中找到）；
  * 正确答案的关键词必须能在所引证据中找到；
  * 每题记录 audio_id + segment_id（ASR 段） + 时间区间。
  校验不过 → 丢弃。

输出：audit/P4B_ai_batch/listening_<AU>.json、listening_raw.json、listening_run_report.json
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
ASR_DIR = BASE / "audit" / "P3-07_preview" / "asr"
OUT = BASE / "audit" / "P4B_ai_batch"
ENDPOINT = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-v4-pro"
MAX_TOKENS = 8192
TEMPERATURE = 0.3
PROMPT_VERSION = "p4b-listening-v1"

#: 纯音频材料活动（教材只印活动指令/残缺框架）。AU25 的"教材句级对齐"仍为 PARTIAL，
#: 本轮按与其他活动同一口径，仅用既有 ASR/segment 证据出题（不涉及、也不放宽 P3-08 边界标准）。
TARGETS = ["AU09", "AU12", "AU16", "AU18", "AU23", "AU25", "AU33", "AU37", "AU39", "AU40",
           "AU43", "AU45"]

SYSTEM = (
    "You write English LISTENING comprehension questions for Chinese junior-high grade 7 students. "
    "You are given the official audio's automatic transcript segments (with ids and times) and the "
    "textbook activity instruction. Output strict JSON.\n\n"
    "HARD RULES\n"
    "1. Use ONLY information that appears in the supplied transcript segments.\n"
    "2. evidence_quote MUST be copied verbatim from the supplied transcript text of that segment.\n"
    "3. evidence_segment_id MUST be the id of the segment containing that quote.\n"
    "4. Options short, mutually exclusive, exactly one correct (one of them is supported by the quote).\n"
    "5. Never invent facts, names, numbers or words that are not in the transcript.\n"
    "6. 2-3 questions per audio; fewer if the material cannot support them.\n"
    "7. Grade-7 level; ask about information retrieval, detail, gist or simple inference. No exam tricks.\n\n"
    "OUTPUT JSON\n"
    '{"questions":[{"stem":"...","options":["...","..."],"answer_index":0,'
    '"evidence_segment_id":"...","evidence_quote":"...","skill":"detail"}]}\n'
)


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFC", str(t or "")).replace("\u2019", "'")
    t = t.replace("\u201c", '"').replace("\u201d", '"')
    return re.sub(r"\s+", " ", t).strip().lower()


def _key() -> str:
    p = Path(os.path.expanduser("~")) / ".codex" / "auth.json"
    return json.loads(p.read_text(encoding="utf-8"))["OPENAI_API_KEY"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=99)
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    OUT.mkdir(parents=True, exist_ok=True)
    key = _key()
    layer = json.loads(LAYER.read_text(encoding="utf-8"))
    by = {r["audio_code"]: r for r in layer["audio_resources"]}
    want = {c for c in args.only.split(",") if c}
    items, calls = [], 0
    usage_total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    report = {"run": "P4B listening comprehension", "model": MODEL, "prompt_version": PROMPT_VERSION,
              "started_at": datetime.datetime.now().isoformat(timespec="seconds"), "tasks": []}

    for code in TARGETS:
        if want and code not in want:
            continue
        if calls >= args.limit:
            break
        res = by[code]
        asr = json.loads((ASR_DIR / (code + ".json")).read_text(encoding="utf-8"))
        segs = [("ASR:%s:%03d" % (code, i + 1), s["start_ms"], s["end_ms"], s["text"])
                for i, s in enumerate(asr.get("segments") or [])]
        lines = "\n".join("[%s %d-%dms] %s" % (sid, a, b, t) for sid, a, b, t in segs)
        seg_text = {sid: t for sid, _, _, t in segs}
        user = ("UNIT: %s\nSECTION: %s\nACTIVITY_AUDIO: %s\n"
                "OFFICIAL AUDIO TRANSCRIPT SEGMENTS (id, time range, text):\n%s\n\n"
                "Write 2-3 multiple-choice listening questions about what is said in this audio."
                % (res["unit_code"], res.get("section_key"), res["filename"], lines))
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
            (OUT / ("listening_%s.json" % code)).write_text(
                json.dumps({"request_user": user, "content": content, "usage": usage},
                           ensure_ascii=False, indent=1), encoding="utf-8")
            kept, dropped = [], []
            for q in parsed.get("questions") or []:
                opts = [str(o).strip() for o in (q.get("options") or []) if str(o).strip()]
                sid = q.get("evidence_segment_id")
                quote = (q.get("evidence_quote") or "").strip()
                stem = (q.get("stem") or "").strip()
                ai = q.get("answer_index")
                bad = None
                if len(opts) < 2 or len(set(opts)) != len(opts):
                    bad = "options_invalid"
                elif not isinstance(ai, int) or not (0 <= ai < len(opts)):
                    bad = "answer_index"
                elif sid not in seg_text:
                    bad = "segment_id"
                elif _norm(quote) not in _norm(seg_text.get(sid, "")):
                    bad = "quote_not_in_transcript"
                elif not stem or len(stem) > 200:
                    bad = "stem_length"
                else:
                    ans_words = [w for w in re.findall(r"[a-z0-9']+", opts[ai].lower()) if len(w) >= 2]
                    if ans_words and not any(w in _norm(quote) for w in ans_words):
                        bad = "answer_unsupported"
                if bad:
                    dropped.append({"reason": bad, "stem": stem[:80]})
                    continue
                sm = next(s for s in segs if s[0] == sid)
                kept.append({"audio": code, "unit": res["unit_code"], "section": res.get("section_key"),
                             "segment_id": sid, "start_ms": sm[1], "end_ms": sm[2],
                             "stem": stem, "options": opts, "answer_index": ai,
                             "quote": quote, "skill": q.get("skill") or "detail"})
            items += kept
            report["tasks"].append({"audio_code": code, "unit": res["unit_code"],
                                    "segments": len(segs), "kept": len(kept), "dropped": dropped,
                                    "usage": usage, "elapsed_s": round(time.time() - t0, 1)})
            print("[%s] segs=%d kept=%d dropped=%d tokens=%s %.0fs"
                  % (code, len(segs), len(kept), len(dropped), usage.get("total_tokens"),
                     time.time() - t0), flush=True)
        except Exception as exc:                                        # noqa: BLE001
            report["tasks"].append({"audio_code": code,
                                    "error": "%s: %s" % (type(exc).__name__, str(exc)[:200])})
            print("[%s] ERROR %s" % (code, exc), flush=True)

    report["calls"] = calls
    report["usage_total"] = usage_total
    report["kept"] = len(items)
    report["finished_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    (OUT / "listening_run_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1),
                                                   encoding="utf-8")
    (OUT / "listening_raw.json").write_text(json.dumps({"run": {"model": MODEL,
                                                                "prompt_version": PROMPT_VERSION},
                                                        "items": items}, ensure_ascii=False, indent=1),
                                            encoding="utf-8")
    print("calls=%d kept=%d usage=%s" % (calls, len(items), usage_total))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
