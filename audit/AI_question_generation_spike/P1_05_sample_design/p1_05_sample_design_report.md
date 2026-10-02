# P1-05-A · AI 题库多 Section 小规模质量验证——只读设计与样本审计报告

最终状态：**DESIGN_PASS**

本轮：**AI 调用 0**，未生成任何题目，未修改任何正式数据。

---

## 0. 结论

当前机制**值得进入小规模真实验证（P1-05-B）**，并已冻结一套包含 **7 个 Section** 的实验方案。

同时明确写下三条纪律：

1. **题量不设配额**——有合适的就多生成，没有就少生成，0 题也是合法结果；
2. **听力证据缺口单列**——不混入普通题目质量评价；
3. **这是工程质量小样本验证**，不能据此推断整本教材的总体质量。

---

## 1. 只读审计：当前真实状态

### 1.1 题库与校验器

| 项 | 当前值 |
| --- | --- |
| `question_library.db` schema | **v2**（`user_version = 2`，integrity ok，无外键违规） |
| 表 | 6 张（`generation_run` / `ai_question` / `question_evidence` / `question_learning_object` / `question_validation` / `question_event`） |
| 题目 | **2 道**，均为 `PENDING_REVIEW`，`active = 0`，**0 道 ACTIVE** |
| 其中 stale | 1 道（`AIQ:7EBCDBC29563`，`stale_reason = VALIDATOR_CHANGED`，P1-04 标记） |
| 事件 | 3 条（2× `VALIDATED` + 1× `MARKED_STALE`），无 `REVIEW_APPROVED` |
| validator | **v3**（P1-04）为最新；**v2 冻结未改**（SHA256 `7C61585A…A683`） |
| 跨库引用 | 3 条 LearningObject + 2 条 evidence block，**全部有效，无悬空** |

### 1.2 教材资源

| 项 | 值 |
| --- | --- |
| contentpack v5 | 3,854 content_block / 520 learning_item / 178 页 / 54 MP3 / `ai_artifact` 0 行 |
| 证据包 | `textbook_evidence_map_v1.json` 共 **360 包** |
| 教材原题 | 157 exercises / **360 questions** / 21 个 listening 活动 |
| **音频文本证据** | `transcript` **0 行**、`audio_token_annotation` **0 行**、`audio_sentence_annotation` **15 行** |
| 官方答案来源 | 360 包与 157 exercise 的 `answer_source` / `answer_status` **全部为 `NO_RELIABLE_SOURCE`** |

### 1.3 历史生成记录（成本基线）

| 轮次 | 模型 | 调用 | prompt / completion / reasoning tokens | 延迟 | 生成 | 入库 |
| --- | --- | --- | --- | --- | --- | --- |
| P0 1450 | deepseek-v4-pro | 1 | 6,837 / 3,904 / 3,296 | 63.0 s | 3 | 3 |
| P0 1610 | 同上 | 1 | 9,451 / 4,096 / 4,096 | 73.1 s | 0（截断） | 0 |
| P0 1630 | 同上 | 1 | 9,451 / 6,123 / 5,648 | 113.3 s | 3 | 3 |
| P0 1650 | 同上 | 1 | 4,154 / 243 / 179 | 6.5 s | 0（证据不足） | 0 |
| P1-03 | 同上 | 1 | 9,451 / 7,332 / 6,638 | 116.6 s | 3 | 2（1 被 validator 拦截） |
| **P0/P1 合计** | — | **5 次云端** | — | — | 9 | 8 |

本地 Qwen 路线已在 P0 判定不可用（GPU 失败 + CPU 2.02 tok/s 超时），本方案不使用。

---

## 2. 选择了哪些 Section，为什么

**不是随机抽样**：按教材形态定向选择 **7 个 Section**，覆盖任务要求的 A–F 六类。

| # | Section | 类别 | 教材页 | blocks | 证据包 | 原题 | 词汇 / 加粗 | 密度 | 选择理由 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Unit 2 · UNDERSTANDING_IDEAS | A 阅读 | 31–34 | 83 | 21 | 21 | 21 / 19 | high | 正文证据最丰富 |
| 2 | Unit 6 · READING_FOR_WRITING | A 阅读 | 104–107 | 54 | 12 | 12 | 16 / 11 | high | 读写结合，含 writing 活动 |
| 3 | Unit 1 · UNDERSTANDING_IDEAS | B 对话（直接引语） | 16–20 | 55 | 19 | 19 | 14 / 12 | high | 含直接引语叙述；**同时是 P1-03 的产生地**，可观测跨轮重复 |
| 4 | Unit 5 · UNDERSTANDING_IDEAS | C 词汇 / 语言运用 | 79–82 | 77 | 21 | 21 | **23 / 17** | high | 词汇最密集，4 个 fill |
| 5 | Starter · GET_READY | D 信息匹配 / 判断 | 3–5 | 77 | 21 | 21 | 15 / 10 | high | 含 match×3 / fill×2 / choice×1 |
| 6 | Unit 3 · STARTING_OUT | E 低证据密度 | 47 | 11 | 4 | 4 | 0 / 0 | **low** | 观察是否会自然少生成 |
| 7 | Unit 1 · DEVELOPING_IDEAS | F 听力证据缺口 | 21–22 | 62 | 14 | 14 | 8 / 8 | high | **对照组**，不计入质量指标 |

### 类别覆盖核对

```text
A 阅读类        ≥2 → 实际 2（#1 #2）
B 对话类        ≥1 → 实际 1（#3，直接引语叙述）
C 词汇/语言运用  ≥1 → 实际 1（#4）
D 信息理解/匹配  ≥1 → 实际 1（#5）
E 低证据密度     ≥1 → 实际 1（#6）
F 证据不足对照   ≤1 → 实际 1（#7）
```

### 关于 B 类（对话）的如实说明

这本教材里**真正的对话文本主要存在于听力层**（例如 Unit 1 DI 的 "Listen to the conversation"），
而听力层当前 **没有文本证据**。因此 B 类只能选取**含直接引语叙述**的 Section
（Unit 1 UI 的段落里有 `"My name's Pan Ming. What's your name?"` 这类直接引语）。
这不是理想样本，但在当前证据条件下是最诚实的替代；P1-05-B 报告中必须保留这一说明。

### 关于 #3 复用 P1-03 产生地的说明

选择 Unit 1 UI 是**有意为之**：它是 P1-03 已入库 2 道题的地方。
P1-05-B 使用**新的 `prompt_version`**，因此 `generation_scope_key` 不同（符合"不重复生成同一 scope key"），
可以合法地观察 **跨轮重复** 与 **同一 evidence block 被重复使用** 的现象。

---

## 3. 每个 Section 的证据情况

完整字段见 `p1_05_sample_matrix.json`，其中包含：
`unit_id` / `section_id` / `section_title` / `activity_ids` / `activity_types` /
`textbook_page_range` / `pdf_page_range` / `content_block_count` / `evidence_package_count` /
`question_count` / `audio_required` / `audio_evidence_available` / `vocabulary_count` /
`bold_vocabulary_count` / `reading_available` / `dialogue_available` / `evidence_density` /
`sample_reason` / `expected_risk`。

### 证据密度分布

```text
high   : 6 个（#1 #2 #3 #4 #5 #7）
medium : 0 个
low    : 1 个（#6 Unit 3 STARTING_OUT）
```

> **密度定义**（写入矩阵的 `field_definitions`）：
> `high` = 非页脚 block ≥ 50 且证据包 ≥ 12；
> `medium` = block ≥ 20 且包 ≥ 6；其余为 `low`。
> 密度只描述证据体量，不是质量评分。

### 每条 `expected_risk` 只描述实验风险

```text
RICH_READING              正文充足，风险在于可能生成过多同质题
DISTRACTOR_RISK           读写段抽象表达多，干扰项可能难以排除
HIGH_DUPLICATION_RISK     该 Section 已有 2 道入库题，需重点观察重复
VOCABULARY_SCOPE          词汇密集，越界风险与“只考词表”风险同时存在
PARTIAL_AUDIO_SCOPE       该 Section 含听力活动，只能对非听力活动出题
LOW_EVIDENCE              证据少，观察是否自然少生成
LISTENING_EVIDENCE_GAP    音频内容无文本证据，无法可靠出题
```

---

## 4. 哪些属于听力证据缺口

### 4.1 缺口事实

```text
transcript                 0 行
audio_token_annotation     0 行
audio_sentence_annotation  15 行（仅覆盖 Unit 1 的 2 个活动）
教材中 audio_required=true 的活动  21 个
```

### 4.2 处理方式（冻结）

| Section | 处理 |
| --- | --- |
| #7 Unit 1 · DEVELOPING_IDEAS | **整段标记 `LISTENING_EVIDENCE_GAP`**，仅作"宁缺毋滥"对照；其题量**不进入质量分母** |
| #5 Starter · GET_READY | 该段含 3 个听力活动 → 标记 `PARTIAL_AUDIO_SCOPE`；**只对非听力活动出题**，听力活动排除 |
| 其余 5 个 Section | 不含 audio_required 活动 |

### 4.3 为什么必须分开

听力题的答案依赖音频内容，而文本层没有音频转写。
若把这类样本混入质量评价，会把"证据缺口"误判成"模型质量差"。
因此 P1-05-B 报告中：

> **`LISTENING_EVIDENCE_GAP` 单独成节，不参与 Evidence PASS Rate / Natural Value Rate 的分母。**

---

## 5. P1-05-B 将如何执行（冻结方案）

### 5.1 冻结项

| 项 | 冻结值 |
| --- | --- |
| 生成单元 | **Section**（可读整个 Section 的合法证据包），但每题必须保留 **Activity 级 provenance** |
| validator | **P1-04 的 `validator_v3`**（v2 保持冻结） |
| 题库 | 当前 `question_library.db`（schema v2） |
| 模型 | `deepseek-v4-pro`（不使用本地 Qwen，不使用其他 AI） |
| `prompt_version` | **`P1-05-v1`**（新版本，见 5.2） |
| `generation_run` | **每个 Section 一条独立 run** |
| `context_hash` | 每次调用前记录 |
| `generation_scope_key` | 同一 scope key 不得重复生成 |
| `max_tokens` | 8192（P0/P1-03 已验证足够） |
| `temperature` | 0.2 |
| 题型 | 仅 `fill` / `vocab_choice` / `reading_choice` / `reading_judge`（均有已验证证据支撑） |
| 入库状态 | 一律 `GENERATED → VALIDATED → PENDING_REVIEW`，**不得 ACTIVE** |
| 调用纪律 | 默认 **0 重试**；仅当 HTTP 层失败且**未产生任何 content** 时允许最多 1 次重试并记入 `retry_count`；**内容质量不达标不得重试** |

### 5.2 `P1-05-v1` 相对 P0 `P0-v1` 的唯一改动：**去掉题量配额**

```text
删除：  "Quantity: AT MOST 3 questions. Fewer is acceptable; 0 is acceptable..."
        "Prefer this distribution when the evidence allows: 1 fill, 1 vocab_choice, 1 ..."

替换为：
  "Quantity: no quota. Generate as many questions as the supplied textbook evidence can
   reliably and uniquely support, and no more. Fewer is acceptable. 0 is an acceptable
   and expected answer when the evidence does not support reliable, unique, traceable
   questions. Do not create a question merely to reach a number. Prefer covering
   different pieces of evidence over restating the same sentence."
```

其余 10 条硬规则、JSON schema、题型定义**逐字保持不变**。
P1-05-B 首次调用前必须记录该 prompt 的 SHA256，并写入 `generation_run` 与报告。

### 5.3 每题必须记录的额外观察字段

除既有字段外，P1-05-B 每题额外记录（**仅后台**）：

| 字段 | 用途 |
| --- | --- |
| `evidence_quote` | 已有（`question_evidence`） |
| `printed_option_overlap` | **§十三 风险观察**：正确答案是否出现在该 Section 教材原题打印的选项文本中 |
| `evidence_block_reuse` | 该 evidence block 在本轮/历史中被使用过几次 |

`printed_option_overlap` 的判定方式（确定性、可复核）：

```text
对该题所属 Section 的每个证据包，取其 original_question.options 文本；
若题目的 correct_answer 文本出现在其中 → printed_option_overlap = true
→ 该题进入人工重点复核队列（EXACT 可能只是"教材印了答案"）
```

### 5.4 执行顺序（每个 Section 重复一次）

```text
① 读该 Section 的合法证据包 → 组装 input_context → 记录 context_hash
② 查 generation_scope_key：若已存在同一 scope key 的成功 run → 跳过该 Section（记录 SKIPPED）
③ 创建 generation_run（in-flight）
④ 调用 DeepSeek 1 次
⑤ 回填 generation_run（status / question_count / usage / finish_reason / latency / retry_count）
⑥ validator_v3 校验（先验证，后入库）
⑦ 仅 PASS 题入库：ai_question + question_evidence + question_learning_object
   + question_validation，事件链 GENERATED → VALIDATED → PENDING_REVIEW
⑧ 落盘原始响应与逐题校验结果到 P1-05-B 审计目录
```

### 5.5 预计规模与成本（用于预算，不是配额）

```text
Section 数     : 7（其中 1 个为对照组）
预计调用       : ≤ 7 次
预计总耗时     : 约 12–15 分钟（按历史单次 63–117 s 估算）
预计总 token   : 约 60k–120k（按历史单次 4k–17k 估算）
```

---

## 6. 人工审核如何进行

使用 `p1_05_human_review_template.md`。每题只做 **6 个 PASS/FAIL 判断 + 1 个最终归类**：

```text
① 教材依据 PASS/FAIL
② 答案是否明确 PASS/FAIL
③ 题目是否自然 PASS/FAIL
④ 是否有独立学习价值 PASS/FAIL
⑤ 是否与已有题重复 PASS/FAIL
⑥ 是否超出初一教材范围 PASS/FAIL
最终：APPROVE / REJECT_CONTENT / REJECT_QUALITY / REJECT_SCOPE
```

审核界面**不得显示** `model` / `prompt_version` / `context_hash` / `generation_run_id` /
`validator_version` / `evidence_block_id` / `question_fingerprint`。
审核员只看到：题目、选项、答案、解析、**教材原页与原文引用**、以及"教材第 XX 页"这样的自然语言来源。

审核按 **Section 分组**进行，每组先看该 Section 的教材原文，再看题。

---

## 7. 如何计算质量指标

| 指标 | 计算方式 |
| --- | --- |
| **Evidence PASS Rate** | `validator PASS / generated`（同时列出 FAIL 数与失败项分布） |
| **Human Value Rate** | `APPROVE / generated` |
| **Natural Value Rate** | 同 Human Value Rate（以生成总数为分母，含被 validator 拦截的题） |
| **Validator Interception** | 按失败项分类计数：vocabulary scope / evidence / answer support / duplicate / structure / option consistency / other |
| **Duplicate / Near Duplicate** | 四个维度分别统计：① 同 Section 内 ② 跨 Section ③ 同一 evidence block 复用次数 ④ 同一知识点换问法 |
| **Question Count Distribution** | 逐 Section 记录 `0 / 1 / 2 / 3 / …`，并附"该 Section 证据密度与题量是否相称"的定性说明 |
| **Cost** | 每次调用记录 model / prompt / cached / completion / reasoning / total tokens / latency / finish_reason / retry_count / generated_question_count |

### 重复判定原则（冻结）

> **同一教材位置生成多道题本身不算重复。**
> 只有**失去独立学习价值**才算重复（例如同一空位换一个问法、同一 evidence_quote 反复出同类题）。

### Question Count Distribution 的判定原则（冻结）

> **不设上限。** 某 Section 生成很多题不会因为"超出预期"自动判错；
> 需要看它是否重复、是否覆盖不同知识点、每道题是否有独立学习价值。

---

## 8. 如何记录成本

每次真实调用在 `generation_run` 中记录：

```text
model · prompt_tokens · cached_tokens · completion_tokens · reasoning_tokens
total_tokens · elapsed_ms · finish_reason · retry_count · question_count
```

这些数据**只进入后台实验报告**，不得进入任何儿童学习界面。
报告需给出：单次成本表、总计、以及"若扩大到全册约 40 个 Section 的成本外推"（明确标注为估算）。

---

## 9. 什么情况必须停止并修机制

出现以下**任一**情况，P1-05-B 立即停止，不得继续跑完剩余 Section：

| # | 停止条件 |
| --- | --- |
| S1 | 任何**已入库**题被人工判为 `REJECT_CONTENT`（依据不足 / 答案不可靠 / 内容错误） |
| S2 | 出现**教材外事实**（如 P1-03 的 `Mozi`）而 validator 未拦截 |
| S3 | 出现 `ACTIVE` 题，或出现任何 `REVIEW_APPROVED` 事件 |
| S4 | 出现跨库悬空引用（LearningObject / evidence block 不存在） |
| S5 | `learning.db` / contentpack / PDF / MP3 / Web / Android / V1.3 / V2.0 任一被修改 |
| S6 | validator 出现**误报**（合规题被判 FAIL）——需要先修 validator 口径 |
| S7 | 单次调用延迟 > 300 s，或出现需要重试的失败 |
| S8 | 任一 Section 出现"为凑数而产生的明显低价值题"（人工判定 REJECT_QUALITY 且原因是凑数） |

停止后必须先形成机制修正方案，不得直接进入下一阶段。

---

## 10. 什么情况可以进入下一阶段

P1-05-B 只有在**同时满足**以下条件时，才可判定"机制值得继续扩大"：

| # | 问题 | 通过条件 |
| --- | --- | --- |
| A | 机制是否稳定阻止明显错误题 | 已入库题中 **0 道** `REJECT_CONTENT`；所有 validator FAIL 的题确实未入库 |
| B | AI 是否做到"有价值才生成" | **至少 1 个 Section 自然产出 0 题**，且不存在"为凑数而生成"的题 |
| C | APPROVE 比例是否够继续 | `Natural Value Rate ≥ 60%` 且 `APPROVE 绝对数 ≥ 5` |
| D | 不同 Section 是否表现出差异 | 题量分布**不是常数**，且差异能由证据密度解释 |
| E | 成本与延迟是否可接受 | 单次 ≤ 180 s，7 次总耗时 ≤ 30 min，无失败调用 |
| F | 是否暴露必须先修的机制问题 | **无 S1–S8 任一条目被触发** |

### 必须同时写明的边界

> 这是**工程质量小样本验证**。
> 6～7 个 Section 的结果**不能**推断整本教材（40 个 Section）的总体质量；
> 它的作用是发现机制缺陷、prompt 缺陷、validator 缺陷、证据缺陷、人工审核瓶颈与成本问题。

---

## 11. 本轮明确不做

- 未调用任何 AI（云端 0 / 本地 0），未生成任何题目
- 未修改 `learning.db`、contentpack、教材 PDF、MP3、Web、Android、V1.3、V2.0
- 未修改 validator v3、未修改 P1-04 任何产物
- 未删除或重新生成 P1-03 的已有题
- 未执行 P1-05-B

---

## 12. 本轮产物

| 文件 | 说明 |
| --- | --- |
| `README.md` | 索引 |
| `p1_05_sample_design_report.md` | 本报告 |
| `p1_05_sample_matrix.json` | 7 个样本 Section 的证据矩阵（含字段定义与排除说明） |
| `p1_05_human_review_template.md` | 人工审核表 |
| `p1_05_acceptance_criteria.md` | 成功/停止判据 |
| `build_sample_matrix.py` | 矩阵生成脚本（只读） |

结果：**DESIGN_PASS**
