"""只读：抽取 V1.3 中与 AI 生成题目直接相关的两节全文，用于权威判断是否冲突。"""
import glob
import os
import re

D = r"D:\ZhixueEnglish\docs"
t = open(glob.glob(os.path.join(D, "*V1.3.md"))[0], encoding="utf-8").read()
heads = [m.start() for m in re.finditer(r"^## ", t, flags=re.M)]


def section(title_keyword):
    for i, s in enumerate(heads):
        e = heads[i + 1] if i + 1 < len(heads) else len(t)
        if title_keyword in t[s:s + 40]:
            return t[s:e]
    return "(未找到)"


for kw in ["九、AI 功能边界", "二十二、学习系统原则"]:
    print("=" * 100)
    print(t[section(kw).find("#"):][:0] or "", end="")
    print(section(kw)[:4200])
