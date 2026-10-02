# P1-08-C 实施报告 · 人工审核 → APPROVED → ACTIVE 全流程实跑

结论：**P1-08-C_PASS**

核心事实：`AI 生成 + validator PASS + 入库 PENDING_REVIEW` 之后，本题库**不会**自动变成可用题；只有经过
人工 `REVIEW_APPROVED` 事件，再经过一次**显式启用**（`ACTIVATED`）事件，题才会成为 `ACTIVE`。
本轮真实跑通了这条链路，同时用 12 项拒绝性测试确认了越权路径全部被数据库层硬门槛拦下。

---

## 1. 初始题库状态（只读审计）

```text
文件            structured/ai/question_library.db
SHA256          F74CA83F7C8A98F2A4A2E672E7BA61ECC34CBFC2338AC10064BF18C0FFD1FD6A
大小            180,224 B
schema          user_version = 2（未改动）
integrity_check ok
foreign_key_check  空
孤儿引用         question_evidence / learning_object / validation / event / generation_run 全部 0
状态↔事件一致    21 / 21 题一致（状态字段 = 该题最后一条事件的 to_status）
```

| 表 | 行数 |
| --- | --- |
| `generation_run` | 12 |
| `ai_question` | 21 |
| `question_evidence` | 22 |
| `question_learning_object` | 37 |
| `question_validation` | 21 |
| `question_event` | 41 |

```text
生命周期   PENDING_REVIEW 21 · APPROVED 0 · ACTIVE 0 · REJECTED 0 · DISABLED 0
事件类型   VALIDATED 21 · PENDING_REVIEW 19 · MARKED_STALE 1
STALE      1 条（AIQ:7EBCDBC29563，stale_reason=VALIDATOR_CHANGED）
```

任务书要求的基线 `PENDING_REVIEW 21 / ACTIVE 0` **成立**。

---

## 2. 选择的测试样本与理由

没有全量处理 21 道题，只选 4 个样本覆盖不同生命周期路径：

| 样本 | question_id | 选择理由 | 用途 |
| --- | --- | --- | --- |
| A | `AIQ:BD59C5958D45` | U2 UI A1、`vocab_choice`、evidence/learning_object/validation/provenance 完整、非 STALE | 真实走 `PENDING_REVIEW → APPROVED → ACTIVE` |
| B | `AIQ:1B3AF72923C4` | Starter GET_READY A3、`fill`、`mechanical_rewrite=true`、evidence 引文为三词片段 | 真实人工驳回 `PENDING_REVIEW → REJECTED` |
| C | `AIQ:75AAEBFE06DF` | U2 UI A1、依赖完整、保持未审核 | 验证 `PENDING_REVIEW` 直接 `ACTIVE` 被拒 |
| D | 同 Sample A | 提交 `REVIEW_APPROVED` 之后、写入 `ACTIVATED` 之前的状态 | 验证 `APPROVED` 不会自动变 `ACTIVE` |
| E | `AIQ:7EBCDBC29563` | 唯一 `stale=1 / VALIDATOR_CHANGED` 的题（P1-03 历史题） | 验证 `STALE` 不能绕过（重新）审核直接 `ACTIVE` |
| F | —— | 当前 21 题五表依赖**全部完整**，不存在缺 evidence / validation / learning_object / provenance 的题 | 记为**未实测**，不伪造数据 |

---

## 3. 拒绝性测试（先做，全部在显式事务内执行并强制回滚）

所有测试在 `BEGIN` 后执行，无论结果如何都 `ROLLBACK`；执行后已确认题库中**没有** `PROBE` / `-TEST` 残留事件或残留题。

| # | 尝试 | 预期 | 实测 | 数据库返回 |
| --- | --- | --- | --- | --- |
| T1 | `PENDING_REVIEW → ACTIVE`（直接改状态） | BLOCKED | **BLOCKED** | `ACTIVE requires a human REVIEW_APPROVED event` |
| T1b | 走"事件先写、状态后改"的规范顺序，但无人工批准事件 | BLOCKED | **BLOCKED** | 同上 |
| T2 | `PENDING_REVIEW → APPROVED` | PASS | **PASS**（真实执行，见 §4） | —— |
| T3 | `APPROVED → ACTIVE`（显式启用） | PASS | **PASS**（真实执行，见 §4） | 必须另有一次 `ACTIVATED` 动作 |
| T4 | `REJECTED → ACTIVE`（无新批准） | BLOCKED | **BLOCKED** | `ACTIVE requires a human REVIEW_APPROVED event` |
| T5 | `STALE → ACTIVE`（无新人工批准） | BLOCKED | **BLOCKED** | 同上 |
| T6 | 缺 evidence / validation / learning_object / provenance → ACTIVE | 存在则 BLOCKED | **未实测** | 无合格测试对象 |
| T12 | `lifecycle_status='PENDING_REVIEW'` 时置 `active=1` | BLOCKED | **BLOCKED** | `CHECK constraint failed: (lifecycle_status='ACTIVE' AND active=1) OR (...)   ` |
| T14 | 以 `actor_kind='machine'` 写 `REVIEW_APPROVED`（伪造审批） | BLOCKED | **BLOCKED** | `CHECK constraint failed: event_type <> 'REVIEW_APPROVED' OR actor_kind='human'` |
| T15 | 写非法事件类型 `FORCED_APPROVE` | BLOCKED | **BLOCKED** | `CHECK constraint failed: event_type IN (...)` |
| T16 | 写 `REVIEW_REJECTED` 但不给 `reason_code` | BLOCKED | **BLOCKED** | `CHECK constraint failed: ... reason_code IS NOT NULL` |
| T17 | `UPDATE question_event`（篡改事件） | BLOCKED | **BLOCKED** | `question_event is append-only: UPDATE is forbidden` |
| T18 | `DELETE question_event` | BLOCKED | **BLOCKED** | `question_event is append-only: DELETE is forbidden` |
| T19 | `DELETE ai_question` | BLOCKED | **BLOCKED** | `ai_question rows may not be deleted; use DISABLED instead` |
| T20 | 直接 `INSERT` 一道 `lifecycle_status='ACTIVE'` 的新题 | BLOCKED | **BLOCKED** | `validator PASS is not enough: a question cannot be inserted as ACTIVE` |

**12 项预期 BLOCKED 的测试全部被拦下，无一项越权通过。**

另有 1 项**信息性探测**（T5b，同样回滚，不留痕）：
`STALE → 新的人工 REVIEW_APPROVED → ACTIVATED → ACTIVE` 在数据库层**被允许**。
这不是漏洞绕过（它确实走了一次新的人工审核），但说明"STALE 必须重新验证"目前只是流程约定，见 §9 发现 F2。

---

## 4. 真实生命周期执行

### Sample A：`PENDING_REVIEW → APPROVED → ACTIVE`

```text
AIEV:BD59C5958D45:V1  VALIDATED        GENERATED      -> VALIDATED        (machine, validator_v3, P1-07 入库)
AIEV:BD59C5958D45:P1  PENDING_REVIEW   VALIDATED      -> PENDING_REVIEW   (machine, p1_07_ingest)
AIEV:BD59C5958D45:RA  REVIEW_APPROVED  PENDING_REVIEW -> APPROVED         (human, human:project-owner)   ← 本轮新增
AIEV:BD59C5958D45:AC  ACTIVATED        APPROVED       -> ACTIVE           (human, human:project-owner)   ← 本轮新增
```

两次动作是**两个独立事务、两条独立事件**：先审核批准，再显式启用。
中间的 Sample D 检查点（批准后、启用前）读到的状态是

```json
{"lifecycle_status": "APPROVED", "active": 0, "auto_promoted": false}
```

即 `APPROVED` **不会**自动升级为 `ACTIVE`，符合 V1.0 §11 第 3 条。

### Sample B：`PENDING_REVIEW → REJECTED`

```text
AIEV:1B3AF72923C4:RR  REVIEW_REJECTED  PENDING_REVIEW -> REJECTED  (human, reason_code=LOW_VALUE)
```

题行保留在题库（`ai_question` 不可删除），`active=0`，且随后 `REJECTED → ACTIVE` 被硬门槛拦下。

### Sample C / E

保持不动：`AIQ:75AAEBFE06DF` 仍为 `PENDING_REVIEW`；`AIQ:7EBCDBC29563` 仍为 `PENDING_REVIEW + stale=1`。

### 生命周期事件衔接

21 道题的 `from_status → to_status` 链条**全部连续**，`lifecycle_status` 与每条题的最后一条事件 `to_status` **全部一致**，
不存在同一题两个冲突状态。P1-08-C 新增事件与 P1-07 / P1-03 的历史事件正确衔接。

---

## 5. 人工审核记录

审核人身份与内容见 `human_review_record.json`。摘要：

| 项 | Sample A（通过） | Sample B（驳回） |
| --- | --- | --- |
| 教材依据 | `FLTRP-EN-7A-2022CUR:P37:B10`，page 32，U2 UI A1 | `FLTRP-EN-7A-2022CUR:P8:B16`，page 3，Starter GET_READY A3 |
| 引文 | "As a rock music lover, I play the electric guitar in the school band." | "I am ready, too" |
| 答案 | `band`，在引文中**逐字命中** | `ready` |
| 结论 | `APPROVE` | `REJECT_CONTENT`（reason_code=`LOW_VALUE`） |
| 理由 | 教材依据可回溯、题干可理解、答案唯一且为教材原句用词、四个选项均来自当前 Unit 教材素材；依赖与 provenance 完整 | 题干是教材短句的三词机械挖空片段（`mechanical_rewrite=true`），学习增量低于可入库标准 |

两点必须如实记录：

1. **审核人身份限制**：本轮审核发生在同一工作流内，`actor` 记为 `human:project-owner`（人类项目所有者，按本轮明确指令执行）。
   agent 只提供只读的事实性追溯核对结果，未代替人类做质量判断。正式生产需要可归责的审核人身份与时间戳（审核命令/界面）。
2. **Sample B 的次要观察**：题干 "I am ___, too." 单独看并不唯一（happy / fine / tired 同样成立），唯一性依赖学生已有教材原句。
   该问题**没有**被写成第二条驳回事件（事件表 append-only，本轮不追加非必要事件），仅作为后续入库闸门的设计输入记录在此。

---

## 6. ACTIVE 进入学习流程的门槛

正式学习层目前**尚未**连接本题库，因此按任务书要求只验证题库自身的硬门槛。学习候选读取口径：

```sql
SELECT question_id FROM ai_question
WHERE lifecycle_status = 'ACTIVE' AND active = 1 AND stale = 0;
```

| 状态 | 是否可被学习候选读取 |
| --- | --- |
| `ACTIVE`（`AIQ:BD59C5958D45`） | **可以**（查询仅返回这 1 条） |
| `PENDING_REVIEW`（`AIQ:75AAEBFE06DF`） | 不可以 |
| `APPROVED` 但未启用（Sample D 检查点） | 不可以 |
| `REJECTED`（`AIQ:1B3AF72923C4`） | 不可以 |
| `STALE`（`AIQ:7EBCDBC29563`） | 不可以 |

未修改 `learning.db`，AI 题仍然**没有**出现在孩子的正式学习流程中。

---

## 7. ACTIVE 的必要依赖与 provenance

唯一一道 `ACTIVE` 题（`AIQ:BD59C5958D45`）逐项核对：

```text
lifecycle_status   ACTIVE, active=1
human approval     REVIEW_APPROVED ×1（actor_kind=human）
activation         ACTIVATED ×1
教材定位           textbook_id / unit_id / section_id / activity_id / page=32 全部存在
evidence           1 条（P37:B10，引文非空）
learning_object    2 条（item_id 保持 LearningObject 语义，非 AIQ:/AIRUN:）
validation         1 条（validator v3、PASS、answer_support_type=EXACT）
provenance         generation_run=AIRUN:20260917T201605:P106_S1
                   model=deepseek-v4-pro · prompt_version=P1-05-v3
                   context_hash=574B24DC8633E26A2B9402A161AD6D5C25EB613E7DB525B4903BF0E2641496E5
                   provider=deepseek · finish_reason=stop
                   context_ref / raw_response_ref 指向 P1-06 真实请求与响应
                   generated_at=2026-09-17T20:16:05+08:00 · question_fingerprint 64 位
```

无缺失项。

---

## 8. 事件不可篡改与最终题库状态

```text
question_event INSERT   正常（本轮真实追加 3 条）
question_event UPDATE   被拒（触发器）
question_event DELETE   被拒（触发器）
ai_question  DELETE     被拒（触发器）
事件顺序              21/21 题连续
状态 ↔ 事件一致       21/21 题一致
未删除任何历史事件，未"恢复原状"
```

执行前后：

| 指标 | 前 | 后 |
| --- | --- | --- |
| `generation_run` | 12 | 12 |
| `ai_question` | 21 | 21 |
| `question_evidence` | 22 | 22 |
| `question_learning_object` | 37 | 37 |
| `question_validation` | 21 | 21 |
| `question_event` | 41 | **44**（+3） |
| `PENDING_REVIEW` | 21 | 19 |
| `APPROVED` | 0 | 0 |
| `ACTIVE` | 0 | **1** |
| `REJECTED` | 0 | **1** |
| `DISABLED` | 0 | 0 |
| `stale=1` | 1 | 1（`AIQ:7EBCDBC29563` 未变） |

只有 2 道题发生变化（Sample A、Sample B），其余 19 道（含 Sample C、Sample E）逐字段未变。
数据库 `integrity_check=ok`、`foreign_key_check` 空、孤儿引用 0。

Schema 比对：`sqlite_master` 对象**新增 0 / 删除 0 / 修改 0**，`user_version` 仍为 2 —— **未改 schema**。

---

## 9. 发现（如实记录，含未验证项）

**已确证有效的硬门槛**

- 新题不能以 `ACTIVE` 插入；
- 转 `ACTIVE` 必须有 `actor_kind='human'` 的 `REVIEW_APPROVED` 事件，且 `ACTIVATED` 必须是独立动作；
- `active=1` 与 `lifecycle_status='ACTIVE'` 互为充要（CHECK）；
- 题不可删、事件不可改不可删、非法事件类型与伪造审批被拒；
- `EXACT` 命中时强制 `needs_human_review=1`；
- 状态字段与事件历史一致，事件链从头到尾连续。

**F1 · 工程缺口（非阻塞）：没有正式的人工审核/启用命令或界面**

仓库里只有数据库层触发器，没有审核服务、命令行或界面。本轮按任务书允许的方式（"若当前没有正式服务/命令，
按现有设计执行，不得自行增加新 API"）用 SQL 事件写入执行。这属于必须补齐的工程缺口：正式生产需要可归责的审核人身份、
审核时间戳与操作入口。

**F2 · 机制缺口（需设计，非阻塞）：两条约束只在流程层，不在数据库层**

1. 数据库层没有"`ACTIVE` 必须存在 evidence / validation / learning_object"的硬约束。
   依赖完整性目前由唯一写入方（P1-07 `ingest.py` 的五表同事务写入 + Gate 1–5）保证。
   本轮实测时当前 21 题依赖**全部完整**，因此无法在不伪造数据的前提下实测该门槛（记为 **T6 未实测**）。
2. `stale=1` 的题在一次**新的人工** `REVIEW_APPROVED` 之后可以进入 `ACTIVE`（T5b 回滚探测）。
   这符合"重新审核"的语义，但"STALE 必须重新验证"目前没有数据库层强制。

以上两条建议在下一阶段做机制设计（不通过堆 Prompt 规则解决）。

**未验证项**

```text
T6  缺依赖 → ACTIVE        未实测（无合格测试对象，未伪造数据）
F2  数据库层依赖门槛        不存在，未在本轮新增（禁止改 schema）
```

---

## 10. 正式资产保护

以只读哈希清单覆盖 **1099 个文件**（`structured/learning`、`structured/contentpack` v1–v5、`structured/textbook`、
`structured/audio`（含 54 个官方 MP3）、`structured/exercises`、`structured/staging`、`docs`、`web`、`android`、
教材 PDF、validator v2/v3、P1-04/05/06/07/08-A/08-B 既有产物、V1.3 / V2.0 正式文档）：

```text
manifest 前  653A0DF87568B9F698EEA9D42BBC279F6A0258DC5352A537FF88198A9C5A25FA
manifest 后  653A0DF87568B9F698EEA9D42BBC279F6A0258DC5352A537FF88198A9C5A25FA
新增 0 / 删除 0 / 修改 0
```

抽样核对（与 P1-08-B 结束时一致，未变）：

```text
learning.db            0C27267BF83A70A75BB400F0055B62CB2985A83EDD120B9AC790A7FD5E59CF91
contentpack v5         65829CA73E41B75ACA010B93B7339EDDF0F666F919148F0F69ED898419700C39
validator_v2.py        7C61585A99B55576CA82D9946635784964322236BA145A23FBDFA2A1F8DCA683
validator_v3.py        EDB1AA5431626752B6D4699EC25ADAC76B10996ABFEC2EA43BDF4CAEB28D900C
教材 PDF               已含在 1099 文件清单内，未变
54 个官方 MP3          已含在 1099 文件清单内，54/54 未变
```

唯一变化的正式资产是 `structured/ai/question_library.db`（本轮授权范围），并且只追加了 3 条事件。
`learning.db` 未被写入，AI 题未进入学习流程。

---

## 11. 任务书 §15 的 17 个问题

1. **初始题库状态？** 21 题全部 `PENDING_REVIEW`，`ACTIVE=0`；事件 41 条（`VALIDATED 21`、`PENDING_REVIEW 19`、`MARKED_STALE 1`）；schema v2；完整性、外键、孤儿、状态↔事件一致性全部通过。
2. **选了哪几道题、为什么？** Sample A（正常批准）、B（人工驳回）、C（未审核）、D（APPROVED 未启用，=A 的中间态）、E（唯一 STALE 历史题）；F（缺依赖）无合格对象，未实测。
3. **`PENDING_REVIEW → APPROVED` 是否真实成功？** **是**，`AIQ:BD59C5958D45`，事件 `AIEV:BD59C5958D45:RA`，`actor_kind='human'`。
4. **`APPROVED → ACTIVE` 是否真实成功？** **是**，独立事件 `AIEV:BD59C5958D45:AC`；批准与启用是两次分离动作。
5. **`PENDING_REVIEW → ACTIVE` 是否被阻止？** **是**，直接改状态与"事件先写"两种走法都返回 `ACTIVE requires a human REVIEW_APPROVED event`。
6. **`REJECTED → ACTIVE` 是否被阻止？** **是**，Sample B 被驳回后尝试直接启用被拒。
7. **`STALE → ACTIVE` 是否被阻止？** **是**（无新批准时）。回滚探测显示"经过一次新的人工审核再启用"是被允许的，见 F2。
8. **缺 evidence / validation / learning_object 时能否阻止 ACTIVE？** **未实测** —— 当前 21 题依赖全完整，无合格对象，未伪造数据。同时发现数据库层缺少该类硬约束（F2）。
9. **ACTIVE 是否具备完整 provenance？** **是**，`generation_run / model / prompt_version / context_hash / provider / finish_reason / context_ref / raw_response_ref / generated_at / fingerprint / validator_version` 全部存在。
10. **ACTIVE 能否被"学习候选"只读判定读取？** **能**，学习候选查询只返回 `lifecycle_status='ACTIVE' AND active=1 AND stale=0`，实测返回且仅返回 `AIQ:BD59C5958D45`。
11. **`PENDING_REVIEW` / `REJECTED` / `STALE` 是否不能进入学习候选？** **是**，三类均不被返回。
12. **`question_event` 是否完整且不可篡改？** **是**：INSERT 正常，UPDATE/DELETE 被触发器拒绝，事件链 21/21 连续，状态与事件历史 21/21 一致，未删除任何历史事件。
13. **是否修改了数据库 schema？** **没有**：`sqlite_master` 对象新增 0 / 删除 0 / 修改 0，`user_version` 仍为 2。
14. **除 `question_library.db` 外是否修改任何正式资产？** **没有**：1099 文件哈希清单前后完全一致（含 learning.db、contentpack、教材数据、54 MP3、PDF、Web、Android、validator、V1.3、V2.0、P1-06/07/08-A/08-B 产物）。
15. **AI 调用是否为 0？** **是，0 次**（DeepSeek 0、Ollama 0、其它云端模型 0、无新题生成）。
16. **最终题库状态？** `ACTIVE 1 / PENDING_REVIEW 19 / REJECTED 1`；`ai_question 21`、`question_event 44`；DB SHA256 `7AA12CA5EB24417BF0AE7E97A8161920B501825D030D69A8E0863272AC695DA7`；`integrity_check=ok`、外键与孤儿检查干净。
17. **是否发现生命周期机制缺陷？** 硬门槛本身**有效且无绕过**；发现两条机制口径缺口（F1 无正式审核命令/界面；F2 依赖完整性与 STALE 复审未在数据库层强制）以及 1 项未实测项（T6）。均为**非阻塞**设计输入，不属于 `STOP_AND_FIX` 条件（未出现未审核可 ACTIVE、STALE 绕审、ACTIVE 缺依赖、事件可篡改、状态与事件不一致、跨库污染）。

---

## 12. 最终结论

```text
P1-08-C_PASS
```

理由：

```text
正常审核 → 批准 → 显式启用链路真实跑通            是
未审核不能 ACTIVE                                是（含 2 种越权走法）
REJECTED / STALE 不能绕过（重新）审核 ACTIVE       是
ACTIVE 具备必要依赖与 provenance                 是
event 正常、append-only、顺序与状态一致            是
无非预期正式资产变化（仅 question_library.db 授权变更）  是
```

本阶段只证明了一件事：

> AI 题从"生成 / 验证通过"到"可以使用"，中间**确实存在且有效**的人工审核与显式启用闸门；
> 机器验证通过**不等于**自动可用。

本轮**不会**自动进入下一阶段，也不建设正式 AI 题库批量能力。
