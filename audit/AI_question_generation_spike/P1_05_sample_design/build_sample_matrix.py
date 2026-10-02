"""P1-05-A · 从正式数据计算 7 个样本 Section 的证据画像并生成样本矩阵。

只读 contentpack / structured；不调用任何 AI；不修改任何正式数据。
输出：p1_05_sample_matrix.json
"""
import collections
import json
import os
import sqlite3

BASE = r"D:\ZhixueEnglish"
HERE = os.path.dirname(os.path.abspath(__file__))
CP = os.path.join(BASE, "structured", "contentpack", "v5", "FLTRP-EN-7A-2022CUR.sqlite")
STRUCT = os.path.join(BASE, "structured", "textbook", "textbook_structure_v2.json")
CATALOG = os.path.join(BASE, "structured", "exercises", "exercise_catalog_v3.json")
RELATIONS = os.path.join(BASE, "structured", "exercises", "exercise_question_relations_v3.json")
EVID = os.path.join(BASE, "structured", "ai", "textbook_evidence_map_v1.json")
OUT = os.path.join(HERE, "p1_05_sample_matrix.json")

SELECTED = [
    ("FLTRP-EN-7A-2022CUR:U2:UNDERSTANDING_IDEAS", "A_READING",
     "正文证据最丰富的阅读段（83 blocks / 21 证据包 / 21 词）", ["RICH_READING"]),
    ("FLTRP-EN-7A-2022CUR:U6:READING_FOR_WRITING", "A_READING",
     "读写结合阅读段（54 blocks / 12 证据包 / 16 词）", ["RICH_READING", "DISTRACTOR_RISK"]),
    ("FLTRP-EN-7A-2022CUR:U1:UNDERSTANDING_IDEAS", "B_DIALOGUE",
     "含直接引语的叙事段；同时是 P1-03 的产生地，可观测跨轮重复", ["HIGH_DUPLICATION_RISK"]),
    ("FLTRP-EN-7A-2022CUR:U5:UNDERSTANDING_IDEAS", "C_VOCABULARY",
     "词汇/语言运用最密集（23 词 / 17 加粗 / 4 个 fill）", ["VOCABULARY_SCOPE"]),
    ("FLTRP-EN-7A-2022CUR:STARTER:GET_READY", "D_INFO_MATCH",
     "信息匹配/判断类（match×3、fill×2、choice×1；21 个证据包）",
     ["PARTIAL_AUDIO_SCOPE", "LISTENING_EVIDENCE_GAP"]),
    ("FLTRP-EN-7A-2022CUR:U3:STARTING_OUT", "E_LOW_EVIDENCE",
     "证据密度低（11 blocks / 4 证据包 / 0 加粗词）——观察是否会自然少生成", ["LOW_EVIDENCE"]),
    ("FLTRP-EN-7A-2022CUR:U1:DEVELOPING_IDEAS", "F_LISTENING_GAP",
     "已知听力证据缺口（transcript=0）；仅作“宁缺毋滥”对照，不计入质量指标", ["LISTENING_EVIDENCE_GAP"]),
]


def main():
    conn = sqlite3.connect("file:" + CP + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    struct = json.load(open(STRUCT, encoding="utf-8"))
    catalog = json.load(open(CATALOG, encoding="utf-8"))
    relations = json.load(open(RELATIONS, encoding="utf-8"))
    evidence = json.load(open(EVID, encoding="utf-8"))

    # section -> unit / title
    meta = {}
    for u in struct["units"]:
        for s in u["sections"]:
            meta[s["section_id"]] = {"unit_id": u["unit_id"], "unit_code": u["unit_code"],
                                     "unit_title": u["title"], "section_key": s["section_key"],
                                     "title": s["title"]}

    # section -> activities（contentpack activity 表）
    acts = collections.defaultdict(list)
    for r in conn.execute("select activity_id, section_id, activity_number, pdf_page, "
                          "textbook_page, instruction from activity order by activity_number"):
        acts[r["section_id"]].append(dict(r))

    # pdf page -> section(s)
    page2sec = collections.defaultdict(set)
    for r in conn.execute("select distinct pdf_page, section_id from activity"):
        page2sec[r["pdf_page"]].add(r["section_id"])

    # section -> content blocks（按页面归属，去 footer）
    blocks = collections.defaultdict(list)
    for r in conn.execute("select b.block_id, b.block_kind, b.text_raw, p.pdf_page "
                          "from content_block b join page p on p.page_id=b.page_id "
                          "order by p.pdf_page, b.reading_order"):
        if r["block_kind"] == "footer_text":
            continue
        for s in page2sec.get(r["pdf_page"], []):
            blocks[s].append({"block_id": r["block_id"], "kind": r["block_kind"],
                              "text": (r["text_raw"] or "").replace("\n", " ").strip()})

    # section -> 证据包 / related_vocabulary
    pkgs = collections.Counter()
    vocab = collections.defaultdict(set)
    for p in evidence["packages"]:
        u, s = p["scope"]["unit"], p["scope"]["section"]
        for sid, m in meta.items():
            if m["unit_code"] == u and m["section_key"] == s:
                pkgs[sid] += 1
                for w in (p.get("related_vocabulary") or []):
                    vocab[sid].add(str(w).strip().lower())

    # section -> exercise 统计
    ex_by_sec = collections.defaultdict(list)
    for e in catalog["exercises"]:
        ex_by_sec[e["section_id"]].append(e)
    q_by_sec = collections.Counter()
    for q in relations["questions"]:
        q_by_sec[q["section_id"]] += 1

    # CORE 词表
    core = set()
    for r in conn.execute("select display_text from learning_item "
                          "where item_type='vocabulary' and learning_requirement='CORE'"):
        head = (r["display_text"] or "").split("/")[0].strip().lower()
        if head:
            core.add(head)
            core.add(head.split()[0])

    # 音频文本证据（transcript / 句子注释）——按教材页归属到 Section
    tbpage2sec = collections.defaultdict(set)
    for r in conn.execute("select distinct textbook_page, section_id from activity"):
        tbpage2sec[r["textbook_page"]].add(r["section_id"])
    audio_text = collections.Counter()
    import re as _re
    for r in conn.execute("select source_page from audio_sentence_annotation"):
        m2 = _re.search(r"p\s*(\d+)", str(r["source_page"] or ""))
        if not m2:
            continue
        for s in tbpage2sec.get(int(m2.group(1)), []):
            audio_text[s] += 1
    has_transcript = conn.execute("select count(*) from transcript").fetchone()[0] > 0

    rows = []
    for sid, category, reason, risks in SELECTED:
        m = meta[sid]
        bl = blocks.get(sid, [])
        ex = ex_by_sec.get(sid, [])
        tb_pages = [a["textbook_page"] for a in acts.get(sid, []) if a["textbook_page"]]
        pdf_pages = [a["pdf_page"] for a in acts.get(sid, [])]
        quoted = [b for b in bl if ("\u201c" in b["text"] and "\u201d" in b["text"])]
        longb = [b for b in bl if len(b["text"]) >= 60]
        vset = vocab.get(sid, set())
        types = sorted({e.get("type") for e in ex} - {None})
        qtypes = sorted({e.get("question_type") for e in ex} - {None})
        audio_required = any(e.get("audio_required") for e in ex)
        pk = pkgs.get(sid, 0)
        nblk = len(bl)
        density = "high" if (nblk >= 50 and pk >= 12) else ("medium" if (nblk >= 20 and pk >= 6) else "low")
        rows.append({
            "category": category,
            "unit_id": m["unit_id"], "unit": m["unit_code"], "unit_title": m["unit_title"],
            "section_id": sid, "section_key": m["section_key"], "section_title": m["title"],
            "activity_ids": [a["activity_id"] for a in acts.get(sid, [])],
            "activity_count": len(acts.get(sid, [])),
            "activity_types": types,
            "question_types": qtypes,
            "textbook_page_range": [min(tb_pages), max(tb_pages)] if tb_pages else None,
            "pdf_page_range": [min(pdf_pages), max(pdf_pages)] if pdf_pages else None,
            "content_block_count": nblk,
            "long_body_block_count": len(longb),
            "quoted_speech_block_count": len(quoted),
            "evidence_package_count": pk,
            "question_count": q_by_sec.get(sid, 0),
            "audio_required": audio_required,
            "audio_evidence_available": bool(has_transcript) or audio_text.get(sid, 0) > 0,
            "audio_text_annotation_count": audio_text.get(sid, 0),
            "vocabulary_count": len(vset),
            "bold_vocabulary_count": len({w for w in vset if w in core}),
            "reading_available": ("reading" in types) or len(longb) >= 5,
            "dialogue_available": len(quoted) >= 2,
            "evidence_density": density,
            "sample_reason": reason,
            "expected_risk": list(dict.fromkeys(
                risks + (["PARTIAL_AUDIO_SCOPE"] if audio_required else []))),
            "planned_scope_note": ("仅对该 Section 的非听力活动出题；听力活动单列 "
                                   "LISTENING_EVIDENCE_GAP" if audio_required else None),
        })
    conn.close()

    doc = {
        "stage": "P1-05-A",
        "generated_at": "2026-09-17",
        "purpose": "P1-05-B 小规模质量验证的样本矩阵（只读设计，不含任何 AI 生成）",
        "field_definitions": {
            "content_block_count": "该 Section 页面上所有非 footer 版式块数量（按 activity 页面归属）",
            "evidence_package_count": "textbook_evidence_map_v1.json 中 scope.unit+section 匹配的证据包数",
            "question_count": "exercise_question_relations_v3.json 中该 Section 的教材原题数",
            "activity_types": "exercise_catalog_v3.json 中该 Section 练习的 type 集合",
            "question_types": "该 Section 教材原题的 question_type 集合",
            "audio_required": "该 Section 是否存在 audio_required=true 的教材活动",
            "audio_evidence_available": "该 Section 的音频内容是否有文本证据（transcript / 音频句子注释）",
            "vocabulary_count": "该 Section 全部证据包 related_vocabulary 去重后的词数",
            "bold_vocabulary_count": "上述词中命中 contentpack CORE（加粗重点词）的词数",
            "reading_available": "存在 type=reading 的练习，或长正文块 >= 5",
            "dialogue_available": "直接引语块 >= 2",
            "evidence_density": "high: blocks>=50 且 packages>=12；medium: blocks>=20 且 packages>=6；其余 low",
        },
        "excluded_from_quality_metrics": {
            "section_id": "FLTRP-EN-7A-2022CUR:U1:DEVELOPING_IDEAS",
            "label": "LISTENING_EVIDENCE_GAP",
            "reason": ("该 Section 的听力活动答案依赖音频内容，而 contentpack 的 transcript 为 0 行、"
                       "audio_token_annotation 为 0 行、audio_sentence_annotation 覆盖不全。"
                       "因此它只作为“宁缺毋滥”对照样本，其题量不进入质量分母。"),
            "evidence": {"transcript_rows": 0, "audio_token_annotation_rows": 0,
                         "audio_sentence_annotation_rows": conn_annotation_rows()},
        },
        "selection_summary": {
            "section_count": len(rows),
            "categories": dict(collections.Counter(r["category"] for r in rows)),
            "not_random": "按教材形态定向选择，覆盖阅读/对话/词汇运用/信息匹配/低证据/听力缺口六类",
            "no_question_quota": "P1-05-B 不为任何 Section 设定题量配额；0 题也是合法结果",
        },
        "sections": rows,
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
    print("已写出 %s" % OUT)
    for r in rows:
        print("  %-8s %-22s blocks=%-3d pkgs=%-3d q=%-3d vocab=%-3d bold=%-3d audio=%-5s %s" % (
            r["unit"], r["section_key"], r["content_block_count"], r["evidence_package_count"],
            r["question_count"], r["vocabulary_count"], r["bold_vocabulary_count"],
            r["audio_required"], r["evidence_density"]))


def conn_annotation_rows():
    c = sqlite3.connect("file:" + CP + "?mode=ro", uri=True)
    n = c.execute("select count(*) from audio_sentence_annotation").fetchone()[0]
    c.close()
    return n


if __name__ == "__main__":
    main()
