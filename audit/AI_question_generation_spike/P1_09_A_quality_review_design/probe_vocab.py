# -*- coding: utf-8 -*-
"""P1-09-A read-only probe: Unit vocabulary + BOLD (emphasis) info for distractor legality."""

import json
import sqlite3

CP = r"D:\ZhixueEnglish\structured\contentpack\v5\FLTRP-EN-7A-2022CUR.sqlite"

WORDS = ["band", "club", "stage", "instrument", "different", "traditional", "electric",
         "weak", "drums", "violin", "piano", "alone", "performance", "erhu", "sound",
         "enjoy", "hobby", "fire up", "guitar", "rap", "rock"]


def main():
    con = sqlite3.connect("file:" + CP.replace("\\", "/") + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    def q(sql, args=()):
        return [dict(r) for r in cur.execute(sql, args).fetchall()]

    print("== item_type distribution ==")
    print(json.dumps(q("SELECT item_type, COUNT(*) n FROM learning_item GROUP BY 1 ORDER BY 2 DESC"),
                     ensure_ascii=False))
    print("\n== source_ref sample for a vocabulary item ==")
    print(json.dumps(q("SELECT * FROM source_ref WHERE item_id='FLTRP-EN-7A-2022CUR:V:758EAAF3C83B'"),
                     ensure_ascii=False, indent=1))
    print("\n== source_ref source_type distribution ==")
    print(json.dumps(q("SELECT source_type, COUNT(*) n FROM source_ref GROUP BY 1 ORDER BY 2 DESC"),
                     ensure_ascii=False))

    print("\n== candidate distractor words in vocabulary list ==")
    for w in WORDS:
        rows = q("SELECT item_id, surface_form, lemma, canonical_text, "
                 "learning_requirement, review_status FROM learning_item "
                 "WHERE lower(lemma)=? OR lower(canonical_text)=?", (w, w))
        mark = "FOUND" if rows else "-- not in list --"
        print("  %-14s %s" % (w, mark))
        for r in rows:
            em = q("SELECT textbook_emphasis, emphasis_source_list FROM source_ref WHERE item_id=?",
                   (r["item_id"],))
            print("      ", r["item_id"], "|", r["surface_form"], "| req", r["learning_requirement"],
                  "| emphasis", em)

    print("\n== all Unit-2-ish vocabulary (surface_form containing 'music'/'band'/'erhu') ==")
    for r in q("SELECT item_id, surface_form, lemma, learning_requirement FROM learning_item "
               "WHERE item_type='vocabulary' AND (lower(surface_form) LIKE '%band%'"
               " OR lower(surface_form) LIKE '%erhu%' OR lower(surface_form) LIKE '%drum%'"
               " OR lower(surface_form) LIKE '%violin%' OR lower(surface_form) LIKE '%piano%'"
               " OR lower(surface_form) LIKE '%music%') ORDER BY surface_form"):
        print("  ", r["item_id"], "|", r["surface_form"], "|", r["learning_requirement"])

    print("\n== learning_item count ==")
    print(q("SELECT COUNT(*) n FROM learning_item")[0])
    con.close()


if __name__ == "__main__":
    main()
