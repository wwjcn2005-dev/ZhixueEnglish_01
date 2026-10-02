"""P1-07 · 唯一允许写 question_library.db 的步骤。

规则：
  * 只写 decision == PASS 的候选；其它一律不入库
  * 整个入库一个事务；任何异常 → rollback（不留半批次）
  * 生命周期只能是 GENERATED → VALIDATED → PENDING_REVIEW
  * 绝不产生 APPROVED / ACTIVE / REVIEW_APPROVED
  * 绝不触碰已有的 2 道题
  * 不新增表/列
"""
import datetime
import hashlib
import json
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = r"D:\ZhixueEnglish"
SPIKE = os.path.join(BASE, "audit", "AI_question_generation_spike")
LIB = os.path.join(BASE, "structured", "ai", "question_library.db")
CP = os.path.join(BASE, "structured", "contentpack", "v5", "FLTRP-EN-7A-2022CUR.sqlite")
CAND = os.path.join(HERE, "candidate_decision.json")
TEXTBOOK_ID = "FLTRP-EN-7A-2022CUR"

sys.path.insert(0, os.path.join(SPIKE, "P1_04_rule_fixes"))
import validator_v3 as V3  # noqa: E402


def sha_file(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest().upper()


def dump(name, obj):
    with open(os.path.join(HERE, name), "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)


def main():
    cand = json.load(open(CAND, encoding="utf-8"))
    rows = cand["candidates"]
    passes = [r for r in rows if r["decision"] == "PASS"]
    ids = [r["derived_question_id"] for r in passes]
    fps = [r["question_fingerprint"] for r in passes]
    if len(set(ids)) != len(ids) or len(set(fps)) != len(fps):
        dump("ingest_result.json", {"status": "ABORTED",
                                    "error": "PASS 候选内部存在重复 ID/指纹，未写库"})
        print("ABORTED：PASS 候选内部存在重复 ID/指纹，未写库")
        return 2

    before = {"sha256": sha_file(LIB), "counts": {}, "questions": []}
    conn = sqlite3.connect(LIB)
    conn.isolation_level = None
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    for t in ["generation_run", "ai_question", "question_evidence", "question_learning_object",
              "question_validation", "question_event"]:
        before["counts"][t] = conn.execute("select count(*) from %s" % t).fetchone()[0]
    before["questions"] = [dict(r) for r in conn.execute(
        "select question_id, version, lifecycle_status, question_fingerprint, correct_answer "
        "from ai_question")]

    snapshot_id = conn.execute("select snapshot_id from generation_run order by generated_at "
                               "limit 1").fetchone()[0]

    # 每个源 Section 一条 generation_run（镜像 P1-06 的真实调用）
    runs = {}
    for tag in ["S1", "S2", "S3", "S4"]:
        if not any(r["source_section"] == tag for r in passes):
            continue
        rq = json.load(open(os.path.join(SPIKE, "P1_06_batch_stability",
                                         "%s_request.json" % tag), encoding="utf-8"))
        rs = json.load(open(os.path.join(SPIKE, "P1_06_batch_stability",
                                         "%s_response.json" % tag), encoding="utf-8"))
        st = os.stat(os.path.join(SPIKE, "P1_06_batch_stability", "%s_response.json" % tag))
        ts = datetime.datetime.fromtimestamp(st.st_mtime).astimezone()
        run_id = "AIRUN:%s:P106_%s" % (ts.strftime("%Y%m%dT%H%M%S"), tag)
        usage = (rs.get("response") or {}).get("usage") or {}
        sid = rq["section_id"]
        runs[tag] = {
            "run_id": run_id, "section_id": sid, "unit_id": sid.rsplit(":", 1)[0],
            "scope_key": hashlib.sha256("\x01".join(
                [sid, "", rq["prompt_version"], rq["context_sha256"]]).encode()).hexdigest().upper(),
            "model": rq["payload"]["model"], "prompt_version": rq["prompt_version"],
            "context_hash": rq["context_sha256"], "usage": usage,
            "elapsed_ms": rs["latency_ms"], "generated_at": ts.isoformat(timespec="seconds"),
            "max_tokens": rq["payload"]["max_tokens"],
            "context_ref": "audit/AI_question_generation_spike/P1_06_batch_stability/%s_request.json" % tag,
            "raw_ref": "audit/AI_question_generation_spike/P1_06_batch_stability/%s_response.json" % tag,
            "count": sum(1 for r in passes if r["source_section"] == tag),
        }

    ok = None
    try:
        conn.execute("BEGIN")
        # ---------- generation_run
        for tag, r in runs.items():
            conn.execute(
                "INSERT INTO generation_run (run_id, generation_scope_key, textbook_id, snapshot_id,"
                " unit_id, section_id, activity_id, model, prompt_version, context_hash, provider,"
                " context_ref, raw_response_ref, requested_max, max_tokens, finish_reason,"
                " usage_json, elapsed_ms, question_count, status, insufficient_evidence, error,"
                " note, generated_at) VALUES (?,?,?,?,?,?,NULL,?,?,?, 'deepseek',?,?,NULL,?,?,?,?,?,"
                " 'OK',0,NULL,?,?)",
                (r["run_id"], r["scope_key"], TEXTBOOK_ID, snapshot_id, r["unit_id"],
                 r["section_id"], r["model"], r["prompt_version"], r["context_hash"],
                 r["context_ref"], r["raw_ref"], r["max_tokens"], "stop",
                 json.dumps(r["usage"], ensure_ascii=False), r["elapsed_ms"], r["count"],
                 "P1-06 批量稳定性验证的真实调用；由 P1-07 入库演练回填（元数据来自 P1-06 产物）",
                 r["generated_at"]))
        # ---------- 题目
        for c in passes:
            tag = c["source_section"]
            run = runs[tag]
            now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
            conn.execute(
                "INSERT INTO ai_question (question_id, version, question_type, question_text,"
                " options_json, correct_option, correct_answer, explanation, difficulty,"
                " textbook_id, snapshot_id, unit_id, section_id, activity_id, page,"
                " generation_run_id, generated_at, question_fingerprint, lifecycle_status,"
                " active, stale, needs_human_review, validator_version, created_at, updated_at)"
                " VALUES (?,1,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'GENERATED',0,0,0,'v3',?,?)",
                (c["derived_question_id"], c["type"], c["question"],
                 json.dumps(c.get("options") or [], ensure_ascii=False)
                 if c.get("options") else None,
                 c.get("correct_option"), c["answer"], c.get("explanation"),
                 c.get("difficulty") or "easy", TEXTBOOK_ID, snapshot_id, c["unit_id"],
                 c["section_id"], c["activity_id"], c["page"], run["run_id"],
                 run["generated_at"], c["question_fingerprint"], now, now))
            for n, b in enumerate(c["blocks"], 1):
                conn.execute(
                    "INSERT INTO question_evidence (question_id, version, ordinal,"
                    " evidence_block_id, evidence_quote, is_primary) VALUES (?,1,?,?,?,?)",
                    (c["derived_question_id"], n, b, c["quote"], 1 if n == 1 else 0))
            for lo in c["learning_objects"]:
                conn.execute(
                    "INSERT INTO question_learning_object (question_id, version, item_id,"
                    " is_primary) VALUES (?,1,?,?)",
                    (c["derived_question_id"], lo["item_id"], lo["is_primary"]))
            # answer_support_type 受 schema 四值枚举约束；judge 题按 D2 豁免后取最接近的可存值
            ast = c["answer_support_type"]
            if ast not in ("EXACT", "VERIFIABLE_REFERENCE", "VERIFIABLE_REPHRASE"):
                ast = "VERIFIABLE_REPHRASE"
            note = ("P1-07 入库演练；mechanical_rewrite=%s original_textbook=%s dedupe_key=%s"
                    % (c["mechanical_rewrite"], c["original_textbook"], c["dedupe_key"][:16]))
            if c["rule4_waived_for_judge"]:
                note += "；rule4_waived_for_judge=true（判断题事实一致性判定，coverage=%s）" % c["judge_coverage"]
            conn.execute(
                "INSERT INTO question_validation (question_id, version, validator_version,"
                " validation_result, validated_at, answer_support_type, checks_json,"
                " out_of_scope_tokens_json, needs_human_review, note)"
                " VALUES (?,1,'v3','PASS',?,?,?,?,0,?)",
                (c["derived_question_id"], now, ast,
                 json.dumps(c["gate_results"], ensure_ascii=False),
                 json.dumps(c["vocabulary_raw_flags"], ensure_ascii=False), note))
            conn.execute(
                "INSERT INTO question_event (event_id, question_id, version, event_type,"
                " from_status, to_status, event_at, actor, actor_kind, note)"
                " VALUES (?,?,1,'VALIDATED','GENERATED','VALIDATED',?, 'validator_v3','machine',?)",
                ("AIEV:%s:V1" % c["derived_question_id"].split(":")[1],
                 c["derived_question_id"], now,
                 "P1-07 只读复算通过（gate1..gate5）"))
            conn.execute(
                "INSERT INTO question_event (event_id, question_id, version, event_type,"
                " from_status, to_status, event_at, actor, actor_kind, note)"
                " VALUES (?,?,1,'PENDING_REVIEW','VALIDATED','PENDING_REVIEW',?, 'p1_07_ingest',"
                "'machine',?)",
                ("AIEV:%s:P1" % c["derived_question_id"].split(":")[1],
                 c["derived_question_id"], now, "P1-07 入库；等待人工审核"))
            conn.execute("UPDATE ai_question SET lifecycle_status='PENDING_REVIEW', updated_at=? "
                         "WHERE question_id=? AND version=1", (now, c["derived_question_id"]))
        # ---------- 事务内自检
        active = conn.execute("select count(*) from ai_question where lifecycle_status='ACTIVE'"
                              ).fetchone()[0]
        appr = conn.execute("select count(*) from question_event where event_type='REVIEW_APPROVED'"
                            ).fetchone()[0]
        bad_lc = conn.execute("select count(*) from ai_question where lifecycle_status not in "
                              "('GENERATED','VALIDATED','PENDING_REVIEW','APPROVED','ACTIVE',"
                              "'REJECTED','DISABLED')").fetchone()[0]
        if active or appr or bad_lc:
            raise RuntimeError("事务内自检失败：active=%d approved_events=%d bad_lifecycle=%d"
                               % (active, appr, bad_lc))
        conn.execute("COMMIT")
        ok = True
    except Exception as exc:
        conn.execute("ROLLBACK")
        print("ROLLBACK：%s" % exc)
        dump("ingest_result.json", {"status": "ROLLBACK", "error": str(exc),
                                    "library_before": before})
        conn.close()
        return 1

    # ---------- 写后核对
    after = {"counts": {}, "questions": []}
    for t in ["generation_run", "ai_question", "question_evidence", "question_learning_object",
              "question_validation", "question_event"]:
        after["counts"][t] = conn.execute("select count(*) from %s" % t).fetchone()[0]
    after["questions"] = [dict(r) for r in conn.execute(
        "select question_id, version, lifecycle_status, question_fingerprint, correct_answer "
        "from ai_question")]
    old_ids = {q["question_id"] for q in before["questions"]}
    new_q = [q for q in after["questions"] if q["question_id"] not in old_ids]
    old_now = [q for q in after["questions"] if q["question_id"] in old_ids]
    unchanged_old = all(
        any(q["question_id"] == o["question_id"] and q["lifecycle_status"] == o["lifecycle_status"]
            and q["question_fingerprint"] == o["question_fingerprint"]
            and q["correct_answer"] == o["correct_answer"] for o in before["questions"])
        for q in old_now)
    conn.close()

    res = {"stage": "P1-07", "status": "COMMITTED", "ai_calls": 0,
           "library_before": before, "library_after": after,
           "generation_runs_created": {k: v["run_id"] for k, v in runs.items()},
           "inserted_questions": [q["question_id"] for q in new_q],
           "inserted_count": len(new_q),
           "existing_questions_unchanged": unchanged_old,
           "active_count": sum(1 for q in after["questions"] if q["lifecycle_status"] == "ACTIVE"),
           "lib_sha256_after": sha_file(LIB)}
    dump("ingest_result.json", res)
    print("已提交：新增 %d 题；已有题保持不变=%s；ACTIVE=%d" % (
        len(new_q), unchanged_old, res["active_count"]))
    print("  表计数：%s" % after["counts"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
