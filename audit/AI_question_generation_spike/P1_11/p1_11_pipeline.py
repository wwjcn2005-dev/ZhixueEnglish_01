# -*- coding: utf-8 -*-
"""P1-11 implementation module: formal 0-question path + AI quality review file record.

Implements exactly the P1-10 minimal scope:
  · SUCCESS_ZERO_QUESTIONS recorded through the existing generation_run fields
    (status='INSUFFICIENT_EVIDENCE' + insufficient_evidence=1) -- no schema change
  · AI quality review stored as JSON files under structured/ai/quality_review/
    (never into question_validation; never lifecycle / question_event)
  · Chinese review summary fields
  · answer_unique: choices = program-computed from per-candidate flags; fill = NOT_PROVABLE
  · cache keyed by question_fingerprint + review_context_hash + review_version

No AI call happens in this module. No schema change. No lifecycle write.
"""

import datetime
import hashlib
import json
import os
import re
import sqlite3

BASE = r"D:\ZhixueEnglish"
LIB = os.path.join(BASE, "structured", "ai", "question_library.db")
REVIEW_DIR = os.path.join(BASE, "structured", "ai", "quality_review")
REVIEW_VERSION = "P1-11-v1"

# outcomes
HAS_QUESTIONS = "HAS_QUESTIONS"
SUCCESS_ZERO_QUESTIONS = "SUCCESS_ZERO_QUESTIONS"
GENERATION_FAILED = "GENERATION_FAILED"
# answer_uniqueness_status (P1-09-G vocabulary)
AU_NOT_PROVABLE = "NOT_PROVABLE"
AU_SUPPORTED = "UNIQUE_SUPPORTED"
AU_UNCERTAIN = "UNIQUE_UNCERTAIN"
AU_RISK = "UNIQUE_RISK"
# answer_unique (P1-11 field spec vocabulary)
AU_FIELD = {AU_NOT_PROVABLE: "NOT_PROVABLE", AU_SUPPORTED: "PASS",
            AU_UNCERTAIN: "CONCERN", AU_RISK: "FAIL"}


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def tokens(text):
    """Same normalisation as validator_v2.tokens (reused semantics, no new rules)."""
    s = (text or "").lower()
    for a, b in (("\u2019", "'"), ("\u2018", "'"), ("\u201c", " "), ("\u201d", " "),
                 ("`", "'")):
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9' ]+", " ", s)
    s = s.replace("'", " ")
    return [w for w in s.split() if w]


def fingerprint(section, activity, qtype, question, quote):
    """Identical to the P1-07 formula (P1-02/P1-03 lineage)."""
    return sha("\x01".join([section or "", activity or "", qtype or "",
                            " ".join(tokens(question)), " ".join(tokens(quote))]))


def review_context_hash(items):
    """Hash of exactly what the reviewer sees (per item: stem/options/answer/evidence)."""
    payload = []
    for it in items:
        payload.append({"question_id": it["question_id"], "question_type": it["question_type"],
                        "question_text": it["question_text"], "options": it.get("options"),
                        "stored_answer": it["stored_answer"],
                        "textbook_evidence": it.get("textbook_evidence")})
    return sha(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def classify_generation(guard_status, parsed, api_error=None):
    """Formal outcome of one Section-level generation call (P1-10 §4.1)."""
    if api_error or guard_status in ("API_ERROR", "TRUNCATED", "EMPTY_CONTENT"):
        return {"outcome": GENERATION_FAILED, "guard_status": guard_status,
                "reason": api_error or ("guard=%s" % guard_status), "questions": None}
    if not isinstance(parsed, dict) or "questions" not in parsed:
        return {"outcome": GENERATION_FAILED, "guard_status": guard_status,
                "reason": "JSON_INVALID: questions 字段缺失", "questions": None}
    qs = parsed.get("questions")
    if not isinstance(qs, list):
        return {"outcome": GENERATION_FAILED, "guard_status": guard_status,
                "reason": "JSON_INVALID: questions 不是数组", "questions": None}
    if qs:
        return {"outcome": HAS_QUESTIONS, "guard_status": guard_status, "reason": None,
                "questions": qs}
    reason = (parsed.get("insufficient_evidence_reason")
              or parsed.get("no_question_reason") or "").strip()
    if not reason:
        return {"outcome": GENERATION_FAILED, "guard_status": guard_status,
                "reason": "PROTOCOL_INVALID: 0 题但未给出理由", "questions": []}
    return {"outcome": SUCCESS_ZERO_QUESTIONS, "guard_status": guard_status, "reason": reason,
            "questions": []}


def record_generation_run(run_id, scope_key, section_id, unit_id, model, prompt_version,
                          context_hash, context_ref, raw_ref, finish_reason, usage,
                          elapsed_ms, outcome, reason, max_tokens=8192,
                          question_count=0):
    """INSERT one generation_run row. Only 0-question runs are recorded here (P1-11 scope)."""
    if outcome == SUCCESS_ZERO_QUESTIONS:
        status, insuf = "INSUFFICIENT_EVIDENCE", 1
    elif outcome == HAS_QUESTIONS:
        status, insuf = "OK", 0
    else:
        status, insuf = "API_ERROR", 0
    conn = sqlite3.connect(LIB)
    conn.isolation_level = None
    try:
        conn.execute("BEGIN")
        conn.execute(
            "INSERT INTO generation_run (run_id, generation_scope_key, textbook_id, snapshot_id,"
            " unit_id, section_id, activity_id, model, prompt_version, context_hash, provider,"
            " context_ref, raw_response_ref, requested_max, max_tokens, finish_reason, usage_json,"
            " elapsed_ms, question_count, status, insufficient_evidence, error, note, generated_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, scope_key, "FLTRP-EN-7A-2022CUR", None, unit_id, section_id, None, model,
             prompt_version, context_hash, "deepseek", context_ref, raw_ref, None, max_tokens,
             finish_reason, json.dumps(usage, ensure_ascii=False), elapsed_ms, question_count,
             status, insuf, None, reason, now()))
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
    return {"run_id": run_id, "status": status, "insufficient_evidence": insuf,
            "question_count": question_count}


def compute_answer_unique(question_type, candidates, current_answer):
    """Program-side computation. The model never returns the final uniqueness verdict."""
    if question_type == "fill":
        return {"answer_unique": AU_FIELD[AU_NOT_PROVABLE], "answer_unique_status": AU_NOT_PROVABLE,
                "answer_unique_coverage": "NONE",
                "basis": "填空题候选池在现有正式数据下不可建（P1-09-E/G 已确认），"
                         "唯一性无法由系统可靠证明"}
    others = [c for c in candidates if c["candidate_text"] != current_answer]
    valid = [c for c in others if (c["grammar_valid"] == "YES" and c["semantic_valid"] == "YES"
                                  and c["textbook_context_valid"] == "YES")]
    # Second, conservative trigger: the model's own per-candidate roll-up valid_alternative=YES.
    # Rationale (P1-11 finding): the v1 prompt omitted the P1-09-F gloss that
    # textbook_context_valid means "compatible with / not contradicted by", so the model used
    # "supported by" semantics and marked a genuine alternative as context_valid=NO while still
    # answering valid_alternative=YES. Using the roll-up as an ADDITIONAL trigger can only turn
    # UNIQUE_SUPPORTED into UNIQUE_RISK, never the reverse, so it cannot create a false "unique".
    rollup = [c for c in others if str(c.get("valid_alternative", "")).upper() == "YES"]
    flagged = sorted({c["candidate_text"] for c in valid + rollup})
    need_ctx = [c for c in candidates if c.get("need_more_context") == "YES"]
    if flagged:
        st = AU_RISK
        basis = ("存在 %d 个非当前答案选项被判为可能成立"
                 "（三字段全 YES 的有 %d 个；模型 valid_alternative=YES 的有 %d 个）"
                 % (len(flagged), len(valid), len(rollup)))
    elif need_ctx:
        st = AU_UNCERTAIN
        basis = "有 %d 个候选 need_more_context=YES" % len(need_ctx)
    elif current_answer and any(c["candidate_text"] == current_answer
                                and c["grammar_valid"] == "YES"
                                and c["semantic_valid"] == "YES"
                                and c["textbook_context_valid"] == "YES" for c in candidates):
        st = AU_SUPPORTED
        basis = "所有非当前答案选项均被排除，且候选集合完整（=题目选项）"
    else:
        st = AU_UNCERTAIN
        basis = "当前答案本身未被判定为有效，无法支撑唯一性结论"
    return {"answer_unique": AU_FIELD[st], "answer_unique_status": st,
            "answer_unique_coverage": "COMPLETE", "basis": basis,
            "flagged_candidates": flagged,
            "flagged_by_three_flags": [c["candidate_text"] for c in valid],
            "flagged_by_model_rollup": [c["candidate_text"] for c in rollup]}


def ensure_review_dir():
    os.makedirs(REVIEW_DIR, exist_ok=True)
    return REVIEW_DIR


def write_review_run(review_run_id, reviews, meta=None):
    """One AI quality review run -> one JSON file (never a database table)."""
    ensure_review_dir()
    doc = {"review_run_id": review_run_id, "review_version": REVIEW_VERSION,
           "written_at": now(), "review_count": len(reviews),
           "meta": meta or {},
           "reviews": reviews}
    # Windows file names cannot contain ':' -> sanitise the file name only
    fname = re.sub(r"[^A-Za-z0-9._-]+", "_", review_run_id) + ".json"
    path = os.path.join(REVIEW_DIR, fname)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2)
    return path


def iter_review_files():
    if not os.path.isdir(REVIEW_DIR):
        return []
    return [os.path.join(REVIEW_DIR, f) for f in sorted(os.listdir(REVIEW_DIR))
            if f.endswith(".json")]


def cache_lookup(question_fingerprint, ctx_hash, review_version=REVIEW_VERSION):
    """Reuse key = fingerprint + review_context_hash + review_version (P1-11 实施5)."""
    matches = []
    for path in iter_review_files():
        try:
            doc = json.load(open(path, encoding="utf-8"))
        except Exception:
            continue
        if doc.get("review_version") != review_version:
            continue
        for rec in doc.get("reviews", []):
            if (rec.get("question_fingerprint") == question_fingerprint
                    and rec.get("review_context_hash") == ctx_hash):
                matches.append((rec.get("assessed_at") or doc.get("written_at") or "", path, rec))
    if matches:
        # 同一 key 出现多条时取最新一条（避免旧文件遮蔽新结论）
        matches.sort(key=lambda m: m[0])
        newest = matches[-1]
        return {"hit": True, "file": newest[1], "record": newest[2],
                "matching_records": len(matches),
                "reason": "fingerprint + review_context_hash + review_version 三项完全一致"
                          "（取最新一条）"}
    return {"hit": False, "file": None, "record": None,
            "matching_records": 0,
            "reason": "没有三项一致的既有审核记录 → 允许产生新的审核结果"}


def human_view(record):
    """Exactly what a future UI may show (no technical metadata)."""
    return {"这道题": record.get("question_text"),
            "AI审核提示": record.get("suggested_decision"),
            "教材依据": record.get("evidence_note_zh"),
            "需要注意的问题": record.get("issues_zh"),
            "AI说明": record.get("summary_zh"),
            "采用或不采用": None}


FORBIDDEN_IN_RECORD = ["lifecycle_status", "active", "question_event", "APPROVED", "ACTIVE",
                       "reasoning_tokens", "validator_code"]


def check_record_safety(record):
    """Guard: the review record must not carry lifecycle or forbidden technical payload."""
    bad = [k for k in FORBIDDEN_IN_RECORD if k in record]
    return {"ok": not bad, "forbidden_keys_present": bad}
