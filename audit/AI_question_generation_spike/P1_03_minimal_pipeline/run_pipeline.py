"""P1-03 · AI Question 最小生产流水线（教材证据 → DeepSeek → Validator v2 → question_library.db）。

严格约束：
  * 复用 P0 已验证的 Unit 1 UNDERSTANDING_IDEAS 输入上下文（不重新组装）
  * 复用 P0 已验证的 prompt（由 AST 从 1610 脚本原样提取，逐字一致）
  * AI generation call = 1（无 retry / 无第二模型）
  * 先 Validator，后入库；只有 PASS 才进入 ai_question
  * 全部新题 lifecycle_status = PENDING_REVIEW（绝不 ACTIVE / APPROVED）
  * 不修改 learning.db / contentpack / PDF / MP3 / validator v2
"""
import ast
import hashlib
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = r"D:\ZhixueEnglish"
SPIKE = os.path.join(BASE, "audit", "AI_question_generation_spike")
PREV_CTX = os.path.join(SPIKE, "20260917_1630_deepseek_second_section_8192", "input_context.json")
PREV_RUN_DIR = os.path.join(SPIKE, "20260917_1630_deepseek_second_section_8192")
PROMPT_SRC = os.path.join(SPIKE, "20260917_1610_deepseek_second_section", "run_second_section.py")
VALIDATOR_DIR = os.path.join(SPIKE, "20260917_1520_validator_fix")
LIB = os.path.join(BASE, "structured", "ai", "question_library.db")
CP = os.path.join(BASE, "structured", "contentpack", "v5", "FLTRP-EN-7A-2022CUR.sqlite")

EXPECTED_CTX_SHA = "471E6FA7AA82E03B99E31A43265944D2D8CA98C6924DCB6D38D196474677DFA4"
MODEL = "deepseek-v4-pro"
ENDPOINT = "https://api.deepseek.com/chat/completions"
MAX_TOKENS = 8192
TEMPERATURE = 0.2
PROMPT_VERSION = "P0-v1"          # P0 冻结提示词（以 SHA256 标识，见报告）
VALIDATOR_VERSION = "v2"
TEXTBOOK_ID = "FLTRP-EN-7A-2022CUR"
UNIT_ID = "FLTRP-EN-7A-2022CUR:U1"
SECTION_ID = "FLTRP-EN-7A-2022CUR:U1:UNDERSTANDING_IDEAS"
UNIT_LABEL, SECTION_KEY = "Unit 1", "UNDERSTANDING_IDEAS"
NOW = "2026-09-17T18:40:00+08:00"

sys.path.insert(0, VALIDATOR_DIR)
import validator_v2 as V  # noqa: E402


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest().upper()


def dump(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)


def die(msg, code=1):
    print("PIPELINE_BLOCKED: %s" % msg)
    raise SystemExit(code)


# ============================================================ 1) 复用 P0 上下文（不重新组装）
raw_ctx = open(PREV_CTX, "rb").read()
ctx_sha = sha256_bytes(raw_ctx)
print("[1] 复用上下文 %s" % os.path.relpath(PREV_CTX, BASE))
print("    SHA256 = %s" % ctx_sha)
if ctx_sha != EXPECTED_CTX_SHA:
    die("输入上下文 SHA256 与 P0 记录不一致")
ctx = json.loads(raw_ctx.decode("utf-8"))

# ============================================================ 2) 复用 P0 提示词（AST 原样提取）
tree = ast.parse(open(PROMPT_SRC, encoding="utf-8").read())
SYSTEM = user_expr = None
for node in tree.body:
    if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
        if node.targets[0].id == "SYSTEM":
            SYSTEM = ast.literal_eval(node.value)
        elif node.targets[0].id == "USER":
            user_expr = node.value
if SYSTEM is None or user_expr is None:
    die("未能从 P0 脚本提取提示词")
USER = eval(compile(ast.Expression(user_expr), "<p0_prompt>", "eval"),
            {"json": json, "ctx": ctx})
sys_sha = sha256_bytes(SYSTEM.encode())
usr_sha = sha256_bytes(USER.encode())
prev_acc = json.load(open(os.path.join(PREV_RUN_DIR, "call_accounting.json"), encoding="utf-8"))
print("[2] 提示词重建：system %s / user %s" % (sys_sha[:16], usr_sha[:16]))
if sys_sha != prev_acc.get("system_prompt_sha256") or usr_sha != prev_acc.get("user_prompt_sha256"):
    die("提示词 SHA256 与 P0(1630) 记录不一致——不允许修改提示词")
print("    与 P0(1630) 记录的提示词 SHA256 完全一致")

# ============================================================ 3) 参考数据（只读 contentpack）
cp = sqlite3.connect("file:" + CP + "?mode=ro", uri=True)
cp.row_factory = sqlite3.Row
snap = cp.execute("select snapshot_id from parse_snapshot where is_active=1").fetchone()[0]
if not cp.execute("select 1 from unit where unit_id=?", (UNIT_ID,)).fetchone():
    die("unit_id 不存在：%s" % UNIT_ID)
if not cp.execute("select 1 from section where section_id=?", (SECTION_ID,)).fetchone():
    die("section_id 不存在：%s" % SECTION_ID)

blocks_known = {r[0] for r in cp.execute("select block_id from content_block")}
items_known = {r[0] for r in cp.execute("select item_id from learning_item")}

# 词表词 -> LearningObject（严格：surface_form 以 "<word> " 或 "<word>/" 开头）
vocab_of_word = {}
for r in cp.execute("select item_id, surface_form from learning_item where item_type='vocabulary'"):
    sf = (r["surface_form"] or "").strip()
    head = sf.split("/", 1)[0].strip().lower()
    if head:
        vocab_of_word.setdefault(head, r["item_id"])
# 活动 -> 该活动的 exercise LearningObject
exercise_of_activity = {}
for r in cp.execute("select li.item_id, sr.source_id from learning_item li "
                    "join source_ref sr on sr.item_id=li.item_id "
                    "where li.item_type='exercise'"):
    exercise_of_activity.setdefault(r["source_id"], r["item_id"])

missing_vocab = [v["word"] for v in ctx["unit_vocabulary"] if v["word"].lower() not in vocab_of_word]
print("[3] snapshot=%s | blocks=%d | learning_item=%d | vocab 词表已映射 %d/%d%s" % (
    snap, len(blocks_known), len(items_known), len(ctx["unit_vocabulary"]) - len(missing_vocab),
    len(ctx["unit_vocabulary"]), ("（缺：%s）" % missing_vocab) if missing_vocab else ""))

# ============================================================ 4) 调用前先创建 generation_run
run_id = "AIRUN:20260917T1840:P103"
scope_key = hashlib.sha256("\x01".join([SECTION_ID, "", PROMPT_VERSION, ctx_sha]).encode()).hexdigest().upper()
lib = sqlite3.connect(LIB)
lib.execute("PRAGMA foreign_keys = ON")
if lib.execute("select count(*) from ai_question").fetchone()[0] != 0:
    die("正式题库非空（%d 条），本轮不得覆盖" %
        lib.execute("select count(*) from ai_question").fetchone()[0])
lib.execute(
    "INSERT INTO generation_run (run_id, generation_scope_key, textbook_id, snapshot_id, unit_id, "
    "section_id, activity_id, model, prompt_version, context_hash, provider, context_ref, "
    "raw_response_ref, requested_max, max_tokens, question_count, status, insufficient_evidence, "
    "note, generated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
    (run_id, scope_key, TEXTBOOK_ID, snap, UNIT_ID, SECTION_ID, None, MODEL, PROMPT_VERSION,
     ctx_sha, "deepseek", os.path.relpath(PREV_CTX, BASE),
     "P1_03_minimal_pipeline/raw_response.json", 3, MAX_TOKENS, 0, "API_ERROR", 0,
     "in-flight: generation call issued", NOW))
lib.commit()
print("[4] 已创建 generation_run %s（in-flight，调用后回填）" % run_id)

# ============================================================ 5) 唯一一次 DeepSeek 调用
key = json.load(open(os.path.join(os.environ["USERPROFILE"], ".codex", "auth.json"),
                     encoding="utf-8"))["OPENAI_API_KEY"]
payload = {"model": MODEL, "temperature": TEMPERATURE, "max_tokens": MAX_TOKENS,
           "messages": [{"role": "system", "content": SYSTEM},
                        {"role": "user", "content": USER}]}
req = urllib.request.Request(ENDPOINT, data=json.dumps(payload).encode(),
                             headers={"Content-Type": "application/json",
                                      "Authorization": "Bearer " + key})
t0 = time.time()
api_error = None
try:
    with urllib.request.urlopen(req, timeout=900) as resp:
        body = resp.read().decode("utf-8")
    elapsed_ms = int((time.time() - t0) * 1000)
    resp_obj = json.loads(body)
except Exception as exc:
    elapsed_ms = int((time.time() - t0) * 1000)
    detail = ""
    if isinstance(exc, urllib.error.HTTPError):
        try:
            detail = exc.read().decode("utf-8")[:600]
        except Exception:
            pass
    api_error = "%s: %s %s" % (type(exc).__name__, exc, detail)
    resp_obj = None

dump(os.path.join(HERE, "raw_response.json"),
     {"endpoint": ENDPOINT, "model": MODEL, "max_tokens": MAX_TOKENS,
      "elapsed_ms": elapsed_ms, "context_hash": ctx_sha,
      "system_prompt_sha256": sys_sha, "user_prompt_sha256": usr_sha,
      "error": api_error, "response": resp_obj})

if api_error:
    lib.execute("UPDATE generation_run SET status='API_ERROR', elapsed_ms=?, error=?, note=? "
                "WHERE run_id=?", (elapsed_ms, api_error, "AI call failed; no retry", run_id))
    lib.commit()
    print("[5] AI 调用失败：%s（已记录 generation_run，本轮停止，无重试）" % api_error)
    raise SystemExit(1)

choice = (resp_obj.get("choices") or [{}])[0]
msg = choice.get("message") or {}
content = msg.get("content") or ""
finish = choice.get("finish_reason")
usage = resp_obj.get("usage") or {}
print("[5] DeepSeek 调用完成 %.1fs | finish=%s | content=%d 字符 | usage=%s" % (
    elapsed_ms / 1000.0, finish, len(content), json.dumps(usage, ensure_ascii=False)))

# ============================================================ 6) 解析
text = content.strip()
fenced = text.startswith("```")
if fenced:
    import re
    text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
try:
    parsed = json.loads(text) if text else {"questions": []}
except Exception as exc:
    parsed = {"questions": [], "parse_error": str(exc), "raw_text": content[:4000]}
questions = parsed.get("questions") or []
dump(os.path.join(HERE, "generated_questions.json"), parsed)
print("[6] 解析得到 %d 道题" % len(questions))

run_status = {"stop": "OK", "length": "TRUNCATED"}.get(finish, "OK")
lib.execute("UPDATE generation_run SET status=?, question_count=?, finish_reason=?, usage_json=?, "
            "elapsed_ms=?, note=? WHERE run_id=?",
            (run_status, len(questions), finish, json.dumps(usage, ensure_ascii=False),
             elapsed_ms, "single generation call; no retry", run_id))
lib.commit()

# ============================================================ 7) Validator v2（先验证，后入库）
allow = V.build_whitelist(ctx)
blk = {b["block_id"]: b for b in ctx["textbook_blocks"]}
pages_ok = {b["page"] for b in ctx["textbook_blocks"]}
acts_ok = {a["activity_no"] for a in ctx["activity_instructions"]} | {None}
seen_q, seen_quote, rows = {}, {}, []

for i, q in enumerate(questions, 1):
    qid = q.get("question_id") or "q%d" % i
    qtype = str(q.get("type") or "?")
    checks = {}
    checks["1_location"] = (q.get("unit") == UNIT_LABEL and q.get("section") == SECTION_KEY
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
    kq = " ".join(V.tokens(quote))[:120]
    dup = dup or seen_quote.get(kq, 0) > 0
    seen_quote[kq] = seen_quote.get(kq, 0) + 1
    checks["7_dedup"] = not dup
    qt = q.get("question") or ""
    if qtype == "fill":
        checks["8_type_rules"] = "___" in qt
    elif qtype in ("vocab_choice", "reading_choice"):
        checks["8_type_rules"] = len(opts) >= 3 and bool(q.get("correct_option"))
    else:
        checks["8_type_rules"] = False
    rows.append({"source_index": i, "model_question_id": qid, "type": qtype,
                 "checks": checks, "answer_support_type": support,
                 "out_of_scope_tokens": extra, "pass": all(checks.values()),
                 "question": q})
print("[7] Validator v2：PASS %d / FAIL %d" % (
    sum(1 for r in rows if r["pass"]), sum(1 for r in rows if not r["pass"])))

# ============================================================ 8) 仅 PASS 题入库（PENDING_REVIEW）
inserted, rejected = [], []
for r in rows:
    q = r["question"]
    act_no = q.get("activity")
    activity_id = ("FLTRP-EN-7A-2022CUR:U1:UNDERSTANDING_IDEAS:A%s" % act_no) if act_no else None
    if activity_id and not cp.execute("select 1 from activity where activity_id=?",
                                      (activity_id,)).fetchone():
        activity_id = None
    # question_fingerprint = hash(section_id, activity_id, question_type, norm(question_text),
    #                             norm(evidence_quote))   —— 与 P1-01/P1-02 完全一致
    fp = hashlib.sha256("\x01".join([
        SECTION_ID, activity_id or "", q.get("type") or "",
        " ".join(V.tokens(q.get("question") or "")),
        " ".join(V.tokens(q.get("evidence_quote") or "")),
    ]).encode()).hexdigest().upper()
    question_id = "AIQ:" + fp[:12]
    r["fingerprint"] = fp
    r["question_id"] = question_id
    r["activity_id"] = activity_id

    if not r["pass"]:
        rejected.append({"question_id": question_id, "reason": "validator_fail",
                         "failed_checks": [k for k, v in r["checks"].items() if not v],
                         "answer_support_type": r["answer_support_type"]})
        continue

    # --- LearningObject 映射（必须真实存在）
    objs = []
    if r["type"] in ("fill", "vocab_choice"):
        w = (q.get("answer") or "").split()[0].strip(".,!?'\u2019\u201d").lower()
        vid = vocab_of_word.get(w)
        if vid:
            objs.append((vid, 1))
    exid = exercise_of_activity.get(activity_id)
    if exid:
        objs.append((exid, 1 if not objs else 0))
    if not objs:
        rejected.append({"question_id": question_id, "reason": "no_learning_object_mapping",
                         "answer_support_type": r["answer_support_type"]})
        continue
    bad = [i for i, _ in objs if i not in items_known]
    bad_blk = [b for b in (q.get("evidence_block_ids") or []) if b not in blocks_known]
    if bad or bad_blk:
        rejected.append({"question_id": question_id, "reason": "dangling_reference",
                         "dangling_items": bad, "dangling_blocks": bad_blk})
        continue

    if lib.execute("select 1 from ai_question where question_fingerprint=?", (fp,)).fetchone():
        rejected.append({"question_id": question_id, "reason": "fingerprint_exists"})
        continue

    lib.execute(
        "INSERT INTO ai_question (question_id, version, question_type, question_text, options_json,"
        " correct_option, correct_answer, explanation, difficulty, textbook_id, snapshot_id,"
        " unit_id, section_id, activity_id, page, generation_run_id, generated_at,"
        " question_fingerprint, lifecycle_status, active, stale, needs_human_review,"
        " validator_version, created_at, updated_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (question_id, 1, r["type"], q.get("question"), json.dumps(q.get("options") or [],
         ensure_ascii=False) if q.get("options") else None, q.get("correct_option") or None,
         q.get("answer"), q.get("explanation"), q.get("difficulty"), TEXTBOOK_ID, snap,
         UNIT_ID, SECTION_ID, activity_id, q.get("page"), run_id, NOW, fp,
         "GENERATED", 0, 0, 0, VALIDATOR_VERSION, NOW, NOW))
    for n, b in enumerate(q.get("evidence_block_ids") or [], 1):
        lib.execute("INSERT INTO question_evidence (question_id, version, ordinal, evidence_block_id,"
                    " evidence_quote, is_primary) VALUES (?,?,?,?,?,?)",
                    (question_id, 1, n, b, q.get("evidence_quote"), 1 if n == 1 else 0))
    for item_id, is_primary in objs:
        lib.execute("INSERT INTO question_learning_object (question_id, version, item_id, is_primary)"
                    " VALUES (?,?,?,?)", (question_id, 1, item_id, is_primary))
    lib.execute(
        "INSERT INTO question_validation (question_id, version, validator_version, validation_result,"
        " validated_at, answer_support_type, checks_json, out_of_scope_tokens_json,"
        " needs_human_review, note) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (question_id, 1, VALIDATOR_VERSION, "PASS", NOW, r["answer_support_type"],
         json.dumps(r["checks"], ensure_ascii=False),
         json.dumps(r["out_of_scope_tokens"], ensure_ascii=False), 0,
         "P1-03 minimal pipeline: validator v2 PASS"))
    lib.execute(
        "INSERT INTO question_event (event_id, question_id, version, event_type, from_status,"
        " to_status, event_at, actor, actor_kind, note) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("AIEV:%s:V1" % question_id.split(":")[1], question_id, 1, "VALIDATED", "GENERATED",
         "PENDING_REVIEW", NOW, "validator_v2", "machine",
         "lifecycle chain GENERATED -> VALIDATED -> PENDING_REVIEW; 本轮无人工审核"))
    lib.execute("UPDATE ai_question SET lifecycle_status='PENDING_REVIEW', updated_at=? "
                "WHERE question_id=? AND version=1", (NOW, question_id))
    lib.commit()
    inserted.append({"question_id": question_id, "type": r["type"],
                     "answer_support_type": r["answer_support_type"],
                     "learning_objects": [i for i, _ in objs], "activity_id": activity_id})
print("[8] 入库 %d 道（全部 PENDING_REVIEW）| 未入库 %d 道" % (len(inserted), len(rejected)))
for rej in rejected:
    print("    未入库：%s | %s" % (rej["question_id"], rej["reason"]))

dump(os.path.join(HERE, "validation_result.json"),
     {"validator_version": VALIDATOR_VERSION, "whitelist_size": len(allow),
      "returned": len(questions), "pass": sum(1 for r in rows if r["pass"]),
      "fail": sum(1 for r in rows if not r["pass"]),
      "rows": [{k: v for k, v in r.items() if k != "question"} for r in rows]})
cp.close()
lib.close()
print("完成。")
