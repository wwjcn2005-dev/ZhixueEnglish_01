"""P1-07 · 入库前确定性判定（只读 fixture + 只读 question_library.db）。

五道闸门：证据完整性 / 教材原题识别 / 机械复现 / deterministic dedupe / schema-provenance
两个已确认口径：D2（reading_judge 豁免规则 4）、D3（词形归一化后再判越界）
一个完整性规则：D4（题干残缺 → EVIDENCE_INCOMPLETE）

输出 candidate_decision.json。**不写正式数据库。**
"""
import hashlib
import json
import os
import re
import sqlite3
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = r"D:\ZhixueEnglish"
SPIKE = os.path.join(BASE, "audit", "AI_question_generation_spike")
D6 = os.path.join(SPIKE, "P1_06_batch_stability")
RUNS = os.path.join(SPIKE, "P1_05_real_validation", "runs")
LIB = os.path.join(BASE, "structured", "ai", "question_library.db")
CP = os.path.join(BASE, "structured", "contentpack", "v5", "FLTRP-EN-7A-2022CUR.sqlite")
EVID = os.path.join(BASE, "structured", "ai", "textbook_evidence_map_v1.json")
sys.path.insert(0, os.path.join(SPIKE, "P1_04_rule_fixes"))
import validator_v3 as V3  # noqa: E402
_lemmas = V3._v2._lemmas          # v2 的词元归一化工具（validator_v3 未直接转出）

CTX = {"S1": "01_Unit2_UNDERSTANDING_IDEAS_context.json",
       "S2": "03_Unit1_UNDERSTANDING_IDEAS_context.json",
       "S3": "04_Unit5_UNDERSTANDING_IDEAS_context.json",
       "S4": "05_Starter_GET_READY_context.json"}
FUNC = V3.FUNC
SENT_END = (".", "!", "?", "\u201d", "\u2019")


def sha(b):
    return hashlib.sha256(b).hexdigest().upper()


def norm(s):
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


def toks(s):
    return V3.tokens(s)


def dedupe_key(section, activity, qtype, answer, blocks):
    return sha("\x01".join([section or "", activity or "", qtype or "", norm(answer),
                            "|".join(sorted(blocks or []))]).encode())


def fingerprint(section, activity, qtype, question, quote):
    """与 P1-02/P1-03 完全一致的 question_fingerprint 公式。"""
    return sha("\x01".join([section, activity or "", qtype or "",
                            " ".join(toks(question)), " ".join(toks(quote))]).encode())


def gap_in_run(stem, src_tokens, max_gap=3):
    """题干（去掉 ___）在 src_tokens 中是否为「只隔一个 空位/少量 token」的连续片段。"""
    st = toks(stem.replace("___", " "))
    n = len(st)
    if n == 0 or len(src_tokens) < n:
        return None
    for i in range(0, len(src_tokens) - n + 1):
        j = 0
        k = i
        ok = True
        gap = 0
        while j < n and k < len(src_tokens):
            if src_tokens[k] == st[j]:
                j += 1
                k += 1
            else:
                gap += 1
                k += 1
                if gap > max_gap:
                    ok = False
                    break
        if ok and j == n and gap <= max_gap:
            return {"start": i, "gap": gap}
    return None


def align_gap1(stem, src_tokens):
    """严格对齐：题干（去掉 ___）与 src 只差 **恰好一个被跳过的 token**；返回该 token。

    用于“复现教材练习空位”的判定：教材练习的空位在文本里就是一个编号 token（如 "1"、"2"）。
    """
    st = toks(stem.replace("___", " "))
    n = len(st)
    if n == 0 or len(src_tokens) < n + 1:
        return None
    for i in range(0, len(src_tokens) - n):
        skipped = src_tokens[i + n] if False else None
        j = 0
        k = i
        skip = []
        while j < n and k < len(src_tokens):
            if src_tokens[k] == st[j]:
                j += 1
                k += 1
            else:
                skip.append(src_tokens[k])
                k += 1
                if len(skip) > 1:
                    break
        if j == n and len(skip) == 1:
            return skip[0]
    return None


def last_token(text):
    t = toks(text)
    return t[-1] if t else None


def ends_with_sentence_punct(text):
    s = (text or "").rstrip()
    return bool(s) and s.endswith(SENT_END)


def lexeme_ok(token, allow):
    """D3：词形归一化后再判越界。"""
    if token in allow:
        return True
    cands = set(_lemmas(token))
    cands.add(token + "s")
    cands.add(token + "es")
    if token.endswith("s"):
        cands.add(token[:-1])
    return any(c in allow for c in cands)


def judge_support(stem, quote, answer):
    """D2：reading_judge 的事实一致性判定（确定性近似）。"""
    s = [w for w in toks(stem) if w not in FUNC]
    q = set(toks(quote))
    if not s:
        return False, 0.0, "stem 无内容词"
    cover = sum(1 for w in s if w in q or any(l in q for l in _lemmas(w))) / len(s)
    neg = {"not", "no", "never", "isn't", "aren't", "don't", "doesn't"}
    a = str(answer).strip().lower()
    stem_neg = bool(neg & set(toks(stem)))
    quote_neg = bool(neg & set(toks(quote)))
    if a in ("true", "t", "yes"):
        return cover >= 0.75, cover, "True：题干内容词覆盖率 %.2f" % cover
    if a in ("false", "f", "no"):
        ok = cover >= 0.5 and (stem_neg != quote_neg)
        return ok, cover, ("False：覆盖率 %.2f，否定词 stem=%s quote=%s"
                           % (cover, stem_neg, quote_neg))
    return False, cover, "未知布尔答案"


def main():
    conn = sqlite3.connect("file:" + LIB + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    lib_keys = {}
    for r in conn.execute("select question_id, section_id, activity_id, question_type, "
                          "correct_answer from ai_question"):
        bs = [x[0] for x in conn.execute(
            "select evidence_block_id from question_evidence where question_id=?",
            (r["question_id"],))]
        lib_keys[dedupe_key(r["section_id"], r["activity_id"], r["question_type"],
                            r["correct_answer"], bs)] = r["question_id"]
    lib_fps = {r[0] for r in conn.execute("select question_fingerprint from ai_question")}
    lib_snapshot = {"counts": {}, "sha256": sha(open(LIB, "rb").read())}
    for t in ["generation_run", "ai_question", "question_evidence", "question_learning_object",
              "question_validation", "question_event"]:
        lib_snapshot["counts"][t] = conn.execute("select count(*) from %s" % t).fetchone()[0]
    conn.close()

    c = sqlite3.connect("file:" + CP + "?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    cp_text_tokens = {}          # pdf_page -> tokens（D3 的“教材正文”基准，比 context 更完整）
    for r in c.execute("select p.pdf_page as pg, b.text_raw as t from content_block b "
                       "join page p on p.page_id=b.page_id"):
        cp_text_tokens.setdefault(r["pg"], set()).update(toks(r["t"] or ""))
    vocab_words = {}
    for r in c.execute("select item_id, surface_form from learning_item "
                       "where item_type='vocabulary'"):
        head = (r["surface_form"] or "").strip().split("/", 1)[0].strip().lower()
        if head:
            vocab_words.setdefault(head, r["item_id"])
    item_ids = {r[0] for r in c.execute("select item_id from learning_item")}
    block_ids = {r[0] for r in c.execute("select block_id from content_block")}
    unit_ids = {r[0] for r in c.execute("select unit_id from unit")}
    ex_of_act = {}
    for r in c.execute("select li.item_id, sr.source_id from learning_item li "
                       "join source_ref sr on sr.item_id=li.item_id where li.item_type='exercise'"):
        ex_of_act.setdefault(r["source_id"], r["item_id"])
    c.close()

    evidence_map = json.load(open(EVID, encoding="utf-8"))
    pkgs = {}
    for p in evidence_map["packages"]:
        pkgs.setdefault((p["scope"]["unit"], p["scope"]["section"]), []).append(p)

    rows = []
    seen_batch = {}
    for tag, cf in CTX.items():
        ctx = json.load(open(os.path.join(RUNS, cf), encoding="utf-8"))
        pa = json.load(open(os.path.join(D6, "%s_request.json" % tag), encoding="utf-8"))
        sid = ctx["textbook_position"]["section_id"]
        unit_id = sid.rsplit(":", 1)[0]
        section_pages = set(ctx["textbook_position"]["textbook_pages"])
        act_map = {a["activity_no"]: a for a in ctx["activity_instructions"]}
        blk = {b["block_id"]: b["text"] for b in ctx["textbook_blocks"]}
        allow = V3.build_whitelist(ctx)
        unit_vocab = {v["word"].lower() for v in ctx["unit_vocabulary"]}
        section_pkgs = pkgs.get((ctx["textbook_position"]["unit"],
                                 ctx["textbook_position"]["section"]), [])
        qs = json.load(open(os.path.join(D6, "%s_parsed.json" % tag), encoding="utf-8")) \
            .get("questions") or []
        cp_allow = set()
        for pg in section_pages:
            cp_allow |= cp_text_tokens.get(pg + 5, set())
        for i, q in enumerate(qs, 1):
            src = "%s-Q%d" % (tag, i)
            qtype = str(q.get("type") or "")
            act_no = q.get("activity")
            activity_id = ("%s:A%s" % (sid, act_no)) if act_no is not None else None
            ids = q.get("evidence_block_ids") or []
            quote = q.get("evidence_quote") or ""
            answer = str(q.get("answer") or "")
            checks = {}
            reasons = []

            # ---------- Gate 1 证据完整性
            g1 = {}
            g1["page"] = q.get("page") in section_pages
            g1["activity"] = act_no in act_map
            g1["blocks_exist"] = bool(ids) and all(b in blk for b in ids)
            g1["block_in_contentpack"] = bool(ids) and all(b in block_ids for b in ids)
            g1["quote_nonempty"] = bool(quote.strip())
            g1["quote_in_block"] = any(
                " ".join(toks(quote)) and " ".join(toks(quote)) in " ".join(toks(blk[b]))
                for b in ids if b in blk)
            # answer support（D2：judge 豁免规则 4）
            if qtype == "reading_judge":
                sup_ok, cover, sup_note = judge_support(q.get("question") or "", quote, answer)
                support_type = "JUDGE_FACT_OK" if sup_ok else "JUDGE_FACT_FAIL"
                rule4_waived = True
            else:
                support_type = V3.answer_support(answer, quote, q.get("question") or "")
                sup_ok = support_type in ("EXACT", "VERIFIABLE_REFERENCE", "VERIFIABLE_REPHRASE")
                cover, sup_note, rule4_waived = None, "", False
            g1["answer_supported"] = sup_ok
            # D4 题干残缺
            truncated_mark = ("..." in (q.get("question") or "")) or ("\u2026" in (q.get("question") or ""))
            # D4 规则②：题干尾部与证据块尾部alike、且该 block 无句末标点 → 题干是被截断的碎片
            block_ends_abruptly = False
            stem_last = last_token(q.get("question") or "")
            for b in ids:
                if b in blk and not ends_with_sentence_punct(blk[b]) \
                        and last_token(blk[b]) == stem_last:
                    block_ends_abruptly = True
                    break
            g1["stem_complete"] = not (truncated_mark or block_ends_abruptly)
            checks["gate1_evidence_complete"] = all(g1.values())
            if not g1["stem_complete"]:
                reasons.append("题干残缺（省略号=%s / 证据块无句末标点=%s）"
                               % (truncated_mark, block_ends_abruptly))
            if not g1["answer_supported"]:
                reasons.append("答案不被引用支持（%s %s）" % (support_type, sup_note))

            # ---------- Gate 2 教材原题识别（严格：题干恰好跳过教材练习的编号空位 token）
            orig_hits = []
            for p in section_pkgs:
                # 只有当题目与该教材练习属于**同一个 activity** 时才可能是“复现该练习的空位”
                if p["scope"].get("activity_no") != act_no:
                    continue
                pt = toks((p.get("original_question") or {}).get("text") or "")
                if not pt:
                    continue
                skipped = align_gap1(q.get("question") or "", pt)
                if skipped and skipped.isdigit() and len(skipped) <= 2:
                    orig_hits.append({"package": p.get("question_id"),
                                      "activity_no": p["scope"].get("activity_no"),
                                      "skipped_blank_marker": skipped})
            checks["gate2_not_textbook_original"] = not orig_hits
            if orig_hits:
                reasons.append("与教材练习空位逐字重合：%s" % orig_hits[:2])

            # ---------- Gate 3 机械复现
            mech = False
            for b in ids:
                if b in blk and gap_in_run(q.get("question") or "", toks(blk[b]), max_gap=3):
                    mech = True
                    break
            head_phrase = " ".join(answer.lower().split()[:2])
            answer_is_learning_point = bool(
                answer.lower() in unit_vocab or head_phrase in unit_vocab
                or answer.lower().strip() in vocab_words
                or qtype.startswith("reading"))
            gate3_ok = (not mech) or answer_is_learning_point
            checks["gate3_mechanical_allowed"] = gate3_ok
            if mech and not answer_is_learning_point:
                reasons.append("机械复现且答案不是明确学习点")

            # ---------- Gate 4 dedupe
            dk = dedupe_key(sid, activity_id, qtype, answer, ids)
            fp = fingerprint(sid, activity_id, qtype, q.get("question") or "", quote)
            dup_of = None
            if dk in seen_batch:
                dup_of = "batch:%s" % seen_batch[dk]
            elif dk in lib_keys:
                dup_of = "library:%s" % lib_keys[dk]
            elif fp in lib_fps:
                dup_of = "library_fingerprint"
            checks["gate4_no_duplicate"] = dup_of is None
            if dup_of:
                reasons.append("重复候选：%s" % dup_of)
            seen_batch.setdefault(dk, src)

            # ---------- Gate 5 schema / provenance
            g5 = {"unit_id_exists": unit_id in unit_ids,
                  "activity_lo_exists": bool(ex_of_act.get(activity_id)),
                  "run_meta_available": bool(pa.get("context_sha256") and pa.get("system_prompt_sha256")),
                  "model_ok": pa.get("payload", {}).get("model") == "deepseek-v4-pro",
                  "prompt_version_ok": pa.get("prompt_version") == "P1-05-v3"}
            checks["gate5_schema_provenance"] = all(g5.values())
            if not all(g5.values()):
                reasons.append("provenance 缺失：%s" % [k for k, v in g5.items() if not v])

            # ---------- D3 词汇边界（词形归一化后再判）
            allow_d3 = set(allow) | cp_allow | {w for v in ctx["unit_vocabulary"]
                                                for w in toks(v["word"])}
            raw_oos = V3.out_of_scope(V3.checked_language(q), allow)
            real_oos = [t for t in raw_oos if not lexeme_ok(t, allow_d3)]
            checks["d3_vocab_after_lemma"] = not real_oos
            if real_oos:
                reasons.append("教材外词汇：%s" % real_oos)

            # ---------- 决策
            if not checks["gate1_evidence_complete"]:
                decision = "EVIDENCE_INCOMPLETE"
            elif not checks["gate4_no_duplicate"]:
                decision = "DUPLICATE_CANDIDATE"
            elif not checks["gate2_not_textbook_original"]:
                decision = "ORIGINAL_TEXTBOOK"
            elif not checks["gate3_mechanical_allowed"]:
                decision = "MECHANICAL_REPRODUCTION"
            elif not (checks["gate5_schema_provenance"] and checks["d3_vocab_after_lemma"]):
                decision = "NEEDS_REVIEW"
            else:
                decision = "PASS"

            # LearningObject 映射（短语优先）
            lo_items = []
            ans_low = answer.lower().strip()
            for w, iid in vocab_words.items():
                if w and (ans_low == w or ans_low.startswith(w + " ") or ans_low in w):
                    lo_items.append((w, iid))
            lo_items.sort(key=lambda x: -len(x[0]))
            primary = lo_items[0][1] if lo_items else ex_of_act.get(activity_id)
            objs = []
            if primary:
                objs.append((primary, 1))
            ex = ex_of_act.get(activity_id)
            if ex and ex != primary:
                objs.append((ex, 0))

            rows.append({
                "source_section": tag, "section_id": sid, "unit_id": unit_id,
                "source_question_id": q.get("question_id"), "source_row": src,
                "derived_question_id": "AIQ:" + fp[:12],
                "question_fingerprint": fp, "dedupe_key": dk,
                "decision": decision, "reasons": reasons,
                "gate_results": {**{"g1_" + k: v for k, v in g1.items()},
                                 **{k: v for k, v in checks.items()},
                                 "gate5_detail": g5},
                "mechanical_rewrite": mech, "original_textbook": bool(orig_hits),
                "evidence_status": "OK" if checks["gate1_evidence_complete"] else "INCOMPLETE",
                "vocabulary_status": "OK" if checks["d3_vocab_after_lemma"] else "OUT_OF_TEXTBOOK",
                "vocabulary_raw_flags": raw_oos, "vocabulary_after_lemma": real_oos,
                "answer_support_type": support_type, "rule4_waived_for_judge": rule4_waived,
                "judge_coverage": cover,
                "type": qtype, "answer": answer, "question": q.get("question"),
                "options": q.get("options") or None,
                "correct_option": q.get("correct_option") or None,
                "difficulty": q.get("difficulty"), "explanation": q.get("explanation"),
                "page": q.get("page"), "activity_id": activity_id,
                "blocks": ids, "quote": quote,
                "learning_objects": [{"item_id": i, "is_primary": p} for i, p in objs],
                "context_hash": pa.get("context_sha256"),
                "prompt_version": pa.get("prompt_version"),
                "model": pa.get("payload", {}).get("model"),
            })

    counts = Counter(r["decision"] for r in rows)
    doc = {"stage": "P1-07", "mode": "candidate_decision", "ai_calls": 0,
           "fixture_files": {t: os.path.relpath(os.path.join(D6, "%s_parsed.json" % t), BASE)
                             for t in CTX},
           "library_snapshot_before": lib_snapshot,
           "gate_definitions": {
               "gate1": "page/activity/block/quote 可追溯 + answer 被引用支持 + 题干完整(D4)",
               "gate2": "与教材练习文本按 token 连续片段比对（空位附近含编号标记）→ ORIGINAL_TEXTBOOK",
               "gate3": "题干为引用 block 的连续片段（含空位）→ mechanical_rewrite=true；"
                        "若答案不是明确学习点则 MECHANICAL_REPRODUCTION",
               "gate4": "dedupe_key=sha256(section×activity×type×norm_answer×block set)；"
                        "并检查 question_fingerprint",
               "gate5": "unit_id / activity LO / run 元数据 / model / prompt_version",
               "d2": "reading_judge 豁免规则 4，改用事实一致性判定（rule4_waived_for_judge）",
               "d3": "越界 token 先做词形归一化，再判是否教材内合法词形",
               "d4": "题干含省略号，或引用 block 无句末标点 → EVIDENCE_INCOMPLETE",
           },
           "decision_counts": dict(counts),
           "candidates": rows}
    with open(os.path.join(HERE, "candidate_decision.json"), "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
    print("已生成 candidate_decision.json")
    print("决策分布:", dict(counts))
    for r in rows:
        print("  %-8s %-18s mech=%-5s orig=%-5s %s" % (
            r["source_row"], r["decision"], r["mechanical_rewrite"],
            r["original_textbook"], "; ".join(r["reasons"])[:90]))


if __name__ == "__main__":
    main()
