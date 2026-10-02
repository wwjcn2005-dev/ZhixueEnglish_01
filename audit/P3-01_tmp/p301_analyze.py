#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P3-01 临时只读分析脚本（不进入正式业务代码）

用途：Starter + Unit 1 官方音频 → 句子级锚定候选。
方法：完全复用项目既有本地方法
  * 解码：builder/mp3_to_wav.ps1（WinRT MediaTranscoder，离线，无安装、无网络）
  * 声学：wave + audioop，HOP_MS=10 / MIN_SPEECH_MS=140 / MIN_GAP_MS=200，
    自适应阈值 thr = max(10 分位 + 12dB, -45dB)（与 builder/build_word_audio_v01.py 一致）

只读边界：不写正式数据库、不改 contentpack / 音频 / web / learning / Android。
输出：TMP 目录下的 JSON/CSV 候选结果。
"""

from __future__ import annotations

import audioop
import hashlib
import json
import math
import re
import sqlite3
import subprocess
import sys
import wave
from pathlib import Path

BASE = Path(r"D:\ZhixueEnglish")
TMP = BASE / "audit" / "P3-01_tmp"
WAV_DIR = TMP / "wav"
TRANSCODER = BASE / "builder" / "mp3_to_wav.ps1"
OFFICIAL_DIR = BASE / "2025年度初一外研版英语教材"
CONTENTPACK = BASE / "structured" / "contentpack" / "v5" / "FLTRP-EN-7A-2022CUR.sqlite"
AUDIO_MAP = BASE / "structured" / "audio" / "exercise_audio_map_v3.json"
CONTENT_REL = BASE / "structured" / "textbook" / "textbook_content_relations_v2.json"
STRUCTURE = BASE / "structured" / "textbook" / "textbook_structure_v2.json"

UNITS = ("Starter", "Unit 1")
HOP_MS, MIN_SPEECH_MS, MIN_GAP_MS = 10, 140, 200

# A9 / A10 教材原页几何修正（与 P2-6-F-4 一致）
BLOCK_ACTIVITY_FIX = {}
for b in ("FLTRP-EN-7A-2022CUR:P10:B1", "FLTRP-EN-7A-2022CUR:P10:B14"):
    BLOCK_ACTIVITY_FIX[b] = "FLTRP-EN-7A-2022CUR:STARTER:GET_READY:A9"
for b in ("FLTRP-EN-7A-2022CUR:P10:B15", "FLTRP-EN-7A-2022CUR:P10:B5", "FLTRP-EN-7A-2022CUR:P10:B6",
          "FLTRP-EN-7A-2022CUR:P10:B7", "FLTRP-EN-7A-2022CUR:P10:B8", "FLTRP-EN-7A-2022CUR:P10:B9",
          "FLTRP-EN-7A-2022CUR:P10:B10", "FLTRP-EN-7A-2022CUR:P10:B11", "FLTRP-EN-7A-2022CUR:P10:B12",
          "FLTRP-EN-7A-2022CUR:P10:B13"):
    BLOCK_ACTIVITY_FIX[b] = "FLTRP-EN-7A-2022CUR:STARTER:GET_READY:A10"


def ro(path):
    c = sqlite3.connect("file:%s?mode=ro" % Path(path).as_posix(), uri=True)
    c.row_factory = sqlite3.Row
    return c


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def transcode(mp3: Path, wav: Path) -> str:
    WAV_DIR.mkdir(parents=True, exist_ok=True)
    cmd = ["powershell.exe", "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass",
           "-File", str(TRANSCODER), "-Src", str(mp3), "-OutDir", str(wav.parent),
           "-OutName", wav.name]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    return (out.stdout or "") + (out.stderr or "")


def load_pcm(wav_path: Path):
    w = wave.open(str(wav_path), "rb")
    ch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
    raw = w.readframes(n)
    w.close()
    if sw != 2:
        raise SystemExit("只支持 16bit PCM")
    if ch == 2:
        raw = audioop.tomono(raw, 2, 0.5, 0.5)
    return raw, sr


def envelope(raw, sr, hop_ms):
    hop = int(sr * hop_ms / 1000.0) * 2
    out = []
    for i in range(0, len(raw) - hop + 1, hop):
        r = audioop.rms(raw[i:i + hop], 2)
        out.append(20.0 * math.log10(r / 32768.0) if r > 0 else -96.0)
    return out


def speech_runs(env, hop_ms, thr, min_speech_ms, min_gap_ms):
    runs, start, end = [], None, None
    for i, db in enumerate(env):
        if db >= thr:
            if start is None:
                start = i
            end = i
        elif start is not None:
            runs.append([start, end]); start = None
    if start is not None:
        runs.append([start, end])
    merged = []
    for r in runs:
        if merged and (r[0] - merged[-1][1]) * hop_ms < min_gap_ms:
            merged[-1][1] = r[1]
        else:
            merged.append(r[:])
    return [{"start_ms": a * hop_ms, "end_ms": (b + 1) * hop_ms, "dur_ms": (b - a + 1) * hop_ms}
            for a, b in merged if (b - a + 1) * hop_ms >= min_speech_ms]


def analyze_wav(wav: Path):
    raw, sr = load_pcm(wav)
    env = envelope(raw, sr, HOP_MS)
    srt = sorted(env)
    thr = max(srt[int(len(srt) * 0.10)] + 12.0, -45.0) if srt else -45.0
    runs = speech_runs(env, HOP_MS, thr, MIN_SPEECH_MS, MIN_GAP_MS)
    return {"sample_rate": sr, "thr_db": round(thr, 1), "total_ms": len(env) * HOP_MS,
            "speech_ms": sum(r["dur_ms"] for r in runs), "runs": runs}


_SENT_END = re.compile(r'(?<=[.!?])(?=["“\'(\[]?\s*[A-Z“\'(\[]|$)')


def split_sentences(text: str) -> list:
    """确定性句子切分：只在句末标点 + 后接空白/引号/大写字母处切。"""
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return []
    parts = [p.strip() for p in _SENT_END.split(text) if p and p.strip()]
    return parts


def is_blank_bearing(text: str) -> bool:
    """教材原页的作答空位：连续 2+ 空格，或夹在词间的孤立数字（印刷空位编号）。"""
    if re.search(r"\S[ \u3000]{2,}\S", text or ""):
        return True
    if re.search(r"(?<=\s)\d{1,2}(?=\s)", text or ""):
        return True
    if re.search(r"[a-z]\s*\d{1,2}(?=[a-z]?\s|$)", (text or "").lower()):
        return True
    return False


def block_texts_for_activity(activity_id, blocks_by_block, rel_map):
    rows = [b for b, a in rel_map.items() if a == activity_id]
    out = []
    for bid in rows:
        b = blocks_by_block.get(bid)
        if b:
            out.append(b)
    out.sort(key=lambda b: (b["page_id"], b["reading_order"]))
    return out


SKIP_KINDS = ("instruction", "heading", "footer_text", "sidebar_tip")
SKIP_ROLES = ("footer", "sidebar")


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def material_by_page(activity_meta, blocks_sorted, activities_on_page):
    """方法 B：该活动所在页只有一个活动时，整页内容块即该活动材料。"""
    if not activity_meta:
        return []
    page = "FLTRP-EN-7A-2022CUR:P%s" % activity_meta["page"]
    if len(activities_on_page.get(page, [])) != 1:
        return []
    return [b for b in blocks_sorted if b["page_id"] == page
            and b["kind"] not in SKIP_KINDS and b["role"] not in SKIP_ROLES]


def material_by_instruction_walk(activity_meta, instruction, blocks_sorted, other_instructions):
    """方法 C：从该活动的 instruction 块开始，按阅读顺序向后取内容块，
    遇到属于其它活动的 instruction 块即停止。"""
    if not activity_meta or not instruction:
        return []
    key = _norm(instruction)[:40]
    start = None
    for i, b in enumerate(blocks_sorted):
        if key and key in _norm(b["text"]):
            start = i
            break
    if start is None:
        return []
    out = []
    for b in blocks_sorted[start + 1:]:
        nk = _norm(b["text"])[:40]
        if b["kind"] == "instruction" or (nk and nk in other_instructions):
            break
        if b["kind"] in SKIP_KINDS or b["role"] in SKIP_ROLES:
            continue
        out.append(b)
    return out


def main():
    TMP.mkdir(parents=True, exist_ok=True)
    amap = json.loads(AUDIO_MAP.read_text(encoding="utf-8"))["audio"]
    targets = [a for a in amap if a.get("unit") in UNITS]

    cp = ro(CONTENTPACK)
    blocks = {r["block_id"]: {"block_id": r["block_id"], "page_id": r["page_id"],
                              "kind": r["block_kind"], "role": r["layout_role"],
                              "reading_order": r["reading_order"], "text": (r["text_raw"] or "").strip()}
              for r in cp.execute("select block_id,page_id,block_kind,layout_role,reading_order,text_raw "
                                  "from content_block")}
    assets = {r["audio_id"]: dict(r) for r in cp.execute(
        "select audio_id,filename,relative_path,sha256,size_bytes,duration_ms from audio_asset")}
    cp.close()

    rel = json.loads(CONTENT_REL.read_text(encoding="utf-8"))["text_references"]
    rel_map = {}
    for r in rel:
        rel_map.setdefault(r["to"], r["from"])
    rel_map.update(BLOCK_ACTIVITY_FIX)

    st = json.loads(STRUCTURE.read_text(encoding="utf-8"))
    act_index = {}
    activities_on_page = {}
    other_instructions = set()
    for u in st.get("units", []):
        for s in u.get("sections", []):
            for a in s.get("activities", []):
                act_index[a["activity_id"]] = {"unit": u["unit_code"], "section": s["section_key"],
                                               "activity_no": a["activity_no"], "page": a["pdf_page"],
                                               "instruction": a.get("instruction")}
                activities_on_page.setdefault("FLTRP-EN-7A-2022CUR:P%s" % a["pdf_page"], []).append(a["activity_id"])
                if a.get("instruction"):
                    other_instructions.add(_norm(a["instruction"])[:40])
    blocks_sorted = sorted(blocks.values(), key=lambda b: (
        int(b["page_id"].rsplit("P", 1)[-1]), b["reading_order"]))

    results = []
    for a in sorted(targets, key=lambda x: x["audio_id"]):
        code = a["audio_id"].split(":")[-1]
        asset = assets.get(a["audio_id"]) or {}
        mp3 = OFFICIAL_DIR / Path(asset.get("filename") or "").name
        rec = {"audio_id": a["audio_id"], "code": code, "filename": asset.get("filename"),
               "unit": a.get("unit"), "section": a.get("section"), "activity_no": a.get("activity_no"),
               "target_type": a.get("target_type"), "target_id": a.get("target_id"),
               "kind": a.get("kind"), "audio_scope": a.get("audio_scope"),
               "audio_status": a.get("status"), "mapping_reason": a.get("reason"),
               "duration_ms": asset.get("duration_ms"),
               "mp3_exists": mp3.is_file(),
               "sha_ok": (sha256(mp3) == (asset.get("sha256") or "").upper()) if mp3.is_file() else False}

        activity_id = a.get("target_id") if a.get("target_type") == "activity" else None
        if not activity_id or activity_id not in act_index:
            # 音频映射用的是 contentpack 活动 id，而 P2-4 重建活动用 A:xxxx / 结构化 id；
            # 用 (unit, section, activity_no) 做确定性回退解析。
            for aid, meta in act_index.items():
                if (meta["unit"] == a.get("unit") and meta["section"] == a.get("section")
                        and meta["activity_no"] == a.get("activity_no")):
                    activity_id = aid
                    break
        rec["activity_id"] = activity_id
        rec["activity_meta"] = act_index.get(activity_id) if activity_id else None

        if activity_id:
            bks = block_texts_for_activity(activity_id, blocks, rel_map)
        else:
            bks = []
        def is_instruction_like(b):
            if b["kind"] in ("instruction", "heading", "footer_text", "sidebar_tip"):
                return True
            n = _norm(b["text"])
            return any(k and k in n for k in other_instructions)

        method = "text_references" if bks else None
        content_bks = [b for b in bks if not is_instruction_like(b) and b["role"] not in SKIP_ROLES]
        if not content_bks and activity_id:
            bks = material_by_page(act_index.get(activity_id), blocks_sorted, activities_on_page)
            content_bks = [b for b in bks if not is_instruction_like(b) and b["role"] not in SKIP_ROLES]
            method = "single_activity_page" if content_bks else method
        if not content_bks and activity_id:
            bks = material_by_instruction_walk(act_index.get(activity_id),
                                               (act_index.get(activity_id) or {}).get("instruction"),
                                               blocks_sorted, other_instructions)
            content_bks = [b for b in bks if not is_instruction_like(b) and b["role"] not in SKIP_ROLES]
            method = "instruction_walk" if content_bks else method
        rec["material_method"] = method
        rec["material_blocks"] = [b["block_id"] for b in content_bks]
        rec["material_text"] = " ".join(b["text"] for b in content_bks)
        rec["material_blank_bearing"] = any(is_blank_bearing(b["text"]) for b in content_bks)
        raw_sentences = split_sentences(rec["material_text"]) if content_bks else []
        rec["sentences"] = [s for s in raw_sentences
                            if len(re.findall(r"[A-Za-z]", s)) >= 4 and len(s.split()) >= 2]

        if mp3.is_file():
            wav = WAV_DIR / ("%s.wav" % code)
            if not (wav.is_file() and wav.stat().st_size > 0):
                log = transcode(mp3, wav)
                rec["transcode"] = log.strip().splitlines()[-1:] and log.strip().splitlines()[-1][:120]
            if wav.is_file() and wav.stat().st_size > 0:
                rec["acoustic"] = analyze_wav(wav)
        results.append(rec)
        print("  %-6s %-8s %-10s runs=%s sentences=%s blanks=%s" % (
            code, rec["unit"], rec["section"], len((rec.get("acoustic") or {}).get("runs") or []),
            len(rec["sentences"]), rec["material_blank_bearing"]), flush=True)

    TMP.joinpath("p301_audio_analysis.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print("written:", TMP / "p301_audio_analysis.json")


if __name__ == "__main__":
    main()
