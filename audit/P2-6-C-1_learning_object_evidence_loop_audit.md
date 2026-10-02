# P2-6-C-1 学习对象映射与证据闭环只读审计报告

> 严格只读审计。本轮**未修改任何代码 / 数据库 / 教材数据 / 规范 / UI / 测试**，未调用 AI。
> 新增文件仅本报告与其 JSON 摘要。

- 审计时间：2026-09-13
- 项目根目录：`D:\ZhixueEnglish`
- 最高规范：`初中英语AI辅助学习系统_最高指导原则与开发规范_V1.2.docx`（+ `docs/…V1.2.md`）
- 上游基线：P2-6-A（PASS / 已归档）、P2-6-B（PASS / FROZEN / 已归档，363 PASS）

---

## 1. 审计结论

**PASS WITH GAPS**

“Learning Object 映射 + 证据闭环”的**设计基础成立**（不存在根本性语义冲突），但**跨任务的统一学习对象尚未成立**：当前所有判定都停留在 `item_id` 粒度，且巩固动作记录缺失，因此尚不具备直接实施条件，需先补设计（见 §22–§25）。

## 2. 执行环境

| 项目 | 值 |
| --- | --- |
| 项目根 | `D:\ZhixueEnglish` |
| 版本控制 | **无 Git 仓库**（`git` 命令不可用，无法给出 git status） |
| 正式数据库 | `D:\ZhixueEnglish\structured\learning\learning.db`（任务书所写 `database\learning.db` **不存在**，以项目真实引用为准） |
| 教材库 | `structured\contentpack\v5\FLTRP-EN-7A-2022CUR.sqlite`（只读） |
| 规范版本 | V1.0 / V1.1 / **V1.2（当前正式）** 三版并存，均只读 |
| 测试基线 | learning 89 + workbench 50 + web 224 = **363 PASS / 0 FAIL / 0 SKIP** |

## 3. 只读声明

本轮仅执行：列目录、读文件、`rg` 搜索、`sqlite3 mode=ro` 查询、运行现有测试。
未执行：任何 INSERT/UPDATE/DELETE/DDL、任何文件写入（除本报告）、任何 AI/网络调用、任何依赖安装、任何 UI/服务/规范改动。
测试运行前后 `learning.db` 的 SHA256 与 mtime 完全一致（§27）。

---

## 4. 项目结构（与 P2-6-C 直接相关）

**Learning Object / Evidence / Diagnosis / Intervention 相关文件**

| 层 | 文件 |
| --- | --- |
| 设计（P2-5） | `structured/learning/learning_model_v1.json`、`learning_evidence_model_v1.json`、`learning_flow_v1.json`、`intervention_model_v1.json`、`stage_assessment_model_v1.json`、`ai_role_model_v1.json` |
| 参数（P2-6-B） | `structured/learning/mastery_rules_v1.json` |
| 服务（P2-6-B） | `learning/evidence_service.py`、`mastery_service.py`、`diagnosis_service.py`、`intervention_service.py` |
| 冻结服务 | `learning/learning_service.py`、`session_service.py`、`activity_service.py`、`behavior_service.py`、`vocabulary_service.py`、`resource_pool_service.py` |
| Web 接线 | `web/flow.py`、`web/app.py`、`web/ui.py` |
| 教材事实 | `structured/contentpack/v5/*.sqlite`、`structured/textbook/*_v2.json`、`structured/exercises/exercise_catalog_v3.json`、`exercise_question_relations_v3.json`、`structured/audio/*_v3.json` |
| 审计 | `audit/P2-6-A_*.md/json`、`audit/P2-6-B_*.md/json`、`audit/P2-6-C-1_*`（本次） |

**可能需后续改造的文件（仅建议，本轮不改）**：`learning/evidence_service.py`（聚集粒度）、`mastery_service.py`、`diagnosis_service.py`、`intervention_service.py`、`web/flow.py`、`web/ui.py`。

---

## 5. V1.2 规范核对（引用原文）

**Learning Object（二十二·3）**

> “教材学习对象包括：单词、短语、句型、语法点、听力任务、阅读文本、写作任务等。”
> “Activity 是任务容器，不等于学习对象。”
> “Exercise（含 Question）是产生学习证据的任务，不等于学习对象。”
> “三层不得混用：学习对象用于聚合与诊断，Activity 用于组织教材任务，Exercise 用于产生证据。”

**学过 / 掌握较稳定（二十二·4）**

> “‘学过’只表示：孩子至少主动发生过一次学习行为。它是事实记录，不等于学会、掌握、熟练或掌握较稳定。”
> “‘掌握较稳定’必须基于多维证据，而不是单次正确。”并列出 5 项工程初始参数（≥3 证据 / ≥2 任务类型 / ≥2 自然日 / 最近 3 次 ≥2 正确 / 无未处理当前错误），同时声明“**不是不可修改的教育真理**”。

**证据优先（二十二·5）**：只看过/只听过不能单独证明掌握；自评不能单独升级；同一学习时段重复操作不能无限增加独立证据权重；**一次错误不等于薄弱**。

**教材优先巩固（二十二·6）**：回看教材文本 → 重听官方音频 → 教材语法提示 → 对照教材范文 → 重做原教材题 → 跨 Section 教材练习；AI 辅助仅在三条件同时满足时考虑。

**AI 边界（二十二·7）**：AI 不得决定学什么/何时学、不得自动安排路径或推进、不得用分数排名等级评价、证据不足不得下确定性结论。

**孩子自主（二十二·2 / 二十二·10）**：自主权不等于取消结构；“证据聚合”与“孩子决定”必须显式存在。

**规范未定义、属工程参数的**：`suspected_weak` 的具体阈值（P2-6-B 已写入 `mastery_rules_v1.json` 并标注可调整）——**本轮不修改**。

---

## 6. P2-6-A / P2-6-B 基线核对

| 项目 | 声明 | 本轮实测 |
| --- | --- | --- |
| P2-6-A 归档 | md/json 存在 | ✅ 存在（SHA 见 §28） |
| P2-6-B 归档 | md/json 存在、FROZEN | ✅ 存在（SHA 见 §28） |
| 测试基线 | 363 PASS / 0 FAIL / 0 SKIP | ✅ 一致（89 + 50 + 224） |
| 正式库未修改 | 是 | ✅ SHA `DBAB743BF6D8F0A3…`、mtime 09-12 23:15 未变 |
| AI 调用 | 0 | ✅ 本轮亦为 0 |
| V1.2 未修改 | 是 | ✅ SHA `6D3595CF7D83879A…` 未变 |
| contentpack 未修改 | 是 | ✅ SHA `ACEBC8C29CF5D11B…` 未变 |

**P2-6-B 的 4 个 Open Issue 复核结果**

1. **Learning Object 映射尚未建立** → **确认成立**（§7、§13、§17）；
2. **巩固动作记录缺失，导致“未处理当前错误”只是近似判断** → **确认成立**（§15、§19）；
3. **阈值需真实数据校准** → **确认成立**（真实数据仅 1 个自然日，无法校准）；
4. **冻结池与 diagnosis 是否统一未决** → **确认成立**（§20），两者目前语义互补、可共存。

---

## 7. Learning Object 审计

| 问题 | 结论 |
| --- | --- |
| V1.2 定义 | 见 §5：学习对象 = 单词/短语/句型/语法点/听力任务/阅读文本/写作任务；用于**聚合与诊断** |
| 边界 | 允许对应**多个 Activity**、**多个 Exercise**、产生**多条 Evidence**；V1.2 明确要求跨任务汇聚 |
| 跨 vocabulary / grammar / exercise | **V1.2 要求**（如“同一个词”的 study + recall + exercise 应汇聚）；**当前无法做到** |
| 层级 | Unit / Section（教材结构）→ item（资源条目）→ question（P2-4 派生）；**尚未有 Learning Object 层** |
| 最接近的层级 | **`item_id` 粒度**（mastery_state 与所有判定都用它） |
| 代码是否实现 | **完全没有**：`rg "learning_object|LearningObject"` 在 `learning/*.py`、`web/*.py`、`learning.db` 中**零命中**；概念只存在于设计文档与审计报告 |

**判定**：概念成立、实现为零；**不存在与 V1.2 的语义冲突**（属“设计成立但尚未实现”）。

## 8. Activity 审计

- **数据库无 activity 实体**：`learning.db` 无 `activity` 表；`contentpack.activity` 96 行仅为教材解析快照。
- `activity_type` 实际取值（`learning_service.ACTIVITY_TYPES`，11 个）：`recognize, read, understand, listen, repeat, spell, substitute, produce, review, study, practice`。
- **语义混用确认**：
  - `activity_service.resolve_activity()` 把 `activity_type` 取自 contentpack `learning_item.item_type`（= **资源类型**：vocabulary / phrase / sentence_pattern / exercise）；
  - 实际写入 `learning_record` 的值来自调用方：`web/app.py` 用 `TYPE_BEHAVIOR[e["type"]]`（= **行为类型**：listen/read/understand/recognize/…），`workbench` 用 `study`/`practice`。
  - 结论：**同一字段同时承载“资源类型”与“学习行为”两种语义**。
- Activity 是否被当成 Learning Object：**代码中没有**（无 LO 概念）；但 `mastery_state.item_id` 事实上把“练习条目”当作聚合单位，**在效果上接近“把 Exercise 当学习对象”**，与 V1.2 相悖（属实现层面，非规范冲突）。

## 9. Exercise / Question 审计

| 问题 | 结论 |
| --- | --- |
| exercise_catalog_v3 如何识别 question | 每道教材活动 = 1 个 exercise（157 条），携带 `questions[]`（P2-4 共 360 题） |
| 是否有 question_type | **有**，10 类：fill 45 / short_answer 34 / reflection 18 / speaking 16 / other 14 / choice 12 / match 9 / writing 7 / order 1 / judge 1 |
| 能否稳定作 task_type 依据 | **能**：`item_id` 与 `exercise_id` **157/157 完全一致**；`evidence_service.normalize_task_type()` 即用该字段 |
| exercise 的 item_id 能否唯一定位学习内容 | 能定位**教材题目**（unit/section/活动号/页码），**不等于**定位学习内容（见 §16 例 3） |
| question → textbook location | **存在**：`exercise_question_relations_v3.json`（360 题含 unit/section/textbook_page/related_text/related_vocabulary/related_audio） |
| question → Learning Object | **不存在**（无 LO 表/字段；仅有 `related_vocabulary` 词面，见 §17） |
| 缺什么 | 缺“question/activity → 学习对象”的**映射层**（键可从 `related_vocabulary` + 教材结构确定性派生） |

## 10. Vocabulary 审计

- 资源：`learning_item.item_type='vocabulary'` **288 条**；**词面唯一 288**（无重名、无多 item_id，实测 0 组重复）。
- 现有行为：`study`（我学好了/我看完了）与 `practice`（记得/有点模糊/忘了）；结果映射 `correct / partial / incorrect`。
- 教材锚点：unit（content 归属可解析，实测 4/7 条记录可归属；练习项为 None 属正常）+ **附录词表页 textbook p150 起**；逐词音频存在（P2-1-C1 manifest，含 start_ms/end_ms）。
- **关键断点**：词汇 `item_id` 与练习 `item_id` **零交集**（0 条词汇 id 出现在 exercise_catalog_v3）；`web/app.py` 提交练习时写入的是 **exercise 的 item_id**，因此：

```
同一个重点词（word "textbook"）
  vocabulary item_id  → study / recall 证据   （记在 V:xxxx）
  exercise item_id    → 教材练习题证据        （记在 X:xxxx）
                       ↑ 两者在 evidence 层永不相遇
```

**结论：词汇当前产生的证据无法与同一教材学习对象下的其他任务证据汇聚**——这是 P2-6-C 的核心断点（不是数据缺失，而是缺少映射层）。

## 11. Grammar 审计

- `learning_item.item_type` **无 grammar**；contentpack **无 grammar 表/字段**；learning.db 无 grammar 相关表。
- 存在的只有 **P2-4 的语法指针**：`textbook_content_relations_v2.json` 的 `grammar_in` 13 条（7 个语法点：nouns / numbers and articles / the simple present tense / the simple future tense / the there be structure / the basic sentence structures / adjectives + 6 条 `Phonetics in use`），每条含教材页（如 nouns → 附录 p130）与原文证据。
- **判定：Grammar 目前不具备 Learning Object 映射基础**（无资源对象、无任务、无证据）。本轮不创建。

---

## 12. Evidence 审计（`learning/evidence_service.py`）

| 问题 | 结论 |
| --- | --- |
| Evidence 是什么 | 由 `learning_record` **派生**的有效判断证据（不落库、无独立 id） |
| valid 定义 | `result ∈ {correct, incorrect, partial}` 且非 `study`（contact_only）且非“仅自评”（self_assessment_only）；其余进 `invalid` / `not_evaluable` |
| 去重规则 | `(learner_id, item_id, evidence_date, task_type)` 保留最新 1 条（`dedupe_keep=latest`），其余记入 `deduped_from` |
| LO 多任务场景是否合理 | **不合理（当前粒度下）**：键含 `item_id`，而同一 LO 的不同任务使用不同 `item_id` → 不同键 → 无法汇聚；同一 item 内重复则正确合并（实测 8 → 1） |
| evidence_id | **缺失**（可用 `source_record_id` 代替，但语义是记录而非证据） |
| learning_object_id | **缺失** |
| item_id / task_type / result / evidence_date | **可推导 / 已有**（task_type 由 item_id → catalog 派生） |
| source / session | source = record_id（已有）；session 需经 `task_id → learning_session.task_id` 间接关联（可推导） |
| parent / related evidence | **缺失**（无 E1 → E2 关系） |

## 13. Mastery 审计（`learning/mastery_service.py` + `mastery_rules_v1.json`）

- **计算粒度：`item_id`**（`mastery_state` 主键 = `(learner_id, item_id)`；服务签名 `evaluate(conn, learner_id, item_id)`）。
- **是否对应 Learning Object：否**（是“资源条目”粒度；词汇条目与练习条目分属不同 id）。
- 5 项条件在**算法上**已严格实现（并由 31 项测试固定）。
- **业务可达性（真实数据追溯）**：
  - `minimum_valid_evidence ≥3`：当前每对象最多 1 条独立证据 → 未达；
  - `minimum_task_types ≥2`：词汇只产生 `recall`（study 不计证据），练习 `question_type` 固定 → **同一 item 内几乎不可能达到 2 种**（`recognize` 等行为是唯一例外，但当前 APP 不产生）→ 未达；
  - `minimum_natural_days ≥2`：全部记录集中在 **2026-09-12** 一天 → 未达。
- 结论：**算法支持 ✅ / 业务数据可达 ❌**（两者必须分开判断；属设计缺口，非算法缺陷）。

## 14. Diagnosis 审计（`learning/diagnosis_service.py`）

- 输入：`latest valid result`（是否 incorrect）、`error_count`、`error_task_types`、`partial_count`、`partial_task_types`，外加冻结池事实 `pool_state`。
- **没有**：Learning Object、跨项 evidence history、consolidation history、handled/resolved 状态。
- 粒度：**item 级诊断**（`diagnose(conn, learner_id, item_id)`）；`list_attention()` 只是对多个 item 的循环。
- 与 LO 的关系：**无**。将来若引入 LO，diagnosis 需按 LO 汇聚，属后续设计（本轮不改）。

## 15. Intervention / Consolidation 审计

| 环节 | 现状 |
| --- | --- |
| Diagnosis | ✅ 存在（只读，item 级） |
| Suggestion | ✅ 存在（`intervention_service` 教材优先顺序；实测 Starter 练习项给出 reread_text / replay_audio / redo_exercise / cross_section_practice，`missing=[]`） |
| Child Click | ⚠️ **只有链接**：`web/ui.py` 渲染 `<a href="…">去看看</a>`，点击只是普通导航 |
| Intervention（正式 action record） | ❌ **不存在**（无记录写入；GET 页面本身不写库） |
| New Evidence | ✅ 孩子随后提交练习/回忆会产生新 record（但与旧 diagnosis **无关联字段**） |

**E1 → S1 → A1 → E2 关系：不存在。** 断点：① 无 action record；② `learning_record` 无 `session_id` / `parent` / `diagnosis_ref` 字段，新证据无法声明“为解决哪次诊断而来”。

## 16. 教材映射审计（三个代表对象）

**例 1 Vocabulary（重点词）**

```
word "textbook" → vocabulary item (V:0ABF…) → unit（Starter / Unit 1 / …）
   → 教材词表页 p150 → study ✅ / recall ✅
   → exercise：❌ 无映射（词 id 与练习 id 不通）
```

**例 2 Grammar（语法点）**

```
grammar point "the simple future tense" → 教材指针 p132（P2-4 grammar_in）
   → grammar resource ❌ 不存在 → grammar task ❌ 不存在 → evidence ❌ 不存在
```

**例 3 Exercise（练习题）**

```
exercise (X:D5F2794974F8) → question_type=fill → 教材位置 Unit 1 / DEVELOPING_IDEAS p22 ✅
   → 底层学习内容：related_vocabulary（词面）可用，但缺 LO id ❌
```

**可行性实测（决定性数据）**：`exercise_question_relations_v3` 的 `related_vocabulary` 共 **1,512 条引用 → 100% 唯一解析到 vocabulary item_id（0 未命中 / 0 歧义）**；词汇词面 288 条**无重名**。→ **确定性映射在数据层面可行**（本次最重要正面结论）。

## 17. 映射键审计

| 键 | 含义 | 稳定 | 唯一 | 跨任务共享 | 适合作 LO 主键 |
| --- | --- | --- | --- | --- | --- |
| `item_id` | 教材资源条目（词/短语/句型/练习） | ✅ | ✅ | ❌（词汇与练习不相通） | **否**（粒度错） |
| `word`（canonical_text） | 词面 | ✅ | ✅（288/288 唯一） | ✅ | **候选**（需设计确认语义） |
| `exercise_id` | 练习条目 id | ✅ | ✅（≡ `learning_item(exercise).item_id`，157/157） | ❌ | 否（是证据来源） |
| `question_id`（P2-4 派生 `Q:hash`） | 题目 | ✅（派生稳定） | ✅ | ❌ | 否 |
| `question_type` | 题型 | ✅ | — | ✅（跨题共享） | 否（是 task_type 来源） |
| `grammar_id` / `grammar_point` | — | ❌ 不存在 | — | — | 否 |
| `unit_id` / `section_id` | 教材结构 | ✅ | ✅ | ✅ | 否（过粗，是 LO 的归属而非 LO 本身） |
| `textbook_id` | 教材 | ✅ | ✅ | ✅ | 否 |
| `content_id` / `knowledge_id` / `resource_id` | 项目中均**不是独立字段**（`knowledge_id` 是 `resource_pool_service` 对 `item_id` 的别名） | — | — | — | 否 |

**结论**：当前**没有现成的 Learning Object ID**；但可从 `word`（+ 教材 unit/section 归属）**确定性派生**候选 LO id（例如 `LO:<textbook>:V:<word>`），无需新字段即可先做**派生映射层**。

## 18. 真实数据样本（全库 20 条记录，只读）

全部 20 条记录**都能定位到教材位置**（练习 6 条经 catalog、词汇 14 条经附录词表页）：

| record_id（前 8 位） | item_id（后 12 位） | activity | result | 类型 | Unit | Section | 教材页 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RADFD5F9 | V:7A89AA02D979 | study | done | vocabulary | Starter | WORDS_AND_EXPRESSIONS | 150 |
| RCE572B9 | V:7A89AA02D979 | study | done | vocabulary | Starter | W&E | 150 |
| RFEC12CC | V:7A89AA02D979 | study | done | vocabulary | Starter | W&E | 150 |
| RC6A4876 | V:EAB999ECEC5C | study | done | vocabulary | Starter | W&E | 150 |
| R767C45B | V:7AEAF8B1531D | study | done | vocabulary | Unit 6 | W&E | 150 |
| R3F95079 | V:C128262B65A0 | study | done | vocabulary | Unit 1 | W&E | 150 |
| R2EEA730 | V:C128262B65A0 | practice | correct | vocabulary | Unit 1 | W&E | 150 |
| R5639DD6 | X:852737996F71 | listen | done | exercise/short_answer | Unit 1 | DEVELOPING_IDEAS | 21 |
| R1ED7CBA | X:1C4143922B1C | listen | partial | exercise/choice | Starter | GET_READY | 5 |
| RC9B04B4 | V:EAB999ECEC5C | study | done | vocabulary | Starter | W&E | 150 |
| R76DC4A7 / RA3F000B / RC03FFFA / R868C9C9 / R36E510D / R6C8F508 | V:C128262B65A0 | study / practice | done / correct | vocabulary | Unit 1 | W&E | 150 |
| R1690092 | X:1C4143922B1C | listen | done | exercise/choice | Starter | GET_READY | 5 |
| RD4691FC / R3A40FCB / R1EF1D99 | X:D5F2794974F8 | listen | done | exercise/fill | Unit 1 | DEVELOPING_IDEAS | 22 |

- 覆盖 **3 个不同 Unit / Section**：Starter / GET_READY（p5）、Unit 1 / DEVELOPING_IDEAS（p21、p22）、Unit 1 词表（p150）+ Unit 6 词表（p150）。
- **能否可靠映射到候选 Learning Object？**
  - 映射到**教材位置**：**20 / 20（100%）**；
  - 映射到**候选 Learning Object**：**无法精确计算**——比例取决于 LO 语义选择（若 LO = 词/语法点，则 14 条词汇记录 + 练习中 `related_vocabulary` 覆盖部分可映射；若 LO = 活动/任务，则与 V1.2 冲突）。**按任务书要求，不做估算。**
  - 可确证的是：**练习证据要进入同一 LO，必须依赖 `related_vocabulary` 的确定性解析（已验证 100% 可解析）**，而不是现有 `item_id`。

## 19. “当前错误”闭环审计（情况 A–E）

定义现状：`latest valid judgment == incorrect ≈ 未处理当前错误`。

| 情况 | 场景 | 当前能否区分 | 说明 |
| --- | --- | --- | --- |
| A | 看到建议但**没有点击** | ❌ 不能 | 无 action record，与 B 完全不可区分 |
| B | 点击教材复习但**没有产生答题证据** | ❌ 不能 | 页面 GET 不写库；无 action record |
| C | 复习后重新答题**正确** | ✅ 能（近似） | 新证据使 latest=correct → 当前错误消失（但“是否因巩固而正确”不可知） |
| D | 复习后重新答题**仍错误** | ✅ 能（近似） | latest 仍 incorrect；但无法统计“巩固次数” |
| E | 多次复习后**暂时正确，后来又错误** | ⚠️ 部分 | 只看 latest 可判“再次错误”；但**无巩固历史**，无法评估巩固有效性 |

**结论**：当前定义只覆盖“最近一次判断”，**不能证明巩固是否发生、是否有效**。需要（仅提出需求，不实施）：`consolidation action record` + `evidence → diagnosis/action 关联字段`。

## 20. frozen pool 与 diagnosis 的关系

| 维度 | `resource_pool_service`（冻结） | `diagnosis_service`（P2-6-B） |
| --- | --- | --- |
| current_error | 最近一条**参与判断**记录为 incorrect（含孩子自评产生的结果） | 最近一条**有效判断证据**为 incorrect（排除仅自评） |
| current_weak | 最近一条 judged = partial | 不产生 current_weak；对应 `suspected_weak`（≥2 次错误或跨 2 类任务）与 `needs_textbook_review`（≥2 partial 且跨 2 类任务） |
| 输入 | 全部 judged 记录（含自评） | 有效判断证据（排除 done / skipped / 仅自评） |
| 输出语义 | “最近一次判断的事实” | “重复性/跨任务后的疑似结论” |
| 是否冲突 | **不冲突**：一个陈述事实、一个给出结论；`diagnosis` 额外暴露 `pool_state` 供 UI 区分 | |
| 可否共存 | **可以**（P2-6-B 已实现共存，UI 文案已区分） | |
| 长期是否统一 | **待设计**（本轮不决定） | |

---

## 21. AI 边界审计

- `rg` 确认：`learning/*.py`、`web/*.py`（业务）**无任何** openai / deepseek / requests / urllib / socket 调用点；`web/ai_grading.py` 仍是本地规则预检（`ai_status=not_connected`）。
- Learning Object 映射、evidence 聚合、mastery、diagnosis、教材优先建议**都应是确定性规则**，与 V1.2 的 AI 边界一致。
- **P2-6-C-1 不需要 AI。本次 AI 调用：0 次。**

## 22. 数据库需求判断

**结论：映射本身「不需要」DB 变化；巩固动作闭环「可能需要」最小新结构。**

**方案 A（无需 DB 变化）**：仅做 `item → 教材位置 → 候选 LO` 的**派生映射**。实测支持：`exercise_id ≡ item_id`（157/157）、`related_vocabulary` 唯一解析 100%、词汇词面唯一 288/288、unit/section 稳定。→ **可行**。

**方案 B（新增只读派生层，无 DB 迁移）**：在 A 之上增加 `learning_object_service.py`（只读派生 LO id 与归属），**不改 schema**。→ **推荐作为 P2-6-C 的最小落地形态**。

**方案 C（必须新增正式数据结构）**：仅在需要**持久化“巩固动作 / 处理状态”**时成立——因为“孩子点了没点、复习了没复习”**无法由现有数据派生**。最小范围建议（仅提出，不实施）：

```
新增 1 张独立表（例如 learner_action_log）：
  action_id / learner_id / item_id / learning_object_id? /
  action_type（reread_text | replay_audio | redo_exercise | …） /
  source_diagnosis_ref / created_at
或：复用 learning_record 语义扩展（不建议：会污染事实层语义）
```

影响评估：不影响冻结服务（新表只读写自身）；不影响 V1.2；对现有 363 测试的影响需在后续阶段评估（本阶段不评估、不实施）。

## 23. 实施前风险矩阵

| 风险 | 严重程度 | 当前状态 | 后果 | 是否必须先解决 |
| --- | --- | --- | --- | --- |
| Learning Object 无稳定映射 | **高** | 概念成立、实现为零；数据侧映射可行性已验证 | 证据无法跨任务汇聚，stable 不可达 | **是** |
| Evidence 无统一对象 | **高** | 去重键含 item_id | 同 LO 多任务被当作不同对象 | **是** |
| task_type 不可达（<2 种） | **高** | 词汇仅 recall；练习题型固定 | 五项条件之一几乎不可能满足 | **是** |
| 当前错误无法闭环 | **高** | 仅有 latest 近似判断 | 无法证明巩固发生 / 有效 | **是** |
| consolidation action 缺失 | **高** | 只有链接，无记录 | A / B 情况不可区分 | **是** |
| frozen pool / diagnosis 重叠 | 中 | 语义互补、可共存 | 长期口径分裂风险 | 否（可延后统一） |
| 教材映射不稳定 | **低** | 实测 20/20 可定位；1,512 引用 100% 解析 | — | 否 |
| 数据库模型不足 | 中 | 事实层够用；动作层不足 | 需最小新结构（仅动作层） | 是（若做闭环） |
| AI 越权风险 | **低** | 业务代码零 AI 调用 | — | 否 |
| 正式数据污染风险 | 中 | 现有 20 条含验收测试数据（`q1=test0`、AU11 三次） | 阈值校准会被污染 | 是（校准时须排除） |

## 24. 12 个核心问题逐项回答

1. **最合理的 Learning Object 候选实体**：**教材词汇条目（单词/短语/句型）** + 教材语法点（暂无对象）+ 教材任务类对象（听力任务 / 阅读文本 / 写作任务）；**不是** Activity，**不是** Exercise。
2. **是否存在稳定的 Learning Object ID**：**不存在**（无字段、无表、无服务）。
3. **能否通过确定性映射得到**：**能**——`related_vocabulary`（1,512 引用，100% 唯一解析）+ 词汇词面唯一（288/288）+ unit/section 稳定；可派生 `LO:<textbook>:<kind>:<key>`。
4. **一个 LO 能否对应多个 Activity**：**当前不能**（无映射）；**设计上应当能**（V1.2 明确）。
5. **一个 LO 能否对应多个 Exercise**：同上；数据侧具备可行性（题目 → 词面 → LO）。
6. **一个 LO 能否汇聚多条 Evidence**：**当前不能**（去重与判定都在 item 级）。
7. **mastery 是否已落到 LO 粒度**：**没有**（`mastery_state` 主键 = learner + item_id）。
8. **≥2 task types 在真实业务中是否可达**：**当前不可达**（词汇仅 recall；练习题型固定）——需 LO 汇聚后才可达。
9. **能否形成“错误 → 巩固 → 新证据 → 再诊断”闭环**：**不能**（缺 action record 与证据关联）。
10. **是否需要 consolidation action record**：**需要**（否则 A / B 不可区分、巩固有效性无法评估）。
11. **是否需要数据库迁移**：**映射不需要；巩固动作记录「可能需要」最小新结构**（方案 B + 局部方案 C）。
12. **下一步**：**先进入 P2-6-C-2（设计）**，把“LO 语义与派生键、evidence 聚集粒度、consolidation action 最小结构”设计清楚，再决定是否实施；**不需要重新设计整体模型**（无根本冲突）。

## 25. 后续建议（仅建议）

1. **P2-6-C-2 设计 LO 映射**：定义 LO 种类（词 / 短语 / 句型 / 语法点 / 听力任务 / 阅读文本 / 写作任务）与派生键规则；明确“词面 → item_id → LO id”的确定性算法与歧义处理（当前实测无歧义）。
2. **设计 evidence 聚集粒度**：由 item 级改为 LO 级（去重键改为 `(learner, LO, 自然日, task_type)`），同时保留 item 级明细以便溯源。
3. **设计 consolidation action 最小结构**（含 `source_diagnosis_ref`），并明确“只由孩子点击产生”。
4. **明确 frozen pool 与 diagnosis 的长期关系**（建议保持“事实层 + 结论层”，不合并语义）。
5. **阈值校准**：待真实、非测试数据充足（≥2 自然日）后校准 `mastery_rules_v1.json`；校准时排除验收测试记录。
6. Grammar 若要成为 LO，需先有 grammar 资源对象（当前仅有指针），属独立设计课题。

## 26. 保护范围（本轮确认未触碰）

规范 V1.0 / V1.1 / V1.2；contentpack 与 P2-4 教材数据（含 exercise_catalog_v3、question relations、textbook / audio v2 / v3）；learning.db；P2-5 / P2-5-C 成果；P2-6-A / P2-6-B 代码、测试、参数与归档；六个 frozen services；Web / Android。

## 27. 测试结果

| 套件 | 结果 |
| --- | --- |
| learning | 89 PASS / 0 FAIL / 0 SKIP |
| workbench | 50 PASS / 0 FAIL / 0 SKIP |
| web | 224 PASS / 0 FAIL / 0 SKIP |
| **合计** | **363 PASS / 0 FAIL / 0 SKIP** |

- 审计前 / 审计后：`learning.db` SHA256 `DBAB743BF6D8F0A3…` **一致**，mtime `2026-09-12 23:15:13` **一致**。
- 本轮未新增、未修改任何测试文件；未产生任何正式学习记录。

## 28. 关键文件 SHA256

| 文件 | SHA256 |
| --- | --- |
| 规范 V1.2 docx | `6D3595CF7D83879ADF3E6452C5E5A74C5300E89265DE1B4F2FA8A1EBDBB861A9` |
| 规范 V1.2 md | `83D39D93EB9255BF6C229FB195A387B1E31C5F8DAB846C86B63D7229079EF88F` |
| P2-6-A audit md | `0FB87839CC09BA8D27BB7D0E980838DA0E9BE0D2DA2BF4325B6CBC6DB5ADAE5B` |
| P2-6-A audit json | `E83CFFEA959296E9A47D73BBF614FEAA1BB35D3334803BDEAC00C551380F5D0D` |
| P2-6-B impl md | `C79852740B6C24563953CE7A37DA801660B0AA3C49BABAF8946FB947BA7AF02C` |
| P2-6-B impl json | `2C51C276310C59A5DC91C6E1E13C46E643149D571C36B47A6B44B9F39F7BCD04` |
| mastery_rules_v1.json | `E7EC99DB55DDCF04BA7C8B5393160ED4C6C99DF2CE1795FB028A5327CFF85D12` |
| evidence_service.py | `864536DEF937E4B39A5C63BDB9956FF6CD090FEC0E47F2BE96166A400AD34F07` |
| mastery_service.py | `8F7372A07E905EF46A7B75DEF6CCE16FF2ED7E9BB5DE490BB6C1081472EA4FDF` |
| diagnosis_service.py | `14CD114724982C7D712160D402C18461AB870EC8B54E644954011B7154612028` |
| intervention_service.py | `4E12CB1AAF429C819AE6014A18F3B13AFB70367121E951CA382DAD7619D5B621` |
| learning.db | `DBAB743BF6D8F0A3832E599CBD5DD2267F008FD9FB3903BACEA93780A466D633` |
| contentpack v5 | `ACEBC8C29CF5D11BAB50BF7962FBEE5DE42CD9CFC7FE48AB6316699D265E1A3F` |
| exercise_catalog_v3.json | `EB2D8E7BD0BD71404FBE2B3C010289158CCB8A12F4DF031ED7444B4BE9570A39` |
| exercise_question_relations_v3.json | `D5A2632D267719449AABA3697AF49675A7E1EBF68E3348A90B75732A6B88A221` |

## 29. 最终结论

**PASS WITH GAPS**（基础成立，存在实施前必须设计清楚的问题；**无需重新设计整体模型**）。

本轮完成审计后**立即停止**，不进入 P2-6-C-2 / P2-6-D，不做任何实施。
