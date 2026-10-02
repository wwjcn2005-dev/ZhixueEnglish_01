# AI 教材习题生成与题库入库流程规范 V1.0

## 0. 文档信息

| 项 | 内容 |
| --- | --- |
| 文档名称 | AI 教材习题生成与题库入库流程规范 |
| 版本 | V1.0 |
| 状态 | FROZEN / 正式开发基线 |
| 最高依据 | 《初中英语 AI 辅助学习系统最高指导原则与开发规范 V1.3》 |
| 上级依据 | 《初中英语 AI 辅助学习系统产品与 UI 架构总纲 V2.0》 |
| 适用对象 | AI 教材习题的生成、确定性验证、题库入库、人工审核与启用的全流程 |
| 依据来源 | P0 收口审计、P1-01～P1-07 全部实施报告与审计产物 |
| 本规范性质 | **补充规范**：只补充"AI 题库生产流程"，不改变 V1.3 / V2.0 的任何既有原则 |
| 边界裁决 | **2026-09-17 采用解读 A**：AI 可生成教材训练题；题干/选项/答案不得冒充教材事实、不得写入教材数据；AI 题独立存放、经审核后方可进入学习流程（详见 §5.3） |

### 优先级

从高到低：

1. 《最高指导原则与开发规范 V1.3》
2. 《产品与 UI 架构总纲 V2.0》
3. 本规范（AI 教材习题生成与题库入库流程）
4. `P1-12-C3-A_正式UI视觉与交互设计规范_V1.0.md` / `P1-12-C3-B_正式页面UI设计基线_V1.0.md`

本规范与 V1.3 / V2.0 冲突时，以 V1.3 / V2.0 为准。

---

## 1. 目的

把 P0～P1-07 已经**实际验证成功**的 AI 习题生成、验证、入库、人工审核流程，
从"实验流程"正式提升为项目开发基线。

本规范**不引入新的产品功能**，只固定已经跑通的机制与边界。

---

## 2. 一句话总纲

> **教材提供边界，AI 负责重新组合，程序负责守住硬边界，人工负责最终教育质量，
> 题库负责保存和复用，`ACTIVE` 才能进入孩子的正式学习。**

与之配套的角色分工：

| 角色 | 负责什么 | 不负责什么 |
| --- | --- | --- |
| **AI（模型）** | 理解教材、重新组织教材已有素材、设计考查角度与选项 | 决定教材事实、决定答案、决定什么题能给孩子 |
| **程序（确定性代码）** | 证据边界、结构合法性、去重、生命周期、数据安全 | 判断题目是否"有教育价值" |
| **人工（审核者）** | 最终教育质量判断：是否自然、是否有学习价值、是否适合初一、是否值得让孩子做 | 重复机器已经能可靠完成的机械检查 |

**AI 出题的适用范围（2026-09-29 明确）**：

- AI 在题库中**只做两类事**：① **补干扰项**；② **按音频补全教材文本挖空**（作为素材）；并**依据教材资源出题**（**教材范围 = 本册 + 已学过的前置教材**）。
- AI 出题**限于依据教材资源生成**——**不得脱离教材**、**不得生成教材外内容**、**不得生成教材中不存在的事实**。
- 这是「不生成独立题」的准确含义：**约束的是「不能脱离教材」，不是「不能出题」**。

---

## 3. 核心流程（正式固定）

```text
教材原始数据（PDF / 音频 / structured 正式数据，只读）
      ↓
教材证据组装（Section 级、完整、可审计）
      ↓
Section 级 AI 生成（1 个 Section = 1 次 generation run）
      ↓
生成结果完整性检查（截断即停、结构完整）
      ↓
确定性验证（证据 / 答案支持 / 词汇边界 / 完整性 / 原题 / 重复 / schema）
      ↓
合格候选
      ↓
questionbank.db（单事务写入，作为素材）
      ↓
PENDING_REVIEW（quality_status / review_status）
      ↓
人工审核
      ↓
APPROVED
      ↓
ACTIVE（显式启用）
      ↓
正式学习系统
```

**关键：`VALIDATED ≠ APPROVED ≠ ACTIVE`。机器验证通过的题，不能直接给孩子使用。**

---

## 4. 五条冻结规则

### 规则 1 · 教材是唯一内容边界

AI **可以**：

- 改写、重组教材已有句子与信息；
- 调整题型、改变考查角度；
- 用教材重点词生成新的练习角度；
- 在教材语境中重新设计选项。

AI **不可以**：

- 引入教材没有依据的事实、人物、事件、词汇或知识；
- 凭空创造学习重点；
- 为了满足数量而填充低价值题；
- 使用教材证据无法确定的答案。

### 规则 2 · Section 是 AI generation boundary

一次 AI generation run **对应一个 Section**。

- 不是整本教材一次调用；
- 不是每道题一次调用；
- 每题必须保留 Activity 级 provenance。

### 规则 3 · 不设固定题量

> 有合适学习点就多生成，没有合适内容就少生成；**允许生成 0 道**。

**质量优先，宁缺毋滥**：合格内容不足时**宁可不生成**（**允许 0 道**），不得为凑数而降低标准。

禁止为了满足固定数量而填充低价值题。
（实测：同一提示词在不同 Section 上分别产出 5、6、6、5 题；在证据不足场景产出 0 题。）

### 规则 4 · 生成前必须先建立完整教材证据

AI 生成前必须建立该 Section 的**完整教材证据**，再按 Activity 定位生成范围。

**不得**简单依赖 `activity → page → text` 反推正文：**"页面没有 activity"不能意味着该页正文被自动丢弃。**

> 依据：P1-07 入库演练暴露的真实缺陷 —— Unit 1 · UNDERSTANDING_IDEAS 的课文主体页
> （教材第 17 页 / PDF 第 22 页）没有 Activity，按"Activity 所在页 → Section"归属时整页正文被漏掉，
> 导致该 Section 的 AI 上下文缺少课文主体。

教材证据组装层**本身必须可审计**：必须能回答"这次生成究竟看到了哪些 block"，
并给出可复核的 context 指纹（见 §7）。

### 规则 5 · 质量责任分层，不得互相替代

程序不得用"AI 说没问题"代替确定性校验；
人工不得被要求重复机器已经能可靠完成的机械检查；
AI 不得代替人工做最终教育质量判断。

---

## 5. 与 V1.3 / V2.0 的关系（含一处需要项目裁决的边界）

### 5.1 本规范性质

本规范**只补充"AI 教材习题的生产与入库流程"**，不改变 V1.3 / V2.0 的任何产品定位与既有原则。
本文件自身**不修改** V1.3 / V2.0。

### 5.2 与 V1.3 明确一致的部分

| V1.3 条款 | 本规范的对应做法 |
| --- | --- |
| 二·2 / 十五：第一阶段不做"无限题库""大型题库""无限题目生成" | 建立的是**有界、受控、必审**的题库：题目必须锚定到具体 Section / Activity / evidence block；按 Section 生成；无固定题量；允许 0 题 |
| 九："AI 生成内容必须与原始教材明确区分" | AI 题**绝不写入教材数据**（`contentpack` 只读）；**入库目标为 `questionbank.db`（作为素材）**，须过确定性闸门与人工审核；孩子端不出现题库概念 |
| 九："AI 生成训练必须服务于明确的学习目标或薄弱点" | 每题必须锚定教材学习点（词汇表 / 重点表达 / 课文重要事实）与 evidence |
| 九："AI 数据与教材资源隔离……允许的关系是教材资源 → AI 分析 → AI Artifact" | 本规范 §12 的数据边界与此完全一致 |
| 九："静态页面浏览不应无意义调用 AI""AI 数据复用优先" | 先查 `ACTIVE` 题库，命中即复用；**禁止页面打开触发生成** |
| 九："禁止……随机大量生成题目""为了增加内容而大量生成题目" | 无固定题量、证据不足可 0 题、不得为凑数生成 |
| 二十二·7 / 二十四：AI 角色边界与职责 | AI 只负责理解与重组；最终教育质量判断交给人工 |
| 十一·8：NEEDS_REVIEW 规则 | 本规范沿用同一标记语义（无法可靠判断不得猜测） |

### 5.3 边界裁决（**已于 2026-09-17 裁决：采用解读 A**）

#### 待裁决的 V1.3 原句

> **V1.3 九·AI 辅助的准确边界（原文）**：
> "AI 可以批改、分析、解释、归纳错误并给出建议（见七·7、七·8），但**不得创造教材事实**——
> **不得生成或改写教材正文、题干、选项、答案、音频与音频片段**，也不得把 AI 生成的结论写入教材内容事实。"

> **V1.3 二十二·1 产品边界（原文）**：
> "本产品不是：**AI 题库**；自动作业系统；自动学习路径系统；刷题系统；分数、排名、等级系统。"

#### 裁决结果

> **项目决策者于 2026-09-17 确认采用解读 A：**
>
> "AI 可以生成教材训练题，但 AI 生成的题干、选项、答案**不得冒充教材事实**，
> **不得写入教材数据**；AI 题**独立存放**，**经审核后**才能进入学习流程。"

#### 两种解读的对照（存档）

| 解读 | 含义 | 与本规范的关系 |
| --- | --- | --- |
| **解读 A（教材事实层）** | 禁止的是"把 AI 生成的题干/选项/答案**当作教材事实**写入教材数据" | 与本规范**完全一致**：AI 题一律不进入 contentpack / structured，其**入库目标为 `questionbank.db`**（作为素材，须先过确定性验证、再经人工审核），不得写入任何教材数据 |
| **解读 B（绝对禁止）** | 任何 AI 生成的题干/选项/答案都不得存在 | 与本规范**直接冲突**；也与 V1.3 九"根据真实薄弱点提供**少量针对性训练**""AI 生成训练必须服务于明确的学习目标或薄弱点"存在内部张力 |

#### 裁决后的正式执行口径

解读 A 生效后，本规范按下列口径执行（其中 1–3 为裁决直接要求，4–5 为本规范加设的更严格限制）：

1. AI 题**不得**写入任何教材数据（`contentpack` 只读）；其**入库目标为 `questionbank.db`**（作为素材），且须**先过确定性验证**（见 §8）、**再经人工审核**方才生效；
2. AI 题必须与教材素材明确区分（独立库 + 独立生命周期）；
3. 只有 `ACTIVE` 才允许进入学习流程，而 `ACTIVE` 的前置是**人工审核通过**；
4. 孩子端**不得**呈现"题库""刷题"概念；
5. 不允许"随机大量生成"——按 Section、受教材证据边界约束、允许 0 题。

即：**产品定位不变（产品仍然不是"AI 题库"）；本规范建立的是后台的、受控的生产流程与素材库。**

#### 裁决的效力说明

1. **自裁决起，本规范与 V1.3 的一致性成立**：在解读 A 下，V1.3 九的禁止对象是"冒充教材事实 / 写入教材数据"，
   与本规范的数据边界完全一致；V1.3 二十二·1 的产品定位（不是 AI 题库 / 刷题系统）也未被本规范改变。
2. **V1.3 / V2.0 本轮仍不改动**：解读 A 下不存在实质矛盾，因此不构成必须修改 V1.3 的情形。
3. 下文的措辞澄清文本**保留为可选建议**，供项目在**下一次 V1.3 修订**时一并纳入，
   以避免未来读者仅凭 V1.3 原文产生歧义。**该澄清是非阻塞的可选项，不影响本规范执行。**

#### 建议的 V1.3 措辞澄清文本（**可选，待下一次 V1.3 修订时执行**）

建议在 V1.3 九·AI 辅助的准确边界中，把该句限定为教材数据层，并显式承认受控的 AI 练习库：

```text
AI 辅助的准确边界：AI 可以批改、分析、解释、归纳错误并给出建议，但不得创造教材事实——
不得生成或改写教材正文、题干、选项、答案、音频与音频片段，也不得把 AI 生成的结论写入教材内容事实。
【建议补充】AI 生成的练习**可入库 `questionbank.db`（作为素材）**，但必须：
① 严格锚定教材证据；② 与教材数据完全隔离；③ 经确定性校验；
④ 经人工审核进入 APPROVED/ACTIVE 后方可使用；⑤ 不得呈现"随机大量生成"或"无限题库"形态。
```

> 裁决记录见 `audit/AI_question_generation_spike/P1_08_A_process_baseline/p1_08_a_decision_record.md`。

---

## 6. 阶段一 · 教材证据组装

### 6.1 必须提供的内容

每个 Section 的证据上下文至少包含：

```text
教材定位：unit_id / section_id / 教材页码范围
活动指令：该 Section 全部 activity 的编号、页码、指令文本
教材正文：该 Section **全部** 非页脚 content_block（不因页面无 activity 而丢弃）
词汇表：该 Unit 的 unit_vocabulary（含 BOLD / PLAIN 标记）
教材练习：该 Section 的全部 evidence package（题干、选项、空位、答案来源状态）
音频说明：哪些 activity 依赖音频、音频文本证据是否存在
```

### 6.2 硬性要求

1. **完整性优先于便利**：证据组装必须覆盖该 Section 的全部正文页；
2. **可审计**：必须落盘 `input_context.json`，并记录 `context_hash`（SHA256）；
3. **可复现**：同一 Section、同一证据状态必须得到字节一致的上下文；
4. **不修改教材**：证据组装只读 contentpack 与 structured 正式数据；
5. **缺口必须显式记录**：若某类证据缺失（例如音频转写），必须在上下文中如实标注，
   不得用推断补齐，也不得因此静默丢弃整页正文。

---

## 7. 阶段二 · AI 生成

### 7.1 生成参数（当前基线）

| 项 | 基线值 |
| --- | --- |
| 模型 | `deepseek-v4-pro`（云端；本地模型路线在 P0 判定不可用） |
| `max_tokens` | **16384** |
| `thinking` | `{"type": "enabled"}` |
| `reasoning_effort` | `low` |
| `temperature` | 0.2 |
| 生成单元 | 一个 Section |
| 题量 | 不设配额，允许 0 题 |

### 7.2 必须记录（provenance）

```text
generation_run_id · section · activity provenance · model · prompt_version
context_hash · generated_at
```

并在 `generation_run` 中同时记录：provider、max_tokens、finish_reason、usage（含 reasoning tokens）、
elapsed_ms、question_count、status（历史状态值：OK / TRUNCATED / API_ERROR / INSUFFICIENT_EVIDENCE）。

### 7.3 生成纪律

1. **允许 0 题**；不设固定题量；
2. **不因内容不理想而自动重试**。重试只允许用于 HTTP 层失败（且未产生任何 content），
   并必须完整记录 `retry_count` 与失败原因；
3. **HTTP 失败与内容失败必须区分**（前者可重试，后者不得重试）；
4. **截断即停**：`finish_reason = length` 必须立即判为 `TRUNCATED`，
   **不得进入解析、不得进入验证、不得入库、不得继续下一个 Section**；
   `length` 且 `content` 非空（半截 JSON）同样必须停止；
5. 页面打开**不得**触发 AI 生成（AI 生成是批次化的后台行为）。

---

## 8. 阶段三 · 确定性验证

确定性验证必须覆盖 **A–J 十类**。**任何一类不通过，该题不得进入正式题库。**

> **2026-09-29 补充**：在原有 A–G 七类之外，新增 **H / I / J** 三类（与 V1.3 第二十九章 §5 同口径）。

### A. 证据真实性

必须全部可追溯：

```text
section → activity → page → evidence_block_ids → evidence_quote
```

`evidence_quote` 必须是对应 block 文本的逐字子串（按归一化后比较）。

### B. Answer support

答案必须能由教材证据支持。判定分级（沿用已实现的校验器口径）：

```text
EXACT / VERIFIABLE_REFERENCE / VERIFIABLE_REPHRASE  → 支持
UNSUPPORTED                                         → 不支持
```

**不得因为模型自称"这是指代/同义替换"就放行。**

### C. Vocabulary scope

题干、选项、答案中实际出现的英语学习材料，不得无依据引入教材外词汇。

**词形变化必须归一化后再判定**，避免以下已实测的假阳性：

```text
point  / points    （Unit 词表 "point out"）
write  / writes    （教材正文 "Please write this down"）
student/ students  （教材练习选项 "Students need to think for themselves."）
```

判定基准是 **contentpack 中该 Section 页面的完整正文 + 该 Unit 词表**，而不是（可能不完整的）生成上下文。

### D. 证据完整性

必须检查：

1. `evidence_quote` 是否包含**完整依据**（尤其是 fill 题：引用必须包含答案词，
   不得只截取空位之前的片段）；
2. fill 的答案是否真的能从完整证据得到，而不是因为教材内容块被截断而产生"假支持"；
3. 题干是否残缺：`...` / `…` 等截断痕迹，或题干尾部与所引 block 尾部同为一处被切开的位置。

### E. 教材原题

教材原题可以作为**教材资源**存在。

但**不得把教材原题（或只换表面形式的教材原练习）当作新的 AI 题进入 AI 题库**。

判定要点：与教材练习文本严格对齐、且差异恰好是教材练习的编号空位。

### F. Mechanical rewrite

**不得一律拒绝"教材原句挖重点词"。**

若同时满足：

```text
学习点明确 · 答案唯一 · 属于重点学习内容 · 不是教材原练习本身的机械复制
```

允许进入 `PENDING_REVIEW`，并记录 `mechanical_rewrite = true`。

最终是否保留，由人工审核决定。

### G. Duplicate

正式去重采用**确定性规则**：

```text
dedupe_key = sha256( section_id × activity_id × question_type
                     × normalized_answer × sorted(evidence_block_ids) )
```

并保留 `question_fingerprint` 用于精确文本重复。

- 批次内部重复 → 拦截；
- 与题库已有题重复 → 拦截；
- 措辞不同但`section / activity / type / answer / evidence block`完全相同 → 判为 `DUPLICATE_CANDIDATE`，不得作为全新题入库；
- **不得因为"看起来相似"就大量误杀**；
- **不引入 AI 语义去重作为硬依赖**；embedding / 向量库不作为必需组件。

### H. 合乎逻辑

题目本身必须**合乎逻辑**：题干与选项/答案之间不得自相矛盾；不得出现「问题问 A、答案答 B」；
不得出现常识性错误（例如与教材事实相反的表述）。

### I. 匹配上下文

题目必须**匹配其教材上下文**：所考查的内容必须落在该 `section_key` / `activity_id` 的教材语境内；
不得脱离该活动的语境去考另一个活动的内容（题干与证据须同一语境）。

### J. 同类型（题型一致）

补全 / 生成的题必须与**目标题型的正式约定一致**：干扰项只补到选项型；挖空只补到填空型；
**不得跨题型套用**（例如把选择题的干扰项塞进填空题，或把挖空塞进选择题）。

---

## 9. 阶段四 · 合格候选判定

候选必须按下列顺序过闸门，命中任一硬性失败即不得入库：

```text
Gate 1 证据完整性（含 D 项的引用完整性与题干残缺检查）
Gate 2 教材原题识别
Gate 3 机械复现（仅在答案不是明确学习点时拒绝）
Gate 4 deterministic dedupe
Gate 5 schema / provenance 完整性
```

候选的判定结果只允许下列取值：

```text
PASS · NEEDS_REVIEW · ORIGINAL_TEXTBOOK · MECHANICAL_REPRODUCTION
EVIDENCE_INCOMPLETE · DUPLICATE_CANDIDATE
```

**只有 `PASS` 允许入库。** 其余一律不得入库。

判定过程必须落盘逐题结论（decision、各闸门结果、原因、dedupe_key、fingerprint、
mechanical_rewrite、original_textbook、evidence_status、vocabulary_status），**可复核**。

---

## 10. 阶段五 · 入库

### 10.1 事务与安全

1. 一个批次使用**一个事务**；出现不可恢复错误必须**全部 rollback**，不得留下半批次状态；
2. 只写 `decision = PASS` 的候选；
3. 入库前后必须做表计数与已有题核对；
4. 不得删除、覆盖、修改题库中已有题的业务内容。

### 10.2 写入内容

每题必须同时写入：

**入库目标 = `questionbank.db`**（2026-09-29 裁决）。写入按**实际 schema**：

| 表 | 写入内容 | 关键字段（实际 schema） |
| --- | --- | --- |
| **`question`** | 题目本身（题干 / 选项 / 答案 / 教材定位 / 来源） | `question_id` / `question_type` / `domain` / **`unit_code`** / **`section_key`** / `activity_id` / `source_item_id` / **`prompt_json`** / **`options_json`** / **`answer_json`** / `answer_kind` / `answer_status` / **`origin`**（`AI_GENERATED`） / `generation_run_id` / `rules_version` / `prompt_version` / `quality_status` / `review_status` / `content_hash` |
| **`question_asset`** | 题目 ↔ 教材资产关联（1:N） | `question_id` / `asset_kind`（`learning_item` / `content_block` / `audio` / `activity` / `section`） / `asset_id` / `role`（`primary` / `support` / `distractor_basis` / `answer_basis` / `audio_source`） / `evidence_quote` |
| **`quality_review`** | 人工 / 机器审核记录 | `review_id` / `question_id` / `layer` / `verdict` / `reasons_json` / `reviewer` / `reviewed_at` |
| **`generation_run`** | 生成批次（provenance） | `run_id` / `generator` / `model` / `prompt_version` / `rules_version` / `input_digest` / `ai_calls` / `started_at` / `finished_at` / `status` |
| **`supplement_task`** | **待 AI 补充任务**（本规范优先消费对象） | `task_id` / **`kind`**（如 `sentence_distractors`） / `unit_code` / `resource_ref` / `reason` / `status` / `created_at` |

**字段级约定（与 V1.3 第二十九章 §16 同口径）**：

```text
题干（含挖空）  -> question.prompt_json.text        空位用 ______（6 个下划线）
空位数量        -> question.prompt_json.blank_count （整数）
选项 / 干扰项    -> question.options_json           [{"key":"a","text":"..."[,"asset_id":"..."]}]
答案            -> question.answer_json
来源标注        -> question.origin（AI_GENERATED）
                 + question.prompt_json.question_origin / .distractor_origin
```

> **历史注记（2026-09-29）**：原候选库 `question_library.db` 的 `ai_question` / `question_evidence` /
> `question_learning_object` / `question_validation` / `question_event` 五张表**不再作为入库目标**；
> 其**生命周期设计逻辑**（`GENERATED -> VALIDATED -> PENDING_REVIEW -> APPROVED -> ACTIVE`）
> **在 `questionbank.db` 侧以 `question.quality_status` / `question.review_status` / `quality_review` / `supplement_task.status` 落地**。

### 10.3 `question_learning_object` 的语义要求

`item_id` **必须保持 LearningObject 语义**（指向 contentpack 的 `learning_item`）。

**绝对禁止把 `question_id` / `run_id` 塞进 LearningObject 位置。**

映射规则：优先映射答案对应的词表条目（短语优先匹配），并同时挂上该 Activity 的练习对象作为次级对象。

---

## 11. 题库生命周期

正常链：

```text
GENERATED → VALIDATED → PENDING_REVIEW → APPROVED → ACTIVE
```

异常状态：

```text
REJECTED（人工驳回，不再自动复用）
DISABLED（已启用后下线）
STALE（与生命周期正交：教材/提示词/模型/校验器变化导致需要重新验证）
```

### 硬性规则

1. **`VALIDATED ≠ APPROVED ≠ ACTIVE`**；
2. 新题入库后**只能停在 `PENDING_REVIEW`**；
3. **只有 `ACTIVE` 允许进入正式学习流程**；`APPROVED` 必须再经一次显式启用才成为 `ACTIVE`；
4. 题库必须在**数据库层**保证上述边界（现有实现通过 SQLite 硬约束实现：
   新题不得以 `ACTIVE` 插入；转为 `ACTIVE` 必须存在人工 `REVIEW_APPROVED` 事件；
   题目不可物理删除；事件表不可 UPDATE / DELETE）；
5. 生命周期事件为**权威事实源**，状态字段是查询用物化结果；二者不一致时以事件为准；
6. 事件表**只允许 append**，非法事件类型与伪造审批必须在数据库层被拒绝。

---

## 12. 数据边界

| 数据 | 职责 | AI 生成题的权限 |
| --- | --- | --- |
| **contentpack（含 structured 教材正式数据）** | 教材正式资源，事实源 | **只读**。AI 题目一律不得写入 |
| **learning.db** | 正式学习证据 / 学习系统数据 | **不得直接写入**。在打通来源字段之前，AI 题不得进入学习流程 |
| **`questionbank.db`** | **正式题库**（含 `question` / `question_asset` / `supplement_task` 等表） | **AI 补全 / 依据教材资源出题的唯一入库目标**（作为素材）；**必须先过第 8 节确定性验证**，未通过不得入库 |
| **`question_library.db`** | **历史候选库**（2026-09-17 期间 AI 出题 Spike 的候选产线） | **不再作为 AI 出题的入库目标**（保留为历史记录，不再写入）；其生命周期设计逻辑（校验→审核→生效）已在 `questionbank.db` 侧复用 |

AI 补全 / 生成的题**经确定性闸门校验通过后可入库 `questionbank.db` 作为素材**；**校验未通过不得入库**。

AI 生成题**不得直接进入孩子的正式学习流程**；**入库不等于进入孩子界面**——是否展示仍由各功能自身的资源范围规则决定。

---

## 13. 人工审核职责

人工审核**不再重复机器已经能够可靠完成的检查**（证据存在性、引文回溯、结构合法性、去重等）。

人工重点审核：

```text
英语是否自然
题目是否真正有学习价值
干扰项是否合理
是否过于机械
是否符合初一阶段
是否符合教材语境
是否值得让孩子实际完成
```

审核结论只允许：

```text
APPROVE · REJECT_CONTENT · REJECT_QUALITY · REJECT_SCOPE
```

通过后：`PENDING_REVIEW → APPROVED`；之后才允许进入 `ACTIVE` 流程。

---

## 14. Provenance（可追溯链）

```text
AI question
  ↓ generation_run_id
generation_run（model / prompt_version / context_hash / generated_at / usage）
  ↓ section_id / activity_id
Section / Activity
  ↓ evidence_block_ids / evidence_quote
教材 evidence
  ↓
原始教材数据
```

必须保留：

```text
context_hash · evidence_block_ids · evidence_quote · model · prompt_version
generation_run_id · generated_at · validator_version · question_fingerprint
```

缺失任一项的题**不得**进入正式题库。

---

## 15. 失败与停止条件

下列情况**必须停止并修复对应机制**，**不得通过放宽规则解决**：

```text
AI 输出截断
evidence 不完整
答案无法由教材支持
教材外事实 / 教材外词汇
教材原题冒充 AI 新题
重复题
结构非法
provenance 缺失
数据库引用不完整
ACTIVE 越权
正式数据污染
```

处理原则：

> **停止 → 定位 → 修复对应机制（证据组装 / 校验 / 入库 / 流程）→ 重新验证。**
> **不要继续堆 Prompt 规则。**

专项停止线（工程参数，可随工程结论调整，属"原则与参数"中的参数）：

```text
单次调用 > 300 秒            → 硬停止
单次正常调用目标 ≤ 180 秒
同一批次出现无法追溯教材依据的大量题目 → 停止
```

---

## 16. 已验证 vs 尚未验证

> 本节是本规范最重要的一节。**不得把设计目标写成已验证事实。**

### 16.1 已经通过 P0～P1-07 实际验证

| 项 | 验证方式 |
| --- | --- |
| Section 级生成 | P1-05-D/F/G、P1-06 共 7 次真实调用，均以 Section 为单位 |
| 无固定题量 | 实测产出 10 / 7 / 8 / 5 / 6 / 6 / 5 题 |
| AI 可生成 0 题 | P0 证据不足场景返回 0 题并说明理由 |
| DeepSeek 当前生成链路可用 | 云端 `deepseek-v4-pro`，多次 HTTP 200 且返回结构化 JSON |
| `max_tokens=16384` 对已测场景的预算可行性 | P1-05-D 与 P1-06 共 5 个 Section，全部 `finish_reason=stop` |
| 输出预算不足会截断 | P1-05-B 6/6 次 `length`；P1-05-C 单次校准复现 |
| 截断保护（截断即停） | 已实现并在 P1-05-D/P1-06 实际套用 |
| 证据真实性校验 | 22 题 `location` 与 `evidence_quote` 失效数均为 0 |
| 词汇边界基本口径 | P1-06/P1-07 中真正教材外词汇为 0（含词形归一化处理） |
| deterministic duplicate key | P1-07 入库演练已实战使用，并用反事实比对证明有效且不误杀 |
| `question_library.db` 历史候选库 | 曾与 contentpack、learning.db 完全分离，多次哈希复核未互相影响；**2026-09-29 起不再作为 AI 出题的入库目标**，其生命周期设计逻辑已在 `questionbank.db` 侧复用 |
| PENDING_REVIEW 生命周期 | P1-03、P1-07 两次真实入库，新题全部停在 `PENDING_REVIEW` |
| ACTIVE hard gate | 数据库层触发器在位并经测试；实际数据中 `ACTIVE` 始终为 0 |
| 单事务入库 | P1-07 单事务写入 19 题，写后核对通过 |
| provenance 完整 | 入库题均具备 run / context_hash / block / quote / validator 记录 |
| 人工审核前不进入正式学习 | `learning.db` 全程未被 AI 题库写入 |
| 原有正式资产保护 | 每轮均以哈希复核 contentpack / learning.db / PDF / MP3 / validator |

### 16.2 尚未充分验证（**不得写成已经解决**）

```text
大规模批量生产稳定性（当前最大规模仅 4 个 Section / 22 题）
低证据 Section 是否自然少出（P1-06 的 4 个样本均为证据充足样本）
listening question（音频文本证据缺口：transcript 0 行）
grammar question
writing question
speaking question
大规模 distractor 质量
长文本 Section
成本 / 吞吐的长期稳定性
教材版本变化后的 stale 机制（字段已设计，尚未实跑）
question_library schema v3 对 judge answer_support 的正式改进（见 §17）
教材证据组装层：当前实现仍存在"页面无 activity 则正文被漏掉"的缺陷（见 §4 规则 4）
人工审核 → APPROVED → ACTIVE 的完整实跑（设计已冻结、数据库硬门槛已验证，但尚未有题走完这一步）
learning_record 侧的 source_kind / source_ref / source_version 迁移（尚未执行，故 AI 题不得进入学习流程）
V1.3 九的措辞澄清（可选、非阻塞；适用域已于 2026-09-17 按解读 A 裁决，见 §5.3）
```

---

## 17. 特殊题型口径

### 17.1 reading_judge（判断题）

判断题的布尔答案**不能机械套用**普通 selectable question 的 answer_support 规则。

应验证：**题干陈述是否能够被教材证据支持或否定。**

现阶段采用已验证的兼容处理：

```text
rule4_waived_for_judge = true
```

并在 validation / checks 中保留实际事实依据（覆盖率、否定词一致性等）。

> **这是当前 schema v2 的兼容处理，不代表未来 schema 不需要优化。**
> schema 的四值枚举无法表达"布尔答案被教材事实验证"，
> 因此当前实现把该字段编码为最接近的可用值，并把真实依据写入 checks 与 note。
> 这一项已登记为 **schema v3 待办**。

### 17.2 fill（填空）

fill 的合法形态是"**用教材重点词进行的、答案唯一且有明确语境的练习**"，
而不是"把教材原句挖掉一个词"。

要求：答案优先来自 Unit 词表（BOLD 优先）或教材重点表达；
答案必须唯一；引用必须包含答案词。

---

## 18. 技术元数据不得暴露给孩子

下列属于**后台技术元数据**，孩子界面**不得显示**：

```text
model · prompt_version · context_hash · generation_run_id · validator_version
evidence_block_id · lifecycle_status · question_fingerprint · 任何数据库内部 ID
```

如需向孩子说明来源，只允许使用自然语言，例如：

> 教材第 17 页

---

## 19. 变更与复用规则

1. **复用优先**：先查 `ACTIVE` 题库，命中即复用，不得重复调用 AI；禁止页面打开即调用 AI；
2. **教材/规则/模型变化**：对已有题标记 `STALE` 并说明原因
   （`EVIDENCE_CHANGED` / `PROMPT_CHANGED` / `MODEL_CHANGED` / `VALIDATOR_CHANGED`），
   保留历史、不静默覆盖；
3. **提示词版本化**：`prompt_version` 只能新增，不得修改历史版本；
4. **schema 变更**：只能新增版本，不得修改已冻结版本的行为。

---

## 20. 与其他正式规范的同步结论

只读比较的实测结果：

| 关键词 | V1.3 命中 | V2.0 命中 |
| --- | --- | --- |
| `question_library` | 0 | 0 |
| 题库 | **6** | 0 |
| 出题 | 0 | 0 |
| 生成题 | **3** | 0 |
| AI 生成题 | **1** | 0 |
| 无限题库 | **1** | 0 |

即：**V2.0 完全未涉及**；**V1.3 有涉及**，且集中在以下条款：

```text
二·2 / 十五 · 第一阶段明确不做：无限题库、大型题库、无限题目生成
七·5        · 教材练习优先于系统自建练习；不得用大量 AI 生成题目替代真实教材练习
九          · AI 生成内容必须与原始教材明确区分；AI 生成训练必须服务明确学习目标或薄弱点
九          · AI 辅助的准确边界（见 §5.3）
九          · AI 数据与教材资源隔离；AI 数据复用优先；静态页面不得无意义调用 AI
二十二·1     · 本产品不是：AI 题库 / 自动作业系统 / 刷题系统
二十二·7、二十四 · AI 角色边界与职责
```

### 结论

1. **V2.0：无需修改**（全文未涉及）。
2. **V1.3：大部分条款与本规范一致**，本规范按 §5.2 逐条对齐；
3. **V1.3 有 1 处需要项目裁决的边界**（§5.3）：
   "不得生成或改写……题干、选项、答案"与"本产品不是 AI 题库"这两句，
   在"绝对禁止"的解读下会与任何 AI 出题流程冲突；
   本规范已给出**同步修订建议文本**，但**本轮不执行修改**，也不擅自改动 V1.3。

```text
最终同步结论：
  V2.0                        → 无需修改
  V1.3                        → 大部分无需修改；1 处边界需裁决（附建议文本，本轮不改）
  本规范                       → 纯增量补充，且已在裁决前按更严格的执行口径表述
```

---

## 21. 术语表

| 术语 | 含义 |
| --- | --- |
| Section | 教材单元内的学习板块，是 AI 生成的边界 |
| Activity | 教材练习活动，是题目的定位单位 |
| evidence block | 教材正文/练习的最小结构化文本块 |
| evidence quote | 题目所依据的教材原文片段，必须逐字可回溯 |
| generation run | 一次 AI 生成调用的完整账目 |
| context hash | 该次生成所见教材证据的指纹 |
| question fingerprint | 题目文本的去重指纹 |
| LearningObject | 教材中值得被学会的最小学习内容（评估聚合单位） |
| PENDING_REVIEW | 已通过机器验证、等待人工审核的状态 |
| ACTIVE | 唯一允许进入孩子正式学习的状态 |

---

## 22. 冻结声明

本规范 V1.0 冻结以下内容：

```text
核心流程 · 角色分工 · 五条冻结规则 · 七类确定性验证 · 闸门顺序与判定取值
入库事务与写入内容 · 生命周期与硬门槛 · 数据边界 · 人工审核职责
provenance 要求 · 失败与停止条件 · 技术元数据边界
```

未列入本规范的内容（例如更细的 UI 展示、学习方法、听力切分等）继续以 V1.3 / V2.0 与其他专项规范为准。

补充（2026-09-19 同步）：本次新增第 23 章「句子听辨 AI 干扰项规则」（正确答案来源、可用教材素材、
禁止的生成方式、确定性校验清单、随资源数量规则、调用时机与缓存、与 Demo 的关系）。第 1–22 章内容未变。

---

## 23. 句子听辨 AI 干扰项规则（2026-09-19 同步）

本节把"句子听辨 AI 智能干扰项"已经实施并真实验证通过的规则固化到本规范。
与本节冲突的旧条文（例如"句子听辨必须四选一"）一律失效。

### 23.1 正确答案

正确答案来自当前教材句子的真实含义 / 已有可靠教材资源。**不得由干扰项生成 AI 重新创造正确答案。**

### 23.2 AI 干扰项允许使用的素材

```text
当前教材句子 · 当前 Unit / Module 教材句子 · 教材 Vocabulary · Phrase · Sentence Pattern
· 已有 textbook evidence · 其他已允许使用的教材语义资源
```

干扰项必须：与正确答案相关、容易混淆、明确错误、符合初一阶段、有教材 evidence、不使用教材外内容。

资源范围（2026-09-19 同步）：句子听辨的正确答案由当前教材句确定；AI 干扰项可使用孩子**截至当前真实学习进度已经学过的 Section** 的教材资源，
即 Starter + 从教材开始到当前真实学习进度的**已学 Section 集合**（这些 Section 可归属于当前及此前已学 Unit；**Section 是学习进度核心粒度，Unit 可作为聚合层**），
但只允许已学内容，不得使用未来尚未学习的 Section / Unit 或无正式资源依据的内容。
学习进度由真实学习证据判定，与正在浏览的 Unit 无关；题目自身所在 Unit 属于本题教材上下文，始终可用；Appendix 不是教学 Unit，不进入资源范围。

### 23.3 禁止的生成方式

禁止把"正确答案 + 句首/句尾少量词"（例如在正确句后加 `everyone` / `here` / `for you`）作为主要干扰项手法——这种方式会通过长度/格式暴露正确答案。

### 23.4 确定性校验（继续作为最终闸门）

AI 只产生候选。已实现并保持的校验（缺一不可）：

```text
正确答案重复（same_as_answer） · 干扰项互相重复（duplicate） · 空值/异常文本（empty / meta_or_abnormal_text）
· evidence 缺失（no_evidence） · 教材阶段越界（out_of_stage） · confidence 不足（low_confidence）
· 异常长度（abnormal_length） · 追加型干扰项（appended_tail_or_prefix）
```

其中"追加型"判定为确定性词级规则：**候选完整保留正确答案的词序，且只在句首/句尾追加 ≤ 少量词 → 过滤**（不引入 NLP / 语义相似度系统）。正常的教材词汇替换、句子成分替换不受影响。未经校验的 AI 输出不得进入页面或缓存。

### 23.5 数量规则（随资源，不固定）

```text
3 个合格干扰项 → 4 选项
2 个 → 3 选项
1 个 → 2 选项
0 个 → 不硬凑，走既有回落机制
```

这是"根据实际合格资源动态决定"，不是固定题型规格。

### 23.6 调用时机与缓存

```text
离线生成 → 确定性校验 → 缓存 → 页面只读缓存
```

- 页面打开、切题、刷新、答题都不做即时 AI 生成；不因刷新/切题/重复练习重复调用。
- 缓存键必须与教材版本、Unit / Section（课时）、具体教材资源、`PROMPT_VERSION`、`RULES_VERSION` 稳定关联。
- 规则或 Prompt 版本变化后，旧版本结果不得当作新版本结果复用（当前句子听辨即通过 `PROMPT_VERSION` + `RULES_VERSION` 隔离）。
- 不建立第二套平行缓存体系；缓存机制沿用既有实现。
- 没有合格缓存时走既有回落机制，不阻塞页面，不展示未经校验的 AI 结果。

### 23.7 与 Demo 的关系

### 24. AI 挖空素材规则（2026-09-29 同步 · 按裁决新增）

本节固化 AI 的**第二类事**：**按音频补全教材文本挖空**（作为素材）。

**24.1 音频来源**

- **只允许官方教材 MP3**（`contentpack` 的教材音频资源）；不得重新切割官方 MP3、不得用 AI 生成音频、不得调用在线音频。
- 挖空必须以**教材文本与官方音频的已确认对应关系**为依据（VERIFIED 区间 / `audio_source_code` / `start_ms` / `end_ms`）。

**24.2 落库字段（与 V1.3 第二十九章 §16 同口径）**

| 内容 | 落库位置 | 约定 |
| --- | --- | --- |
| 挖空文本 | `question.prompt_json` 的 **`text`** | 空位用 **`______`**（6 个下划线）表示 |
| 空位数量 | **`prompt_json.blank_count`** | 整数 |
| 答案 | **`answer_json`** | 与既有题型约定一致 |
| 来源标注 | `question.origin` + `prompt_json.question_origin` / `prompt_json.distractor_origin` | **必须标注**，便于追溯哪些内容由 AI 补全 |

**24.3 生成纪律**

- **不得猜测补齐**：无法确认的教材内容必须标记为待确认，不得进入孩子界面（见 §4 规则 4）。
- 挖空素材是**教材事实的搬运与变形**，不是新造内容；不得改变教材原意、不得引入教材外词汇与结构。
- **不硬凑**：合格资源不足时不生成（**允许 0 道**），见 §4 规则 3。

---
### 25. AI 补全/出题的题型优先级（2026-09-29 同步 · 按裁决新增）

**适用范围**：仅指 AI 在题库中的两类事（**补干扰项** / **按音频补全挖空**）以及**依据教材资源出题**时的**题型倾向**。

- **优先**：**听力**（`listen_*` / `sentence_listen_*`）、**阅读**（`reading_choice`）、**语境词汇**（`vocab_context_choice` / `phrase_meaning_choice`）。
- **少补**：**孤立拼写**（`vocab_phonetic_write` / `phonetics_symbol_write`）、**纯语法**类。

**与 §4 规则 3「不设固定题量」的边界（必须同时遵守）**：

- 本节是**优先级 / 倾向**，**不是固定配额**——**不得**据此推导出「每类固定 N 题」或「优先题型必须占某个比例」；
- **§4 规则 3 仍然优先**：有合适学习点就多生成，没有合适内容就少生成，**允许生成 0 道**；
- 当「优先题型」没有合格资源时，**不得**为凑优先级而降低质量或越过教材范围。

---
当前 Demo 的确定性模拟生成、真实 AI Spike 输出与 Demo 缓存都属于**验证机制**，不代表正式生产已经全量采用；
正式全量生成须按本规范的参数与闸门执行，并把 AI 生成结果按第 9–11 章（合格候选判定 / 入库 / 生命周期）处理。

---

## 26. AI 老师·例句来源规则（2026-09-29 同步 · 按裁决新增）

本节为《最高指导原则与开发规范 V1.3》第二十九章 §18 的**细则版**（结论在 V1.3，字段与成本在本节）。

### 26.1 三句话输出

| 句 | 内容 | 约束 |
| --- | --- | --- |
| 1 | **错在哪** | 一句话；孩子能懂的词；不用语法术语 |
| 2 | **该用什么** | 一句话；讲清正确用法；不展开 |
| 3 | **一个例句** | 一句话；来源见 26.2；越界则丢弃 |

**恰好三句**；每句不超过一行；无第四句。

### 26.2 例句来源三层优先级

```text
① 检索课文原文（text_references：活动 ↔ 内容块，含 sample）-> 合适就用（标来源）
② 取不到 -> 依教材素材（本册 + 已学过的前置）生成合乎逻辑的例句
③ 都不行 -> 不给（宁缺毋滥，只保留前两句）
```

### 26.3 检索范围与守界

- **范围** = 当前课时 + 之前学过的课时：`learned_sections()` 已学 Section 集合 **∪** 本题自身 Section。
- **守界** = 不超教材范围 + 只用学过的内容；**越界即丢弃第 3 句**（确定性闸门拦截，**不采信 AI 自证**，与第 8 节 A–J 十类校验同精神）。

### 26.4 分层覆盖（如实）

| 分层 | 范围 | 路径 |
| --- | --- | --- |
| ① 有映射课时 | **25 / 46**（`text_references` 实测） | 检索课文原文 |
| ② 无映射课时 | **21 / 46** | AI 依教材素材生成 |
| ② 词表课 | `WORDS_AND_EXPRESSIONS` | 教材侧**无课文**（`activity`=0、`content_block`=0）；素材 = `learning_item` 词汇条目，**无课时归属** |

> **⚠️ 25/46 是「课时覆盖率」，不是「适用题占比」** —— 两者口径不同，**不得混用或互相换算**。

### 26.5 落点与下发（第一步已实现）

- **落点**：`web/ui.py` 的 `_p5_feedback()` 答错分支（**唯一落点**，仅 1 处调用）。
- **下发容器**：`<script id="zx-teach" type="application/json">`（**非可执行脚本**，复用 J1 的 `json.dumps` + `<`/`>` 转义做法；**不复用 `zx-evidence`** —— 后者的注入条件为 `answer_kind == "ai_eval"`，与客观题答错场景互斥）。
- **下发字段**：`_question_id` / `question_type` / `instruction` / `text` / `options` / `picked` / `answer` / `unit_code` / `section_key` / `_granularity` / `_resolved_via` / `evidence_pool`（含 `related_text` / `related_vocabulary` / `textbook_reference`）。
- **不下发**：`answer_kind` 不在 `("option_key","exact","normalized")`，或 `unit_code` / `section_key` 为空。

### 26.6 成本与失败

- **触发**：仅答错，1 题 1 次（可选缓存）。
- **调用量**：约 600–900 prompt tokens；输出约 60–120 tokens ⇒ **`maxTokens` 建议 320**。
- **通路**：复用 `AiClient.chatJson` + `AiConfidenceGate`，**不新建机制**。
- **失败**：AI 不可用 / 未配置 / 超时 / 桥未注入 → **保持现状**（只显示正确答案），**不阻断确定性学习功能**（Android 基线 §9 同口径）。

### 26.7 数据来源

`textbook_content_relations_v2.json`（`text_references`）/ `textbook_structure_v2.json`（`pdf_page_start` 课时顺序）/ `textbook_context_relations_v2.json`（`belongs_to`：`A:xxx` → Section）。

---

## 27. AI 指令按题型族分派（2026-09-29 同步 · 按裁决新增）

本节为 V1.3 第二十九章 §19 第 4 条的**细则版**：**AI 指令必须按题型族分别设计，不得统一模板**。

### 27.1 四个题型族

| 族 | 覆盖题型（示例） | 指令重点 | 不得出现 |
| --- | --- | --- | --- |
| **语法类** | `vocab_word_form`（词形变化） | 讲"该用哪个形式"与规则出处（教材附录）；例句须体现该形式 | 不得展开完整语法体系；不得引入教材外语法的术语 |
| **词汇类** | `vocab_listen_write` / `vocab_meaning_choice` / `vocab_context_choice` / `phrase_meaning_choice` / `vocab_phonetic_write` | 讲"词义 / 搭配 / 语境"；例句须是教材语境句 | 不得只给中文释义了事；不得用教材外词造句 |
| **理解类** | `textbook_native` / `sentence_listen_*` / `listening_choice` / `listen_*` / `reading_choice` | 讲"听到了 / 读到了什么"与判断依据（教材原句） | 不得脱离教材原文推断；不得编造教材未说的事实 |
| **写作类** | 写作 / 连词成句类（当前正式数据以 `textbook_native` 承载） | 讲"该怎么组织句子"；例句须是可仿写的教材句 | 不得给范文式长文；不得超出该 Unit 词汇 |

### 27.2 共同硬约束（四族通用，不得因分族而放松）

- **三句话**（错在哪 / 该用什么 / 例句）；每句不超过一行；无第四句（V1.3 §18）。
- **例句来源三层优先级**：课文原文检索 → 教材素材生成 → 不给（宁缺毋滥）。
- **范围**：以题目自身粒度定锚点（Section 级 `section_key` / Unit 级 `unit_code`），再向已学内容扩展。
- **守界**：越界即丢弃例句（确定性闸门拦截，**不采信 AI 自证**）。
- **失败不阻断**：AI 不可用 / 未配置 / 超时 / 桥未注入 ⇒ 保持现状（只显示正确答案）。

### 27.3 与既有章节的关系

本节**不重复** §26 的字段与落点（那部分唯一权威在 §26）；本节只补"**指令内容按题型族分派**"这一层。
