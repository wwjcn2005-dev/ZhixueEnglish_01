#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""句子听辨 AI 干扰项：正式全量离线生成（教材 38 条句子）

只做一件事：把 `sentence_distractors` 已验证的**候选生成层**接到项目既有 AI 口径上，
按批（默认 5 条）调用真实 AI，然后**原样喂给现有 rules-v2 确定性校验**，
校验通过的候选写入**现有缓存** `demo/ai_cache/sentence_distractors.json`。

复用（不新增机制、不新增缓存）：
  * 端点 / 模型：与项目既有 AI 管线一致（https://api.deepseek.com/chat/completions，deepseek-v4-pro）；
  * 凭据：`%USERPROFILE%\.codex\auth.json` 的 OPENAI_API_KEY（脚本不打印 key）；
  * prompt / 证据清单：`sentence_distractors.build_ai_batch_prompt` + `evidence_catalogue`；
  * 校验 / 数量上限 / 缓存键 / 缓存结构：`sentence_distractors.validate` / `MAX_DISTRACTORS`
    / `context_hash` / `load_cache`+`save_cache`；
  * 结构组装：`sentence_distractors.build_entry`（注入单句响应，不复制生成逻辑）。

边界：
  * 只读教材资源；不写 learning.db、不写结构化教材数据、不改页面；
  * 页面运行期不调用 AI：本脚本只在命令行显式运行时生成；
  * 批次失败不降低校验标准：失败的批次记录原因后跳过，已成功批次照常保存。
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = Path(os.environ.get("ZX_ROOT") or r"D:\ZhixueEnglish")
for _p in (str(BASE / "demo"), str(BASE / "web")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
sys.dont_write_bytecode = True

import sentence_distractors as sd          # noqa: E402

ENDPOINT = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-v4-pro"
MAX_TOKENS = 16384                          # P1-05-D 校准：8192 会因 reasoning 触顶截断
TEMPERATURE = 0.3
DEFAULT_BATCH_SIZE = 5


def call_ai(system: str, user: str, timeout: int = 1800):
    """调用项目既有 AI（与 audit 管线相同的端点 / 模型 / 凭据来源）。"""
    payload = {"model": MODEL, "temperature": TEMPERATURE, "max_tokens": MAX_TOKENS,
               "messages": [{"role": "system", "content": system},
                            {"role": "user", "content": user}]}
    key_path = Path(os.environ["USERPROFILE"]) / ".codex" / "auth.json"
    key = json.loads(key_path.read_text(encoding="utf-8"))["OPENAI_API_KEY"]
    req = urllib.request.Request(ENDPOINT, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer " + key})
    t0, resp_obj, api_error = time.time(), None, None
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp_obj = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        api_error = "HTTPError %s: %s" % (exc.code, exc.reason)
    except Exception as exc:                            # noqa: BLE001
        api_error = "%s: %s" % (type(exc).__name__, exc)
    return resp_obj, api_error, int((time.time() - t0) * 1000)


def collect_targets() -> list:
    """全量目标 = 现有教学范围里的全部教材短句（与 sd.generate() 同一范围）。"""
    import server as demo_server
    out = []
    for unit in demo_server.units():
        for lesson in demo_server.lessons(unit):
            if not any(lesson["counts"].values()):
                continue
            for sentence in (demo_server.lesson_sentences(unit, lesson) or []):
                if not (sentence.get("text") or "").strip():
                    continue
                out.append({"unit": unit["unit_code"], "lesson": lesson["key"],
                            "sentence": sentence})
    return out


def chunk(seq: list, size: int) -> list:
    return [seq[i:i + size] for i in range(0, len(seq), size)]


def entry_from_batch(unit_code: str, lesson_key: str, sentence: dict, raw_cands: list) -> dict:
    """把一批 AI 响应里的单句候选交给现有 build_entry（校验 + 结构 + 缓存键）。"""
    raw_distractors = [{"text": c.get("text"), "confidence": c.get("confidence"),
                        "reason": c.get("reason"),
                        "evidence_ids": [e.get("id") for e in (c.get("source_evidence") or [])
                                         if e.get("id")]}
                       for c in raw_cands]
    sub_response = {"items": [{"sentence_index": 0, "distractors": raw_distractors}]}
    saved_caller, saved_model = sd.AI_CALLER, sd.MODEL
    try:
        sd.AI_CALLER = lambda system, user: sub_response
        sd.MODEL = MODEL
        entry = sd.build_entry(unit_code, lesson_key, sentence)
    finally:
        sd.AI_CALLER, sd.MODEL = saved_caller, saved_model
    entry["ai_called"] = True                   # 真实 AI 生成（值变了，结构不变）
    return entry


def filter_stats(cands: list, target: dict, unit_code: str) -> tuple:
    """只读统计：复用现有 validate 记录保留/过滤原因（不产生 AI 调用，不改规则）。"""
    seen, kept, reasons, filtered = {sd._norm(target.get("text"))}, [], {}, []
    for cand in cands:
        ok, why = sd.validate(cand, target, unit_code, seen)
        if ok:
            seen.add(sd._norm(cand["text"]))
            kept.append(cand)
            if len(kept) >= sd.MAX_DISTRACTORS:
                break
        else:
            key = why.split(":")[0]
            reasons[key] = reasons.get(key, 0) + 1
            filtered.append({"text": cand.get("text"), "reason": why})
    return kept, reasons, filtered


def revalidate(args) -> int:
    """离线复核：用当前规则重新校验缓存里已有的 AI 候选，并重新绑定版本（不调用 AI）。

    只做确定性校验 + 重新计算缓存键；不改动候选文本，不生成新候选。
    """
    cache = sd.load_cache(args.path)
    entries_in = cache.get("entries") or {}
    report = {"run": "revalidate cached sentence distractors (no AI)",
              "prompt_version": sd.PROMPT_VERSION, "rules_version": sd.RULES_VERSION,
              "cache_file": str(args.path or sd.CACHE_FILE),
              "entries_in": len(entries_in), "entries_out": 0,
              "distractors_in": 0, "distractors_kept": 0, "dropped": [], "entries": []}
    entries_out = {}
    for _old_hash, entry in entries_in.items():
        qi = entry.get("question_item") or {}
        unit_code, lesson_key = qi.get("unit"), qi.get("lesson")
        answer = entry.get("correct_answer") or ""
        target = {"text": answer, "uid": qi.get("sentence_uid")}
        seen, kept = {sd._norm(answer)}, []
        for cand in entry.get("distractors") or []:
            report["distractors_in"] += 1
            ok, why = sd.validate(cand, target, unit_code, seen)
            if ok:
                seen.add(sd._norm(cand["text"]))
                kept.append(cand)
                if len(kept) >= sd.MAX_DISTRACTORS:
                    break
            else:
                report["dropped"].append({"unit": unit_code, "lesson": lesson_key,
                                          "correct_answer": answer,
                                          "text": cand.get("text"), "reason": why})
        new_entry = dict(entry)
        new_entry["distractors"] = kept
        new_entry["prompt_version"] = sd.PROMPT_VERSION
        new_entry["rules_version"] = sd.RULES_VERSION
        new_entry["context_hash"] = sd.context_hash(unit_code, lesson_key, answer)
        entries_out[new_entry["context_hash"]] = new_entry
        report["distractors_kept"] += len(kept)
        report["entries"].append({"unit": unit_code, "lesson": lesson_key,
                                  "correct_answer": answer,
                                  "distractors": [d["text"] for d in kept]})
    cache["version"] = sd.RULES_VERSION
    cache["prompt_version"] = sd.PROMPT_VERSION
    cache["entries"] = entries_out
    report["entries_out"] = len(entries_out)
    if not args.dry_run:
        sd.save_cache(cache, args.path)
    stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    out_dir = Path(args.report_dir) if args.report_dir else (
        BASE / "demo" / "ai_cache" / ("revalidate_%s" % stamp))
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "revalidate_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: report[k] for k in
                      ("entries_in", "entries_out", "distractors_in", "distractors_kept",
                       "rules_version")}, ensure_ascii=False), flush=True)
    print("dropped: %s" % json.dumps(report["dropped"], ensure_ascii=False), flush=True)
    print("report: %s" % out_dir, flush=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 条（调试用，默认全量）")
    ap.add_argument("--only-missing", action="store_true",
                    help="续跑：跳过缓存里已经由真实 AI 生成（ai_called=true）的句子")
    ap.add_argument("--path", default=None, help="缓存路径（默认现有 demo/ai_cache/sentence_distractors.json）")
    ap.add_argument("--report-dir", default=None)
    ap.add_argument("--dry-run", action="store_true", help="只出报告，不写缓存")
    ap.add_argument("--revalidate", action="store_true",
                    help="只对缓存里已有 AI 候选用当前规则重新校验并重新绑定规则版本（不调用 AI）")
    args = ap.parse_args()

    if args.revalidate:
        return revalidate(args)

    targets = collect_targets()
    if args.only_missing:
        done = {k for k, v in (sd.load_cache(args.path).get("entries") or {}).items()
                if v.get("ai_called")}
        targets = [t for t in targets
                   if sd.context_hash(t["unit"], t["lesson"],
                                      t["sentence"].get("text") or "") not in done]
    if args.limit:
        targets = targets[:args.limit]
    batch_size = max(1, args.batch_size)
    batches = chunk(targets, batch_size)
    stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    report_dir = Path(args.report_dir) if args.report_dir else (
        BASE / "demo" / "ai_cache" / ("full_%s" % stamp))
    report_dir.mkdir(parents=True, exist_ok=True)

    cache = sd.load_cache(args.path)
    entries = cache.setdefault("entries", {})
    report = {"run": "sentence distractors full generation", "model": MODEL,
              "prompt_version": sd.PROMPT_VERSION, "rules_version": sd.RULES_VERSION,
              "batch_size": batch_size, "targets": len(targets), "batches": len(batches),
              "ai_calls": 0, "failed_batches": [], "samples": [], "started_at": stamp}
    by_kept = {0: 0, 1: 0, 2: 0, 3: 0}
    reasons_total, raw_total, kept_total = {}, 0, 0
    t0 = time.time()

    for bi, batch in enumerate(batches, 1):
        samples = [{"sentence_index": i, "text": t["sentence"]["text"], "unit": t["unit"]}
                   for i, t in enumerate(batch)]
        system, user = sd.build_ai_batch_prompt(samples)
        resp_obj, api_error, latency_ms = call_ai(system, user)
        report["ai_calls"] += 1
        content, finish_reason = "", None
        if resp_obj:
            choice = (resp_obj.get("choices") or [{}])[0]
            content = (choice.get("message") or {}).get("content") or ""
            finish_reason = choice.get("finish_reason")
        parsed = sd._parse_ai_json(content)
        per_index = sd.ai_candidates_batch(parsed, samples)
        got = sum(len(per_index.get(i, [])) for i in range(len(batch)))
        ok_batch = not api_error and bool(per_index)
        print("[batch %d/%d] %s 条｜latency=%.1fs｜finish=%s｜raw=%d%s"
              % (bi, len(batches), len(batch), latency_ms / 1000.0, finish_reason, got,
                 "" if ok_batch else "  ← FAILED: %s" % (api_error or "unparsable")), flush=True)
        if not ok_batch:
            report["failed_batches"].append({"batch": bi, "api_error": api_error,
                                             "finish_reason": finish_reason,
                                             "sentences": [s["text"] for s in samples]})
            continue

        for i, t in enumerate(batch):
            sentence, unit_code = t["sentence"], t["unit"]
            target = {"text": sentence.get("text") or "", "uid": sentence.get("uid"),
                      "pdf_page": sentence.get("pdf_page")}
            cands = per_index.get(i, [])
            kept, reasons, filtered = filter_stats(cands, target, unit_code)
            entry = entry_from_batch(unit_code, t["lesson"], sentence, cands)
            if len(entry["distractors"]) != len(kept):       # 两条路径必须一致
                raise AssertionError("validate/build_entry mismatch: %s" % target["text"])
            entries[entry["context_hash"]] = entry
            raw_total += len(cands)
            kept_total += len(kept)
            by_kept[min(len(kept), 3)] += 1
            for k, v in reasons.items():
                reasons_total[k] = reasons_total.get(k, 0) + v
            report["samples"].append({
                "unit": unit_code, "lesson": t["lesson"], "correct_answer": target["text"],
                "sentence_uid": target["uid"], "textbook_page": target["pdf_page"],
                "raw_count": len(cands), "kept_count": len(kept),
                "kept": [d["text"] for d in entry["distractors"]],
                "kept_detail": [{"text": d["text"], "confidence": d["confidence"],
                                 "origin": d["origin"],
                                 "evidence": [e.get("id") or e.get("pack")
                                              for e in d["source_evidence"]]}
                                for d in entry["distractors"]],
                "filtered": filtered})
            print("   · %s → 保留 %d：%s" % (target["text"], len(kept),
                                             [d["text"] for d in entry["distractors"]]), flush=True)

        cache["version"] = sd.RULES_VERSION
        cache["prompt_version"] = sd.PROMPT_VERSION
        sd.save_cache(cache, args.path)          # 每批成功即落盘（失败批次不影响已成功批次）

    report["elapsed_sec"] = round(time.time() - t0, 1)
    report["raw_candidates"] = raw_total
    report["kept_candidates"] = kept_total
    report["kept_distribution"] = by_kept
    report["filtered_reasons"] = reasons_total
    report["fallback_count"] = by_kept.get(0, 0)
    report["cache_entries"] = len(entries)
    report["cache_file"] = str(args.path or sd.CACHE_FILE)
    report["finished_at"] = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    (report_dir / "run_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1),
                                                encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("ai_calls", "targets", "batches", "elapsed_sec",
                                             "raw_candidates", "kept_candidates",
                                             "kept_distribution", "filtered_reasons",
                                             "failed_batches")}, ensure_ascii=False), flush=True)
    print("report: %s" % report_dir, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
