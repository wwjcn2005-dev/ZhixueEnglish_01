# P1-04 · AI Question Library 规则修正报告

最终状态：**FIX_PASS**

执行日期：2026-09-17
AI 调用：**0**（本轮不生成任何新题）

---

## 0. 结论速览

| 项 | 结果 |
| --- | --- |
| 问题 A（EXACT 误报） | **已修正**（题库触发器 + Python 语义同步） |
| 问题 B（fill 带选项） | **已约束**（validator v3，v2 原样保留） |
| 问题 C（事件枚举） | **已升级**（schema v1 → v2，逐行数据不变） |
| P1-02 回归 | **18 PASS / 1 FAIL**（唯一失败项 T15 的断言已被 P1-03 合法入库取代，见 §5） |
| P1-04 新测试 | **28 / 28 PASS** |
| 两道已有真实题 | **业务内容零变化**（未重新生成、未删除、未篡改） |
| learning.db | **零修改** |
| AI 调用 | **0** |

---

## 1. 只读审计：三个问题确认存在

| 问题 | 实测证据 | 结论 |
| --- | --- | --- |
| A | 两道入库题的 `needs_human_review` 均为 1；其中 `AIQ:7EBCDBC29563` 是 **fill**，其答案已从题干挖空，仅因模型自带 options 就被标记 | **确实存在** |
| B | `AIQ:7EBCDBC29563`（fill）携带 `options_json = ["sentence","mistake","polite","meaning"]` 与 `correct_option='A'` | **确实存在** |
| C | `user_version = 1`，`question_event.event_type` 枚举只有 `VALIDATED / REVIEW_APPROVED / REVIEW_REJECTED / ACTIVATED / DISABLED / MARKED_STALE`；P1-03 只能用一条 `VALIDATED` 事件表达 `GENERATED → PENDING_REVIEW` | **确实存在** |

实际情况与 P1-03 报告一致 → 继续修正，未触发 `FIX_BLOCKED`。

---

## 2. 问题 A：EXACT 特殊复核规则如何修改

### 修改前（误报来源）

```sql
answer_support_type = 'EXACT'
AND ( 答案文本出现在 question_text  OR  答案文本出现在 options_json )
→ needs_human_review = 1
```

由于**选择题的正确答案本来就在 options 里**，这条规则对选择题几乎必然触发。

### 修改后

```sql
answer_support_type = 'EXACT'
AND 题目为可选型（options_json IS NOT NULL）
AND 正确答案文本本身出现在教材 evidence_quote 中
→ needs_human_review = 1
```

三个条件必须**同时**成立。语义要点：

- **`options` 本身不再是触发依据**。答案恰好是选项之一，不再导致标记（修正了 P1-03 的误报）。
- **纯填空题不触发**：孩子必须自己写出答案，不存在“照抄可见选项”的风险。
- **只看正确答案**：错误选项出现在教材引文中不会触发（T4）。
- **教材原文已经直接给出答案**时仍然触发并强制人工复核——这正是 P0 记下的真实风险。

实现位置：

- **权威执行**：`question_library.db` 触发器 `trg_validation_exact_trap`（已替换，见 §6）
- **Python 等价语义**：`validator_v3.exact_print_risk()`
- 两者由 `test_T4b_python_rule_matches_sql_semantics` 与 T1–T4 的数据库行为测试共同锁定

> **重要：Validator 的 `answer_support` 规则未被放宽。** `EXACT / VERIFIABLE_REFERENCE /
> VERIFIABLE_REPHRASE` 的判定逻辑与 v2 完全一致（v3 直接复用 v2 的函数对象）。

---

## 3. 问题 B：fill 结构如何约束

### 正式定义

> `fill` = **纯填空题**。题干必须有 `___`，**不得**携带 `options`，**不得**携带 `correct_option`。

### 判定结果

| 情形 | 结果 |
| --- | --- |
| `fill` + `___` + 无 options + 无 correct_option | **PASS**（T5） |
| `fill` + `options` | **FAIL**（T6） |
| `fill` + `correct_option` | **FAIL**（T7） |
| `fill` + 两者 | **FAIL**（T8） |
| `fill` + 无空位 | **FAIL**（T10b，v2 原有规则保留） |
| `vocab_choice` + 4 个 options + correct_option | PASS（T9，未受影响） |
| `reading_choice` + options + correct_option | PASS（T10，未受影响） |

### 实现位置：**不修改 v2，新增 v3**

```text
audit/AI_question_generation_spike/P1_04_rule_fixes/validator_v3.py
    ├ 以只读方式 import validator_v2（原文件一行未改）
    ├ 原样转出 v2 全部能力：tokens / answer_support / build_whitelist /
    │                     checked_language / out_of_scope / FUNC / PRONOUNS
    ├ 新增 type_rules()      ← 收紧后的题型结构规则
    └ 新增 validate_question() / validate_batch()  ← 8 项校验（第 8 项用新规则）
```

`validator_v2.py` 保持原样（SHA256 `7C61585A…A683` 未变），P1-02/P1-03 的历史结论不受影响。
本轮**没有**增加新的 `question_type`（带词库的填空留待将来单独立型）。

---

## 4. 问题 C：event schema 是否升级

### 结论：**已升级**（v1 → v2），不是 DEFERRED

升级是安全的，因为 `question_event` 不承载业务内容，且可以对全部行做逐行哈希比对：

| 检查 | 结果 |
| --- | --- |
| `user_version` | 1 → **2** |
| 6 张表行数 | 迁移前后完全一致 |
| 6 张表逐行哈希 | **全部一致**（含 `question_event` 的 2 行） |
| `integrity_check` | ok |
| `foreign_key_check` | 空（无违规） |
| 枚举可用性（事务内试插并回滚） | `GENERATED` ✔ 可写、`PENDING_REVIEW` ✔ 可写 |
| 非法枚举仍被拒绝 | ✔（T14b） |
| 事件仍 append-only | ✔（T14） |
| `REVIEW_APPROVED` 仍必须 `actor_kind='human'` | ✔（T14c） |

新枚举（v2）：

```text
GENERATED · VALIDATED · PENDING_REVIEW · REVIEW_APPROVED
REVIEW_REJECTED · ACTIVATED · DISABLED · MARKED_STALE
```

### 迁移的具体做法（最小改动）

```text
1. 摘除挂在旧表上的触发器与索引
   （含 ai_question 上的 lifecycle 触发器——它引用了 question_event，必须先摘后恢复）
2. 建 question_event__v2_tmp（仅扩枚举）→ 逐行复制 → 删旧表 → 改名
3. 原样恢复索引 idx_question_event_q / idx_question_event_type
4. 原样恢复 append-only 触发器与 ACTIVE 硬门槛触发器
5. 替换 EXACT 触发器（问题 A）
6. PRAGMA user_version = 2
```

其余 5 张表、全部索引、其余触发器**完全沿用 v1 定义**（v2 通过 import v1 复用，不复制、不重写）。

迁移前先在内存库做了完整 dry-run（`dryrun_migration.py`），确认无误后才对正式库执行。

---

## 5. 回归结果

### 5.1 P1-04 新测试：**28 / 28 PASS**

```text
Ran 28 tests in 0.025s
OK
```

| 组 | 覆盖 |
| --- | --- |
| `ExactRuleTests` | T1 纯填空不触发、T2 仅 options 不触发、T3 答案在教材引文触发、T4 错误选项不触发、T4b Python/SQL 语义一致 |
| `FillRuleTests` | T5 正常 fill PASS、T6 options FAIL、T7 correct_option FAIL、T8 两者 FAIL、T9/T10 选择题不受影响、T10b 无空位 FAIL、T10c 未放宽其他题型 |
| `EventSchemaTests` | T11 `GENERATED`、T12 `VALIDATED`、T13 `PENDING_REVIEW`、T14 append-only、T14b 非法枚举拒绝、T14c 审批必须人工 |
| `HardGateTests` | §九 全部硬门槛在 v2 schema 上复验 |
| `FrozenV1SchemaTests` | v1 schema 定义保持冻结；v1/v2 建库脚本均不插入任何数据 |
| `LiveDataTests` | T15 正式库仍可读、P1-03 两道题完好 |

### 5.2 P1-02 回归：**18 PASS / 1 FAIL**（必须如实说明）

```text
Ran 19 tests
FAILED (failures=1)
唯一失败：test_T15_official_db_has_no_real_questions
         AssertionError: 2 != 0
```

**这不是本轮修正造成的回归。** P1-02 的 T15 断言“正式题库为空”，而该断言在 **P1-03 被合法打破**——
P1-03 的任务明确要求把真实 AI 题写入 `question_library.db`。本轮又明确禁止删除这两道题，
因此 T15 在结构上**不可能再通过**。

处理方式（未修改 P1-02 的任何文件）：

- T15 的**原始意图**是「建库脚本本身不得插入数据」。该意图由 P1-04 新增的
  `FrozenV1SchemaTests` 用同一 v1 schema 定义在内存库上复核，**PASS**；
- 同时新增 `test_v2_schema_definition_inserts_no_data`，确认 v2 建库同样只建结构。

其余 18 项（建库、6 表、主键/UNIQUE/CHECK/FK、0..N 基数、fingerprint 去重、
版本并存、STALE+ACTIVE、事件不可篡改、REJECTED 抑制、learning.db 哈希等）**全部 PASS**，
说明本轮修正**没有削弱任何既有硬门槛**。

---

## 6. 两道已有真实题是否完全保持不变

### 业务内容：**完全不变**

| 字段 | 是否变化 |
| --- | --- |
| `question_id` / `version` | 未变 |
| `question_text` / `options_json` / `correct_option` / `correct_answer` / `explanation` | **未变** |
| `question_fingerprint` | 未变 |
| `question_evidence`（block + quote） | 未变 |
| `question_learning_object`（3 条引用） | 未变 |
| `lifecycle_status` | 未变（仍为 `PENDING_REVIEW`） |
| `generation_run`（1 条） | 未变 |
| `question_validation`（2 行 PASS） | 未变 |

脚本 `mark_validator_changed_stale.py` 迁移前后对业务字段做了逐题比对，输出：

```text
标记为 stale 的题：['AIQ:7EBCDBC29563']
业务内容发生变化的题：[]
```

### 一处**派生字段**修正（P1-04 §六 明确允许）

问题 B 使「`fill` 携带 options」成为结构不合格，而 P1-03 入库的
`AIQ:7EBCDBC29563` 正是这种题。因此对它做了**规则纠正性质的派生字段修正**：

```text
stale        : 0 → 1
stale_reason : NULL → 'VALIDATOR_CHANGED'
stale_since  : 2026-09-17T19:10:00+08:00
新增事件      : MARKED_STALE（actor=validator_v3, actor_kind=machine）
                from_status = to_status = PENDING_REVIEW（生命周期不变）
```

**未改动任何业务内容，也未改变生命周期。** 另一道题 `AIQ:3179968E3E74` 不受影响
（它是 `vocab_choice`，在新规则下仍然合规）。

`needs_human_review` 无需重算：两道题在新规则下依然满足触发条件
（`vocab_choice` 的答案 `polite`、`fill` 的答案 `sentence` 都逐字出现在各自的
`evidence_quote` 中），因此两值仍为 1，与原值一致。

### 处置建议（留给人工审核）

`AIQ:7EBCDBC29563` 现已标记 `stale=1 / VALIDATOR_CHANGED`，**不应再作为可用题**；
人工审核时建议以 `REVIEW_REJECTED` + `reason_code='TEXTBOOK_MISMATCH'` 或
`'OTHER'` 结案（本轮未代为决定，因为本轮没有人工审核）。

---

## 7. §九 硬门槛复验（在 v2 schema 上）

| 硬门槛 | 结果 |
| --- | --- |
| validator PASS ≠ ACTIVE | ✔（新题不能以 ACTIVE 插入） |
| 无人工 `REVIEW_APPROVED` 不能 ACTIVE | ✔（机器事件不算数；人工事件后才允许） |
| `question_event` 不可 UPDATE / DELETE | ✔ |
| question 不可物理删除 | ✔ |
| `UNSUPPORTED` 不可 PASS | ✔（CHECK 约束） |
| `AIQ:` / `AIRUN:` 不可进入 `item_id` | ✔ |

---

## 8. 保护项

| 资产 | 结果 |
| --- | --- |
| `learning.db` | **未修改**：SHA256 `0C27267BF83A70A75BB400F0055B62CB2985A83EDD120B9AC790A7FD5E59CF91` |
| contentpack v5 | **未修改**：2,715,648 B，mtime 2026-09-14 14:37:54，`ai_artifact` = 0 行 |
| 教材 PDF | **未修改**：SHA256 `C732051E91121BC991DBDD01235662629620DF6BFCCBBBD834EAEA6FCECD4F2F` |
| 54 个官方 MP3 | **未修改**：54 / 54 与 `audio_asset.sha256` 完全一致 |
| `validator_v2.py` | **未修改**：SHA256 `7C61585A…A683` |
| P1-02 `ql_schema.py` | **未修改**：SHA256 `E152E9A82648C44F3B1B3F73CCDB4610467632E7E3F4E7243B3BF0DF5B06DAF9` |
| P1-03 产物 | 未修改（`run_pipeline.py` SHA256 `77ECFCA5…` 与生成时一致） |
| P0 / P1-01 / P1-02 / P1-03 报告 | 未修改 |
| Web / Android / V1.3 / V2.0 | 未修改 |
| 重新解析 PDF | **否** |
| AI 调用 | **0** |
| 生成新题 | **0** |

本轮被修改的正式资产**只有** `structured/ai/question_library.db`
（schema v1→v2、1 个触发器替换、1 道题 3 个派生字段 + 1 条事件）。

---

## 9. 产物

| 文件 | 说明 |
| --- | --- |
| `validator_v3.py` | 新 validator（复用 v2 + 收紧 fill 规则 + `exact_print_risk`） |
| `ql_schema_v2.py` | v2 schema 定义（增量：新事件枚举 + 新 EXACT 触发器）与迁移语句 |
| `dryrun_migration.py` | 内存库迁移演练 |
| `migrate_to_v2.py` | 正式库 v1 → v2 迁移（带逐表哈希校验） |
| `mark_validator_changed_stale.py` | 因规则变化而 stale 的题的派生字段修正 |
| `test_p1_04_rules.py` | P1-04 测试（T1–T15 + §九 硬门槛） |
| `dump_p1_04_audit.py` | 审计导出工具 |
| `p1_04_rule_fix_audit.json` | 审计结果 |
| `migration_v1_to_v2.json` | 迁移前后逐表行哈希对比 |
| `stale_marking.json` | stale 标记结果与业务字段比对 |
| `p1_04_rule_fix_report.md` | 本报告 |
| `README.md` | 索引 |

结果：**FIX_PASS**。按指令不进入 P1-05。
