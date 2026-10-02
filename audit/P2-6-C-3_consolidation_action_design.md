# P2-6-C-3 Consolidation Action 与“错误 → 巩固 → 新证据 → 再诊断”闭环设计

> **只读设计阶段。** 本轮未修改任何代码 / 数据库 / 教材 / 规范 / 测试 / Android，未调用 AI。
> 输入：P2-6-C-1（只读审计）、P2-6-C-2（LO 设计）、P2-6-A/B（掌握与干预实现）、V1.2、`mastery_rules_v1.json`。
> 本阶段不重复 C-1/C-2 已完成的分析，只在此基础上定义 Consolidation Action 语义、生命周期与闭环关系。

- 设计时间：2026-09-13
- 项目：`D:\ZhixueEnglish`
- 产出：本文件 + `P2-6-C-3_consolidation_action_design.json`

---

## 1. 结论

**PASS_WITH_GAPS**

Consolidation Action 的语义、最小生命周期、与 Evidence / LO / Diagnosis 的关系、Current Error 的 8 种情形与再诊断路径、持久化边界均已定义清楚，**可以交给 P2-6-C-4 做综合设计评审**；遗留项为“是否需要独立持久化结构”的最终决策与若干产品口径（详见 §20）。

## 2. 本阶段范围

只设计：① Action 定义与类型；② 最小生命周期；③ E1→D1→S1→A1→E2→D2 关系链；④ Current / Historical Error 语义；⑤ Action–Evidence–LO 关系；⑥ Re-diagnosis 逻辑；⑦ 孩子自主权约束；⑧ 持久化 / DB 判断；⑨ 与冻结服务边界；⑩ V1.2 同步判断；⑪ 验收标准与边界案例。

不设计：UI 形态、数据库实施、算法实现、阶段验证、专项学习、AI 批改内容。

## 3. 已阅读资料

`audit/P2-6-C-1_*.md/json`、`audit/P2-6-C-2_*.md/json`、V1.2（docx + md）、`audit/P2-6-B_*.md/json`、`learning/evidence_service.py`、`mastery_service.py`、`diagnosis_service.py`、`intervention_service.py`、`structured/learning/mastery_rules_v1.json`。

## 4. 当前闭环现状（C-1/C-2 结论，不再重审）

| 环节 | 现状 |
| --- | --- |
| Evidence | ✅ 只读派生（有效证据 + 去重，item 级） |
| Diagnosis | ✅ item 级（current_error / suspected_weak / needs_textbook_review） |
| Suggestion | ✅ 教材优先建议（只读，含教材定位） |
| Child click | ⚠️ 只有普通链接（无记录） |
| Consolidation Action | ❌ 完全不存在 |
| New Evidence | ✅ 会产生新 record，但与诊断无关联 |
| Re-diagnosis | ⚠️ 只能看 latest，无法表达“为哪次诊断而巩固” |
| Learning Object | ❌ 未实现（C-2 已设计：只读派生 + 六类叶 LO，映射覆盖 89/157） |

---

## 5. Consolidation Action 定义

> **Consolidation Action（巩固行动）**：孩子**主动开始并执行**的、指向某个教材巩固目标（教材文本 / 官方音频 / 语法提示 / 范文 / 教材原题 / 跨板块教材练习）的一次最小学习行为单元；它有明确的 `action_type`、教材目标、起止时间与“完成”判据。

**必须严格区分的六个概念（同一链条上的不同环节）**

| 概念 | 含义 | 是否持久化 | 能否改变 Current Error |
| --- | --- | --- | --- |
| `suggestion_card_rendered` | 建议卡片被展示 | ❌ 不持久化（派生对象） | 不能 |
| `child_clicked` | 孩子点击“去看看” | ❌ 不单独持久化（行为入口，不是状态） | 不能 |
| `action_started` | 孩子真正进入目标教材资源并开始执行 | ✅ 是（Action 起点） | 不能 |
| `action_completed` | 达成该 `action_type` 的最小完成判据 | ✅ 是（Action 终点） | **不能**（只有新证据才能） |
| `new_evidence` | 由学习行为产生的**有效判断证据** | ✅ 派生自 learning_record | **能** |
| `rediagnosis` | 基于新证据重新判定 | ❌ 派生 | — |

**核心结论**：`建议展示 ≠ 孩子点击 ≠ 开始巩固 ≠ 完成巩固 ≠ 错误已解决`。**只有新的有效判断证据才能改变 Current Error。**

## 6. Action 类型（最小模型）

V1.2 二十二·6 的六项教材优先顺序，逐项判断：

| V1.2 条目 | 是否可作 `action_type` | 说明 | 对应 `target_resource` |
| --- | --- | --- | --- |
| reread_text | ✅ 可以 | 孩子行为 | 教材文本（unit/section/page 或文本块） |
| replay_audio | ✅ 可以 | 孩子行为 | 教材官方音频（audio_id / 活动） |
| grammar_pointer | ✅ 可以 | 孩子行为 | 教材语法提示页（topic + 附录页） |
| model_text_review | ✅ 可以 | 孩子行为 | 教材范文（Reading for writing 文本） |
| redo_exercise | ✅ 可以 | 孩子行为 | 单道教材题（exercise_id） |
| cross_section_practice | ✅ 可以 | 孩子行为 | 教材题集合（unit/section 范围） |

**设计决定**

1. **`action_type` 与 `target_resource` 必须分离**：同一类型可指向不同教材目标（reread_text 可指课文或词表），同一目标可被不同类型使用（同一篇课文既可 reread_text 也可 grammar_pointer）。
2. **不设通用兜底类型**：无法归入这六类的行为**不构成 Action**（记 `unmapped`，不记录、不闭环）——避免制造 V1.2 未定义的 action 类型。
3. **不新增类型**：本阶段不引入 V1.2 未列出的巩固类型（如"AI 出题""看视频"等一律不做）。
4. **类型集合固定为 6 个**，与 C-2 的 `intervention.textbook_first_order` 完全一致（同源，不新增映射表）。

## 7. Action 生命周期（最小）

```
   （建议展示 suggestion_card_rendered —— 不产生记录）
              │ 孩子点击
              ▼
         [进入目标资源]
              │ 真正开始执行
              ▼
        started ────────────────► completed
           │                        （达成最小完成判据）
           │ 中途退出 / 主动取消
           ▼
        abandoned
```

**必需状态只有 3 个：`started → completed | abandoned`。**

回答任务书 §六 的 10 个问题：

1. **suggestion-only 是否产生 Action 记录？** → **不产生**（建议是派生对象，持久化会造成与规则版本漂移）。
2. **child_clicked 是否产生 Action 记录？** → **不单独产生**；点击只是进入资源的入口，只有当孩子真正开始执行时才创建 `started`。
3. **clicked 但没有真正开始，是什么状态？** → **无状态**（不创建 Action）；因其不能改变 Current Error，记录它只会制造噪声。
4. **started 后退出，是什么状态？** → `abandoned`。
5. **completed 的最低定义？** → 达成**该 `action_type` 的资源类型最小行为确认**：
   - `reread_text` / `grammar_pointer` / `model_text_review`：孩子在该教材资源上完成一次学习行为确认（复用既有 `study/done` 语义，不发明新语义）；
   - `replay_audio`：孩子完整听完目标教材音频（复用既有播放语义）；
   - `redo_exercise` / `cross_section_practice`：孩子**提交**至少 1 道教材题（产生 `learning_record`）。
6. **completed 是否必须产生新 Evidence？** → **不必须**。例如 `reread_text` 完成只产生 `study/done`（按 V1.2 属"接触"，不是有效判断证据）。
7. **completed 但没有新 Evidence 如何处理？** → Action 记为 completed，**Current Error 保持**（详见 §9 情况 4）。
8. **abandoned 是否影响 mastery？** → **不影响**（不产生证据、不改变状态、不产生负面结论）。
9. **cancelled 是否影响 mastery？** → **不影响**，且**不需要与 abandoned 区分**（教育语义相同：未完成）。
10. **是否需要 interrupted？** → **不需要**；若将来出现"系统级中断"（如崩溃）且需要区分，再作为 `abandoned.reason` 的取值考虑，不新增状态。

## 8. E1 → D1 → S1 → A1 → E2 → D2

| 环节 | 定义 | 持久化判断 | 理由 |
| --- | --- | --- | --- |
| **E1** 原始证据 | 由 `learning_record` 派生的有效判断证据（LO 级聚合见 C-2） | 事实层已有（record），证据为派生 | 事实即证据来源 |
| **D1** 诊断 | 基于该 LO 证据集合的当前诊断（current_error / suspected_weak / needs_textbook_review） | **不持久化**（派生） | 规则与阈值将来会调整，落库会产生与 `mastery_rules_v1` 漂移 |
| **S1** 建议 | 由 D1 + `intervention_model` 派生的教材优先建议（含教材定位） | **不持久化**（派生） | 同上；且建议是"展示物"，非事实 |
| **A1** 巩固行动 | 孩子主动执行的巩固行为 | **需要持久化**（唯一无法派生的事实） | "孩子做过什么"不可由 record 推断 |
| **E2** 新证据 | A1 之后产生的有效判断证据 | 派生自新的 `learning_record` | 与 E1 同等地位 |
| **D2** 再诊断 | 基于 E1+E2（同 LO）重新判定 | **不持久化**（派生） | 与 D1 同一逻辑 |

**关系要求**

1. **D1 是否必须持久化？** 否；若需追溯"当时依据哪次诊断"，用**派生指纹** `diagnosis_key = hash(LO + evidence_ids + rules_version)`（字符串，作为 Action 的 provenance 可选字段，不落库为独立对象）。
2. **S1 是否必须持久化？** 否（同 D1）；如需展示追溯，同样用 `suggestion_key`（派生字符串）。
3. **A1 是否必须持久化？** **是**。
4. **E1/E2 如何关联？** 通过 **LO**（C-2 设计）：E1 → LO_x，A1 归属 LO_x，E2（可能来自不同 item）→ 同一 LO_x；Action 记录 `related_evidence_ids[]` 指向 A1 之后产生的证据。
5. **一个 Action 产生 0 / 1 / 多个 Evidence？** → **0、1、多个都允许**（见 §11）。
6. **一个 Evidence 关联多个 LO？** → **允许**（C-2 §10：一条证据 + 多引用，不复制证据）。
7. **一个 Action 涉及多个 LO？** → **允许**（`cross_section_practice` 天然覆盖多个 LO；用 `target_lo_ids[]` 记录**意图**，实际归属以 Evidence 的 LO 引用（**事实**）为准）。
8. **是否必须保留 provenance？** → **必须**：Action 保留 `target_resource`（教材定位）、`session_ids`/`record_ids`、时间；Evidence 保留 `record_id/item_id`（C-2 已定）。

**原则**：意图（Action 想覆盖哪些 LO）与事实（证据实际归属哪些 LO）**分开记录**、**不得互相覆盖**。

## 9. Current Error 语义（8 种情况）

定义：

- **Historical Error（历史错误）**：`learning_record` 中所有 `result = incorrect` 的记录。**永久保留、不删除、不修改**，不因后来答对或完成巩固而消失。
- **Current Error（当前错误）**：**行动状态**，定义 = 该 **LO 最近一条有效判断证据为 `incorrect`**（P2-6-B 现有近似规则的 LO 级版本），且**未被后续有效判断证据取代**。
- **单一真相原则**：Current Error 只由**有效判断证据**推导；**任务完成、点击、Action 完成都不参与该判定**。

| # | 情况 | Current Error | 说明 |
| --- | --- | --- | --- |
| 1 | 出现错误，系统显示建议，**未点击** | **保持** | 无新证据；Action 不存在 |
| 2 | **点击**建议但未开始 | **保持** | 点击不产生 Action、不产生证据 |
| 3 | 开始巩固后**中途退出**（abandoned） | **保持** | Action 存在但无证据；不影响 mastery |
| 4 | **完成巩固但没有新有效证据** | **保持**（不得视为已解决） | completed ≠ resolved；典型于 reread_text/replay_audio |
| 5 | 完成巩固并产生新证据 = **incorrect** | **保持**（且错误计数 +1） | 可能升级为 `suspected_weak`（≥2 次错误或跨 ≥2 任务类型） |
| 6 | 完成巩固并产生新证据 = **partial** | **退出 current_error**，但**进入"需要再看"语义** | latest 非 incorrect；对应 C-2 的 partial 路径（`needs_textbook_review` / 当前薄弱） |
| 7 | 完成巩固并产生新证据 = **correct** | **退出 current_error**，但**不等于掌握** | 需按 `mastery_rules_v1` 五项条件判定；证据不足时只能是"看起来会了"，不得判 stable |
| 8 | 后来**再次出现错误** | **重新进入 current_error** | latest=incorrect；历史错误始终保留 |

**核心原则（重申）**："建议展示过""孩子点击过""孩子完成过一次巩固"**都不等价于**"当前错误已解决"。

## 10. Historical Error 语义

- 永久保留（append-only），是**事实**；
- 不因答对、不因巩固完成、不因 Action 完成而删除或修改；
- 参与 `mastery_rules_v1` 的"最近 3 次"与错误计数（作为历史证据）；
- 历史错误多而最近正确 → 由"最近 3 次 ≥2 正确"等条件决定状态，**不得用历史错误总数直接判薄弱**（V1.2：一次错误 ≠ 薄弱，反向亦然：历史错误不自动等于现在薄弱）。

## 11. Action 与 Evidence 的数量关系

| 关系 | 允许 | 例 | 设计处理 |
| --- | --- | --- | --- |
| 0 Evidence | ✅ | 打开课文后退出（abandoned）；或完成 reread_text 但只产生 study/done | Action 记录 completed/abandoned；`related_evidence_ids` 为空 |
| 1 Evidence | ✅ | redo_exercise 提交一次 | 回填该 evidence 的派生 id 列表 |
| 多个 Evidence | ✅ | cross_section_practice 连续做 5 题 | `related_evidence_ids[]` 全部回填 |

**绑定方式的推荐（最小且可扩展）**：

- Action **不直接绑定单条 `evidence_id`**（会限制"多证据"场景）；
- 采用 **`related_evidence_ids[]` 派生引用 + 事实侧 provenance**：
  - Action 侧记录 `session_ids[]`（若走会话）与时间窗；
  - Evidence 侧保留 `record_id / item_id / learning_object_ids[]`（C-2）；
  - 二者通过"时间窗 + 会话 + 目标资源"匹配，**不复制证据**。
- 理由：Action 是"孩子做了什么"，Evidence 是"产生了什么判断"；两者多对多，用引用数组表达最稳定，也便于将来扩展到 grammar/text/listening。

## 12. LO 与 Action / Evidence 关系

```
LO（C-2 定义的叶学习对象）
 ├── Evidence E1（来自 item A，引用 LO）
 ├── Action   A1（孩子主动巩固，target_lo_ids 记录意图）
 └── Evidence E2（来自 item B，引用同一 LO）
```

- **一个 Evidence 可以引用多个 LO**（C-2 已定；不复制证据，不制造 E2-A / E2-B）；
- **一个 Action 可以涉及多个 LO**（意图层 `target_lo_ids[]`）；
- **Action 不改变 LO 的掌握状态**（只有证据能）；Action 完成只影响"是否已尝试"这一**辅助展示信息**；
- **无法映射到 LO 的内容一律 `unmapped`**：不强行绑定（Edge 15），也不为凑闭环而归属。

---

## 13. Re-diagnosis 设计

解决 C-1 遗留问题："诊断过于依赖 latest item evidence"。

**推荐：LO 级、三段式判定（不引入新阈值）**

| 判定 | 输入 | 规则来源 |
| --- | --- | --- |
| Current Error | 该 LO **最近一条有效判断证据** | P2-6-B `diagnosis_service`（LO 级版本） |
| Suspected Weak | 该 LO 的**错误次数 / 错误覆盖的任务类型数** | P2-6-B 阈值（≥2 次 或 跨 ≥2 类型） |
| Mastery State | 该 LO 的**全部有效证据集合**（去重后） | `mastery_rules_v1.json` 五项条件（阈值不变） |

**对四种候选输入方式的判断（必须选一个）**

| 候选 | 判断 |
| --- | --- |
| 只看最新证据 | ❌ 不采用（会丢失多维条件，且单次正确≠掌握） |
| 看 LO 全部历史证据 | ⚠️ 只用于**计数类条件**（证据条数、任务类型数、自然日数） |
| 看时间窗口 | ✅ 采用（"最近 3 次"即窗口） |
| 当前错误 + 最近有效证据 | ✅ 采用（current_error 判定） |
| 使用 `mastery_rules_v1` | ✅ **最终状态判定**（五项条件） |

**推荐组合**：`current_error（最新一条）` + `最近窗口（最近 3 次）` + `全量计数（条数/类型/自然日）` —— 这正是 `mastery_rules_v1` 的形态，因此**无需修改参数**。

**跨 item 的 LO 链（示例，来自 C-2 设计模型）**

```
E1: Vocabulary "important" 的 recall 错误
        → LO:VOCAB:important（当前错误）
D1 → S1: 建议 reread_text（教材词表页 / 课文中出现该词的句子）
A1: 孩子主动回到教材文本并完成学习确认（completed）
E2: 另一道教材练习（不同 item_id）中再次涉及 important，答对
        → 同一 LO:VOCAB:important
D2: current_error 退出；掌握状态按五项条件重算（证据仍可能不足 → 非 stable）
```

**规则要点**

- `item_id` **保留**（provenance）；LO ID 仅作聚合层；
- **新证据可以来自不同 item**；只要映射到同一 LO 就不算"另起一条链"；
- 新证据**不因 item 不同而断开 LO 链**；
- 若新证据无法映射到任何 LO → `unmapped`，**不参与** D2（不得强行绑定，Edge 15）。

## 14. Child Autonomy（逐条核对 V1.2）

| # | 约束 | 设计是否满足 | 说明 |
| --- | --- | --- | --- |
| 1 | Suggestion ≠ Command | ✅ | 建议只展示，不带任何强制语义 |
| 2 | Suggestion ≠ Action | ✅ | 展示不创建 Action |
| 3 | 展示建议不自动创建 Action | ✅ | Action 仅在 `started` 时创建 |
| 4 | 点击建议 ≠ 完成学习 | ✅ | 点击不产生 Action、不产生证据 |
| 5 | 系统不得自动开始学习 | ✅ | 无自动进入路径 |
| 6 | 系统不得自动播放音频 | ✅ | 音频只有孩子点击才播放（现有实现即如此） |
| 7 | 系统不得自动跳转 | ✅ | 建议只给链接 |
| 8 | 系统不得自动进入下一项 | ✅ | 无自动推进 |
| 9 | 不得因 current_error 强制巩固 | ✅ | Current Error 只影响展示的可选入口 |
| 10 | Action 完成不自动提升 mastery | ✅ | 只有证据参与判定 |
| 11 | Abandoned / cancelled 不产生负面结论 | ✅ | 不产生证据、不改变状态 |
| 12 | AI 不决定孩子是否继续 | ✅ | 本设计 AI 调用 0 |
| 13 | AI 不决定孩子是否必须巩固 | ✅ | 无 AI 参与闭环判定 |

## 15. Persistence / DB 判断

| 方案 | 可行性 | 结论 |
| --- | --- | --- |
| **方案 A：不建独立表，全部由 LearningRecord + Diagnosis + Evidence 推导** | **不可行** | "孩子开始/完成了一次巩固行为"**无法从 learning_record 派生**：点击、进入文本、听音频都不产生记录；`redo_exercise` 虽产生 record，但无法区分"它是为巩固而来"还是普通练习。若强行把 Action 定义为"产生 record 的行为"，则 Action 退化为 Evidence 的同义词，失去闭环意义。 |
| **方案 B：新增最小独立 Consolidation Action 持久化结构** | **推荐** | 唯一无法派生的事实（孩子主动做过什么）需要落库；结构最小化，不与冻结表耦合。 |

**推荐结构（概念字段；本阶段不执行 DDL）**

| 字段 | 必要性 | 说明 |
| --- | --- | --- |
| `action_id` | ✅ 必须 | 主键；可用确定性 id（learner + type + target + started_at 派生） |
| `learner_id` | ✅ 必须 | 归属 |
| `action_type` | ✅ 必须 | 6 值之一（§6） |
| `target_resource` | ✅ 必须 | 教材定位（kind + unit/section/activity_no/page/audio_id/exercise_id）；**不得为空**（否则不是 Action） |
| `target_lo_ids[]` | ⚠️ 可选（意图） | `cross_section_practice` 等可能覆盖多 LO；允许为空 |
| `status` | ✅ 必须 | `started / completed / abandoned` |
| `started_at` / `ended_at` | ✅ 必须 | 生命周期时间 |
| `related_evidence_ids[]` | ✅ 必须（可为空数组） | 完成后回填；0/1/多个均允许 |
| `source_ref` | ⚠️ 可选 | 派生指纹（`diagnosis_key` / `suggestion_key`），仅用于展示追溯 |
| `created_at` | ✅ 必须 | 记录创建时间 |
| **`suggestion_id`** | ❌ **不必要** | 建议不持久化；持久化会产生与规则版本漂移 |
| **`diagnosis_id`** | ❌ **不必要** | 诊断不持久化；如需追溯用派生字符串 `source_ref` |

**DB 判断**：**可能需要**（仅 1 张新表；映射与证据仍为只读派生）。**本轮不创建、不迁移。**

## 16. 与冻结服务边界

- 冻结对象（不得修改）：`learning_service.py`、`session_service.py`、`activity_service.py`、`behavior_service.py`、`vocabulary_service.py`、`resource_pool_service.py`、`learning.db`、contentpack、P2-4、P2-5、V1.2、Android。
- **实现路径：新增独立最小层**（例如 `learning/consolidation_service.py` + 可选 `consolidation_action` 表），**不扩展现有冻结服务的职责**；
- Evidence 继续由 `learning_record` 派生（现有 `evidence_service`，将来按 C-2 扩展为 LO 级聚合）；
- Action 的写入只发生在**孩子主动开始巩固**时（`started`），且由新服务负责；
- 结论：**A/B（不修改 frozen service）成立**；若将来确需修改，属新的评审事项，本阶段不改。

## 17. V1.2 同步判断

**本阶段设计与 V1.2 一致，无需同步修改最高指导规范。**

理由：

1. 六种 `action_type` 直接来自 V1.2 二十二·6 的教材优先顺序，未新增类型；
2. "只有新证据改变判定""完成巩固≠已解决"是二十二·4/5（证据优先、重复不增值）的直接推论；
3. 孩子自主与不自动推进（二十二·2）在本设计中被显式约束（§14）；
4. AI 边界（二十二·7）未扩大（本设计 AI 参与为 0）；
5. 未改任何阈值（`mastery_rules_v1.json` 未修改）。

Consolidation Action 属**实现层概念**（记录孩子主动行为），不属于规范级教育原则，因此无需写入 V1.2。

## 18. Acceptance Criteria

| 编号 | 验收标准 |
| --- | --- |
| AC-01 | Suggestion ≠ Action（展示不创建 Action） |
| AC-02 | Click ≠ Started（点击不产生 Action、不产生证据） |
| AC-03 | Started ≠ Completed（两种状态可区分） |
| AC-04 | Completed ≠ mastery 提升（完成不改变状态） |
| AC-05 | Completed without Evidence 不会自动清除 current_error |
| AC-06 | 只有新的**有效证据**才参与重新诊断 |
| AC-07 | 新证据可来自**不同 item** |
| AC-08 | 新证据可映射到**同一 LO**（不断链） |
| AC-09 | Historical Error 不删除、不修改 |
| AC-10 | Current Error 可重新出现（latest=incorrect） |
| AC-11 | 一个 Action 可 0 / 1 / 多个 Evidence |
| AC-12 | 一个 Evidence 可关联多个 LO（不复制证据） |
| AC-13 | Action provenance 保留（target_resource + 时间窗 + related_evidence_ids） |
| AC-14 | Child autonomy 不被破坏（§14 全部满足） |
| AC-15 | AI 调用 0 |
| AC-16 | 不修改数据库（本轮） |
| AC-17 | 不修改冻结代码 |
| AC-18 | 不修改 V1.2 |
| AC-19 | 设计可进入 P2-6-C-4 综合设计评审（无临时再发明规则的需求） |

---

## 19. Edge Cases（15 项）

| # | 场景 | 设计处理 |
| --- | --- | --- |
| Edge 1 | 建议展示但孩子从未点击 | 无 Action、无证据；current_error 保持 |
| Edge 2 | 点击建议后立即退出 | 无 Action（未 started）；current_error 保持 |
| Edge 3 | 开始巩固后退出 | Action = `abandoned`；无证据；不影响 mastery |
| Edge 4 | 完成巩固但没有 Evidence | Action = `completed`；current_error **保持** |
| Edge 5 | 完成巩固并产生 incorrect | current_error 保持；错误计数 +1（可能升级 suspected_weak） |
| Edge 6 | 完成巩固并产生 partial | current_error 退出；进入"需要再看"语义（非已解决） |
| Edge 7 | 完成巩固并产生 correct，但历史错误很多 | current_error 退出；mastery 仍按五项条件判定（历史错误不自动判薄弱，正确一次也不判掌握） |
| Edge 8 | 之后再次出现错误 | current_error 重新进入（latest=incorrect） |
| Edge 9 | 一个 Action 涉及多个 LO | `target_lo_ids[]` 记录意图；实际归属以证据为准 |
| Edge 10 | 一个 Evidence 涉及多个 LO | 一条证据 + 多 LO 引用（不复制） |
| Edge 11 | 一个 Action 产生多个 Evidence | `related_evidence_ids[]` 全量回填 |
| Edge 12 | Action 完成后孩子没有继续 | 不产生任何自动推进；Action 状态即为事实 |
| Edge 13 | Action 被取消 | 归入 `abandoned`；不产生负面结论 |
| Edge 14 | Evidence 来自与原始错误不同的题目，但属同一 LO | 正常参与 D2（通过 LO 聚合，不断链） |
| Edge 15 | 找不到可靠 LO 映射 | **不强行绑定**：记 `unmapped`，不参与闭环判定 |

## 20. Open Decisions

1. **Action 是否落库（方案 B）的最终确认**：本设计推荐 B；若产品希望零 DB 变化，则必须接受"无法区分点击/开始/完成"的代价（该代价已在 §15 说明）。
2. **`started` 的判定口径**：本设计给出"进入目标资源并开始执行"的定义；具体触发点（进入页面 vs 首次互动）需与 UI 实现一并确认，**不得用时间阈值发明规则**。
3. **`completed` 的确认方式**：本设计复用既有语义（study/done、提交题目、听完音频）；是否需要显式"完成"按钮由 UI 阶段决定（属产品形态，不改本设计的语义边界）。
4. **`cross_section_practice` 的范围定义**：需确认是否限定在同一 Unit 内（建议：同一 Unit 内的跨 Section；跨 Unit 属阶段验证范畴，不属巩固）。
5. **Action 的保留期限与展示方式**（历史 Action 是否在 UI 中呈现）——产品决策。
6. **Grammar LO 前置数据**（来自 C-2）：未具备前，`grammar_pointer` 的 target 只能是"教材提示页"，其证据归 `unmapped`。

## 21. 保护基线（本轮实测）

| 项目 | 结果 |
| --- | --- |
| 业务代码 | **未修改**（`learning/`、`web/`、`workbench/` 时间戳不变） |
| `learning.db` | **未修改**（SHA256 前 16 位 `DBAB743BF6D8F0A3`，mtime `2026-09-12 23:15:13`） |
| contentpack | **未修改**（`ACEBC8C29CF5D11B`） |
| V1.2 | **未修改**（docx `6D3595CF7D83879A`） |
| `mastery_rules_v1.json` | **未修改**（`E7EC99DB55DDCF04`） |
| 测试 | **未修改**（未新增、未改动任何测试文件） |
| Android | 未触碰 |
| 新增文件 | 仅本报告与 JSON |

## 22. 测试结果（只读执行）

| 套件 | 结果 |
| --- | --- |
| learning | 89 PASS / 0 FAIL / 0 SKIP |
| workbench | 50 PASS / 0 FAIL / 0 SKIP |
| web | 224 PASS / 0 FAIL / 0 SKIP |
| **合计** | **363 PASS / 0 FAIL / 0 SKIP**（与基线一致） |

未修改任何测试以迎合数字；实际结果与任务书声明的 363 一致。

## 23. AI 调用统计

**AI 调用 = 0**（本轮全部为本地只读阅读、代码/数据结构阅读与设计推理）。

## 24. 下一步建议

1. 将本设计与 C-2 的 LO 设计一并提交 **P2-6-C-4 综合设计评审**（重点评审 §20 的 6 项 Open Decisions）；
2. 评审通过后，实施顺序建议：① LO 派生映射层（C-2，零 DB 变化）→ ② Consolidation Action 最小结构（C-3，1 张新表）→ ③ LO 级证据聚合与再诊断 → ④ 巩固入口的最小 UI 接线；
3. 实施前需产品确认：Action 是否落库、`started/completed` 的交互触发点、`cross_section_practice` 范围；
4. **本阶段不实施**：不写代码、不建表、不迁库、不接 AI。设计完成后立即停止，等待人工审核。

---

### 附录：对任务书 §二十五 10 个问题的直接回答

1. **Consolidation Action 是什么**：孩子主动开始并执行的、指向某个教材巩固目标的最小学习行为单元（6 种教材优先类型，含目标资源、起止时间与完成判据）。
2. **Suggestion 与 Action 如何区分**：Suggestion 是派生展示物（不落库、不改变任何状态）；Action 是孩子主动行为的持久化事实（仅在 `started` 时创建）。
3. **Click / Started / Completed 是否都要记录**：只记录 `started` 与终态（`completed` / `abandoned`）；**Click 不单独记录**（它不是状态，且无法改变判定）。
4. **Action 完成但没有新证据时 current_error 是什么状态**：**保持**（未解决）；完成巩固 ≠ 已解决。
5. **什么情况下 current_error 可以被重新判断**：当该 LO 产生**新的有效判断证据**时（correct → 退出；partial → 转为"需要再看"；incorrect → 保持并可能升级）。
6. **新证据如何连接到原来的 LO**：通过 C-2 的确定性映射（item → LO，允许来自不同 item，一条证据可引用多个 LO），`item_id` 保留为 provenance。
7. **Historical Error 与 Current Error 如何共存**：历史错误永久保留在 `learning_record`（事实）；Current Error 是 LO 级派生行动状态（可进可出），二者互不删除、互不替代。
8. **是否需要独立持久化 Action**：**需要**（方案 B）；因为"孩子做过什么"无法由现有数据派生。
9. **是否需要数据库结构变化**：**可能需要**（仅 1 张最小 Action 表；LO 映射与证据仍为只读派生）。**本轮不实施**。
10. **C-4 是否已经具备进入综合设计评审的条件**：**具备**——Action 语义、生命周期、证据关系、Current Error 处理、LO 再诊断与持久化边界已定义清楚，评审无需在实现阶段临时发明规则。
