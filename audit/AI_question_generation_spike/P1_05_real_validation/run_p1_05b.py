"""P1-05-B · 多 Section 小规模真实质量验证。

严格按 P1-05-A 冻结方案：
  * 样本 = p1_05_sample_matrix.json 的 7 个 Section（不换样本）
  * 模型 = deepseek-v4-pro（不使用本地 Qwen / 其他 AI）
  * 每个 Section 一条独立 generation_run；Section 为 generation scope，保留 Activity provenance
  * prompt_version = P1-05-v1（P0-v1 去掉题量配额；参数化页面/活动范围；见 prompt_meta）
  * validator = P1-04 的 validator_v3（不改）
  * 默认 retry = 0（仅 HTTP 层失败且无 content 时允许 1 次，并完整记录）
  * 入库状态一律 GENERATED -> VALIDATED -> PENDING_REVIEW，绝不 ACTIVE
  * 每次记录 latency / tokens / finish_reason / retry_count / question_count
  * 触发 S1-S8 中可机械判定的条件即立即停止
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
MATRIX = os.path.join(SPIKE, "P1_05_sample_design", "p1_05_sample_matrix.json")
PROMPT_SRC = os.path.join(SPIKE, "20260917_1610_deepseek_second_section", "run_second_section.py")
VALIDATOR_DIR = os.path.join(SPIKE, "P1_04_rule_fixes")
CP = os.path.join(BASE, "structured", "contentpack", "v5", "FLTRP-EN-7A-2022CUR.sqlite")
LIB = os.path.join(BASE, "structured", "ai", "question_library.db")
RUNS_DIR = os.path.join(HERE, "runs")

MODEL = "deepseek-v4-pro"
ENDPOINT = "https://api.deepseek.com/chat/completions"
MAX_TOKENS = 8192
TEMPERATURE = 0.2
PROMPT_VERSION = "P1-05-v1"
VALIDATOR_VERSION = "v3"
TEXTBOOK_ID = "FLTRP-EN-7A-2022CUR"
TS_BASE = "2026-09-17T19:30"

sys.path.insert(0, VALIDATOR_DIR)
import validator_v3 as V3  # noqa: E402
sys.path.insert(0, os.path.join(BASE, "web"))
import content as C  # noqa: E402

os.makedirs(RUNS_DIR, exist_ok=True)
PREPARE_ONLY = "--prepare-only" in sys.argv


def sha(b):
    return hashlib.sha256(b).hexdigest().upper()


def dump(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)


def stop(reason, code=2):
    print("STOP_CONDITION: %s" % reason)
    raise SystemExit(code)


# ---------------------------------------------------------------- 1) 参考数据
cp = sqlite3.connect("file:" + CP + "?mode=ro", uri=True)
cp.row_factory = sqlite3.Row
snapshot = cp.execute("select snapshot_id from parse_snapshot where is_active=1").fetchone()[0]
blocks_known = {r[0] for r in cp.execute("select block_id from content_block")}
items_known = {r[0] for r in cp.execute("select item_id from learning_item")}
vocab_of_word = {}
for r in cp.execute("select item_id, surface_form from learning_item where item_type='vocabulary'"):
    head = (r["surface_form"] or "").strip().split("/", 1)[0].strip().lower()
    if head:
        vocab_of_word.setdefault(head, r["item_id"])
exercise_of_activity = {}
for r in cp.execute("select li.item_id, sr.source_id from learning_item li "
                    "join source_ref sr on sr.item_id=li.item_id where li.item_type='exercise'"):
    exercise_of_activity.setdefault(r["source_id"], r["item_id"])
audio_activity_ids = {r[0] for r in cp.execute(
    "select distinct activity_id from activity where activity_id in "
    "(select target_id from audio_mapping where target_type='activity')")}

matrix = json.load(open(MATRIX, encoding="utf-8"))
SECTIONS = matrix["sections"]

# ---------------------------------------------------------------- 2) P1-05-v1 提示词
tree = ast.parse(open(PROMPT_SRC, encoding="utf-8").read())
SYSTEM_P0 = user_src = None
for node in tree.body:
    if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
        if node.targets[0].id == "SYSTEM":
            SYSTEM_P0 = ast.literal_eval(node.value)
        elif node.targets[0].id == "USER":
            user_src = node.value
assert SYSTEM_P0 and user_src

OLD_Q = ("Quantity: AT MOST 3 questions. Fewer is acceptable; 0 is acceptable if the "
         "evidence is insufficient.\nPrefer this distribution when the evidence allows: "
         "1 fill, 1 vocab_choice, 1 reading_choice/reading_judge.")
NEW_Q = ("Quantity: no quota. Generate as many questions as the supplied textbook evidence "
         "can reliably and uniquely support, and no more. Fewer is acceptable. 0 is an "
         "acceptable and expected answer when the evidence does not support reliable, unique, "
         "traceable questions. Do not create a question merely to reach a number. Prefer "
         "covering different pieces of evidence over restating the same sentence.")
OLD_READ = "about explicit facts in the story blocks (page 17)"
NEW_READ = "about explicit facts in the provided textbook blocks"
OLD_PAGE = ("page must be one of 16,17,18,19,20 and activity must be one of 2,3,4,5,6,8 "
            "(or null).")

PROMPT_DIFF = {
    "base": "P0-v1（20260917_1610_deepseek_second_section/run_second_section.py 中的 SYSTEM 字面量）",
    "changes": [
        {"kind": "quota_removed", "old": OLD_Q, "new": NEW_Q},
        {"kind": "desectionalised_reading_bullet", "old": OLD_READ, "new": NEW_READ},
        {"kind": "parameterised_page_activity", "old": OLD_PAGE, "new": "<per-section>"},
        {"kind": "user_tail", "old": "Generate at most 3 questions now. Output JSON only.",
         "new": "Generate questions for this Section now. Output JSON only."},
    ],
    "note": ("P0-v1 的页面/活动行与 (page 17) 是硬编码给 Unit 1 UI 的；"
             "为在 7 个不同 Section 上执行冻结设计，必须按 Section 参数化。"
             "10 条硬规则、JSON schema、题型定义逐字未改。"),
}


def build_system(pages, act_nos):
    s = SYSTEM_P0
    for old, new in ((OLD_Q, NEW_Q), (OLD_READ, NEW_READ),
                     (OLD_PAGE, "page must be one of %s and activity must be one of %s (or null)."
                      % (",".join(str(p) for p in pages), ",".join(str(a) for a in act_nos)))):
        if s.count(old) != 1:
            stop("提示词替换失败（找不到唯一片段）：%s" % old[:40])
        s = s.replace(old, new)
    return s


# ---------------------------------------------------------------- 3) 逐 Section 组装上下文
page2sec = {}
for r in cp.execute("select distinct pdf_page, section_id from activity"):
    page2sec.setdefault(r["pdf_page"], set()).add(r["section_id"])
blocks_by_sec = {}
for r in cp.execute("select b.block_id, b.block_kind, b.layout_role, b.text_raw, p.pdf_page "
                    "from content_block b join page p on p.page_id=b.page_id "
                    "order by p.pdf_page, b.reading_order"):
    if r["block_kind"] == "footer_text":
        continue
    text = (r["text_raw"] or "").replace("\n", " ").strip()
    if not text:
        continue
    for s in page2sec.get(r["pdf_page"], []):
        blocks_by_sec.setdefault(s, []).append(
            {"block_id": r["block_id"], "kind": r["block_kind"],
             "role": r["layout_role"], "text": text})

emph = {}
for r in cp.execute("select item_id, textbook_emphasis from source_ref "
                    "where item_id like 'FLTRP-EN-7A-2022CUR:V:%'"):
    emph.setdefault(r["item_id"], r["textbook_emphasis"])
unit_vocab_cache = {}


def unit_vocabulary(unit_key):
    if unit_key not in unit_vocab_cache:
        rows = []
        for item in C.list_unit_resources(unit_key, "vocabulary")["items"]:
            rows.append({"word": item["text"], "pos": item["part_of_speech"],
                         "meaning_zh": item["meaning"],
                         "emphasis": emph.get(item["item_id"], "PLAIN"),
                         "is_core": bool(item["can_study"]), "textbook_page": item["page"]})
        unit_vocab_cache[unit_key] = rows
    return unit_vocab_cache[unit_key]


evidence_map = json.load(open(os.path.join(BASE, "structured", "ai",
                                           "textbook_evidence_map_v1.json"), encoding="utf-8"))
packages_by_scope = {}
for p in evidence_map["packages"]:
    packages_by_scope.setdefault((p["scope"]["unit"], p["scope"]["section"]), []).append(p)


def build_context(sec, run_idx):
    sid = sec["section_id"]
    acts = []
    for r in cp.execute("select activity_id, activity_number, textbook_page, pdf_page, instruction "
                        "from activity where section_id=? order by activity_number", (sid,)):
        acts.append({"activity_no": r["activity_number"], "page": r["textbook_page"],
                     "instruction": r["instruction"],
                     "audio_required": r["activity_id"] in audio_activity_ids})
    packages = []
    for p in packages_by_scope.get((sec["unit"], sec["section_key"]), []):
        tr = p["textbook_reference"]
        packages.append({"question_id": p["question_id"],
                         "activity_no": p["scope"].get("activity_no"),
                         "question_no": p["scope"].get("question_no"),
                         "page": tr.get("textbook_page"), "instruction": tr.get("instruction"),
                         "original_question_text": (p["original_question"] or {}).get("text", "")[:300],
                         "answer_source": p.get("answer_source"),
                         "answer_note": p.get("answer_note")})
    unit_key = "starter" if sec["unit"] == "Starter" else sec["unit"].lower().replace(" ", "")
    ctx = {"textbook_position": {
               "unit": sec["unit"], "unit_title": sec["unit_title"],
               "section": sec["section_key"], "section_title": sec["section_title"],
               "textbook_pages": list(range(sec["textbook_page_range"][0],
                                            sec["textbook_page_range"][1] + 1)),
               "section_id": sid, "is_listening_gap_control": sec["category"] == "F_LISTENING_GAP"},
           "activity_instructions": acts,
           "textbook_blocks": blocks_by_sec.get(sid, []),
           "unit_vocabulary": unit_vocabulary(unit_key),
           "evidence_packages": packages,
           "rules": {"BOLD": "core textbook word (教材黑体重点词)",
                     "PLAIN": "ordinary textbook word (非核心重点词)",
                     "audio_required": ("该活动的内容在音频中，提供的证据里没有音频转写文本" )}}
    return ctx, unit_key


# ---------------------------------------------------------------- 4) 主流程
lib = sqlite3.connect(LIB)
lib.execute("PRAGMA foreign_keys = ON")
key = json.load(open(os.path.join(os.environ["USERPROFILE"], ".codex", "auth.json"),
                     encoding="utf-8"))["OPENAI_API_KEY"]

protected_before = {}
for name, path in [("learning.db", os.path.join(BASE, "structured", "learning", "learning.db")),
                   ("contentpack", CP),
                   ("validator_v2", os.path.join(SPIKE, "20260917_1520_validator_fix", "validator_v2.py")),
                   ("validator_v3", os.path.join(VALIDATOR_DIR, "validator_v3.py"))]:
    protected_before[name] = sha(open(path, "rb").read())

summary = {"model": MODEL, "prompt_version": PROMPT_VERSION, "validator_version": VALIDATOR_VERSION,
           "prompt_diff": PROMPT_DIFF, "snapshot_id": snapshot, "sections": [], "stopped": None}

for idx, sec in enumerate(SECTIONS, 1):
    sid = sec["section_id"]
    ctx, unit_key = build_context(sec, idx)
    ctx_bytes = json.dumps(ctx, ensure_ascii=False, sort_keys=True).encode()
    ctx_hash = sha(ctx_bytes)
    pages = ctx["textbook_position"]["textbook_pages"]
    act_nos = [a["activity_no"] for a in ctx["activity_instructions"]]
    SYSTEM = build_system(pages, act_nos)
    USER = ("Textbook scope and evidence (JSON):\n" + json.dumps(ctx, ensure_ascii=False) +
            "\n\nGenerate questions for this Section now. Output JSON only.")
    scope_key = sha("\x01".join([sid, "", PROMPT_VERSION, ctx_hash]).encode())
    tag = "%s_%s" % (sec["unit"].replace(" ", ""), sec["section_key"])

    if PREPARE_ONLY:
        dump(os.path.join(RUNS_DIR, "%02d_%s_context.json" % (idx, tag)), ctx)
        dump(os.path.join(RUNS_DIR, "%02d_%s_prompt.json" % (idx, tag)),
             {"section_id": sid, "context_hash": ctx_hash, "scope_key": scope_key,
              "system_prompt_sha256": sha(SYSTEM.encode()),
              "user_prompt_sha256": sha(USER.encode()),
              "system_prompt": SYSTEM, "user_prompt_len": len(USER),
              "pages": pages, "activity_nos": act_nos,
              "blocks": len(ctx["textbook_blocks"]),
              "packages": len(ctx["evidence_packages"]),
              "activity_instructions": ctx["activity_instructions"]})
        print("[%d/7] %s 准备完成 | blocks=%d packages=%d acts=%s pages=%s user_len=%d" % (
            idx, tag, len(ctx["textbook_blocks"]), len(ctx["evidence_packages"]),
            act_nos, pages, len(USER)))
        continue

    if lib.execute("select 1 from generation_run where generation_scope_key=? and status='OK'",
                   (scope_key,)).fetchone():
        summary["sections"].append({"section_id": sid, "status": "SKIPPED_SCOPE_EXISTS"})
        print("[%d/7] %s → SKIPPED（scope key 已存在）" % (idx, tag))
        continue

    run_id = "AIRUN:20260917T1930:P105_%d" % idx
    lib.execute(
        "INSERT INTO generation_run (run_id, generation_scope_key, textbook_id, snapshot_id, "
        "unit_id, section_id, model, prompt_version, context_hash, provider, requested_max, "
        "max_tokens, question_count, status, generated_at, note) "
        "VALUES (?,?,?,?,?,?,?,?,?,'deepseek',NULL,?,0,'API_ERROR',?,'in-flight')",
        (run_id, scope_key, TEXTBOOK_ID, snapshot, sec["unit_id"], sid, MODEL, PROMPT_VERSION,
         ctx_hash, MAX_TOKENS, TS_BASE + ":00+08:00"))
    lib.commit()

    payload = {"model": MODEL, "temperature": TEMPERATURE, "max_tokens": MAX_TOKENS,
               "messages": [{"role": "system", "content": SYSTEM},
                            {"role": "user", "content": USER}]}
    req = urllib.request.Request(ENDPOINT, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer " + key})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=880) as resp:
            body = resp.read().decode("utf-8")
        latency = int((time.time() - t0) * 1000)
        resp_obj = json.loads(body)
        err = None
    except Exception as exc:
        latency = int((time.time() - t0) * 1000)
        err = "%s: %s" % (type(exc).__name__, exc)
        resp_obj = None
    dump(os.path.join(RUNS_DIR, "%02d_%s_raw_response.json" % (idx, tag)),
         {"run_id": run_id, "section_id": sid, "context_hash": ctx_hash,
          "system_prompt_sha256": sha(SYSTEM.encode()), "user_prompt_sha256": sha(USER.encode()),
          "latency_ms": latency, "retry_count": 0, "error": err, "response": resp_obj})

    if err:
        lib.execute("UPDATE generation_run SET status='API_ERROR', elapsed_ms=?, error=?, "
                    "note='HTTP layer failure; no retry performed' WHERE run_id=?",
                    (latency, err, run_id))
        lib.commit()
        summary["stopped"] = "API_ERROR on %s" % sid
        stop("S7/失败调用：%s" % err)

    choice = (resp_obj.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    content = msg.get("content") or ""
    finish = choice.get("finish_reason")
    usage = resp_obj.get("usage") or {}

    text = content.strip()
    if text.startswith("```"):
        import re
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text) if text else {"questions": []}
    except Exception as exc:
        parsed = {"questions": [], "parse_error": str(exc), "raw_text": content[:4000]}
    questions = parsed.get("questions") or []
    dump(os.path.join(RUNS_DIR, "%02d_%s_questions.json" % (idx, tag)), parsed)

    run_status = {"stop": "OK", "length": "TRUNCATED"}.get(finish, "OK")
    lib.execute("UPDATE generation_run SET status=?, question_count=?, finish_reason=?, "
                "usage_json=?, elapsed_ms=?, note=? WHERE run_id=?",
                (run_status, len(questions), finish, json.dumps(usage, ensure_ascii=False),
                 latency, "single generation call; retry_count=0", run_id))
    lib.commit()

    # ---- validator v3
    allow = V3.build_whitelist(ctx)
    blk = {b["block_id"]: b for b in ctx["textbook_blocks"]}
    pages_ok = set(pages)
    acts_ok = set(act_nos) | {None}
    # 教材原题打印的选项文本（printed_option_overlap 判定用）
    printed = " || ".join((p.get("original_question_text") or "")
                          for p in ctx["evidence_packages"]).lower()
    rows = V3.validate_batch(questions, blocks_by_id=blk, pages_ok=pages_ok, acts_ok=acts_ok,
                             allow=allow, unit_label=ctx["textbook_position"]["unit"],
                             section_key=ctx["textbook_position"]["section"])

    inserted = []
    for r in rows:
        q = questions[r["source_index"] - 1]
        act_no = q.get("activity")
        activity_id = ("%s:A%s" % (sid, act_no)) if act_no is not None else None
        if activity_id and not cp.execute("select 1 from activity where activity_id=?",
                                          (activity_id,)).fetchone():
            activity_id = None
        fp = sha("\x01".join([sid, activity_id or "", str(q.get("type") or ""),
                              " ".join(V3.tokens(q.get("question") or "")),
                              " ".join(V3.tokens(q.get("evidence_quote") or ""))]).encode())
        question_id = "AIQ:" + fp[:12]
        r.update({"question_id": question_id, "fingerprint": fp, "activity_id": activity_id})
        answer = str(q.get("answer") or "")
        overlap = bool(answer) and answer.strip().lower() in printed
        r["printed_option_overlap"] = overlap

        if not r["pass"]:
            r["entered"] = False
            r["reject_reason"] = "validator_fail"
            continue
        if lib.execute("select 1 from ai_question where question_fingerprint=?", (fp,)).fetchone():
            r["entered"] = False
            r["reject_reason"] = "fingerprint_exists"
            continue
        objs = []
        if r["type"] in ("fill", "vocab_choice"):
            w = answer.split()[0].strip(".,!?'\u2019\u201d").lower() if answer else ""
            vid = vocab_of_word.get(w)
            if vid:
                objs.append((vid, 1))
        exid = exercise_of_activity.get(activity_id)
        if exid:
            objs.append((exid, 1 if not objs else 0))
        if not objs or any(i not in items_known for i, _ in objs):
            r["entered"] = False
            r["reject_reason"] = "no_valid_learning_object"
            continue
        bad_blocks = [b for b in (q.get("evidence_block_ids") or []) if b not in blocks_known]
        if bad_blocks:
            r["entered"] = False
            r["reject_reason"] = "dangling_evidence_block"
            continue

        now = TS_BASE + ":00+08:00"
        lib.execute(
            "INSERT INTO ai_question (question_id, version, question_type, question_text, "
            "options_json, correct_option, correct_answer, explanation, difficulty, textbook_id, "
            "snapshot_id, unit_id, section_id, activity_id, page, generation_run_id, generated_at,"
            " question_fingerprint, lifecycle_status, active, stale, needs_human_review, "
            "validator_version, created_at, updated_at) "
            "VALUES (?,1,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'GENERATED',0,0,0,?,?,?)",
            (question_id, r["type"], q.get("question"),
             json.dumps(q.get("options") or [], ensure_ascii=False) if q.get("options") else None,
             q.get("correct_option") or None, answer, q.get("explanation"), q.get("difficulty"),
             TEXTBOOK_ID, snapshot, sec["unit_id"], sid, activity_id, q.get("page"), run_id,
             now, fp, VALIDATOR_VERSION, now, now))
        for n, b in enumerate(q.get("evidence_block_ids") or [], 1):
            lib.execute("INSERT INTO question_evidence (question_id, version, ordinal, "
                        "evidence_block_id, evidence_quote, is_primary) VALUES (?,1,?,?,?,?)",
                        (question_id, n, b, q.get("evidence_quote"), 1 if n == 1 else 0))
        for item_id, pri in objs:
            lib.execute("INSERT INTO question_learning_object (question_id, version, item_id, "
                        "is_primary) VALUES (?,1,?,?)", (question_id, item_id, pri))
        lib.execute(
            "INSERT INTO question_validation (question_id, version, validator_version, "
            "validation_result, validated_at, answer_support_type, checks_json, "
            "out_of_scope_tokens_json, needs_human_review, note) "
            "VALUES (?,1,?,?,?,?,?,?,0,?)",
            (question_id, VALIDATOR_VERSION, "PASS", now, r["answer_support_type"],
             json.dumps(r["checks"], ensure_ascii=False),
             json.dumps(r["out_of_scope_tokens"], ensure_ascii=False),
             "P1-05-B; printed_option_overlap=%s" % ("true" if overlap else "false")))
        lib.execute(
            "INSERT INTO question_event (event_id, question_id, version, event_type, from_status,"
            " to_status, event_at, actor, actor_kind, note) VALUES (?,?,1,'VALIDATED',"
            "'GENERATED','PENDING_REVIEW',?,?, 'machine', ?)",
            ("AIEV:%s:V1" % fp[:12], question_id, now, "validator_v3",
             "P1-05-B chain GENERATED -> VALIDATED -> PENDING_REVIEW; no human review in this round"))
        lib.execute("UPDATE ai_question SET lifecycle_status='PENDING_REVIEW', updated_at=? "
                    "WHERE question_id=? AND version=1", (now, question_id))
        lib.commit()
        r["entered"] = True
        inserted.append(question_id)

    dump(os.path.join(RUNS_DIR, "%02d_%s_validation.json" % (idx, tag)),
         {"section_id": sid, "run_id": run_id, "returned": len(questions),
          "pass": sum(1 for r in rows if r["pass"]),
          "fail": sum(1 for r in rows if not r["pass"]),
          "rows": [{k: v for k, v in r.items() if k != "question"} for r in rows]})
    summary["sections"].append({
        "index": idx, "tag": tag, "section_id": sid, "category": sec["category"],
        "run_id": run_id, "context_hash": ctx_hash, "scope_key": scope_key,
        "latency_ms": latency, "finish_reason": finish, "usage": usage, "retry_count": 0,
        "generated": len(questions), "pass": sum(1 for r in rows if r["pass"]),
        "fail": sum(1 for r in rows if not r["pass"]), "entered": inserted,
        "printed_option_overlap": [r["question_id"] for r in rows if r.get("printed_option_overlap")],
        "rows": [{k: v for k, v in r.items() if k != "question"} for r in rows]})
    print("[%d/7] %-28s gen=%d pass=%d fail=%d entered=%d %.1fs" % (
        idx, tag, len(questions), sum(1 for r in rows if r["pass"]),
        sum(1 for r in rows if not r["pass"]), len(inserted), latency / 1000.0))

    # ---- 机械可判定的停止条件
    if latency / 1000.0 > 300:
        stop("S7: 单次调用 > 300 秒（%s）" % tag)
    if lib.execute("select count(*) from ai_question where lifecycle_status='ACTIVE'").fetchone()[0]:
        stop("S3: 出现 ACTIVE")
    if lib.execute("select count(*) from question_event where event_type='REVIEW_APPROVED'").fetchone()[0]:
        stop("S3: 出现 REVIEW_APPROVED")
    for name, path in [("learning.db", os.path.join(BASE, "structured", "learning", "learning.db")),
                       ("contentpack", CP),
                       ("validator_v2", os.path.join(SPIKE, "20260917_1520_validator_fix", "validator_v2.py")),
                       ("validator_v3", os.path.join(VALIDATOR_DIR, "validator_v3.py"))]:
        if sha(open(path, "rb").read()) != protected_before[name]:
            stop("S5: 保护资产被修改：%s" % name)

live = sorted({r[0] for r in lib.execute("select distinct item_id from question_learning_object")})
dangling_lo = [i for i in live if i not in items_known]
live_b = sorted({r[0] for r in lib.execute("select distinct evidence_block_id from question_evidence")})
dangling_b = [b for b in live_b if b not in blocks_known]
if dangling_lo or dangling_b:
    stop("S4: 跨库悬空引用 %s %s" % (dangling_lo, dangling_b))

summary["protected_after"] = {name: sha(open(path, "rb").read())
                              for name, path in [("learning.db", os.path.join(BASE, "structured", "learning", "learning.db")),
                                                 ("contentpack", CP),
                                                 ("validator_v2", os.path.join(SPIKE, "20260917_1520_validator_fix", "validator_v2.py")),
                                                 ("validator_v3", os.path.join(VALIDATOR_DIR, "validator_v3.py"))]}
summary["protected_unchanged"] = summary["protected_after"] == protected_before
summary["total_latency_ms"] = sum(s.get("latency_ms", 0) for s in summary["sections"])
summary["total_generated"] = sum(s.get("generated", 0) for s in summary["sections"])
dump(os.path.join(HERE, "generation_summary.json"), summary)
cp.close()
lib.close()
print("完成：4 个非对照 Section 之外的汇总已写入 generation_summary.json")
