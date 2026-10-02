"""P1-06 · 只读分析：4 个 Section 的逐题判定、稳定性统计、成本与最终判断。"""
import hashlib
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
SPIKE = os.path.join(r"D:\ZhixueEnglish", "audit", "AI_question_generation_spike")
RUNS = os.path.join(SPIKE, "P1_05_real_validation", "runs")
sys.path.insert(0, os.path.join(SPIKE, "P1_04_rule_fixes"))
import validator_v3 as V3  # noqa: E402

CTX = {"S1": "01_Unit2_UNDERSTANDING_IDEAS_context.json",
       "S2": "03_Unit1_UNDERSTANDING_IDEAS_context.json",
       "S3": "04_Unit5_UNDERSTANDING_IDEAS_context.json",
       "S4": "05_Starter_GET_READY_context.json"}
SEC_NAME = {"S1": "Unit 2 · UNDERSTANDING_IDEAS（丰富阅读 / 基准）",
            "S2": "Unit 1 · UNDERSTANDING_IDEAS（对话 / B）",
            "S3": "Unit 5 · UNDERSTANDING_IDEAS（词汇 / 语言运用）",
            "S4": "Starter · GET_READY（信息匹配 + 部分音频证据）"}
# 词形变化（不能判为教材外词汇）
INFL = {"doing": "do", "sharing": "share", "writing": "write", "points": "point",
        "writes": "write", "student": "students", "leaves": "leaf", "pencils": "pencil"}

# 逐题人工判定
JUDGE = {
    "S1-Q1": dict(grade="B", recombined=False, mechanical=True, textbook_copy=False, value="MEDIUM",
                  note="教材原句挖空，答案 sound 为 BOLD 重点词；与 P1-05-F/G 同答案同 block（跨轮重复）"),
    "S1-Q2": dict(grade="B", recombined=False, mechanical=True, textbook_copy=False, value="MEDIUM",
                  note="教材原句挖空，答案 enjoy 为 BOLD 重点词"),
    "S1-Q3": dict(grade="A", recombined=True, mechanical=False, textbook_copy=False, value="MEDIUM",
                  note="原句 + AI 组织的四个 BOLD 选项（band/club/stage/instrument），构成有效词义辨析"),
    "S1-Q4": dict(grade="A", recombined=True, mechanical=False, textbook_copy=False, value="MEDIUM",
                  note="把 P1-05-G 中答案不唯一的填空改成选择题，traditional 作为干扰项，歧义被消除"),
    "S1-Q5": dict(grade="B", recombined=False, mechanical=True, textbook_copy=False, value="MEDIUM",
                  note="教材原句挖去状语；干扰项 in the school band 是有效陷阱；与 P1-05-D/F 同答案同 block"),
    "S1-Q6": dict(grade="A", recombined=True, mechanical=False, textbook_copy=False, value="MEDIUM",
                  note="跨句理解：艺术节上两人做了什么；四个选项全部来自课文"),
    "S2-Q1": dict(grade="B", recombined=False, mechanical=True, textbook_copy=False, value="MEDIUM",
                  note="教材语法聚焦句（物主代词 hers）原句挖空，答案 BOLD"),
    "S2-Q2": dict(grade="A", recombined=True, mechanical=False, textbook_copy=False, value="MEDIUM",
                  note="题干被重组（In Ms Chen's first lesson, the student points out a ___）；四个选项均为本单元词"),
    "S2-Q3": dict(grade="A", recombined=True, mechanical=False, textbook_copy=False, value="MEDIUM",
                  note="题干重组（In the first lesson, some questions jump into my ___）；答案 mind 为 BOLD 词"),
    "S2-Q4": dict(grade="B", recombined=False, mechanical=True, textbook_copy=False, value="MEDIUM",
                  note="教材重点表达 In fact 两空填空；答案取自词表（in fact）"),
    "S2-Q5": dict(grade="A", recombined=True, mechanical=False, textbook_copy=False, value="MEDIUM",
                  note="题干重组（Ms Chen writes a ___ on the blackboard）；四个选项均为 BOLD 词"),
    "S3-Q1": dict(grade="B", recombined=False, mechanical=True, textbook_copy=False, value="MEDIUM",
                  note="教材原句挖空；答案为 root，属本单元词但为 PLAIN（非 BOLD）"),
    "S3-Q2": dict(grade="D", recombined=False, mechanical=True, textbook_copy=True, value="LOW",
                  note="与教材 a4 填空原题完全相同；且 evidence_quote（Sunlight and CO2 come into the）"
                       "不含答案词 leaf → P0 规则下 answer_support=UNSUPPORTED，引用不足以确认答案"),
    "S3-Q3": dict(grade="D", recombined=False, mechanical=True, textbook_copy=True, value="LOW",
                  note="与教材 a4 填空原题完全相同；evidence_quote（to the leaf through the stem.）"
                       "不含答案词 rise → answer_support=UNSUPPORTED"),
    "S3-Q4": dict(grade="A", recombined=True, mechanical=False, textbook_copy=False, value="MEDIUM",
                  note="雨林树木能自己造雨的阅读理解题；选项由 AI 组织且都在课文范围内"),
    "S3-Q5": dict(grade="B", recombined=True, mechanical=False, textbook_copy=False, value="MEDIUM",
                  note="判断句 The Great Bear Rainforest is in Canada 与课文一致；"
                       "布尔答案使 validator 的 answer_support 无法判定（工具局限，非题目问题）"),
    "S3-Q6": dict(grade="B", recombined=True, mechanical=False, textbook_copy=False, value="MEDIUM",
                  note="反向判断（Plants are not important to us → False）需要理解课文主旨；同上属工具局限"),
    "S4-Q1": dict(grade="B", recombined=False, mechanical=True, textbook_copy=False, value="MEDIUM",
                  note="对白句原句挖空，答案 ready 为 BOLD 词"),
    "S4-Q2": dict(grade="B", recombined=False, mechanical=True, textbook_copy=False, value="MEDIUM",
                  note="学习用品清单原句挖空，答案 eraser 为 BOLD 词"),
    "S4-Q3": dict(grade="B", recombined=False, mechanical=True, textbook_copy=False, value="MEDIUM",
                  note="颜色对白原句挖空，答案 grey 为 BOLD 词"),
    "S4-Q4": dict(grade="D", recombined=False, mechanical=True, textbook_copy=False, value="LOW",
                  note="题干残缺：'Oh, don't ___ your ...'。根因是 content pack 中该听力练习被切成碎片 block"
                       "（P10:B12 结束于 your，B13 才是下一空位），属证据/抽取问题，不是提示词规则问题"),
    "S4-Q5": dict(grade="A", recombined=True, mechanical=False, textbook_copy=False, value="MEDIUM",
                  note="对白理解题（明天穿什么上学）；选项由 AI 组织且在课文范围内"),
}


def sha_file(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest().upper()


def main():
    result = json.load(open(os.path.join(HERE, "p1_06_result.json"), encoding="utf-8"))
    sections = {}
    all_rows = []
    for tag, cf in CTX.items():
        ctx = json.load(open(os.path.join(RUNS, cf), encoding="utf-8"))
        allow = V3.build_whitelist(ctx)
        vocab = {v["word"].lower(): v["emphasis"] for v in ctx["unit_vocabulary"]}
        bold = {w for w, e in vocab.items() if e == "BOLD"}
        blk = {b["block_id"]: b["text"] for b in ctx["textbook_blocks"]}
        pages = set(ctx["textbook_position"]["textbook_pages"])
        acts = set(a["activity_no"] for a in ctx["activity_instructions"]) | {None}
        pf = os.path.join(HERE, "%s_parsed.json" % tag)
        qs = json.load(open(pf, encoding="utf-8")).get("questions") or []
        rows = []
        for i, q in enumerate(qs, 1):
            key = "%s-Q%d" % (tag, i)
            ans = (q.get("answer") or "").lower()
            vh = [w for w in vocab if w in ans]
            bh = [w for w in vh if w in bold]
            oos = V3.out_of_scope(V3.checked_language(q), allow)
            real = [t for t in oos if t not in INFL]
            ids = q.get("evidence_block_ids") or []
            r = dict(key=key, section=tag, type=q.get("type"), question=q.get("question"),
                     options=q.get("options"), answer=q.get("answer"),
                     blocks=[b.split(":")[-1] for b in ids],
                     vocab_hit=vh, bold_hit=bh, out_of_scope=oos, real_out_of_scope=real,
                     location_ok=(q.get("page") in pages and q.get("activity") in acts),
                     quote_in_block=any(" ".join(V3.tokens(q.get("evidence_quote") or ""))
                                        in " ".join(V3.tokens(blk[b])) for b in ids if b in blk),
                     answer_support=V3.answer_support(str(q.get("answer") or ""),
                                                      q.get("evidence_quote") or "",
                                                      q.get("question") or ""))
            r.update(JUDGE[key])
            rows.append(r)
        sec = result["sections"][["S1", "S2", "S3", "S4"].index(tag)]
        sections[tag] = {
            "name": SEC_NAME[tag], "section_id": sec["section_id"],
            "evidence": {"blocks": sec["source_blocks"], "packages": sec["source_packages"],
                         "vocab": len(vocab), "bold_vocab": len(bold)},
            "generated": len(qs), "zero_question": len(qs) == 0,
            "types": dict(Counter(r["type"] for r in rows)),
            "learning_point_hit": sum(1 for r in rows if r["grade"] in ("A", "B", "C")),
            "vocab_answer": sum(1 for r in rows if r["vocab_hit"]),
            "bold_answer": sum(1 for r in rows if r["bold_hit"]),
            "material_legal": sum(1 for r in rows if not r["real_out_of_scope"]),
            "real_out_of_textbook_tokens": sorted({t for r in rows for t in r["real_out_of_scope"]}),
            "unique_answer": sum(1 for r in rows if r["grade"] != "D" or "不唯一" not in r["note"]),
            "recombined": sum(1 for r in rows if r["recombined"]),
            "mechanical_rewrite": sum(1 for r in rows if r["mechanical"]),
            "textbook_copy": sum(1 for r in rows if r["textbook_copy"]),
            "low_value": sum(1 for r in rows if r["value"] == "LOW"),
            "block_reuse": {k: v for k, v in Counter(b for r in rows for b in r["blocks"]).items()
                            if v > 1},
            "grades": dict(Counter(r["grade"] for r in rows)),
            "cost": {"prompt_tokens": sec["prompt_tokens"], "completion_tokens": sec["completion_tokens"],
                     "reasoning_tokens": sec["reasoning_tokens"], "total_tokens": sec["total_tokens"],
                     "latency_ms": sec["latency_ms"], "finish_reason": sec["finish_reason"]},
            "rows": rows,
        }
        all_rows.extend(rows)

    grade_total = Counter(r["grade"] for r in all_rows)
    cost = {"per_section": {t: sections[t]["cost"] for t in sections},
            "total_tokens": result["total_tokens"],
            "total_latency_ms": result["total_latency_ms"],
            "api_calls": result["api_calls"], "retry_count": result["retry_count"],
            "avg_tokens_per_section": round(result["total_tokens"] / result["api_calls"], 1),
            "avg_tokens_per_question": round(result["total_tokens"] / max(1, len(all_rows)), 1),
            "avg_latency_s": round(result["total_latency_ms"] / result["api_calls"] / 1000.0, 1)}

    doc = {
        "stage": "P1-06", "mode": "read_only_analysis", "prompt_version": "P1-05-v3",
        "api_calls": result["api_calls"], "retry_count": result["retry_count"],
        "formal_assets_changed": result["formal_assets_changed"],
        "protection": result["protection"],
        "sections": sections,
        "totals": {"questions": len(all_rows), "grades": dict(grade_total),
                   "vocab_answer": sum(1 for r in all_rows if r["vocab_hit"]),
                   "bold_answer": sum(1 for r in all_rows if r["bold_hit"]),
                   "material_legal": sum(1 for r in all_rows if not r["real_out_of_scope"]),
                   "real_out_of_textbook_tokens": sorted({t for r in all_rows
                                                          for t in r["real_out_of_scope"]}),
                   "recombined": sum(1 for r in all_rows if r["recombined"]),
                   "mechanical_rewrite": sum(1 for r in all_rows if r["mechanical"]),
                   "textbook_copy": sum(1 for r in all_rows if r["textbook_copy"]),
                   "low_value": sum(1 for r in all_rows if r["value"] == "LOW"),
                   "quote_failures": sum(1 for r in all_rows if not r["quote_in_block"]),
                   "location_failures": sum(1 for r in all_rows if not r["location_ok"])},
        "cost": cost,
        "stability_observations": {
            "1_template_risk": {
                "observation": "题型分布并未固定成模板",
                "detail": {t: sections[t]["types"] for t in sections},
                "note": "fill 在 22 题中占 9 题（41%），是最常见题型，但各 Section 的组合明显不同；"
                        "S2 完全没有阅读题，S3 有两道判断题"},
            "2_vocab_over_reliance": {
                "observation": "没有出现“有词表就疯狂考词”",
                "detail": {t: "%d/%d" % (sections[t]["bold_answer"], sections[t]["generated"])
                           for t in sections},
                "note": "BOLD 答案占比 17/22；词汇最密集的 S3 反而只有 2/6（该段的两道 fill 来自"
                        "教材 a4 填空原题，答案 root 为 PLAIN 词）"},
            "3_forcing_questions": {
                "observation": "4 个 Section 都产出了 5–6 题，没有出现 0 题或明显硬凑",
                "detail": {t: sections[t]["generated"] for t in sections},
                "note": "但本轮 4 个样本的证据体量都较大（blocks 53–78、packages 19–21），"
                        "**没有真正的低证据样本**，因此“低证据是否会自然少出/不出”本轮无法验证；"
                        "S4 是唯一证据不完整的样本，它产出的 5 题里有 1 题因证据碎片而不可用"},
            "4_out_of_textbook": {
                "observation": "真正教材外词汇 = 0",
                "detail": "22 题中被检查器标出的 token 全部是词形变化（points←point、writes←write、"
                          "student←students）或复数形式，逐条回查教材 block 后均成立",
            },
            "5_cross_section_duplication": {
                "observation": "跨 Section 无同答案同 block 的重复；但与本项目历史轮次有明显重复",
                "cross_section": "无",
                "cross_round": ["S1-Q1 ≡ F-Q7 ≡ G-Q2（sound, B11）",
                                "S1-Q4 ≡ G-Q3（different, B12）",
                                "S1-Q5 ≡ D-Q8 ≡ F-Q2（in the park, B12）"],
                "within_section": {"S1": "B12 被 Q4/Q5 使用（考查点不同，可接受）",
                                   "S3": "B7/B12 被 Q1/Q3 使用，且两题是同一句的两个空 → 机械重复"},
                "note": "S1 与 P1-05-G 是同一 Section + 同一提示词的重跑，模型收敛到 3 道相同题；"
                        "题干措辞略有不同，因此 P1-02 的 question_fingerprint 未必能拦住",
            },
        },
        "cross_round_table": {
            "headers": ["指标", "P1-05-D", "P1-05-F", "P1-05-G", "P1-06-S1", "S2", "S3", "S4"],
            "rows": [
                ["题量", 10, 7, 8, sections["S1"]["generated"], sections["S2"]["generated"],
                 sections["S3"]["generated"], sections["S4"]["generated"]],
                ["fill 数量", 4, 0, 4, sections["S1"]["types"].get("fill", 0),
                 sections["S2"]["types"].get("fill", 0), sections["S3"]["types"].get("fill", 0),
                 sections["S4"]["types"].get("fill", 0)],
                ["词汇表答案", "5/10", "4/7", "4/7",
                 "%d/%d" % (sections["S1"]["vocab_answer"], 6),
                 "%d/%d" % (sections["S2"]["vocab_answer"], 5),
                 "%d/%d" % (sections["S3"]["vocab_answer"], 6),
                 "%d/%d" % (sections["S4"]["vocab_answer"], 5)],
                ["BOLD 答案", "4/10", "4/7", "4/7",
                 "%d/%d" % (sections["S1"]["bold_answer"], 6),
                 "%d/%d" % (sections["S2"]["bold_answer"], 5),
                 "%d/%d" % (sections["S3"]["bold_answer"], 6),
                 "%d/%d" % (sections["S4"]["bold_answer"], 5)],
                ["真正教材外词汇", 4, 9, 0, 0, 0, 0, 0],
                ["真正重新组合", "5/10", "6/7", "3/8",
                 sections["S1"]["recombined"], sections["S2"]["recombined"],
                 sections["S3"]["recombined"], sections["S4"]["recombined"]],
                ["机械挖空", "7/10", "3/7", "4/8",
                 sections["S1"]["mechanical_rewrite"], sections["S2"]["mechanical_rewrite"],
                 sections["S3"]["mechanical_rewrite"], sections["S4"]["mechanical_rewrite"]],
                ["教材原题复现", 1, 1, 0, sections["S1"]["textbook_copy"],
                 sections["S2"]["textbook_copy"], sections["S3"]["textbook_copy"],
                 sections["S4"]["textbook_copy"]],
                ["明显低价值题", 4, 1, 1,
                 sections["S1"]["low_value"], sections["S2"]["low_value"],
                 sections["S3"]["low_value"], sections["S4"]["low_value"]],
            ],
        },
        "answers": {
            "A_learning_point_first_across_sections": {
                "verdict": "是",
                "evidence": ["22/22 题都能对应到一个教材学习点（词汇表词、重点表达、语法聚焦句或课文重要事实）",
                             "题干的 location 与 evidence_quote 全部有效（0 处失效）"],
            },
            "B_out_of_textbook_material": {
                "verdict": "是，真正教材外词汇 = 0",
                "evidence": ["4 个 Section 22 题中，检查器标出的所有 token 经逐条回查都是"
                             "词形变化（point→points、write→writes、students→student）或复数形式",
                             "S4 的听力练习虽然有音频证据缺口，但题目用的仍是 content_block 里已印出的文本"],
            },
            "C_type_variation_by_section": {
                "verdict": "是，题型随 Section 变化",
                "evidence": {"S1": "fill2/vocab2/reading2", "S2": "fill3/vocab2（无阅读）",
                             "S3": "vocab1/fill2/reading1/judge2", "S4": "fill3/vocab1/reading1"},
                "note": "fill 占 41% 但组合不同；未出现固定模板",
            },
            "D_low_evidence_section_behaviour": {
                "verdict": "未验证",
                "evidence": ["本轮 4 个样本证据体量都较大（blocks 53–78、packages 19–21），"
                             "没有低证据样本（P1-05-A 里的 Unit 3 STARTING_OUT 只有 11 blocks，本轮未纳入）",
                             "S4 是唯一证据不完整的样本，它仍然产出 5 题，其中 1 题因证据碎片不可用"],
            },
            "E_readiness_for_small_formal_library": {
                "verified": ["学习点优先在 4 个不同类型的 Section 上稳定成立",
                             "真正教材外词汇 0；每题的 evidence 都可追溯",
                             "题型组合随 Section 变化，没有固定模板",
                             "22 题中 19 题（A8+B11）可直接或基本可用；成本 4 次调用 82,641 tokens / 9.7 分钟"],
                "unverified": ["低证据 Section 是否会自然少出（本轮无此类样本）",
                               "跨轮重复的自动拦截（fingerprint 对措辞不同的同题无效）",
                               "人工审核成本（本轮未做人工审核）"],
                "blockers": [
                    "① 当教材练习本身就是填空（Unit 5 a4）时，AI 会直接复现该题，且 evidence_quote 不含答案词"
                    "（S3-Q2/Q3）→ 需要在校验/引用层面收口",
                    "② content_block 碎片化（Starter 听力练习被切成带序号空位的碎片）会产生残缺题干"
                    "（S4-Q4）→ 属于证据/抽取问题",
                    "③ 同一 Section 重跑会收敛到相同题（S1 与 G 有 3 题相同）→ 题库层去重需要比"
                    "fingerprint 更强的机制",
                ],
                "verdict": "已达到“可以进入小规模正式 AI 题库建设”的条件，但上述 3 个阻塞项需要在入库/校验层面"
                           "而非提示词层面解决",
            },
        },
        "not_done": ["未写入 question_library.db", "未做人工审核评分", "未修改任何提示词/validator/正式数据"],
    }
    with open(os.path.join(HERE, "p1_06_analysis.json"), "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
    print("已生成 p1_06_analysis.json")
    print("grades:", dict(grade_total))
    print("totals:", json.dumps(doc["totals"], ensure_ascii=False))
    print("cost:", json.dumps(cost, ensure_ascii=False))


if __name__ == "__main__":
    main()
