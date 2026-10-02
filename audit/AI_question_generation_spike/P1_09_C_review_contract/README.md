# P1-09-C · AI 英语质量复核输入契约与判定口径设计

阶段结论：**P1-09-C_DESIGN_PASS**（纯设计，AI 调用 = 0）

```text
AI 调用 0 · 新题 0 · question_library.db 0 修改 · learning.db 0 修改
contentpack / 教材 PDF / 54 MP3 / Web / Android 0 修改
validator v2/v3 0 修改 · reviewer_prompt.py 0 修改 · V1.0 / V1.3 / V2.0 0 修改
未建表 · 未改 schema · 未接入学习流程 · 未做 UI · 未自动 APPROVED / ACTIVE
```

## 本目录内容

| 文件 | 说明 |
| --- | --- |
| `p1_09_c_report.md` | 主报告：只读机制审计（10 问）、问题 A/B 的解决、离线重判、样本计划、13 条验收 |
| `review_context_contract_v1.md` | **输入契约**：三层职责、必须给/禁止给、Minimal / Extended、`CONTEXT_INSUFFICIENT` |
| `answer_uniqueness_contract_v1.md` | **唯一性契约**：两种作答标准、四类判定、六步确定性程序、四种输出 |
| `quality_dimensions_contract_v1.md` | **六维判定契约**：判断对象 / 能做 / 不能做 / PASS-CONCERN-FAIL / 误判风险 |
| `offline_case_analysis.json` | 问题 A 根因（摘录 vs 证据块全文）、全库摘录截断规模、`B6463523F9E5` 等 7 题的新口径重判 |
| `offline_context_probe.json` | 10 道样本可取得的教材信息、证据块邻域、关键术语在 Section 中的位置 |
| `minimal_extended_context_costs.json` | Minimal / Extended / 整章三级上下文的逐题与合计成本 |
| `audit_context.py` / `context_levels.py` / `offline_case_analysis.py` | 只读审计脚本（全部使用 `?mode=ro` 连接，不写任何数据库） |

## 核心结论

```text
问题 A（evidence_concern 误报）
  根因：question_evidence.evidence_quote 只是证据块的一段摘录
        （AIQ:6ECD02B9D381：摘录 48 字符，证据块全文 202 字符，而 "art festival" 就在同一块里）
  规模：全库 22 条 evidence 中 18 条的 quote 短于证据块全文
  修法：Review Context Contract V1 的 Minimal 级改为给**证据块全文**（169.9 tok/题，题目部分 1.65×）
        整章输入被明确拒绝（31×）

问题 B（唯一性口径不一致）
  根因：同一个现象被两个标准判过（课文陈述 vs 现实常识），导致 FP/FN 无共同基准
  修法：Answer Uniqueness Contract V1 —— 先声明 TEXTBOOK_ANCHORED / SELF_CONTAINED，
        再按 A/B/C/D 四类判定；现实常识层面的候选明确排除在唯一性之外
  结果：AIQ:B6463523F9E5 判 UNIQUE（旧标签重映射为 NOT_A_UNIQUENESS_ISSUE）
        同时 4 道题判 UNIQUE_RISK（与 P1-08-C 人工观察、P1-09-B 判断方向一致）

机械复现：程序结果 = hard fact，AI 结果 = quality observation；不一致不自动覆盖，进入人工复核信息
```

## 重新运行（只读，不调用 AI）

```powershell
python -X utf8 -B audit\AI_question_generation_spike\P1_09_C_review_contract\audit_context.py
python -X utf8 -B audit\AI_question_generation_spike\P1_09_C_review_contract\context_levels.py
python -X utf8 -B audit\AI_question_generation_spike\P1_09_C_review_contract\offline_case_analysis.py
python -X utf8 -B audit\AI_question_generation_spike\P1_09_C_review_contract\protect_snapshot.py before
python -X utf8 -B audit\AI_question_generation_spike\P1_09_C_review_contract\protect_snapshot.py after
python -X utf8 -B audit\AI_question_generation_spike\P1_09_C_review_contract\protect_compare.py
```
