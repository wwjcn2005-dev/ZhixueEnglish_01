"""P1-02 · 创建正式 AI Question Library 数据库（只建结构，不写入任何题目）。

用法：
    python create_question_library.py            # 创建（若已存在则拒绝覆盖）
    python create_question_library.py --dry-run  # 只在临时库上演练，不碰正式文件

安全约束：
  * 绝不修改 learning.db / contentpack / 教材数据；
  * 不调用任何 AI；
  * 不写入任何真实题目（只建 6 张空表）。
"""
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ql_schema as S  # noqa: E402

BASE = r"D:\ZhixueEnglish"
DB_DIR = os.path.join(BASE, "structured", "ai")
DB_PATH = os.path.join(DB_DIR, "question_library.db")


def _create(path: str) -> None:
    conn = sqlite3.connect(path)
    try:
        S.create_schema(conn)
        conn.commit()
    finally:
        conn.close()


def main() -> int:
    dry = "--dry-run" in sys.argv

    if dry:
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "question_library.db")
            _create(p)
            c = sqlite3.connect("file:" + p + "?mode=ro", uri=True)
            n = c.execute("select count(*) from sqlite_master where type='table' "
                          "and name not like 'sqlite_%'").fetchone()[0]
            c.close()
            print("[dry-run] 临时库创建成功，表数 = %d（未触碰正式文件）" % n)
        return 0

    if os.path.exists(DB_PATH):
        print("拒绝执行：%s 已存在。本脚本不会覆盖既有数据库。" % DB_PATH)
        return 2

    os.makedirs(DB_DIR, exist_ok=True)
    _create(DB_PATH)
    print("已创建：%s" % DB_PATH)
    print("表：%s" % ", ".join(S.TABLE_NAMES))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
