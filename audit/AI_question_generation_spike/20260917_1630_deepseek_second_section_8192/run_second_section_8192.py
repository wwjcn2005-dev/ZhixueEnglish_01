"""P0 第二 Section 单变量复测：max_tokens 4096 -> 8192。

唯一变量：max_tokens。
提示词（system / user）不是重打的，而是从上一轮脚本
20260917_1610_deepseek_second_section/run_second_section.py
中用 AST 原样提取字面量表达式后求值，以保证逐字一致。
上下文直接复用上一轮 input_context.json（先校验 SHA256，再字节级复制）。
"""
import ast
import hashlib
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = r"D:\ZhixueEnglish"
SPIKE = os.path.join(BASE, "audit", "AI_question_generation_spike")
PREV_DIR = os.path.join(SPIKE, "20260917_1610_deepseek_second_section")
PREV_SCRIPT = os.path.join(PREV_DIR, "run_second_section.py")
VALIDATOR_DIR = os.path.join(SPIKE, "20260917_1520_validator_fix")

MODEL = "deepseek-v4-pro"
ENDPOINT = "https://api.deepseek.com/chat/completions"
MAX_TOKENS = 8192                       # 本轮唯一变化的参数（上一轮为 4096）
PREV_MAX_TOKENS = 4096
EXPECTED_CTX_SHA = "471E6FA7AA82E03B99E31A43265944D2D8CA98C6924DCB6D38D196474677DFA4"
UNIT, SECTION_KEY = "Unit 1", "UNDERSTANDING_IDEAS"

# --------------------------------------------------------------- 1) 复用上一轮上下文（字节级）
src_ctx_path = os.path.join(PREV_DIR, "input_context.json")
raw_bytes = open(src_ctx_path, "rb").read()
sha = hashlib.sha256(raw_bytes).hexdigest().upper()
print("上一轮 input_context.json SHA256 = %s" % sha)
assert sha == EXPECTED_CTX_SHA, "上下文 SHA256 与上一轮不一致，停止！"
dst_ctx_path = os.path.join(HERE, "input_context.json")
if not os.path.exists(dst_ctx_path):
    shutil.copyfile(src_ctx_path, dst_ctx_path)
sha_new = hashlib.sha256(open(dst_ctx_path, "rb").read()).hexdigest().upper()
assert sha_new == EXPECTED_CTX_SHA, "复制后 SHA256 不一致，停止！"
print("本轮 input_context.json SHA256 = %s（与上一轮一致）" % sha_new)

ctx = json.loads(raw_bytes.decode("utf-8"))     # dict 顺序保留，可复现原提示词字符串

# --------------------------------------------------------------- 2) 从上一轮脚本原样提取提示词
tree = ast.parse(open(PREV_SCRIPT, encoding="utf-8").read())
SYSTEM = None
user_expr = None
for node in tree.body:
    if not (isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)):
        continue
    name = node.targets[0].id
    if name == "SYSTEM":
        SYSTEM = ast.literal_eval(node.value)
    elif name == "USER":
        user_expr = node.value
assert SYSTEM is not None and user_expr is not None, "未能从上一轮脚本提取提示词"
USER = eval(compile(ast.Expression(user_expr), "<prev_prompt>", "eval"),
            {"json": json, "ctx": ctx})
print("提示词已按上一轮字面量原样重建：system %d 字符 / user %d 字符" % (len(SYSTEM), len(USER)))
print("  system SHA256 = %s" % hashlib.sha256(SYSTEM.encode()).hexdigest().upper()[:32])
print("  user   SHA256 = %s" % hashlib.sha256(USER.encode()).hexdigest().upper()[:32])

# --------------------------------------------------------------- 3) 唯一一次云端生成调用
key = json.load(open(os.path.join(os.environ["USERPROFILE"], ".codex", "auth.json"),
                     encoding="utf-8"))["OPENAI_API_KEY"]
payload = {"model": MODEL, "temperature": 0.2, "max_tokens": MAX_TOKENS,
           "messages": [{"role": "system", "content": SYSTEM},
                        {"role": "user", "content": USER}]}
req = urllib.request.Request(ENDPOINT, data=json.dumps(payload).encode(),
                             headers={"Content-Type": "application/json",
                                      "Authorization": "Bearer " + key})

t0 = time.time()
try:
    with urllib.request.urlopen(req, timeout=900) as resp:
        body = resp.read().decode("utf-8")
    elapsed = round(time.time() - t0, 1)
    resp_obj = json.loads(body)
    json.dump({"endpoint": ENDPOINT, "model": MODEL, "max_tokens": MAX_TOKENS,
               "elapsed_s": elapsed, "input_context_sha256": sha,
               "system_prompt_sha256": hashlib.sha256(SYSTEM.encode()).hexdigest().upper(),
               "user_prompt_sha256": hashlib.sha256(USER.encode()).hexdigest().upper(),
               "response": resp_obj},
              open(os.path.join(HERE, "raw_response.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("DeepSeek 调用完成 %.1fs  usage=%s" % (elapsed, resp_obj.get("usage")))
    api_ok = True
except Exception as exc:
    elapsed = round(time.time() - t0, 1)
    body_text = ""
    if isinstance(exc, urllib.error.HTTPError):
        try:
            body_text = exc.read().decode("utf-8")[:800]
        except Exception:
            pass
    json.dump({"endpoint": ENDPOINT, "model": MODEL, "max_tokens": MAX_TOKENS,
               "elapsed_s": elapsed, "input_context_sha256": sha,
               "error": "%s: %s" % (type(exc).__name__, exc), "error_body": body_text},
              open(os.path.join(HERE, "raw_response.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("DeepSeek 调用失败 %.1fs：%s %s" % (elapsed, type(exc).__name__, str(exc)[:300]))
    api_ok = False

if not api_ok:
    print("按规则：调用失败即停止，不重试、不补调用。")
    raise SystemExit(1)

choice = (resp_obj.get("choices") or [{}])[0]
msg = choice.get("message") or {}
content = msg.get("content") or ""
reasoning = msg.get("reasoning_content") or ""
finish = choice.get("finish_reason")
usage = resp_obj.get("usage") or {}
print("finish_reason=%s  content=%d 字符  reasoning=%d 字符" %
      (finish, len(content), len(reasoning)))

# --------------------------------------------------------------- 4) 原样解析并存题
text = content.strip()
fenced = text.startswith("```")
if fenced:
    import re
    text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
if not text:
    parsed = {"questions": [], "parse_error": "empty content", "raw_text": ""}
else:
    try:
        parsed = json.loads(text)
    except Exception as exc:
        parsed = {"questions": [], "parse_error": str(exc), "raw_text": content[:8000]}
questions = parsed.get("questions") or []
json.dump(parsed, open(os.path.join(HERE, "generated_questions.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("解析得到题目数：%d%s" % (len(questions), "" if not fenced else "（已剥离代码围栏）"))

# --------------------------------------------------------------- 5) validator v2（8 项，规则不放宽）
sys.path.insert(0, VALIDATOR_DIR)
import validator_v2 as V                                    # noqa: E402

blk = {b["block_id"]: b for b in ctx["textbook_blocks"]}
pages_ok = {b["page"] for b in ctx["textbook_blocks"]}
acts_ok = {a["activity_no"] for a in ctx["activity_instructions"]} | {None}
allow = V.build_whitelist(ctx)

seen_q, seen_quote, rows = {}, {}, []
for i, q in enumerate(questions, 1):
    qid = q.get("question_id") or "q%d" % i
    qtype = str(q.get("type") or q.get("question_type") or "?")
    checks = {}
    checks["1_location"] = (q.get("unit") == UNIT and q.get("section") == SECTION_KEY
                            and q.get("page") in pages_ok and q.get("activity") in acts_ok)
    ids = q.get("evidence_block_ids") or []
    checks["2_evidence_ids"] = bool(ids) and all(b in blk for b in ids)
    quote = q.get("evidence_quote") or ""
    checks["3_evidence_quote"] = any(
        V.tokens(quote) and " ".join(V.tokens(quote)) in " ".join(V.tokens(blk[b]["text"]))
        for b in ids if b in blk)
    support = V.answer_support(str(q.get("answer") or ""), quote, q.get("question") or "")
    checks["4_answer_support"] = support in ("EXACT", "VERIFIABLE_REFERENCE", "VERIFIABLE_REPHRASE")
    extra = V.out_of_scope(V.checked_language(q), allow)
    checks["5_vocab_scope"] = not extra
    opts = q.get("options") or []
    if qtype in ("vocab_choice", "reading_choice"):
        co = str(q.get("correct_option") or "").strip().upper()
        ok_co = co in list("ABCD")[:len(opts)]
        checks["6_options"] = (len(opts) >= 3 and ok_co and
                               " ".join(V.tokens(opts["ABCD".index(co) if ok_co else ""]))
                               == " ".join(V.tokens(str(q.get("answer") or ""))))
    else:
        checks["6_options"] = True
    key_q = " ".join(V.tokens(q.get("question")))
    dup = key_q in seen_q
    seen_q[key_q] = qid
    key_quote = " ".join(V.tokens(quote))[:120]
    dup = dup or (seen_quote.get(key_quote, 0) > 0)
    seen_quote[key_quote] = seen_quote.get(key_quote, 0) + 1
    checks["7_dedup"] = not dup
    qt = q.get("question") or ""
    if qtype == "fill":
        checks["8_type_rules"] = "___" in qt
    elif qtype in ("vocab_choice", "reading_choice"):
        checks["8_type_rules"] = len(opts) >= 3 and bool(q.get("correct_option"))
    elif qtype == "reading_judge":
        checks["8_type_rules"] = str(q.get("answer")).strip().lower() in (
            "true", "false", "t", "f", "yes", "no")
    else:
        checks["8_type_rules"] = False
    passed = all(checks.values())
    rows.append({"question_id": qid, "type": qtype, "checks": checks,
                 "answer_support_type": support, "out_of_scope_tokens": extra,
                 "pass": passed, "database_candidate_program": "YES" if passed else "NO"})

result = {"input_context_sha256": sha, "model": MODEL, "max_tokens": MAX_TOKENS,
          "cloud_calls": 1, "local_ai_calls": 0, "elapsed_s": elapsed,
          "finish_reason": finish, "requested_max": 3, "returned": len(questions),
          "pass": sum(1 for r in rows if r["pass"]),
          "fail": sum(1 for r in rows if not r["pass"]),
          "whitelist_size": len(allow), "rows": rows,
          "section": {"unit": UNIT, "section": SECTION_KEY,
                      "section_id": "FLTRP-EN-7A-2022CUR:U1:UNDERSTANDING_IDEAS",
                      "blocks": len(ctx["textbook_blocks"]),
                      "vocab": len(ctx["unit_vocabulary"]),
                      "packages": len(ctx["evidence_packages"])}}
json.dump(result, open(os.path.join(HERE, "validation_result.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# --------------------------------------------------------------- 6) 调用账目
json.dump({
    "run": "20260917_1630_deepseek_second_section_8192",
    "reused_from": "20260917_1610_deepseek_second_section",
    "single_variable_changed": {"max_tokens": {"from": PREV_MAX_TOKENS, "to": MAX_TOKENS}},
    "unchanged": ["input_context.json", "system prompt", "user prompt", "model",
                  "provider", "endpoint", "temperature", "question cap = 3",
                  "question types", "JSON schema", "validator v2"],
    "section": {"unit": UNIT, "section": SECTION_KEY,
                "section_id": "FLTRP-EN-7A-2022CUR:U1:UNDERSTANDING_IDEAS",
                "textbook_pages": [16, 17, 18, 19, 20], "pdf_pages": [21, 22, 23, 24, 25]},
    "input_context_sha256": sha,
    "system_prompt_sha256": hashlib.sha256(SYSTEM.encode()).hexdigest().upper(),
    "user_prompt_sha256": hashlib.sha256(USER.encode()).hexdigest().upper(),
    "model": MODEL, "endpoint": ENDPOINT,
    "cloud_generation_calls": 1, "cloud_metadata_calls": 0,
    "local_ai_calls": 0, "retries": 0,
    "elapsed_s": elapsed,
    "finish_reason": finish,
    "usage": usage,
    "max_tokens_requested": MAX_TOKENS,
    "content_chars": len(content),
    "reasoning_content_chars": len(reasoning),
    "questions_returned": len(questions),
    "validator": {"pass": result["pass"], "fail": result["fail"], "whitelist_size": len(allow)},
}, open(os.path.join(HERE, "call_accounting.json"), "w", encoding="utf-8"),
    ensure_ascii=False, indent=1)

print("校验：通过 %d / 失败 %d" % (result["pass"], result["fail"]))
for r in rows:
    print("  %-4s %-14s %-22s %s" % (r["question_id"], r["type"], r["answer_support_type"],
                                     "PASS" if r["pass"] else "FAIL: %s" % [
                                         k for k, v in r["checks"].items() if not v]))
