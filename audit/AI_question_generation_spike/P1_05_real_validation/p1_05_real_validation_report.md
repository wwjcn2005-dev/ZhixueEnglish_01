# P1-05-B · AI 题库多 Section 小规模真实质量验证报告

最终状态：**VALIDATION_BLOCKED**

执行日期：2026-09-17
模型：`deepseek-v4-pro` · prompt_version：`P1-05-v1` · validator：`v3`

---

## 0. 执行摘要

按 P1-05-A 冻结方案对 7 个 Section 执行，实际跑完 **6 个 Section 后停止**。

**全部 6 个已执行 Section 的调用都以 `finish_reason=length` 结束，`content` 为空，生成 0 道题。**

这不是"AI 判断证据不足所以不出题"，而是**输出预算在 reasoning 阶段被耗尽的技术性截断**——
与 P0 1610 的失败机理相同。

因此：

- **本轮不能对题目质量作出任何结论**（没有题目可评）；
- 已按冻结纪律**停止实验**，未继续跑第 7 个 Section，未现场改参数重跑；
- 正式资产**零污染**，已有 2 道题**完全未被触碰**。

> 本状态**不是** `QUALITY_NOT_READY`。`QUALITY_NOT_READY` 意味着"质量测过了但不够好"；
> 本轮是"质量没能被测到"。二者不能混为一谈。

---

## 1. 严格按冻结方案执行的部分

| 冻结项 | 执行情况 |
| --- | --- |
| 样本 | 使用 `P1-05_sample_design/p1_05_sample_matrix.json` 的 7 个 Section，**未换样本** |
| 模型 | `deepseek-v4-pro`，**未使用** Qwen / 本地模型 / 其他云模型 |
| `prompt_version` | `P1-05-v1` |
| 题量配额 | **已删除**"最多 3 题"限制（见 §3 提示词差异） |
| 生成范围 | Section 为 scope，保留 Activity / Page / evidence block provenance |
| 每个 Section | 一条独立 `generation_run`，调用前记录 `context_hash` 与 `generation_scope_key` |
| retry | **0**（无任何重试） |
| 入库状态 | 无题入库，因此无 `ACTIVE`、无 `REVIEW_APPROVED` |
| 调用顺序 | 生成 context → 记 hash → 查 scope → 建 run → 调用 → 存原始结果 → validator → 入库 |

### 提示词差异（`P1-05-v1` vs `P0-v1`）

```text
① 删除题量配额：
   old: "Quantity: AT MOST 3 questions. Fewer is acceptable; 0 is acceptable if the evidence
         is insufficient. / Prefer this distribution when the evidence allows: 1 fill,
         1 vocab_choice, 1 reading_choice/reading_judge."
   new: "Quantity: no quota. Generate as many questions as the supplied textbook evidence can
         reliably and uniquely support, and no more. Fewer is acceptable. 0 is an acceptable
         and expected answer when the evidence does not support reliable, unique, traceable
         questions. Do not create a question merely to reach a number. Prefer covering
         different pieces of evidence over restating the same sentence."

② 阅读题示例去 Unit 1 硬编码："(page 17)" → "the provided textbook blocks"

③ 页面/活动范围按 Section 参数化：
   old: "page must be one of 16,17,18,19,20 and activity must be one of 2,3,4,5,6,8 (or null)."
   new: 每个 Section 使用自己的真实页码范围与活动号集合

④ USER 结尾："Generate at most 3 questions now." → "Generate questions for this Section now."
```

> ②③④ 是把 P0 针对 Unit 1 UI 硬编码的范围行**参数化**，否则无法在另外 6 个 Section 上执行同一套设计；
> **10 条硬规则、JSON schema、题型定义逐字未改。** 每次调用的 system/user prompt SHA256 已随原始响应留档。

---

## 2. 实际执行结果（真实产物）

| # | Section | 类别 | 运行结果 | finish_reason | 生成 | 入库 | 延迟 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Unit 2 · UNDERSTANDING_IDEAS | A 阅读 | `TRUNCATED` | **length** | 0 | 0 | 123.4 s |
| 2 | Unit 6 · READING_FOR_WRITING | A 阅读 | `TRUNCATED` | **length** | 0 | 0 | 125.1 s |
| 3 | Unit 1 · UNDERSTANDING_IDEAS | B 对话 | `TRUNCATED` | **length** | 0 | 0 | 128.2 s |
| 4 | Unit 5 · UNDERSTANDING_IDEAS | C 词汇 | `TRUNCATED` | **length** | 0 | 0 | 118.5 s |
| 5 | Starter · GET_READY | D 信息匹配 | `TRUNCATED` | **length** | 0 | 0 | 128.7 s |
| 6 | Unit 3 · STARTING_OUT | E 低证据 | `TRUNCATED` | **length** | 0 | 0 | 117.8 s |
| 7 | Unit 1 · DEVELOPING_IDEAS | F 听力对照 | **未执行**（被终止） | — | — | — | — |

第 7 个 Section 的 `generation_run` 保留为 in-flight 占位（`API_ERROR`），
未产生任何 content、未产生题目——如实记录，不删除、不美化。

### 截断的直接证据（逐次调用）

| Section | prompt tokens | completion tokens | reasoning tokens | content 字符 | reasoning 字符 |
| --- | --- | --- | --- | --- | --- |
| U2 UI | 10,619 | 8,192 | **8,192（占满）** | **0** | 33,515 |
| U6 RfW | 7,732 | 8,192 | **8,192** | **0** | 32,564 |
| U1 UI | 8,680 | 8,192 | **8,192** | **0** | 32,737 |
| U5 UI | 10,044 | 8,192 | **8,192** | **0** | 32,733 |
| Starter GET_READY | 9,160 | 8,192 | **8,192** | **0** | 32,079 |
| U3 STARTING_OUT | 3,663 | 8,192 | **7,538** | **0** | 30,249 |

6 次调用的 `completion_tokens` **全部精确等于 `max_tokens = 8192`**（其中 5 次 reasoning 也占满 8,192），
而 `content` 全为 0 —— 输出预算被推理阶段吃光。
(U3 STARTING_OUT 的 reasoning 为 7,538，是唯一略低于上限的一次，但同样以 `length` 结束、content 为空。)

---

## 3. 根因分析（这是本轮唯一有效的结论）

### 3.1 直接机理

```text
P1-05-v1 删除了"最多 3 题"的配额
        ↓
模型在 reasoning 阶段失去"该收手了"的信号，持续推演
        ↓
reasoning 用满 max_tokens = 8192
        ↓
finish_reason = length，content = "" → 0 题
```

### 3.2 与 P0 的对照（说明这是可复现的工程缺陷，不是偶发）

| 轮次 | 提示词 | max_tokens | reasoning tokens | content | 结果 |
| --- | --- | --- | --- | --- | --- |
| P0 1630 | P0-v1（**有** 3 题上限） | 8192 | 5,648 | 1,685 字符 | ✅ 3 题 |
| P0 1650 | P0-v1 + 证据不足条款 | 8192 | 179 | 362 字符 | ✅ 0 题（AI 主动拒答） |
| P1-03 | P0-v1（有上限） | 8192 | 6,638 | 2,436 字符 | ✅ 3 题 |
| **P1-05-B（本轮）** | **P1-05-v1（无上限）** | **8192** | **8,192（占满）** | **0** | ❌ 6/6 截断 |

**结论：P1-05-A 冻结的两个参数互相冲突**——"去掉题量配额"的提示词需要一个比 8192 更大的输出预算，
而 P1-05-A 同时冻结了 `max_tokens = 8192`。

这不是模型"变差了"，也不是证据不足，更不是 validator 的问题：**validator 本轮没有任何输入可处理。**

### 3.3 为什么不能"顺手把 max_tokens 调大再跑"

P1-05-B §二 明确规定：发现机制问题必须**停止并报告**，不得现场修改规则继续跑。
直接调高 `max_tokens` 再跑属于现场修机制，且会让本轮结果的解释完全失效。
因此本轮**没有**这样做。

---

## 4. 为什么停止（以及为什么 S1–S8 没有字面触发）

按 P1-05-A 冻结的停止条件逐条核对：

| 条件 | 是否触发 | 说明 |
| --- | --- | --- |
| S1 已入库题出现 `REJECT_CONTENT` | 否 | 本轮 0 题入库 |
| S2 教材外事实未被拦截 | 否 | 本轮没有产生任何内容 |
| S3 出现 `ACTIVE` 或伪造审批 | 否 | 0 道 ACTIVE，0 条 `REVIEW_APPROVED` |
| S4 跨库悬空引用 | 否 | 全部引用有效 |
| S5 正式保护资产被修改 | 否 | 见 §10 |
| S6 validator 误报 | 否 | 无输入 |
| S7 单次 > 300 秒 | 否 | 最长 128.7 s |
| S8 出现凑数低价值题 | 否 | 无题目 |

**S1–S8 无一条被字面触发。** 停止依据是 P1-05-B **§二**：

> 「如果发现机制问题：**停止并报告，不得现场修机制继续跑。**」

6 次调用给出完全一致的截断签名，已足以判定这是**系统性机制问题**而非偶发；
继续执行第 7 个 Section 只会以真实成本重复同一个空结果。因此停止，
并**如实标注第 7 个 Section 未执行**，而不是假装实验完整。

---

## 5. §十七 核心统计（如实填写）

| # | 指标 | 值 |
| --- | --- | --- |
| 1 | `generated_count` | **0** |
| 2 | `validated_pass_count` | **0** |
| 3 | `validated_fail_count` | **0** |
| 4 | `Evidence PASS Rate` | **N/A**（0/0，未定义；不是 0%） |
| 5 | `APPROVE` | 0 |
| 6 | `REJECT_CONTENT` | 0 |
| 7 | `REJECT_QUALITY` | 0 |
| 8 | `REJECT_SCOPE` | 0 |
| 9 | `Natural Value Rate` | **N/A**（0/0，未定义；不是 0%） |

> 全部为 0 的含义是 **"无样本"**，不是"质量差"，也不是"没有重复"。

---

## 6. §十八 Validator Interception（如实填写）

| 失败项 | 次数 |
| --- | --- |
| vocabulary scope | 0 |
| evidence | 0 |
| answer support | 0 |
| duplicate | 0 |
| structure | 0 |
| option consistency | 0 |
| other | 0 |

> **validator 没有可拦截的对象。** 本轮不是"拦截率为 0"，而是"没有内容进入 validator"。
> 因此本轮**不能**用来验证 validator v3 的拦截能力。

---

## 7. §十九 重复分析（如实填写）

```text
Section 内重复        : 无样本
Section 间重复        : 无样本
同一 evidence block   : 无样本
仅换问法的近重复       : 无样本
```

没有生成任何题目，四个维度均无数据。**不构成"无重复"的质量结论。**

---

## 8. §十五 人工审核（如实填写）

**本轮没有可审核的对象。**

人工审核按 P1-05-A 模板执行，但表单的六项判断与四类归类都要求存在题目。
0 题意味着：

```text
APPROVE         0
REJECT_CONTENT  0
REJECT_QUALITY  0
REJECT_SCOPE    0
```

这不是"全部通过"，也不是"全部驳回"——是**没有题可看**。
本报告**不伪造任何审核记录**。

---

## 9. §二十 成本统计

| 项 | 值 |
| --- | --- |
| 模型 | `deepseek-v4-pro` |
| 完成的调用数 | **6** |
| 被终止的调用 | 1（第 7 个 Section，未产生 content） |
| 重试次数 | **0** |
| API 层失败调用 | **0** |
| 总 prompt tokens | **49,898** |
| 总 completion tokens | **49,152**（其中 reasoning 48,498） |
| **总 tokens** | **99,050** |
| 总耗时 | **741.7 s（12.4 分钟）** |
| 平均单次耗时 | 123.6 s |
| 最长单次耗时 | 128.7 s（≤ 180 s 正常目标，≤ 300 s 硬停止线） |
| 每次调用生成题数 | 全部为 0 |
| 每道生成题平均 tokens | **未定义**（分母为 0） |
| 每道 APPROVE 题 tokens | **未定义**（分母为 0） |

### 成本观察

本轮**为 0 道题花了约 9.9 万 tokens / 12.4 分钟**。
这说明：**当输出预算不足时，成本全额浪费**——预算参数不是"省一点"的问题，
而是决定这次调用有没有产出的问题。

---

## 10. 保护项（执行后复验）

| 资产 | 结果 |
| --- | --- |
| `learning.db` | **未修改**（SHA256 `0C27267B…CF91`） |
| contentpack v5 | **未修改**（SHA256 `65829CA7…0C39`，`ai_artifact` = 0 行） |
| 教材 PDF | **未修改**（`C732051E…4F2F`） |
| 54 个官方 MP3 | 未修改（沿用上一轮 54/54 校验结论，本轮无写入路径触碰音频） |
| `validator_v2.py` | **未修改**（`7C61585A…A683`） |
| `validator_v3.py` | **未修改**（`EDB1AA54…900C`） |
| Web / Android / V1.3 / V2.0 | 未修改 |
| 正式 Web 8770 / Demo 8780 | 未被终止（停止时只终止了 P1-05-B 进程） |
| **已有 2 道题** | **完全未变**：`AIQ:3179968E3E74`、`AIQ:7EBCDBC29563`（数量、内容、生命周期均未动） |
| `question_library.db` | 唯一被写入的正式资产：新增 7 条 `generation_run`（6 条 `TRUNCATED` + 1 条 in-flight 占位），**0 条新题** |

题目总数在实验前后均为 **2**，`ACTIVE` 始终为 **0**，`REVIEW_APPROVED` 始终为 **0**。

---

## 11. §二十一 验收（严格判定，不美化）

| # | 条件 | 判定 | 依据 |
| --- | --- | --- | --- |
| **A** | 已入库题 `REJECT_CONTENT = 0` | **空转成立但无验证力** | 0 道入库题，条件无法检验 |
| **B** | 至少 1 个正常 Section **自然**产出 0 题 | **FAIL** | 6 个 Section 全部为 0，但原因是**技术截断**；§二十一 明确排除"技术失败导致的 0 题" |
| **C** | `Natural Value Rate ≥ 60%` 且 `APPROVE ≥ 5` | **FAIL** | N/A（0/0）；APPROVE = 0 |
| **D** | 题量分布不能相同，且差异可由证据密度解释 | **FAIL** | 分布为常数 0，无法与证据密度关联 |
| **E** | 单次 ≤ 180 s、总计 ≤ 30 min、失败调用 = 0 | **PASS** | 118.5–128.7 s；12.4 min；API 层失败 0 |
| **F** | 未触发任何停止条件 | **部分** | S1–S8 均未字面触发；实验因 §二 机制问题条款主动中止 |

### 总判定

```text
NOT_PASS
```

且**不是** `QUALITY_NOT_READY`——质量指标从未获得可用样本。

---

## 12. 本轮不能回答的问题（必须明确记录）

P1-05-A 设定的六个问题中，本轮**只回答了半个**：

| 问题 | 本轮能否回答 |
| --- | --- |
| A 机制能否稳定阻止明显错误题 | ❌ 无内容进入 validator |
| B AI 是否能做到"有价值才生成" | ❌ 0 题来自技术截断，不是 AI 判断 |
| C APPROVE 比例是否够继续 | ❌ 无可审核样本 |
| D 不同 Section 是否出现合理题量差异 | ❌ 分布为常数 0 |
| E 成本与延迟是否可接受 | ✅ **可回答**：单次 118.5–128.7 s 正常，但**有效产出为 0，成本全部浪费** |
| F 是否暴露必须先修的机制问题 | ✅ **可回答**：**是的**，见 §3 |

**本轮唯一有效的正向产出，是发现了一个必须先修的机制缺陷。**

---

## 13. 下一轮之前必须先解决的问题（只记录，不实施）

1. **`max_tokens` 与"无配额提示词"必须匹配。**
   实测 reasoning 需要超过 8192 tokens 才能收敛。下一轮需要重新确定一个经**真实调用**验证过的预算，
   并把"预算是否足够"写进执行前的安全检查（例如先跑 1 个 Section 确认 `finish_reason=stop` 再继续）。
2. **需要一个"截断即停"的前置规则。**
   本轮 6 次截断才停；若在第一次 `finish_reason=length` 时就停，可省下约 5 次无效调用
   （约 8.2 万 tokens / 10 分钟）。建议把"出现 `length` 截断"加入显式停止条件。
3. **P1-05-A 的冻结方案存在内部冲突**，需要在下一版设计里显式标注参数之间的依赖关系
   （提示词约束强度 ↔ 输出预算）。

以上三条**不在本轮实施**。

---

## 14. 本次任务输入的一处不完整（如实说明）

本轮任务书在「**二十四、正式题库保护**」处被截断（原文最后为
"本轮允许向：`structured/ai/question_libra_..."），其后内容不可见。

处理方式：按既有各轮一致的保护约束执行，即

> 允许写入 `structured/ai/question_library.db`；`learning.db` / contentpack / 教材 PDF /
> 54 个 MP3 / Web / Android / V1.3 / V2.0 一律不得修改；不得覆盖已有题库数据。

该假设偏保守，并在执行前后都做了哈希复验（见 §10）。

---

## 15. 产物

| 文件 | 说明 |
| --- | --- |
| `README.md` | 索引 |
| `p1_05_real_validation_report.md` | 本报告 |
| `p1_05_real_validation_audit.json` | 审计结果（含验收 A–F 与保护项） |
| `generation_summary.json` | 7 个 Section 的执行摘要（含未执行的第 7 个） |
| `human_review_results.json` | 人工审核结果（0 题，明确标注"无可审核对象"） |
| `cost_summary.json` | 成本统计（逐次调用） |
| `question_distribution.json` | 题量分布（全部为 0，并说明原因） |
| `duplicate_analysis.json` | 重复分析（无样本） |
| `runs/` | 每个 Section 的 context / prompt / 原始响应 / 解析结果 / validator 结果 |
| `run_p1_05b.py` | 执行脚本 |
| `build_report_data.py` | 结果统计脚本 |

结果：**VALIDATION_BLOCKED**
