# P1 设计建议（只设计，不实施）

前提：P0 已收口（`P0_CLOSE`）。本文件**只提出设计任务**，
不包含任何实现步骤、不建表、不写代码、不调用 AI。

P1 的统一原则：

> **先设计“题目怎么被管住”，再谈“生成多少题”。**

---

## P1-01 · AI Question Library 最小数据模型设计

**目标**：给出一个字段级、可审计、可复用的最小题目数据模型设计文档（不建库）。

**必须覆盖的字段分组**

| 分组 | 字段 |
| --- | --- |
| 身份 | `question_id`、`question_type`、`question_text`、`options`、`correct_answer`、`explanation` |
| 教材来源 | `unit_id`、`section_id`、`activity_id`、`page`、`evidence_block_ids`、`evidence_quote` |
| AI 来源 | `model`、`prompt_version`、`context_hash`、`generation_run_id`、`generated_at` |
| 审核 | `validation_status`、`answer_support_type`、`review_status`、`reviewer`、`reviewed_at`、`review_note` |
| 生命周期 | `active`、`version`、`disabled_reason`、`stale_reason` |

**必须写清的设计决策**

1. `evidence_block_ids` 与 `evidence_quote` 是**强制非空**字段（无证据的题不得入库）。
2. `context_hash` 指向教材证据快照；教材变化时必须使旧条目可识别为 `stale`。
3. 是否允许一题多条 evidence（跨句）——**P1 先明确“不支持”，并写明后续扩展点**。
4. `options` 为空表示非选择题；由此派生题型结构约束。

**验收标准**：任意一条题目记录，都能仅凭记录本身回答
“它来自教材哪一页哪一句、由哪个模型哪个提示词版本在哪次运行生成”。

---

## P1-02 · AI Question Lifecycle / Review 状态设计

**目标**：把 P0 报告第 6 节的生命周期落成正式设计文档。

**状态机**

```text
GENERATED → VALIDATED → PENDING_REVIEW → APPROVED → ACTIVE
任意状态 → REJECTED | DISABLED
APPROVED → PENDING_REVIEW（教材/规则/模型变化导致 stale 时）
ACTIVE   → DISABLED（下线）
```

**必须写清的设计决策**

1. **学习系统只能读 `ACTIVE`**；`APPROVED` 必须再经一次显式启用。
2. `REJECTED` 必须沉淀 `reject_signature`（题干 + evidence_quote 指纹），供生成侧去重。
3. 状态迁移必须是**显式动作 + 记录操作者/时间/原因**，不允许隐式跳变。
4. 谁有权限把题目推进到 `APPROVED`（P1 阶段 = 人工）。

**验收标准**：给定任意一条题目，能完整重建它的状态迁移历史与每次迁移的原因。

---

## P1-03 · Generation Cache / Reuse Key 设计

**目标**：定义“什么时候才允许调用 AI”的缓存与复用契约。

**建议复用键**

```text
reuse_key = hash(section_id, activity_id, question_type, prompt_version, context_hash)
```

**必须写清的设计决策**

1. **禁止页面打开即调用 AI**（写入设计文档的硬性条款）。
2. 命中 `ACTIVE` 题目 → 直接复用，**0 次 AI 调用**。
3. 命中 `PENDING_REVIEW` → 复用待审条目，**不重复生成**。
4. 命中 `REJECTED` → 直接丢弃，**不重复生成**。
5. `context_hash` 变化 → 视为新条目，旧条目保留并标记 `stale`。
6. 生成侧的三重预算限制：**批次上限 + 单日调用上限 + 单次耗时上限**。

**验收标准**：能用一次模拟推演证明“同一 Section 同一题型，第二次进入学习场景时 AI 调用次数为 0”。

---

## P1-04 · Validator v2 → 正式质量门槛设计

**目标**：把 P0 的 validator v2 提升为正式质量门槛，并**补上 P0 已确认的盲区**。

**必须保留为硬门槛（P0 已验证有效）**

1. 定位真实性
2. `evidence_block_ids` 真实性
3. `evidence_quote` 可回溯
4. 答案支持分级（`EXACT` / `VERIFIABLE_REFERENCE` / `VERIFIABLE_REPHRASE`）
5. 词汇白名单（只检查 `question + options + answer`）
6. 选项一致性与唯一正确项
7. 题型结构规则
8. 重复检测

**P1 必须新增设计的三条（P0 已确认的盲区）**

1. **`EXACT` 语义陷阱规则**
   当 `answer` 命中证据的原因仅仅是“该字符串印在教材上”（例如题干自带的选项文本而非正文陈述），
   需要一条**降级规则**：把 `EXACT` 降为 `NEEDS_HUMAN`，而不是直接 PASS。
   *设计目标：把 P0 报告 5.3 的风险变成可执行规则。*
2. **覆盖度约束**
   同一 `section_id` 下的题目不得集中在单一 page / 单一 block；
   需给出“同一 block 最多贡献 N 题”的设计值。
3. **干扰项可解释性要求**
   选择题的干扰项应能说明“为什么错”（与教材事实冲突 / 词性不符 / 上下文不成立），
   至少要求人工复核项固定填写该说明。

**明确不做（P1 不解决）**：教育价值的机器判定、语言自然度的机器判定。

**验收标准**：用 P0 的 6 道真实题 + 6 个对抗样本 + 新增“选项在教材中”的对抗样本，全部给出可复现判定。

---

## P1-05 · AI 题目人工复核最小界面 / 流程设计

**目标**：设计一个**最小**的复核流程，让复核成本可控（这是规模化的真正瓶颈）。

**必须包含的信息（一屏之内可判定）**

1. 题目全文 + 选项 + 答案
2. **教材原文并排显示**（`evidence_quote` 高亮在 block 原文中）
3. 教材定位：unit / section / activity / page
4. 程序判定结果：8 项校验逐项 + `answer_support_type`
5. 生成来源：model / prompt_version / context_hash / generated_at

**流程与动作**

```text
待审队列（PENDING_REVIEW）
    ↓ 逐题
通过 → APPROVED        驳回 → REJECTED（必填原因，沉淀 reject_signature）
    ↓ 显式启用
ACTIVE
```

**必须写清的设计决策**

1. 驳回原因是**结构化必填项**（教材不符 / 答案不唯一 / 干扰项无效 / 超纲 / 其他）。
2. 复核界面**不得提供“批量一键通过”**（在 P1 阶段）。
3. 记录复核耗时，用于估算规模化所需人力（P0 已提示这是瓶颈）。

**验收标准**：复核员在不知道生成细节的前提下，仅凭该界面即可判断“这道题能不能给孩子做”。

---

## P1 明确暂不做

以下内容**本期不设计、不实施**，避免提前扩大：

- 批量生成几百题
- 自动入库（跳过人工复核）
- AI 学习计划 / AI 自动布置任务
- 页面实时生成
- 听力类活动的证据补齐工程（先作为已知缺口记录）

---

## P1 建议顺序与依赖

```text
P1-01 数据模型 ──┬─→ P1-02 生命周期 ──→ P1-05 复核界面/流程
                 └─→ P1-03 缓存与复用键
P1-04 质量门槛 ──→（与 P1-02 的状态迁移耦合：VALIDATED / PENDING_REVIEW 的判定依据）
```

建议先做 **P1-01**（其余四项都以它为共同语言），随后并行 P1-02 / P1-03 / P1-04，
最后落 P1-05。P1 全程**不调用 AI**，除非另行批准一次小规模验证。
