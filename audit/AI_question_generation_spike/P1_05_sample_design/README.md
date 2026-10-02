# P1-05-A · AI 题库多 Section 小规模质量验证——设计与样本审计

最终状态：**DESIGN_PASS**

本轮是**实验设计阶段**：**AI 调用 0**，未生成任何题目，未修改任何正式数据。

---

## 一句话结论

当前机制**值得进入小规模真实验证**，并已冻结包含 **7 个 Section** 的 P1-05-B 实验方案。

三条纪律同时冻结：

1. **题量不设配额**——有合适的就多生成，没有就少生成，0 题是合法结果；
2. **听力证据缺口单列**，不混入普通题目质量评价；
3. **这是工程质量小样本验证**，不能推断整本教材的总体质量。

---

## 选中的 7 个 Section（定向选择，非随机）

| # | Section | 类别 | blocks | 证据包 | 原题 | 词汇/加粗 | 密度 | 主要实验风险 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Unit 2 · UNDERSTANDING_IDEAS | A 阅读 | 83 | 21 | 21 | 21 / 19 | high | `RICH_READING` |
| 2 | Unit 6 · READING_FOR_WRITING | A 阅读 | 54 | 12 | 12 | 16 / 11 | high | `RICH_READING` `DISTRACTOR_RISK` |
| 3 | Unit 1 · UNDERSTANDING_IDEAS | B 对话（直接引语） | 55 | 19 | 19 | 14 / 12 | high | `HIGH_DUPLICATION_RISK` |
| 4 | Unit 5 · UNDERSTANDING_IDEAS | C 词汇/语言运用 | 77 | 21 | 21 | **23 / 17** | high | `VOCABULARY_SCOPE` |
| 5 | Starter · GET_READY | D 信息匹配/判断 | 77 | 21 | 21 | 15 / 10 | high | `PARTIAL_AUDIO_SCOPE` `LISTENING_EVIDENCE_GAP` |
| 6 | Unit 3 · STARTING_OUT | E 低证据密度 | 11 | 4 | 4 | 0 / 0 | **low** | `LOW_EVIDENCE` |
| 7 | Unit 1 · DEVELOPING_IDEAS | F 听力缺口对照 | 62 | 14 | 14 | 8 / 8 | high | `LISTENING_EVIDENCE_GAP`（**不计入质量分母**） |

类别覆盖：阅读 ≥2 ✔、对话 ≥1 ✔、词汇/语言运用 ≥1 ✔、信息匹配 ≥1 ✔、
低证据密度 ≥1 ✔、听力缺口对照 1 ✔。

---

## P1-05-B 冻结要点

```text
生成单元        Section（保留 Activity 级 provenance）
validator       P1-04 的 validator_v3（v2 保持冻结）
模型            deepseek-v4-pro（不使用本地 Qwen / 其他 AI）
prompt_version  P1-05-v1 = P0-v1 去掉"最多 3 题"配额，其余逐字不变
调用纪律        每个 Section 一条 generation_run；默认 0 重试
                （仅 HTTP 层失败且无 content 时允许 1 次重试并记录 retry_count）
入库状态        一律 GENERATED → VALIDATED → PENDING_REVIEW，不得 ACTIVE
题型            fill / vocab_choice / reading_choice / reading_judge
```

### §十三 风险的具体观察方式

每题额外记录 **`printed_option_overlap`**：正确答案文本是否出现在该 Section 教材原题
打印的选项文本中。命中即为"教材印了答案"的风险题，进入人工重点复核。

---

## 人工审核

每题只做 6 个判断 + 1 个归类：

```text
① 教材依据 PASS/FAIL    ② 答案明确 PASS/FAIL    ③ 题目自然 PASS/FAIL
④ 独立学习价值 PASS/FAIL ⑤ 是否重复 PASS/FAIL    ⑥ 是否超范围 PASS/FAIL
最终：APPROVE / REJECT_CONTENT / REJECT_QUALITY / REJECT_SCOPE
```

审核界面**不得显示** `model` / `prompt_version` / `context_hash` / `generation_run_id` /
`validator_version` / `evidence_block_id` / `question_fingerprint`。

---

## 成功判据（六问）

| # | 问题 | 通过条件摘要 |
| --- | --- | --- |
| A | 机制能否稳定阻止明显错误题 | 已入库题 0 道 `REJECT_CONTENT`；validator FAIL 的题确实未入库 |
| B | AI 能否做到"有价值才生成" | 至少 1 个 Section 自然产出 0 题；无"凑数题" |
| C | APPROVE 比例是否够继续 | `Natural Value Rate ≥ 60%` 且 APPROVE ≥ 5 |
| D | 不同 Section 是否表现出差异 | 题量分布不是常数，且差异可由证据密度解释 |
| E | 成本与延迟是否可接受 | 单次 ≤ 180 s；7 次总耗时 ≤ 30 min；无失败调用 |
| F | 是否暴露必须先修的机制问题 | 未触发 S1–S8 任一条 |

**停止条件 S1–S8**（任一触发即停并修机制）：已入库题出现 `REJECT_CONTENT`、
教材外事实未被拦截、出现 `ACTIVE` 或伪造审批、跨库悬空引用、正式资产被改、
validator 误报、单次调用 > 300 s、出现凑数低价值题。

完整判据见 `p1_05_acceptance_criteria.md`（执行期间不得放宽）。

---

## 产物

| 文件 | 说明 |
| --- | --- |
| `README.md` | 本索引 |
| `p1_05_sample_design_report.md` | 完整设计报告（含 10 项必答内容） |
| `p1_05_sample_matrix.json` | 7 个样本的证据矩阵 + 字段定义 + 听力缺口排除说明 |
| `p1_05_human_review_template.md` | 人工审核表 |
| `p1_05_acceptance_criteria.md` | 成功判据与停止条件 |
| `build_sample_matrix.py` | 矩阵生成脚本（只读） |

---

## 保护项

```text
AI 调用              0
生成题目             0
learning.db          未修改（SHA256 0C27267B…CF91）
contentpack v5       未修改（ai_artifact = 0 行）
教材 PDF / 54 MP3     未修改
validator v3 / P1-04 未修改
P1-03 已有题          未删除、未重新生成
Web / Android / V1.3 / V2.0  未修改
```

本轮唯一写入位置：`audit/AI_question_generation_spike/P1_05_sample_design/`。

**不执行 P1-05-B。**
