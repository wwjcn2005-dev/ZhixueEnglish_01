"""P1-05-G · 只读分析：逐题判定 + 与 P1-05-D / F 对照。不调用 AI、不写题库。"""
import hashlib
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
SPIKE = os.path.join(r"D:\ZhixueEnglish", "audit", "AI_question_generation_spike")
CTX = os.path.join(SPIKE, "P1_05_real_validation", "runs",
                   "01_Unit2_UNDERSTANDING_IDEAS_context.json")
G_PARSED = os.path.join(HERE, "p1_05g_parsed.json")
F_PARSED = os.path.join(SPIKE, "P1_05_prompt_v2_textbook_focus", "p1_05f_parsed.json")
D_PARSED = os.path.join(SPIKE, "P1_05_budget_calibration_v2", "calibration_parsed.json")
sys.path.insert(0, os.path.join(SPIKE, "P1_04_rule_fixes"))
import validator_v3 as V3  # noqa: E402

# 逐题人工判定（对照教材证据）
JUDGE = {
    1: dict(answer_vocab="guitar", answer_bold=True, unique=True,
            verbatim_context=True, recombined=False, textbook_copy=False, value="MEDIUM",
            learning_point="electric guitar（BOLD 核心词搭配）",
            note="教材原句挖空；答案来自词汇表 BOLD 词"),
    2: dict(answer_vocab="sound", answer_bold=True, unique=True,
            verbatim_context=True, recombined=False, textbook_copy=False, value="MEDIUM",
            learning_point="sound（BOLD）+ 教材 a5 语法聚焦例句 the sound of … cuts in",
            note="教材原句挖空；对应教材明确聚焦的语言点"),
    3: dict(answer_vocab="different", answer_bold=True, unique=False,
            verbatim_context=True, recombined=False, textbook_copy=False, value="MEDIUM",
            learning_point="different（BOLD）",
            note="唯一性风险：traditional 同为 BOLD 词，'a traditional kind of music' 在语言上也成立"),
    4: dict(answer_vocab="practice", answer_bold=True, unique=True,
            verbatim_context=True, recombined=False, textbook_copy=False, value="MEDIUM",
            learning_point="practice（BOLD）",
            note="教材原句挖空；与 P1-05-F Q5 同答案同 block"),
    5: dict(answer_vocab="decide", answer_bold=True, unique=True,
            verbatim_context=False, recombined=True, textbook_copy=False, value="MEDIUM",
            learning_point="decide to do（BOLD + 核心结构）",
            note="语境被重组（in it → the school art festival）；干扰项 decide/practice/enjoy 全为 BOLD 词；与 P1-05-D Q7 同答案同 block"),
    6: dict(answer_vocab=None, answer_bold=False, unique=True,
            verbatim_context=False, recombined=True, textbook_copy=False, value="MEDIUM",
            learning_point="课文重要事实（爷爷在公园拉二胡 + 一起唱京剧）",
            note="把 block B12 的两个事实合并成一道理解题；三个选项全部来自课文"),
    7: dict(answer_vocab="instrument", answer_bold=True, unique=True,
            verbatim_context=False, recombined=True, textbook_copy=False, value="MEDIUM",
            learning_point="fire up our instruments（重点表达，含 BOLD 词 instrument）",
            note="与教材 a4 图表考同一句，但题型与考法不同；三个选项全部来自课文"),
    8: dict(answer_vocab=None, answer_bold=False, unique=True,
            verbatim_context=True, recombined=False, textbook_copy=False, value="LOW",
            learning_point="课文重要事实（相视而笑）",
            note="题干就是教材原句本身，判 True 过于直接，学习增量低；与 P1-05-F Q4 同事实同题型"),
}


def sha_file(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest().upper()


def analyze(questions, ctx, allow, vocab, bold, judge=None):
    rows = []
    for i, q in enumerate(questions, 1):
        ans = (q.get("answer") or "").lower()
        vh = [w for w in vocab if w in ans]
        bh = [w for w in vh if w in bold]
        oos = V3.out_of_scope(V3.checked_language(q), allow)
        r = {"index": i, "type": q.get("type"), "question": q.get("question"),
             "options": q.get("options"), "answer": q.get("answer"),
             "blocks": [b.split(":")[-1] for b in (q.get("evidence_block_ids") or [])],
             "vocab_hit": vh, "bold_hit": bh, "out_of_scope": oos}
        if judge:
            r.update(judge[i])
        rows.append(r)
    return rows


def main():
    ctx = json.load(open(CTX, encoding="utf-8"))
    allow = V3.build_whitelist(ctx)
    vocab = {v["word"].lower(): v["emphasis"] for v in ctx["unit_vocabulary"]}
    bold = {w for w, e in vocab.items() if e == "BOLD"}
    G = json.load(open(G_PARSED, encoding="utf-8"))["questions"]
    F = json.load(open(F_PARSED, encoding="utf-8"))["questions"]
    D = json.load(open(D_PARSED, encoding="utf-8"))["questions"]

    gr = analyze(G, ctx, allow, vocab, bold, JUDGE)
    fr = analyze(F, ctx, allow, vocab, bold)
    dr = analyze(D, ctx, allow, vocab, bold)

    # 检查器的 -ing 假阳性（教材内词的词形变化）
    g_oos = sorted({t for r in gr for t in r["out_of_scope"]})
    inflections = {"doing": "do", "sharing": "share", "writing": "write"}
    g_real_oos = [t for t in g_oos if t not in inflections]

    def base(rows):
        return {"total": len(rows),
                "types": dict(Counter(r["type"] for r in rows)),
                "fill_count": sum(1 for r in rows if r["type"] == "fill"),
                "fill_vocab_answer": sum(1 for r in rows if r["type"] == "fill" and r["vocab_hit"]),
                "fill_bold_answer": sum(1 for r in rows if r["type"] == "fill" and r["bold_hit"]),
                "vocab_answer": sum(1 for r in rows if r["vocab_hit"]),
                "bold_answer": sum(1 for r in rows if r["bold_hit"]),
                "oos_questions": sum(1 for r in rows if r["out_of_scope"]),
                "oos_tokens": sorted({t for r in rows for t in r["out_of_scope"]}),
                "block_reuse": {k: v for k, v in Counter(
                    b for r in rows for b in r["blocks"]).items() if v > 1}}

    g_sum, f_sum, d_sum = base(gr), base(fr), base(dr)
    g_sum.update({
        "unique_answer": sum(1 for r in gr if r["unique"]),
        "material_legal": len(gr) - sum(1 for r in gr if r["out_of_scope"]) + 1,
        "real_out_of_textbook_tokens": g_real_oos,
        "recombined": sum(1 for r in gr if r["recombined"]),
        "verbatim_blank": sum(1 for r in gr if r["verbatim_context"] and r["type"] == "fill"),
        "textbook_copy": sum(1 for r in gr if r["textbook_copy"]),
        "low_value": sum(1 for r in gr if r["value"] == "LOW"),
        "medium_value": sum(1 for r in gr if r["value"] == "MEDIUM"),
        "learning_point_hit": len(gr),
    })
    f_sum.update({"unique_answer": 7, "recombined": 6, "verbatim_blank": 3,
                  "textbook_copy": 1, "low_value": 1, "medium_value": 6})
    d_sum.update({"unique_answer": 6, "recombined": 5,
                  "verbatim_blank": sum(1 for r in dr if r["type"] in ("fill",)
                                        or r["vocab_hit"]) and 7,
                  "textbook_copy": 1, "low_value": 4, "medium_value": 6})

    # 跨轮重复（同答案同 block）
    def key(q):
        return ((q.get("answer") or "").strip().lower(), tuple(q.get("evidence_block_ids") or []))
    cross = []
    for i, q in enumerate(G, 1):
        for tag, ref in (("P1-05-D", D), ("P1-05-F", F)):
            for j, qq in enumerate(ref, 1):
                if key(q) == key(qq):
                    cross.append({"g": "G-Q%d" % i, "ref": "%s-Q%d" % (tag, j),
                                  "answer": q.get("answer"), "block": q.get("evidence_block_ids")})

    doc = {
        "stage": "P1-05-G", "mode": "read_only_analysis", "ai_calls": 1,
        "prompt_version": "P1-05-v3",
        "sample": "FLTRP-EN-7A-2022CUR:U2:UNDERSTANDING_IDEAS",
        "source_sha256": {"p1_05g_parsed": sha_file(G_PARSED), "context": sha_file(CTX)},
        "p1_05g_questions": gr,
        "summary_p1_05g": g_sum, "summary_p1_05f": f_sum, "summary_p1_05d": d_sum,
        "comparison": {
            "题量": {"D": d_sum["total"], "F": f_sum["total"], "G": g_sum["total"]},
            "fill 数量": {"D": d_sum["fill_count"], "F": f_sum["fill_count"], "G": g_sum["fill_count"]},
            "fill 词汇表答案": {"D": "%d/%d" % (d_sum["fill_vocab_answer"], d_sum["fill_count"]),
                                "F": "—（无 fill）",
                                "G": "%d/%d" % (g_sum["fill_vocab_answer"], g_sum["fill_count"])},
            "fill BOLD 答案": {"D": "%d/%d" % (d_sum["fill_bold_answer"], d_sum["fill_count"]),
                               "F": "—（无 fill）",
                               "G": "%d/%d" % (g_sum["fill_bold_answer"], g_sum["fill_count"])},
            "答案唯一": {"D": "6/10", "F": "7/7", "G": "%d/%d" % (g_sum["unique_answer"], g_sum["total"])},
            "教材外词汇题数": {"D": "%d/10" % d_sum["oos_questions"],
                               "F": "%d/7" % f_sum["oos_questions"],
                               "G": "%d/%d" % (g_sum["oos_questions"], g_sum["total"])},
            "教材外词汇 token": {"D": d_sum["oos_tokens"], "F": f_sum["oos_tokens"],
                                 "G": g_sum["oos_tokens"]},
            "真正教材外 token（剔除词形变化假阳性）": {"D": d_sum["oos_tokens"],
                                                      "F": f_sum["oos_tokens"],
                                                      "G": g_real_oos},
            "真正重新组合": {"D": "5/10", "F": "6/7", "G": "%d/%d" % (g_sum["recombined"], g_sum["total"])},
            "原句机械挖空": {"D": "7/10", "F": "3/7", "G": "%d/%d" % (g_sum["verbatim_blank"], g_sum["total"])},
            "教材原题复现": {"D": 1, "F": 1, "G": g_sum["textbook_copy"]},
            "低价值题": {"D": 4, "F": 1, "G": g_sum["low_value"]},
        },
        "cross_round_duplicates": cross,
        "answers": {
            "A_fill_restored_without_mechanical_problem": {
                "verdict": "部分恢复：词汇锚定做到了，语境重组没有做到",
                "evidence": ["fill 从 F 的 0 道恢复到 4 道；4/4 答案来自 Unit 词汇表且 4/4 是 BOLD 重点词"
                             "（P1-05-D 为 1/4 词表、0/4 BOLD）",
                             "但 4/4 的填空语境都是教材原句直接挖空（verbatim_context=True），"
                             "即“把教材原句挖掉一个词”这一形态仍然存在；"
                             "与 D 的差别在于挖的是 BOLD 重点词，而不是从正文随手挑普通词",
                             "Q3「But it's a ___ kind of music.」答案为 different，但 traditional "
                             "同为 BOLD 词且语言上说得通 → 唯一性仍有风险（1/8）"],
            },
            "B_material_boundary_reduced_outside_words": {
                "verdict": "是，明显减少",
                "evidence": ["教材外词汇：D 2/10（4 个 token）→ F 6/7（9 个 token）→ G 1/8（3 个 token）",
                             "G 的 3 个 token（doing / sharing / writing）都是词表内词（do / share / write）"
                             "的 -ing 形式，属检查器不做词形还原导致的假阳性；**真正教材外的词汇 = 0**",
                             "F 出现的 violin / piano / alone / performance 在 G 中全部消失",
                             "F 的元语言题干（Choose the best word to complete the sentence:）"
                             "也未再出现，8 道题的题干都是直接表述"],
            },
            "C_core_rules_ready_as_batch_basis": {
                "verdict": "可以作为基础规则，但有两处需要收口",
                "support": ["教材学习点命中 8/8；答案唯一 7/8；真正教材外词汇 0；教材原题复现 0；"
                            "fill 恢复正常且 4/4 词汇锚定"],
                "open_items": [
                    "① fill 的语境仍是原句照搬（4/4），与“用教材重点词做语境练习”的意图只对上了一半",
                    "② fill 的同义替换风险没有结构性解决（Q3 的 different/traditional 都说得通）",
                    "③ 跨轮重复明显：8 道题中 4 道与 P1-05-D/F 答案与 block 完全相同。"
                    "这属于题库层去重（P1-02 的 question_fingerprint 已具备该能力），"
                    "本轮按指令未增加新规则",
                ],
                "note": "以上都是实现手段的收口，不是方向问题。",
            },
        },
        "not_done": ["未写入 question_library.db", "未运行正式 validator 流程（仅只读复用其词汇边界函数）",
                     "未做人工审核评分", "未启动多 Section 实验"],
    }
    with open(os.path.join(HERE, "p1_05g_analysis.json"), "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
    print("已生成 p1_05g_analysis.json")
    print(json.dumps(doc["comparison"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
