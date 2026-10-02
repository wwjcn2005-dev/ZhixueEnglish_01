# P2-6-C-4 Full Chain Design Review

> **只读综合设计评审。** 本轮未修改任何代码 / 测试 / 数据库 / contentpack / 教材 / V1.2 / P2-4 / P2-5 / Android，未调用 AI。
> 评审对象：P2-6-B（实现）+ C-1（审计）+ C-2（LO 设计）+ C-3（Action 设计）拼合后的**全链路一致性**。
> 评审立场：站在"如果明天开始写代码，半年后会不会因模型设计错误而返工"的角度，**不因连续完成 C-1/C-2/C-3 而倾向给 PASS**。

- 评审时间：2026-09-13
- 项目：`D:\ZhixueEnglish`
- 产出：本文件 + `P2-6-C-4_full_chain_design_review.json`

---

## 1. Executive Conclusion

**PASS WITH GAPS**

**12 条红线全部未触发**（§23），核心架构成立、闭环自洽、且**不依赖 AI、不需要数据库迁移、不需要修改冻结服务与 V1.2**；存在 6 项**可延期 GAP**（§24），其中 3 项必须在 D 阶段以"显式边界"方式处理（unmapped、Action 归因规则、Grammar 避开策略）。

## 2. Review Scope

审查 P2-6-B/C-1/C-2/C-3 拼合后的：层职责边界、LO 成立性、映射覆盖率、Evidence 聚合、Mastery 粒度、Diagnosis 语义、Suggestion/Action 分离、Current/Historical Error、Re-diagnosis 触发、frozen pool 共存、AI 与数据库边界、D 阶段最小实施边界。

不重复 C-1 的数据盘点、C-2 的 LO 候选分析、C-3 的生命周期逐项解释；只检查**冲突、遗漏、循环断点、实现风险**。

## 3. Source Documents

`初中英语AI辅助学习系统_最高指导原则与开发规范_V1.2.docx` 与 `docs/…V1.2.md`；`audit/P2-6-C-1_*.md/json`；`audit/P2-6-C-2_*.md/json`；`audit/P2-6-C-3_*.md/json`；`audit/P2-6-B_*.md/json`；`learning/evidence_service.py`、`mastery_service.py`、`diagnosis_service.py`、`intervention_service.py`；`structured/learning/mastery_rules_v1.json`。

## 4. Full Architecture Chain

```
教材事实（contentpack v5 + P2-4：unit/section/activity/词表/文本/音频/练习）
   │  确定性映射（无 AI）：C-2 §9 R1–R6 + 词条键
   ▼
Learning Object（叶 LO：VOCAB | PHRASE | PATTERN | LISTENING | READING | WRITING）
   │  归属容器（非 mastery 对象）
   ▼
Activity（任务容器）
   ▼
Exercise / Question（证据产生器；exercise_id ≡ item_id）
   ▼
Evidence（有效判断证据；item 级 provenance；可引用多个 LO）
   │  两层去重（item/日/类型 → LO/日/类型）
   ▼
Mastery（LO 粒度；mastery_rules_v1 五项条件）
   ▼
Diagnosis（LO 粒度：current_error / suspected_weak / needs_textbook_review）
   ▼
Intervention / Suggestion（教材优先六类；含教材定位）
   ▼
Child Choice（点击 ≠ 开始 ≠ 完成）
   ▼
Consolidation Action（started → completed | abandoned；可选持久化）
   ▼
新的学习行为（教材文本/音频/语法页/范文/原题）
   ▼
新的 Evidence（可来自不同 item，经 LO 汇聚）
   ▼
Re-diagnosis（读时派生，无独立触发机制）
```

**闭环完整性**：链上每一层都有输入/输出，且**不存在必须由 AI 或新持久化结构填补的空洞**；唯一"可选持久化"节点是 Consolidation Action。

## 5. Layer Responsibility Matrix

| Layer | Definition | Persistent/Derived | Input | Output | Frozen Boundary |
| --- | --- | --- | --- | --- | --- |
| 教材事实 | contentpack + P2-4 结构/音频/题目 | **Persistent（只读）** | PDF/MP3（原样） | unit/section/activity/词条/文本/音频 | 只读，不得修改 |
| Learning Object | 教材最小可判定学习内容 | **Derived**（C-2 设计） | 教材事实 | LO id + canonical key | 不落库 |
| Activity | 教材任务容器 | Persistent（contentpack 96 行快照）+ 派生（P2-3 补 64） | 教材版式 | 活动编号/指令/边界 | 不修改 |
| Exercise / Question | 证据产生器（157 / 360） | Persistent（catalog v3 + question relations） | Activity/教材语义 | 题型/选项/空位/教材位置 | 只读 |
| Evidence | 有效判断证据（非行为记录） | **Derived**（`evidence_service`） | learning_record + catalog | 有效证据集合（含 task_type/自然日） | 只读派生 |
| Mastery | 稳定掌握判定 | **Derived**（LO 级，C-2/C-4） | LO 证据集合 | state + 条件明细 | 只读派生（`mastery_state` 为 item 级事实缓存） |
| Diagnosis | 当前是否需行动 | **Derived** | LO 证据集合 | current_error / suspected_weak / needs_textbook_review | 只读派生 |
| Intervention / Suggestion | 教材优先建议 | **Derived** | Diagnosis + `intervention_model` | 建议列表（含教材定位） | 只读派生 |
| Child Choice | 孩子的点击与决定 | 不持久化（点击）/ 或 Action 起点 | 建议 | 是否进入资源 | 无自动执行 |
| Consolidation Action | 孩子主动巩固行为 | **可选 Persistent**（C-3 方案 B） | 孩子行为 | started/completed/abandoned + 目标 | 新独立层，不碰 frozen |
| 新 Evidence / Re-diagnosis | 新事实 → 新判定 | **Derived** | 新 learning_record | 更新后的 Diagnosis/Mastery | 只读派生 |

**职责重叠检查结论**：无致命重叠；存在 2 处**需显式声明的边界**（见 §9、§18）：①`mastery_state`（item 级持久化缓存）与 LO 级派生 mastery 的关系；②frozen pool 的"当前错误"与新 diagnosis 层的"current_error"的语义分层。

---

## 6. Learning Object Review

| # | 问题 | 判定 | 理由 |
| --- | --- | --- | --- |
| 1 | LO 是否足够小 | ✅ | 词条/文本/任务的粒度可独立讨论"会不会"；Unit/Section 仅作容器 |
| 2 | 是否稳定 | ✅ | 词条键（词面唯一 288/288）、文本键（unit+section+page）、任务键（unit+section+activity_no）均来自教材事实 |
| 3 | 是否来自教材事实 | ✅ | 全部来自 contentpack/P2-4，无运行时状态参与 |
| 4 | LO ID 是否确定性生成 | ✅ | `LO:<textbook>:<TYPE>:<sha256(canonical)[:12]>`，同输入同输出 |
| 5 | 相同教材事实是否得到相同 LO | ✅ | canonical_string 只含教材字段（已明确排除 record/mastery/时间/AI） |
| 6 | 不同 LO 是否可能错误合并 | ⚠️ 低风险 | 仅当规范化规则把不同词条折叠为同一 lexeme（如大小写/标点差异）时；C-2 已固定 NFC+小写+去尾标点+保留连字符与撇号 → 需 D 阶段以"规范化后词面唯一性断言"守住 |
| 7 | 一个教材对象是否可能对应多个 LO | ✅ 允许 | 同词不同义（当前无案例，`sense` 位预留）；同文本的阅读与写作可各为 LO |
| 8 | 一个 Exercise 是否可关联多个 LO | ✅ | C-2 R5：12 个练习有 ≥2 个 CORE 词候选 |
| 9 | 一个 Evidence 是否可关联多个 LO | ✅ | C-2 §10 方案 A（一条证据 + 多引用，不复制） |
| 10 | Vocab global LO 与 Unit 属性的设计 | ✅ 合理 | 词表每词一条、无重名；`primary_unit` 为属性而非身份 |

**LO 成立性结论**：**成立**，且已有真实数据支撑（见 §21 Case C）。

## 7. Unmapped Exercise Review

事实：157 个练习中 **89 可映射（56.7%）**，**68 unmapped（43.3%）**——构成：speaking 16、reflection 18、other 14、无 CORE 词候选的词汇类练习等（另 64 个练习无 `activity_id`，其中部分落入 unmapped）。

| # | 问题 | 判定 |
| --- | --- | --- |
| 1 | 是否应在 D 之前解决 | ❌ 不必须；unmapped 是**显式设计状态**，不是错误 |
| 2 | 是否允许保持 unmapped | ✅ 允许（V1.2 未要求 100% 覆盖） |
| 3 | unmapped 是否破坏 Evidence→LO→Mastery | ⚠️ 局部影响：这些练习的证据**停留在 item 级**，不参与 LO 判定；但闭环整体仍成立 |
| 4 | 哪些功能可在映射不完整下正常实现 | ✅ LO 映射服务、LO 证据聚合、LO mastery、LO 诊断、教材建议、再诊断（对已映射部分） |
| 5 | 哪些必须等 mapping 完成 | ⚠️ "全教材覆盖率声明"、"跨 LO 综合诊断"的完整版、阶段验证的题源完整性 |
| 6 | 是否应新增 LO 类型 | ⚠️ 需产品决策（speaking/reflection 是否成为 LO）——**本阶段不自增** |
| 7 | 新增是否超出 V1.2 | ⚠️ 会超出（V1.2 列举的 LO 类型不含 speaking/reflection）→ 属产品边界问题，须走规范同步或明确不做 |
| 8 | 是否需人工产品决策 | ✅ 需要（3 项：speaking、reflection、other 类练习归属） |
| 9 | 是否存在"为闭环强行映射"风险 | ⚠️ 存在；**必须由 D 阶段以 `unmapped` + 复核清单守住** |

**分类结论**：

- **可进入 D**：已映射的 89 个练习 + 288 词条 + 文本/听力/写作 LO；
- **不必阻塞 D**：68 unmapped 保持显式状态，D 必须在展示与统计中**如实标注覆盖率**；
- **可延期**：speaking / reflection 的类型决策、64 个无 `activity_id` 练习的题目关系补齐。

## 8. Grammar LO Review

| 检查项 | 结果 |
| --- | --- |
| V1.2 是否要求 Grammar LO | **是**（二十二·3 列举"语法点"为学习对象） |
| grammar pointer 是否足够 | ❌ 不足：仅 13 条教材提示指针（7 语法 + 6 语音），无条目/例句结构 |
| 是否存在 grammar learning object | ❌ |
| 是否存在 grammar exercise | ❌（语法练习散落在 fill/other 题型中，未标注语法目标） |
| 是否存在 grammar evidence | ❌（无语法目标 → 无法归属） |
| 是否能形成 grammar mastery / diagnosis / consolidation | ❌（缺目标对象；`grammar_pointer` 建议只能指向"教材提示页"，证据归 unmapped） |

**方案判断**：**取方案 A（Grammar LO 暂缓，不阻塞其他 LO 的最小实现）**。
理由：① V1.2 要求的是"语法点可以是学习对象"，而非"必须本期实现"；② 当前无教材资源对象，强行实施等于制造教材事实（违反最高原则）；③ 其他五类 LO（词/短语/句型/听力/阅读/写作）已可独立成立。
**D 阶段安全避开方式**：语法类证据显式记 `unmapped(grammar)`；`grammar_pointer` 建议保留但只指向教材提示页、不设 LO、不参与 mastery。

## 9. Evidence Review

| 检查项 | 结论 |
| --- | --- |
| done 是否仍被计入 Evidence | ❌ 不计（`EVIDENCE_RESULTS` 含 done，但 `evidence_service` 以 `counted_results=(correct,incorrect,partial)` 排除 done/skipped/NULL）→ **正确** |
| self-assessment 是否单独成为 Evidence | ❌ 不会（`self_assessment_only` 规则排除） |
| contact-only 是否被排除 | ✅（`study` → contact_only） |
| correct / incorrect / partial 如何进入 | ✅ 作为有效判断证据（`judged_result`） |
| task_type 是否确定 | ✅（练习：`exercise_catalog_v3.question_type`；词汇：`textbook_study`/`recall`；其他：activity_type 原值） |
| item_id 是否保留 | ✅（`source_record_id` + `item_id`，C-2 要求继续保留） |
| evidence_date 如何确定 | ✅ `created_at[:10]`（ISO8601 带 +08:00，时区一致） |
| 去重规则 | ✅ 当前 item 级；C-2 设计为两层（item/日/类型 → LO/日/类型） |
| 同一天不同题不能无限增加证据 | ✅ 第 2 层去重（同 LO 同日同类型只计 1） |
| 跨自然日形成新独立证据 | ✅ 第 4 层 |
| 同一 LO 的多个 item 如何聚合 | ✅ 经 LO 映射汇聚，`sources[]` 保留 provenance |
| 一条 Evidence 多 LO 如何处理 | ✅ 一条证据 + 多引用（不复制） |

**两层 dedupe 是否存在逻辑冲突**：**无冲突**。item 级是"同一题重复不增值"，LO 级是"同一 LO 同日同类型换题不增值"；两者是包含关系（后者更严），不产生矛盾。**唯一需注意**：LO 级去重会把"同一 LO 同日两道不同类型的题"分别计入（符合"≥2 task types"的设计意图），这是**有意设计**而非漏洞。

## 10. Mastery Review

| # | 问题 | 判定 |
| --- | --- | --- |
| 1 | 五项条件能否在 LO 层获得 | ✅ 可（按 LO 聚合后的证据集合） |
| 2 | 是否 item 层伪装成 LO 层 | ❌ 不是（LO 级聚合后判定；item 仅作 provenance） |
| 3 | task_type 是否真能跨任务类型 | ✅ 实际可达：真实数据中 `VOCAB:eraser` 同时有 recall 证据与 2 个映射练习（题型 match）→ 跨任务类型成立 |
| 4 | natural day 是否一致 | ✅ 统一用 `created_at[:10]` |
| 5 | latest 3 是否 LO 级 | ⚠️ 当前实现是 item 级；**D 阶段须改为 LO 级**（C-2 设计已明确指出） |
| 6 | current error 是否 LO 级 | ⚠️ 同上（当前 item 级；D 阶段改 LO 级） |
| 7 | Action completion 是否错误影响 mastery | ❌ 不会（C-3 明确完成 ≠ 掌握） |
| 8 | correct evidence 是否被过度解释 | ❌ 不会（单次正确不判 stable；需五项条件） |

**"当前数据 stable=0 是正常还是缺陷"** → **正常现象**，原因有三且均已核实：① 全部记录集中在 1 个自然日（条件 3 不满足）；② 每对象有效证据 ≤1 条（条件 1 不满足）；③ 尚未实现 LO 聚合（跨任务类型未汇合）。**不是设计缺陷**：用真实教材数据可验证"eraser"这一 LO 同时具备 recall 与练习映射（若孩子当天再练一次该题即出现 2 种任务类型）。

## 11. Diagnosis Review

| # | 问题 | 判定 |
| --- | --- | --- |
| 1 | Diagnosis 是否以 LO 为核心 | ⚠️ 当前 item 级；**D 阶段迁到 LO 级**（规则不变） |
| 2 | current_error 是否来自 LO 级证据 | ⚠️ 同上（当前是 item 级"最近一条有效证据"） |
| 3 | suspected_weak 如何产生 | ✅ 阈值已定（≥2 次错误 或 跨 ≥2 任务类型） |
| 4 | partial 如何产生"需要再看" | ✅ `needs_textbook_review`（≥2 partial 且跨 ≥2 类型） |
| 5 | 一次错误是否会被误判为 weakness | ❌ 不会（单次错误只出 current_error） |
| 6 | 新 Evidence 是否能改变诊断 | ✅ 能（且**只有**新证据能） |
| 7 | 不同 item 是否可重新判断同一 LO | ✅ 可（经 LO 聚合） |
| 8 | 历史错误是否保留 | ✅（append-only） |
| 9 | Current Error 是否只是派生状态 | ✅（无独立持久化） |

## 12. Intervention / Suggestion Review

| 检查项 | 结论 |
| --- | --- |
| 六类建议是否都有可靠教材资源 | ⚠️ 部分：reread_text（文本/词表页 ✅）、replay_audio（官方音频 ✅）、grammar_pointer（提示页 ✅ 但仅指针）、model_text_review（Reading for writing 范文 ✅）、redo_exercise（✅）、cross_section_practice（unit 练习列表 ✅） |
| resource target 是否与 action type 分离 | ✅（C-3 已明确分离） |
| 找不到资源时是否编造 | ❌ 不编造（`requires_resource_mapping` + `missing`） |
| 是否存在 AI 兜底 | ❌ 无（`ai_assist = not_implemented`） |
| 是否自动执行/跳转/播放/进入下一项 | ❌ 全部否（仅链接，需孩子点击） |

## 13. Consolidation Action Review

| # | 问题 | 判定 |
| --- | --- | --- |
| 1 | Action 模型是否最小 | ✅ 三态（started/completed/abandoned）+ 6 类型；无 suggestion/click 状态 |
| 2 | 是否真的需要独立持久化 | **YES WITH GAP**：证据闭环**不依赖**它（新证据自会到达）；但"区分点击/开始/完成"与"呈现已尝试"**必须**它 → **D 可先做证据闭环，Action 表紧随其后** |
| 3 | 推荐字段是否合理 | 见下表 |
| 4 | 是否需要 suggestion_id | ❌ 不需要（建议为派生展示物） |
| 5 | 是否需要 diagnosis_id | ❌ 不需要（诊断派生；如需追溯用 `source_ref` 派生指纹） |
| 6 | Action 是否涉及多个 LO | ✅ 可（`target_lo_ids[]` 记意图，事实以证据为准） |
| 7 | Action 是否产生多个 Evidence | ✅ 必须支持（`related_evidence_ids[]`） |

**字段逐项判断**

| 字段 | 判定 |
| --- | --- |
| action_id | **必需** |
| learner_id | **必需** |
| action_type | **必需**（6 值） |
| target_resource | **必需**（否则不构成 Action） |
| status | **必需**（started/completed/abandoned） |
| started_at / ended_at | **必需** |
| related_evidence_ids | **必需（可空数组）** |
| created_at | **必需** |
| target_lo_ids | **可延期**（`cross_section_practice` 才需要；可先用派生推导） |
| source_ref（diagnosis/suggestion 指纹） | **可延期**（追溯用途，非功能必需） |
| suggestion_id | **不应该存在**（重复状态） |
| diagnosis_id | **不应该存在**（重复状态） |

**Action 归因的 D 前置设计**：`related_evidence_ids` 的回填规则必须明确（建议：`created_at >= action.started_at` 且 事件属于该 action 的会话或目标范围）；否则会把窗口内**无关**的新证据误挂到该 Action。**这是 D 的前置项，不是 C-4 的阻塞项。**

---

## 14. Current Error Review

**唯一、清晰的状态语义（三段完全分离）**

| 维度 | 定义 | 载体 | 可进可出 |
| --- | --- | --- | --- |
| **Action status** | 孩子巩固行为的状态：started / completed / abandoned | Consolidation Action 记录 | 不适用 |
| **Current Error status** | 该 LO 最近一条**有效判断证据**为 incorrect | **派生**（不落库） | ✅ 可进可出 |
| **Mastery status** | 该 LO 的证据集合是否满足五项条件 | **派生**（不落库） | ✅ 可升可降 |

**全序列判定表**

| 阶段 | Current Error | Mastery | 说明 |
| --- | --- | --- | --- |
| 未处理（首次错误） | 进入 | 非 stable | 单次错误 ≠ 薄弱 |
| 建议展示 | 保持 | 不变 | 展示不产生任何状态变化 |
| 未开始（点击即退出） | 保持 | 不变 | click 不落状态 |
| 开始（started） | 保持 | 不变 | Action 与 mastery 无关 |
| 完成但无新证据 | **保持** | 不变 | completed ≠ resolved |
| 新证据 incorrect | 保持（错误计数+1） | 不变/降级 | 可能升级 suspected_weak |
| 新证据 partial | **退出** | 可能降级 | 转"需要再看" |
| 新证据 correct | **退出** | 需重算（未必 stable） | 单次正确 ≠ 掌握 |
| 后续再次错误 | **重新进入** | 可能降级 | 历史错误始终保留 |

**结论**：三者不得混为一个字段；Current Error 完全由证据派生，Action 与 Mastery 各自独立。

## 15. Historical Error Review

| 检查项 | 结论 |
| --- | --- |
| 答对后历史错误是否仍存在 | ✅ 存在（learning_record append-only，未被修改） |
| 当前错误消失后是否还能查看历史 | ✅ 可以（历史记录不因出池而删除） |
| 后续再次错误是否重新进入 Current Error | ✅ 会（latest=incorrect） |
| frozen resource pool 是否与 diagnosis 冲突 | ⚠️ 语义分层，不冲突（§18） |
| 是否存在两个系统分别定义"错误" | ✅ 存在但不是冲突：pool=最近一次判断**事实**（含自评）；diagnosis=LO 级**有效证据结论** |

## 16. Re-diagnosis Review

**触发机制**：**无需独立触发器**——Re-diagnosis 是**读时派生**：任何查询该 LO 状态的动作都会基于当时的证据集合重新计算。因此不需要事件总线/异步任务/版本号。

**输入选取（C-3 建议的验证）**

| 候选 | 采用 | 理由 |
| --- | --- | --- |
| 全历史 | ⚠️ 仅用于计数类条件 | 避免"重复动作无限增值"与忽略近期性 |
| 最近窗口 | ✅（最近 3 次） | 对应 `mastery_rules_v1.recent_attempt_window` |
| current error + recent evidence | ✅ | 对应 current_error（最新一条） |
| 使用 mastery_rules | ✅ | 状态判定的唯一阈值来源 |
| 独立 diagnosis_rules | ❌ **不需要新增** | 现有 `mastery_rules_v1.diagnosis`（suspected_weak / textbook_review 阈值）已覆盖，新增会产生双阈值冲突 |

**闭环真实性**：**成立**——新证据 → LO 映射 → 证据集合变化 → 下次查询即得 D2；且**证据可来自不同 item**（§21 Case C 有真实数据支撑）。

## 17. Activity / Exercise / Evidence Boundary

| 检查项 | 结论 |
| --- | --- |
| Activity 能否直接作为 mastery evidence | ❌ 不能（活动是容器，证据必须来自作答/行为结果） |
| Exercise 能否直接作为 LO | ❌ 不能（会产生"做完即掌握"） |
| Question 能否直接作为 LO | ❌ 不能（题目是证据来源） |
| Action 与 Activity 是否重叠 | ❌ 不重叠：Action = 孩子主动巩固行为（可跨资源）；Activity = 教材上的任务块（版式对象）；二者可能指向同一教材资源，但语义层级不同 |
| 是否存在语义冲突 | ⚠️ 一处措辞风险：`activity_type` 字段同时承载"资源类型"（activity_service 取 item_type）与"学习行为"（调用方写 listen/read/study/practice）→ **D 阶段必须只用其行为语义**，资源类型以 `learning_item.item_type` 为准 |

## 18. Resource Pool Relationship

| 问题 | 结论 |
| --- | --- |
| 两者是否重复 | ❌ 不重复（事实层 vs 结论层） |
| 谁负责"事实池" | **frozen `resource_pool_service`**（最近一条 judged 记录，含孩子自评） |
| 谁负责"当前判断" | **`diagnosis_service`**（LO 级有效证据结论） |
| 谁负责"建议" | **`intervention_service`**（教材优先，只读） |
| 是否最终统一 | ⚠️ 待产品决策（建议长期保持两层语义，不合并；合并会失去"事实可核对性"） |
| D 阶段是否需要碰 `resource_pool_service` | ❌ **不需要**（保持冻结；D 只读取它用于展示口径对齐） |

## 19. AI Boundary

- 闭环中**不存在 AI 必需节点**：教材事实 → 确定性规则 → LO → Evidence → Mastery/Diagnosis → 教材建议 → 孩子选择，全部可由本地规则完成。
- AI 未来可辅助：开放题批改、错误解释、证据诊断、教材范围内变式——但**不得**自动选科、自动安排、自动决定必须巩固、自动执行 Action、自动决定 mastery、脱离教材生成路径。
- **本轮 AI 调用 = 0**（已核实：业务代码零网络/AI 调用点，`ai_grading` 为本地规则）。

## 20. Database / Persistence Boundary

| 对象 | 持久化判断 | 理由 |
| --- | --- | --- |
| LearningRecord（事实） | ✅ 已持久化（不动） | 唯一事实来源 |
| `mastery_state`（现有 item 级缓存） | ✅ 保持现状（不动） | 由 frozen 写入；**D 阶段应明确其定位为"item 级事实缓存"，LO 级 mastery 才是判定对象** |
| Learning Object | ❌ 不落库（派生） | 可由教材事实稳定重算 |
| Evidence | ❌ 不落库（派生） | 可由 record + rules 稳定重算 |
| Diagnosis / Suggestion | ❌ 不落库（派生） | 规则/阈值会演进，落库会漂移 |
| Consolidation Action | ⚠️ **可选落库**（1 张最小表） | 唯一无法派生的事实；可延期但需要它才能区分"未处理 / 已尝试" |

**结论**：**不需要把 LO / Evidence / Diagnosis 落库**；最坏情形只新增 1 张 Action 表（且可延期）。

## 21. End-to-End Cases

### Case A：Vocabulary（词条 LO）

```
E1  recall 错误        → LO:VOCAB:without（current_error）
D1  current_error
S1  reread_text（教材词表页 p150 / 课文含该词的句子）
A1  child clicks → started → 完成阅读确认 → completed
E2  另一题（不同 item）中涉及 without 且答对 → 经 LO 映射回到同一 LO
D2  current_error 退出；mastery 按五项条件重算 → 证据不足 → 非 stable
```

判定：E2 通过**词条键**映射回同一 LO；current_error 退出；**mastery 不会立即 stable**（需 ≥3 证据 / ≥2 类型 / ≥2 自然日 / 最近 3 次 ≥2 正确 / 无未处理错误）。

### Case B：Exercise（题 → LO）

```
E1  incorrect          → LO-x（如 LO:LISTENING 或 LO:VOCAB:eraser）
D1  current_error（首次）→ 若已有第 2 次错误则 suspected_weak
S1  redo_exercise（同一教材题）
A1  completed
E2  仍 incorrect       → 同一 LO
D2  current_error 保持；错误计数 +1 → 升级 suspected_weak
```

判定：current_error 保持；可能升级 weak；**历史错误全部保留**（两条 incorrect 均在 learning_record）。

### Case C：跨 Item 同一 LO（**真实数据可证**）

```
E1  item = V:C128262B65A0（"without" 之外的 eraser 类词汇 recall）
        → LO:VOCAB:eraser
Action  reread_text（教材词表页）
E2  item = X:082981460EC2（Starter GET_READY A1 "Match…"，题型 match）
        → 同一 LO:VOCAB:eraser
```

**真实数据支撑（本轮只读验证）**：

- 映射到 `VOCAB:eraser` 的练习有 **2 个不同 exercise**（`X:082981460EC2`、`X:737C6C9C364F`）；
- 学习者已存在 `eraser` 的词汇记录（study / recall）；
- 另有 3 个 LO（`need`、`club`、`amazing`）各有 ≥2 个不同 exercise 可汇聚。

→ **跨 item 同一 LO 的证据链在真实教材数据中成立**，依赖的确定性映射为：`exercise → activity_id → related_vocabulary（词面）→ vocabulary item_id（288 词面唯一，1,512 引用 100% 唯一解析）→ LO id`。

---

## 22. Acceptance Criteria

| 编号 | 验收标准 |
| --- | --- |
| AC-01 | LO 映射确定性（同输入同输出；跨进程可复现） |
| AC-02 | 不同教材对象不错误合并（规范化后词面唯一性断言） |
| AC-03 | Vocabulary → LO 确定性（288/288） |
| AC-04 | Exercise → LO 确定性（含 `unmapped` 显式标记） |
| AC-05 | 同一 LO 可关联多个合法任务来源（真实数据已有 4 例） |
| AC-06 | Evidence 保留 item 级 provenance |
| AC-07 | 两层去重生效（item/日/类型 → LO/日/类型） |
| AC-08 | Mastery 以 LO 为判定对象；item 级仅作缓存/来源 |
| AC-09 | Diagnosis 以 LO 证据为核心；单次错误不判薄弱 |
| AC-10 | Suggestion 与 Action 分离；点击不落状态 |
| AC-11 | Action 完成不影响 mastery；无证据不清除 current_error |
| AC-12 | Historical Error 不被删除（learning.db SHA 不变） |
| AC-13 | Current Error 可重新出现 |
| AC-14 | Re-diagnosis 为读时派生，无独立触发器 |
| AC-15 | unmapped 内容不参与 LO 判定，且覆盖率如实报告 |
| AC-16 | AI 调用 0 |
| AC-17 | 不修改冻结服务 / contentpack / V1.2 / 测试 |
| AC-18 | 现有 363 测试保持通过 |

## 23. Blocking Issues

**无。** 12 条红线逐项核对：

| # | 红线 | 判定 |
| --- | --- | --- |
| 1 | LO 无法稳定确定 | ❌ 未触发（六类键确定性；覆盖率 56.7% 但 unmapped 显式） |
| 2 | Evidence 无法稳定映射 LO | ❌ 未触发（已映射部分 100% 可解析） |
| 3 | Mastery 无法在 LO 层定义 | ❌ 未触发（规则可直接套用） |
| 4 | Diagnosis 与 Mastery 语义冲突 | ❌ 未触发（行动状态 vs 稳定状态） |
| 5 | Action 与 Evidence 无法区分 | ❌ 未触发（C-3 已分离） |
| 6 | New Evidence 无法回到原 LO | ❌ 未触发（真实数据 Case C 已证） |
| 7 | Current Error 无法可靠重判 | ❌ 未触发（latest LO evidence） |
| 8 | Historical Error 会被错误删除 | ❌ 未触发（append-only） |
| 9 | 闭环依赖 AI 才能成立 | ❌ 未触发（AI 非必需节点） |
| 10 | 必须修改 V1.2 | ❌ 未触发 |
| 11 | 必须大规模迁移 learning.db | ❌ 未触发（最多 1 张可选表） |
| 12 | 必须破坏冻结服务 | ❌ 未触发（新增独立层） |

## 24. Deferrable Gaps

| # | GAP | 影响 | 处置 |
| --- | --- | --- | --- |
| G1 | 68/157 练习 unmapped（43%） | 这些练习的证据停留在 item 级 | D 阶段显式标记 + 如实报告覆盖率；产品决策 speaking/reflection 归属 |
| G2 | Grammar LO 缺教材对象 | 语法证据无法归属 | D 阶段记 `unmapped(grammar)`，`grammar_pointer` 仅指提示页 |
| G3 | Consolidation Action 表未建 | 无法区分"未处理 / 已尝试未解决" | D 可先做证据闭环；Action 表作为紧随其后的增量 |
| G4 | Action → Evidence 归因规则未细化 | 可能误挂窗口内的无关证据 | D 前置：定义时间窗 + 会话/目标范围规则 |
| G5 | `mastery_state`（item 级）与 LO 级 mastery 并存 | UI 口径可能混淆 | D 阶段明确"item 级=事实缓存、LO 级=判定对象"，UI 标注来源 |
| G6 | 64 个练习无 `activity_id` | 影响 R3–R5 的可用性 | 可延期（补齐 P2-3 活动与 contentpack 题目关系） |

## 25. P2-6-D Must / Can Defer / Not Yet

**D-必须做（不做无法形成最小闭环）**

1. Learning Object 确定性映射服务（只读派生，零 DB 变化）；
2. LO 级 Evidence 聚合（两层去重 + provenance 保留）；
3. LO 级 Mastery（只读派生，复用 `mastery_rules_v1` 五项条件，阈值不变）；
4. LO 级 Diagnosis（current_error / suspected_weak / needs_textbook_review）；
5. 教材优先 Suggestion（迁移到 LO 定位；保持只读、需孩子点击）；
6. `unmapped` 的显式处理与覆盖率如实报告；
7. Re-diagnosis（读时派生，无独立触发器）；
8. 专项验收测试（上表 AC-01…AC-18 对应项）。

**D-可以延期**

1. Consolidation Action 最小表（建议紧随 D 之后）；
2. Action → 新证据的归因规则细化（若同时做 Action 表则为前置）；
3. Grammar LO（等待教材语法对象数据）；
4. speaking / reflection 的 LO 归属决策与实现；
5. 64 个无 `activity_id` 练习的题目关系补齐；
6. 跨 Unit 阶段验证入口。

**D-暂不做**

1. UI 大改（仅允许最小接线：展示 LO 状态与教材建议）；
2. AI 批改 / AI 生成（保持 0）；
3. Android 修改；
4. 积分 / 排名 / 等级 / 游戏化；
5. 专项题库；
6. 数据库大规模迁移或表重构。

## 26. V1.2 Spec Sync Decision

**无需修改 V1.2。**

理由：全链路设计（LO 类型、证据优先、五项条件、教材优先巩固、AI 边界、孩子自主）均落在 V1.2 第二十二章既有条文范围内；Consolidation Action 属实现层概念；阈值仍在 `mastery_rules_v1.json`（工程参数）。
**唯一可能触发规范同步的情形**（本阶段不执行）：若产品决定把 **speaking / reflection** 新增为 LO 类型，则需在 V1.2 补充 LO 类型清单——属产品边界决策，须单独走规范同步流程。

## 27. Protection Baseline

| 项目 | 结果 |
| --- | --- |
| 业务代码 | 未修改 |
| 测试 | 未修改 |
| `learning.db` | 未修改（SHA16 `DBAB743BF6D8F0A3`，mtime `2026-09-12 23:15:13`） |
| contentpack | 未修改（`ACEBC8C29CF5D11B`） |
| V1.2 | 未修改（`6D3595CF7D83879A`） |
| P2-4 / P2-5 | 未修改 |
| `mastery_rules_v1.json` | 未修改（`E7EC99DB55DDCF04`） |
| Android | 未修改 |
| AI 调用 | **0** |
| 新增文件 | 仅本报告与 JSON |

## 28. Tests

| 套件 | 结果 |
| --- | --- |
| learning | 89 PASS / 0 FAIL / 0 SKIP |
| workbench | 50 PASS / 0 FAIL / 0 SKIP |
| web | 224 PASS / 0 FAIL / 0 SKIP |
| **合计** | **363 PASS / 0 FAIL / 0 SKIP**（与基线一致；只读执行） |

## 29. AI Calls

**0**。本阶段全部为本地只读阅读、静态分析与数据推导。

## 30. Final Recommendation

**PASS WITH GAPS → 可以进入 P2-6-D**，按 §25 的 Must / Can Defer / Not Yet 边界实施；D 阶段必须遵守：零 DB 迁移（除可选的 1 张 Action 表）、不动冻结服务、不改 V1.2、AI=0、不得为提高映射率而强行归属。

---

### 附录：15 个必答问题

| # | 问题 | 结论 | 理由 |
| --- | --- | --- | --- |
| 1 | 当前 LO 模型是否成立 | **YES** | 六类叶 LO 键均来自教材事实、确定性可复现；Unit/Section 仅作容器 |
| 2 | 68/157 unmapped 是否阻塞 D | **NO** | unmapped 是显式设计状态；闭环对已映射部分成立 |
| 3 | Grammar LO 是否阻塞 D | **NO** | 采用方案 A；语法证据记 `unmapped(grammar)`，不影响其他 LO |
| 4 | Evidence 是否已具备 LO 聚合基础 | **YES WITH GAP** | 有效证据/去重/溯源已实现；LO 级聚合层需 D 实现 |
| 5 | Mastery 是否可迁移到 LO 层 | **YES WITH GAP** | 规则可直接套用；需先实现 LO 聚合（当前为 item 级） |
| 6 | Diagnosis 是否可迁移到 LO 层 | **YES WITH GAP** | 规则不变，输入换成 LO 证据集合 |
| 7 | Suggestion 与 Action 是否已清晰分离 | **YES** | C-3 已定义六概念分离，展示/点击/开始/完成各不相同 |
| 8 | Action 是否需要独立持久化 | **YES WITH GAP** | 证据闭环不依赖它；但要区分"未处理/已尝试"必须有它，可延期 |
| 9 | Current Error 是否可可靠重新判断 | **YES** | 由 LO 最新有效证据派生，读时重算 |
| 10 | Historical Error 是否完全安全 | **YES** | append-only；本轮实测 learning_record 未被修改 |
| 11 | Re-diagnosis 是否真正闭环 | **YES** | 读时派生；真实数据已验证跨 item 同 LO（eraser 等 4 例） |
| 12 | frozen pool 与 Diagnosis 是否可安全共存 | **YES** | 事实层 vs 结论层，语义互补；D 不改 pool |
| 13 | AI 是否仍不是闭环必需节点 | **YES** | 全链路确定性规则；AI 调用 0 |
| 14 | 是否需要修改 V1.2 | **NO** | 设计与 V1.2 一致；仅 speaking/reflection 类型决策未来可能触发同步 |
| 15 | **现在是否可以进入 P2-6-D** | **YES WITH GAP** | 无阻塞项；按 §25 边界实施，并先收口 G3/G4/G5 三项 D 前置口径 |
