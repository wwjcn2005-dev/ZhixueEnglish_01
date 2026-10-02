# -*- coding: utf-8 -*-
"""P1-09-G: deterministic pre-screen rules for choice-item answer-uniqueness risk.

AI = 0. Read-only. Writes prescreen_result.json

Rules (fully deterministic, no scores, no percentages):
  R1 option duplicate / containment
  R2 two options share a lemma (inflection pair)
  R3 >=2 non-answer options share the answer's part of speech
  R4 R3 within a content-word slot (noun/verb/adj/adv)  [semantic-slot proxy]
  R5 textbook origin profile of the options
  R6 relation of each option to the evidence block
  R7 stem context length
"""

import json
import os
import re
import sqlite3
import sys

BASE = r"D:\ZhixueEnglish"
SPIKE = os.path.join(BASE, "audit", "AI_question_generation_spike")
LIB = os.path.join(BASE, "structured", "ai", "question_library.db")
CP = os.path.join(BASE, "structured", "contentpack", "v5", "FLTRP-EN-7A-2022CUR.sqlite")
P1_08_B = os.path.join(SPIKE, "P1_08_B_evidence_assembly_fix")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, P1_08_B)
import evidence_assembly as EA  # noqa: E402

WORD = re.compile(r"[A-Za-z][A-Za-z'\-]*")
ARTICLES = ("a ", "an ", "the ")
CONTENT_POS = {"n", "v", "adj", "adv"}


def ro(path):
    con = sqlite3.connect("file:" + path.replace("\\", "/") + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def norm_opt(text):
    s = (text or "").strip().lower()
    for a in ARTICLES:
        if s.startswith(a):
            s = s[len(a):]
    s = re.sub(r"[^a-z0-9' ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def lemma_keys(word):
    """Conservative base-form candidates (reverse direction of validator_v2._lemmas)."""
    w = norm_opt(word)
    keys = {w}
    for suf in ("ies", "es", "s", "ed", "ing"):
        if w.endswith(suf) and len(w) > len(suf) + 1:
            keys.add(w[: -len(suf)])
            keys.add(w[: -len(suf)] + "e")
    return keys


def load_context(cp):
    ccur = cp.cursor()
    vocab = {}
    for r in ccur.execute("SELECT item_id, lemma, part_of_speech FROM learning_item"
                          " WHERE item_type='vocabulary'").fetchall():
        lemma = (r["lemma"] or "").strip().lower()
        if lemma:
            vocab[lemma] = (r["part_of_speech"] or "").strip().lower()
    blocks = [(r["block_id"], r["page_id"], r["text_raw"] or "") for r in
              ccur.execute("SELECT block_id, page_id, text_raw FROM content_block").fetchall()]
    page_of = {r["page_id"]: r["pdf_page"] for r in
               ccur.execute("SELECT page_id, pdf_page FROM page").fetchall()}
    ranges = EA.section_page_ranges(cp)
    unit_pages = {}
    for sid, (a, b) in ranges.items():
        unit_pages.setdefault(sid.rsplit(":", 1)[0], set()).update(range(a, b + 1))
    all_words = set()
    for bid, pid, t in blocks:
        all_words |= {w.lower() for w in WORD.findall(t)}
    return {"vocab": vocab, "blocks": blocks, "page_of": page_of, "ranges": ranges,
            "unit_pages": unit_pages, "all_words": all_words,
            "sec_cache": {}, "unit_cache": {}}


def words_on(ctx, pages):
    out = set()
    for bid, pid, t in ctx["blocks"]:
        if ctx["page_of"].get(pid) in pages:
            out |= {w.lower() for w in WORD.findall(t)}
    return out


def sec_words(ctx, sid):
    if sid not in ctx["sec_cache"]:
        a, b = ctx["ranges"][sid]
        ctx["sec_cache"][sid] = words_on(ctx, set(range(a, b + 1)))
    return ctx["sec_cache"][sid]


def unit_words(ctx, sid):
    uid = sid.rsplit(":", 1)[0]
    if uid not in ctx["unit_cache"]:
        ctx["unit_cache"][uid] = words_on(ctx, ctx["unit_pages"][uid])
    return ctx["unit_cache"][uid]


def covers(word, text_words):
    return bool(lemma_keys(word) & text_words)


def load_items(lib):
    items = []
    for r in lib.execute("SELECT question_id, question_type, question_text, options_json,"
                         " correct_answer, section_id, activity_id, page, lifecycle_status"
                         " FROM ai_question WHERE question_type IN"
                         " ('vocab_choice','reading_choice') ORDER BY question_id"):
        ev = [dict(e) for e in lib.execute(
            "SELECT evidence_block_id, evidence_quote FROM question_evidence"
            " WHERE question_id=? ORDER BY ordinal", (r["question_id"],))]
        items.append({"question_id": r["question_id"], "question_type": r["question_type"],
                      "question": r["question_text"],
                      "options": json.loads(r["options_json"]),
                      "answer": r["correct_answer"], "section_id": r["section_id"],
                      "activity_id": r["activity_id"], "page": r["page"],
                      "lifecycle_status": r["lifecycle_status"],
                      "evidence_block_ids": [e["evidence_block_id"] for e in ev],
                      "evidence_quote": ev[0]["evidence_quote"] if ev else "",
                      "source": "question_library"})
    fx = json.load(open(os.path.join(SPIKE, "P1_09_D_boundary_validation", "fixtures.json"),
                        encoding="utf-8"))["fixtures"]
    # map the two known-risk fixtures to their real Sections (taken from their `location` field,
    # which is also part of the allowed review context - not gold information)
    fixture_section = {"FIX-C1": "FLTRP-EN-7A-2022CUR:U2:UNDERSTANDING_IDEAS",
                       "FIX-C2": "FLTRP-EN-7A-2022CUR:U1:UNDERSTANDING_IDEAS"}
    for f in fx:
        if f["fixture_id"] in ("FIX-C1", "FIX-C2"):
            items.append({"question_id": f["fixture_id"], "question_type": f["question_type"],
                          "question": f["question"], "options": f["options"],
                          "answer": f["answer"],
                          "section_id": fixture_section[f["fixture_id"]], "activity_id": None,
                          "page": f["textbook_context"][0]["textbook_page"],
                          "lifecycle_status": "FIXTURE",
                          "evidence_block_ids": [b["block_id"] for b in f["textbook_context"]],
                          "evidence_quote": f["textbook_context"][0]["text"],
                          "source": "P1-09-D fixture (known true second answer)"})
    return items


def apply_rules(it, ctx):
    opts, ans, sid = it["options"], it["answer"], it["section_id"]
    nopts = [norm_opt(o) for o in opts]
    ans_n = norm_opt(ans)
    others = [o for o in nopts if o != ans_n]
    rules = {}
    dup_pairs = [[opts[i], opts[j]] for i in range(len(nopts)) for j in range(i + 1, len(nopts))
                 if nopts[i] == nopts[j] or nopts[i] in nopts[j] or nopts[j] in nopts[i]]
    rules["R1_option_duplicate_or_containment"] = {"fired": bool(dup_pairs), "pairs": dup_pairs}
    pairs = []
    for i in range(len(nopts)):
        for j in range(i + 1, len(nopts)):
            key = lemma_keys(nopts[i]) & lemma_keys(nopts[j])
            if nopts[i] != nopts[j] and key and min(len(x) for x in key) >= 3:
                pairs.append([opts[i], opts[j], sorted(key)])
    rules["R2_same_lemma_pair"] = {"fired": bool(pairs), "pairs": pairs}
    ans_keys = lemma_keys(ans_n) & set(ctx["vocab"])
    ans_pos = ctx["vocab"].get(ans_n) or (ctx["vocab"][sorted(ans_keys)[0]] if ans_keys else "")
    same_pos = []
    for o in others:
        o_keys = lemma_keys(o) & set(ctx["vocab"])
        pos = ctx["vocab"].get(o) or (ctx["vocab"][sorted(o_keys)[0]] if o_keys else "")
        if pos and ans_pos and pos == ans_pos:
            same_pos.append(o)
    rules["R3_same_pos_parallel"] = {
        "fired": len(same_pos) >= 2, "answer_pos": ans_pos, "answer_pos_known": bool(ans_pos),
        "same_pos_options": same_pos, "count": len(same_pos),
        "pos_known_non_answer_options": sum(
            1 for o in others if (lemma_keys(o) & set(ctx["vocab"])))}
    rules["R4_content_slot_parallel"] = {
        "fired": bool(len(same_pos) >= 2 and ans_pos in CONTENT_POS),
        "answer_pos": ans_pos,
        "note": "R4 = 语义槽位相容性的确定性代理：空位是实词槽且至少两个同词性候选可入槽"}
    if sid:
        sec = sec_words(ctx, sid)
        uni = unit_words(ctx, sid)
        other_in_sec = [o for o in others if covers(o, sec)]
        rules["R5_textbook_origin"] = {
            "fired": len(other_in_sec) >= 2,
            "answer_in_section_text": covers(ans, sec),
            "options_in_section_text": [o for o in opts if covers(o, sec)],
            "non_answer_in_section_text": other_in_sec,
            "non_answer_in_unit_text": [o for o in others if covers(o, uni)],
            "non_answer_book_only": [o for o in others
                                     if covers(o, ctx["all_words"]) and not covers(o, sec)],
            "non_answer_in_vocabulary": [o for o in others
                                         if lemma_keys(o) & set(ctx["vocab"])],
            "note": "来自教材不等于正确；这里只刻画来源"}
    else:
        rules["R5_textbook_origin"] = {"fired": None, "note": "fixture 无 section 关联，跳过"}
    ev_ids = set(it["evidence_block_ids"])
    ev_blocks = [(bid, t) for bid, pid, t in ctx["blocks"] if bid in ev_ids]
    def phrase_in(text, phrase):
        """Match the whole option phrase (normalised), not just its first word."""
        p = re.sub(r"\s+", " ", phrase).strip()
        if not p:
            return False
        return re.search(r"\b" + re.escape(p) + r"\b", re.sub(r"\s+", " ", text), re.I) is not None
    in_ev = [o for o in others if any(phrase_in(t, o) for bid, t in ev_blocks)]
    rules["R6_evidence_relation"] = {
        "fired": len(in_ev) >= 1, "answer_in_evidence": ans_n in (it["evidence_quote"] or "").lower(),
        "non_answer_in_evidence": in_ev, "non_answer_count_in_evidence": len(in_ev),
        "note": "非答案选项也出现在证据块内 → 语境相邻，提高风险信号"}
    stem = re.sub(r"_{2,}", " ", it["question"] or "")
    stem_words = WORD.findall(stem)
    rules["R7_stem_context_length"] = {
        "fired": len(stem_words) < 6, "stem_word_count": len(stem_words),
        "note": "短题干 → 语境不足以排除其他候选（仅风险信号）"}
    fired = [k for k, v in rules.items() if v.get("fired")]
    return {"question_id": it["question_id"], "question_type": it["question_type"],
            "lifecycle_status": it["lifecycle_status"], "source": it["source"],
            "question": it["question"], "options": opts, "answer": ans,
            "rules": rules, "fired_rules": fired,
            "state": "AI_REVIEW_CANDIDATE" if fired else "NO_AI_SIGNAL"}


def main():
    lib, cp = ro(LIB), ro(CP)
    ctx = load_context(cp)
    items = [apply_rules(it, ctx) for it in load_items(lib)]
    result = {"stage": "P1-09-G", "ai_calls": 0,
              "rules_definition": {
                  "R1": "选项重复或互相包含（归一化去冠词/标点后）",
                  "R2": "两个选项共享同一词元（词形变化对）",
                  "R3": ">=2 个非答案选项与答案同词性（同词性不等于多答案）",
                  "R4": "R3 且空位为实词槽（语义槽位相容性的确定性代理）",
                  "R5": "选项教材来源刻画（词表 / Section / Unit / 全书）",
                  "R6": "选项与证据块的关系（是否与答案同处证据块）",
                  "R7": "题干上下文长度（少于 6 词视为短上下文）"},
              "items": items}
    with open(os.path.join(HERE, "prescreen_result.json"), "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    for it in items:
        print("%-20s %-14s %-13s %-20s fired=%s"
              % (it["question_id"], it["question_type"], it["lifecycle_status"], it["state"],
                 ",".join(r.split("_")[0] for r in it["fired_rules"]) or "-"))
        for k in ("R1_option_duplicate_or_containment", "R2_same_lemma_pair",
                  "R3_same_pos_parallel", "R4_content_slot_parallel", "R5_textbook_origin",
                  "R6_evidence_relation", "R7_stem_context_length"):
            v = it["rules"][k]
            detail = {kk: vv for kk, vv in v.items() if kk not in ("fired", "note")}
            print("     %-34s fired=%-5s %s" % (k, v.get("fired"), detail))
    lib.close()
    cp.close()


if __name__ == "__main__":
    main()
