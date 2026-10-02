"""P0 Spike 第一步：组装教材上下文（只读 contentpack v5 + 证据包）。

只写本目录的 input_context.json。
"""
import json
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = r"D:\ZhixueEnglish"
CP = os.path.join(BASE, "structured", "contentpack", "v5", "FLTRP-EN-7A-2022CUR.sqlite")
EV = os.path.join(BASE, "structured", "ai", "textbook_evidence_map_v1.json")

sys.path.insert(0, os.path.join(BASE, "web"))
import content as C  # noqa: E402

db = sqlite3.connect(CP)
db.row_factory = sqlite3.Row

SECTION = {"unit": "Unit 3", "unit_title": "Family ties", "section": "READING_FOR_WRITING",
           "section_title": "Reading for writing",
           "textbook_pages": [56, 57, 58, 59], "pdf_pages": [61, 62, 63, 64]}

blocks = []
for page in SECTION["textbook_pages"]:
    for r in db.execute(
            "select b.block_id, b.block_kind, b.layout_role, b.reading_order, b.text_raw "
            "from content_block b join page p on p.page_id=b.page_id "
            "where p.pdf_page=? order by b.reading_order", (page + 5,)):
        text = (r["text_raw"] or "").replace("\n", " ").strip()
        if not text or r["block_kind"] == "footer_text":
            continue
        if page == 59 and r["block_kind"] != "instruction":
            continue          # 写作页只留任务指令，去掉表格占位符噪声
        blocks.append({"block_id": r["block_id"], "page": page, "kind": r["block_kind"],
                       "role": r["layout_role"], "text": text})

emph = {}
for r in db.execute("select item_id, textbook_emphasis from source_ref "
                    "where item_id like 'FLTRP-EN-7A-2022CUR:V:%'"):
    emph.setdefault(r["item_id"], r["textbook_emphasis"])
vocab = []
for item in C.list_unit_resources("unit3", "vocabulary")["items"]:
    vocab.append({"word": item["text"], "pos": item["part_of_speech"],
                  "meaning_zh": item["meaning"], "emphasis": emph.get(item["item_id"], "PLAIN"),
                  "is_core": bool(item["can_study"]), "textbook_page": item["page"]})

ev = json.load(open(EV, encoding="utf-8"))
packages = []
for p in ev["packages"]:
    sc = p["scope"]
    if sc.get("unit") != SECTION["unit"] or sc.get("section") != SECTION["section"]:
        continue
    tr = p["textbook_reference"]
    packages.append({"question_id": p["question_id"], "activity_no": sc.get("activity_no"),
                     "page": tr.get("textbook_page"),
                     "instruction": tr.get("instruction"),
                     "original_question_text": (p["original_question"] or {}).get("text", "")[:300],
                     "answer_source": p.get("answer_source"),
                     "answer_note": p.get("answer_note")})

acts = []
for r in db.execute("select activity_number, instruction, textbook_page from activity "
                    "where section_id='FLTRP-EN-7A-2022CUR:U3:READING_FOR_WRITING' "
                    "order by activity_number"):
    acts.append({"activity_no": r["activity_number"], "page": r["textbook_page"],
                 "instruction": r["instruction"]})

context = {"textbook_position": SECTION, "activity_instructions": acts,
           "textbook_blocks": blocks, "unit_vocabulary": vocab,
           "evidence_packages": packages,
           "rules": {"BOLD": "core textbook word (教材黑体重点词)",
                     "PLAIN": "ordinary textbook word (非核心重点词)"}}
with open(os.path.join(HERE, "input_context.json"), "w", encoding="utf-8") as fh:
    json.dump(context, fh, ensure_ascii=False, indent=1)

print("输入范围: %s / %s" % (SECTION["unit"], SECTION["section"]))
print("  教材页: %s (pdf %s)" % (SECTION["textbook_pages"], SECTION["pdf_pages"]))
print("  content_block: %d 个; 页码 %s" % (len(blocks), sorted({b["page"] for b in blocks})))
print("  activity: %s" % [a["activity_no"] for a in acts])
print("  Unit 词汇: %d (BOLD %d / PLAIN %d)" % (
    len(vocab), sum(1 for v in vocab if v["emphasis"] == "BOLD"),
    sum(1 for v in vocab if v["emphasis"] != "BOLD")))
print("  证据包: %d" % len(packages))
print("  context 字符: %d" % len(json.dumps(context, ensure_ascii=False)))
