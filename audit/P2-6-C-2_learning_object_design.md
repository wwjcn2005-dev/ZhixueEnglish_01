# P2-6-C-2 Learning Object 语义、映射与证据聚集粒度设计

> **设计任务，不实施。** 本轮未修改任何代码 / 数据库 / 教材 / 规范 / 测试，未调用 AI。
> 输入基线：P2-6-C-1（PASS WITH GAPS）、P2-6-A/B 归档、规范 V1.2、`mastery_rules_v1.json`。
> 设计铁律：**教材语义优先于 mastery 算法条件**——绝不为凑「≥2 task types」而合并教材上无语义关系的对象。

- 设计时间：2026-09-13
- 项目：`D:\ZhixueEnglish`
- 产出：本文件 + `P2-6-C-2_learning_object_design.json`

---

## 1. 执行结论

**PASS_WITH_GAPS**

可以定义一个**确定性、可重复生成、与数据库主键解耦**的 Learning Object 模型；映射规则无歧义，但**当前教材数据结构只支撑 89/157（56.7%）练习的 LO 归属**，其余 43% 必须在后续阶段决定“新增 LO 类型”或“保持 unmapped”。因此设计成立、实施需先补齐前置条件。

## 2. 设计范围

仅设计：① LO 语义与类型体系；② 稳定 ID / Canonical Key；③ 来源 → LO 的确定性映射规则；④ Evidence 聚集粒度与去重模型；⑤ Mastery 粒度；⑥ 历史数据兼容方案；⑦ 对 frozen service / 数据库 / V1.2 的影响判断；⑧ 实施前置条件与验收标准。

不设计（留给后续阶段）：巩固动作记录（Consolidation Action）结构、阶段验证、专项学习、任何 UI 与算法实现。

## 3. 输入基线

| 项 | 值 |
| --- | --- |
| P2-6-C-1 | PASS WITH GAPS（20/20 记录可定位教材位置；1,512 条 `related_vocabulary` 100% 唯一解析；288 词面唯一；157 练习 `exercise_id ≡ item_id`；词汇与练习 item_id 零交集；无 LO 实现；mastery = learner+item；Evidence 键含 item_id；无 consolidation action；grammar 仅 13 条指针） |
| P2-6-A/B | 掌握判定五项条件已实现（item 级）；363 PASS |
| 规范 | V1.2 第二十二章（LO 定义、学过≠掌握、证据优先、教材优先巩固、AI 边界、孩子自主） |

**本轮新增只读验证（为本设计提供数据支撑）**

| 验证项 | 结果 |
| --- | --- |
| 练习携带 contentpack `activity_id` | 93 / 157（64 个 P2-3 新增活动无 activity 行 → 无题目关系） |
| 题目 `related_vocabulary` 命中本单元 CORE 词 | 唯一 1 个：**12**；≥2 个：**12**；无候选：**133** |
| 按推荐规则映射结果 | LO-LISTENING **21** / LO-READING **37** / LO-WRITING **7** / LO-VOCAB(single) **12** / LO-VOCAB(multi) **12** / **unmapped 68** |
| 历史 20 条记录在新规则下的归属 | LO-VOCAB **14** / LO-LISTENING **6** / unmapped **0**（20/20 可映射） |

## 4. V1.2 原则约束（设计必须满足）

1. Learning Object 用于**聚合与诊断**；Activity 是任务容器；Exercise/Question 是产生证据的任务（二十二·3）。
2. 学过只是事实；掌握较稳定需多维证据且五参数为可调整工程参数（二十二·4）。
3. 只看过/听过/自评不能单独证明；同段重复不计独立证据；**一次错误不等于薄弱**（二十二·5）。
4. 巩固教材优先（二十二·6）；AI 不得决定路径或越界（二十二·7）；孩子自主、不自动推进（二十二·2）。

**设计含义**：LO 必须由教材事实决定（不能由算法条件反推），且必须支持“同一 LO 多任务证据汇聚”，但**汇聚必须来自教材语义上的同一学习内容**。

---

## 5. 概念边界（六个概念，不得混用）

| 概念 | 是什么 | 不是什么 |
| --- | --- | --- |
| **Learning Object** | 教材中**可独立讨论掌握状态**的最小学习内容（词/短语/句型/听力任务/阅读文本/写作任务） | 不是任务容器、不是题目、不是资源文件、不是教材位置 |
| **Activity** | 教材上的**任务容器**（活动编号 + 指令 + 版式） | 不是知识对象；一个 Activity 可涉及多个 LO |
| **Exercise / Question** | 教材练习与其题目，是**证据产生器** | 不是 LO；答对不等于掌握 |
| **Evidence** | 一次**有效判断**的派生事实（有来源记录、任务类型、自然日） | 不是学习次数、不是自评、不是 AI 结论 |
| **Resource** | 教材文本、官方音频、语法提示页、Model Text、词汇表、练习册页等**素材** | 素材本身不是 LO（但可作为建议定位与证据来源） |
| **Textbook Location** | 教材位置（unit/section/activity/页码） | 位置不是学习内容，不能作为掌握对象 |

## 6. Learning Object 正式定义

> **Learning Object（学习对象）**：教材中具有明确教学语义、可被一个或多个合法教材任务共同提供学习证据、并能够独立讨论其掌握状态的最小学习内容单元。

边界规则：

1. **必须**对应教材已有内容（可回溯到 unit/section/activity/页码或词表条目）；
2. **允许多个** Activity / Exercise 为之提供证据；
3. **允许多条** Evidence；
4. **拥有独立 mastery**（判定对象）；
5. **可被孩子主动学习**（孩子可从教材主线直接进入该 LO 对应的教材内容）；
6. **不得**由任务或题目充当；**不得**由 Unit/Section 充当（避免“万能 LO”）；
7. 一个 LO 的粒度标准：**小到可以独立讨论“会不会”，大到能让不同任务产生有意义的证据汇聚**。

## 7. LO 类型设计

| 类型 | 建议成为 LO | 教材语义依据 | 已有数据基础 | 当前可映射 | 风险 |
| --- | --- | --- | --- | --- | --- |
| **Vocabulary（words）** | ✅ 是 | 词表条目（Words and expressions）是教材权威学习单位 | 288 条、词面唯一、含音标/词性/释义/教材页/逐词音频 | ✅ 确定性 | 同词不同义（当前无案例） |
| **Phrase** | ✅ 是 | 教材词表内的固定搭配，独立教学条 目 | 23 条（item_type=phrase） | ✅ 确定性 | 与 Vocabulary 边界（含空格的词条） |
| **Sentence Pattern** | ✅ 是 | 教材句型条 目 | 52 条（item_type=sentence_pattern） | ✅ 确定性 | 与语法 LO 的边界 |
| **Listening Task** | ✅ 是 | 教材带耳机图标的听力活动（音频 + 任务） | 21 个活动 + 官方音频 + 题型 | ✅ 确定性 | 一个音频对应多题时证据归属需共享 |
| **Reading Text** | ✅ 是 | Understanding ideas / Reading for writing 的课文 | 37 个练习可回溯到文本 | ✅ 确定性 | 短答与反思需区分 |
| **Writing Task** | ✅ 是 | Reading for writing / Presenting ideas 的写作任务 | 7 个写作练习 + Model Text | ✅ 确定性 | 评分主观（未来 AI 域） |
| **Grammar Point** | ⚠️ 设计上应存在，**工程暂缓** | 教材“Know more about … pNN”指针 7 条 | ❌ 无 grammar resource / task / evidence 对象 | ❌ 暂不可映射 | 强行实施会制造无依据对象 |
| **Exercise 作为 LO** | ❌ 否 | 题目是证据产生器 | — | — | 会退化为刷题系统 |
| **Speaking / Reflection** | ❌ 暂不定为 LO | V1.2 未列；当前无独立教材资源对象 | 16 + 18 个活动 | ❌ | 不发明类型；其证据归 `unmapped` |
| **Integrated / Cross-section LO** | ❌ 本阶段不做 | 无教材依据支撑“跨板块合并” | — | — | 直接导致“万能 LO” |

## 8. Vocabulary LO（含 Phrase / Sentence Pattern）

**粒度判定：每个教材词条 = 1 个 LO（全局，不按 Unit 重复）**。

依据：
1. 教材词表每个词条只有**一条**权威条目（288 词面 100% 唯一，无重名、无多 item_id）；
2. 词条的 `primary_unit` 是**属性**（“这个词在哪个单元被教”），不是身份的一部分；同一个词在不同单元正文出现，不构成不同的学习对象；
3. 若未来出现**同词不同义**（同一词面在不同 unit 给出不同 `meaning_zh`），则启用 `sense` 判别位（见 §13）——当前数据**无此案例**，不做提前拆分。

**三层键（设计）**

| 键 | 形式 | 用途 |
| --- | --- | --- |
| business key | `word_lexeme`（教材词条身份，等价于 `learning_item.item_id` 的语义） | 业务讨论与去重 |
| source key | `learning_item.item_id`（`V:*`） | 教材事实溯源 |
| canonical key | `vocab|<textbook_id>|<normalized_lexeme>|<pos>|<sense:`（`sense` 当前为空） | 生成稳定 LO ID |
| display key | `canonical_text`（+ 音标/词性） | 展示 |

## 9. Exercise → LO 映射（确定性规则，按优先级）

规则（自上而下，命中即止；均只用现有教材事实）：

```
R1  listening_icon == true 或 audio_required == true        → LO-LISTENING（该活动）
R2  question_type == 'writing'                              → LO-WRITING（该活动/范文）
R3  question_type ∈ {short_answer, choice, judge, order, match, fill}
    且 section ∈ {UNDERSTANDING_IDEAS, READING_FOR_WRITING}
    且 该活动有 related_text（P2-4）                          → LO-READING（该阅读文本）
R4  本单元 CORE 词候选 == 1                                  → LO-VOCAB（该词）
R5  本单元 CORE 词候选 ≥ 2                                   → LO-VOCAB × N（**共享证据**）
R6  以上都不成立                                             → unmapped（不强行归属）
```

**关键判断：`related_vocabulary` 不足以单独作为正式确定性映射。** 实测：157 个练习中“本单元 CORE 词唯一”的只有 **12** 个，≥2 个 **12** 个，其余 **133** 个无 CORE 候选（其中 64 个连 `activity_id` 都没有，因不在 contentpack.activity 中）。→ `related_vocabulary` 只能作为**候选线索**（R4/R5 的输入之一），不能作为唯一依据。

**映射覆盖率（实测）**：LO-LISTENING 21 + LO-READING 37 + LO-WRITING 7 + LO-VOCAB(single) 12 + LO-VOCAB(multi) 12 = **89/157（56.7%）**；**unmapped 68（43.3%）**——主要是 speaking(16)、reflection(18)、other(14)、无候选的 match/fill 等。**该 43% 必须在 P2-6-C-3 明确处置**（新增类型 or 保持 unmapped），本阶段不擅自扩张类型。

## 10. Question → LO

- Question 是**证据最小来源**，不直接持有 LO；映射通过其所属 Exercise 的规则（§9）继承。
- **多 LO 情形选择：方案 A —— 一条 Evidence + 多个 LO 引用**（而不是为每个 LO 复制一条 Evidence）。
  理由：① 避免同一作答被计为多次独立证据（违反“重复动作不能无限增加证据权重”）；② 保留“一次作答同时暴露多个学习内容”的真实语义；③ 反查与统计更简单（`evidence.learning_object_ids[]`）。
- 实测多 LO 候选（R5）**12 个练习**，说明该情形真实存在，必须支持。

## 11. Grammar LO

- **设计上应存在**（V1.2 明确“语法点”属学习对象）；
- **当前工程不能实施**：无 grammar resource / grammar task / grammar evidence，仅有 13 条教材指针（7 语法 + 6 语音）；
- **暂缓理由**：没有教材资源对象就没有可信的 LO 身份与证据来源；强行创建等于制造教材事实；
- **将来进入的最小教材数据基础**：① 教材语法条目（topic + 教材页 + 教材例句）② 与之关联的教材练习（哪些题在考该语法点，且要有可核对的教材证据）③ 题型/证据来源。三者齐备前，语法题证据一律归 `unmapped`。

## 12. Text / Listening / Writing LO

| 类型 | 身份（canonical） | 证据来源 | 备注 |
| --- | --- | --- | --- |
| Reading Text | `read|<textbook_id>|<unit>|<section>|<textbook_page>` | 该文本相关的阅读理解/短答题（R3） | 以教材“一篇文章/一段对话”为单位；不跨 section 合并 |
| Listening Task | `list|<textbook_id>|<unit>|<section>|A<activity_no>` | 该活动题目（R1），共享同一音频 | 活动=听力任务的教材载体（音频+任务），非 Exercise |
| Writing Task | `write|<textbook_id>|<unit>|<section>|A<activity_no>` | 写作任务提交（R2） | 与 Model Text 关联（教材范文） |

---

## 13. 稳定 ID / Canonical Key

**格式**

```
LO:<textbook_id>:<LO_TYPE>:<canonical_key>
```

- `LO_TYPE` ∈ `VOCAB | PHRASE | PATTERN | LISTENING | READING | WRITING`（Grammar 待定，暂不产号）；
- `canonical_key` = `sha256(canonical_string)` 前 12 位大写；**仅用于压缩长度，不携带语义**；
- `canonical_string` 完全由教材事实构成，**与 learning_record / mastery / evidence 数量无关**。

**canonical_string 规则**

| 类型 | canonical_string |
| --- | --- |
| VOCAB / PHRASE / PATTERN | `lex|<textbook_id>|<kind>|<normalized_lexeme>|<pos>|<sense>` |
| LISTENING | `listen|<textbook_id>|<unit>|<section>|<activity_no>` |
| READING | `read|<textbook_id>|<unit>|<section>|<textbook_page>` |
| WRITING | `write|<textbook_id>|<unit>|<section>|<activity_no>` |

**规范化规则（必须固定）**

1. Unicode **NFC**；英文**转小写**；中文保持原样；
2. 去除首尾空白，内部连续空白折叠为 1 个空格；
3. 去除词条末尾的标点（`. , ; :`），**保留**词内连字符 `-` 与撇号 `'`（如 `point out`、`each other`、`don't`）；
4. `pos` 取教材词性（无则空串），`sense` 取词义判别位（当前恒空）；
5. 数字与符号不做额外改写（如 `3D`、`T-shirt` 原样小写）。

**参与 / 不参与 canonical 的字段**

| 参与 | 不参与（绝不参与） |
| --- | --- |
| textbook_id、LO 类型、词条文本（规范化后）、词性、词义判别位、unit/section、activity_no、textbook_page | learning_record、mastery_state、evidence 数量、孩子 id、时间戳、AI 输出、数据库自增 id、任何运行时状态 |

**同词不同义的处理**：`sense` 位预留。触发条件：同一 `textbook_id` 下同一 `normalized_lexeme` 出现**不同 `meaning_zh`** 或多个 `learning_item.item_id`。当前实测 288 词面唯一、无重名 → **不启用**（保持一词一 LO）；一旦教材数据出现该情况，则按 `sense = normalize(meaning_zh)` 拆分，且**不做全局合并**。

## 14. Evidence 聚集粒度（三方案比较）

| 维度 | 方案 A：Evidence 直接加 `learning_object_id` | 方案 B：record 保持 item 粒度 + 只读聚合层派生 LO | 方案 C：独立 Evidence–LO mapping 表 |
| --- | --- | --- | --- |
| 数据污染风险 | **高**（要改 `learning_record` 写入路径；历史 20 条需回填 → 触碰正式数据） | **低**（零写入） | 中（新增表需维护一致性） |
| 兼容现有 learning_record | **破坏兼容**（需迁移） | **完全兼容**（只读派生） | 兼容（旁挂表） |
| 对 frozen service 影响 | **需改 frozen 写入路径**（违反冻结） | **无影响** | 无影响（但要新增写入方 → 引入新的写路径） |
| 对 mastery 影响 | 直接支持 LO 粒度 | 支持（聚合后判定） | 支持（需 join） |
| 历史数据兼容 | 需回填（不可接受） | **天然兼容**（现有 20 条 100% 可派生） | 需回填 mapping 行 |
| 未来扩展（grammar/text/listening） | 差（字段语义固定） | **好**（映射规则可扩展） | 好（可增量插行） |
| 是否需要 DB migration | **需要** | **不需要** | 需要（新增表） |

**推荐：方案 B（只读聚合层派生 LO），语义上采用 §10 的“一条 Evidence + 多 LO 引用”。**
理由：完全不触碰冻结服务与正式数据、历史数据天然兼容、扩展性最好；缺点是每次判定需派生（可用缓存缓解）。方案 A 被拒（污染风险 + 需迁移）；方案 C 暂缓（当前无“必须持久化 mapping”的需求，属过度设计；若将来需要一致性校验再引入）。

## 15. 去重模型（多层独立性）

```
第 1 层（最细）：同一 item 同一自然日同一 task_type 的重复作答  → 只计 1 条
第 2 层：同一 LO 同一自然日同一 task_type，但来自不同 item      → 仍只计 1 条（换题不增值）
第 3 层：同一 LO 同一自然日，不同 task_type                      → 各自独立计
第 4 层：同一 LO 跨自然日                                       → 独立计
```

**LO 级证据键**：`(learner_id, learning_object_id, evidence_date, task_type)`，保留最新一条，其余记入 `sources[]`。

**回答“两个不同 Exercise 都测同一 LO，同一天是否算两条独立证据？”** → **不算**（第 2 层）。理由：V1.2 明确“同一学习时段内的重复操作不能无限增加独立证据权重”；同一天两道同类型题只证明“当天做过两次”，不构成新的独立性维度。**但两条 item 的来源必须保留**（provenance），以便溯源与将来更细的分析。

**保留 item_id**：`evidence.sources[]` 内含 `record_id / item_id / activity_id`，item_id **不删除**。

## 16. Mastery 粒度

1. **mastery 只存在于 LO 粒度**（`learner_id + learning_object_id`）——判定对象必须是“孩子掌握了什么”。
2. **item 级 mastery 不再作为独立状态**：它是证据的**来源粒度**，不是学习状态粒度；保留双重状态会产生“同一内容两个真相”。
3. **命名约定（设计）**：`mastery_state`（LO 级，派生）与 `item_provenance`（来源，不是状态）。**本轮不改名、不动表。**
4. **聚合算法（设计，不实现）**：
   ```
   1) 由 record 派生 item 级证据（现有 evidence_service，含 done/skipped/自评排除）
   2) 由 §9 规则把每个 item 证据映射到 1..N 个 LO（共享引用）
   3) 按 (learner, LO, 自然日, task_type) 去重（§15）
   4) 对 LO 的证据集合套用 mastery_rules_v1 五项条件 → LO 状态
   ```
5. **例**：LO 有 3 条证据、2 种 task_type、2 个自然日 → 条件 1–3 满足，再检查最近 3 次 ≥2 正确与无未处理当前错误。
6. **避免错误合并**：只在 §9 规则命中时归属；R5 的多个 LO 各自独立判定（共享证据但**不合并状态**）；`unmapped` 一律不参与任何 LO 判定。
7. **同一 LO 同时有 Vocabulary Recall / Exercise / Listening**：按 task_type 分别计入；但**只有教材语义确实同属该 LO 的才计入**（例如一个听力活动只有在它是该词的教材练习时才与词 LO 关联——当前规则 R4/R5 只接受 `related_vocabulary ∩ 本单元 CORE`，不做跨单元联想）。

## 17. `mastery_rules_v1.json` 兼容性

| 判断 | 结论 |
| --- | --- |
| 规则本身（≥3 证据 / ≥2 任务类型 / ≥2 自然日 / 最近 3 次 ≥2 正确 / 无未处理当前错误） | **可继续使用**，直接套用于 LO 级证据集合（阈值不变） |
| 当前数据结构是否已支撑该规则 | **不支撑**：缺 LO 聚合层；`mastery_state` 主键仍为 item；去重键仍含 item_id |
| 需要改规则文件吗 | **不需要**（本轮未修改 JSON；阈值保持） |

## 18. 历史数据兼容

- **现有 20 条 learning_record 100% 可重新派生 LO**（实测：14 → LO-VOCAB，6 → LO-LISTENING，unmapped 0）。
- 派生方式：`record.item_id` → ① 命中 `exercise_catalog_v3` → 按 §9 规则 → LO；② 否则为词汇/短语/句型 → 按 `textbook_id + normalized_lexeme` → LO-VOCAB/PHRASE/PATTERN。
- **不修改、不删除、不清洗**任何历史记录；派生结果只读。
- 无法映射的记录（未来可能出现）：标记 **`unmapped`** 并保留原因（`missing_activity_link` / `no_vocab_candidate` / `unknown_item`），**不补造**、不计入任何 LO 判定。

## 19. 对 frozen service 的影响

**结论：方案 B（不修改 frozen service）。**

- `learning_service` / `session_service` / `activity_service` / `behavior_service` / `vocabulary_service` / `resource_pool_service` **保持冻结**：事实写入与池语义不变；
- LO 映射与聚合全部放在**新增的只读服务**（例如 `learning/learning_object_service.py` + `evidence_aggregation`），只 SELECT；
- 唯一可能的 C 情形：若将来要把 LO 级 mastery **持久化**（写库），则需要新的写路径——但**可以放在新服务里**，仍不必修改 frozen 的既有函数（届时再评估）。

## 20. 数据库影响

| 问题 | 结论 |
| --- | --- |
| LO 映射是否需要 DB | **不需要**（确定性派生层） |
| Evidence 是否需要 `learning_object_id` 字段 | **不需要**（可由 mapping layer 派生；写字段会污染事实层并需迁移） |
| Mastery 是否需要 `learner + learning_object_id` | **设计上需要**；**实施上可先只读派生**（不落库即可满足判定）；若将来要求持久化/性能/历史快照，再单独评估新表（属后续阶段） |
| 历史 learning_record | 20/20 可派生（§18）；无需任何写入 |
| 本轮是否迁移 | **否**（未执行任何 DDL/DML） |

---

## 21. AI 边界

LO 映射、Canonical Key、证据聚合、Mastery、诊断初始确定性层：**全部不使用 AI**。
AI 未来只可用于：开放题批改、复杂答案分析、教材证据范围内解释、条件允许的教材变式生成等 V1.2 允许的辅助行为。
**本阶段 AI calls = 0。**

## 22. 三个候选方案比较

| 维度 | 方案 A：最小教材对象（词/短语/句型/听力/阅读/写作各自独立 LO） | 方案 B：Unit / Section 聚合为 LO | 方案 C：混合层级（A 为叶 LO；Section/Unit 仅作归属容器，不做 mastery 对象） |
| --- | --- | --- | --- |
| 教育语义 | **强**（对应教材真实学习单位） | **弱**（“Unit 1 掌握”无法讨论） | **强**（叶 LO 可讨论，容器只做分组） |
| 数据稳定性 | 高（词表/文本/任务均有稳定键） | 高但**无意义** | 高 |
| 证据聚集能力 | 好（多任务可汇聚到叶 LO） | 表面最强，实则**混合不可解释** | 好（汇聚到叶 LO，容器不参与判定） |
| mastery 合理性 | **合理** | **不合理**（万能 LO） | **合理** |
| 扩展性 | 好（可增类型） | 差 | 好 |
| 历史数据兼容 | 20/20 可派生 | 同样可派生但含义错误 | 20/20 可派生 |
| 实施复杂度 | 中 | 低（但错误） | 中（= A + 容器概念） |
| 与 V1.2 一致性 | 高 | **低**（V1.2 明确 Learning Object 不是 Activity/Exercise；Section 更粗） | 高 |

**推荐：方案 C（叶 LO = 方案 A 的类型体系；Section / Unit 仅作为归属层级与浏览结构，不承载 mastery）。**
理由：既保留方案 A 的可解释性与可判定性，又避免把结构容器误当学习对象；同时拒绝方案 B 的“万能 LO”。

## 23. 推荐方案（正式）

1. **叶 LO 类型**：`VOCAB / PHRASE / PATTERN / LISTENING / READING / WRITING`（Grammar 待前置数据齐备后加入）；
2. **归属层级**：`Textbook → Unit → Section → Activity` 仅作**定位与浏览**，不参与 mastery；
3. **证据路径**：`Activity/Exercise/Question → Evidence → (1..N) LO → Mastery(LO)`；
4. **映射方式**：§9 的 R1–R6 确定性规则 + 只读聚合层（方案 B）；
5. **未映射**：`unmapped` 明确保留（当前 68/157 练习、0/20 历史记录）。

## 24. 边界案例（逐项处理）

| # | 案例 | 未来模型的处理 |
| --- | --- | --- |
| 1 | 同词不同义 | 当前数据无此案例；若出现，`sense` 位参与 canonical → 拆成两个 LO，**不合并** |
| 2 | 同词不同 Unit | 不拆：词条身份与 unit 无关；`primary_unit` 只作为属性（教材词表一词一条） |
| 3 | 一个 Exercise 引用多个 Vocabulary | R5：该证据**共享**给多个 VOCAB LO（一条 Evidence + 多引用），各自独立判定 |
| 4 | 一个 Question 同时考词汇和语法 | 词汇侧按 R4/R5 归属；语法侧**暂不归属**（Grammar LO 未启用），记 `unmapped(grammar)` |
| 5 | 同一题重复做三次 | 第 1 层去重：同日同 item 同 task_type → 1 条；来源全部保留 |
| 6 | 同一天做多个不同题 | 第 2 层去重：同 LO 同日同 task_type → 1 条（不同题不增值） |
| 7 | 不同自然日做同一任务 | 第 4 层：独立计数（这是“保持”的真实证据） |
| 8 | Recall 与 Exercise 都正确 | 两个不同 task_type（recall / 该题题型）→ 各自独立 → 共同满足“≥2 任务类型” |
| 9 | Recall 正确但 Exercise 错误 | 证据冲突：最近 3 次规则 + 当前错误规则生效 → 状态回落到 `likely_understood` 或 `needs_review`，**不下“已稳定”结论** |
| 10 | 一个 LO 尚没有第二种 task type | 条件 2 不满足 → 停留在非 stable（**这正是当前真实情况**，不允许为凑条件合并对象） |

## 25. 未来跨任务证据模型（示例）

> **标注：以下为设计模型示例，不是当前正式数据事实**（真实数据目前只有 LO-VOCAB 与 LO-LISTENING 两类证据，且尚无同一 LO 的多任务案例）。

```
LO:FLTRP-EN-7A-2022CUR:VOCAB:7A89AA02D979   (lexeme = "eraser", primary_unit = Starter)
   ├── Vocabulary Recall（workbench/词汇页）    D1 → E1  (recall, correct)
   ├── Exercise A（教材词表类练习，R4 命中）    D1 → E2  (match,  correct)
   └── Exercise B（另一教材练习，R4 命中）      D3 → E3  (fill,   correct)

为什么属于同一 LO：三者的教材语义都是“eraser 这个词条”（R4/R5 + 词条唯一）
为什么是不同 task types：recall / match / fill（题型来自 exercise_catalog_v3.question_type）
去重：E1 与 E2 若同属 D1 且 task_type 不同 → 各计 1；若同属 D1 且同类型 → 只计 1（保留两条来源）
natural day：D1 与 D3 构成 2 个自然日 → 满足条件 3
最近 3 次：按 LO 级证据时间顺序取最近 3 条 → 本示例为 correct/correct/correct
不增加的重复动作：同一题同日重复、同一类型同日换题 —— 都不增加独立证据
```

## 26. 实施前置条件（进入 P2-6-D 之前必须确定）

1. **unmapped 处置决策**：68/157 练习（speaking 16 / reflection 18 / other 14 / 无候选词汇类 20）是“保持 unmapped”还是“新增 LO 类型”；
2. **R5 多 LO 共享证据**的最终确认（本设计推荐方案 A：一条证据多引用）；
3. **Grammar LO 的教材数据前置条件**（语法条目 + 关联练习 + 证据来源）；
4. **Speaking / Reflection 的归属口径**（V1.2 未列 → 建议保持 unmapped，需产品确认）；
5. **LO 聚合层是否需要缓存/持久化**（当前设计为只读派生；若需要持久化再评估新表）；
6. **Consolidation Action 结构**（属 P2-6-C-3/D，本阶段不设计）。

## 27. 未来验收标准（LO-01 … LO-12 + 2）

| 编号 | 验收标准 |
| --- | --- |
| LO-01 | 同一教材对象每次生成**相同** LO ID（同输入同输出，跨进程可复现） |
| LO-02 | 不同教材对象不会错误合并（含同词不同义、不同 section 同名文本） |
| LO-03 | Vocabulary → LO 映射确定性（288/288 可映射，0 歧义） |
| LO-04 | Exercise → LO 映射确定性（同一练习每次得到相同 LO 集合；unmapped 明确标记） |
| LO-05 | 同一 LO 可关联多个合法任务来源（R4/R5 命中时） |
| LO-06 | Evidence 保留 item-level provenance（`sources[]` 含 record_id / item_id） |
| LO-07 | 重复操作不会无限增加独立证据（四层去重生效） |
| LO-08 | mastery 以 LO 为判断对象（item 级仅作来源） |
| LO-09 | 历史 learning_record 不被修改（SHA 不变） |
| LO-10 | 无法映射的历史记录不被删除（标记 unmapped 并留原因） |
| LO-11 | AI 调用 0 次 |
| LO-12 | 现有 363 个测试全部保持通过 |
| LO-13（新增） | 映射覆盖率与 unmapped 比例被如实报告（不得为提升覆盖率强行归属） |
| LO-14（新增） | 任一步骤不得写入 `learning_record` / `mastery_state`（只读派生） |

## 28. V1.2 同步需求

**无需修改 V1.2。**
理由：本设计与 V1.2 第二十二章一致（LO 用于聚合与诊断、Activity/Exercise 不是 LO、证据优先、教材优先、AI 边界、孩子自主）；所有阈值/参数仍在 `mastery_rules_v1.json`（工程参数），无需上升为规范条文。**本轮未修改 V1.2。**

## 29. 未决问题

1. 43%（68/157）练习的 `unmapped` 处置（保持 or 新增类型）；
2. Grammar LO 的教材数据前置条件何时具备；
3. Speaking / Reflection 是否应成为 LO（V1.2 未列，需产品决策）；
4. LO 级 mastery 是否需要持久化（当前建议只读派生）；
5. Consolidation Action 结构（P2-6-C-3/D）；
6. 64 个无 `activity_id` 的练习（P2-3 新增活动未入 contentpack.activity）是否补齐题目关系（会影响 R3–R5 的可用性）。

## 30. 最终结论

**PASS_WITH_GAPS**：Learning Object 的定义、类型、稳定 ID、确定性映射规则、证据聚集与去重模型、mastery 粒度、历史兼容方案均已设计完成并可解释；**无需重新设计整体模型**，也**无需修改 V1.2 / frozen service / 数据库**即可先以只读派生方式实施（除 `unmapped` 处置与 Grammar 前置条件外）。

**本阶段不实施**：不写代码、不迁库、不建表、不写数据、不接 AI。设计完成后**立即停止**，等待人工审核后再决定是否进入 P2-6-C-3 / P2-6-D。
