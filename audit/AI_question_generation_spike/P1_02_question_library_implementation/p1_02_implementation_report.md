# P1-02 · AI Question Library 最小数据库实现报告

最终状态：**IMPLEMENTATION_PASS**

执行日期：2026-09-17
SQLite 版本：3.49.1
依据：P0_closeout（P0_CLOSE）、P1-01 Question Library Design、validator v2

---

## 0. 结论速览

| 项 | 结果 |
| --- | --- |
| 创建数据库 | `structured/ai/question_library.db`（126,976 B） |
| 表数量 | **6 / 6**，全部按 P1-01 定义 |
| 索引 | 14 个（含 1 个 UNIQUE） |
| 触发器 | 6 个（4 类硬保证） |
| 最小测试 | **19 / 19 PASS**（覆盖 T1–T16） |
| 跨库 LearningObject 检查 | **PASS**（无悬空引用） |
| 数据库内真实 AI 题目 | **0 条** |
| AI 调用 | **0**（云端 0 / 本地 0） |
| `learning.db` | **零修改** |
| 保护项 | 全部 PASS（含 PDF 与 54 个 MP3 哈希复核） |

---

## 1. 只读核对（建库前的状态确认）

| 核对项 | 结果 |
| --- | --- |
| `learning_record.item_id` 是否仍为 LearningObject | **是**。实测 7 个不同 `item_id` 全部存在于 contentpack `learning_item`（`:V:` 词汇 / `:X:` 练习） |
| `learning.db` 是否未被修改 | **是**。118,784 B，mtime `2026-09-13 15:50:09`，SHA256 `0C27267B…CF91` |
| contentpack 是否没有 AI Question Library | **是**。`ai_artifact` = 0 行；无任何题库表 |
| `structured/` 是否尚未存在 question library | **是**。建库前该目录下只有 `learning/learning.db` 一个数据库 |
| validator v2 是否未被修改 | **是**。SHA256 `7C61585A…A683`，mtime `2026-09-17 14:31:02` |
| P1-01 设计是否与实际结构冲突 | **无冲突**，可以直接实现 |

---

## 2. 实际创建了什么

新建独立 SQLite 数据库（**不附加、不修改任何既有数据库**）：

```text
D:\ZhixueEnglish\structured\ai\question_library.db
size = 126,976 B
SHA256 = 5FECB38F20303723F4231EBB3406C97ED5F5DD2DE35C17253525D16968CEA9D8
PRAGMA user_version = 1
PRAGMA integrity_check = ok
PRAGMA foreign_key_check = 空（无违规）
```

创建脚本：`create_question_library.py`（配套 DDL 模块 `ql_schema.py`）。
脚本设计为**拒绝覆盖已存在的数据库**，避免误删既有数据。

---

## 3. 六张表结构

### 3.1 `generation_run` — 一次 AI 调用的账目

主键：`run_id`

核心字段：`generation_scope_key` / `textbook_id` / `snapshot_id` / `unit_id` / `section_id` /
`activity_id` / `model` / `prompt_version` / `context_hash` / `provider` / `context_ref` /
`raw_response_ref` / `requested_max` / `max_tokens` / `finish_reason` / `usage_json` /
`elapsed_ms` / `question_count` / `status` / `insufficient_evidence` / `error` / `note` / `generated_at`

关键约束：

- `status ∈ {OK, TRUNCATED, API_ERROR, INSUFFICIENT_EVIDENCE}`
- `question_count >= 0`（**允许 0 题**，对应 P0 的截断与证据不足两种真实情形）
- `CHECK (insufficient_evidence = 0 OR status = 'INSUFFICIENT_EVIDENCE')`
- `usage_json` 必须是合法 JSON（`json_valid`）

### 3.2 `ai_question` — 题目实体

主键：`(question_id, version)`（**版本只增不改的物理保证**）

内容：`question_type` / `question_text` / `options_json` / `correct_option` / `correct_answer` /
`explanation` / `difficulty`

教材定位：`textbook_id` / `snapshot_id` / `unit_id` / `section_id` / `activity_id` / `page`

来源：`generation_run_id`（FK）/ `generated_at` / `question_fingerprint`

生命周期：`lifecycle_status` / `active` / `disabled_reason` / `stale` / `stale_reason` / `stale_since`

技术追踪：`validator_version` / `needs_human_review`

关键约束：

- `lifecycle_status ∈ {GENERATED, VALIDATED, PENDING_REVIEW, APPROVED, ACTIVE, REJECTED, DISABLED}`
- `CHECK ((lifecycle_status='ACTIVE' AND active=1) OR (lifecycle_status<>'ACTIVE' AND active=0))`
- `CHECK (stale = 1 OR stale_reason IS NULL)` 且 `CHECK (stale = 0 OR stale_reason IS NOT NULL)`
  —— 即 `stale_reason` 与 `stale=1` 严格互为充要
- `question_fingerprint` 长度必须为 64（SHA256）

**AI 原始 reasoning 未作为任何字段保存**；只保留 `generation_run.raw_response_ref` 指向原始响应文件。

### 3.3 `question_evidence` — 题目 ↔ 教材证据（1:N）

主键：`(question_id, version, ordinal)`

字段：`evidence_block_id` / `evidence_quote` / `is_primary`

约束：`ordinal >= 1`；`evidence_quote` 非空；FK → `ai_question(question_id, version)`。

这回答了 P1-01 的核心问题：**一道题可以依赖多个 evidence block**（P0 的 6 道题恰好都是单块，
但结构上不被样本偶然性锁死）。

### 3.4 `question_learning_object` — 题目 ↔ LearningObject（1:N）

主键：`(question_id, version, item_id)`

字段：`item_id` / `is_primary`

**关键约束（防止语义污染）**：

```sql
CHECK (item_id NOT LIKE 'AIQ:%' AND item_id NOT LIKE 'AIRUN:%')
```

即：**不可能把 question_id 或 run_id 塞进 LearningObject 位置**。
`item_id` 只能指向 contentpack `learning_item`。

### 3.5 `question_validation` — validator 结果

主键：`(question_id, version, validator_version)`

字段：`validation_result` / `validated_at` / `answer_support_type` / `checks_json` /
`out_of_scope_tokens_json` / `needs_human_review` / `note`

约束：

- `answer_support_type ∈ {EXACT, VERIFIABLE_REFERENCE, VERIFIABLE_REPHRASE, UNSUPPORTED}`
- `CHECK (validation_result <> 'PASS' OR answer_support_type IN
  ('EXACT','VERIFIABLE_REFERENCE','VERIFIABLE_REPHRASE'))` —— **UNSUPPORTED 不可能 PASS**
- 主键含 `validator_version`，validator 升级后可重复验证，历史结论并存

### 3.6 `question_event` — append-only 生命周期 / 审核事件

主键：`event_id`

字段：`question_id` / `version` / `event_type` / `from_status` / `to_status` / `event_at` /
`actor` / `actor_kind` / `reason_code` / `note`

约束：

- `event_type ∈ {VALIDATED, REVIEW_APPROVED, REVIEW_REJECTED, ACTIVATED, DISABLED, MARKED_STALE}`
- `CHECK (event_type <> 'REVIEW_APPROVED' OR actor_kind = 'human')` —— **审批必须是人工**
- `CHECK (event_type <> 'REVIEW_REJECTED' OR actor_kind = 'human')`
- `CHECK (event_type <> 'REVIEW_REJECTED' OR reason_code IS NOT NULL)` —— 驳回必须给结构化原因

---

## 4. 主键 / 外键 / UNIQUE / INDEX 汇总

### 主键

| 表 | 主键 |
| --- | --- |
| `generation_run` | `(run_id)` |
| `ai_question` | `(question_id, version)` |
| `question_evidence` | `(question_id, version, ordinal)` |
| `question_learning_object` | `(question_id, version, item_id)` |
| `question_validation` | `(question_id, version, validator_version)` |
| `question_event` | `(event_id)` |

### 外键

| 表 | 外键 | 动作 |
| --- | --- | --- |
| `ai_question` | `generation_run_id → generation_run(run_id)` | RESTRICT / CASCADE(update) |
| `question_evidence` | `(question_id, version) → ai_question` | CASCADE |
| `question_learning_object` | `(question_id, version) → ai_question` | CASCADE |
| `question_validation` | `(question_id, version) → ai_question` | CASCADE |
| `question_event` | `(question_id, version) → ai_question` | **RESTRICT** |

### UNIQUE

- 各表主键自带唯一约束；
- **`uq_ai_question_fingerprint`：`question_fingerprint` 全局唯一**
  —— 这是 T9（同指纹不可重复）与 T13（REJECTED 结构性抑制）的实现基础。

### 索引（14 个，全部实际创建）

```text
idx_generation_run_scope      (generation_scope_key)          → 复用键查询
idx_generation_run_target     (section_id, activity_id)
idx_generation_run_time       (generated_at)
uq_ai_question_fingerprint    (question_fingerprint) UNIQUE   → 去重 / REJECTED 抑制
idx_ai_question_scope         (section_id, activity_id, lifecycle_status, stale) → 取 ACTIVE 题
idx_ai_question_lifecycle     (lifecycle_status)               → PENDING_REVIEW / ACTIVE
idx_ai_question_stale         (stale, stale_reason)            → 找需重验的题
idx_ai_question_run           (generation_run_id)              → 同源题目
idx_question_evidence_block   (evidence_block_id)              → 反查某 block 被哪些题引用
idx_qlo_item                  (item_id)                        → 按 LearningObject 查题
idx_validation_result         (validation_result)
idx_validation_support        (answer_support_type)
idx_question_event_q          (question_id, version, event_at)
idx_question_event_type       (event_type, event_at)
```

---

## 5. 生命周期约束（validator PASS ≠ ACTIVE）

### 生命周期枚举

```text
GENERATED → VALIDATED → PENDING_REVIEW → APPROVED → ACTIVE
任意状态 → REJECTED | DISABLED
```

### STALE 的正交表达

`STALE` **不是** `lifecycle_status` 的取值；它是 `stale` + `stale_reason` 字段。
数据库层面明确允许 **ACTIVE + stale=1** 的组合（T11 已实测通过）。

### 两条硬门槛触发器

```sql
-- 1) 新插入的题不允许直接是 ACTIVE
CREATE TRIGGER trg_ai_question_insert_active_forbidden
BEFORE INSERT ON ai_question
WHEN NEW.lifecycle_status = 'ACTIVE'
BEGIN SELECT RAISE(ABORT, 'validator PASS is not enough: a question cannot be inserted as ACTIVE'); END;

-- 2) 只有存在“人工 REVIEW_APPROVED 事件”才允许转为 ACTIVE
CREATE TRIGGER trg_ai_question_active_requires_human_approval
BEFORE UPDATE OF lifecycle_status ON ai_question
WHEN NEW.lifecycle_status = 'ACTIVE'
 AND NOT EXISTS (SELECT 1 FROM question_event e
                  WHERE e.question_id = NEW.question_id AND e.version = NEW.version
                    AND e.event_type = 'REVIEW_APPROVED' AND e.actor_kind = 'human')
BEGIN SELECT RAISE(ABORT, 'ACTIVE requires a human REVIEW_APPROVED event'); END;
```

即：**即使 validator 判 PASS，也无法把题目变成 ACTIVE**。必须走
`PENDING_REVIEW → APPROVED（人工事件）→ ACTIVE`。T11b 已实测拦截成功。

### 其他三条保护触发器

```text
trg_question_event_no_update   事件不可 UPDATE
trg_question_event_no_delete   事件不可 DELETE
trg_ai_question_no_delete      题目不可 DELETE（下线只能用 DISABLED）
```

---

## 6. EXACT 风险处理（P0 已确认的陷阱）

P0 结论：当选项文本本身出现在教材证据里时，`answer_support = EXACT` **不等于**答案被证明。

本实现把这条风险变成了数据库行为，而不是靠人记住：

```sql
CREATE TRIGGER trg_validation_exact_trap
AFTER INSERT ON question_validation
WHEN NEW.answer_support_type = 'EXACT'
 AND EXISTS (SELECT 1 FROM ai_question q
              WHERE q.question_id = NEW.question_id AND q.version = NEW.version
                AND ( instr(lower(q.question_text), lower(q.correct_answer)) > 0
                      OR (q.options_json IS NOT NULL
                          AND instr(lower(q.options_json), lower(q.correct_answer)) > 0) ) )
BEGIN
  UPDATE question_validation SET needs_human_review = 1 WHERE ...;
  UPDATE ai_question         SET needs_human_review = 1, updated_at = NEW.validated_at WHERE ...;
END;
```

效果：

- 一旦 `EXACT` 且答案文本同时出现在题干/选项中 → **自动强制 `needs_human_review = 1`**（T14 实测通过）；
- 答案只出现在 evidence_quote、不出现在题干/选项中 → **不会误伤**（T14b 实测通过）；
- 结合 §5 的 ACTIVE 硬门槛，这类题**必须经过人工审核**才能上线。

---

## 7. 复用键（按 P1-01 修正方案实现）

```text
generation_scope_key = SHA256(section_id, activity_id, prompt_version, context_hash)
question_fingerprint = SHA256(section_id, activity_id, question_type,
                              norm(question_text), norm(evidence_quote))
```

实现位置：`ql_schema.py` 的 `generation_scope_key()` 与 `question_fingerprint()`；
归一化规则为「统一弯引号 → 折叠空白 → 转小写」。

**同一教材位置可以存在多道不同题目**——T8 实测：同一 `section_id + activity_id` 下写入
两道不同 fingerprint 的题，成功。

### 一处需要明确记录的设计取舍

P1-01 §8.4 曾建议把 fingerprint 做成**部分唯一索引**（仅对 ACTIVE 生效），
以便教材改版后可以“合法重生”。P1-02 的任务要求 **T9「完全相同 fingerprint 不能重复」**
并与 **T13「REJECTED 题目的 fingerprint 可以用于后续抑制」** 相呼应，
因此本次实现改为 **`question_fingerprint` 全局唯一**。

带来的直接后果（必须知情）：

1. 被驳回（REJECTED）的题目**在结构上无法被重新生成**——这正是 T13 期望的抑制效果；
2. 版本升级的前提是**内容发生变化**（`question_text` / `evidence_quote` 变化 → 指纹不同）才能写入
   `version=2`；
3. 若未来确实需要“同内容合法重生”，需要一次性放开该唯一索引（单行 DDL 变更），
   本次不预留开关，以免把复杂度提前引入。

---

## 8. 最小测试结果（T1–T16）

测试文件：`test_question_library.py`（19 个测试方法，覆盖 T1–T16）。
**测试全部跑在临时数据库上，正式库始终为空。**

| 编号 | 验证内容 | 对应测试 | 结果 |
| --- | --- | --- | --- |
| T1 | 数据库可正常创建并打开 | `test_T1_database_can_be_opened` | PASS |
| T2 | 6 张表全部存在 | `test_T2_six_tables_exist` | PASS |
| T3 | 主键 / UNIQUE / CHECK / FK 正常 | `test_T3_primary_key_and_checks`、`test_T3b_learning_object_cannot_be_a_question_id` | PASS |
| T4 | 一次 run 可对应 0 道题 | `test_T4_run_with_zero_questions` | PASS |
| T5 | 一次 run 可对应多道题 | `test_T5_run_with_multiple_questions` | PASS |
| T6 | 一道题可对应多个 evidence | `test_T6_question_with_multiple_evidence` | PASS |
| T7 | 一道题可对应多个 LearningObject | `test_T7_question_with_multiple_learning_objects` | PASS |
| T8 | 同一教材位置可存在不同 fingerprint 的多道题 | `test_T8_same_position_allows_multiple_distinct_questions` | PASS |
| T9 | 完全相同 fingerprint 不能重复 | `test_T9_identical_fingerprint_rejected` | PASS |
| T10 | version 可以并存、互不覆盖 | `test_T10_versions_coexist_without_overwrite` | PASS |
| T11 | STALE 可与 ACTIVE 同时存在 | `test_T11_active_can_be_stale`、`test_T11b_validator_pass_never_becomes_active_automatically` | PASS |
| T12 | question_event 连续记录生命周期变化 | `test_T12_event_stream_records_transitions_and_is_immutable` | PASS |
| T13 | REJECTED 的 fingerprint 可用于抑制 | `test_T13_rejected_fingerprint_suppresses_regeneration` | PASS |
| T14 | EXACT + 选项命中 → `needs_human_review=1` | `test_T14_exact_trap_forces_human_review`、`test_T14b_exact_without_option_hit_is_not_forced` | PASS |
| T15 | 数据库中不存在任何真实 AI 题目 | `test_T15_official_db_has_no_real_questions` | PASS |
| T16 | `learning.db` SHA256 与执行前完全一致 | `test_T16_learning_db_unchanged` | PASS |

```text
Ran 19 tests in 5.438s
OK
```

---

## 9. 跨库 LearningObject 检查（只读，不自动修复）

脚本：`check_cross_db_refs.py`

```text
question_learning_object.item_id       refs=0 ok=0 dangling=0
question_evidence.evidence_block_id    refs=0 ok=0 dangling=0

跨库检查结果：PASS（无悬空引用）
```

说明：正式库当前为空，因此引用数天然为 0；检查逻辑本身已就绪
（以 contentpack `learning_item.item_id` 与 `content_block.block_id` 为基准集合，
发现悬空即报 **ERROR** 并以退出码 1 结束）。**本阶段不做任何自动修复与自动同步。**

---

## 10. 【必须写入】与 LearningRecord 的边界

本阶段**未执行** P1-01 提出的 `learning_record` 三字段迁移，也**未修改 `learning.db`**。

原因：当前阶段只是建立 AI Question Library 数据资产。
在 `learning_record` 尚未具备下列字段之前：

```text
source_kind
source_ref
source_version
```

> **AI 题目不得进入孩子正式学习流程。**

该限制在本阶段始终有效；题库只能承载生成、校验、审核、入库与版本管理。

---

## 11. 前台显示边界（必须遵守）

AI Question Library 是**后台学习资源库**。题库保存完整技术溯源信息，
但未来孩子看到的学习页面：

> **不得显示任何技术元数据。**

禁止出现在孩子页面：`model`、`prompt_version`、`context_hash`、`generation_run_id`、
`validator_version`、`evidence_block_id`、`lifecycle_status`、`review_status`、
`stale_reason`、`question_fingerprint`，以及任何数据库内部 ID。

如需告诉孩子教材来源，只使用自然的学习语言，例如：

> 教材第 17 页

---

## 12. 保护项复验

| 保护项 | 结果 |
| --- | --- |
| `learning.db` | **未修改**：118,784 B，mtime `2026-09-13 15:50:09`，SHA256 `0C27267B…CF91`（与本轮开始前一致） |
| contentpack v5 | **未修改**：2,715,648 B，`ai_artifact` = 0 行 |
| 教材 PDF | **未修改**：SHA256 `C732051E91121BC991DBDD01235662629620DF6BFCCBBBD834EAEA6FCECD4F2F`，与 `textbook_structure_v2.json` 记录值一致 |
| 54 个官方 MP3 | **未修改**：逐个与 `audio_asset.sha256` 比对，**54 / 54 全部 MATCH** |
| validator v2 | **未修改**：SHA256 `7C61585A…A683`，mtime `2026-09-17 14:31:02` |
| Web / Android / V1.3 / V2.0 | **未修改** |
| AI API 调用 | **0**（未调用 DeepSeek，也未调用任何本地或云端模型） |
| 重新解析 PDF | **否** |
| 正式库中的真实题目 | **0 条**（6 张表全部空表） |

---

## 13. 是否修改正式学习数据

**否。**

- `learning.db` 哈希与 mtime 均未变化；
- 未向任何学习表写入数据；
- 未把任何 AI 题目接入学习流程；
- 新建的 `question_library.db` 是**独立数据库文件**，与 `learning.db` 无物理关联。

---

## 14. 本轮产物

| 文件 | 说明 |
| --- | --- |
| `structured/ai/question_library.db` | **本次唯一创建的正式数据库**（6 表结构，0 数据） |
| `create_question_library.py` | 建库脚本（拒绝覆盖既有库；支持 `--dry-run`） |
| `ql_schema.py` | DDL 模块 + 两个复用键计算函数 |
| `test_question_library.py` | 19 个最小测试（T1–T16） |
| `check_cross_db_refs.py` | 跨库引用只读检查 |
| `dump_schema_audit.py` | schema 审计导出工具 |
| `p1_02_schema_audit.json` | schema 审计结果（结构化） |
| `p1_02_implementation_report.md` | 本报告 |
| `README.md` | 索引 |

附带说明：运行上述脚本时 Python 在本目录生成了派生字节码缓存
`__pycache__/ql_schema.cpython-312.pyc`（仅为本目录 `ql_schema.py` 的编译结果，可随时重新生成，
不含业务数据）。清理该缓存的操作被本机命令策略拦截，故保留并在此披露。

---

## 15. 明确未做的事

- 未创建任何额外表（无 prompt / model / reviewer / user / analytics / statistics /
  recommendation / learning plan / AI conversation / embedding 等表）
- 未建立独立缓存系统
- 未生成任何真实 AI 题目
- 未调用任何 AI
- 未修改 `learning.db`、contentpack、教材 PDF、MP3、Web、Android、V1.3、V2.0
- 未做跨库自动同步
- 未执行 `learning_record` 三字段迁移
