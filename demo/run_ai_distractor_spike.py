#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""真实 AI 句子听辨干扰项最小 Spike（1 次真实调用）

只做一件事：把 `sentence_distractors` 的**候选生成层**接到项目既有的 AI 调用口径上，
让真实 AI 针对少量教材句子生成干扰项候选，然后**原样喂给现有确定性校验**，
记录：原始候选 / 校验后有效候选 / 每条被过滤的原因 / evidence / 调用次数。

复用（不新增架构）：
  * 端点与模型：与项目既有 AI 管线一致（https://api.deepseek.com/chat/completions，deepseek-v4-pro）；
  * 凭据：`%USERPROFILE%\.codex\auth.json` 的 OPENAI_API_KEY（Codex 已配置，脚本不打印 key）；
  * 校验 / evidence / 动态 2–4 选项 / 缓存结构 / 页面消费：全部沿用 `sentence_distractors` 现状。

边界：
  * 只读教材资源；**不写** `learning.db`、不写正式缓存（`demo/ai_cache/sentence_distractors.json`）；
  * Spike 结果单独落在 `demo/ai_cache/spike_<时间戳>/`；
  * Demo 页面默认行为不变（默认仍走确定性模拟，只有显式注入 AI_CALLER 才走真实 AI）。
"""

from __future__ import annotations

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
#: 项目 P1-05-D 已校准的生成预算（8192 会因 reasoning 触顶而截断 → 16384 能正常收敛）
MAX_TOKENS = int(os.environ.get("ZX_SPIKE_MAX_TOKENS", "16384"))
TEMPERATURE = 0.3
SAMPLE_LIMIT = int(os.environ.get("ZX_SPIKE_LIMIT", "5"))   # 5–10 条代表性教材句子

#: 复验固定样本（与上一轮相同的 5 条真实教材句子；不重新选样）
SAMPLE_TEXTS = (
    "Are you ready?",
    "What are you going to wear tomorrow for school?",
    "The new school year is beginning.",
    "What are the new students' problems?",
    "\u201cWhy don\u2019t we put our music together?",
)


def call_ai(system: str, user: str, timeout: int = 900):
    """调用项目既有 AI（与 audit 管线相同的端点 / 模型 / 凭据来源）。"""
    payload = {"model": MODEL, "temperature": TEMPERATURE, "max_tokens": MAX_TOKENS,
               "messages": [{"role": "system", "content": system},
                            {"role": "user", "content": user}]}
    key = json.load(open(os.path.join(os.environ["USERPROFILE"], ".codex", "auth.json"),
                         encoding="utf-8"))["OPENAI_API_KEY"]
    req = urllib.request.Request(ENDPOINT, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer " + key})
    t0, resp_obj, api_error = time.time(), None, None
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
        resp_obj = json.loads(body)
    except urllib.error.HTTPError as exc:
        api_error = "HTTPError %s: %s" % (exc.code, exc.reason)
    except Exception as exc:                            # noqa: BLE001
        api_error = "%s: %s" % (type(exc).__name__, exc)
    return resp_obj, api_error, int((time.time() - t0) * 1000), payload


def pick_samples():
    """复验样本：固定使用 SAMPLE_TEXTS 这 5 条（与上一轮完全相同的教材句子）。"""
    import server as demo_server
    production = sd.load_cache().get("entries") or {}
    samples = []
    wanted = [sd._norm(t) for t in SAMPLE_TEXTS]
    for unit in demo_server.units():
        for lesson in demo_server.lessons(unit):
            if not any(lesson["counts"].values()):
                continue
            for s in demo_server.lesson_sentences(unit, lesson) or []:
                text = (s.get("text") or "").strip()
                if not text or not s.get("uid"):
                    continue
                if sd._norm(text) not in wanted:
                    continue                                # 只取固定复验样本
                h = sd.context_hash(unit["unit_code"], lesson["key"], text)
                samples.append({"unit": unit["unit_code"], "lesson": lesson["key"],
                                "text": text, "uid": s.get("uid"),
                                "pdf_page": s.get("pdf_page"),
                                "previous_kept": [d["text"] for d in
                                                  (production.get(h) or {}).get("distractors") or []],
                                "simulated": [d["text"] for d in
                                              (production.get(h) or {}).get("distractors") or []]})
                if len(samples) >= len(SAMPLE_TEXTS):
                    return samples
    return samples


def main() -> int:
    samples = pick_samples()
    for i, s in enumerate(samples):
        s["sentence_index"] = i
    print("样本 %d 条：%s" % (len(samples), [s["unit"] for s in samples]))

    system, user = sd.build_ai_batch_prompt(samples)
    out_dir = BASE / "demo" / "ai_cache" / ("spike_%s" % datetime.datetime.now().strftime("%Y%m%dT%H%M%S"))
    out_dir.mkdir(parents=True, exist_ok=True)

    resp_obj, api_error, latency_ms, payload = call_ai(system, user)      # ← 唯一一次调用
    ai_calls = 1
    content = ""
    finish_reason, usage = None, {}
    if resp_obj:
        choice = (resp_obj.get("choices") or [{}])[0]
        content = (choice.get("message") or {}).get("content") or ""
        finish_reason = choice.get("finish_reason")
        usage = resp_obj.get("usage") or {}
    parsed = sd._parse_ai_json(content)

    raw_by_index = sd.ai_candidates_batch(parsed, samples)
    # 验证句级接入路径：把同一次 AI 响应注入 candidates_for() 的生成层（不再产生新调用）
    saved_caller = sd.AI_CALLER
    sd.AI_CALLER = lambda system, user: parsed
    try:
        first = samples[0]
        dispatch = sd.candidates_for({"text": first["text"], "uid": first["uid"],
                                      "pdf_page": first["pdf_page"],
                                      "sentence_index": first["sentence_index"]}, first["unit"])
        dispatch_ok = len(dispatch) == len(raw_by_index.get(first["sentence_index"], []))
    finally:
        sd.AI_CALLER = saved_caller
    report = {"spike": "P1-12-AI sentence distractors", "model": MODEL,
              "prompt_version": sd.PROMPT_VERSION, "rules_version": sd.RULES_VERSION,
              "ai_calls": ai_calls, "retry_count": 0, "api_error": api_error,
              "finish_reason": finish_reason, "usage": usage, "latency_ms": latency_ms,
              "candidates_for_dispatch_verified": dispatch_ok, "samples": [], "summary": {}}
    raw_total = kept_total = 0
    by_kept = {0: 0, 1: 0, 2: 0, 3: 0}
    reasons = {}
    for s in samples:
        raw = raw_by_index.get(s["sentence_index"], [])
        target = {"text": s["text"], "uid": s["uid"], "pdf_page": s["pdf_page"]}
        seen, kept, filtered = {sd._norm(s["text"])}, [], []
        for cand in raw:
            ok, why = sd.validate(cand, target, s["unit"], seen)      # ← 现有确定性校验
            if ok:
                seen.add(sd._norm(cand["text"]))
                kept.append(cand)
                if len(kept) >= sd.MAX_DISTRACTORS:
                    break
            else:
                filtered.append({"text": cand.get("text"), "reason": why,
                                 "confidence": cand.get("confidence"),
                                 "evidence": [e.get("id") or e.get("pack")
                                              for e in cand.get("source_evidence") or []]})
                reasons[why.split(":")[0]] = reasons.get(why.split(":")[0], 0) + 1
        raw_total += len(raw)
        kept_total += len(kept)
        by_kept[min(len(kept), 3)] = by_kept.get(min(len(kept), 3), 0) + 1
        report["samples"].append({
            "sentence_index": s["sentence_index"], "unit": s["unit"], "lesson": s["lesson"],
            "correct_answer": s["text"], "sentence_uid": s["uid"], "textbook_page": s["pdf_page"],
            "raw_ai_candidates": raw, "raw_count": len(raw),
            "kept": kept, "kept_count": len(kept), "filtered": filtered,
            "simulated_baseline": s["simulated"]})
    report["summary"] = {"sentences": len(samples), "ai_calls": ai_calls,
                         "candidates_for_dispatch_verified": dispatch_ok,
                         "raw_candidates": raw_total, "kept_candidates": kept_total,
                         "kept_distribution": by_kept, "filtered_reasons": reasons,
                         "filter_ratio": (round(1 - kept_total / raw_total, 3) if raw_total else None)}

    (out_dir / "raw_response.json").write_text(
        json.dumps({"request": payload, "response": resp_obj, "api_error": api_error,
                    "latency_ms": latency_ms, "finish_reason": finish_reason},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / "spike_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1),
                                               encoding="utf-8")

    lines = ["# 真实 AI 句子听辨干扰项 Spike", "",
             "- model: %s ｜ prompt: %s ｜ rules: %s" % (MODEL, sd.PROMPT_VERSION, sd.RULES_VERSION),
             "- ai_calls: %d ｜ retry: 0 ｜ finish_reason: %s ｜ latency_ms: %s"
             % (ai_calls, finish_reason, latency_ms),
             "- usage: %s" % json.dumps(usage, ensure_ascii=False),
             "- 样本 %d 条 ｜ AI 原始候选 %d ｜ 校验后保留 %d ｜ 过滤比例 %s"
             % (len(samples), raw_total, kept_total, report["summary"]["filter_ratio"]), "",
             "- 保留数量分布：%s" % json.dumps(by_kept, ensure_ascii=False),
             "- 过滤原因：%s" % json.dumps(reasons, ensure_ascii=False), ""]
    for s in report["samples"]:
        lines += ["## [%d] %s · %s" % (s["sentence_index"], s["unit"], s["lesson"]),
                  "- 正确答案：%s" % s["correct_answer"],
                  "- AI 原始候选：%d ｜ 校验后：%d" % (s["raw_count"], s["kept_count"])]
        for d in s["kept"]:
            lines.append("  - ✅ %s（conf=%s，evidence=%s）"
                         % (d["text"], d["confidence"],
                            [e.get("id") or e.get("pack") for e in d["source_evidence"]][:2]))
        for d in s["filtered"]:
            lines.append("  - ❌ %s（%s）" % (d["text"], d["reason"]))
        lines.append("")
    (out_dir / "spike_report.md").write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps({"out_dir": str(out_dir), **report["summary"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
