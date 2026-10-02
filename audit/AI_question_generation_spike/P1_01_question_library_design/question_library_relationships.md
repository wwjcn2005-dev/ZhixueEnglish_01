# AI Question Library V1 · 关系图与数据流

配套文件：`question_library_v1_design.md`（设计说明）、`question_library_schema.json`（schema 草案）
状态：**只设计，未实现**

---

## 1. 主链：从一次 AI 调用到教材证据

```text
┌──────────────────────────────┐
│      generation_run          │   一次云端调用 = 一行
│  PK run_id                   │   P0 实测：1 次调用 → 0 或 3 道题
│  model / prompt_version      │
│  context_hash / context_ref  │   ← 当时 AI 看到的教材证据快照
│  raw_response_ref            │   ← reasoning 只留在这里，不入库为字段
│  run_status / returned_count │   ← 0 题（截断/证据不足）同样必须落库
└───────────────┬──────────────┘
                │ 1 : N（run_id）
                ▼
┌──────────────────────────────┐
│        ai_question           │   一道题的一个版本 = 一行
│  PK (question_id, version)   │   ← 版本只增不改，旧行永不覆盖
│  question_type / question_text│
│  options_json / correct_answer│
│  unit_id / section_id        │
│  activity_id / page          │
│  lifecycle_status / stale    │
│  question_fingerprint        │
└───┬───────────┬───────────┬──┘
    │           │           │
    │ 1:N       │ 1:N       │ 1:N
    ▼           ▼           ▼
┌──────────────┐ ┌──────────────────┐ ┌───────────────────┐
│question_     │ │question_learning_│ │question_validation│
│evidence      │ │object            │ │PK(question_id,    │
│PK(question,  │ │PK(question,      │ │   version,        │
│  version,    │ │  version,item_id)│ │   validator_ver)  │
│  ordinal)    │ │                  │ │checks_json        │
│block_id      │ │item_id           │ │answer_support_type│
│evidence_quote│ │is_primary        │ │needs_human_review │
└──────┬───────┘ └────────┬─────────┘ └───────────────────┘
       │ 外部引用           │ 外部引用
       ▼                   ▼
┌──────────────────┐ ┌──────────────────────┐
│ contentpack v5   │ │ contentpack v5       │
│ content_block    │ │ learning_item        │
│ (block_id) 只读   │ │ (item_id) 只读        │
└──────────────────┘ └──────────┬───────────┘
                                │ 同一 ID 空间（不写回）
                                ▼
                    ┌──────────────────────────┐
                    │ contentpack learning_item│
                    │ = LearningObject         │
                    └───────────┬──────────────┘
                                │ 现有正式机制
                                ▼
                    ┌──────────────────────────┐
                    │ learning.db              │
                    │ mastery_state(item_id)   │
                    └──────────────────────────┘
```

**要点**

- 跨库引用（`block_id` / `item_id`）**不是**外键，SQLite 无法强制；靠
  `content_snapshot_id` + 巡检任务防止悬空。
- `question_learning_object` 是 AI 题库与现有学习体系的**唯一接缝**；
  它只声明「测哪个 LearningObject」，不改变 `mastery_state` 的聚合键。

---

## 2. 生命周期事件链（权威来源）

```text
question_event (append-only)

  ① VALIDATED          actor_kind=machine, actor=validator_v2
        │                  （附 question_validation 行）
        ▼
  lifecycle_status = VALIDATED / PENDING_REVIEW
        │
  ② REVIEW_APPROVED    actor_kind=human, actor=<复核人>
        │  或  REVIEW_REJECTED + reason_code
        ▼
  lifecycle_status = APPROVED         或  REJECTED（终态，fingerprint 永久抑制）
        │
  ③ ACTIVATED          actor_kind=human
        ▼
  lifecycle_status = ACTIVE   ← 唯一允许进入学习系统的状态
        │
  ④ DISABLED           actor_kind=human，附 reason_note
        ▼
  lifecycle_status = DISABLED

任意状态 ─ ⑤ MARKED_STALE（stale=1 + stale_reason）
             状态不变，仅表示“不再作为复用来源”
```

**读表规则**：`question_event` 是事实源；`ai_question.lifecycle_status` 是为查询准备的物化字段。
二者不一致时以事件流为准，并可用事件流重建。

---

## 3. reuse / cache 查询路径（决定“要不要调用 AI”）

```text
进入某个 Section / Activity 的学习场景
        │
        ▼
① 查 ai_question
   WHERE section_id=? AND activity_id=? AND question_type=?
     AND lifecycle_status='ACTIVE' AND stale=0
        │
        ├── 命中 → 直接复用（AI 调用 = 0）  ✔ P0 硬性要求
        │
        └── 未命中
                │
                ▼
② 查 ai_question
   WHERE question_fingerprint IN (候选指纹) AND lifecycle_status='REJECTED'
        │
        ├── 命中 → 直接丢弃该题，不再生成、不再送审
        │
        └── 未命中
                │
                ▼
③ 查 generation_run
   WHERE generation_scope_key = hash(section_id, activity_id, prompt_version, context_hash)
        │
        ├── 已有 OK 运行 → 说明生成过；若题目都在审核中则等待，不重复调用
        │
        ├── 已有 INSUFFICIENT_EVIDENCE 运行 → 回退到教材原题，不再调用
        │
        └── 无记录 → 允许进入生成批次（仍受批次/预算/证据充分性约束）
```

**冻结条款：禁止页面打开即调用 AI。**

---

## 4. 版本与 STALE 的关系

```text
question_id = AIQ:9F3C1A2B7D04

version=1  prompt_version=P1  context_hash=ABC  ── 标记 stale=1 (PROMPT_CHANGED)
                                                      │  历史保留，不再复用
version=2  prompt_version=P2  context_hash=ABC  ── 当前版本
                                                      │
version=3  prompt_version=P2  context_hash=XYZ  ── 教材重建后（EVIDENCE_CHANGED）
                                                      │
       若 validator 规则升级 → 对存量版本重跑 question_validation（新增 validator_version 行）
                                不删除任何旧结论
```

规则：

1. 内容变化 = 新增 `version`；旧行**永不 UPDATE 内容字段**。
2. `(question_id, version)` 是主键，物理上杜绝覆盖。
3. `stale` 与 `lifecycle_status` 正交：ACTIVE 且 stale=1 的题**不可用但可见**。

---

## 5. 与 `learning.db` 的关系（未来）

### 5.1 现状：无法回答“做的是哪道题的哪个版本”

```text
当前（不加字段）

  learner ──► learning_task ──► learning_record ──► item_id ──► LearningObject
                                                    │
                                                    └─ ✗ 无法知道来自 contentpack 题目还是 AI 题目
                                                       ✗ 无法知道题目版本
```

### 5.2 推荐的最小迁移（设计，不执行）

```text
建议（未来迁移后）

  learning_record
    item_id         → LearningObject（语义不变，mastery_state 不受影响）
    source_kind     → 'contentpack' | 'ai_library'
    source_ref      → 'AIQ:9F3C1A2B7D04'
    source_version  → 2

             │ source_kind='ai_library'
             ▼
     AI Question Library 的 ai_question(question_id, version)
```

**回答“`question_id` + `question_version` 是否足够”**：

> 不够。还必须有一个字段说明**来自哪个题库**（`source_kind`），
> 否则 contentpack 题目与 AI 题目会在同一条记录里失去区分，未来也无法按来源统计。

### 5.3 阻断规则

```text
该迁移完成之前：
    AI 题目  ✗ 不得进入孩子可见的学习流程
    AI 题目  ✔ 可以生成、校验、审核、入库（停在 PENDING_REVIEW / APPROVED）
```

---

## 6. provenance 可解释链（“为什么当时被批准”）

```text
┌ question_event: REVIEW_APPROVED (actor, reason_code, created_at)
│
├ question_validation: validator_version, checks_json(8项),
│                      answer_support_type, needs_human_review, validated_at
│
├ generation_run: model, prompt_version, context_hash, context_ref,
│                 raw_response_ref, max_tokens, usage_json, started_at
│
└ question_evidence: block_id, evidence_quote   ← 教材哪一块、哪一句
                    ↓
        完整回答：谁批的、按什么规则批的、当时 AI 看到什么、引用教材哪一句
```

**EXACT 陷阱的处置位置**（P0 已确认的风险）：

```text
answer_support_type == 'EXACT'
        +
answer 文本同时出现在 question_text / options 自身中
        ↓
needs_human_review = 1   ← 题库侧字段，不需要改 validator v2
        ↓
不走快通道，必须人工确认“答案是被教材正文证明的，而不是因为选项印在教材上”
```

---

## 7. 与正式数据的边界（不变式）

```text
contentpack v5   ── 只读，ai_artifact 保持 0 行
learning.db      ── 本轮零改动
question_library.db（未来）── 可写、可审核、可版本化、可复用

三条不变式：
  1. 教材数据不被 AI 题目污染
  2. 未经人工审核的 AI 题目不被孩子看到
  3. 任何 ACTIVE 题目都能回溯到教材证据与生成来源
```

---

## 8. 本文件自我约束

本文件只是关系说明，**没有创建任何表、任何数据库文件**，
**没有修改** `learning.db`、contentpack、`structured/` 正式数据、validator v2、Web、Android、V1.3/V2.0，
**没有调用任何 AI**、**没有重新解析 PDF**。
