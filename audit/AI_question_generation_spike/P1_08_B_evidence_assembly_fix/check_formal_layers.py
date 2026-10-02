"""只读：检查正式层（web/ demo/）是否存在同样的 page→section 反推缺陷。"""
import glob
import os
import re

BASE = r"D:\ZhixueEnglish"
PATTERNS = [
    ("activity_pages_join", r"from\s+activity|join\s+activity"),
    ("page2sec", r"page2sec|page_to_section|pdf_page.*section_id"),
    ("content_block_use", r"content_block"),
    ("section_range", r"pdf_page_start|pdf_page_end"),
]

targets = []
for sub in ["web", "demo"]:
    targets += glob.glob(os.path.join(BASE, sub, "*.py"))
targets += glob.glob(os.path.join(BASE, "structured", "**", "*.py"), recursive=True)

print("=== 正式层扫描 ===")
for p in sorted(targets):
    t = open(p, encoding="utf-8", errors="ignore").read()
    hits = {name: len(re.findall(pat, t, flags=re.I)) for name, pat in PATTERNS}
    if hits["content_block_use"] or hits["activity_pages_join"]:
        print("  %-58s %s" % (os.path.relpath(p, BASE), hits))
        for name, pat in PATTERNS[:2]:
            for m in list(re.finditer(pat, t, flags=re.I))[:2]:
                s = max(0, m.start() - 130)
                print("      [%s] ...%s..." % (name, t[s:m.end() + 120].replace("\n", " ")[:240]))
        print()
