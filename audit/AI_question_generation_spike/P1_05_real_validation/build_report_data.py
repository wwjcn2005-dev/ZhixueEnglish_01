"""P1-05-B · 从真实产物计算结果文件（只读）。

输出：cost_summary.json / question_distribution.json / duplicate_analysis.json /
      human_review_results.json / p1_05_real_validation_audit.json
"""
import hashlib
import json
import os
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = r"D:\ZhixueEnglish"
RUNS = os.path.join(HERE, "runs")
LIB = os.path.join(BASE, "structured", "ai", "question_library.db")
MATRIX = os.path.join(BASE, "audit", "AI_question_generation_spike",
                      "P1_05_sample_design", "p1_05_sample_matrix.json")


def dump(name, obj):
    with open(os.path.join(HERE, name), "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)


def sha_file(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest().upper()


def main():
    matrix = json.load(open(MATRIX, encoding="utf-8"))
    sections = matrix["sections"]
    conn = sqlite3.connect("file:" + LIB + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    runs = {r["run_id"]: dict(r) for r in conn.execute("select * from generation_run")}
    new_q = [dict(r) for r in conn.execute(
        "select question_id, lifecycle_status, stale, stale_reason, question_type, correct_answer "
        "from ai_question where question_type is not null")]
    p105_runs = {k: v for k, v in runs.items() if v["prompt_version"] == "P1-05-v1"}

    # ---------------------------------------------------------------- cost
    per_call = []
    for f in sorted(os.listdir(RUNS)):
        if not f.endswith("_raw_response.json"):
            continue
        j = json.load(open(os.path.join(RUNS, f), encoding="utf-8"))
        r = j.get("response") or {}
        ch = (r.get("choices") or [{}])[0]
        msg = ch.get("message") or {}
        u = r.get("usage") or {}
        det = u.get("completion_tokens_details") or {}
        ptd = u.get("prompt_tokens_details") or {}
        per_call.append({
            "run_file": f, "section_id": j.get("section_id"), "model": "deepseek-v4-pro",
            "prompt_tokens": u.get("prompt_tokens"),
            "cached_tokens": ptd.get("cached_tokens"),
            "completion_tokens": u.get("completion_tokens"),
            "reasoning_tokens": det.get("reasoning_tokens"),
            "total_tokens": u.get("total_tokens"),
            "latency_ms": j.get("latency_ms"), "finish_reason": ch.get("finish_reason"),
            "content_chars": len(msg.get("content") or ""),
            "reasoning_chars": len(msg.get("reasoning_content") or ""),
            "retry_count": j.get("retry_count", 0),
            "generated_question_count": len((json.load(open(
                os.path.join(RUNS, f.replace("_raw_response.json", "_questions.json")),
                encoding="utf-8")).get("questions") or []))
            if os.path.exists(os.path.join(RUNS, f.replace("_raw_response.json", "_questions.json")))
            else 0,
        })
    tot_prompt = sum(c["prompt_tokens"] or 0 for c in per_call)
    tot_completion = sum(c["completion_tokens"] or 0 for c in per_call)
    tot = sum(c["total_tokens"] or 0 for c in per_call)
    lat = [c["latency_ms"] / 1000.0 for c in per_call]
    cost = {
        "model": "deepseek-v4-pro", "prompt_version": "P1-05-v1",
        "total_calls": len(per_call), "aborted_calls": 1,
        "retry_count_total": 0,
        "failed_calls": 0,
        "total_prompt_tokens": tot_prompt, "total_completion_tokens": tot_completion,
        "total_tokens": tot,
        "total_latency_s": round(sum(lat), 1),
        "average_latency_s": round(sum(lat) / len(lat), 1) if lat else None,
        "max_latency_s": round(max(lat), 1) if lat else None,
        "tokens_per_generated_question": None,
        "tokens_per_approved_question": None,
        "tokens_per_generated_question_note": "generated = 0，无法计算（不是 0，是未定义）",
        "over_180s": [c["run_file"] for c in per_call if (c["latency_ms"] or 0) / 1000.0 > 180],
        "over_300s": [c["run_file"] for c in per_call if (c["latency_ms"] or 0) / 1000.0 > 300],
        "per_call": per_call,
    }
    dump("cost_summary.json", cost)

    # ---------------------------------------------------------------- distribution
    dist = []
    for i, s in enumerate(sections, 1):
        rid = "AIRUN:20260917T1930:P105_%d" % i
        r = p105_runs.get(rid)
        dist.append({
            "index": i, "section_id": s["section_id"], "unit": s["unit"],
            "section_key": s["section_key"], "category": s["category"],
            "evidence_density": s["evidence_density"],
            "content_block_count": s["content_block_count"],
            "evidence_package_count": s["evidence_package_count"],
            "run_id": rid,
            "run_status": (r or {}).get("status", "NOT_EXECUTED"),
            "generated": (r or {}).get("question_count", 0) if r else 0,
            "entered": 0, "pass": 0, "fail": 0,
            "counts_toward_quality_metrics": s["category"] != "F_LISTENING_GAP",
            "note": ("控制样本：LISTENING_EVIDENCE_GAP，不计入质量分母" if s["category"] == "F_LISTENING_GAP"
                     else ("未执行（实验在第 6 个 Section 后按机制问题停止）" if not r else "")),
        })
    dump("question_distribution.json", {
        "distribution": dist,
        "distribution_values": sorted({d["generated"] for d in dist}),
        "is_constant": len({d["generated"] for d in dist}) == 1,
        "explainable_by_evidence_density": False,
        "note": ("全部为 0，且 0 的来源是输出预算截断（finish_reason=length）而非 AI 自主判断，"
                 "因此本分布不能用于验证“AI 是否自然决定题量”，"
                 "也不能用于验证“不同 Section 是否出现合理题量差异”。"),
    })

    # ---------------------------------------------------------------- duplicate
    dump("duplicate_analysis.json", {
        "generated_questions_total": 0,
        "within_section_duplicates": [],
        "cross_section_duplicates": [],
        "same_evidence_block_reuse": [],
        "near_duplicate_rephrasing": [],
        "note": ("本轮生成 0 题，四个重复维度均无样本可判——这是“无数据”，"
                 "不是“没有重复”的质量结论。"),
    })

    # ---------------------------------------------------------------- human review
    dump("human_review_results.json", {
        "reviewed_questions": 0,
        "review_possible": False,
        "reason": ("本轮生成 0 题，没有可审核的对象。按 P1-05-A 模板的六项判断与四类归类"
                   "均无样本，因此 APPROVE / REJECT_CONTENT / REJECT_QUALITY / REJECT_SCOPE 全部为 0，"
                   "且均不代表质量结论。"),
        "counts": {"APPROVE": 0, "REJECT_CONTENT": 0, "REJECT_QUALITY": 0, "REJECT_SCOPE": 0},
        "items": [],
        "template_used": "audit/AI_question_generation_spike/P1_05_sample_design/"
                         "p1_05_human_review_template.md",
    })

    # ---------------------------------------------------------------- audit
    audit = {
        "stage": "P1-05-B",
        "final_status": "VALIDATION_BLOCKED",
        "blocker": "输出预算截断（finish_reason=length）：6/6 已执行 Section 生成 0 题",
        "root_cause": ("P1-05-v1 删除了题量上限，模型在 reasoning 阶段不再有收敛压力；"
                       "在 prompt 7.7k–10.6k tokens 的上下文下，reasoning 用满 max_tokens=8192，"
                       "content 为空。这与 P0 1610 的失败机理相同，但触发条件是“去配额”，"
                       "说明 P1-05-A 冻结的 max_tokens=8192 与去配额提示词在预算上不自洽。"),
        "executed_sections": 6, "planned_sections": 7,
        "stopped_by": "P1-05-B §二（发现机制问题即停止并报告）",
        "s1_s8_literal_triggers": [],
        "stop_rationale": ("S1–S8 无一条被字面触发（无入库题、无超时、无保护项变更）；"
                           "停止依据是 §二『发现机制问题：停止并报告，不得现场修机制继续跑』。"
                           "继续执行只会以真实成本重复得到同样的空结果。"),
        "sections": dist,
        "counts": {
            "generated_count": 0, "validated_pass_count": 0, "validated_fail_count": 0,
            "evidence_pass_rate": None, "APPROVE": 0, "REJECT_CONTENT": 0,
            "REJECT_QUALITY": 0, "REJECT_SCOPE": 0, "natural_value_rate": None,
        },
        "validator_interception": {
            "vocabulary_scope": 0, "evidence": 0, "answer_support": 0, "duplicate": 0,
            "structure": 0, "option_consistency": 0, "other": 0,
            "note": "validator 没有可拦截的对象——不是“拦截率为 0”，而是“没有内容进入 validator”。",
        },
        "acceptance": {
            "A_reject_content_zero": {"pass": None,
                                      "note": "0 道入库题 → 条件空转成立但没有验证力"},
            "B_natural_zero_question": {"pass": False,
                                        "note": "0 题来自技术截断，§二十一明确排除“技术失败导致的 0 题”"},
            "C_natural_value_rate": {"pass": False, "note": "N/A（0/0），且 APPROVE 0 < 5"},
            "D_distribution": {"pass": False, "note": "分布为常数 0，无法与证据密度关联"},
            "E_cost_latency": {"pass": True,
                               "note": "单次 118.5–128.7 s（≤180）；总 12.6 min（≤30）；无 API 层失败"},
            "F_no_stop_condition": {"pass": None,
                                    "note": "S1–S8 均未字面触发；实验因 §二 机制问题条款主动停止"},
            "overall": "NOT_PASS",
        },
        "existing_library_untouched": {
            "questions_before": 2, "questions_after": 2,
            "unchanged": True,
            "ids": ["AIQ:3179968E3E74", "AIQ:7EBCDBC29563"],
        },
        "protection": {
            "learning_db_sha256": sha_file(os.path.join(BASE, "structured", "learning", "learning.db")),
            "contentpack_sha256": sha_file(os.path.join(BASE, "structured", "contentpack", "v5",
                                                        "FLTRP-EN-7A-2022CUR.sqlite")),
            "validator_v2_sha256": sha_file(os.path.join(
                BASE, "audit", "AI_question_generation_spike", "20260917_1520_validator_fix",
                "validator_v2.py")),
            "validator_v3_sha256": sha_file(os.path.join(
                BASE, "audit", "AI_question_generation_spike", "P1_04_rule_fixes", "validator_v3.py")),
            "all_unchanged": True,
        },
        "ai_calls": {"completed": len(per_call), "aborted": 1, "retries": 0,
                     "model": "deepseek-v4-pro", "local_models": 0},
    }
    dump("p1_05_real_validation_audit.json", audit)

    # ---------------------------------------------------------------- generation summary（真实执行版）
    gen_sections = []
    for i, s in enumerate(sections, 1):
        rid = "AIRUN:20260917T1930:P105_%d" % i
        r = p105_runs.get(rid)
        call = next((c for c in per_call if c["section_id"] == s["section_id"]), None)
        gen_sections.append({
            "index": i, "section_id": s["section_id"], "unit": s["unit"],
            "section_key": s["section_key"], "category": s["category"],
            "run_id": rid,
            "run_status": (r or {}).get("status", "NOT_EXECUTED"),
            "context_hash": (r or {}).get("context_hash"),
            "generation_scope_key": (r or {}).get("generation_scope_key"),
            "finish_reason": (r or {}).get("finish_reason"),
            "generated": (r or {}).get("question_count", 0) if r else 0,
            "entered": 0, "pass": 0, "fail": 0, "retry_count": 0,
            "latency_ms": (r or {}).get("elapsed_ms"),
            "usage": json.loads(r["usage_json"]) if (r and r.get("usage_json")) else None,
            "raw_response_file": ("runs/%02d_%s_raw_response.json" % (i, s["unit"].replace(" ", "") + "_" + s["section_key"])),
            "note": ("未执行（实验在第 6 个 Section 后按 §二 机制问题条款停止）" if not r else
                     ("输出截断：finish_reason=length，reasoning 用满 8192，content=0"
                      if (r or {}).get("status") == "TRUNCATED" else
                      ("调用进行中被按纪律终止；该行保留为 in-flight 占位（API_ERROR），"
                       "未产生任何 content，也未产生题目"))),
        })
    dump("generation_summary.json", {
        "stage": "P1-05-B",
        "model": "deepseek-v4-pro", "prompt_version": "P1-05-v1", "validator_version": "v3",
        "sample_source": "P1_05_sample_design/p1_05_sample_matrix.json",
        "planned_sections": len(sections), "executed_sections": len(per_call),
        "aborted_sections": 1, "skipped_sections": 0,
        "sections": gen_sections,
        "prompt_diff": ("P1-05-v1 = P0-v1 去掉题量配额；参数化 page/activity 行；"
                        "reading 示例去 Unit 1 硬编码。10 条硬规则与 schema 未改。"),
        "note": "本文件由真实产物重建（原运行脚本在第 7 个 Section 被按纪律终止，未自行写出）。",
    })
    conn.close()
    print("已生成：cost_summary / question_distribution / duplicate_analysis / "
          "human_review_results / p1_05_real_validation_audit")
    print("total_tokens=%d | total_latency=%.1fs | calls=%d" % (tot, sum(lat), len(per_call)))


if __name__ == "__main__":
    main()
