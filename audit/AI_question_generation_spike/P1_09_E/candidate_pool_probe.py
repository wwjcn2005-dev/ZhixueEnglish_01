# -*- coding: utf-8 -*-
"""P1-09-E: build candidate-answer pools offline and check coverage.

AI calls = 0. Read-only on contentpack. Writes candidate_pool_probe.json.
Scopes: SECTION text / UNIT text / BOOK text. Filters: POS match when POS is known.
"""

import json
import os
import re
import sqlite3
import sys

BASE = r"D:\ZhixueEnglish"
SPIKE = os.path.join(BASE, "audit", "AI_question_generation_spike")
CP = os.path.join(BASE, "structured", "contentpack", "v5", "FLTRP-EN-7A-2022CUR.sqlite")
P1_08_B = os.path.join(SPIKE, "P1_08_B_evidence_assembly_fix")
sys.path.insert(0, P1_08_B)
import evidence_assembly as EA  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
WORD = re.compile(r"[A-Za-z][A-Za-z'\-]*")

# P1-09-D fixtures: id -> (scope section_id, answer, designed alternative(s))
CASES = {
    "FIX-C1": ("FLTRP-EN-7A-2022CUR:U2:UNDERSTANDING_IDEAS", "friends",
               ["students", "grandpa", "teachers"]),
    "FIX-C2": ("FLTRP-EN-7A-2022CUR:U1:UNDERSTANDING_IDEAS", "sentence", ["word", "name"]),
}
GOLD_ALT = {"FIX-C1": "students", "FIX-C2": "word"}


def ro(path):
    con = sqlite3.connect("file:" + path.replace("\\", "/") + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def forms(lemma):
    """Rule-based surface forms of a lemma (candidate generation, not normalisation)."""
    w = lemma.lower()
    out = {w}
    if w.endswith("y") and len(w) > 2 and w[-2] not in "aeiou":
        out.add(w[:-1] + "ies")
    if w.endswith(("s", "x", "z", "ch", "sh")):
        out.add(w + "es")
    out.add(w + "s")
    if w.endswith("e"):
        out.add(w + "d")
        out.add(w[:-1] + "ing")
    else:
        out.add(w + "ed")
        out.add(w + "ing")
    if w.endswith("e"):
        out.add(w + "s")
    return sorted(out)


def main():
    cp = ro(CP)
    cur = cp.cursor()

    vocab = {}
    rows = cur.execute("""
            SELECT i.item_id, i.item_type, i.lemma, i.surface_form, i.part_of_speech,
                   i.learning_requirement
            FROM learning_item i WHERE i.item_type='vocabulary'""").fetchall()
    cur2 = cp.cursor()
    for r in rows:
        bold = cur2.execute(
            "SELECT COUNT(*) FROM source_ref WHERE item_id=? AND textbook_emphasis='BOLD'",
            (r["item_id"],)).fetchone()[0] > 0
        lemma = (r["lemma"] or "").strip().lower()
        if not lemma:
            continue
        vocab[lemma] = {"pos": (r["part_of_speech"] or "").strip().lower(), "bold": bold,
                        "requirement": r["learning_requirement"], "item_id": r["item_id"]}
    phrases = {}
    for r in cur.execute("SELECT lemma, surface_form FROM learning_item WHERE item_type='phrase'"):
        phrases[(r["lemma"] or "").strip().lower()] = r["surface_form"]
    patterns = [r[0] for r in cur.execute(
        "SELECT surface_form FROM learning_item WHERE item_type='sentence_pattern'")]

    blocks = [(r["block_id"], r["page_id"], r["text_raw"] or "") for r in cur.execute(
        "SELECT block_id, page_id, text_raw FROM content_block")]
    page_of = {r["page_id"]: r["pdf_page"] for r in cur.execute(
        "SELECT page_id, pdf_page FROM page")}
    section_of_page = {}
    for sid, (a, b) in EA.section_page_ranges(cp).items():
        for p in range(a, b + 1):
            section_of_page.setdefault(p, sid)
    unit_of_section = {sid: sid.rsplit(":", 1)[0] for sid in
                       set(section_of_page.values())}
    unit_pages = {}
    for sid, uid in unit_of_section.items():
        unit_pages.setdefault(uid, set()).update(
            p for p, s in section_of_page.items() if s == sid)

    def words_in(pred):
        out = {}
        for bid, pid, text in blocks:
            if not pred(page_of.get(pid)):
                continue
            for w in WORD.findall(text):
                out.setdefault(w.lower(), set()).add(bid)
        return out

    book_words = words_in(lambda p: True)
    section_words = {s: words_in(lambda p, s=s: section_of_page.get(p) == s)
                     for s in set(section_of_page.values())}
    unit_words = {u: words_in(lambda p, u=u: p in unit_pages[u]) for u in unit_pages}

    book_lemmas = {}
    for w in book_words:
        book_lemmas.setdefault(w, set()).add(w)
        for f in forms(w):
            book_lemmas.setdefault(w, set()).add(f)

    def pool(section_id, answer, scope):
        uid = section_id.rsplit(":", 1)[0]
        src = {"SECTION": section_words.get(section_id, {}),
               "UNIT": unit_words.get(uid, {}),
               "BOOK": book_words}[scope]
        ans_lemma = answer.lower()
        ans_pos = vocab.get(ans_lemma, {}).get("pos", "")
        cand = {}
        for w in src:
            base = w
            v = vocab.get(base)
            if ans_pos and v and v["pos"] and v["pos"] != ans_pos:
                continue
            cand[w] = {"pos": v["pos"] if v else "", "bold": v["bold"] if v else False,
                       "pos_known": bool(v and v["pos"]), "in_vocab": bool(v)}
        # vocabulary-driven candidates with inflection forms
        for lemma, v in vocab.items():
            if ans_pos and v["pos"] and v["pos"] != ans_pos:
                continue
            for f in forms(lemma):
                cand.setdefault(f, {"pos": v["pos"], "bold": v["bold"], "pos_known": True,
                                    "in_vocab": True})
        cand.pop(ans_lemma, None)
        for f in forms(ans_lemma):
            cand.pop(f, None)
        return cand, ans_pos

    out = {"stage": "P1-09-E", "ai_calls": 0,
           "vocab_size": len(vocab), "vocab_with_pos": sum(1 for v in vocab.values() if v["pos"]),
           "phrase_count": len(phrases), "sentence_pattern_count": len(patterns),
           "book_distinct_words": len(book_words),
           "book_distinct_words_with_pos": sum(1 for w in book_words if vocab.get(w, {}).get("pos")),
           "cases": {}, "pool_size_by_type": {}}

    for fid, (sid, ans, alts) in CASES.items():
        row = {"fixture_id": fid, "section_id": sid, "stored_answer": ans,
               "designed_alternatives": alts, "scopes": {}}
        for scope in ("SECTION", "UNIT", "BOOK"):
            p, ans_pos = pool(sid, ans, scope)
            hits = {a: (a.lower() in p or any(f in p for f in forms(a))) for a in alts}
            detail = {}
            for a in alts:
                key = a.lower() if a.lower() in p else next(
                    (f for f in forms(a) if f in p), None)
                detail[a] = {"in_pool": bool(key), "matched_surface": key,
                             "in_section_text": a.lower() in section_words.get(sid, {}),
                             "in_unit_text": a.lower() in unit_words.get(
                                 sid.rsplit(":", 1)[0], {}),
                             "in_book_text": a.lower() in book_words,
                             "in_vocabulary": a.lower() in vocab,
                             "vocab_pos": vocab.get(a.lower(), {}).get("pos", ""),
                             "bold": vocab.get(a.lower(), {}).get("bold", False)}
            row["scopes"][scope] = {"answer_pos": ans_pos, "pool_size": len(p),
                                    "alternative_hits": hits, "detail": detail}
        row["gold_alternative"] = GOLD_ALT[fid]
        out["cases"][fid] = row

    # pool size statistics for the 15 P1-09-D fixtures (using each fixture's own answer)
    fx = json.load(open(os.path.join(SPIKE, "P1_09_D_boundary_validation", "fixtures.json"),
                        encoding="utf-8"))["fixtures"]
    sizes = {}
    for f in fx:
        sid = f["location"] and None
        sizes.setdefault(f["question_type"], []).append(
            {"fixture_id": f["fixture_id"],
             "answer_in_vocab": f["answer"].lower() in vocab,
             "answer_pos": vocab.get(f["answer"].lower(), {}).get("pos", "")})
    out["pool_size_by_type"] = sizes

    with open(os.path.join(HERE, "candidate_pool_probe.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    print("vocab:", out["vocab_size"], "with POS:", out["vocab_with_pos"],
          "| book distinct words:", out["book_distinct_words"],
          "| of which POS known:", out["book_distinct_words_with_pos"])
    for fid, row in out["cases"].items():
        print("\n==", fid, "answer:", row["stored_answer"], "gold alt:", row["gold_alternative"])
        for scope, d in row["scopes"].items():
            print("   %-8s answer_pos=%-4s pool_size=%-5d hits=%s"
                  % (scope, d["answer_pos"], d["pool_size"],
                     {k: v for k, v in d["alternative_hits"].items()}))
            for a, det in d["detail"].items():
                print("        %-9s in_pool=%-5s section=%-5s unit=%-5s book=%-5s vocab=%-5s pos=%s bold=%s"
                      % (a, det["in_pool"], det["in_section_text"], det["in_unit_text"],
                         det["in_book_text"], det["in_vocabulary"], det["vocab_pos"], det["bold"]))
    cp.close()


if __name__ == "__main__":
    main()
