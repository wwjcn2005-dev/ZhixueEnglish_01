# -*- coding: utf-8 -*-
"""P1-09-A: verify distractor legality / POS for the T4 triage rule (read-only)."""

import sqlite3

CP = r"D:\ZhixueEnglish\structured\contentpack\v5\FLTRP-EN-7A-2022CUR.sqlite"
WORDS = ["polite", "dry", "important", "mistake", "different", "traditional", "electric",
         "weak", "band", "club", "stage", "instrument", "root", "stem", "sugar", "oxygen"]


def main():
    con = sqlite3.connect("file:" + CP.replace("\\", "/") + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    for w in WORDS:
        rows = cur.execute(
            "SELECT item_id, surface_form, part_of_speech, learning_requirement, review_status"
            " FROM learning_item WHERE item_type='vocabulary' AND lower(lemma)=?", (w,)).fetchall()
        em = cur.execute(
            "SELECT DISTINCT textbook_emphasis FROM source_ref r JOIN learning_item i"
            " ON i.item_id = r.item_id WHERE lower(i.lemma)=? AND i.item_type='vocabulary'",
            (w,)).fetchall()
        if rows:
            r = rows[0]
            print("%-12s IN LIST   pos=%-5s req=%-11s review=%-12s emphasis=%s"
                  % (w, r["part_of_speech"], r["learning_requirement"], r["review_status"],
                     [e[0] for e in em]))
        else:
            print("%-12s not in vocabulary list (may still appear in textbook text)" % w)
    con.close()


if __name__ == "__main__":
    main()
