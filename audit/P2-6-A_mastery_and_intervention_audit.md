# P2-6-A 掌握判定与“诊断 → 巩固”链路只读审计报告

> 本报告只做只读检查、关系梳理、差距分析与实施建议。**本轮未修改任何既有文件**，
> 未修改数据库、contentpack、P2-4/P2-5 成果、业务代码、Web UI、Android 与规范 V1.2，未调用 AI。

- 审计时间：2026-09-13
- 审计对象：`learning/`（6 个服务）、`structured/learning/learning.db`、`web/`（flow/app/ui/exercises/ai_grading）、`workbench/`、P2-4/P2-5 成果、规范 V1.2
- 项目状态：无 Git 仓库（`git` 不可用）；V1.0 / V1.1 / V1.2 三版规范均在；P2-5 与 P2-5-C 成果均在
- 测试基线：**332 PASS / 0 FAIL / 0 SKIP**（web 224 + learning 58 + workbench 50）

---

## 1. 实施结论

**PASS WITH GAPS**

本轮完成了 V1.2 原则 → 数据 → 学习服务 → 诊断 → 巩固 → 新证据的全链路只读审计，并定位了 5 类实质缺口（掌握判定缺失、证据去重缺失、任务类型未结构化、诊断-巩固链路缺失、教材优先资源未接线）。
所有缺口均为“待 P2-6-B 实现”，**不是本轮可修复项**；本轮目标为审计，故判定 PASS WITH GAPS。

---

## 2. 当前实现地图

| 环节 | 当前实现位置 | 事实 |
| --- | --- | --- |
| V1.2 原则 | `初中英语…规范_V1.2.docx` / `docs/…V1.2.md`（第二十二章） | 已定义 学过/掌握较稳定、证据优先、教材优先巩固、AI 边界、阶段验证、专项学习 |
| 教材事实 | contentpack v5 + P2-4 结构/证据包 | 157 活动 / 360 题 / 54 音频；**业务代码尚未读取 P2-4 证据包** |
| 学习事实 | `learning_record`（20 行） | 行为（activity_type）＋结果（result）＋attempt_no＋hints_used＋response_raw＋created_at |
| 服务层 | `learning_service` / `session_service` / `activity_service` / `behavior_service` | 写入 Record + UPSERT mastery_state，同一事务 |
| 掌握缓存 | `mastery_state`（7 行） | `mastery_level` 全部为 `unknown`；`evidence_count` 最多 8、`correct_count` 最多 3 |
| 池（当前错误/薄弱） | `resource_pool_service`（只读派生） | 当前错误=最近 judged=incorrect；当前薄弱=最近 judged=partial；含 judged/incorrect/partial/correct 计数 |
| 诊断 | **不存在** | 无 diagnosis 表/字段/服务；池只表达“最近状态事实” |
| 巩固建议 | **不存在** | 无建议生成、无干预模型接线（`intervention_model_v1.json` 仅设计文档） |
| 巩固行为 | 部分存在 | `/review` 页面只能把**词汇**送回 `/vocabulary/study`；练习类薄弱项不展示 |
| 新证据 | 同 学习事实 | 再次作答会产生新 Record（未做去重/独立性判定） |
| AI | `web/ai_grading.py`（本地规则预检） | `ai_status = not_connected`；业务代码无任何网络/AI 调用点 |

---

## 3. 掌握判定差距矩阵

| V1.2 要求 | 当前实现 | 缺口 | P2-6 是否需要处理 |
| --- | --- | --- | --- |
| **≥3 个有效判断证据** | `mastery_state.evidence_count` 计数（含 done 也计数，见 `EVIDENCE_RESULTS`） | ①把 `done`（自评完成）计为证据；②无“有效”定义落地；③无去重 | **是（核心）** |
| **≥2 种任务类型** | 无 task_type 字段；`activity_type` 混用（服务端=resource type，调用方=行为） | 练习类可经 `item_id → exercise_catalog_v3.question_type` 恢复（choice/fill/short_answer…）；词汇类只有 study/practice 两种，recall 未单独记录 | **是（可先派生，后补字段）** |
| **≥2 个自然日** | `created_at` 为 ISO8601 带 `+08:00`，可可靠计算自然日 | 现有数据全部集中在 2026-09-12（1 天），条件**当前不可达**（数据不足，非缺陷） | 是（判定实现时需按自然日去重） |
| **最近 3 次 ≥2 次正确** | **不存在**（无 rolling/last-N 逻辑） | 需在判定中按 (learner,item) 取最近 3 条 judged 记录 | **是（核心）** |
| **无未处理当前错误** | `resource_pool_service` 可给出“最近 judged=incorrect” | 无“未处理”概念（无处理动作与标记） | **是（需定义处理动作）** |
| **重复行为去重** | 无 | 真实数据已出现：同一 (learner,item,自然日,任务) 重复 2 次的组合有 **3 组**；同一词汇对象单日 **8 条**记录 | **是（核心）** |
| **学过 ≠ 掌握** | 满足：`mastery_level` 从不推进；UI 只用“未学/学过/错误/薄弱” | 无（现状正确，需在实现判定时保持） | 否（保持） |
| **单次正确 ≠ 掌握** | 满足：仅计数，无升级 | 无（保持） | 否（保持） |
| **单次错误 ≠ 薄弱** | **部分不满足**：池以“最近一条 judged=incorrect”即进入当前错误 | 缺“≥2 次错误 / 跨任务重复”的疑似薄弱层；文案须区分“当前错误”与“薄弱” | **是** |

---

## 4. “诊断 → 巩固”差距矩阵

| 环节 | 当前实现 | 数据来源 | 是否可追踪 | 缺口 |
| --- | --- | --- | --- | --- |
| 证据 | 有（learning_record） | `learning_record` + `mastery_state` | 可追踪（record_id / attempt_no / created_at） | 无任务类型、无独立性与强度判定 |
| 诊断 | **无** | — | — | 无阈值聚合、无“疑似/确认”分层、无归因 |
| 巩固建议 | **无** | — | — | 未接 `intervention_model_v1.json`；无“教材优先”建议生成 |
| 巩固行为 | 极弱（仅词汇回学） | `/review` → `/vocabulary/study` | 可追踪（新 Record + 新 Session） | 练习类薄弱项无入口；无“回教材/重听音频/看语法页/对照范文”路径 |
| 新证据 | 有 | 同上 | 可追踪 | 与旧证据无关联（无法区分“巩固后的验证”与“重复操作”） |

**越权行为检查（均未发现）**：无 AI 决定下一步、无自动安排任务、无自动推进、无无限生成练习、无用 AI 题替代教材原题。
（`/review` 需孩子点击才进入；练习提交需孩子点击按钮；`ai_grading` 未联网。）

---

## 5. 状态命名引用清单

**（A）规范五档命名**“未学习 / 正在学习 / 初步掌握 / 掌握较稳定 / 需要再次巩固”：

| 位置 | 类型 | 说明 |
| --- | --- | --- |
| `docs/…V1.0.md:271`、`docs/…V1.1.md:448`、`docs/…V1.2.md:465` | 规范正文 | 原 §十·2 表述 |
| `docs/…V1.2.md:477` | 规范正文 | P2-5-C 新增交叉引用：以第二十二章第 4、5 条为准，不得作为等级评价 |
| `docs/P1-04_教材内容数据模型设计_V1.md:558,729` | 上游设计 | mastery_level 取值说明（旧） |
| `audit/P1-06-B1.15_*.md:263-265`、`audit/P1-06-B1.12_*.md:211` | 设计文档 | `learning/familiar/stable` 语义定义（旧） |

**（B）代码中的等级枚举**：`learning/learning_service.py:44`（`MASTERY_LEVELS`）、`structured/learning/init_learning_db.py:90`（DDL 默认 `unknown`）——**除定义外，无任何代码写入 learning/familiar/stable**。

**（C）UI 实际使用的状态命名**：`web/flow.py:74-116` → `error / weak / studied / unseen`（“错误 / 有点模糊 / 学过 / 未学”）；`workbench/vocabulary_learning_v01.py:645-649` → “掌握状态：学习证据 N 次 …”（**存在“掌握状态”字样，但内容只是计数，不是等级**）。

**（D）测试引用**：`web/test_p2_5c_spec_sync.py:170`（校验规范措辞）；`web/test_vocabulary_flow.py:626`（“从未学习”注释）；无测试断言五档状态。

**核查结论**：①**不存在“状态＝等级”的展示**（无分数/徽章/等级文案）；②**不存在仅凭一次结果直接改变状态**（等级从不改变）；③**不存在“学过＝掌握”的实现**（`mastery_level` 恒为 unknown）。唯一需要注意的措辞是 workbench 的“掌握状态：学习证据 N 次”（建议 P2-6-B 改为“学习证据 N 次（不代表掌握）”）。

---

## 6. 数据模型问题

| 编号 | 问题 | 证据 |
| --- | --- | --- |
| M1 | **`learning_gap` 不存在**（任务书假设其存在）：库中 7 表为 learner / learning_record / learning_session / learning_task / mastery_state / schema_migration / task_item，无 gap/wrong/review 表 | `PRAGMA table_info` 全表核对 |
| M2 | **`mastery_level` 是空壳**：声明 4 档，代码只累加计数，从不推进；真实数据 7 条全为 `unknown` | `learning_service._upsert_mastery()` |
| M3 | **`done` 计入证据**：`EVIDENCE_RESULTS = (correct, incorrect, partial, done)` → “我看完了/我完成了”会抬高 evidence_count | `learning_service.py:40` |
| M4 | **无任务类型字段**：`learning_record` 无 task_type/question_type；`activity_type` 语义混用（服务端取 contentpack `item_type`，调用方写行为值） | `learning_service.py:286-289`、`activity_service.py:101`、`web/app.py:503` |
| M5 | **无会话关联字段**：`learning_record` 无 session_id，只能经 `task_id → learning_session.task_id` 间接关联 | 表结构 |
| M6 | **无“无提示”数据**：`hints_used` 全部为 0，UI 无提示机制，无法区分“独立完成”与“被提示后完成” | 20/20 条为 0 |
| M7 | **重复提交未去重**：同一 (learner,item,自然日,任务) 重复出现 3 组；同一词汇单日 8 条 | SQL 聚合 |
| M8 | **`attempt_no` 恒为 1**：因其按 (learner, task, item, activity_type) 计数，而每次学习都新建 Task | 20/20 条为 1 |
| M9 | **`response_raw` 不含题型**：仅 answers/result/summary；题型需经 item_id → exercise_catalog_v3 反查 | response_raw 抽样 |
| M10 | **P2-5 设计 JSON 无机器可读参数**：`learning_model_v1.json` 的阈值是中文描述（“≥3 条独立判断证据”），不能被程序直接读取 | 结构核对 |

---

## 7. 测试结果

| 套件 | 结果 |
| --- | --- |
| learning | 58 PASS / 0 FAIL / 0 SKIP |
| workbench | 50 PASS / 0 FAIL / 0 SKIP |
| web（含 P2-4、P2-5、P2-5-C 专项） | 224 PASS / 0 FAIL / 0 SKIP |
| **合计** | **332 PASS / 0 FAIL / 0 SKIP** |

无失败测试，因此不存在“失败是否与 P2-6 有关”的判断问题。测试未修改正式库（web 测试使用 `%TEMP%` 副本）。

---

## 8. 风险

| 风险 | 等级 | 说明 | 现有缓解 |
| --- | --- | --- | --- |
| **重复证据风险** | 高 | 若 P2-6-B 直接用 `evidence_count` 判定，会把同一时段重复操作累计成“多维证据”（真实数据已有单日 8 条） | 无（本轮新增发现） |
| **状态误判风险** | 高 | `done` 计入证据 + 无“最近 3 次”规则 → 可能出现“点了几次完成就算掌握” | 现状 `mastery_level` 不推进，属暂时安全 |
| **数据污染风险** | 中 | 现有 20 条记录中含**验收测试产生的数据**（如 `q1=test0…`、三次 `AU11` 听力自评），若直接用于判定会混入非真实学习行为 | 无标记字段（task_kind 全为 learn） |
| **AI 越权风险** | 低 | 业务代码零网络调用，`ai_grading` 为本地规则 | 设计层 `ai_role_model_v1.json` 已定义边界 |
| **教材脱离风险** | 中 | 业务代码尚未读取 P2-4 证据包/音频 v3；巩固若实现可能退化为“只出题不回教材” | P2-5 设计已给出教材优先顺序；需在 P2-6-B 强制 |

补充事实：**“当前错误”判定只看最近一条 judged 记录**——若孩子后续答对，池立即出池（历史错误仍保留在 `learning_record`）。这与 V1.2“无未处理当前错误”一致，但与“疑似薄弱需 ≥2 次”不同层，需在 P2-6-B 明确分层。

---

## 9. P2-6-B 最小实施方案（仅提议，不实施）

### 9.1 目标（最小闭环，不新增产品功能）
把 V1.2 的掌握判定与“诊断 → 教材优先巩固”做成**可验证的最小实现**，且不引入 AI、不改教材数据、不做 UI 大改。

### 9.2 修改范围

| 文件 | 修改内容 | 为什么 |
| --- | --- | --- |
| `structured/learning/mastery_rules_v1.json`（**新增**） | 把 V1.2 阈值写成机器可读参数（`min_judged_evidence=3`、`min_task_types=2`、`min_natural_days=2`、`last_n_attempts=3`、`last_n_min_correct=2`、`require_no_current_error=true`、`dedupe_by=session_or_day`） | 参数与原则分离，便于按真实数据校准 |
| `learning/mastery_service.py`（**新增，只读派生**） | 输入 `(learner_id, item_id)` 或批量，输出 `state + 依据 + 命中/未命中条件`；**不写库** | 掌握判定是派生结论，不应写回事实层 |
| `learning/evidence_service.py`（**新增，只读派生**） | 去重与“有效判断证据”过滤：排除 `done/skipped/NULL`；同会话/同自然日同 item 只计 1 条；输出任务类型（经 `item_id → exercise_catalog_v3.question_type` 与 `activity_type` 派生） | 直接消除重复证据与 done 计入问题 |
| `learning/diagnosis_service.py`（**新增，只读派生**） | 分层：`current_error`（事实）→ `suspected_weak`（≥2 次错误或跨 2 类任务重复）→ `needs_textbook_review`；附教材定位（页码来自 P2-4） | 落实“一次错误 ≠ 薄弱”与“教材优先” |
| `learning/intervention_service.py`（**新增，只读建议**） | 读 `structured/learning/intervention_model_v1.json`，按问题类型给出**教材优先**的 1–2 个干预建议（含教材页码/音频 id/语法页），**不自动执行** | 巩固链路最小实现 |
| `web/flow.py` + `web/ui.py`（**小幅扩展**） | `/review` 增加“疑似薄弱”分组与练习类条目；每条给出“回教材哪一页 / 重听哪段音频 / 重做哪道原题”的入口；文案去掉“掌握状态”歧义 | 让链路对孩子可见（不改导航结构） |
| `learning/test_*.py`（**新增测试**） | 掌握判定 9 项、证据去重 4 项、诊断分层 5 项、干预建议 5 项、越权与边界 4 项 | 与 V1.2 逐条对应 |

### 9.3 数据库是否需要迁移

**不需要表结构迁移**（M3/M5/M7 均可用派生方式解决）：

- 任务类型：`item_id → exercise_catalog_v3.question_type` + `activity_type` 派生；
- 会话关联：`learning_record.task_id → learning_session.task_id` 连接；
- 去重：按 `(learner_id, item_id, 自然日)` 或 `(…, task_id)` 分组。

若后续确需写入“处理动作/阶段验证标记”，建议**新增一张独立表**（如 `learner_action_log`）而不是改 `learning_record` 语义；该决定留待 P2-6-C。

### 9.4 是否需要新增测试

必须。至少覆盖：①done/skipped 不计证据；②同日同题重复只计 1 条；③3 证据+2 任务类型+2 自然日缺失任一项都不判 stable；④最近 3 次规则；⑤有当前错误时不得 stable；⑥池分层不把单次错误标为薄弱；⑦干预建议均带教材定位；⑧无自动推进/无 AI 调用。

### 9.5 是否需要规范 V1.3

**不需要**。V1.2 已含全部原则，P2-6-B 只实现参数与链路；参数值调整走 `mastery_rules_v1.json`，不改规范文本。若实现对某条原则产生歧义（例如“未处理当前错误”的处理动作定义），再考虑 V1.3 增补。

### 9.6 是否需要 UI / AI

- **UI**：仅 `/review` 与练习结果页的小幅扩展（不加导航、不加分数、不加徽章）；
- **AI**：**不需要**。P2-6-B 全程 AI=0；AI 批改属 P2-6-C 及以后。

### 9.7 实施顺序（建议）

1. `mastery_rules_v1.json`（参数）→ 2. `evidence_service`（去重与有效性）→ 3. `mastery_service`（判定）→
4. `diagnosis_service`（分层 + 教材定位）→ 5. `intervention_service`（教材优先建议）→
6. `web` 最小接线（/review 与结果页文案）→ 7. 测试与真机验证。

### 9.8 验收标准

| 编号 | 验收标准 |
| --- | --- |
| A1 | 现有 20 条真实记录在判定中不产生任何 `stable`（因均只跨 1 个自然日） |
| A2 | `done/skipped/NULL` 不计入判定证据；同日同题重复只计 1 条 |
| A3 | 9 项 V1.2 条件逐条有测试；缺任一项不判 `stable` |
| A4 | 单次错误只进“当前错误”，不自动升级为“疑似薄弱” |
| A5 | 所有干预建议均带教材定位（页码/音频 id/语法页），且需孩子点击才进入 |
| A6 | learning.db / contentpack / P2-4 成果未被修改；AI 调用 0；无自动推进路径 |

---

## 10. 本轮没有做什么（明确确认）

- **业务代码未修改**：`learning/`、`web/`、`workbench/`、`builder/` 均未改动（时间戳保持）
- **测试代码未修改**：现有测试文件未改动（本轮未新增测试文件）
- **数据库未修改**：`learning.db` 仅 `mode=ro` 只读访问，无写入（mtime 保持 2026-09-12 23:15）
- **正式数据未修改**：未产生任何新的 LearningRecord / Session / Task
- **contentpack / 教材原始数据未修改**：未写入
- **P2-4 / P2-5 成果未修改**：未写入
- **规范 V1.2 未修改**：未写入
- **Android 未修改**：未触碰
- **AI 调用 0**：未调用任何 AI / 网络服务
- **未进入 P2-6-B**：未实现掌握算法、未设计 UI、未迁移数据库

本轮新增文件仅为：本审计报告（`audit/P2-6-A_mastery_and_intervention_audit.md` 及其 `.json` 摘要）。
