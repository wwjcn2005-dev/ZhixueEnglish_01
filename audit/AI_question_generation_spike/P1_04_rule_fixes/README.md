# P1-04 · AI Question Library 规则修正

最终状态：**FIX_PASS**
AI 调用：**0** · 新生成题目：**0**

---

## 三个问题的处理结果

| 问题 | 处理 | 落点 |
| --- | --- | --- |
| **A** EXACT 特殊复核对选择题过度触发 | **已修正** | `question_library.db` 触发器 `trg_validation_exact_trap` + `validator_v3.exact_print_risk()` |
| **B** `fill` 可携带 options / correct_option | **已约束**（validator 必须 FAIL） | `validator_v3.type_rules()`（v2 原样未改） |
| **C** 事件枚举无法表达 `GENERATED` / `PENDING_REVIEW` | **已升级** schema v1 → v2 | `question_library.db`，逐行数据不变 |

---

## A：新的 EXACT 规则

```text
修改前：EXACT 且（答案出现在题干 或 答案出现在 options）           → 选择题几乎必然触发
修改后：EXACT 且 题目可选型（有 options）且 正确答案出现在教材 evidence_quote 中 → 触发
```

- **options 本身不再是触发依据**（消除 P1-03 的误报）
- **纯填空题不触发**（孩子必须自己写答案，没有可照抄的选项）
- **只看正确答案**，错误选项出现在教材引文中不触发
- `answer_support` 判定**未被放宽**——v3 直接复用 v2 的函数对象

## B：fill 的正式定义

```text
fill = 纯填空：题干必须有 ___ ；不得有 options ；不得有 correct_option
```

违反任一条 → **validator FAIL**。本轮不新增题型。

## C：schema v1 → v2

```text
user_version : 1 → 2
枚举新增     : GENERATED、PENDING_REVIEW
数据影响     : 无（6 张表逐行哈希全部一致，含 question_event 的 2 行）
索引/触发器  : 原样恢复，另替换 EXACT 触发器
```

迁移前先在内存库 dry-run，再对正式库执行，并逐表比对行哈希。

---

## 测试

```text
P1-04 新测试        28 / 28 PASS
P1-02 回归          18 / 19 PASS
```

**P1-02 唯一失败项必须说明**：`test_T15_official_db_has_no_real_questions` 断言「正式题库为空」，
而该断言已被 **P1-03 的合法入库**取代（题库现有 2 道真实题）。本轮又禁止删除这两道题，
因此它在结构上不可能再通过。P1-04 用同一 v1 schema 定义新增了等价测试，覆盖 T15 的原始意图
「建库脚本不插入任何数据」并 PASS。其余 18 项（含全部硬门槛）无退化。

---

## 已有两道真实题

**业务内容零变化**：`question_text` / `options` / `correct_option` / `answer` /
`explanation` / `evidence` / `fingerprint` / `lifecycle_status` 全部未动，
未重新生成、未删除。

唯一改动是**派生字段**（P1-04 §六 允许的规则纠正）：

```text
AIQ:7EBCDBC29563 （fill + options，在新规则下不再合规）
  stale        0 → 1
  stale_reason NULL → 'VALIDATOR_CHANGED'
  stale_since  2026-09-17T19:10:00+08:00
  新增事件      MARKED_STALE（生命周期不变，仍为 PENDING_REVIEW）
```

另一道 `AIQ:3179968E3E74`（vocab_choice）在新规则下仍然合规，不受影响。

---

## 保护项

```text
learning.db        未修改（SHA256 0C27267B…CF91）
contentpack v5     未修改（ai_artifact = 0 行）
教材 PDF           未修改（SHA256 C732051E…4F2F）
54 个 MP3          未修改（54 / 54 与 audio_asset.sha256 一致）
validator_v2.py    未修改（SHA256 7C61585A…A683）
P1-02 ql_schema.py 未修改（SHA256 E152E9A8…DAF9）
P1-03 产物          未修改
P0/P1-01/P1-02/P1-03 报告  未修改
Web / Android / V1.3 / V2.0  未修改
AI 调用             0
重新解析 PDF        否
```

本轮被修改的正式资产**只有** `structured/ai/question_library.db`。

---

## 产物

| 文件 | 说明 |
| --- | --- |
| `README.md` | 本索引 |
| `p1_04_rule_fix_report.md` | 完整修正报告 |
| `p1_04_rule_fix_audit.json` | 审计结果 |
| `validator_v3.py` | 新 validator（复用 v2，只收紧 fill 规则） |
| `ql_schema_v2.py` | v2 schema 与迁移语句 |
| `migrate_to_v2.py` / `dryrun_migration.py` | 迁移执行与演练 |
| `migration_v1_to_v2.json` | 迁移前后逐表行哈希对比 |
| `mark_validator_changed_stale.py` / `stale_marking.json` | 派生字段修正与业务字段比对 |
| `test_p1_04_rules.py` | 28 项测试 |
| `dump_p1_04_audit.py` | 审计导出工具 |

---

## 给 P1-05 的输入

1. `validator_v3.py` 目前位于本目录；若要成为正式版本，需要一次明确的版本落地决定
   （`validator_v2.py` 保持不动）。
2. `AIQ:7EBCDBC29563` 已在待审队列中标记 `VALIDATOR_CHANGED`，需要人工给出
   `REVIEW_REJECTED` 或修正后重新生成（本轮不代为决定）。
3. 事件枚举已可表达 `GENERATED → VALIDATED → PENDING_REVIEW`，后续流水线应逐段记录，
   不再用单条 `VALIDATED` 事件折叠表达。
