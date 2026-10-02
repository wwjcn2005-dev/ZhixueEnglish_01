"""P1-02 §12 · 跨库引用只读检查（不自动修复、不做同步）。

检查两件事：
  1) question_learning_object.item_id 是否存在于 contentpack 的 learning_item
  2) question_evidence.evidence_block_id 是否存在于 contentpack 的 content_block

只读打开两个数据库；发现悬空引用时报告 ERROR 并以退出码 1 结束。
"""
import os
import sqlite3
import sys

BASE = r"D:\ZhixueEnglish"
LIB = os.path.join(BASE, "structured", "ai", "question_library.db")
CP = os.path.join(BASE, "structured", "contentpack", "v5", "FLTRP-EN-7A-2022CUR.sqlite")


def ro(path):
    return sqlite3.connect("file:" + path + "?mode=ro", uri=True)


def main() -> int:
    if not os.path.exists(LIB):
        print("ERROR: question_library.db 不存在：%s" % LIB)
        return 1

    lib, cp = ro(LIB), ro(CP)
    errors = 0
    checked = {}

    # 1) LearningObject 引用
    items = [r[0] for r in lib.execute(
        "select distinct item_id from question_learning_object")]
    known = {r[0] for r in cp.execute("select item_id from learning_item")}
    dangling = [i for i in items if i not in known]
    checked["question_learning_object.item_id"] = {
        "distinct_refs": len(items), "known_in_contentpack": len(items) - len(dangling),
        "dangling": dangling}
    for i in dangling:
        print("ERROR: 悬空 LearningObject 引用：%s" % i)
    errors += len(dangling)

    # 2) evidence block 引用
    blocks = [r[0] for r in lib.execute(
        "select distinct evidence_block_id from question_evidence")]
    known_b = {r[0] for r in cp.execute("select block_id from content_block")}
    dangling_b = [b for b in blocks if b not in known_b]
    checked["question_evidence.evidence_block_id"] = {
        "distinct_refs": len(blocks), "known_in_contentpack": len(blocks) - len(dangling_b),
        "dangling": dangling_b}
    for b in dangling_b:
        print("ERROR: 悬空 evidence block 引用：%s" % b)
    errors += len(dangling_b)

    cp.close()
    lib.close()

    print()
    for k, v in checked.items():
        print("%-38s refs=%d ok=%d dangling=%d" % (k, v["distinct_refs"],
                                                   v["known_in_contentpack"], len(v["dangling"])))
    print()
    if errors:
        print("跨库检查结果：ERROR（%d 处悬空引用；本阶段不自动修复）" % errors)
        return 1
    print("跨库检查结果：PASS（无悬空引用）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
