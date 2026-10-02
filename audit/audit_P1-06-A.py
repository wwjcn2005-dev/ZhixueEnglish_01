#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P1-06-A 教材派生学习资源设计与只读审计（只读，标准库。

产物：audit/P1-06-A_learning_resource_design.md / .json
"""

import hashlib
import json
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(r"D:\ZhixueEnglish")
DB = BASE / "structured" / "contentpack" / "v1" / "FLTRP-EN-7A-2022CUR.sqlite"
AUDIT = BASE / "audit"

CJK = re.compile(r"[\u4e00-\u9fff]")
PHON = re.compile(r"/[^/\s]{2,}/")
POS = re.compile(r"\b(n|v|adj|adv|prep|pron|conj|num|art|int|abbr)\.")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def classify(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return "empty"
    latin = bool(re.match(r"^[A-Za-z]", t))
    cjk = bool(CJK.search(t))
    if latin and cjk and (PHON.search(t) or POS.search(t)):
        return "head_entry"
    if latin and cjk:
        return "latin_cjk_entry"
    if cjk and not latin:
        return "continuation_or_cjk"
    if latin:
        return "latin_only"
    return "other"


def headword(text: str) -> str:
    t = PHON.sub(" ", text or "")
    t = re.split(r"\s*(?=[\u4e00-\u9fff])", t)[0]
    t = POS.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip(" -·")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    conn = sqlite3.connect("file:%s?mode=ro" % DB.as_posix(), uri=True)
    q = lambda sql, args=(): conn.execute(sql, args).fetchall()
    one = lambda sql, args=(): conn.execute(sql, args).fetchone()[0]

    db_info = {"path": str(DB), "size_bytes": DB.stat().st_size,
               "sha256": sha256_file(DB), "readonly": True}

    counts = {t: one("SELECT COUNT(*) FROM %s" % t) for t in
              ("page", "unit", "section", "activity", "content_block", "content_asset",
               "evidence", "audio_asset", "audio_mapping", "sub_question",
               "learning_item", "learning_goal", "ai_artifact")}

    def page_status(pg):
        r = q("SELECT layout_type, reading_order_status, page_role FROM page WHERE pdf_page=?",
              (pg,))
        return dict(zip(("layout_type", "reading_order_status", "page_role"), r[0])) if r else {}

    ranges = {"Words and expressions p155-162": (155, 162),
              "Proper nouns p163-164": (163, 164),
              "Vocabulary A-Z p165-173": (165, 173)}
    vocab = {}
    for label, (a, b) in ranges.items():
        rows = q("SELECT b.text_raw FROM content_block b JOIN page p ON b.page_id=p.page_id "
                 "WHERE p.pdf_page BETWEEN ? AND ? ORDER BY p.pdf_page, b.reading_order", (a, b))
        kinds, heads = {}, []
        for (raw,) in rows:
            k = classify(raw)
            kinds[k] = kinds.get(k, 0) + 1
            if k in ("head_entry", "latin_cjk_entry"):
                heads.append((raw or "")[:60])
        multi = [h for h in heads if " " in headword(h)]
        vocab[label] = {"blocks": len(rows), "kinds": kinds, "entries": len(heads),
                        "multiword_entries": len(multi), "multiword_samples": multi[:8],
                        "page_status": {str(p): page_status(p) for p in range(a, min(a + 1, b) + 1)}}

    cb_pages = [r[0] for r in q("SELECT DISTINCT p.pdf_page FROM content_block b "
                                "JOIN page p ON b.page_id=p.page_id "
                                "WHERE b.text_raw LIKE '%Communication bank%' ORDER BY 1")]
    comm = {"pages": cb_pages,
            "bullets": one("SELECT COUNT(*) FROM content_block WHERE text_raw LIKE '•%'"),
            "useful": one("SELECT COUNT(*) FROM content_block WHERE text_raw LIKE '%Useful expressions%'"),
            "samples": [r[0][:48] for r in q("SELECT text_raw FROM content_block WHERE text_raw LIKE '•%' LIMIT 10")]}

    ptrs = [{"page": r[0], "text": r[1][:48]} for r in
            q("SELECT p.pdf_page, b.text_raw FROM content_block b JOIN page p ON b.page_id=p.page_id "
              "WHERE b.text_raw LIKE '%Grammar rules%' ORDER BY p.pdf_page")]
    guide_start = one("SELECT pdf_page_start FROM section WHERE title='Guide to the language use'")
    guide_topics = [{"page": r[0], "text": r[1][:52]} for r in
                    q("SELECT p.pdf_page, b.text_raw FROM content_block b JOIN page p ON b.page_id=p.page_id "
                      "WHERE p.pdf_page BETWEEN ? AND ? AND b.layout_role IN ('heading','section_title') "
                      "ORDER BY p.pdf_page", (guide_start, guide_start + 20))]
    toc_grammar = [r[0][:60] for r in
                   q("SELECT b.text_raw FROM content_block b JOIN page p ON b.page_id=p.page_id "
                     "WHERE p.pdf_page IN (5,6) AND (b.text_raw LIKE '%Grammar%' "
                     "OR b.text_raw LIKE '%tense%' OR b.text_raw LIKE '%pronoun%') LIMIT 10")]
    grammar = {"pointers": ptrs, "guide_start": guide_start, "guide_topics": guide_topics,
               "toc_mentions": toc_grammar}

    def range_status(a, b):
        return {"%s|%s" % (r[0], r[1]): r[2] for r in
                q("SELECT layout_type, reading_order_status, COUNT(*) FROM page "
                  "WHERE pdf_page BETWEEN ? AND ? GROUP BY 1,2", (a, b))}

    need = {"activity_boundary": one("SELECT COUNT(*) FROM activity WHERE boundary_status<>'OK'"),
            "reading_order": one("SELECT COUNT(*) FROM page WHERE reading_order_status='NEED_REVIEW'"),
            "sub_question": one("SELECT COUNT(*) FROM sub_question WHERE review_status='NEED_REVIEW'"),
            "by_range": {"WordsAndExpressions": range_status(155, 162),
                         "Vocabulary": range_status(165, 173),
                         "CommunicationBank": range_status(117, 134),
                         "GuideToLanguageUse": range_status(135, 154),
                         "UnitContent": range_status(19, 114)}}

    kinds = dict(q("SELECT block_kind, COUNT(*) FROM content_block GROUP BY 1 ORDER BY 2 DESC"))

    verdicts = {
        "Vocabulary": {"verdict": "可行（部分自动 + 部分人工）",
                       "auto": "附录 head_entry 型条目（含音标或词性 + 中文释义）",
                       "manual": "跨块续行条目合并、Proper nouns 归类",
                       "forbidden": "从正文/对话/语法说明自动抽词；AI 推荐词"},
        "Phrase": {"verdict": "部分可行（以人工确认为主）",
                   "auto": "附录词汇表中 headword 含空格的多词条目",
                   "manual": "Communication bank / Useful expressions 中的交际表达",
                   "forbidden": "把普通连续文本机械切片成短语"},
        "Sentence Pattern": {"verdict": "部分可行（需人工确认）",
                             "auto": "Communication bank 的 • 条目结构化定位",
                             "manual": "占位符规范化、归属 Unit 与功能、是否核心句型",
                             "forbidden": "把阅读课文/语法例句中的普通句子当作句型"},
        "Grammar": {"verdict": "可行（结构证据明确）",
                    "auto": "Guide to the language use 主题标题 + Grammar rules 指针 + 目录 Grammar 栏",
                    "manual": "主题规范命名、绑定教学页范围",
                    "forbidden": "根据文本用法推断教材正在教授某语法点"}}

    payload = {"task": "P1-06-A 教材派生学习资源设计与只读审计",
               "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
               "verdict": "PASS WITH NOTES", "database": db_info, "counts": counts,
               "vocabulary_sources": vocab, "communication_bank": comm,
               "grammar_evidence": grammar, "need_review": need,
               "block_kind_distribution": kinds, "resource_verdicts": verdicts,
               "learning_item_fields": {
                   "item_id": "必需（稳定主键）",
                   "textbook_id": "必需（版本隔离）",
                   "snapshot_id": "必需（快照隔离）",
                   "item_type": "必需（vocabulary/phrase/sentence_pattern/grammar）",
                   "canonical_text": "必需（规范形式，用于去重检索）",
                   "display_text": "必需（保留教材原始写法）",
                   "explanation": "不放入 L2；解释属 L3 AI 辅助层",
                   "source_ref": "必需（至少一条，指向 content_block）",
                   "review_status": "必需（EXTRACTED/NEED_REVIEW/REVIEWED_OK/REJECTED）",
                   "schema_version": "必需",
                   "content_hash": "必需",
                   "created_at/updated_at": "必需"},
               "boundaries": {"sqlite_modified": False, "pdf_modified": False,
                              "mp3_modified": False, "parser_modified": False,
                              "builder_modified": False, "learning_item_created": False,
                              "ai_calls": 0}}

    AUDIT.mkdir(parents=True, exist_ok=True)
    jp = AUDIT / "P1-06-A_learning_resource_design.json"
    jp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md = ["# P1-06-A 教材派生学习资源设计与只读审计报告", "",
          "- 生成时间：%s" % payload["generated_at"],
          "- 结论：%s" % payload["verdict"],
          "- 审计对象：%s（只读）" % db_info["path"],
          "- 数据库 SHA256：%s" % db_info["sha256"], "",
          "## 1. 资源来源证据", ""]
    for label, info in vocab.items():
        md += ["### %s" % label,
               "- 内容块 %d 条；条目型 %d 条；多词条目 %d 条" %
               (info["blocks"], info["entries"], info["multiword_entries"]),
               "- 分类分布：%s" % info["kinds"],
               "- 多词样例：%s" % info["multiword_samples"], ""]
    md += ["### Communication bank（句型/交际功能）",
           "- 出现页：%s" % comm["pages"],
           "- • 条目块：%d；Useful expressions 块：%d" % (comm["bullets"], comm["useful"]),
           "- 样例：%s" % comm["samples"][:6], "",
           "### Grammar",
           "- Grammar rules 指针：%s" % [g["text"] for g in ptrs if "⇢" in g["text"]],
           "- Guide to the language use 起始页：p.%s" % guide_start,
           "- 语法主题标题样例：%s" % [g["text"] for g in guide_topics[:12]],
           "- 目录 Grammar 栏：%s" % toc_grammar, "",
           "## 2. 四类资源可行性", "",
           "| 类型 | 判定 | 自动 | 人工确认 | 禁止 |",
           "| --- | --- | --- | --- | --- |"]
    for k, v in verdicts.items():
        md.append("| %s | %s | %s | %s | %s |" % (k, v["verdict"], v["auto"], v["manual"], v["forbidden"]))
    md += ["", "## 3. NEED_REVIEW 影响",
           "- Activity boundary：%d" % need["activity_boundary"],
           "- Reading-order：%d 页" % need["reading_order"],
           "- SubQuestion：%d" % need["sub_question"]]
    for k, v in need["by_range"].items():
        md.append("- %s：%s" % (k, v))
    md += ["", "## 4. 当前底座不足",
           "- block_kind 分布：%s（dialogue=0，分类偏粗）" % kinds,
           "- evidence 缺 bbox / extraction_version（P1-05-C 已记录）",
           "- 附录词汇表存在跨块续行（head entry 与中文续行分离）",
           "- 部分 Unit 页 reading order 为 NEED_REVIEW，影响句级定位，不影响块内文本", "",
           "## 5. learning_item 字段评估", ""]
    for k, v in payload["learning_item_fields"].items():
        md.append("- %s：%s" % (k, v))
    md += ["", "## 6. 边界", ""]
    for k, v in payload["boundaries"].items():
        md.append("- %s：%s" % (k, v))
    mp = AUDIT / "P1-06-A_learning_resource_design.md"
    mp.write_text("\n".join(md) + "\n", encoding="utf-8")
    conn.close()

    print("P1-06-A 完成：", payload["verdict"])
    for k, v in verdicts.items():
        print("  %s: %s" % (k, v["verdict"]))
    for label, info in vocab.items():
        print("  %s: blocks=%d entries=%d multiword=%d" %
              (label, info["blocks"], info["entries"], info["multiword_entries"]))
    print("  Communication bank pages:", comm["pages"])
    print("  Grammar pointers:", len(ptrs), " guide topics:", len(guide_topics))
    print("  NEED_REVIEW:", need["activity_boundary"], "activity /", need["reading_order"], "pages")
    print("报告:", mp)
    print("JSON:", jp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
