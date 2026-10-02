# -*- coding: utf-8 -*-
"""P1-09-A read-only probe: contentpack v5 schema + Unit vocabulary for distractor legality."""

import sqlite3

CP = r"D:\ZhixueEnglish\structured\contentpack\v5\FLTRP-EN-7A-2022CUR.sqlite"


def main():
    con = sqlite3.connect("file:" + CP.replace("\\", "/") + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    print("== objects ==")
    for r in cur.execute("SELECT type, name FROM sqlite_master WHERE type IN ('table','view')"
                         " ORDER BY type, name"):
        print("  ", r[0], r[1])
    print("\n== table columns ==")
    names = [r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
    for n in names:
        cols = [c[1] for c in cur.execute("PRAGMA table_info(%s)" % n).fetchall()]
        print("  %s: %s" % (n, ", ".join(cols)))

    print("\n== learning_item rows (limit 25) ==")
    for r in cur.execute("SELECT * FROM learning_item LIMIT 25").fetchall():
        print("  ", dict(r))
    print("\n== learning_item count by kind ==")
    for r in cur.execute("SELECT item_kind, COUNT(*) n FROM learning_item GROUP BY 1"
                         " ORDER BY 2 DESC").fetchall():
        print("  ", r[0], r[1])
    con2 = sqlite3.connect("file:" + CP.replace("\\", "/") + "?mode=ro", uri=True)
    print("\n== Unit 2 vocabulary (word forms containing band/traditional/electric/weak) ==")
    for r in con2.execute(
            "SELECT * FROM learning_item WHERE unit_id LIKE '%U2'"
            " AND (lower(item_text) IN ('band','traditional','electric','weak','different','club','stage','instrument'))"
    ).fetchall():
        print("  ", dict(r))
    con.close()


if __name__ == "__main__":
    main()
