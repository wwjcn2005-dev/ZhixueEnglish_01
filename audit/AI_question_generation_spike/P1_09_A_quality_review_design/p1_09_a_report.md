# P1-09-A 实施报告 · AI 英语质量复核只读设计审计

结论：**P1-09-A_PASS**

本阶段只做 READ-ONLY AUDIT + DESIGN：读取现有代码、数据库、报告与正式规范，确认报告里的机制是否仍然存在，
并设计"AI 英语质量复核"应该放在哪一层、审什么、输出什么、是否入库。

```text
AI 调用 = 0           （未调用 DeepSeek / Ollama / 任何模型）
新题生成 = 0
question_library.db 修改 = 0    （SHA256 前后一致）
learning.db / contentpack / 教材 PDF / 54 MP3 / Web / Android 修改 = 0
validator v2 / v3 修改 = 0
新依赖 = 0
```

---

## 1. 侦察结果：报告中的机制是否仍然存在（实测，不是看报告）

| 机制 | 实测方式 | 结果 |
| --- | --- | --- |
| `question_library.db` schema v2 | 只读 `PRAGMA user_version` + `sqlite_master` | **存在**，`user_version=2`，6 张表 |
| 6 个生命周期硬门槛触发器 | 只读 `sqlite_master` | **6/6 存在**：`trg_ai_question_insert_active_forbidden`、`trg_ai_question_active_requires_human_approval`、`trg_ai_question_no_delete`、`trg_question_event_no_update`、`trg_question_event_no_delete`、`trg_validation_exact_trap` |
| validator v2 | 读源码 + 重算 | **存在**，SHA256 `7C61585A…DCA683` |
| validator v3 | 读源码 + 重算 | **存在**，SHA256 `EDB1AA54…8D900C`，v2 原样转出、只收紧 fill 结构规则 |
| 8 项确定性校验 | 读 `validate_question()` 源码 + 读库内 `checks_json` | **存在且一致**：`1_location / 2_evidence_ids / 3_evidence_quote / 4_answer_support / 5_vocab_scope / 6_options / 7_dedup / 8_type_rules` |
| P1-07 五道入库闸门 | 读库内 `checks_json` | **存在**：`gate1_evidence_complete`、`gate2_not_textbook_original`、`gate3_mechanical_allowed`、`gate4_no_duplicate`、`gate5_schema_provenance` + `gate5_detail` |
| DeepSeek 生成实现 | 读 `P1_06_batch_stability/run_p1_06.py` | **存在**：`https://api.deepseek.com/chat/completions`、`deepseek-v4-pro`、`temperature=0.2`、`max_tokens=16384`、`thinking={"type":"enabled"}`、`reasoning_effort=low`、`prompt_version=P1-05-v3` |
| 截断保护 | 读 `P1_05_budget_calibration/generation_guard.py` 的调用点 | **存在**：`finish_reason=length` → `TRUNCATED` → 立即停止 |
| 生命周期硬门槛有效性 | 读 `P1_08_C_lifecycle_run/lifecycle_test_result.json`（12 项拒绝性测试） | **仍然有效**：12/12 越权路径被拒 |
| judge 题 answer_support 口径 | 重算 21 题 | **仍是 schema v2 兼容处理**（见 §9），V1.0 §17.1 的 "schema v3 待办" 仍未解决 |

### 1.1 当前 `question_library.db` 实测状态

```text
path          D:\ZhixueEnglish\structured\ai\question_library.db
SHA256        7AA12CA5EB24417BF0AE7E97A8161920B501825D030D69A8E0863272AC695DA7
size          180,224 B
user_version  2
integrity     ok        foreign_key_check  空

generation_run 12 · ai_question 21 · question_evidence 22
question_learning_object 37 · question_validation 21 · question_event 44

lifecycle   ACTIVE 1 · PENDING_REVIEW 19 · REJECTED 1
events      VALIDATED 21 · PENDING_REVIEW 19 · REVIEW_APPROVED 1
            ACTIVATED 1 · REVIEW_REJECTED 1 · MARKED_STALE 1

题型        fill 9 · vocab_choice 6 · reading_choice 4 · reading_judge 2
answer_support（库内取值）  EXACT 18 · VERIFIABLE_REPHRASE 3
validator   v3 19 条 · v2 2 条（P1-03 遗留）
```

`ACTIVE=1` 与 `PENDING_REVIEW=19`、`REJECTED=1` 与 P1-08-C 收口状态一致，说明报告描述的机制没有被后续改动破坏。

---

## 2. A. AI 质量复核应该放在哪一层

### 2.1 四个方案的比较（只列事实性差异，不做评分）

| 维度 | 方案 A 同一个 AI 自查 | 方案 B 第二次独立 AI 复核 | 方案 C 只人工审核 | 方案 D AI 复核 + 人工审核 |
| --- | --- | --- | --- | --- |
| 可靠性 | 低：与生成同一上下文、同一角色，倾向确认自己刚产出的答案 | 中：独立一次调用能换一个视角，但仍有同源盲点（同一模型家族） | 取决于审核人英语水平；**本项目负责人不是英语教师**，无法判断英语质量 | 中高：AI 负责语言/教育质量初筛，人只看"是否值得采用" |
| 成本 | 最低（可以塞进生成同一次调用） | 中：每 Section 一次批量复核 ≈ 生成的 8.4%（见 §10） | 0 token，但人工时间成本最高 | 中：等于方案 B |
| 延迟 | 不增加调用次数，但会拉长生成调用 | 增加一次调用；批量复核输入仅 1.6–2.3 KB | 0 | 同 B（批量） |
| 防止自我循环 | 最差：同一次输出里"自己批准自己" | 中：换角色、换上下文、不带生成解释 | 最好（不涉及模型） | 好：模型结论必须经人类确认 |
| 实施复杂度 | 低 | 低（可直接复用现有 DeepSeek 调用路径） | 最低（现有 PENDING_REVIEW 流程已支持） | 低（B 的产物给现有审核动作当输入） |
| 与当前系统兼容性 | 需改生成 prompt 与输出 schema | 完全兼容：生成链路不动，新增只读复核调用 | 完全兼容，但缺审核入口（P1-08-C F1） | 完全兼容，且正好补上 F1 的信息缺口 |

### 2.2 关键事实（来自本轮实测，不是推测）

1. **方案 C 单独不成立**：P1-08-C 的审核记录写明审核人 `human:project-owner` 只做了事实性追溯核对，
   明确未做英语质量判断。P1-08-C 同时观察到"某些题程序验证通过但学习价值较低""某些填空题答案并不唯一"——
   这两件事恰好是人工审核人**没有能力判断**的部分。因此"只靠人工"无法闭合质量判断。
2. **方案 A 的独立性最弱**：同一个 prompt、同一段上下文、同一次输出里判断自己刚写的题，
   等于把"生成正确"和"质量合格"合并成一个不可区分的结论；本轮 §9 已给出具体的自我循环风险清单。
3. **方案 D 与既有规范不冲突**：V1.3 二十四·1 规定 AI 职责是"分析 → 评估 → 反馈 → 建议"，
   二十四·3 规定"AI 只能建议"；V1.0 §13 规定人工审核后 `PENDING_REVIEW → APPROVED`。
   AI 复核只产出建议、人类仍然做最终确认，二者天然对齐。

### 2.3 推荐路线

> **采用方案 D：生成 AI → 程序验证 → 第二次独立 AI 英语质量复核（建议）→ 人类最终确认 → APPROVED → 显式启用 → ACTIVE。**

理由（可直接落到工程上）：

- AI 复核补的是**程序确定的盲区**（英语质量、答案唯一性、自然度、学习价值、干扰项、年级适配）；
- 人类审核人不需要懂英语也能用：AI 复核把"判断英语"翻译成"读一句中文理由 + 按一个按钮"；
- 不改变任何现有硬门槛：AI 复核**不产生任何生命周期事件**，`PENDING_REVIEW → APPROVED → ACTIVE` 的路径完全不动；
- 成本可控：批量复核只占生成成本的个位数百分比（§10），不需要换模型、不需要新依赖。

---

## 3. B. AI 质量复核到底审什么

任务书列出 8 个候选维度。本轮的结论是**压缩为 6 个 AI 维度 + 2 个程序维度**，不做"几十条规则"。

### 3.1 职责分工（明确边界）

| 关注点 | 负责方 | 依据 |
| --- | --- | --- |
| 教材定位是否真实（unit/section/activity/page） | **程序** | validator 第 1 项 + P1-07 gate1 |
| evidence_block_id 是否存在 | **程序** | validator 第 2 项 |
| evidence_quote 是否命中教材原文 | **程序** | validator 第 3 项 |
| 答案是否被教材证据支持（EXACT / REFERENCE / REPHRASE） | **程序** | validator 第 4 项 + `answer_support_type` |
| 词汇是否越界 | **程序** | validator 第 5 项 + 词形归一化 |
| 选项唯一性（结构）/ correct_option 与 answer 一致 | **程序** | validator 第 6 项 |
| 批次内去重 / 与题库去重 | **程序** | validator 第 7 项 + P1-07 gate4 |
| 题型结构是否合法 | **程序** | validator 第 8 项（v3 收紧 fill） |
| 是否教材原题 / 机械复现 | **程序算标志 + AI 判断价值** | `mechanical_rewrite` / `original_textbook` 由程序算出；是否仍值得做由 AI 判断 |
| **英语是否正确** | **AI 复核** | 本轮设计 |
| **答案是否唯一（含替代答案）** | **AI 复核** | 本轮设计 |
| **表达是否自然** | **AI 复核** | 本轮设计 |
| **学习价值高低** | **AI 复核** | 本轮设计 |
| **干扰项质量** | **AI 复核**（仅选择题） | 本轮设计 |
| **是否适合初一阶段** | **AI 复核** | 本轮设计 |

### 3.2 维度压缩结果

```text
AI 复核 6 维：english_correct · answer_unique · naturalness
                learning_value · distractor_quality · grade_fit
程序保留 2 维：mechanical_reproduction（程序已算） · evidence_consistency（程序负责）
```

- `mechanical_reproduction` **不设成 AI 字段**：同一个事实不设两个来源。程序已经算出 `mechanical_rewrite`，
  AI 只需要回答"这条机械挖空还有没有学习价值"（= `learning_value`）。
- `evidence_consistency` **不进 AI 复核**：教材边界、证据存在性、词汇边界由程序负责，AI 不以任何形式重新裁决。
  AI 拿到 `evidence_quote` 只是为了"在教材语境下"判断语言与教学价值，不是让它重做程序已经做完的检查。

---

## 4. C. 最小输出结构，以及每个字段该不该永久存储

完整结构见 `review_output_design.json`。设计原则：**不机械照抄字段列表**，每个字段都要能回答"谁来用、存哪里"。

### 4.1 最小输出（每道题一条）

```text
question_id · suggested_decision · english_correct · answer_unique · naturalness
learning_value · distractor_quality · grade_fit · short_reason · confidence
```

对任务书给的字段列表，本设计做了三处明确调整：

| 原字段 | 本设计处理 | 理由 |
| --- | --- | --- |
| `overall_decision` | 改名 `suggested_decision`，取值只允许 `suggest_approve / suggest_fix / suggest_reject` | 避免与生命周期 `APPROVED / ACTIVE` 同形，从命名上堵住"AI 结论被当成审核结论写入" |
| `mechanical_reproduction` | 删除该 AI 字段 | 程序已确定性计算 `mechanical_rewrite`；AI 只在 `learning_value` 里体现代价 |
| `evidence_consistency` | 删除该 AI 字段 | 证据边界由程序负责；不设第二个来源 |

### 4.2 字段存储分级（A 永久存储 / B 仅审核过程 / C 不应存储）

**A · 若未来采用，只持久化这些**（append-only，绝不覆盖原题）

```text
question_id · suggested_decision · english_correct · answer_unique · naturalness
learning_value · distractor_quality · grade_fit · short_reason · confidence
reviewer_model · prompt_version · review_context_hash · reviewed_at
```

最后 4 项是可追溯链：没有它们，AI 复核结论就无法回答"是哪次、哪个模型、看的哪份输入"作出的。

**B · 只留在审计 / 运行包，不进入正式库**

```text
原始模型响应全文（raw_response.json）
逐题长解释（超过 short_reason 的部分）
prompt_tokens / completion_tokens / reasoning_tokens / latency
reviewer system prompt 全文与 payload
确定性 triage 命中记录与规则版本
模型中间推理过程（不展示给任何用户）
```

**C · 不应该存储**

```text
把 AI 结论写成 lifecycle_status，或写进 question_event（AI 复核不是审核事件）
把 AI 复核写进 question_validation（该表语义是程序验证结果）
AI 改写后的题干 / 选项 / 答案（AI 只能给意见，不能覆盖原题）
面向孩子的评价文案（评价语言由学习层统一）
AI 的 chain-of-thought
以 actor_kind='human' 记录的 AI 结论（伪造人工审核）
```

最关键的一条：**AI 复核结果不能覆盖原题，只能是"审核意见"**。题目文本、选项、答案一旦生成入库，
就只能被人工驳回（`REVIEW_REJECTED`）或人工批准（`REVIEW_APPROVED`），不能被模型改写。

---

## 5. D. AI 复核是否应该写入 question_library.db

### 5.1 三个候选落点与取舍

| 落点 | 可行性 | 问题 |
| --- | --- | --- |
| 复用 `question_validation` 表（`validator_version='ai-review-v1'`） | 技术上可以塞进去 | **不应该**。该表语义是"程序验证结果"（`validation_result` 只有 PASS/FAIL、`answer_support_type` 只有 4 值枚举）。混入 AI 意见后，无法区分"机器验证通过"与"模型觉得不错"，正好破坏本项目最重视的那条边界。另外本轮已实测该表被 judge 题的兼容编码占用（§9），再加一层语义必然混淆。 |
| 新增表 `question_ai_review`（纯增量） | 干净 | 属于 schema v3：`user_version 2 → 3`。V1.0 §19.4 允许"只能新增版本"，但这是**正式 schema 变更**，不应在本轮 Spike 里做。 |
| 审核运行包文件（`structured/ai/quality_review/<review_run_id>.json`）+ `question_fingerprint` 关联 | 干净、可回退 | 不享受数据库的引用完整性与 append-only 保护，需要读取方自己校验指纹。 |

### 5.2 本轮结论

> **本轮不升级 schema。** AI 复核结果先用"审核运行包文件"落地，结构与未来 `question_ai_review` 表**同构**，
> 用 `question_id` + `question_fingerprint` 建立稳定关联；读取时必须校验指纹与 DB 一致，不一致就拒绝使用。

理由：

1. **能不能不升级 schema？能。** AI 复核是"对题目的意见"，不是题干/选项/答案本身，也不参与生命周期；
   文件形式完全可以承载，且 P1-08-C 已经证明生命周期硬门槛不依赖它。
2. **但现在就升级 schema 并不划算。** 复核口径（维度、阈值、是否批量）还没在真实题上验证过；
   先用文件跑一轮，口径稳定后再一次性把结构搬进表，避免 schema 反复改。
3. **最终仍然需要 schema v3 的纯新增表**，如果 AI 复核要成为正式审核链路的一部分（补上 P1-08-C 的 F1 缺口：
   没有正式审核入口）。届时的变更应当是：**只新增 `question_ai_review` + 两个 append-only 触发器，
   不修改任何既有表/列/触发器/索引，不新增 event_type**。草案见 `schema_v3_draft.sql`（design only，未执行）。

### 5.3 三个必须守住的约束（无论落在哪里）

```text
1. AI 复核结果 不得 写入 lifecycle_status，不得 生成 question_event
2. AI 复核结果 不得 修改题干 / 选项 / 答案
3. AI 复核结论 不得 以 actor_kind='human' 出现
```

---

## 6. E. "同一个模型审自己"的问题

当前生成模型是 DeepSeek（`deepseek-v4-pro`）。如果用它审自己生成的题，会同时存在四类风险：

1. **自我确认**：同一模型对自己刚产出的答案有先验偏好，容易给出"这个答案是对的、这条题没问题"的结论。
   本轮已有一个具体例子：`AIQ:75AAEBFE06DF` 的干扰项 `traditional` 是教材 BOLD 核心词、语法上同样能填进空里
   （"But it's a traditional kind of music." 完全成立），只有读课文才能排除。生成模型当时把它当成好干扰项，
   同一个模型复读一遍大概率也会说"干扰项合理"。
2. **对错误答案的坚持**：模型倾向于证明自己的产出合理。填空类题目尤其危险——
   模型会默认"我写空位的那个词当然唯一"，而不是主动寻找替代答案。
3. **与生成 prompt 的偏差**：生成时模型被要求"优先教材学习点、尽量多出题"，这个目标压力会带进复核。
   如果复核复用生成 prompt 或生成上下文，等于让它重复生成时的判断。
4. **第二次调用是否真的"独立"**：独立 = 独立 session、独立 system prompt、独立输入、不携带生成时的
   `explanation` 与"必须产出 N 道题"的指令。**如果做不到这四点，第二次调用只是复读，不是复核。**

### 6.1 最小可行方案（不引入第二个模型）

```text
1. 独立调用：新的 request，不带生成时的 system prompt / explanation / 题量压力
2. 角色对抗：system prompt 明确要求"先尝试找出至少一个更合理的替代答案或至少一个语言问题；
   只有确实找不到时才判 unique / ok"
3. 输入只给：题干、选项、正确答案、教材引文、页码 —— 不给内部 ID、不给其它题的答案
4. 输出固定 schema（本报告 §4），其中 answer_unique=ambiguous 时必须写出替代答案
5. 记录 review_context_hash 与 prompt_version，与生成账目并列，便于事后审计
6. 先用确定性 triage（§10.4）决定"哪些题值得花这次复核"，而不是全量复核
7. 每道题的复核结论只作建议，人类仍然必须点"通过"
```

### 6.2 必须如实说明的局限

> 同一模型 + 不同角色，只能**降低**自我循环，不能**消除**它。
> "第二次调用是否真的独立"不能用设计宣称，只能用实测回答：在一批真实题上比较
> **AI 复核结论 vs 人工结论**的一致率与漏检率。这件事属于 P1-09-B，本轮不宣称已经解决。
> 本轮也不假设必须换第二个模型——在有了上述实测数据之前，换模型只是换一个未知。

---

## 7. F. 用现有真实题设计下一阶段测试样本

全部来自当前 `question_library.db`，每题都从库里读取（不是手抄、不是 AI 生成）。
完整明细见 `sample_matrix.json`。

| 类别 | 真实样本 | 说明 |
| --- | --- | --- |
| 1 明显合格题 | `AIQ:BD59C5958D45`（ACTIVE）、`AIQ:04CC9B1CF690` | 答案在教材原句逐字命中，答案为 BOLD 核心词 |
| 2 低学习价值题 | `AIQ:1B3AF72923C4`、`AIQ:1BA260727793` | 前者已在 P1-08-C 被人工驳回；后者是双空挖空的语篇标记词片段 |
| 3 答案不唯一风险题 | `AIQ:1B3AF72923C4`、`AIQ:120FFEECA78F` | 程序都判 EXACT；单看题干时 happy/fine 或任意颜色同样成立 |
| 4 机械挖空题 | 7 条（含 `AIQ:BD59C5958D45`） | `mechanical_rewrite=True`，其中包含已审核通过的题 → 机械挖空 ≠ 不合格 |
| 5 选择题干扰项风险题 | `AIQ:75AAEBFE06DF`、`AIQ:3179968E3E74`、`AIQ:B6463523F9E5` | 干扰项全部是教材合法素材且语法成立，只能靠课文排除 |
| 6 阅读理解题 | 4 条 `reading_choice` | 含唯一一条 `difficulty=medium`、`VERIFIABLE_REPHRASE` 的 `AIQ:6ECD02B9D381` |
| 7 `vocabulary_choice` | 6 条（全部） | —— |
| 8 `fill` | 9 条（全部） | 含 P1-03 遗留、v3 判结构不合法的 `AIQ:7EBCDBC29563` |
| 9 `judge` | 2 条（全部） | True / False 各一条 |

### 7.1 现有真实样本不足的类别（如实声明）

```text
现有真实样本不足：英语本身存在错误的题
  21 条真实题里没有语法/拼写错误题，程序与人工都没发现语言错误。
  要验证"AI 复核能否发现真实英语错误"，只能另建人工撰写的 fixture（不得调用 AI 生成）。

现有真实样本不足：干扰项明显垃圾/荒谬的题
  现有选择题干扰项全部来自教材词表，没有明显无意义选项。

现有真实样本不足：难度明显超出初一阶段的题
  21 条题全部 easy，仅 1 条 medium；grade_fit 没有真实反例。
```

下一阶段（P1-09-B）建议的固定样本 = 上表 9 类中的真实题。九类**去重后正好覆盖当前题库全部 21 条题**
（多条题同时属于多个类别，例如 `AIQ:1B3AF72923C4` 同时出现在低价值、答案不唯一、机械挖空三类），
再加上由人工撰写的少量 fixture（英语错误题 1 条、荒谬干扰项 1 条）。
全部作为固定夹具反复使用，不允许用 AI 现场生成。

---

## 8. G. P1-08-C Sample B 与 validator 的能力边界（实测）

### 8.1 重算结果

对 21 道真实题**只读重算** validator v2/v3（`validator_capability_check.json`）：19/21 与库内记录一致，
2 条不一致的全部是 `reading_judge`（原因见 §8.3）。

| 题 | 程序判定 | 该题的真实问题 | validator 能否发现 |
| --- | --- | --- | --- |
| `AIQ:1B3AF72923C4`（P1-08-C Sample B）<br>"I am ___, too." → ready | `answer_support=EXACT`，`type_rules=ok`，**8 项全过** | 单看题干答案不唯一（happy / fine / tired 同样成立）；学习价值低 | **不能** |
| `AIQ:120FFEECA78F`<br>"What colour is it? It's ___." → grey | `EXACT`，`type_rules=ok`，**8 项全过** | 同样的独立唯一性问题：任意颜色都成立 | **不能** |
| `AIQ:75AAEBFE06DF`<br>"But it's a ___ kind of music." → different | `EXACT`，`type_rules=ok`，**8 项全过** | 干扰项 `traditional` 是教材 BOLD 核心词且语法成立 | **不能** |
| `AIQ:7EBCDBC29563`（STALE） | `answer_support=EXACT`，但 **`type_rules=FAIL`**：`fill must not carry options` | 题型标记为 fill 却带 options | **能**（v3 收紧规则后；P1-04 正是因此把它标 `VALIDATOR_CHANGED`） |

### 8.2 结论：这是"程序硬验证"与"AI 教育质量复核"的明确边界

validator v2/v3 的 8 项全部是**结构 / 证据 / 词汇 / 去重**类确定性判断，
代码里不存在任何判断"英语质量""答案唯一性""学习价值""干扰项是否合理"的逻辑。
所以：

```text
程序验证 PASS  不表示  英语质量合格
程序验证 PASS  不表示  答案唯一
程序验证 PASS  不表示  值得给孩子做
```

补充一个词汇校验的事实：库内 `out_of_scope_tokens_json` 并非全空，例如 `AIQ:5B4C80443D5F`
是 `["points","student"]`、`AIQ:A9D1F3EC6020` 是 `["writes"]` —— 这三个词经 P1-04 的 D3 词形归一化层
（points→point、writes→write、student→students）判定为教材内合法词形，入库时按通过处理
（`checks_json.d3_vocab_after_lemma=true`）。说明"词汇越界"这一项也已有明确归属与处理口径。

**本轮不修改 validator。** 这条边界不需要靠继续加 validator 规则来补齐——
它天然属于 AI 质量复核 + 人类最终确认的职责（§3.1）。

### 8.3 顺带实测到的一个既存口径问题（只记录，不修改）

两条 `reading_judge` 题的库内 `answer_support_type` 是 `VERIFIABLE_REPHRASE`，
而 validator 重算结果是 `UNSUPPORTED` —— 因为布尔答案"True / False"本质上无法被教材引文逐字支持。
P1-07 按 V1.0 §17.1 的 D2 口径做了 `rule4_waived_for_judge` 兼容处理，并把真实依据写进 `checks_json` / `note`，
枚举字段只能填最接近的可用值。

这说明：**`question_validation` 表已经被用作"兼容编码"**，因此更不应该把 AI 复核结果塞进这张表（§5.1）。
该问题的正式修复（judge 的 answer_support 表达）仍登记为 schema v3 待办，与本阶段结论一致。

---

## 9. H. 成本与调用次数

### 9.1 实测基准（真实调用数据，不是假设）

| 来源 | Section | 题数 | prompt | completion | reasoning | total | 延迟 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P1-06 S1 | U2 UI | 6 | 11,387 | 12,021 | 10,823 | 23,408 | 176.5 s |
| P1-06 S2 | U1 UI | 5 | 9,448 | 7,852 | 7,111 | 17,300 | 111.3 s |
| P1-06 S3 | U5 UI | 6 | 10,812 | 11,796 | 10,884 | 22,608 | 161.5 s |
| P1-06 S4 | Starter GR | 5 | 9,928 | 9,397 | 8,706 | 19,325 | 133.2 s |
| P1-05-D 校准 | U2 UI | 10 | 10,540 | 12,434 | 10,481 | 22,974 | 172.9 s |

```text
P1-06 合计：4 次调用 / 22 题 / 82,641 tokens / 约 582 s
折算：平均每题 3,756 tokens
chars/token 标定：由 4 次真实请求实测得出 3.074 chars/token（不是猜测值）
```

### 9.2 复核输入规模（程序侧构造，未调用 AI）

把每个 Section 的题目（题干 + 选项 + 答案 + 教材引文）打包成复核输入：

```text
S1  6 题  2,279 字符  ≈ 741 tokens
S2  5 题  1,647 字符  ≈ 536 tokens
S3  6 题  2,103 字符  ≈ 684 tokens
S4  5 题  1,619 字符  ≈ 527 tokens
```

即：**复核输入比生成输入小一个数量级**（生成 prompt 约 29,000–35,000 字符）。

### 9.3 四种方案（含调用次数、token 与相对成本）

| 方案 | 调用次数 | 输入 tokens | 输出 tokens | 合计 | 占该批生成成本（82,641 tokens） |
| --- | --- | --- | --- | --- | --- |
| 1 每题一次复核 | 22 | 20,210 | 4,840 | 25,050 | 30.3% |
| 2 每 Section 批量复核 | 4 | 4,985 | 1,920 | 6,905 | 8.4% |
| 3 只复核程序 PASS 的题 | 4 | 4,985 | 1,920 | 6,905 | 同方案 2（本数据集程序 PASS=22/22，过滤后一条都没少） |
| 4 只复核高风险题（宽口径 triage，11 题） | 1 | 1,919 | 2,420 | 4,339 | 5.3% |
| 4b 只复核高风险题（窄口径 triage，5 题） | 1 | 1,334 | 1,100 | 2,434 | 2.9% |

输出 token 按每题 220（8 个短字段 + 一句中文理由）估算；延迟主要由**调用次数**决定
（22 次串行 vs 4 次串行 vs 1 次），而不是 token 总量。

### 9.4 确定性 triage（程序侧，无 AI）——以及它的边界

本轮实现了一组确定性 triage 规则（`triage_result.json`，只读计算）：

```text
T1 fill 去掉空位后英文实词 < 6 个（语境不足）
T2 fill 有 2 个以上空位
T3 mechanical_rewrite=true 且去空位后 < 8 词
T4 选择题干扰项是同一 Unit 词表里与答案同词性的词
T5 fill 题型却带 options（validator v3 必判不合法）
```

实测命中：**宽口径 11/21**（T1–T5 任一），**窄口径 5/21**（T1/T2/T3/T5，不含 T4）。

必须如实说明 T4 的局限：**它会把合格题一起命中。** 已在 P1-08-C 人工审核通过、
现在是 `ACTIVE` 的 `AIQ:BD59C5958D45` 的四个选项全部是教材 BOLD 核心词、同词性，
同样会被 T4 命中。也就是说 T4 描述的是"答案只能靠课文决定"这一类**风险特征**，不是缺陷判定。

因此 triage 的正确定位是：**决定把复核预算花在哪里，而不是决定题目合不合格。**
不能让 triage 单独当闸门。

T4 的具体数据（只读查 contentpack v5 教材词表，输出见 `probe_pos.py`）：

```text
AIQ:3179968E3E74  polite(adj,CORE,BOLD) + dry(adj,CORE,BOLD) / important(adj,CORE,BOLD) / mistake(n,CORE,BOLD)
AIQ:75AAEBFE06DF  different / traditional / electric / weak   全部 adj,CORE,BOLD
AIQ:BD59C5958D45  band / club / stage / instrument            全部 n,CORE,BOLD（已通过人工审核并 ACTIVE）
AIQ:6721EC6C5D1F  root(RECOGNITION,PLAIN) + stem / sugar(CORE,BOLD) / oxygen(RECOGNITION,PLAIN)  全部 n
```

即：干扰项全部来自教材词表，多数还是 **BOLD 重点词**。"同词性 + 教材合法 + 语法上也能填"这三件事同时成立时，
**只有读课文才能排除**——而"这个干扰项是否已经不公平"是语言判断，属于 AI 复核，不属于 triage。

### 9.5 成本结论

- 逐题复核（方案 1）调用次数是方案 2 的 5.5 倍（22 vs 4）、token 成本约 3.6 倍（25,050 vs 6,905），
  收益只是"单次上下文更小"，不划算；
- **批量复核（方案 2）是当前性价比最好的基线**：每 Section 一次调用、约 8.4% 的生成成本，
  且与"以 Section 为生成边界"的既有结构一致（同一个 Section 的题一起看，复核者还能顺带发现同 Section 内的重复）；
- triage 预筛（方案 4b）能把复核开销从 8.4% 压到约 2.9%，但覆盖面只剩 22 题中的 5 题，
  只有在 triage 规则本身被真实数据验证过之后才值得启用；
- 复核用不着 `max_tokens=16384`，也不需要与生成相同的 thinking 设置——但**具体参数属于 P1-09-B 待实测项**，
  本轮不预设。

---

## 10. "AI 复核 PASS ≠ APPROVED ≠ ACTIVE"

这一条在本轮被显式验证过（读 P1-08-C 实测记录 + 只读检查数据库触发器）：

```text
question_library.db 中 6 个触发器仍然在位：
  trg_ai_question_insert_active_forbidden       新题不能以 ACTIVE 插入
  trg_ai_question_active_requires_human_approval 转 ACTIVE 必须有人类 REVIEW_APPROVED 事件
  trg_ai_question_no_delete                     题目不可删除
  trg_question_event_no_update                  事件不可修改
  trg_question_event_no_delete                  事件不可删除
  trg_validation_exact_trap                     EXACT 命中时强制 needs_human_review=1

P1-08-C 12 项拒绝性测试：12/12 被拦下（含未审核直接 ACTIVE、REJECTED -> ACTIVE、STALE -> ACTIVE）
唯一可进入学习候选的条件：lifecycle_status='ACTIVE' AND active=1 AND stale=0
```

因此本设计的硬性约束是：

```text
AI 复核只能说 "建议通过 / 建议修改 / 建议驳回"
                        ↓ （只是建议，不产生任何事件）
人类点击"通过"          →  question_event: REVIEW_APPROVED (actor_kind='human')
                        ↓
APPROVED                →  仍需 显式 ACTIVATED
                        ↓
ACTIVE                  →  才可能被学习候选读取
```

---

## 11. J. 未来审核界面需要的最小信息（只设计，不实现）

目标读者是**不会英语的家长**。因此界面不展示任何技术字段，只回答五个问题：

```text
这是什么题        → 题干 + 选项
正确答案是什么    → 正确答案
教材在哪          → 第 X 页 + 教材原句
AI 觉得哪里有风险 → 一句话中文结论（short_reason）
AI 是否建议采用   → 建议通过 / 建议修改 / 建议驳回
是否需要我再看    → 由 answer_unique / english_correct 推导的"需要人工确认"标记
```

操作只有三个：`通过 / 驳回 / 暂缓`。`通过` 必须由人类点击并记录为 `actor_kind='human'`。

不得出现在界面上（V1.0 §18 已冻结）：`model`、`prompt_version`、`context_hash`、`generation_run_id`、
`validator_version`、`evidence_block_id`、`lifecycle_status`、`question_fingerprint`、任何数据库内部 ID。

界面本身**本轮不实现**，也不新增页面；按 V2.0 的页面层级最小化原则，它应该作为现有审核动作的入口，
而不是新的一级页面。

---

## 12. 保护项与副作用

本轮只新增了一个独立审计目录：

```text
audit/AI_question_generation_spike/P1_09_A_quality_review_design/
```

前后哈希清单（1,099 个文件，覆盖 `structured/learning`、`structured/contentpack` v1–v5、
`structured/textbook`、`structured/audio`（含 54 个官方 MP3）、`structured/exercises`、`structured/staging`、
`structured/ai`、`docs`、`web`、`android`、教材 PDF、validator v2/v3、P0 closeout 与 P1-04/05/06/07/08 全部产物、
V1.3 / V2.0 正式文档）：

```text
manifest before  FE66A3291BC97805D7646F54C5748C775BD89D56D910339D87B97B9EEB449653
manifest after   FE66A3291BC97805D7646F54C5748C775BD89D56D910339D87B97B9EEB449653
added / removed / modified = 0 / 0 / 0
```

`question_library.db` 与 `learning.db` 在本阶段全程只以 `?mode=ro` 只读 URI 打开；
导入 validator 时使用 `python -B`（`sys.dont_write_bytecode=True`），不写入任何 `__pycache__`。

```text
AI 调用 0 · 新题 0 · question_library.db 0 修改 · learning.db 0 修改
contentpack 0 修改 · Web / Android 0 修改 · V1.0 / V1.3 / V2.0 0 修改 · 新依赖 0
```

---

## 13. 最终验收（任务书 16 项）

| # | 验收项 | 结果 |
| --- | --- | --- |
| 1 | 已实际读取当前 `question_library.db` schema | **是**：`user_version=2`、6 表 6 触发器、列清单与完整性全部实测（§1） |
| 2 | 已实际确认当前生成 / 验证机制 | **是**：读 `run_p1_06.py`、`validator_v2.py`、`validator_v3.py`、库内 `checks_json`（§1） |
| 3 | 已分析 AI 质量复核应该放在哪里 | **是**：方案 A/B/C/D 比较 + 推荐方案 D（§2） |
| 4 | 已明确与程序验证、人类确认的职责边界 | **是**：8 关注点分工表 + 6 AI 维 / 2 程序维（§3） |
| 5 | 已设计最小输出结构 | **是**：`review_output_design.json`，10 字段 + A/B/C 存储分级（§4） |
| 6 | 已分析是否需要 schema v3 | **是**：本轮不升级；最终需纯新增 `question_ai_review`（§5 + `schema_v3_draft.sql`） |
| 7 | 已分析成本 / 调用次数 | **是**：基于 5 次真实调用的 token 标定 + 4 方案对比（§9） |
| 8 | 已用现有真实题设计下一阶段测试样本 | **是**：9 类全部有真实样本，3 类如实声明样本不足（§7） |
| 9 | AI 调用 0 次 | **是** |
| 10 | `question_library.db` 0 修改 | **是**（SHA256 前后一致 `7AA12CA5…5DA7`） |
| 11 | `learning.db` 0 修改 | **是** |
| 12 | contentpack 0 修改 | **是**（v1–v5 全部未变） |
| 13 | Web / Android 0 修改 | **是** |
| 14 | V1.3 / V2.0 / V1.0 流程规范 0 修改 | **是** |
| 15 | 未安装任何依赖 | **是**（只用标准库 `sqlite3 / json / hashlib / re`） |
| 16 | 没有伪造 AI 质量审核结果 | **是**：本阶段产出全部是只读审计事实与设计文档，没有任何"AI 复核结论"数据 |

---

## 14. 结论

```text
P1-09-A_PASS
```

本阶段确认并设计了三件事：

1. **机制仍然存在**：schema v2 + 6 个触发器 + validator v2/v3 + P1-07 五道闸门 + 生命周期硬门槛，
   全部经实测复核，报告的结论没有被后续改动破坏。
2. **边界必须分开**：程序负责硬边界（定位、证据、词汇、结构、重复、生命周期），
   AI 质量复核负责程序无法确定性判断的**语言与教育质量**（英语正确性、答案唯一性、自然度、学习价值、
   干扰项、年级适配），人类负责**最终是否采用**。
3. **AI 复核只能当助手**：它进不了 `PENDING_REVIEW → APPROVED → ACTIVE` 任何一步；
   本轮不升级 schema、不进正式题库、不改 validator、不改任何正式数据。

仍未验证、必须留给下一阶段的部分（不得在本轮写成已解决）：

```text
AI 质量复核在真实题上的准确率 / 漏检率（AI 结论 vs 人工结论）
同一模型自我复核的真实独立性（只能用实测一致率回答）
复核调用的最佳参数（max_tokens / thinking / reasoning_effort）
复核口径稳定后 question_ai_review 表的正式落地（schema v3）
judge 题 answer_support 语义（schema v3 待办，P1-09-A 未处理）
缺少真实反例的三类样本（英语错误题 / 荒谬干扰项 / 超纲题）需要人工 fixture
```

本阶段完成报告后停止，不进入 P1-09-B。
