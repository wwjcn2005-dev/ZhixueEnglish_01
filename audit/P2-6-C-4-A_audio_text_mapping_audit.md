# P2-6-C-4-A Audio–Text Mapping Audit

> **只读专项审计。** 未修改任何代码 / 测试 / 数据库 / contentpack / 教材 / 音频 / V1.2 / P2-4 / P2-5 / Android；未创建派生音频；未调用 AI。
> 审计对象：54 个官方教材音频与教材文字（Activity / Text / Dialogue / Question）的对应关系。

- 审计时间：2026-09-13 ｜ 项目：`D:\ZhixueEnglish`
- 产出：本文件 + `P2-6-C-4-A_audio_text_mapping_audit.json`（含完整 54 行 mapping 表）

---

## 1. Executive Conclusion

**PASS WITH GAPS**（对应任务书判定档 **B**：存在局部数据缺口，但不改变 LO 模型；无系统性错配）

**关键结论**：**未发现任何真实 Audio↔Text 错配**。"页面文字很短但音频很长"是**教材完整材料音频的正常现象**（可见文字多为**活动指令**，音频覆盖的是同一活动中教材印刷的**完整对话/语篇**），而非错误绑定。

## 2. Why This Audit Was Added

真实使用中发现"短文字 + 长音频"现象，需确认它是**教材完整材料音频**还是**错误绑定**。本专项以教材结构、活动指令、题数与题型、对话文本、音频元数据与既有证据链综合判断，**不以时长单独判错**。

## 3. Scope

54 个官方教材 MP3 与教材文字的全量结构对应；语义范围分类；是否需要切分；对 Listening LO、Evidence、C-4 与 P2-6-D 的影响。**不含声学内容确认**（无转写数据，见 §11）。

## 4. Source Documents

`audit/P2-6-C-4_full_chain_design_review.md/json`、`P2-6-C-2_*`、`P2-6-C-3_*`、V1.2（docx + md）；数据源：`structured/contentpack/v5/*.sqlite`（audio_asset / audio_mapping / activity / content_block）、`structured/audio/exercise_audio_map_v3.json`、`structured/textbook/textbook_content_relations_v2.json`、`structured/exercises/exercise_catalog_v3.json`、`exercise_question_relations_v3.json`、教材目录下 54 个 MP3（只读）。

## 5. Audio Inventory

| 项目 | 数值 |
| --- | --- |
| 官方音频总数 | **54** |
| 可定位（audio_asset + 映射 + 文件存在） | **54 / 54** |
| 时长范围 | 33.6 s – 191.7 s（中位数 **78.0 s**） |
| 类型分布 | exercise 41、word_list 7、phonetics 6 |
| 映射状态（P2-3 证据链） | 全部 **CONFIRMED**（0 NEEDS_REVIEW） |
| 教材分册 | FLTRP-EN-7A-2022CUR（外研版七上） |

**时长分布是本次审计的重要证据**：**全部 54 条均落在 33–192 秒区间**（含"Listen and choose."这类短指令活动对应 58 秒音频）。若存在"短文字错误绑定长音频"，应出现**时长异常分散/离群**，但实测分布连续且集中在 1–3 分钟（教学录音含停顿的正常长度）。→ 支持"完整材料音频"结论。

## 6. Text Inventory

| 项目 | 数值 |
| --- | --- |
| 教材活动 | 157（其中 93 有 contentpack `activity_id`） |
| 教材题目 | 360（含题型分布 fill 45 / short_answer 34 / reflection 18 / speaking 16 / other 14 / choice 12 / match 9 / writing 7 / order 1 / judge 1） |
| 内容块（含文本） | 3,854 行，其中 `dialogue` 132 行、`instruction` 194 行 |
| 活动↔文本块关系 | `textbook_content_relations_v2.json` 的 `text_references` 875 条 |
| 听力脚本（transcript） | **0 行（无转写）** |

**文字侧证据覆盖率（本专项实测）**：54 条音频中 **29 条**可关联到活动文本块或本页对话文本；**25 条无文字证据**，其中 **13 条为词表/语音音频（结构性正常，本就不对应活动文本）**，**12 条为真实数据缺口**（见 §11）。

## 7. Audio–Text Mapping Model

```
Audio Resource（教材官方 MP3，原样保留）
      ↓ 由 P2-3 证据链确认（单元 + 板块 + 活动号 + 指令文本 + 耳机图标）
Activity（教材任务容器）/ Word-List / Phonetics Box
      ↓ text_references（activity → content_block）
Text（对话 / 语篇 / 指令 / 词条）
      ↓ 语义范围判定（本专项）
semantic_scope（listening_task | reading_passage_or_dialogue | model_demo_audio |
                unit_word_list | phonetics_box | unknown）
      ↓
Learning Object（Listening LO / Reading LO / Vocabulary LO …）
```

**关系方向**：`Learning Object → Audio Resource`（资源服务于学习对象），**同时**允许 `一个 Audio → 多个 LO`（词表音频）。资源不被复制，LO 与资源为多对多。

## 8. Semantic Scope Classification

| semantic_scope | 数量 | 说明 |
| --- | --- | --- |
| listening_task（教材听力任务） | 31 | 带耳机图标的听力活动音频，覆盖该活动全部题目 |
| reading_passage_or_dialogue（语篇朗读） | 5 | 课文/语篇的朗读支撑音频 |
| model_demo_audio（口语示范） | 4 | Work in pairs / Talk / Discuss 类活动的示范音频 |
| unit_word_list（单元词表） | 7 | 一个音频覆盖该单元全部词条 |
| phonetics_box（语音小栏） | 6 | 一个音频覆盖语音小栏全部条目 |
| unknown | 1 | 文字侧证据不足（见 §11） |

**mapping_class 统计**

| class | 数量 |
| --- | --- |
| FULL_LISTENING_MATERIAL | **40** |
| MULTI_TEXT_ONE_AUDIO | **13** |
| INSUFFICIENT_EVIDENCE | **1** |
| EXACT_MATCH | 0 |
| FULL_DIALOGUE | 0（对话类已并入上面两类；实测含对话文本证据的音频 4 条：14 / 23 / 32 / 34） |
| PARTIAL_TEXT_REFERENCE | 0 |
| **POSSIBLE_MISMATCH** | **0** |
| UNMAPPED | 0 |

## 9. Full Dialogue / Listening Analysis

- **完整对话**：教材 Developing ideas 的听力活动（如 U1 A3 "Listen to the conversation and complete the table"、U3 A3、U4 A3、U5 A3、U6 A3）音频时长 140–192 秒、题数 1–5、题型 fill/match → **一个音频服务一个完整听力任务**。
- **完整语篇**：Understanding ideas / Reading for writing 的朗读音频（如 U1 A2、U2 A2、U4 A2、U5 A2、U6 A2）时长 105–132 秒 → 教材语篇朗读，非"单句音频"。
- **词表音频**：7 条，90–112 秒，覆盖整单元词表（32–46 词条）→ 典型"一音频多文本"。
- **语音音频**：6 条，49–68 秒，覆盖 Phonetics in use 小栏全部条目。

## 10. Short Text + Long Audio Analysis

**现象成立，但性质为"正常完整材料音频"**。判定依据（按任务书优先级，时长排在最后）：

1. **教材结构**：这些音频对应的活动，其教材页面上印有**完整对话/语篇**（如 Starter Get ready A2 "Read and complete. Then listen and check." 对应页面上 2 组对话，含 9 个空）；
2. **活动指令**：指令文本（"Listen and complete…"）本身**不是被朗读的内容**，而是任务说明；
3. **题目数量与题型**：对应活动题数 1–6、题型 fill/choice/order/judge/match → 说明音频需覆盖**多题信息**；
4. **音频元数据**：54 条时长连续分布（33–192 s，中位 78 s），无离群；
5. **既有证据链**：P2-3 以"文件名 + 单元 + 板块 + 活动号 + 指令文本相似度 + 耳机图标"判定 **54/54 CONFIRMED**，本次未发现任何反例。

→ 标记 `possible_full_material_audio = true`（54 条中凡属听力/阅读/词表/语音者），**不判错**。

## 11. Suspected Mismatches

**confirmed_mismatches = 0**；**possible_mismatches = 0**。

但存在 **1 类数据缺口（非错配）**：

| 缺口 | 数量 | 说明 | 处置 |
| --- | --- | --- | --- |
| 文字侧无法关联（真实缺口） | **12** | 活动有题目但 `text_references` 未覆盖其文本块（如 01/02/03/09/16/20/21/27/37/41/43/47） | 记为 `text_evidence: missing`；**不判错**；属 P2-4 文本关系覆盖缺口，建议 D 阶段列为已知 GAP |
| 文字侧结构性不适用 | 13 | 7 词表 + 6 语音音频本就不对应活动文本 | 正常 |
| **无转写** | 54（全部） | `transcript` 表 0 行 → **无法进行声学确认** | 明确声明：本次仅完成**结构性审计**，未听音频、不做声学判定 |

**结论**："文字很短 + 音频很长"中，凡能定位到教材文本的案例，均可在教材页面中找到对应的完整对话/语篇；不能定位的 12 条属**文本关系数据缺口**，而非音频绑定错误。

## 12. Split Decision

| 决策 | 数量 | 对象 |
| --- | --- | --- |
| KEEP_AS_FULL_AUDIO | **41** | 全部听力任务（31）、语篇朗读（5）、口语示范（4）、1 条证据不足但绑定已确认者 |
| DERIVED_SEGMENT_POSSIBLE | **13** | 7 词表 + 6 语音（教材结构支持按条目切分，但当前无需切） |
| **SPLIT_REQUIRED** | **0** | — |
| HUMAN_REVIEW_REQUIRED | **0** | — |

**重要先例（项目已有做法）**：词表音频**已经**按教材词条派生为 288 个逐词 WAV（P2-1-C1），且**原始 MP3 完整保留**（`structured/audio/derived/words/` + `word_audio_manifest.json` 含 start_ms/end_ms）。→ 未来任何切分必须遵循同一原则：**保留原始音频 + 生成派生片段 + 不覆盖不删除**。**本次未创建任何派生音频。**

## 13. Listening LO Impact

| # | 问题 | 判定 |
| --- | --- | --- |
| 1 | Listening LO 应对应一句话？ | ❌ 否 |
| 2 | 应对应一个完整听力任务？ | ✅ **是**（C-2 设计正确） |
| 3 | 应对应一个完整 Dialogue？ | ⚠️ 对话是材料形态，**任务才是 LO 边界**（一个任务可含对话 + 题目） |
| 4 | 其他？ | ❌ |

**结论：当前 Listening LO 粒度正确**（`listen|<textbook>|<unit>|<section>|<activity_no>`），不需要因为"音频很长"而改粒度。

## 14. Evidence Impact

- **播放音频 ≠ Evidence**（现有实现正确：播放不产生 `learning_record`）；
- Listening Evidence 只能来自**作答产生 correct/incorrect/partial**（现有 `evidence_service` 已如此）；
- **听完音频 ≠ mastery +1**（无此逻辑）；
- 本次未发现任何"播放即记证据"的路径。

## 15. C-4 Impact

**情况 2**（多个 Audio/Text 关系存在数据缺口，但 LO 模型仍成立）→ **C-4 结论保持 PASS WITH GAPS**，本专项结果作为 **D 前置 GAP**：

1. **G-Audio-1**：12 条音频缺文字侧关联（P2-4 `text_references` 覆盖不足）——影响"文字↔音频"的审计可读性，**不影响**音频绑定正确性；
2. **G-Audio-2**：无转写（transcript 0 行）→ 无法声学确认；若未来需要"音频内容级"校验，需先建立转写（属独立课题，且不得用外部 AI 擅自生成）；
3. **G-Audio-3**：词表/语音音频为"一音频多文本、一资源多 LO"，D 阶段需明确**资源语义不复制**（一条资源服务多个 LO，LO 各自独立判定）。

## 16. Normal Cases（3 个）

**Normal 1｜Starter Get ready A2（`01_…Read and complete. Then listen and check.mp3`，60.7 s，题数 4/fill）**

```
教材结构：Starter / GET_READY / A2 / 教材 p3
文字：指令"Read and complete. Then listen and check." + 页面印刷对话（Li Ming / Li Meng，9 个空）
Audio：60.7 s
上下文：教材设计为"先读后听核对"，音频即该段完整对话
当前绑定：exercise → activity（P2-3 CONFIRMED）
判断：FULL_LISTENING_MATERIAL，KEEP_AS_FULL_AUDIO（正常）
```

**Normal 2｜Unit 1 Developing ideas A3（`12_…Listen to the conversation and complete the table.mp3`，175.0 s，题数 3/fill）**

```
教材结构：Unit 1 / DEVELOPING_IDEAS / A3 / 教材 p23
文字：关联文本块 154 words（对话 + 表格）
Audio：175.0 s ≈ 154 words 的朗读 + 教学停顿（≈0.9 words/s，符合教学录音节奏）
判断：FULL_LISTENING_MATERIAL，KEEP_AS_FULL_AUDIO（正常）
```

**Normal 3｜Unit 2 Words and expressions（`50_…Words and expressions-Unit 2.mp3`，112.3 s）**

```
教材结构：Unit 2 / 词表（附录 Words and expressions）
文字：45 个词条（一词一条）
Audio：112.3 s ≈ 每词条 2.5 s（词 + 释义 + 停顿）
判断：MULTI_TEXT_ONE_AUDIO（一音频多文本），DERIVED_SEGMENT_POSSIBLE（逐词片段已派生且原音频保留）
```

## 17. Problem Cases（3 个）

本专项**未发现真正的错误绑定**；以下 3 例是**最重要的问题候选**，全部判为"数据缺口/正常完整材料"，不判错：

**Problem 1｜`02_Starter_Get ready_3 Listen and complete the conversation…`（33.6 s，题数 1）**

```
教材结构：Starter / GET_READY / A3 / 教材 p3
文字：无关联文本块、本页无 dialogue 记录（text_evidence missing）
Audio：33.6 s（对应 12 个数字/冠词填空的对话）
当前绑定：P2-3 CONFIRMED（指令相似度 1.00）
判断：INSUFFICIENT_EVIDENCE（仅"文字侧证据不足"）→ split=KEEP_AS_FULL_AUDIO
处置：列入 G-Audio-1，D 阶段不因此阻塞
```

**Problem 2｜12 条"文字侧无关联"音频集合（01/02/03/09/16/20/21/27/37/41/43/47）**

```
共同特征：活动有 1–6 道题（fill/choice/short_answer），但 text_references 未覆盖其文本块
判断：绑定正确（指令与文件名一致 + 题型/题数匹配），文字关系数据缺口
处置：G-Audio-1；建议 D 阶段补齐 text_references 覆盖率（不改教材、不改音频）
```

**Problem 3｜"短指令 + 长音频"的观感（如 `03_…Listen and choose.mp3` 58.2 s，页面仅显示一句指令）**

```
教材结构：Starter / GET_READY / A10 / 教材 p5（Listen and choose，6 题选择）
文字：指令极短；选项/对话内容在教材页面与音频中
Audio：58.2 s（含 6 题的完整听力材料）
判断：FULL_LISTENING_MATERIAL（正常）— 时长由"材料完整度"决定，不由"可见文字长度"决定
处置：无需修改；若 UI 需要，应展示"这是一段完整听力材料"的说明，而非缩短音频
```

## 18. Acceptance Criteria

| 编号 | 验收标准 |
| --- | --- |
| AM-01 | 54 条音频全部可定位（asset + 映射 + 文件存在） |
| AM-02 | 每条音频给出 semantic_scope 与 mapping_class |
| AM-03 | 不以时长单独判错（判定含教材结构/指令/题数/题型证据） |
| AM-04 | 无证据支持的错配不得断言（本次 POSSIBLE_MISMATCH = 0） |
| AM-05 | 文字侧缺口如实登记（12 条），不隐藏、不伪造 |
| AM-06 | 明确声明无转写、未做声学确认 |
| AM-07 | 切分决策四分类齐备（KEEP 41 / DERIVED 13 / SPLIT 0 / HUMAN 0） |
| AM-08 | 若切分必须保留原始音频（本次未创建任何派生音频） |
| AM-09 | 播放音频不得成为 Evidence（现有实现已满足） |
| AM-10 | Listening LO 粒度不因音频时长改变 |
| AM-11 | 不修改任何正式数据 / 音频 / 代码 / 规范 / 测试 |
| AM-12 | AI 调用 0 |

## 19. Open Issues

1. **G-Audio-1**：12 条音频缺文字侧关联（P2-4 text_references 覆盖不足）→ 建议 D 前置或并行补齐（不改教材）；
2. **G-Audio-2**：无转写（0 行）→ 声学级校验暂不可行；若未来需要，须建立转写且**不得调用外部 AI**（属独立课题）；
3. **G-Audio-3**：词表/语音音频为"一音频多文本/多 LO"，D 需明确资源语义不复制；
4. **多段听力任务的判定**：教材同一活动含多个听力子任务（如 U1 A1/A2/A3 三段音频）时，当前实现已分别建音频，**无需切分**；若未来出现"一个文件含多子任务"，须人工确认（本次未发现此类案例）。

## 20. P2-6-D Impact

- **不阻塞**：Listening LO 与 Audio Resource 的映射关系可直接实施；
- **D 前置/并行项**：把 G-Audio-1（12 条文字关联缺口）列入已知 GAP 清单，并在展示层**如实标注**（不得声称 100% 文字关联）；
- **D 需明确的口径**：① 资源与 LO 多对多、不复制资源语义；② 播放不产生证据；③ 音频保持完整，不因 UI 需要而切分；
- **D 不得做**：创建派生音频、修改原始 MP3、把播放行为记入 Evidence。

## 21. Protection Baseline

| 项目 | 结果 |
| --- | --- |
| 代码 / 测试 | 未修改 |
| `learning.db` | 未修改（SHA16 `DBAB743BF6D8F0A3`，mtime `2026-09-12 23:15:13`） |
| contentpack | 未修改（`ACEBC8C29CF5D11B`） |
| 教材 / 音频 | 未修改（54 个 MP3 未触碰；未创建派生音频） |
| V1.2 / P2-4 / P2-5 / Android | 未修改 |
| AI 调用 | **0** |
| 新增文件 | 仅本报告与 JSON |

## 22. Tests

| 套件 | 结果 |
| --- | --- |
| learning | 89 PASS / 0 FAIL / 0 SKIP |
| workbench | 50 PASS / 0 FAIL / 0 SKIP |
| web | 224 PASS / 0 FAIL / 0 SKIP |
| **合计** | **363 PASS / 0 FAIL / 0 SKIP**（只读执行，与基线一致） |

## 23. AI Calls

**0**（未使用任何外部语音识别/大模型服务；未生成新转写）。

## 24. Final Recommendation

**PASS WITH GAPS → 不阻塞 P2-6-D。**

Audio↔Text 基本可靠：**0 个确认错配、0 个疑似错配**；"短文字 + 长音频"确认为教材完整材料音频的正常形态；13 条词表/语音音频存在"一音频多文本"（已有派生先例，原音频保留）。
需随 D 一并处理的 3 项 GAP：**12 条文字侧关联缺口（G-Audio-1）**、**无转写导致无法声学确认（G-Audio-2）**、**资源与 LO 多对多的口径（G-Audio-3）**。
**建议人工听音频的音频数 = 0**（无错配疑点）；若产品要求"音频内容级"确认，需先建立转写能力（独立课题，本轮不做）。

---

### 附录：12 个必答问题

| # | 问题 | 结论 | 理由 |
| --- | --- | --- | --- |
| 1 | 54 个 Audio 是否全部能定位 | **YES** | asset + 映射 + 文件三者齐备（54/54） |
| 2 | 是否存在真实 Audio↔Text 错配 | **NO** | 未发现；P2-3 证据链 54/54 CONFIRMED 且无反例 |
| 3 | 是否存在"一小段文字 + 长对话音频" | **YES** | 结构性存在（可见文字多为指令，音频为完整材料） |
| 4 | 是正常完整材料还是错误绑定 | **正常完整材料** | 时长分布连续、题数/题型匹配、教材页面含完整对话/语篇 |
| 5 | 哪些 Audio 属于完整 Dialogue | **YES WITH GAP** | 含对话文本证据者 4 条（14/23/32/34）；对话类听力活动并入 listening_task |
| 6 | 哪些 Audio 属于完整 Listening Material | **YES** | 40 条（31 听力任务 + 5 语篇朗读 + 4 口语示范） |
| 7 | 一个 Audio 是否对应多个文本 | **YES** | 13 条（7 词表 + 6 语音） |
| 8 | 一个 Audio 是否对应多个 LO | **YES WITH GAP** | 词表音频服务整单元词条 LO；需明确资源不复制、LO 独立判定 |
| 9 | 当前 Listening LO 粒度是否正确 | **YES** | 一个教材听力任务 = 一个 LO（不是一句） |
| 10 | 哪些 Audio 应保持完整 | **YES** | 41 条 KEEP_AS_FULL_AUDIO（含全部听力/朗读/示范音频） |
| 11 | 哪些 Audio 有必要未来切分 | **YES WITH GAP** | 13 条 DERIVED_SEGMENT_POSSIBLE（词表 7 / 语音 6）；SPLIT_REQUIRED 0 |
| 12 | 是否改变 C-4 / 阻塞 P2-6-D | **NO（PASS WITH GAPS）** | C-4 保持；本专项作为 D 前置 GAP（G-Audio-1/2/3） |
