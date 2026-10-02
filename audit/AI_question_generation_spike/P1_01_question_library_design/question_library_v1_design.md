# AI Question Library V1 · 最小数据模型设计

阶段：P1-01（**只设计，不实现**）
状态：设计文档
依赖依据：`P0_closeout/`（P0_CLOSE）、`structured/` 现有正式结构、`validator_v2.py`

---

## 0. 一句话方案

> 新建一个**独立可写数据库** `structured/ai/question_library.db`，
> 用 **6 张表**承载「一次 AI 调用 → 0~N 道题 → 每题多条教材证据 / 多个学习对象 → 多次校验 → 人工审核事件」，
> 所有教材定位字段以**外部引用**形式指向 contentpack v5，
> `learning.db` 在 P1-01 **不做任何修改**。

---

## 1. 只读核对结论（设计的现实依据）

### 1.1 `learning.db` 现状

| 事实 | 对设计的影响 |
| --- | --- |
| 表：`learner` / `learning_task` / `task_item` / `learning_record` / `mastery_state` / `learning_session` / `schema_migration` | 已有一套学习闭环；**无任何 AI 表** |
| `learning_record.item_id` 是**自由文本**，没有 FK | 说明项目已采用「外部内容 ID 引用」模式 |
| 实测：`learning_record` 实际写入的 7 个 `item_id` **全部存在于 contentpack 的 `learning_item`**（`:V:` 词汇与 `:X:` 练习） | AI 题目必须沿用同一套 LearningObject 语义 |
| `mastery_state` 主键 = `(learner_id, item_id)` | 若 AI 题目想进入掌握度聚合，`item_id` 必须仍是 **LearningObject**，不能塞题目 ID 进去 |
| `learning_record` 已有 `textbook_id` / `snapshot_id` | 项目已有 provenance 习惯，可直接沿用 |
| 最近记录时间 2026-09-13 | 学习数据仍在早期，改造成本低，但本次仍**不改** |

### 1.2 contentpack v5 现状（AI 题目的教材锚点）

| 事实 | 对设计的影响 |
| --- | --- |
| `content_block.block_id` 形如 `FLTRP-EN-7A-2022CUR:P22:B6` | `question_evidence.block_id` 直接引用它 |
| `learning_item.item_id` 形如 `FLTRP-EN-7A-2022CUR:V:EAB999ECEC5C`；`item_type ∈ {vocabulary, phrase, sentence_pattern, exercise}` | AI 题目用同一 ID 空间声明「测的是哪个学习对象」 |
| 每张内容表都带 `textbook_id` + `snapshot_id` | 设计沿用 `textbook_id` + `content_snapshot_id` |
| `parse_snapshot` 表记录快照链（含 `status`、`parent_snapshot_id`） | 「教材变了」在项目里已有正式表达方式 |
| `ai_artifact` 表 **0 行** | AI 题目**不写入 contentpack**，保持教材冻结 |
| `transcript` 0 行 / `audio_sentence_annotation` 仅 15 行，而 `audio_required=true` 的听力活动有 21 个 | 听力类活动目前只能走「证据不足 → 不生成」 |

### 1.3 `learning_model_v1.json` 的官方口径

项目自己写得很清楚：

> **Exercise / Question 是产生证据的手段，不是学习对象**；聚合单位是 LearningObject。

这直接决定了本设计的一条硬规则：

> **AI Question 的定位是“证据生产者”，它必须声明自己测哪个 LearningObject，
> 但绝不能取代 LearningObject 成为新的聚合键。**

### 1.4 validator v2 现状

8 项确定性校验 + `answer_support_type ∈ {EXACT, VERIFIABLE_REFERENCE, VERIFIABLE_REPHRASE, UNSUPPORTED}`，
并且 P0 已确认一条结构性边界（本设计第 9 节专门处理）。

---

## 2. 设计原则与边界

1. **教材冻结**：AI 题目一律不写入 contentpack v5；contentpack 只读。
2. **审核前不进入学习系统**：`learning.db` 在 P1-01 保持零改动。
3. **可追溯**：任何 ACTIVE 题目都必须能回答「来自哪本教材、哪个 Unit/Section/Activity/Page、哪些 evidence block、当时 AI 看到了什么、谁生成的、谁批的」。
4. **不覆盖历史**：题目版本只增不改，旧版本永久可查。
5. **最小可用**：6 张表，不为“以后可能用”加表加字段。
6. **可校验的外部引用**：跨库引用（contentpack / learning.db）无法用 FK 强制，必须靠 `content_snapshot_id` + 巡检任务保证不悬空。

---

## 3. 实体总览（6 张表）

| # | 表 | 职责 | 粒度 |
| --- | --- | --- | --- |
| 1 | `generation_run` | 一次 AI 调用的完整账目 | 1 行 / 1 次调用 |
| 2 | `ai_question` | 题目实体（含教材定位与生命周期） | 1 行 / (question_id, version) |
| 3 | `question_evidence` | 题目 ↔ 教材证据块（**多条**） | 1 行 / (question, version, ordinal) |
| 4 | `question_learning_object` | 题目 ↔ LearningObject（**多个**） | 1 行 / (question, version, item_id) |
| 5 | `question_validation` | validator 结果（可多次、可重跑） | 1 行 / (question, version, validator_version) |
| 6 | `question_event` | 生命周期与人工审核事件（**append-only，权威来源**） | 1 行 / 1 次事件 |

为什么是 6 张而不是更少：

- `question_evidence` **必须**独立成表——P0 已确认一道题可能依赖多个 evidence block，塞进 JSON 会让“引文回溯”这条最重要的查询失效。
- `question_learning_object` **必须**独立成表——它是 AI 题目接入 `mastery_state` 的唯一通道，也是最常被查询的关系。
- `question_validation` 独立——同一条题会在 validator 升级后重跑，历史结果必须并存。
- `question_event` 独立——「为什么当时被批准」必须来自不可篡改的事件流，而不是可被覆盖的状态字段。

---

## 4. 逐表字段设计

### 4.1 `generation_run`（AI 调用账目）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `run_id` | TEXT **PK** | `AIRUN:20260917T1440:2F1A` |
| `provider` | TEXT NOT NULL | `deepseek` |
| `model` | TEXT NOT NULL | `deepseek-v4-pro` |
| `prompt_version` | TEXT NOT NULL | `P1` |
| `context_hash` | TEXT NOT NULL | `input_context.json` 的 SHA256 |
| `context_ref` | TEXT | 落盘的 `input_context.json` 路径 |
| `raw_response_ref` | TEXT | 落盘的 `raw_response.json` 路径 |
| `target_unit_id` / `target_section_id` / `target_activity_id` | TEXT | 本次生成范围（用于缓存查询） |
| `generation_scope_key` | TEXT NOT NULL | 见第 8 节（**批量级**复用键） |
| `requested_max` | INTEGER | 请求题量上限（P0 中为 3） |
| `max_tokens` | INTEGER | 实际请求值（P0 中 4096 / 8192） |
| `finish_reason` | TEXT | `stop` / `length` / … |
| `usage_json` | TEXT (**JSON**) | prompt / completion / reasoning tokens |
| `elapsed_ms` | INTEGER | 耗时 |
| `returned_count` | INTEGER NOT NULL DEFAULT 0 | 本次产出的题数（可为 0） |
| `run_status` | TEXT NOT NULL | `OK` / `TRUNCATED` / `API_ERROR` / `INSUFFICIENT_EVIDENCE` |
| `run_note` | TEXT | 模型自述理由（例如 Spike 3 的 `insufficient_evidence_reason`） |
| `started_at` | TEXT NOT NULL | ISO8601 |

**关键判断：`generation_run` 必须独立保存。** 三条理由：

1. P0 实测：**一次调用产出 3 道题**（1450 / 1630），这 3 题必须能彼此知道“同源”；
2. P0 实测：**一次调用产出 0 道题**（1610 截断、1650 证据不足）——如果没有 `generation_run`，
   这两次“失败/拒答”将不留下任何痕迹，复用逻辑就无法判断“这个范围已经试过了、结果是空的”；
3. 成本与预算控制需要按“调用”而不是按“题目”核算。

### 4.2 `ai_question`（题目实体）

| 分组 | 字段 | 类型 | 说明 |
| --- | --- | --- | --- |
| 身份 | `question_id` | TEXT | `AIQ:9F3C1A2B7D04`（**跨版本稳定**） |
| 身份 | `version` | INTEGER | 从 1 开始，只增不改 |
| 身份 | `question_type` | TEXT | `fill` / `vocab_choice` / `reading_choice` / `reading_judge` |
| 内容 | `question_text` | TEXT NOT NULL | 题干 |
| 内容 | `options_json` | TEXT (**JSON**) | 选项数组；非选择题为 NULL |
| 内容 | `correct_option` | TEXT | `A`/`B`…；非选择题为 NULL |
| 内容 | `correct_answer` | TEXT NOT NULL | 标准答案 |
| 内容 | `explanation` | TEXT | 解析（模型输出，非授权证据） |
| 内容 | `difficulty` | TEXT | `easy` / `medium`（P1 保留，成本为零） |
| 来源 | `run_id` | TEXT NOT NULL | → `generation_run.run_id` |
| 来源 | `textbook_id` | TEXT NOT NULL | `FLTRP-EN-7A-2022CUR` |
| 来源 | `curriculum_version` | TEXT | 课程版本（来自 `textbook_edition`） |
| 来源 | `content_snapshot_id` | TEXT | 生成时使用的 contentpack 快照 |
| 来源 | `unit_id` / `section_id` / `activity_id` | TEXT NOT NULL | 教材定位 |
| 来源 | `page` | INTEGER NOT NULL | 教材页码 |
| 生命周期 | `lifecycle_status` | TEXT NOT NULL | 见第 5 节（查询用物化字段） |
| 生命周期 | `stale` | INTEGER NOT NULL DEFAULT 0 | 与状态**正交** |
| 生命周期 | `stale_reason` | TEXT | `EVIDENCE_CHANGED` / `PROMPT_CHANGED` / `MODEL_CHANGED` / `VALIDATOR_CHANGED` |
| 生命周期 | `stale_since` | TEXT | |
| 复用 | `question_fingerprint` | TEXT NOT NULL | 见第 8 节（**题级**指纹） |
| 时间 | `created_at` / `updated_at` | TEXT NOT NULL | |

**主键**：`(question_id, version)` —— 这是“旧题不能被悄悄覆盖”的物理保证。

### 4.3 `question_evidence`（题目 ↔ 教材证据）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `question_id` | TEXT | 联合主键之一 |
| `version` | INTEGER | 联合主键之一 |
| `ordinal` | INTEGER | 联合主键之一，1 = 主证据 |
| `block_id` | TEXT NOT NULL | → contentpack `content_block.block_id` |
| `evidence_quote` | TEXT NOT NULL | 必须是对应 block 文本的（归一化后）逐字子串 |
| `is_primary` | INTEGER NOT NULL DEFAULT 0 | 主证据标记（与 `ordinal=1` 保持一致的冗余） |

**回答第 6 节的问题：一个题目是否可能依赖多个 evidence block？——可能。**
所以这里从一开始就设计成 **1:N**，而不是在 `ai_question` 里放单个 `evidence_block_id`。
（P0 的 6 道题恰好都是单块证据，但设计不能被样本的偶然性锁死。）

### 4.4 `question_learning_object`（题目 ↔ 学习对象）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `question_id` / `version` | TEXT / INTEGER | 联合主键 |
| `item_id` | TEXT | 联合主键；→ contentpack `learning_item.item_id` |
| `is_primary` | INTEGER NOT NULL DEFAULT 0 | 主学习对象 |

这一张表是 AI 题目与现有学习体系之间的**唯一接缝**：
`mastery_state(learner_id, item_id)` 与 `learning_record.item_id` 都按 LearningObject 聚合，
AI 题目只负责“声明我测的是哪些对象”，不改变聚合键。

### 4.5 `question_validation`（validator 结果）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `question_id` / `version` | TEXT / INTEGER | 联合主键 |
| `validator_version` | TEXT | 联合主键；`v2` |
| `validated_at` | TEXT NOT NULL | |
| `overall_status` | TEXT NOT NULL | `PASS` / `FAIL` |
| `checks_json` | TEXT (**JSON**) | 8 项逐项布尔值 |
| `answer_support_type` | TEXT NOT NULL | `EXACT` / `VERIFIABLE_REFERENCE` / `VERIFIABLE_REPHRASE` / `UNSUPPORTED` |
| `needs_human_review` | INTEGER NOT NULL DEFAULT 0 | **专为 `EXACT` 陷阱设置的升级标记** |
| `out_of_scope_tokens_json` | TEXT (**JSON**) | 越界词 |
| `validation_note` | TEXT | |

### 4.6 `question_event`（生命周期 / 审核事件，append-only）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `event_id` | TEXT **PK** | `AIEV:<uuid/时间戳>` |
| `question_id` / `version` | TEXT / INTEGER | 事件对象 |
| `event_type` | TEXT NOT NULL | `VALIDATED` / `REVIEW_APPROVED` / `REVIEW_REJECTED` / `ACTIVATED` / `DISABLED` / `MARKED_STALE` |
| `from_status` / `to_status` | TEXT | 状态迁移前后 |
| `actor_kind` | TEXT NOT NULL | `machine` / `human` |
| `actor` | TEXT NOT NULL | `validator_v2` / 复核人标识 |
| `reason_code` | TEXT | 结构化原因：`TEXTBOOK_MISMATCH` / `AMBIGUOUS_ANSWER` / `BAD_DISTRACTOR` / `OUT_OF_SCOPE` / `LOW_VALUE` / `OTHER` |
| `reason_note` | TEXT | 自由文本说明 |
| `created_at` | TEXT NOT NULL | |

设计选择：**把“人工审核”并入事件表**，而不是单开一张 review 表。
理由：审核本质上就是一次状态迁移，重复建表会让“为什么当时被批准”出现两个事实源。

---

## 5. 生命周期：哪些持久化，哪些用字段组合表达

### 5.1 判断结果

| 状态 | 处理方式 | 理由 |
| --- | --- | --- |
| `GENERATED` | **可由字段推导**（存在题目但无 PASS 校验） | 不需要独立存储 |
| `VALIDATED` | **可由字段推导**（存在 PASS 校验、无审核事件） | 不需要独立存储 |
| `PENDING_REVIEW` | **可由字段推导**（PASS 校验 + 尚未审核 / `needs_human_review=1`） | 不需要独立存储 |
| `APPROVED` | 由 `REVIEW_APPROVED` 事件表达 | 需要事件流 |
| `REJECTED` | 由 `REVIEW_REJECTED` 事件表达 | 需要事件流 |
| `ACTIVE` / `DISABLED` | 需要显式操作 | 需要事件流 |
| **`STALE`** | **不作为状态**，用 `stale` + `stale_reason` 字段表达 | 与生命周期**正交**：一道 ACTIVE 题可以同时是 STALE |

### 5.2 最终落地方式

- **权威来源（source of truth）**：`question_event` 事件流。
- **查询用物化字段**：`ai_question.lifecycle_status`（枚举同上，SELECT 时不必 join 事件表）。
- 二者不一致时**以事件流为准**，并可随时重建 `lifecycle_status`。

### 5.3 状态机

```text
GENERATED ──validator PASS──> VALIDATED ──> PENDING_REVIEW
                                                │
                        ┌──人工通过──────────────┤
                        ↓                        └──人工驳回──> REJECTED
                    APPROVED
                        │ 显式启用
                        ↓
                      ACTIVE ──下线──> DISABLED

任意状态 ──教材/规则/模型/提示词变化──> 标记 stale（状态不变，stale=1）
```

**硬性规则（来自 P0 结论）**：

> **validator PASS 绝不等于 APPROVED。**
> PASS 只能把题目推进到 `VALIDATED`，必须经人工审核才能到 `APPROVED`，
> 再经**显式启用**才能到 `ACTIVE`（唯一允许进入学习系统的状态）。

---

## 6. 版本与 STALE（旧题不能被悄悄覆盖）

### 6.1 场景推演

```text
Q001 v1  model=deepseek-v4-pro  prompt_version=P1  context_hash=ABC
        ↓ prompt 改成 P2
新生成的题目不是「覆盖 Q001」，而是：
Q001 v2  model=deepseek-v4-pro  prompt_version=P2  context_hash=ABC
        └─ 旧行 Q001/v1 完整保留（PK 保证），仅被标记 stale=1 + stale_reason=PROMPT_CHANGED
```

### 6.2 四条规则

1. **旧版本永不删除、永不 UPDATE 内容字段**（只允许更新 `stale*` / `lifecycle_status`）。
2. 内容变化 = **新建 version**，不是改旧行。
3. 触发 `stale` 的四类变化（对应四个 `stale_reason`）：
   - `EVIDENCE_CHANGED`：`content_snapshot_id` 变化（教材重建）
   - `PROMPT_CHANGED`：`prompt_version` 升级
   - `MODEL_CHANGED`：生成模型更换
   - `VALIDATOR_CHANGED`：validator 规则发生影响性变化
4. `stale=1` 的题**不得**再作为复用来源，但**仍可被查询与导出**；重新通过校验后可解除 stale。

**为什么不用简单的 `is_active` 布尔**：布尔无法区分“批准”与“上线”，也无法承载驳回原因；
也无法表达“已上线但因教材改版而失效”。

---

## 7. 与 `learning.db` 的关系（本次不改，只说明未来）

### 7.1 结论

> **P1-01 不修改 `learning.db`。** 且在这条关联打通之前，AI 题目**不得**进入孩子可见的学习流程。

### 7.2 为什么必须补一个字段

现在的 `learning_record` 只能回答“孩子练了哪个 LearningObject”，
**无法**回答“练的是哪一道题的哪个版本”。而 P0 已经把「可追溯」定为硬要求。

### 7.3 推荐的最小迁移（设计在此，执行不在本轮）

```sql
-- 设计草案，本轮不执行
ALTER TABLE learning_record ADD COLUMN source_kind TEXT;     -- 'contentpack' | 'ai_library'
ALTER TABLE learning_record ADD COLUMN source_ref TEXT;      -- 'AIQ:9F3C1A2B7D04'
ALTER TABLE learning_record ADD COLUMN source_version INTEGER;
CREATE INDEX idx_record_source ON learning_record(source_kind, source_ref);
```

保留 `learning_record.item_id` 的**既有语义**（= LearningObject），
这样 `mastery_state` 的聚合逻辑完全不用改。

### 7.4 写入时的取值规则

| 字段 | 取值 |
| --- | --- |
| `item_id` | 仍为 LearningObject（`FLTRP-EN-7A-2022CUR:V:…`） |
| `source_kind` | `ai_library` |
| `source_ref` | `AIQ:9F3C1A2B7D04` |
| `source_version` | `2` |

即 **`question_id` + `question_version` 是必要的，但只有它们还不够**——
还需要一个字段说明“这条记录来自哪个题库”，否则将来 contentpack 题目与 AI 题目会在同一条记录里失去区分。

---

## 8. 复用与缓存（对 P0 建议的修正）

### 8.1 审计 P0 的 `reuse_key`

P0 建议：`hash(section_id, activity_id, question_type, prompt_version, context_hash)`

| 审计问题 | 结论 |
| --- | --- |
| 是否足够唯一？ | **作为“题目键”不够**。P0 实测一次调用就产出 3 道 **不同类型**的题，说明该键描述的是**一次生成的范围**，不是一道题 |
| 是否会导致不同题型冲突？ | 不会冲突，但会把“同一范围的不同题型”割裂成不同批次，反而**妨碍**一次调用批量产出多题型 |
| 同一 evidence 下是否允许多个不同题目？ | 该键**不限制**这一点（它不含题干），所以不会误伤——但它也就无法用于题级去重 |
| 一次 generation run 是否可能产生多题？ | **是**（P0 实测 3 题），因此键的粒度必须与 run 对齐，而不是与 question 对齐 |
| REJECTED 题如何防止无意义重复生成？ | 该键**做不到**——它不包含题干，无法识别“上次被驳回的就是这道题” |

### 8.2 修正为**两个键**（推荐）

```text
generation_scope_key  = hash(section_id, activity_id, prompt_version, context_hash)
   → 挂在 generation_run 上；回答“这个范围用这套提示词和这批证据，生成过了吗？”
   → 作用：阻止无意义的重复 AI 调用（0 次调用即可判定）

question_fingerprint  = hash(section_id, activity_id, question_type,
                             normalized(question_text), normalized(evidence_quote))
   → 挂在 ai_question 上；回答“这道题是不是已经存在？”
   → 作用：题级去重 + REJECTED 抑制 + STALE 后重生的识别
```

注意两处刻意的设计：

1. `generation_scope_key` **不含 `question_type`**——因为一次调用会同时产出多种题型。
2. `question_fingerprint` **不含 `prompt_version` / `model`**——这样“被驳回的题”不会因为换了提示词就换个马甲重新进来。

### 8.3 三类命中规则

| 场景 | 处理 |
| --- | --- |
| 命中 `ACTIVE` 且 `stale=0` | **直接复用，0 次 AI 调用** |
| 命中 `PENDING_REVIEW` / `APPROVED` | 复用待审条目，**不重复生成** |
| 命中 `REJECTED`（fingerprint 相同） | **直接丢弃**，不送审、不再生成（默认永久；如需重试必须显式覆盖） |
| 命中 `stale=1` | 可作为“参考”但不作为可用题；必须重新校验或重新生成 |

### 8.4 唯一约束的取舍

- `question_fingerprint` **不做全局唯一**——否则教材改版后合法重生会被挡住。
- 只对“当前线上可用”加部分唯一索引：

```sql
CREATE UNIQUE INDEX uq_question_active
  ON ai_question(question_fingerprint)
  WHERE lifecycle_status = 'ACTIVE' AND stale = 0;
```

---

## 9. validator 结果如何持久化（含 `EXACT` 陷阱）

P0 已确认：

> 当选项文本本身出现在教材证据里时，`answer_support = EXACT` **不等于**答案真的被教材证据证明。

### 9.1 必须持久化的 validator 结果

| 字段 | 必须？ | 理由 |
| --- | --- | --- |
| `overall_status` | **必须** | 决定能否进入待审 |
| `checks_json`（8 项） | **必须** | 事后解释“当时为什么能过” |
| `answer_support_type` | **必须** | 直接对应 `EXACT` 陷阱 |
| `needs_human_review` | **必须** | 把陷阱变成可执行标记，而不是靠人记住 |
| `validator_version` | **必须** | 规则变了必须能分辨旧结论 |
| `out_of_scope_tokens_json` | 建议 | 解释词汇越界判定 |
| 完整原始 stdout / 日志 | 不需要入库 | 归入审计日志（文件），不进题库 |

### 9.2 针对 `EXACT` 陷阱的规则设计（写入题库模型，而非事后补丁）

```text
若 answer_support_type == 'EXACT'
   且 该 answer 文本同样出现在「题干或选项自身」中
   （即命中原因是“教材印着这个选项”，而不是“教材正文陈述了该事实”）
则 → needs_human_review = 1，并禁止走自动快通道
```

这条规则**不需要改 validator**，它属于题库侧的判定，可先用人工规则 + 已有 `checks` 数据实现。

### 9.3 「为什么这道题当时被批准」的完整可解释链

```text
question_event(REVIEW_APPROVED, actor=复核人, reason_code, created_at)
        +
question_validation(validator_version, checks_json, answer_support_type, validated_at)
        +
generation_run(model, prompt_version, context_hash, context_ref, raw_response_ref)
        +
question_evidence(block_id, evidence_quote)
        ↓
可完整回答：谁批的、依据什么规则、当时 AI 看到什么、引用了教材哪一句
```

---

## 10. 教育质量字段：P1 必须 / 可以暂不做 / 以后再加

### P1 必须

| 字段 | 理由 |
| --- | --- |
| `question_type` | 题型规则、复用键、学习场景选择都要用 |
| `difficulty` | 模型本来就输出，成本为零，用于排序与难度分层 |
| `question_learning_object`（关系） | 没有它，AI 题目无法进入现有掌握度聚合 |
| `explanation` | 复核界面与孩子看解析都需要 |

### P1 可以暂不做

| 字段 | 替代方案 |
| --- | --- |
| `quality_note` | 用 `question_event.reason_note` 表达 |
| `skill`（听说读写标签） | 可由 `question_type` + LearningObject 类型推导 |
| `estimated_time` | 暂无使用者 |

### 后续需要时再增加

`learning_objective`（先由 `question_learning_object` 覆盖）、`usage_count`、
`first_used_at`、`distractor_review_note`、`variant_of`（同源变式题）。

**原则**：最小可用，而不是一次设计完整宇宙。

---

## 11. 明确不做

- ❌ 不修改 contentpack v5，不把 AI 题目混入教材原始数据
- ❌ 不修改 `learning.db`（本轮零改动）
- ❌ 不直接覆盖旧题（版本只增；旧题只标记 stale）
- ❌ 不允许 validator PASS 自动 ACTIVE
- ❌ 不允许页面直接触发生成
- ❌ 不把一次生成结果当作临时响应后丢弃（`generation_run` 必须落库，**含 0 题的失败/拒答**）
- ❌ 不把 AI 原始 reasoning 作为正式题目字段（只保留 `raw_response_ref` 指向原始文件）
- ❌ 不为未来可能需求提前建立十几张表的系统

---

## 12. 推荐方案汇总（对应任务要求的 13 项）

| # | 项目 | 推荐 |
| --- | --- | --- |
| 1 | 需要几个实体/表 | **6 张**：generation_run、ai_question、question_evidence、question_learning_object、question_validation、question_event |
| 2 | 核心字段 | 见第 4 节逐表字段表 |
| 3 | 主键 | `generation_run(run_id)`；`ai_question(question_id, version)`；`question_evidence(question_id, version, ordinal)`；`question_learning_object(question_id, version, item_id)`；`question_validation(question_id, version, validator_version)`；`question_event(event_id)` |
| 4 | 外键关系 | 库内：全部指向 `ai_question(question_id, version)`，`ai_question.run_id → generation_run`；跨库：`block_id` / `item_id` / `unit_id` 等为**外部引用**，SQLite 无法强制，靠 `content_snapshot_id` + 巡检任务 |
| 5 | JSON 字段 | `options_json`、`checks_json`、`out_of_scope_tokens_json`、`usage_json`（**仅这 4 个**） |
| 6 | 索引 | 见 `question_library_schema.json` 的 `indexes` 段 |
| 7 | 唯一约束 | 各表主键；`ai_question` 上加**部分唯一索引**保证同一 fingerprint 只有一条 ACTIVE |
| 8 | 生命周期字段 | `lifecycle_status`（物化）+ `stale` / `stale_reason` / `stale_since`；权威来源是 `question_event` |
| 9 | provenance 字段 | `run_id` → (model, prompt_version, context_hash, context_ref, raw_response_ref, started_at)；另加 `validator_version` |
| 10 | evidence 关系 | 独立的 1:N 表 `question_evidence`，每条含 `block_id` + `evidence_quote` |
| 11 | review 关系 | 并入 `question_event`（`REVIEW_APPROVED` / `REVIEW_REJECTED` + actor + reason_code + 时间） |
| 12 | reuse/cache 机制 | **两个键**：`generation_scope_key`（批次级，防重复调用）+ `question_fingerprint`（题级，去重与 REJECTED 抑制） |
| 13 | 与 learning.db 的关系 | 本轮零改动；未来加 3 个可空列（`source_kind` / `source_ref` / `source_version`）+ 一个索引；`item_id` 语义保持不变 |

---

## 13. 待确认 / 风险

| # | 事项 | 说明 |
| --- | --- | --- |
| 1 | 库文件位置与命名 | 建议 `structured/ai/question_library.db`；最终以正式目录规范为准 |
| 2 | 谁有权限审批 | P1 阶段为人工；审批人标识的取值规范待定 |
| 3 | `REJECTED` 抑制是否永久 | 建议默认永久 + 显式覆盖开关 |
| 4 | `EXACT` 陷阱规则（9.2） | 需要一次小样本验证，确认不会把正常题全部打成 `needs_human_review` |
| 5 | 跨库引用悬空 | contentpack 重建后 `block_id` / `item_id` 变化需巡检；建议 P1 增加只读巡检脚本 |
| 6 | 听力类活动 | 证据缺口未解前，该类活动应在前置检查阶段直接跳过 |

---

## 14. 本文件的自我约束

本设计**没有**创建任何数据库表，**没有**修改 `learning.db`、contentpack、
`structured/` 正式数据、validator v2、Web、Android、V1.3/V2.0 规范，
**没有**调用任何 AI，**没有**重新解析 PDF。
本文件与同目录其余三个文件是本轮唯一的写入产物。
