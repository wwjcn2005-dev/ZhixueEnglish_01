"""P1-05-F · 只读分析：逐题判定 + 与 P1-05-D 对照统计。不调用 AI、不写题库。"""
import hashlib
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = r"D:\ZhixueEnglish"
SPIKE = os.path.join(BASE, "audit", "AI_question_generation_spike")
CTX = os.path.join(SPIKE, "P1_05_real_validation", "runs",
                   "01_Unit2_UNDERSTANDING_IDEAS_context.json")
F_PARSED = os.path.join(HERE, "p1_05f_parsed.json")
D_PARSED = os.path.join(SPIKE, "P1_05_budget_calibration_v2", "calibration_parsed.json")
sys.path.insert(0, os.path.join(SPIKE, "P1_04_rule_fixes"))
import validator_v3 as V3  # noqa: E402

# ------------------------------------------------------------------ P1-05-F 逐题人工判定
F_JUDGE = {
    1: dict(learning_point="electric guitar（BOLD 核心词 + 课文事实）", priority=3, value="MEDIUM",
            category="B_RECOMBINED", mechanical_blank=False, textbook_exercise_copy=False,
            unique=True, evidence_sufficient=True, issue="干扰项 violin / piano 不在教材词表或正文中"),
    2: dict(learning_point="课文重要事实：爷爷在公园和朋友拉二胡", priority=4, value="MEDIUM",
            category="B_RECOMBINED", mechanical_blank=False, textbook_exercise_copy=False,
            unique=True, evidence_sufficient=True, issue="与 P1-05-D 的 Q8 实质同题（跨轮重复）"),
    3: dict(learning_point="decide to take part in（BOLD 重点词 + 核心结构）", priority=3, value="MEDIUM",
            category="B_RECOMBINED", mechanical_blank=False, textbook_exercise_copy=False,
            unique=True, evidence_sufficient=True, issue="干扰项 alone 不在教材词表或正文中"),
    4: dict(learning_point="课文重要事实：演出后二人相视而笑", priority=4, value="MEDIUM",
            category="B_RECOMBINED", mechanical_blank=False, textbook_exercise_copy=False,
            unique=True, evidence_sufficient=True,
            issue="题干用词 performance 不在教材词表或正文中；该题型本批首次出现"),
    5: dict(learning_point="practice（BOLD 核心词）", priority=2, value="MEDIUM",
            category="B_RECOMBINED", mechanical_blank=True, textbook_exercise_copy=False,
            unique=True, evidence_sufficient=True, issue="题干含元语言 sentence / word（越界）"),
    6: dict(learning_point="instrument(s)（BOLD 核心词）", priority=2, value="LOW",
            category="A_DIRECT_REPRODUCTION", mechanical_blank=True, textbook_exercise_copy=True,
            unique=True, evidence_sufficient=True,
            issue="目标词 instruments 就是教材 a4 图表填空的同一个空，学习增量接近零；"
                  "干扰项 bands / guitars / stages 为复数形式且不在词表"),
    7: dict(learning_point="the sound of Grandpa’s erhu cuts in（教材 a5 语法聚焦例句中的 sound，BOLD）",
            priority=1, value="MEDIUM", category="B_RECOMBINED", mechanical_blank=True,
            textbook_exercise_copy=False, unique=True, evidence_sufficient=True,
            issue="题干含元语言 sentence / word（越界）"),
}


def sha_file(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest().upper()


def metrics(questions, ctx, judge=None):
    allow = V3.build_whitelist(ctx)
    vocab = {v["word"].lower(): v["emphasis"] for v in ctx["unit_vocabulary"]}
    bold = {w for w, e in vocab.items() if e == "BOLD"}
    out = []
    for i, q in enumerate(questions, 1):
        ans = (q.get("answer") or "").lower()
        vhit = [w for w in vocab if w in ans]
        bhit = [w for w in vhit if w in bold]
        rec = {"index": i, "type": q.get("type"), "answer": q.get("answer"),
               "blocks": [b.split(":")[-1] for b in (q.get("evidence_block_ids") or [])],
               "vocab_hit": vhit, "bold_hit": bhit,
               "out_of_scope": V3.out_of_scope(V3.checked_language(q), allow)}
        if judge:
            rec.update(judge[i])
        out.append(rec)
    return out


def main():
    ctx = json.load(open(CTX, encoding="utf-8"))
    F = json.load(open(F_PARSED, encoding="utf-8"))["questions"]
    D = json.load(open(D_PARSED, encoding="utf-8"))["questions"]
    fm = metrics(F, ctx, F_JUDGE)
    dm = metrics(D, ctx)

    def summarize(rows, judged):
        n = len(rows)
        s = {"total": n,
             "type_distribution": dict(Counter(r["type"] for r in rows)),
             "vocab_answer": sum(1 for r in rows if r["vocab_hit"]),
             "bold_answer": sum(1 for r in rows if r["bold_hit"]),
             "questions_with_out_of_scope": sum(1 for r in rows if r["out_of_scope"]),
             "out_of_scope_tokens": sorted({t for r in rows for t in r["out_of_scope"]}),
             "block_reuse": {k: v for k, v in Counter(
                 b for r in rows for b in r["blocks"]).items() if v > 1}}
        if judged:
            s.update({
                "learning_point_hit": sum(1 for r in rows if r.get("priority")),
                "priority_1to3": sum(1 for r in rows if r.get("priority") in (1, 2, 3)),
                "priority_4": sum(1 for r in rows if r.get("priority") == 4),
                "mechanical_blank": sum(1 for r in rows if r.get("mechanical_blank")),
                "textbook_exercise_copy": sum(1 for r in rows if r.get("textbook_exercise_copy")),
                "unique_answer": sum(1 for r in rows if r.get("unique")),
                "evidence_sufficient": sum(1 for r in rows if r.get("evidence_sufficient")),
                "recombined": sum(1 for r in rows if r.get("category") == "B_RECOMBINED"),
                "direct_reproduction": sum(1 for r in rows if r.get("category") == "A_DIRECT_REPRODUCTION"),
                "low_value": sum(1 for r in rows if r.get("value") == "LOW"),
                "high_value": sum(1 for r in rows if r.get("value") == "HIGH"),
                "medium_value": sum(1 for r in rows if r.get("value") == "MEDIUM"),
            })
        return s

    f_sum = summarize(fm, True)
    d_sum = summarize(dm, False)
    # P1-05-D 的对照项取自 P1-05-E 人工审阅
    d_review = json.load(open(os.path.join(SPIKE, "P1_05_manual_review",
                                           "p1_05_manual_review.json"), encoding="utf-8"))
    ds = d_review["stats"]
    d_sum.update({"unique_answer": ds["unique_answer_pass"],
                  "mechanical_blank": 7,                    # P1-05-E：Q1–Q7 都是原句挖空
                  "textbook_exercise_copy": 1,              # Q10 = 教材 a3 原题
                  "recombined": ds["B_recombined"],
                  "direct_reproduction": ds["A_direct_reproduction"],
                  "low_value": ds["learning_value_low"],
                  "medium_value": ds["learning_value_medium"],
                  "high_value": ds["learning_value_high"],
                  "learning_point_hit": None})

    doc = {
        "stage": "P1-05-F",
        "mode": "read_only_analysis",
        "ai_calls": 1,
        "prompt_version": "P1-05-v2",
        "sample": "FLTRP-EN-7A-2022CUR:U2:UNDERSTANDING_IDEAS",
        "source_sha256": {"p1_05f_parsed": sha_file(F_PARSED), "context": sha_file(CTX)},
        "p1_05f_questions": fm,
        "p1_05d_questions": dm,
        "summary_p1_05f": f_sum,
        "summary_p1_05d": d_sum,
        "comparison": {
            "questions": {"p1_05d": d_sum["total"], "p1_05f": f_sum["total"]},
            "fill_questions": {"p1_05d": d_sum["type_distribution"].get("fill", 0),
                               "p1_05f": f_sum["type_distribution"].get("fill", 0)},
            "vocab_answer_rate": {"p1_05d": "%d/%d" % (d_sum["vocab_answer"], d_sum["total"]),
                                  "p1_05f": "%d/%d" % (f_sum["vocab_answer"], f_sum["total"])},
            "bold_answer_rate": {"p1_05d": "%d/%d" % (d_sum["bold_answer"], d_sum["total"]),
                                 "p1_05f": "%d/%d" % (f_sum["bold_answer"], f_sum["total"])},
            "mechanical_blank": {"p1_05d": "%d/%d" % (d_sum["mechanical_blank"], d_sum["total"]),
                                 "p1_05f": "%d/%d" % (f_sum["mechanical_blank"], f_sum["total"])},
            "textbook_exercise_copy": {"p1_05d": d_sum["textbook_exercise_copy"],
                                       "p1_05f": f_sum["textbook_exercise_copy"]},
            "unique_answer": {"p1_05d": "%d/%d" % (d_sum["unique_answer"], d_sum["total"]),
                              "p1_05f": "%d/%d" % (f_sum["unique_answer"], f_sum["total"])},
            "recombined": {"p1_05d": "%d/%d" % (d_sum["recombined"], d_sum["total"]),
                           "p1_05f": "%d/%d" % (f_sum["recombined"], f_sum["total"])},
            "out_of_scope_questions": {
                "p1_05d": "%d/%d" % (d_sum["questions_with_out_of_scope"], d_sum["total"]),
                "p1_05f": "%d/%d" % (f_sum["questions_with_out_of_scope"], f_sum["total"])},
            "low_value": {"p1_05d": d_sum["low_value"], "p1_05f": f_sum["low_value"]},
        },
        "new_findings": [
            {"id": "G1", "severity": "REGRESSION",
             "title": "fill 题型被规则整体判死（4 → 0）",
             "detail": ("P1-05-v2 里针对 fill 的两条约束（答案必须唯一、机械挖空价值低）"
                        "让模型完全不再生成填空题。但填空正是教材 a4 / a6 / a7 的主要练习形态，"
                        "等于把最重要的一类练习从产出中移除。"),
             "suggested": "把 fill 的设计改为「限定词库的语境填空」或要求答案取自 unit_vocabulary，"
                          "而不是简单要求模型少出 fill"},
            {"id": "G2", "severity": "REGRESSION",
             "title": "新提示词下出现教材外干扰词与元语言题干",
             "detail": ("Q1 的 violin / piano、Q3 的 alone、Q4 的 performance 都不在 Unit 2 词表或正文中；"
                        "Q5/Q6/Q7 的题干引入了 “Choose the best word to complete the sentence:”，"
                        "其中 sentence / word 同样是越界词。用 validator v3 的词汇边界检查（只读）"
                        "复算：P1-05-F 有 6/7 道题会因词汇越界被判 FAIL，而 P1-05-D 只有 2/10。"),
             "suggested": "在提示词里明确禁止在题干中加入指令式元语言，并限定干扰项只能取自本单元词表"},
            {"id": "G3", "severity": "IMPROVE",
             "title": "block 复用更集中",
             "detail": "P1-05-F 的 Q3 / Q5 / Q6 共用 block P38:B3（3 次）；P1-05-D 是 3 个 block 各 2 次。",
             "suggested": "同一 Section 内对同一 block 的复用设上限（例如 ≤2），并要求先覆盖未使用的重点词"},
            {"id": "G4", "severity": "OBSERVE",
             "title": "跨轮重复",
             "detail": "P1-05-F 的 Q2 与 P1-05-D 的 Q8 是同一道题（同 block、同答案、四个选项中三个相同）；"
                       "Q1 与 P1-05-D 的 Q5 也都在考 electric guitar 这一件事。",
             "suggested": "正式实验应跨轮做 fingerprint 去重（P1-02 的 question_fingerprint 已具备该能力）"},
        ],
        "key_question": {
            "question": "把教材学习重点、词汇表、短句作为出题核心，再让 AI 利用课文语境重新组合，"
                        "是否比单纯把整章文本交给 AI 自由生成更符合本项目要求？",
            "answer": "是，方向明确更符合要求；但本轮同时暴露两个新问题，需要一并修正。",
            "supporting": [
                "答案不唯一的填空题从 4/10 降到 0/7 —— P1-05-E 认定的 BLOCKER（F1）在 v2 下没有复现",
                "原句机械挖空从 7/10 降到 3/7；教材词表答案占比从 50% 升到 57%，BOLD 占比从 40% 升到 57%",
                "不再从正文随手挑普通词出题（P1-05-D 的 autumn / great / Rock music / Beijing opera 这类答案消失）",
                "教材原题复现没有增加（D 1 道主旨原题 → F 1 道教材图表原词），且新增了 reading_judge 题型",
                "7/7 都能对应到一个教材学习点（5 道命中词汇表/重点结构，2 道命中课文重要事实）",
            ],
            "counter_evidence": [
                "fill 题型被整体判死（4 → 0），而填空是教材最主要的练习形态",
                "词汇越界题从 2/10 升到 6/7（干扰词与题干元语言）",
                "同一 block 复用更集中（B38:B3 被用 3 次）",
                "与 P1-05-D 存在跨轮重复题",
            ],
            "conclusion": ("v2 的“学习点优先”方向是对的，且确实修掉了 P1-05-E 的 BLOCKER（填空答案不唯一）；"
                           "但 v2 的措辞把 fill 逼死、并让模型开始使用教材外用词。"
                           "下一版应在保留“学习点优先”的同时，明确 fill 的合法形态与用词边界。"),
        },
        "not_done": ["未写入 question_library.db", "未运行正式 validator 流程（仅只读复用其词汇边界函数）",
                     "未做人工审核评分", "未生成第二版题目", "未启动多 Section 实验"],
    }
    with open(os.path.join(HERE, "p1_05f_analysis.json"), "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
    print("已生成 p1_05f_analysis.json")
    print(json.dumps(doc["comparison"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
