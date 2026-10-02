#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3-07 isolated sentence review + sentence interval annotation Spike."""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import urllib.parse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.dont_write_bytecode = True

BASE = Path(r"D:\ZhixueEnglish")
CONTENTPACK = BASE / "structured" / "contentpack" / "v5" / "FLTRP-EN-7A-2022CUR.sqlite"
LEARNING_DB = BASE / "structured" / "learning" / "learning.db"
OFFICIAL_DIR = BASE / "2025年度初一外研版英语教材"
SPIKE_DIR = Path(__file__).resolve().parent
CANDIDATES = SPIKE_DIR / "data" / "candidates.json"
SUGGESTED = SPIKE_DIR / "data" / "suggested_locations.json"
DRAFTS = SPIKE_DIR / "data" / "annotations.json"
STATIC = SPIKE_DIR / "static"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def audio_row(audio_num: str):
    con = sqlite3.connect(f"file:{CONTENTPACK}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        return con.execute(
            "SELECT audio_id, filename, duration_ms FROM audio_asset "
            "WHERE audio_id=?", ("FLTRP-EN-7A-2022CUR:" + audio_num,)).fetchone()
    finally:
        con.close()


def candidates_payload() -> dict:
    """Merge non-formal suggested locations into the page candidate payload."""
    data = read_json(CANDIDATES, {})
    suggestions = read_json(SUGGESTED, {})
    for c in data.get("candidates") or []:
        s = suggestions.get(c.get("candidate_id"))
        if s:
            c["suggested_start_ms"] = s.get("suggested_start_ms")
            c["suggested_end_ms"] = s.get("suggested_end_ms")
            c["suggested_status"] = s.get("status")
            c["suggested_source"] = s.get("source")
    return data


def validate_sentence(payload: dict) -> dict:
    status = (payload.get("status") or "CANDIDATE").upper()
    if status not in ("CANDIDATE", "VERIFIED", "REJECTED"):
        raise ValueError("status must be CANDIDATE, VERIFIED or REJECTED")
    text = (payload.get("sentence_text") or "").strip()
    if status in ("CANDIDATE", "VERIFIED") and not text:
        raise ValueError("sentence_text is required")
    if status == "VERIFIED" and "___" in text:
        raise ValueError("VERIFIED sentence still contains ___")
    if status == "REJECTED" and not (payload.get("reject_reason") or "").strip():
        raise ValueError("reject_reason is required for REJECTED")
    audio = audio_row(payload["audio_num"])
    if not audio:
        raise ValueError("audio not found")
    start = payload.get("start_ms")
    end = payload.get("end_ms")
    if status == "VERIFIED":
        if start is None or end is None:
            raise ValueError("VERIFIED requires start_ms and end_ms")
        start, end = int(start), int(end)
        if start < 0 or end <= start or end > int(audio["duration_ms"]):
            raise ValueError("invalid sentence interval")
    else:
        start = None if start in (None, "") else int(start)
        end = None if end in (None, "") else int(end)
        if start is not None and end is not None:
            if start < 0 or end <= start or end > int(audio["duration_ms"]):
                raise ValueError("invalid sentence interval")
    if status == "REJECTED":
        start = end = None
    return {"status": status, "start_ms": start, "end_ms": end, "text": text}


def save_sentence(payload: dict, checked: dict) -> None:
    sentence_uid = "P3-07:" + payload["candidate_id"]
    ts = now_iso()
    con = sqlite3.connect(CONTENTPACK)
    try:
        con.execute("BEGIN IMMEDIATE")
        con.execute(
            """INSERT INTO audio_sentence_annotation
               (sentence_uid, textbook_id, snapshot_id, audio_id, unit, chapter,
                activity, source_page, sentence_index, sentence_text, source_text,
                context_text, start_ms, end_ms, status, origin, selection_reason,
                reject_reason, pattern_key, function_tag, duplicate_of, review_status,
                reviewed_by, reviewed_at, source_json, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(sentence_uid) DO UPDATE SET
                 unit=excluded.unit, chapter=excluded.chapter, activity=excluded.activity,
                 source_page=excluded.source_page, sentence_text=excluded.sentence_text,
                 source_text=excluded.source_text, context_text=excluded.context_text,
                 start_ms=excluded.start_ms, end_ms=excluded.end_ms, status=excluded.status,
                 origin=excluded.origin, selection_reason=excluded.selection_reason,
                 reject_reason=excluded.reject_reason, pattern_key=excluded.pattern_key,
                 function_tag=excluded.function_tag, duplicate_of=excluded.duplicate_of,
                 review_status=excluded.review_status, reviewed_by=excluded.reviewed_by,
                 reviewed_at=excluded.reviewed_at, source_json=excluded.source_json,
                 updated_at=excluded.updated_at""",
            (sentence_uid, "FLTRP-EN-7A-2022CUR", None, payload["audio_id"],
             payload.get("unit"), payload.get("chapter"), payload.get("activity"),
             payload.get("page"), payload.get("sentence_index"), checked["text"],
             payload.get("source_text"), payload.get("context_text"),
             checked["start_ms"], checked["end_ms"], checked["status"], "HUMAN",
             payload.get("selection_reason"), payload.get("reject_reason"),
             payload.get("pattern_key"), payload.get("function_tag"),
             payload.get("duplicate_of"), checked["status"], payload.get("reviewer") or "local-human",
             ts, json.dumps(payload, ensure_ascii=False), ts, ts))
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


class Handler(BaseHTTPRequestHandler):
    server_version = "ZhixueEnglish-P3-07-Review/0.2"

    def _send(self, code, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload, code=200):
        self._send(code, json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _file(self, path: Path, ctype: str):
        try:
            self._send(200, path.read_bytes(), ctype)
        except OSError:
            self._send(404, b"not found", "text/plain; charset=utf-8")

    def _audio(self, audio_num: str):
        row = audio_row(audio_num)
        if not row:
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return
        path = OFFICIAL_DIR / Path(row["filename"]).name
        try:
            size = path.stat().st_size
        except OSError:
            self._send(404, b"audio file not found", "text/plain; charset=utf-8")
            return
        start, end, code = 0, max(size - 1, 0), 200
        rng = (self.headers.get("Range") or "").strip()
        if rng:
            m = re.match(r"bytes=(\d*)-(\d*)$", rng)
            if m and (m.group(1) or m.group(2)):
                start = int(m.group(1) or 0)
                end = min(int(m.group(2)), size - 1) if m.group(2) else size - 1
                if start > end or start >= size:
                    self.send_response(416)
                    self.send_header("Content-Range", "bytes */%d" % size)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                code = 206
        length = end - start + 1
        self.send_response(code)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        if code == 206:
            self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
        self.end_headers()
        with open(path, "rb") as fh:
            fh.seek(start)
            remaining = length
            while remaining > 0:
                chunk = fh.read(min(65536, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._file(STATIC / "index.html", "text/html; charset=utf-8")
            return
        if path.startswith("/static/"):
            rel = path[len("/static/"):]
            ctype = {"app.js": "application/javascript; charset=utf-8",
                     "style.css": "text/css; charset=utf-8"}.get(rel, "text/plain; charset=utf-8")
            self._file(STATIC / rel, ctype)
            return
        if path == "/api/candidates":
            self._json(candidates_payload())
            return
        if path == "/api/annotations":
            self._json(read_json(DRAFTS, {}))
            return
        if path.startswith("/audio/"):
            self._audio(Path(path).stem)
            return
        self._send(404, b"not found", "text/plain; charset=utf-8")

    def do_POST(self):
        if urllib.parse.urlparse(self.path).path != "/api/save":
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            checked = validate_sentence(payload)
            saved_at = now_iso()
            payload["saved_at"] = saved_at
            drafts = read_json(DRAFTS, {})
            drafts[payload["candidate_id"]] = payload
            write_json(DRAFTS, drafts)
            save_sentence(payload, checked)
            self._json({"ok": True, "status": checked["status"], "saved_at": saved_at})
        except Exception as exc:
            self._json({"ok": False, "error": str(exc)}, 400)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8781)
    args = ap.parse_args()
    print("P3-07 review Spike:", "http://%s:%d/" % (args.host, args.port), flush=True)
    print("learning.db: unused", LEARNING_DB, flush=True)
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
