#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3-07 preview: local faster-whisper transcription for all activity MP3s."""
from __future__ import annotations

import json
import time
from pathlib import Path


BASE = Path(r"D:\ZhixueEnglish")
OUT = BASE / "audit" / "P3-07_preview"
ASR = OUT / "asr"
MODEL = BASE / "models" / "whisper" / "models--Systran--faster-whisper-small" / "snapshots" / "536b0662742c02347bc0e980a01041f333bce120"


def main() -> int:
    from faster_whisper import WhisperModel
    ASR.mkdir(parents=True, exist_ok=True)
    items = json.loads((OUT / "audio_index.json").read_text(encoding="utf-8"))
    t0 = time.time()
    model = WhisperModel(str(MODEL), device="cpu", compute_type="int8",
                         num_workers=1, local_files_only=True)
    print("model_loaded_s", round(time.time() - t0, 1), flush=True)
    total = len(items)
    for n, item in enumerate(items, 1):
        out_path = ASR / (item["audio_num"] + ".json")
        if out_path.exists():
            print("[%d/%d] SKIP %s" % (n, total, item["audio_num"]), flush=True)
            continue
        started = time.time()
        segments, info = model.transcribe(
            item["absolute_path"], language="en", beam_size=1,
            word_timestamps=True, vad_filter=False,
            condition_on_previous_text=False)
        segs = []
        words = []
        for s in segments:
            segs.append({
                "start_ms": int(round(s.start * 1000)),
                "end_ms": int(round(s.end * 1000)),
                "text": s.text.strip(),
            })
            for w in (s.words or []):
                words.append({
                    "word": w.word.strip(),
                    "start_ms": int(round(w.start * 1000)),
                    "end_ms": int(round(w.end * 1000)),
                })
        payload = {
            "audio_id": item["audio_id"],
            "audio_num": item["audio_num"],
            "filename": item["filename"],
            "duration_ms": item["duration_ms"],
            "segment_count": len(segs),
            "word_count": len(words),
            "segments": segs,
            "words": words,
            "runtime": {
                "model": "small",
                "device": "cpu",
                "compute_type": "int8",
                "local_files_only": True,
                "elapsed_s": round(time.time() - started, 1),
            },
        }
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print("[%d/%d] %s duration=%.1fs words=%d elapsed=%.1fs"
              % (n, total, item["audio_num"], item["duration_ms"] / 1000.0,
                 len(words), payload["runtime"]["elapsed_s"]), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
