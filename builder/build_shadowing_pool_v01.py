#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P8-Read-B · 正式跟读资源池注册（只登记 P8-Read 已核验的句级资源）

本轮只做「已有验证成果 → 正式资源池」的落地，不重新发现资源：
  * 输入：`structured/audio/resources/audio_resource_v1.json` 中 P8-Read 已核验的
    VERIFIED 句级段（教材正文逐字命中 + 官方 MP3 + 精确 start_ms/end_ms）；
  * 输出：`structured/audio/resources/shadowing_pool_v1.json`（最小正式登记文件）。

规则：
  1. 不使用词汇音频、不改写教材句、不推导任何新时间范围（时间一律取自既有验证证据）；
  2. MEDIUM 条目先做**静态边界确认**（语音窗口 ⊆ 段落窗口 / 与相邻段不重叠 /
     语速合理 / 边界状态与置信度达标）→ 通过才登记；
  3. 同句多音源时，采用与该教材正文活动归属一致的既有正式题源位置，另一处记入 alternate；
  4. 已在既有正式读取链（题库句子题）中服务的句子标 served_by=questionbank（不重复供给）。

运行：python builder\build_shadowing_pool_v01.py [--write]
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
AUDIO_RESOURCE = BASE / "structured" / "audio" / "resources" / "audio_resource_v1.json"
OUT_PATH = BASE / "structured" / "audio" / "resources" / "shadowing_pool_v1.json"
CONTENTPACK = BASE / "structured" / "contentpack" / "v5" / "FLTRP-EN-7A-2022CUR.sqlite"
QUESTIONBANK = BASE / "structured" / "questionbank" / "questionbank.db"
UNIT_ORDER = ("Starter", "Unit 1", "Unit 2", "Unit 3", "Unit 4", "Unit 5", "Unit 6")
DIGIT_RESIDUE = (r"\([^)]*\d[^)]*\)", r"\d\s*/\s*\d")

#: P8-Read 已核验的高价值跟读句（Unit, 教材页, content_block, audio, start_ms, end_ms, 原文, 置信度）
AUDITED = (
    ("Starter", 3, "FLTRP-EN-7A-2022CUR:P8:B20", "AU02", 28480, 31760, "They are all in my pencil case.", "HIGH"),
    ("Starter", 9, "FLTRP-EN-7A-2022CUR:P14:B7", "AU05", 17060, 20580, "I’m Mr Pan, your English teacher.", "HIGH"),
    ("Starter", 9, "FLTRP-EN-7A-2022CUR:P14:B7", "AU05", 20940, 23880, "I’m so happy to meet you all.", "HIGH"),
    ("Starter", 9, "FLTRP-EN-7A-2022CUR:P14:B7", "AU05", 23800, 29960, "I like playing the piano, reading books and travelling.", "HIGH"),
    ("Starter", 9, "FLTRP-EN-7A-2022CUR:P14:B7", "AU05", 35040, 39340, "This year, we’ll explore the world of English together.", "HIGH"),
    ("Starter", 9, "FLTRP-EN-7A-2022CUR:P14:B7", "AU05", 39840, 41940, "It’ll be a lot of fun!", "HIGH"),
    ("Starter", 9, "FLTRP-EN-7A-2022CUR:P14:B7", "AU05", 42820, 46520, "Now, it’s your turn to introduce yourselves.", "HIGH"),
    ("Unit 1", 17, "FLTRP-EN-7A-2022CUR:P22:B2", "AU07", 40300, 43850, "But is it OK to point out the mistake?", "HIGH"),
    ("Unit 1", 17, "FLTRP-EN-7A-2022CUR:P22:B5", "AU07", 68580, 70060, "I put up my hand.", "HIGH"),
    ("Unit 1", 17, "FLTRP-EN-7A-2022CUR:P22:B7", "AU07", 85340, 89970, "In fact, this is my first lesson for all of you.", "HIGH"),
    ("Unit 1", 17, "FLTRP-EN-7A-2022CUR:P22:B7", "AU07", 90500, 93680, "You are now in junior high school.", "HIGH"),
    ("Unit 1", 17, "FLTRP-EN-7A-2022CUR:P22:B7", "AU07", 93840, 96110, "Learning will be more difficult.", "HIGH"),
    ("Unit 1", 23, "FLTRP-EN-7A-2022CUR:P28:B22", "AU12", 57320, 59520, "A project may take weeks.", "HIGH"),
    ("Unit 3", 48, "FLTRP-EN-7A-2022CUR:P53:B5", "AU21", 32400, 36460, "This is from my favourite film, Postmen in the Mountains.", "HIGH"),
    ("Unit 3", 48, "FLTRP-EN-7A-2022CUR:P53:B5", "AU21", 37340, 41720, "It’s a touching story about the love between father and son.", "HIGH"),
    ("Unit 3", 48, "FLTRP-EN-7A-2022CUR:P53:B6", "AU21", 47700, 52100, "He was often absent from home and the son seldom saw him.", "HIGH"),
    ("Unit 3", 48, "FLTRP-EN-7A-2022CUR:P53:B6", "AU21", 52640, 56120, "But now the son is taking over his father’s position.", "HIGH"),
    ("Unit 3", 48, "FLTRP-EN-7A-2022CUR:P53:B6", "AU21", 56700, 60250, "The father goes with him on his first day of work.", "HIGH"),
    ("Unit 3", 49, "FLTRP-EN-7A-2022CUR:P54:B0", "AU21", 72540, 77040, "It brings back the father’s memory of carrying the son on his back.", "HIGH"),
    ("Unit 3", 49, "FLTRP-EN-7A-2022CUR:P54:B0", "AU21", 77080, 80740, "Tears quietly run down his face.", "HIGH"),
    ("Unit 3", 49, "FLTRP-EN-7A-2022CUR:P54:B1", "AU21", 86520, 88780, "He is happy about his son’s growth.", "HIGH"),
    ("Unit 3", 49, "FLTRP-EN-7A-2022CUR:P54:B1", "AU21", 88870, 92340, "But he just hides his care in his heart.", "HIGH"),
    ("Unit 3", 49, "FLTRP-EN-7A-2022CUR:P54:B1", "AU21", 93120, 95940, "He doesn’t give hugs or kisses to his son.", "HIGH"),
    ("Unit 3", 49, "FLTRP-EN-7A-2022CUR:P54:B1", "AU21", 97000, 98740, "His love may be silent.", "HIGH"),
    ("Unit 3", 49, "FLTRP-EN-7A-2022CUR:P54:B1", "AU21", 99080, 102240, "But like a mountain, it is always there.", "HIGH"),
    ("Unit 3", 54, "FLTRP-EN-7A-2022CUR:P59:B12", "AU23", 30600, 34520, "Every day, she dresses up as a queen.", "HIGH"),
    ("Unit 3", 56, "FLTRP-EN-7A-2022CUR:P61:B5", "AU27", 23600, 26180, "They are always close to each other.", "HIGH"),
    ("Unit 3", 56, "FLTRP-EN-7A-2022CUR:P61:B5", "AU27", 33540, 39200, "He has to stay at home every day and he often feels lonely.", "HIGH"),
    ("Unit 3", 56, "FLTRP-EN-7A-2022CUR:P61:B5", "AU27", 40100, 42730, "He wants to join the other kids.", "HIGH"),
    ("Unit 3", 56, "FLTRP-EN-7A-2022CUR:P61:B5", "AU27", 43360, 45880, "He wants to go out and play.", "HIGH"),
    ("Unit 3", 56, "FLTRP-EN-7A-2022CUR:P61:B7", "AU27", 56300, 61180, "He puts Robert in a trailer and pulls it along with his bike.", "HIGH"),
    ("Unit 3", 56, "FLTRP-EN-7A-2022CUR:P61:B7", "AU27", 62060, 66640, "For the first time, Robert feels like the other kids.", "HIGH"),
    ("Unit 3", 56, "FLTRP-EN-7A-2022CUR:P61:B7", "AU27", 67040, 71040, "A big, bright smile appears on his face.", "HIGH"),
    ("Unit 3", 57, "FLTRP-EN-7A-2022CUR:P62:B0", "AU27", 78520, 81960, "It is hard for John to pull Robert’s trailer.", "HIGH"),
    ("Unit 3", 57, "FLTRP-EN-7A-2022CUR:P62:B0", "AU27", 82400, 86240, "But John refuses to race without his brother.", "HIGH"),
    ("Unit 3", 57, "FLTRP-EN-7A-2022CUR:P62:B0", "AU27", 87100, 88860, "They don’t often win.", "HIGH"),
    ("Unit 3", 57, "FLTRP-EN-7A-2022CUR:P62:B0", "AU27", 89080, 94540, "But for the brothers, some things are more important than winning.", "HIGH"),
    ("Unit 3", 57, "FLTRP-EN-7A-2022CUR:P62:B1", "AU27", 98580, 101400, "“We are family,” John says.", "HIGH"),
    ("Unit 4", 73, "FLTRP-EN-7A-2022CUR:P78:B1", "AU34", 69600, 74520, "But she never regrets her decision to be an ER doctor.", "HIGH"),
    ("Unit 4", 73, "FLTRP-EN-7A-2022CUR:P78:B2", "AU34", 91960, 96660, "They give up their family time to answer the call of duty.", "HIGH"),
    ("Unit 5", 81, "FLTRP-EN-7A-2022CUR:P86:B0", "AU35", 24680, 28960, "He’s going to start work in the plant.", "HIGH"),
    ("Unit 5", 81, "FLTRP-EN-7A-2022CUR:P86:B1", "AU35", 40300, 44940, "They collect sunlight and CO2 during the day.", "MEDIUM"),
    ("Unit 5", 81, "FLTRP-EN-7A-2022CUR:P86:B1", "AU35", 45840, 49220, "Now workers from the Root send up water.", "HIGH"),
    ("Unit 5", 81, "FLTRP-EN-7A-2022CUR:P86:B1", "AU35", 50040, 53820, "The water will rise up to the Leaf through the Stem.", "HIGH"),
    ("Unit 5", 81, "FLTRP-EN-7A-2022CUR:P86:B1", "AU35", 54920, 60350, "Then workers in the Leaf will mix water, CO2 and sunlight.", "MEDIUM"),
    ("Unit 5", 81, "FLTRP-EN-7A-2022CUR:P86:B2", "AU35", 64100, 68100, "Most importantly (for them), there will be sugar!", "HIGH"),
    ("Unit 5", 81, "FLTRP-EN-7A-2022CUR:P86:B2", "AU35", 68980, 71780, "It’s useful for the growth of the plant.", "HIGH"),
    ("Unit 5", 81, "FLTRP-EN-7A-2022CUR:P86:B2", "AU35", 72620, 77940, "Another product will be oxygen, but the plant doesn’t need much of it.", "HIGH"),
    ("Unit 5", 81, "FLTRP-EN-7A-2022CUR:P86:B2", "AU35", 78420, 83620, "It means a lot to animals and humans, though – they need it to breathe!", "HIGH"),
    ("Unit 5", 81, "FLTRP-EN-7A-2022CUR:P86:B3", "AU35", 87400, 89500, "Soon it’s going to get dark.", "HIGH"),
    ("Unit 5", 81, "FLTRP-EN-7A-2022CUR:P86:B5", "AU35", 95880, 98210, "They give more than food and oxygen.", "HIGH"),
    ("Unit 5", 81, "FLTRP-EN-7A-2022CUR:P86:B5", "AU35", 98900, 103250, "Without plants, the natural world would be very different!", "HIGH"),
    ("Unit 5", 86, "FLTRP-EN-7A-2022CUR:P91:B14", "AU37", 57700, 60720, "People even use it to make toys.", "HIGH"),
    ("Unit 5", 86, "FLTRP-EN-7A-2022CUR:P91:B14", "AU37", 61280, 64830, "It’s also part of Mexican culture.", "HIGH"),
    ("Unit 5", 87, "FLTRP-EN-7A-2022CUR:P92:B10", "AU40", 33790, 37340, "We make chips with corn seeds, too.", "HIGH"),
    ("Unit 6", 96, "FLTRP-EN-7A-2022CUR:P101:B1", "AU42", 36440, 39630, "I’m watching pigeons in the park now.", "HIGH"),
    ("Unit 6", 96, "FLTRP-EN-7A-2022CUR:P101:B1", "AU42", 44420, 46860, "They leave droppings here and there.", "HIGH"),
    ("Unit 6", 96, "FLTRP-EN-7A-2022CUR:P101:B1", "AU42", 47560, 51380, "Pigeons are BORING and DIRTY!", "HIGH"),
    ("Unit 6", 96, "FLTRP-EN-7A-2022CUR:P101:B2", "AU42", 52640, 54360, "A girl is feeding them.", "HIGH"),
    ("Unit 6", 97, "FLTRP-EN-7A-2022CUR:P102:B0", "AU42", 63720, 66520, "I’m doing some online research.", "HIGH"),
    ("Unit 6", 97, "FLTRP-EN-7A-2022CUR:P102:B0", "AU42", 67200, 71000, "Pigeons can recognise themselves in mirrors.", "MEDIUM"),
    ("Unit 6", 97, "FLTRP-EN-7A-2022CUR:P102:B1", "AU42", 80660, 82790, "I’m back at the park again.", "HIGH"),
    ("Unit 6", 97, "FLTRP-EN-7A-2022CUR:P102:B1", "AU42", 84380, 87420, "That pigeon is looking at itself in the water!", "HIGH"),
    ("Unit 6", 97, "FLTRP-EN-7A-2022CUR:P102:B1", "AU42", 88100, 90610, "Maybe I was wrong about pigeons.", "HIGH"),
    ("Unit 6", 97, "FLTRP-EN-7A-2022CUR:P102:B2", "AU42", 94760, 97400, "I’m reading in the library now.", "HIGH"),
    ("Unit 6", 97, "FLTRP-EN-7A-2022CUR:P102:B2", "AU42", 97980, 102360, "Oh, there are over 200 kinds of pigeons.", "HIGH"),
    ("Unit 6", 97, "FLTRP-EN-7A-2022CUR:P102:B2", "AU42", 103120, 108240, "Some can fly several thousand kilometres and don’t get lost.", "HIGH"),
    ("Unit 6", 97, "FLTRP-EN-7A-2022CUR:P102:B2", "AU42", 108880, 114860, "They can also fly at speeds of over 100 km per hour.", "HIGH"),
    ("Unit 6", 97, "FLTRP-EN-7A-2022CUR:P102:B2", "AU42", 115360, 118080, "That’s as fast as my dad’s car!", "HIGH"),
    ("Unit 6", 97, "FLTRP-EN-7A-2022CUR:P102:B3", "AU42", 119240, 123180, "Well, pigeons aren’t boring or scary.", "HIGH"),
    ("Unit 6", 97, "FLTRP-EN-7A-2022CUR:P102:B3", "AU42", 123520, 128440, "They are AMAZING – I just didn’t know enough about them!", "HIGH"),
    ("Unit 6", 102, "FLTRP-EN-7A-2022CUR:P107:B4", "AU43", 37180, 40790, "Over the years, he saved many lives.", "HIGH"),
)

#: 同句双音源 → 采用与教材正文活动归属一致的既有正式题源位置（另一处记入 alternate）
DUAL_SOURCE_CHOICE = {
    "People even use it to make toys.": ("AU39", 54680, 57730, "AU37", 57700, 60720),
    "It’s also part of Mexican culture.": ("AU39", 58400, 61830, "AU37", 61280, 64830),
    "Over the years, he saved many lives.": ("AU45", 33600, 37180, "AU43", 37180, 40790),
}
DUAL_SOURCE_REASON = ("同句存在两处可靠音源（同一录音的两个活动位置）；采用与该教材正文活动"
                      "归属一致的既有正式题源位置，另一处仅登记为 alternate，不重复供给。")


def _norm(text) -> str:
    t = unicodedata.normalize("NFC", str(text or "")).lower()
    t = t.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    return re.sub(r"\s+", " ", t).strip()


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--out", default=str(OUT_PATH))
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    data = json.loads(AUDIO_RESOURCE.read_text(encoding="utf-8"))
    resources = {r["audio_code"]: r for r in data["audio_resources"]}
    segs = {}
    for r in data["audio_resources"]:
        for s in (r.get("segments") or []):
            if s.get("status") == "VERIFIED" and s.get("text_resource_kind") == "content_block":
                segs[(r["audio_code"], s["text_resource_id"], int(s["start_ms"]), int(s["end_ms"]))] = s
    by_audio_block = {}
    for (code, block, s0, s1), s in segs.items():
        by_audio_block.setdefault((code, block), []).append(s)

    cp = sqlite3.connect("file:%s?mode=ro" % CONTENTPACK.as_posix(), uri=True)
    cp.row_factory = sqlite3.Row
    block_text = {r["block_id"]: (r["text_raw"] or "") for r in
                  cp.execute("SELECT block_id, text_raw FROM content_block")}
    page_of = {r["block_id"]: r["textbook_page"] for r in cp.execute(
        "SELECT cb.block_id, p.textbook_page FROM content_block cb JOIN page p ON p.page_id=cb.page_id")}
    cp.close()

    # 既有正式读取链（题库句子题）已在服务的句子 → 避免重复供给
    served_texts = set()
    qb = sqlite3.connect("file:%s?mode=ro" % QUESTIONBANK.as_posix(), uri=True)
    qb.row_factory = sqlite3.Row
    for r in qb.execute("SELECT prompt_json, answer_json FROM question WHERE question_type IN "
                        "('sentence_listen_write','sentence_listen_choice')"):
        prompt = json.loads(r["prompt_json"] or "{}")
        answer = json.loads(r["answer_json"] or "{}")
        if prompt.get("audio_url") and prompt.get("start_ms") is not None:
            served_texts.add(_norm(answer.get("text")))
    qb.close()

    entries, problems, medium_checks = [], [], []
    seen = {}
    for unit, page, block, code, s0, s1, text, conf in AUDITED:
        if (code, block, int(s0), int(s1)) not in segs:
            problems.append("段不存在或非 VERIFIED：%s %s %d-%d" % (code, block, s0, s1))
            continue
        if _norm(text) not in _norm(block_text.get(block, "")):
            problems.append("教材原文不逐字命中：%s %s" % (code, text[:40]))
            continue
        if not (0 < int(s0) < int(s1)):
            problems.append("时间非法：%s %s" % (code, text[:40]))
            continue
        key = _norm(text)
        if key in seen:
            problems.append("同句重复：%s" % text[:40])
            continue
        seen[key] = True
        seg = segs[(code, block, int(s0), int(s1))]
        ev = seg.get("alignment_evidence") or {}
        start_ms, end_ms = int(s0), int(s1)
        status, confidence, alternate = "VERIFIED", conf, None

        # B. MEDIUM：静态边界确认（不改时间、不重跑 ASR）
        if conf == "MEDIUM":
            neighbours = sorted(by_audio_block[(code, block)], key=lambda x: x["start_ms"])
            idx = [i for i, x in enumerate(neighbours) if x["segment_id"] == seg["segment_id"]][0]
            prev_s = neighbours[idx - 1] if idx > 0 else None
            next_s = neighbours[idx + 1] if idx + 1 < len(neighbours) else None
            sp0, sp1 = ev.get("speech_start_ms"), ev.get("speech_end_ms")
            words = len([w for w in re.findall(r"[A-Za-z']+", text)])
            wpm = words / ((end_ms - start_ms) / 60000.0)
            checks = {
                "speech_window_inside_segment": bool(sp0 is not None and sp1 is not None
                                                     and start_ms <= sp0 < sp1 <= end_ms),
                "no_overlap_with_neighbours": bool(
                    (prev_s is None or prev_s["end_ms"] <= start_ms)
                    and (next_s is None or next_s["start_ms"] >= end_ms)),
                "speaking_rate_plausible": 60 <= wpm <= 220,
                "boundary_status_and_confidence": (ev.get("boundary_status") in ("GOOD_BOUNDARY", "AUTO_RESOLVED")
                                                   and ev.get("boundary_confidence") == "HIGH"),
            }
            medium_checks.append({"text": text, "audio_code": code, "start_ms": start_ms,
                                  "end_ms": end_ms, "match_score": ev.get("match_score"),
                                  "speech_start_ms": sp0, "speech_end_ms": sp1,
                                  "words_per_minute": round(wpm, 1), "checks": checks,
                                  "confirmed": all(checks.values()),
                                  "method": "静态确认（既有对齐证据 + 相邻段不重叠 + 语速合理），未重跑 ASR"})
            if not all(checks.values()):
                problems.append("MEDIUM 静态确认未通过：%s" % text[:40])
                continue
            status, confidence = "STATIC_CONFIRMED", "HIGH(static)"

        # C. 同句双音源：采用既有正式题源位置
        if text in DUAL_SOURCE_CHOICE:
            chosen_audio, cs0, cs1, alt_audio, as0, as1 = DUAL_SOURCE_CHOICE[text]
            if (chosen_audio, block, cs0, cs1) not in segs or (alt_audio, block, as0, as1) not in segs:
                problems.append("双音源证据缺失：%s" % text[:40])
                continue
            if code != chosen_audio:                       # 换用既有正式位置的时间
                code, start_ms, end_ms = chosen_audio, cs0, cs1
                seg = segs[(chosen_audio, block, cs0, cs1)]
                ev = seg.get("alignment_evidence") or {}
            alternate = {"audio_code": alt_audio, "start_ms": as0, "end_ms": as1,
                         "reason": DUAL_SOURCE_REASON}

        rid = "SHP:" + hashlib.sha1(("|".join([unit, code, str(start_ms), key])).encode("utf-8")
                                    ).hexdigest()[:12].upper()
        entries.append({
            "resource_id": rid, "unit_code": unit, "textbook_page": page,
            "content_block": block, "text": text,
            "audio_code": code, "audio_url": "/audio/official/%s.mp3" % code,
            "start_ms": start_ms, "end_ms": end_ms,
            "registration": "P8_READ_VERIFIED", "verification_status": status,
            "confidence": confidence, "segment_id": seg["segment_id"],
            "alignment_method": seg.get("alignment_method"),
            "source_artifact": seg.get("source_artifact"),
            "evidence_ref": "P8-Read 报告 §4 + P3-07 深审边界复核（audio_resource_v1.json VERIFIED）",
            "served_by": "questionbank" if key in served_texts else "shadowing_pool",
            "pool_role": "BACKFILL" if key in served_texts else "SERVE",
            "alternate_source": alternate})

    entries.sort(key=lambda e: (UNIT_ORDER.index(e["unit_code"]), e["audio_code"], e["start_ms"]))
    order = {"RECOMMENDED_AUDITED": 0}
    result = {
        "layer": "shadowing_pool", "version": "v1",
        "generated_by": "builder/build_shadowing_pool_v01.py",
        "generated_at": _now(), "ai_calls": 0,
        "principle": ("教材原文为权威文本；官方教材 MP3 为权威声音来源；ASR/对齐仅作时间定位证据；"
                      "只登记已核验句级资源，不猜时间、不改写教材句。"),
        "sources": [{"path": "structured/audio/resources/audio_resource_v1.json",
                     "sha256": _sha(AUDIO_RESOURCE)},
                    {"path": "structured/contentpack/v5/FLTRP-EN-7A-2022CUR.sqlite",
                     "sha256": _sha(CONTENTPACK)},
                    {"path": "structured/questionbank/questionbank.db", "sha256": _sha(QUESTIONBANK)}],
        "rules": {
            "registration_scope": "P8-Read 已核验的 72 条高价值教材句（69 HIGH + 3 MEDIUM 静态确认）",
            "no_new_time_derivation": "所有 start_ms/end_ms 取自既有 VERIFIED 句级段或既有正式题源位置",
            "medium_handling": "静态确认：语音窗口 ⊆ 段落窗口 / 与相邻段不重叠 / 语速合理 / 边界状态与置信度达标",
            "dual_source_handling": DUAL_SOURCE_REASON,
            "duplicate_policy": "同一教材句在池中只登记一次；已被题库句子题服务的句子标 served_by=questionbank，不重复供给",
            "not_included": {"borderline_candidates": 19, "excluded_candidates": 89,
                             "partial_sentence_segments": 263},
        },
        "counts": {"entries": len(entries),
                   "by_verification": {"VERIFIED": sum(1 for e in entries if e["verification_status"] == "VERIFIED"),
                                       "STATIC_CONFIRMED": sum(1 for e in entries if e["verification_status"] == "STATIC_CONFIRMED")},
                   "served_by_questionbank": sum(1 for e in entries if e["served_by"] == "questionbank"),
                   "new_to_app": sum(1 for e in entries if e["pool_role"] == "SERVE"),
                   "dual_source_resolved": sum(1 for e in entries if e.get("alternate_source")),
                   "by_unit": {u: sum(1 for e in entries if e["unit_code"] == u) for u in UNIT_ORDER},
                   "by_audio": {c: sum(1 for e in entries if e["audio_code"] == c)
                                for c in sorted({e["audio_code"] for e in entries})}},
        "medium_static_confirmation": medium_checks,
        "entries": entries}

    print("entries:", len(entries), "| by_verification:", result["counts"]["by_verification"])
    print("served_by_questionbank:", result["counts"]["served_by_questionbank"],
          "| new_to_app:", result["counts"]["new_to_app"])
    print("by unit:", result["counts"]["by_unit"])
    print("by audio:", result["counts"]["by_audio"])
    print("problems:", len(problems), problems[:5])
    if problems:
        print("STOP：未写文件。")
        return 3
    if args.write:
        out = Path(args.out)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        print("新登记文件 →", out)
        print("  sha256:", _sha(out)[:16])
    else:
        print("（dry-run，未写文件）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
