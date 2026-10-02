# P2-5 架构影响分析（对现有代码与数据的影响）

> 只读审查结论 + 下一阶段改造建议。**本阶段不修改任何业务代码、数据库、contentpack、P2-4 产物、Android、Web UI。**

- 审查对象：`learning/`（冻结服务 6 个）、`structured/learning/learning.db`（7 表）、`web/`（app/ui/flow/content/exercises/audio/ai_grading）、`workbench/`、P2-2/P2-3/P2-4 产物
- 结论：现有实现**没有与新教育模型冲突到必须推倒的程度**，但有一个**空壳**（掌握判定）与两条**缺失链路**（诊断-巩固、AI 批改）需要重建。

---

## 1. 逐项影响评估

| 现有对象 | 现状（只读核实） | 判断 | 影响与建议 |
| --- | --- | --- | --- |
| `learning_record` | 记录行为（9 类 activity_type）、结果（correct/incorrect/partial/done/skipped/NULL）、attempt_no、hints_used、response_raw、时间戳 | **KEEP** | 就是本设计需要的“证据原始事实”。建议下一阶段只**新增**证据维度字段（task_type / source / evidence_strength），不改语义。 |
| `mastery_state` | 字段有 `mastery_level(unknown/learning/familiar/stable)`、`evidence_count`、`correct_count`、`last_result`、`review_needed`；**代码只累加计数，从不推进 mastery_level**（真实数据里 3 条证据仍是 unknown） | **REBUILD（判定） / EXTEND（存储）** | 保留表结构，但**判定输入必须扩展**：任务类型、自然日、是否无提示、证据强度。绝不能改成“计数到 N 就升级”。 |
| `resource_pool_service` | 只读派生：当前错误 = 最近一条 judged=incorrect；当前薄弱 = 最近一条 judged=partial；不改库 | **KEEP（现状语义） / EXTEND（诊断分层）** | 作为“最近状态事实”可用。建议新增“疑似薄弱”层（≥2 次错误或跨任务重复），并在 UI 文案上严格区分：**当前错误 ≠ 薄弱点**。 |
| `learning_session` / `learning_task` / `task_item` | 会话/任务/条目，`entry_point` 已有 5 值 | **EXTEND** | 增加“教材主线 / 巩固 / 阶段验证”三类会话语义（可复用 entry_point 扩展，不必改表结构）。阶段验证的会话必须可区分，才能做保持分析。 |
| `session_service` / `activity_service` / `behavior_service` | 冻结服务；要求 item 必须存在于 contentpack；`RESOURCE_TYPES` 目前只允许 vocabulary/phrase/sentence_pattern | **EXTEND（受控）** | 教材练习已有 157 条 `learning_item(item_type='exercise')` 可用。若下一阶段要做“阶段验证会话”，建议**只扩 entry_point / task_kind 的取值**，不放开 RESOURCE_TYPES（避免题库化）。 |
| `web/ai_grading.py` | 本地规则预检，明确 `ai_status = not_connected` | **REBUILD（链路）** | 需要接入 P2-4 `textbook_evidence_map_v1.json` 的证据包与 §六 的输出契约；本阶段仍不接真实 API，先用契约校验与 mock。 |
| `web/exercises.py` + `exercise_catalog_v3` | 真实题型（16 类里 10 类）、教材空位、🎧 音频、不伪造答案 | **KEEP** | 直接作为“证据产生器”。建议结果页预留 AI 批改结论位（暂显占位，不显示分数）。 |
| `web/ui.py` 页面族 | 首页 / 教材中心 / Unit / 资源列表 / Study-Recall-Result / 练习列表-练习-结果 / review | **EXTEND（信息架构）** | 与 §十二 的“一条主线 + 三个辅助面”一致；需补“疑似薄弱（带教材页码）”“巩固入口”“阶段验证入口可选”。**不建议**在下一阶段之前改动导航。 |
| `workbench/vocabulary_learning_v01.py` | 独立的词汇学习实验台（Study→Recall→Result） | **KEEP（参考实现）** | 其交互（孩子主动确认 + 回忆三档）与证据模型一致，可作为线上实现的参考；但它是实验台，不应成为产品入口。 |
| P2-4 产物（结构/视觉/上下文/内容/证据包） | 157 活动 / 360 题 / 4,220 关系 / 360 份证据包 | **KEEP** | 直接作为 AI 批改的输入契约与教材定位来源。 |
| P2-3 音频证据链 | 54/54 CONFIRMED，`audio_scope=activity/section` | **KEEP** | 听力类证据（P2/P5 干预）依赖它定位“重听哪一段”。 |
| 专项独立题库 / 阶段测试页面 / 家长看板 | 不存在 | **DEFER** | 按 §八、§九 的设计，先做数据结构与离线验证，再考虑产品化。 |

---

## 2. 三个 REBUILD 的具体含义

### 2.1 掌握判定算法（最严重）
现状：`_upsert_mastery()` 只做 `evidence_count += 1`、`correct_count += 1`，**从不写入 learning/familiar/stable**。也就是说，当前产品里“等级”是**声明出来的空壳**。
风险：如果下一阶段简单加一句“correct_count ≥ 3 → stable”，就会得到“做过三次就对”的假掌握。
建议：按 `learning_model_v1.json` 的 `stable.required_evidence` 实现，输入必须包含 **任务类型集合、自然日集合、是否无提示、最近 3 次结果序列、未处理当前错误**。

### 2.2 诊断 → 巩固链路（完全缺失）
现状：`/review` 只展示池，没有任何“为什么/怎么办”。
建议：最小实现 = 池里的每条内容附“教材页码 + 可选干预类型（来自 intervention_model）+ 孩子点击才进入”；**不做自动进入**。

### 2.3 AI 批改链路（未接入）
现状：`ai_grading.analyze_short_answer()` 是本地关键词规则；练习提交只写 record。
建议：以 `textbook_evidence_map_v1.json` 的单题证据包为输入，定义 §六 的 7 项输出契约；先做 **mock 校验器**（校验字段完整性与“证据不足不得下结论”的规则），不接真实 API。

---

## 3. 数据安全与边界（本轮实测）

| 项目 | 结果 |
| --- | --- |
| `learning.db` | 未写入（本任务只读；库内为真实使用数据） |
| contentpack v5 | 未修改 |
| P2-4 产物 | 未修改（只读引用） |
| Android / Web UI | 未修改 |
| 真实 AI 调用 | 0 |
| 新产生学习记录 | 0 |

---

## 4. 下一阶段开发顺序建议（按依赖关系）

1. **证据维度落地**（不改表语义，先加字段/派生视图）：任务类型、是否无提示、来源、强度。
2. **教材证据包接线**：练习 → `textbook_evidence_map_v1` 单题包 → 批改输入（离线 mock）。
3. **最小诊断-巩固闭环**：阈值聚合 → “疑似”列表（带教材页码）→ 孩子点击 → 教材优先干预。
4. **阶段验证数据结构**（可先无 UI，用现有练习页复用）：会话标记 + 结果只进证据层。
5. 上述完成并经过真实孩子使用验证后，再讨论 UI 与专项入口产品化。

**明确不在下一阶段做**：题库、积分/排名/打卡、家长系统、AI 自动学习计划、教材外内容生成。
