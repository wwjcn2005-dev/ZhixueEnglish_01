#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Minimal formal schema migration for P3-07 sentence review.

Only audio_sentence_annotation is migrated. audio_token_annotation is left empty
and untouched as a historical Spike table.
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


CONTENTPACK = Path(r"D:\ZhixueEnglish\structured\contentpack\v5\FLTRP-EN-7A-2022CUR.sqlite")

NEW_SENTENCE_DDL = """
CREATE TABLE audio_sentence_annotation (
  sentence_uid       TEXT PRIMARY KEY,
  textbook_id        TEXT NOT NULL,
  snapshot_id        TEXT,
  audio_id           TEXT NOT NULL,
  unit               TEXT,
  chapter            TEXT,
  activity           TEXT,
  source_page        TEXT,
  sentence_index     INTEGER,
  sentence_text      TEXT NOT NULL,
  source_text        TEXT,
  context_text       TEXT,
  start_ms           INTEGER,
  end_ms             INTEGER,
  status             TEXT NOT NULL CHECK(status IN ('CANDIDATE','VERIFIED','REJECTED')),
  origin             TEXT NOT NULL CHECK(origin IN ('HUMAN','AUTO','HUMAN_CORRECTED')),
  selection_reason   TEXT,
  reject_reason      TEXT,
  pattern_key        TEXT,
  function_tag       TEXT,
  duplicate_of       TEXT,
  review_status      TEXT NOT NULL,
  reviewed_by        TEXT,
  reviewed_at        TEXT,
  source_json        TEXT,
  created_at         TEXT NOT NULL,
  updated_at         TEXT NOT NULL,
  CHECK(start_ms IS NULL OR start_ms >= 0),
  CHECK(end_ms IS NULL OR end_ms > 0),
  CHECK(start_ms IS NULL OR end_ms IS NULL OR start_ms < end_ms)
);
"""


def columns(con: sqlite3.Connection, table: str) -> set:
    return {r[1] for r in con.execute("PRAGMA table_info(%s)" % table)}


def needs_migration(con: sqlite3.Connection) -> bool:
    if not con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='audio_sentence_annotation'"
    ).fetchone():
        return True
    required = {
        "chapter", "context_text", "selection_reason", "reject_reason",
        "pattern_key", "function_tag", "duplicate_of",
    }
    if not required.issubset(columns(con, "audio_sentence_annotation")):
        return True
    ddl = con.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='audio_sentence_annotation'"
    ).fetchone()[0]
    return "REJECTED" not in ddl


def migrate(con: sqlite3.Connection) -> None:
    con.execute("PRAGMA foreign_keys=OFF")
    con.execute("PRAGMA legacy_alter_table=ON")
    con.execute("BEGIN IMMEDIATE")
    try:
        had_old = bool(con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='audio_sentence_annotation'"
        ).fetchone())
        if had_old:
            con.execute("ALTER TABLE audio_sentence_annotation RENAME TO audio_sentence_annotation_legacy")
        con.executescript(NEW_SENTENCE_DDL)
        if had_old:
            old_cols = columns(con, "audio_sentence_annotation_legacy")
            common = [
                c for c in (
                    "sentence_uid", "textbook_id", "snapshot_id", "audio_id", "unit",
                    "activity", "source_page", "sentence_index", "sentence_text",
                    "source_text", "start_ms", "end_ms", "status", "origin",
                    "review_status", "reviewed_by", "reviewed_at", "source_json",
                    "created_at", "updated_at",
                ) if c in old_cols
            ]
            if "sentence_uid" in common:
                target = common + ["chapter", "context_text", "selection_reason",
                                   "reject_reason", "pattern_key", "function_tag", "duplicate_of"]
                select = common + ["NULL", "NULL", "NULL", "NULL", "NULL", "NULL", "NULL"]
                con.execute(
                    "INSERT INTO audio_sentence_annotation (%s) SELECT %s FROM audio_sentence_annotation_legacy" %
                    (",".join(target), ",".join(select)))
            con.execute("DROP TABLE audio_sentence_annotation_legacy")
        con.execute("CREATE INDEX IF NOT EXISTS idx_sentence_annotation_audio "
                    "ON audio_sentence_annotation(audio_id, sentence_index)")
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.execute("PRAGMA legacy_alter_table=OFF")
        con.execute("PRAGMA foreign_keys=ON")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    con = sqlite3.connect(CONTENTPACK)
    try:
        if not args.apply:
            print("DRY_RUN", CONTENTPACK)
            print("needs_migration", needs_migration(con))
            return 0
        before = con.execute("SELECT count(*) FROM audio_sentence_annotation").fetchone()[0] \
            if not needs_migration(con) else 0
        if needs_migration(con):
            migrate(con)
        after = con.execute("SELECT count(*) FROM audio_sentence_annotation").fetchone()[0]
        print("APPLIED", CONTENTPACK)
        print("rows_before", before, "rows_after", after)
        print("columns", sorted(columns(con, "audio_sentence_annotation")))
        print("token_rows", con.execute("SELECT count(*) FROM audio_token_annotation").fetchone()[0])
        print("token_fk", [tuple(r) for r in con.execute("PRAGMA foreign_key_list(audio_token_annotation)")])
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
