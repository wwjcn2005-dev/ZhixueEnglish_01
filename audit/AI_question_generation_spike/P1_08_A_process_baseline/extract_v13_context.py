"""只读：提取 V1.3 中与"题库/生成题"相关的上下文，用于规范 §20 的准确性核对。"""
import glob
import os
import re

D = r"D:\ZhixueEnglish\docs"
p = glob.glob(os.path.join(D, "*V1.3.md"))[0]
t = open(p, encoding="utf-8").read()
for kw in ["无限题库", "生成题", "AI 生成题", "题库"]:
    print("=" * 90)
    print("关键词:", kw, "命中", len(re.findall(re.escape(kw), t)), "次")
    for m in re.finditer(re.escape(kw), t):
        s = max(0, m.start() - 170)
        e = min(len(t), m.end() + 170)
        print("   ...", t[s:e].replace("\n", " "), "...")
        print()
