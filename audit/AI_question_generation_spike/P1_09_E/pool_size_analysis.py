# -*- coding: utf-8 -*-
"""P1-09-E: pool size vs coverage for four candidate-pool strategies (no AI calls).

Strategies: P1 vocabulary(BOLD, Section) / P2 same-slot substitution / P3 Section text words /
P4 book text words. Writes pool_size_analysis.json
"""

import collections
import json
import os
import re
import sqlite3

BASE = r"D:\ZhixueEnglish"
SPIKE = os.path.join(BASE, "audit", "AI_question_generation_spike")
CP = os.path.join(BASE, "structured", "contentpack", "v5", "FLTRP-EN-7A-2022CUR.sqlite")
HERE = os.path.dirname(os.path.abspath(__file__))
WORD = re.compile(r"[A-Za-z][A-Za-z'\-]*")
U2 = "FLTRP-EN-7A-2022CUR:U2:UNDERSTANDING_IDEAS"
U1 = "FLTRP-EN-7A-2022CUR:U1:UNDERSTANDING_IDEAS"
RANGES = {U2: (37, 41), U1: (21, 25)}


def main():
    cp = sqlite3.connect("file:" + CP.replace("\\", "/") + "?mode=ro", uri=True)
    cp.row_factory = sqlite3.Row
    cur = cp.cursor()

    vocab = {}
    for r in cur.execute("SELECT item_id, lemma, part_of_speech FROM learning_item"
                         " WHERE item_type='vocabulary'").fetchall():
        lemma = (r["lemma"] or "").strip().lower()
        if lemma:
            vocab[lemma] = (r["part_of_speech"] or "").strip().lower()
    bold = {r[0] for r in cp.execute(
        "SELECT DISTINCT item_id FROM source_ref WHERE textbook_emphasis='BOLD'")}
    bold_lemmas = {lemma for lemma in vocab
                   if any(r[0] in bold for r in cp.execute(
                       "SELECT item_id FROM learning_item WHERE lower(lemma)=?", (lemma,)))}

    blocks = [(r["block_id"], r["page_id"], r["text_raw"] or "") for r in
              cur.execute("SELECT block_id, page_id, text_raw FROM content_block").fetchall()]
    page_of = {r["page_id"]: r["pdf_page"] for r in
               cur.execute("SELECT page_id, pdf_page FROM page").fetchall()}

    def words(pages):
        out = set()
        for bid, pid, t in blocks:
            if page_of.get(pid) in pages:
                out |= {w.lower() for w in WORD.findall(t)}
        return out

    sec_words = {s: words(set(range(a, b + 1))) for s, (a, b) in RANGES.items()}
    all_words = words(set(page_of.values()))

    def slot_pool(pattern):
        rx = re.compile(pattern, re.I)
        out = collections.Counter()
        for bid, pid, t in blocks:
            for m in rx.finditer(t):
                out[m.group(1).lower()] += 1
        return out

    cases = {
        "FIX-C1": {"answer": "friends", "alt": "students",
                   "pos": vocab.get("friends", ""), "section": U2,
                   "slot": r"with his ([a-z]+)"},
        "FIX-C2": {"answer": "sentence", "alt": "word",
                   "pos": vocab.get("sentence", ""), "section": U1,
                   "slot": r"a ([a-z]+) on the blackboard"},
    }
    rows = {}
    for fid, c in cases.items():
        sec = c["section"]
        pos = c["pos"]
        p1 = sorted(l for l in bold_lemmas
                    if pos and vocab.get(l) == pos and l != c["answer"])
        p2 = slot_pool(c["slot"])
        p3 = sorted(w for w in sec_words[sec] if w != c["answer"])
        p4 = sorted(w for w in all_words if w != c["answer"])
        rows[fid] = {
            "answer": c["answer"], "designed_alternative": c["alt"],
            "answer_pos_in_vocabulary": pos or None,
            "P1_vocabulary_BOLD_pos": {"pool_size": len(p1), "covers_alt": c["alt"] in p1,
                                       "sample": p1[:15]},
            "P2_same_slot": {"pool_size": len(p2), "covers_alt": c["alt"] in p2,
                             "sample": [w for w, _ in p2.most_common(15)]},
            "P3_section_text": {"pool_size": len(p3), "covers_alt": c["alt"] in p3,
                                "pos_known_share": round(
                                    sum(1 for w in p3 if vocab.get(w)) / max(len(p3), 1), 3)},
            "P4_book_text": {"pool_size": len(p4), "covers_alt": c["alt"] in p4,
                             "pos_known_share": round(
                                 sum(1 for w in p4 if vocab.get(w)) / max(len(p4), 1), 3)},
        }

    # per question-type pool size reference, using the 15 P1-09-D fixtures
    fx = json.load(open(os.path.join(SPIKE, "P1_09_D_boundary_validation", "fixtures.json"),
                        encoding="utf-8"))["fixtures"]
    by_type = {}
    for f in fx:
        by_type.setdefault(f["question_type"], []).append(f["fixture_id"])
    summary = {
        "vocabulary_items": len(vocab), "vocabulary_with_pos": sum(1 for v in vocab.values() if v),
        "book_distinct_words": len(all_words),
        "book_words_with_pos": sum(1 for w in all_words if vocab.get(w)),
        "book_pos_known_share": round(sum(1 for w in all_words if vocab.get(w)) / len(all_words), 3),
        "pos_source_gap": "正式数据里只有教材词表（288 条）带词性；教材正文中其余 87% 的词没有词性。",
        "fixtures_by_question_type": {k: len(v) for k, v in by_type.items()},
    }
    out = {"stage": "P1-09-E", "ai_calls": 0, "summary": summary, "cases": rows}
    with open(os.path.join(HERE, "pool_size_analysis.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print()
    for fid, r in rows.items():
        print("==", fid, "answer:", r["answer"], "| designed alternative:", r["designed_alternative"],
              "| answer POS:", r["answer_pos_in_vocabulary"])
        for k in ("P1_vocabulary_BOLD_pos", "P2_same_slot", "P3_section_text", "P4_book_text"):
            v = r[k]
            extra = (" pos_known=%s" % v["pos_known_share"]) if "pos_known_share" in v else ""
            print("   %-22s size=%-6d covers_alt=%-5s%s sample=%s"
                  % (k, v["pool_size"], v["covers_alt"], extra,
                     str(v.get("sample"))[:60]))
    cp.close()


if __name__ == "__main__":
    main()
