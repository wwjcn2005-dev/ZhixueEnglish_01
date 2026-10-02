# P2-6-F-0：教材内容、音频与练习结构修复可实施性审计

> **只读审计**：未修改任何代码 / 数据 / 教材 / 音频 / 规范 / 测试 / Android；**AI 调用 0**。
> 本阶段只回答：P2-6-E 发现的问题**能不能依据现有教材事实严谨地修**、每项修复**需要什么依据**。

- 审计时间：2026-09-13
- 项目根目录：`D:\ZhixueEnglish`
- 最高依据：`初中英语AI辅助学习系统_最高指导原则与开发规范_V1.2.docx`（SHA256 `6D3595CF…`，未修改）
- 本次新增文件：仅本报告 `.md` 与同名 `.json`（见 §14）

---

## 0. 结论摘要

| 问题 | 本次审计结论 |
| --- | --- |
| 教材事实源是否存在 | **存在且可用**：出版社原 PDF（178 页，175 页有文本层）+ contentpack v5 + 54 个官方 MP3（SHA 全对）+ P2-4 四个派生 JSON |
| 教材正文能不能恢复 | **能**：正文/阅读/对话在 `content_block`（3854 块）里是**有序、逐块、与 PDF 文本层一致**的 → `DIRECT_RESTORE`；板块归属 `DETERMINISTIC_MAPPING` |
| 音频要不要切割 | **不需要**：54 条音频里 41 条是"活动级"、13 条是"板块级"，**没有任何一条音频跨活动** → `SPLIT_REQUIRED = 0` |
| 题目结构能不能恢复 | **部分能**：选项在题干里的 5 条可确定性恢复；`options` 字段另有 **3 条是错的**（页眉/页脚噪声）；**1 条选项归属需人工看图核验** |
| 答案能不能恢复 | **不能自动恢复**：157 条练习 / 360 道题 **全部 `NO_RELIABLE_SOURCE`**；教材学生用书**没有答案页**，项目内**没有教师用书/答案文件** → 必须人工核验 |
| P1-01 的根因 | **缺的是"答案来源"**，不是缺 Question 实体、不是缺批改器、不是缺 Evidence 接口（后三者在代码里都已存在） |
| 本阶段能否开始修 | 可以，但**必须先分清两类任务**：*不需要答案就能做的*（正文接入、结构恢复、噪声清理）与 *必须先有人工核验答案才做的*（真实判分） |

> **最关键的判断**：当前项目**不能**靠"多写代码 + 多映射"把教材练习变成有效证据。有效证据的门槛是 `correct / incorrect / partial`，而这三者都要求**先有可核对的答案**；答案在当前数据源里**确定不存在**。因此"提高可作答率"这条路上，**真正的瓶颈是人工核验，而不是工程实现**。

---

## 1. 审计范围与边界

**允许**：读取文件 / 搜索代码 / 读数据库（只读打开）/ 静态分析 / 计算 SHA256 / 提取 PDF 文本层（确定性读取，非 AI）/ 运行现有测试（隔离临时库）。

**未做**（严格遵守任务书 §三）：

- 未修改任何 `.py / .html / .css / .js / .json / .db / .mp3 / .docx`
- 未改 contentpack、教材数据、音频、`exercise_catalog_v3`、`learning.db`、测试、Android
- 未新增业务代码或测试、未做迁移、未做数据清理
- **未调用任何 AI / 未联网**（本报告中的"PDF 文本层提取"使用的是本地 PyMuPDF 确定性文本读取，不是 AI、不是模型推理）
- 未根据 AI 推测教材答案、未猜音频切割位置

本次执行的测试（隔离临时库，正式库前后 SHA 一致）：

| 套件 | 结果 |
| --- | --- |
| `learning/` | 112 PASS |
| `workbench/` | 50 PASS |
| `web/` | 235 PASS |
| **合计** | **397 PASS / 0 FAIL / 0 SKIP**（与 P2-6-E 基线一致） |

---

## 2. 教材事实源清单（§五）

| 数据源 | 文件 / 位置 | 内容类型 | 是否正式 | 是否可作为事实源 |
| --- | --- | --- | --- | --- |
| 出版社原 PDF | `2025年度初一外研版英语教材\（根据2022年版课程标准修订）义务教育教科书·英语 七年级上册.pdf`（123,040,213 B，178 页） | 教材原始版面 + **完整文本层** | ✅ 正式原件 | ✅ **最高事实源**（实测：178 页中 175 页可直接取文，仅 P1/P3/P178 封面封底为 0 字符；中位 711 字符/页） |
| contentpack v5 | `structured/contentpack/v5/FLTRP-EN-7A-2022CUR.sqlite`（SHA256 `ACEBC8C29CF5…`） | 结构化教材（23 表） | ✅ 正式 | ✅ **由 PDF 确定性派生**，可作事实源 |
| 官方音频 | `2025年度初一外研版英语教材\*.mp3`（54 个） | 教材官方听力音频 | ✅ 正式 | ✅ **本次 54/54 SHA256 与 `audio_asset` 逐一比对，全部一致** |
| 原书词表（附录） | contentpack PDF 155–173 页 + `learning_item`（288 词汇） | Vocabulary / Phrase / Sentence pattern | ✅ 正式 | ✅ 已进入产品 |
| P2-4 教材结构 | `structured/textbook/textbook_structure_v2.json` | 8 Unit / 40 板块 / 157 活动 / 360 题 / 850 空线 | ⚠️ 派生 | ✅ **结构事实可用**（页码、板块、活动号） |
| P2-4 内容关系 | `structured/textbook/textbook_content_relations_v2.json` | 875 文本引用 / 13 语法指针 / 485 词汇引用 | ⚠️ 派生 | ⚠️ **只能作线索**：本次实测存在活动归属错误（见 §4.3） |
| P2-4 视觉关系 | `structured/textbook/textbook_visual_relations_v2.json` | 图片/视觉关系 | ⚠️ 派生 | ⚠️ 线索（本次未作为结论依据） |
| P2-4 上下文关系 | `structured/textbook/textbook_context_relations_v2.json` | 上下文关系 | ⚠️ 派生 | ⚠️ 线索 |
| P2-4 练习目录 | `structured/exercises/exercise_catalog_v3.json`（SHA256 `EB2D8E7BD0BD…`） | 157 练习 / 360 题 | ⚠️ 派生 | ⚠️ **部分字段不可用**：`options` 35 条非空但含页眉页脚噪声；`answer_status` 全部 `NO_RELIABLE_SOURCE` |
| P2-4 题目关系 | `structured/exercises/exercise_question_relations_v3.json` | 360 题（related_text 315 / related_vocabulary 303 / related_audio 121 / options 90） | ⚠️ 派生 | ⚠️ 线索，需重建（§4.3） |
| 音频映射 | `structured/audio/exercise_audio_map_v3.json`（54/54 `CONFIRMED`）、`structured/audio/audio_question_relations_v3.json`（121 条） | 音频↔活动/板块 | ✅ 派生且已证据化 | ✅ **音频↔活动可作事实源**（依据：文件名自带单元+板块+活动号+指令，文本相似度 0.99–1.00） |
| AI 证据包 | `structured/ai/textbook_evidence_map_v1.json`（360 份） | AI 批改输入材料 | ⚠️ 派生 | ⚠️ **是"批改输入"，不是"答案来源"** |
| 派生词音频 | `structured/audio/derived/words/**`（288 个 wav）+ `word_audio_manifest.json` | 由官方整单元词表音频**离线切分** | ⚠️ 派生 | ⚠️ manifest 已声明"不是官方独立单词音频"；**不作为教材事实** |
| 规范 V1.2 | `初中英语AI辅助学习系统_最高指导原则与开发规范_V1.2.docx` + `docs\..._V1.2.md` | 规范 | ✅ 正式 | ✅ 最高依据（本阶段只读） |
| **答案来源** | —— | —— | ❌ **不存在** | ❌ **不可作事实源**（详见 §8） |

**结论**：教材"内容事实"齐备；教材"答案事实"为零。这两者必须分开对待。

---

## 3. 教材正文恢复可行性（§六）

### 3.1 实测：正文文本是否真的可用

以 Unit 1 阅读正文《The first lesson》为例（PDF 第 21–22 页 / 教材 16–17 页）：

```
PDF 文本层（PyMuPDF 直接读取）          contentpack content_block
1 Our English teacher Ms Chen …          P22:B0  dialogue      o=0  1 Our English teacher Ms Chen …
2 We start to write. …                   P22:B1  exercise_item o=1  2 We start to write. …
3 "That's not right. …"                  P22:B2  dialogue      o=2  3 "That's not right. …"
…                                        …
9 That's really an important lesson!     P22:B9  exercise_item o=9  9 That's really an important lesson!
  A new start  17                        P22:B10 footer_text   o=10   A new start  17
```

**实测结论**：`content_block` 与 PDF 文本层**逐块一致、阅读顺序明确**，页眉/页脚已被分离到 `footer_text` / `layout_role=footer`。因此正文不是"能不能解析"的问题，而是"要不要接进页面"的问题。

### 3.2 分类结果

| 内容 | 数据是否存在 | 数据结构 | Unit/Section 是否明确 | Activity 是否明确 | 顺序是否稳定 | 缺字段 | 分类 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Text（说明/叙述正文）** | ✅ 有 | `content_block.text_raw` + `reading_order` | ✅ 页码明确；板块边界由 `section.pdf_page_start` 推得 | ⚠️ 部分（阅读任务活动号已知） | ✅ 稳定 | 无 | **DIRECT_RESTORE** |
| **Dialogue（对话）** | ✅ 有（132 块 `block_kind=dialogue`） | 同上 | ✅ 同上 | ⚠️ 部分 | ✅ 稳定 | 无 | **DIRECT_RESTORE** |
| **Reading（阅读语篇）** | ✅ 有（U1–U6 每单元 2 篇：Understanding ideas + Reading for writing） | 同上 | ✅ 同上 | ✅ 活动号已标（如 U1 A2 "Read the passage…"） | ✅ 稳定 | 无 | **DIRECT_RESTORE** |
| **Listening material（音频）** | ✅ 有（41 条活动级官方 MP3） | `audio_asset` + `audio_mapping`（CONFIRMED） | ✅ | ✅ 1 音频 ↔ 1 活动 | ✅ | 无 | **DIRECT_RESTORE（音频）** |
| **Listening 原文 / 脚本** | ❌ 无 | `transcript` 表 **0 行** | — | — | — | 需要官方脚本或 ASR | **NOT_AVAILABLE** |
| **Listening 印刷配套结构**（poster / table / chart 的空位） | ✅ 有 | 在 `content_block` 内（如 `2 Listen again and complete the poster.` + 编号空位） | ✅ | ✅ | ✅ | 无 | **DIRECT_RESTORE** |
| **Grammar** | ⚠️ 仅 **13 条指针**（`Know more about … ⇢ pNN` / `Grammar rules ⇢ pNN`） | `grammar_in` 关系 | ✅ 指针页明确 | ✅ 归属 Unit | — | **语法条目未切分** | 指针 **DETERMINISTIC_MAPPING**；条目 **NEEDS_REVIEW** |
| **Vocabulary / Phrase / Sentence pattern** | ✅ 有 | `learning_item` + 附录页码 | ✅ | ✅ | ✅ | 无 | 已进入产品（🟢） |
| 板块 → 文本块 的稳定关系 | ⚠️ 生成了但没有校验 | `text_references` 875 条 | ⚠️ 存在错误归属 | ⚠️ 存在错误归属 | — | — | **DETERMINISTIC_MAPPING（须重建）** |

### 3.3 需要新增 / 重建的结构

1. **板块 → 文本块** 的稳定关系（可由 `page.pdf_page` + `section.pdf_page_start` + `reading_order` 确定性生成，**不需要 AI**）。
2. **活动 → 文本块** 的边界规则必须重建（现有 `text_references` 有实测反例，见 §4.3）。
3. **页眉/页脚/侧栏剔除规则**（`layout_role in (footer, sidebar)` + `block_kind in (footer_text, sidebar_tip)`）—— 现成字段即可，无需人工。

---

## 4. 文字—音频—上下文—题目锚定审计（§七）

### 4.1 音频量与分布（实测）

| 项 | 数值 |
| --- | --- |
| 官方音频总数 | **54**（`audio_asset` 54 行；教材目录 54 个 MP3，**SHA 全部一致**） |
| 活动级音频 | 41（`audio_scope=activity`） |
| 板块级音频 | 13（7 条 `word_list` + 6 条 `phonetics`） |
| 映射状态 | **54/54 CONFIRMED**（依据：文件名含单元+板块+活动号+指令，文本相似度 0.99–1.00） |
| 音频→题目关系 | 121 条，`scope=activity`，`review_status=OK` |
| 一个音频服务的活动数 | **1**（实测：不存在"一条音频跨多个活动"） |
| 一个音频服务的题目数 | 1–6 题（分布：2 题×15、3 题×7、1 题×6、4 题×5、6 题×4、5 题×4） |
| 一个练习对应多条音频 | 无 |

### 4.2 逐问回答（§七 六问）

| 问题 | 回答 |
| --- | --- |
| ① 音频对应哪个教材材料？ | **可确定**：`audio_mapping.target_id` = 活动 id 或板块 id，且 54/54 CONFIRMED |
| ② 教材文字对应哪个音频？ | **可确定但未建立**：印刷文字在 `content_block`，音频按活动发行；两者目前**没有直接的文字↔音频关系**，只能通过"活动"这个共同锚点连接 |
| ③ 一段音频是否对应多个 Question？ | **是**，最多 6 题（AU03、AU28）；同一活动内多题**共享同一段音频**，这是教材原设计 |
| ④ 每个 Question 考查什么上下文？ | **活动级可确定**（`activity_id` 已知）；**题级不可确定**（没有 transcript，无法定位"第 3 题考的是对话第几句"） |
| ⑤ Question 能否确定对应 Text Block？ | ⚠️ **现有数据不能直接采信**（反例见 §4.3）；用"活动号 + 页码 + 阅读顺序"重建**可以**确定 |
| ⑥ 音频是否需要切割？ | **不需要**（见 §5） |

### 4.3 实测反例（为什么必须重建锚定层）

| # | 反例 | 实测证据 |
| --- | --- | --- |
| A | **活动边界归属错误**：Starter PDF P10 上，A10 "Listen and choose." 的 8 空对话（`P10:B5/B7–B12`）被 `text_references` 全部记到 **A9**（A9 是 "Match the words and expressions with the pictures"）；A10 只剩活动号块 `P10:B17` | A9 的 `related_text` 含 12 个块（含对话），A10 只有 1 个块（"10"）；而 `exercise_catalog_v3` 里 A10 的 `questions[]` 又是那段对话 → **两份派生数据互相矛盾** |
| B | **同页跨活动串题**：`web/exercises.py::sub_questions()` 只按 `pdf_page` 取 `sub_question`，不按活动过滤 → `X:FA515DD3ECF0`（Starter A4 "Read and check your answers"）拿到了同页 A3 的题 "Where are the new students?" | 代码路径 + 实际渲染文本实测 |
| C | **把指令当题目**：22 条 `short_answer` 走"指令回退"，其中 **7 条**呈现的"题目"根本没有问号（如 "Look at the picture and answer the questions."） | 实测清单 |
| D | **选项字段被页眉/页脚污染**：`X:3DCE713706DE`(U1 A7) `options=[great teacher, new start 19]`、`X:BEF04AA1DF4C`(U1 A4) `options=[new start 23]`、`X:F21C9E2036F7`(U1 Starting out A2, fill) `options=[new start 15]` —— `new start 19/23/15` 是**页脚**，"great teacher" 是**页面小标题** | PDF 文本层对照：页脚为 "A new start 19"，小标题为 "A great teacher" |
| E | **侧栏知识混入选项**：`X:8AA3C10E358E`(U5 A3) 为 "Choose another suitable title"，正确选项 a–d，但 `options` 里多出第 5 条 `pun is a word with more than one`（来自 "Learning to think" 侧栏） | PDF 文本层对照 |

> 结论：**锚定层不能用现有的 `text_references` / `related_text` 直接喂给 UI**；必须按"活动号 + 页码 + 阅读顺序"重建，并对页眉/页脚/侧栏做排除。

---

## 5. 音频切割判定（§八）

### DETERMINISTIC_SEGMENT

**0 条**。不需要切割，理由如下（全部为实测事实）：

1. 出版社已经把听力材料**按活动出版**：文件名本身就是 `序号_单元_板块_活动号_指令.mp3`（例：`01_Starter_Get ready_2 Read and complete. Then listen and check.mp3`）。
2. `audio_mapping` **54/54 CONFIRMED**，且**没有任何一条音频跨活动**（实测）。
3. 一次课文的"第一次听 / 再听一遍"是**两个独立官方文件**（例：AU09 "…1 Listen to the radio…" 与 AU11 "…2 Listen again and complete the poster"），边界由出版社给出，不需要我们推算。
4. 多题共享一段音频是教材原设计（`audio_scope=activity`），**题级音频边界不存在也不需要**。

### NEEDS_REVIEW

**41 条**（活动级音频）。原因不是"切割点不明"，而是**音频内容与题目答案的语义对应必须由人听审确认**：

> 例：`AU32`（U4 Developing ideas A2 "Listen again and complete the poster. Then write F (fact) or O (opinion)…"）——第 1–6 个空该填什么、每个陈述是 F 还是 O，只有听过音频的人能确定。

### 明确禁止（本次未做，也不允许进入 F-1…F-7）

- ❌ 用 AI 猜切割点 ❌ 用音频时长推算 ❌ 用文字长度推算 ❌ 用语义相似度猜边界
- ❌ 根据 AI 推测教材答案

### 保留策略

**保留官方完整音频 + 完整教材文字**，优先保证教材真实性；只使用"出版社已按活动分轨"这一确定事实。

---

## 6. 全量 Question 结构恢复审计（§九 / 157 练习 · 360 题）

### 6.1 当前运行期真实现状（实测复现）

> 重要事实：**运行期 Web 练习页使用的是 `exercise_catalog_v2.json`，不是 v3。**
> `web/exercises.py` 第 26–28 行：`CATALOG = CATALOG_V2 if CATALOG_V2.exists() else CATALOG_V1`。
> v3（P2-4）只被 `learning/` 侧服务（`learning_object_service` / `evidence_service` / `intervention_service`）使用。

| 运行期交互类型 | 数量 |
| --- | --- |
| spelling（看中文写单词） | 26 |
| fill（按空位数出输入框） | 27 |
| short_answer（简答） | 35 |
| choice（单选） | 6 |
| match（配对输入） | 4 |
| self_check（只有"我完成了 / 还想再看一遍"） | 59 |
| 合计 | **157** |

### 6.2 逐题型：当前结构 vs 教材事实 vs 可恢复程度

| question_type | 练习数 | 题数 | 当前结构（运行期实测） | 教材事实（已核验） | 可恢复程度 |
| --- | ---: | ---: | --- | --- | --- |
| choice | 12 | 30 | 6 条渲染单选（其中 **3 条选项是噪声**）；2 条被降级成 spelling；5 条降级 self_check | 12 条教材选择题：5 条选项已在数据里且正确；5 条选项在题干/正文内联；1 条选项归属待核验；1 条根本不是选择题 | **DIRECT_RESTORE 4 条 / DETERMINISTIC_MAPPING 6 条 / NEEDS_REVIEW 2 条** |
| judge | 1 | 3 | 0 条渲染（全 self_check） | U4 Developing ideas A2：F / O 二分判断，指令已明示规则 | 结构 **DETERMINISTIC**；答案 **NEEDS_REVIEW**（需听音频） |
| fill | 45 | 124 | 27 条渲染填空；**18 条被降级成 spelling** | 45 条均为教材 "Complete the …" 任务；空位结构可从 PDF 文本层确定性恢复 | 结构 **DETERMINISTIC**；答案 **NEEDS_REVIEW**（无来源） |
| match | 9 | 14 | 3 条渲染 match；**6 条被降级成 spelling** | 左右列项目部分已存在（`check_items` 4/9 条）；图片类右列不在数据内 | 结构 **部分 DIRECT / 部分 NEEDS_REVIEW**（涉图） |
| order | 1 | 2 | 渲染成 match（列 4 个项目） | U2 A2 "Listen again and order the pictures." —— 依赖 4 张图片 | **NEEDS_REVIEW**（图片不在数据内） |
| short_answer | 34 | 111 | 35 条渲染简答 | 13 条来自 `sub_question`（**按页取，存在跨活动串题**）；22 条回退成"指令当题目"（7 条无问号） | 结构 **需重建**；答案 **无标准答案 → AI + 教材依据** |
| writing | 7 | 16 | 0 条渲染输入框（全 self_check） | 7 条均为明确的教材写作要求（"Write a summary…" / "Write a short paragraph…"） | 结构 **DIRECT**（题干在 `instruction`）；评分标准 **NEEDS_REVIEW** |
| reflection | 18 | 18 | 0 条渲染勾选（全 self_check） | 教材原设计：1/2/3 三档自评 + "To express my understanding, I can… ☐" 清单（PDF 文本层可见） | **DETERMINISTIC_RESTORE**（自评，不作判断证据） |
| speaking | 16 | 22 | 0 条渲染（全 self_check） | 教材要求明确（"Work in pairs…"），无书面作答载体 | 结构 **DIRECT**；作答载体需设计（最小动作） |
| other | 14 | 20 | 13 条 self_check + 1 条 short_answer | 混合：7 条"语法小结"、Starter 项目页、U6 测验等 | **逐条分类后处理** |

### 6.3 逐条明细（choice 12 条练习 / 30 题）

| 练习 | 教材位置 | 教材原题 | 选项事实 | 判定 |
| --- | --- | --- | --- | --- |
| `X:1C4143922B1C` | Starter GET_READY A10 p5 | Listen and choose.（8 空对话 + 9 项 ☐ 词表） | 页面有 ☐ 词表，但 P2-4 把该块归给 A9 | **NEEDS_REVIEW**（需人工看图定归属） |
| `X:7ABB5256D7ED` | Starter Know your school A2 p7 | Read and tick the correct sentences. Then correct the wrong ones. | 真选项 = 题干里 4 个 ☐ 句子；数据里的 `options` 是同一页 A3 的句子 | **DETERMINISTIC**（并删噪声） |
| `X:0E367840E9FC` | Unit 1 Understanding ideas A3 p18 | Choose the main idea of the passage. a/b/c | ✅ 已存在且正确 | **DIRECT**（当前被降级成 spelling） |
| `X:8D3E1E4E1B31` | Unit 1 Understanding ideas A6 p19 | Circle the correct words.（my / I、we / our、mine / my、their / them） | 选项内联在 4 个句子中 | **DETERMINISTIC** |
| `X:3DCE713706DE` | Unit 1 Understanding ideas A7 p19 | Read the passage and circle the correct words. | 选项内联在正文（their / my、your / his、I / he …）；数据里是页眉+页脚噪声 | **DETERMINISTIC**（并删噪声） |
| `X:BEF04AA1DF4C` | Unit 1 Developing ideas A4 p23 | Work in pairs. Choose a problem … and give advice. | **教材不是选择题**；数据里 `options=[new start 23]` 是页脚 | **NEEDS_REVIEW**（题型误判） |
| `X:C29E418B7E32` | Unit 2 Understanding ideas A3 p34 | Choose the best main idea. a/b/c | ✅ 正确 | **DIRECT** |
| `X:74BDDE140FAE` | Unit 3 Understanding ideas A3 p50 | Read and tick. What does the film review include? | ☐ 清单在题干文本内 | **DETERMINISTIC** |
| `X:62B3B2420DF9` | Unit 4 Understanding ideas A3 p66 | Choose the best ending. a/b/c | ✅ 正确 | **DIRECT**（当前被降级成 spelling） |
| `X:8AA3C10E358E` | Unit 5 Understanding ideas A3 p82 | Choose **another suitable title** and give your reasons. a–d | ✅ a–d 正确；多 1 条侧栏噪声 | **DETERMINISTIC**（删噪声）；**答案开放，不宜单一判分** |
| `X:36ECBA5AD565` | Unit 6 Understanding ideas A1 p96 | Tick the words to describe pigeons. | ☐ boring/fast/scary/clever/dirty/amazing/others 在题干内 | **DETERMINISTIC** |
| `X:8B987AF028E9` | Unit 6 Understanding ideas A3 p98 | Choose another suitable title. a–d | ✅ 正确 | **DIRECT**；**答案开放** |

**judge（1 条 / 3 题）**：`X:C2D62A46BE36` U4 Developing ideas A2 p70 —— 结构 = F / O（指令给出），答案需听 `AU32` → 结构可恢复、答案需人工。

**fill（45 条 / 124 题）——两个结构缺陷（实测）**

- **空位数=0 → 只出 1 个输入框**（6 条）：`88C641F5FA05`(Starter A1)、`F21C9E2036F7`(U1 Starting out A2)、`2CA1B9F43CB3`(U1 RfW A5)、`24C80DAE6FAE`(U2 U-I A6)、`6BB271F5F101`(U5 U-I A6)、`5BCC4D6DC928`(U6 U-I A6)
- **空位数=9 → 被截成 8 个输入框**（3 条）：`AC02902827A8`(U1 A1)、`41B8D362116C`(U2 U-I A7)、`0AD8920218D8`(U5 RfW A3)

这两类都可以用"PDF 文本层里的编号空位"确定性修正，不需要 AI。

**reflection（18 条）**：教材结构 = 三档自评（`*1 = excellent, 2 = good, 3 = not yet`）+ 勾选清单 → 可确定性恢复为"自评"控件（**仍然不进有效证据**，符合 V1.2"自评不能单独升级掌握状态"）。

---

## 7. P2-6-E 六项 P1 逐项追踪（§十）

### P1-01 教材练习无法产生有效证据

**逐层判定（缺什么）**

| 环节 | 是否存在 | 实测依据 |
| --- | --- | --- |
| Question（题目实体） | ✅ 存在（157 练习 / 360 题，`exercise_catalog_v3` + 证据包） | 360 条全部有 `question_id`、页码、活动号 |
| 作答控件 | ⚠️ 部分存在（98/157 有控件；59 条只有自评） | 运行期渲染实测 |
| **可核对答案** | ❌ **完全不存在**（157/157 `NO_RELIABLE_SOURCE`；360/360 `answer_source=NO_RELIABLE_SOURCE`） | catalog + 证据包字段 + 教材无答案页 + 项目无教师用书 |
| 规则批改器 | ✅ 存在（spelling 已真实判分 `correct/partial/incorrect`） | `web/exercises.py::grade` |
| Evidence 接口 | ✅ 存在（`learning/evidence_service.py`，只认 `correct/incorrect/partial`） | 代码 + 112 项 learning 测试 |
| UI 呈现 | ✅ 存在 | 真机已验收（P2-3 / P1-13-C1） |

**根因排序**

1. **答案来源缺失（决定性）** —— 没有答案，"判分"无从谈起；自评被规范排除在有效证据外。
2. **题目结构缺失/错误（次要但真实）** —— 选项噪声、空位数错、把正文当题目。
3. 其余环节（Question 实体、批改器、Evidence 接口、UI）都**不是**瓶颈。

**结论（重要）**：P1-01 **不能靠工程手段闭合**。要么引入官方答案源，要么人工核验答案。**在此之前，任何"提升教材练习证据产出"的做法都会退化为伪造答案**，直接违反 V1.2。

---

### P1-02 5 条 choice/judge 无选项（逐条）

| # | exercise_id | 教材位置 | 教材原始题目 | 是否存在选项事实 | 是否可确定恢复 | 是否需人工核验 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `X:1C4143922B1C` | Starter / GET_READY / A10（p5） | Listen and choose. | ⚠️ 页面有 9 项 ☐ 词表（sports trousers… coat）+ 8 空对话，但 P2-4 把该块归给 A9 | 结构可写、归属不可自动定 | ✅ **需要**（看 1 张页面图即可定案） |
| 2 | `X:8D3E1E4E1B31` | Unit 1 / Understanding ideas / A6（p19） | Circle the correct words.（4 句） | ✅ 有（内联 "my / I" 形式） | ✅ 可（按 "A / B" 解析） | ❌ 不需要 |
| 3 | `X:74BDDE140FAE` | Unit 3 / Understanding ideas / A3（p50） | Read and tick. What does the film review include? | ✅ 有（题干内 ☐ 清单） | ✅ 可 | ❌ 不需要 |
| 4 | `X:C2D62A46BE36` | Unit 4 / Developing ideas / A2（p70） | …write F (fact) or O (opinion) in the boxes. | ✅ 有（F / O，指令已定义） | ✅ 结构可 | ✅ 需要（答案须听 `AU32`） |
| 5 | `X:36ECBA5AD565` | Unit 6 / Understanding ideas / A1（p96） | Tick the words to describe pigeons. | ✅ 有（☐ boring/fast/scary/clever/dirty/amazing/others） | ✅ 可 | ❌ 不需要 |

**P2-6-E 未列出的同类新发现（本次实测）**：

- `X:7ABB5256D7ED`(Starter A2)、`X:3DCE713706DE`(U1 A7)、`X:BEF04AA1DF4C`(U1 A4)：**选项是页眉/页脚/同页其它活动的句子**，属于比"无选项"更危险的一类（孩子会看到错误选项）。
- `X:8AA3C10E358E`(U5 A3)：5 条选项里混入 1 条侧栏文本。

---

### P1-03 "18 条 fill 被转换成词表 spelling"

**口径修正（实测）**：真正被词表拼写替换的练习是 **26 条**，不只 18 条。

| 原始教材题型 | 条数 | 说明 |
| --- | ---: | --- |
| fill | 18 | 如 U1 A4 "Complete the summary with the words and expression from the passage." |
| **match** | **6** | 如 Starter A1 "Match the words and expression with the things in the picture." |
| **choice** | **2** | U1 A3 "Choose the main idea"、U4 A3 "Choose the best ending"（**选项本来就是正确可用的**） |
| 合计 | **26** | 与运行期 `spelling = 26` 完全一致 |

**根因（代码级）**：`web/exercises.py::build_questions()` 第 1 条分支 `if etype == "vocabulary"` 直接短路 —— 只要练习 `type=vocabulary` 且该单元词表非空，就用"本单元 4 个 CORE 词的看中文写单词"替换掉教材原任务，**教材原题的作答结构从未渲染**。

**逐条确认（18 条 fill）**：全部确认为**真正的教材填空任务**（"Complete the notes / questionnaire / summary / chart / form / webpage / display board…"），**不是**词表练习；教材原文与空位可从 PDF 文本层恢复；**标准答案不存在**。

→ 可确定恢复"教材填空结构"；**不可**确定恢复"标准答案"。

---

### P1-04 教材正文 / 阅读 / 对话未进入产品

| 问题 | 回答 |
| --- | --- |
| 数据在哪里 | `contentpack v5` → `content_block`（3854 块；`dialogue` 132、`exercise_item` 2133、`heading` 344、`instruction` 194、`footer_text` 178、`sidebar_tip` 348、`vocabulary_entry` 525） |
| 如何接 Unit / Section | 用 `page.pdf_page` + `section.pdf_page_start` + `reading_order` 生成"板块 → 文本块"关系；剔除 `layout_role in (footer/sidebar)` 与 `block_kind in (footer_text/sidebar_tip)` |
| 是否已有稳定 ID | ✅ 有：`block_id`（如 `FLTRP-EN-7A-2022CUR:P22:B0`）、`page_id`、`section_id`、`activity_id` |
| 是否需要新增结构 | ✅ 需要 1 个只读派生关系（板块/活动 ↔ 文本块），**不需要改 contentpack schema** |
| 是否需要人工映射 | 抽检级别：12 篇阅读正文的板块归属 + 同页跨板块情况（例如一页含上一活动结尾与下一活动开头） |
| 产品侧入口 | 现无路由（实测仅有 `/`、`/textbook`、`/unit/<slug>`、`/unit/<slug>/exercises`、`/exercise/<key>`、`/review`、`/vocabulary/*`、`/health`） |

---

### P1-05 7 条 writing 无输入框

| 问题 | 回答 |
| --- | --- |
| 教材是否确实要求写作 | ✅ 是（7 条 instruction 全部为写作任务：Write about yourself / Write a summary of the story / Write a short paragraph about…） |
| 当前数据有什么 | `instruction`（7/7）+ `check_items`（5/7）+ 来源页码；**无评分标准** |
| 是否存在写作题干 | ✅ 有（`instruction` 即写作要求；部分还带要点清单） |
| 是否有评分依据 | ❌ 无（教材学生用书无评分标准；项目内无 rubric） |
| AI 批改需要哪些输入 | ① 写作要求（题干）② 教材依据（Reading for writing 的范文/句式/Useful expressions）③ 孩子原文 ④ 评分维度（需人工定义一次：内容要点 / 语言准确性 / 是否使用教材表达） |

---

### P1-06 8 条音频练习"只有音频 + 自评"（逐条）

| # | exercise_id | 教材位置 | 音频 | 文字 | Question | options/blanks | context | answer | 能否恢复 |
| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `X:1C4143922B1C` | Starter A10 p5 | AU03（58.2s） | 对话正文（8 空） | 6 条（实为对话正文） | options 0 / blanks 8 | 活动级 | ❌ | 结构需人工核验（见 P1-02 #1） |
| 2 | `X:AE2533FCC40F` | U1 U-I A8 p20 | AU08（72.5s） | 口语任务 + thinking map | 无 | — | 活动级 | — | **口语任务**，本身不需要书面答案 |
| 3 | `X:98EDEBD8BB3C` | U2 U-I A8 p36 | AU15（51.0s） | 口语/写作混合任务 | 无 | — | 活动级 | — | 同上（任务类型需人工确认） |
| 4 | `X:6A15670681BC` | U3 U-I A8 p52 | AU22（67.5s） | "Draw and write about a loving family moment." | 无 | — | 活动级 | — | **写作任务**，需输入框（P1-05） |
| 5 | `X:9DCBC9B25099` | U4 U-I A8 p68 | AU29（62.1s） | 口语任务 + thinking map | 无 | — | 活动级 | — | 口语任务 |
| 6 | `X:C2D62A46BE36` | U4 D-I A2 p70 | AU32（77.4s） | poster + 6 空 + F/O | 3 条 | blanks 6 | 活动级 | ❌ | 结构可恢复（F/O），**答案需听音频** |
| 7 | `X:04DE72A05D12` | U5 U-I A8 p84 | AU36（52.7s） | 口语任务 | 无 | — | 活动级 | — | 口语任务 |
| 8 | `X:9A6A563440C5` | U6 U-I A2 p96 | AU42（131.6s） | "Read the blogs and find out the words Henry used." | 无 | — | 活动级 | ⚠️ | 可从课文文本确定（**需人工核验后**方可作为答案） |

> 说明：这 8 条的真实性质并不相同 —— 4 条是**口语任务**（本来就没有书面答案）、1 条是**写作任务**、2 条是**真实听力/判断题**（需要答案）、1 条是**任务类型标注错误**（U6 A2 其实是阅读找词）。因此它们应当被"分类处理"，而不是统一补控件。

---

## 8. 答案来源审计（§十一 · 本阶段核心）

### 8.1 Question → Answer Source → Verified Answer

**实测结论：链路在第二环断开，且无任何候选来源。**

| 候选答案来源 | 是否存在 | 证据 |
| --- | --- | --- |
| 教材学生用书自带答案页 | ❌ 不存在 | 附录实测仅 6 类：Communication bank(117–134) / Guide to the language use(135–154) / Words and expressions(155–162) / Proper nouns(163) / Vocabulary(165–173) / Pronunciation guide(174–176)；**无 Answer key** |
| 项目内教师用书 / 答案文件 | ❌ 不存在 | 全仓库检索 `answer key / 答案 / 参考` 仅命中 "answer the questions" 这类指令文本，无答案数据 |
| contentpack 答案字段 | ❌ 不存在 | `activity` / `sub_question` / `transcript`(0 行) 均无答案字段 |
| `exercise_catalog_v3` | ❌ 全部显式为无 | `answer_status = NO_RELIABLE_SOURCE` × 157（生成器注释："教材未提供可核对的答案来源；不猜测答案"） |
| AI 证据包 | ❌ | `answer_source = NO_RELIABLE_SOURCE` × 360，`answer_note` 明确"不得编造教材事实" |

### 8.2 逐类统计

| 题型 | 正式题数 | 有可靠答案 | 无答案 | 需要人工核验 | 建议判分方式 |
| --- | ---: | ---: | ---: | ---: | --- |
| choice | 30 | **0** | 30 | 30 | 规则 + 标准答案（答案须人工核验） |
| judge | 3 | **0** | 3 | 3 | 规则 + 标准答案（须听音频） |
| fill | 124 | **0** | 124 | 124 | 规则 + 标准答案（须人工核验） |
| match | 14 | **0** | 14 | 14 | 规则 + 标准答案 |
| order | 2 | **0** | 2 | 2 | 规则 + 标准答案（依赖图片） |
| short_answer | 111 | **0** | 111 | 111（评分要点） | AI 批改 + 教材依据 |
| writing | 16 | **0** | 16 | 16（评分标准） | AI 批改 + 教材依据 |
| other | 20 | **0** | 20 | 20（先分类） | 分类后决定 |
| speaking | 22 | **0** | 22 | 0 | 只记录"完成"，不判分 |
| reflection | 18 | **0** | 18 | 0 | 自评，不计证据 |
| **合计** | **360** | **0** | **360** | **320** | — |

（练习级口径同样：157 条练习 **全部 0 条有可靠答案**。）

### 8.3 明确禁止

❌ AI 猜答案 ❌ 按语义自行创造答案 ❌ 模型推理补答案后直接入正式数据 ❌ 用"文本相似度"把课文里的词自动填成标准答案

---

## 9. AI 批改边界设计（§十二 · 只读设计，本阶段不调用）

### 9.1 客观题（choice / judge / fill / spelling / match / order）

```
题目结构（题干 + 选项/空位）  +  已核验标准答案  +  孩子作答
        ↓  规则比对（大小写/标点归一化，确定性）
correct / incorrect / partial
```

- **AI 不承担"猜答案"职责**；AI 最多用于"错误归类解释"（可选、可缓存）。
- 前提：标准答案必须来自**已核验**数据（人工核验后标 `review_status=VERIFIED_BY_HUMAN`）。

### 9.2 主观题（short_answer / writing）

| 项 | 设计 |
| --- | --- |
| AI 输入 | `TextbookEvidencePackage`（题目 + 教材原文 + 页码 + 指令 + 相关词汇/句型）+ 孩子原始回答 + 任务类型 |
| 教材依据 | 阅读正文 / 听力材料的印刷结构 / Useful expressions / 单元词表（**必须是教材里真实存在的文本**） |
| 标准答案 / 评分标准 | 教材**没有**标准答案 → 必须人工定义"评分要点"（内容要点 + 是否使用教材表达 + 语言准确性），**不以唯一答案判定** |
| 三档输出 | `correct`（覆盖要点且表达正确）/ `partial`（覆盖部分要点）/ `incorrect`（未回答问题或语义不符）；**必须附引用到的教材依据** |
| 原始回答 | 原样保存（`response_raw`），不得被改写 |
| Evidence | 批改结果写入 `learning_record.result` ∈ {correct, partial, incorrect} → 由既有 `evidence_service` 判定（**不改冻结服务**） |

### 9.3 高频 / 低频 / 按需 / 可缓存

| 能力 | 建议 | 理由 |
| --- | --- | --- |
| 客观题判分 | **不调用 AI**（确定性规则；高频） | 成本 0、可离线、可复现 |
| 简答批改 | **按需 + 可缓存**（同题同答命中缓存） | 中频；每次都要带教材依据，token 成本可控 |
| 写作批改 | **按需（低频）** | 长文本、成本高；孩子主动提交才触发 |
| 错误归因 / 巩固建议 | **按需 + 可缓存**（本地规则先生成，AI 只补充解释） | 避免无谓调用 |
| 教材内容提取（正文/选项/答案） | **不调用 AI**（PDF 文本层 + 确定性规则 + 人工核验） | 教材事实不得由模型生成 |

---

## 10. 正式练习的目标产品结构（§十三）

```
教材上下文（Unit / Section / Activity）
   ↓
教材文字（content_block：正文 / 对话 / 印刷配套结构）      ← 现缺页面（P1-04）
   ↓
官方音频（54 MP3，按活动分轨，SHA 已验证）                ← 已有
   ↓
Question（题干 + 选项 / 空位 + 上下文锚点）                 ← 部分缺失/错误（P1-02 / P1-03）
   ↓
真实作答控件（选择 / 判断 / 填空 / 匹配 / 写作 / 口语）      ← 59 条只有自评
   ↓
提交
   ↓
批改（客观：规则 + 已核验答案；主观：AI + 教材依据）        ← 答案来源缺口（P1-01）
   ↓
Evidence（correct / incorrect / partial）
   ↓
Mastery / Diagnosis（既有冻结服务，不改）
```

**孩子负责**：选择学什么 / 什么时候学 / 做题 / 暂停继续 / 是否继续巩固。
**系统负责**：批改 / 分析 / 解释 / 形成证据 / 给出教材优先建议。
**禁止设计**："请你自己判断这道题做得怎么样。"（当前 59 条 self_check 就是这个形态，只能作为过渡态）

---

## 11. 最小修复路线 F-1 … F-7（§十四）

> 不写代码。每步给出：输入 / 输出 / 修改文件 / 人工核验 / 改正式数据 / 改 DB / 风险 / 真机可见变化。

### F-1 教材正文接入（Text / Dialogue / Reading）

| 项 | 内容 |
| --- | --- |
| 输入 | `content_block`（`page_id` + `reading_order` + `block_kind` + `layout_role`）、`section.pdf_page_start`、`textbook_structure_v2` |
| 输出 | 只读派生关系"板块 → 有序文本块"（+ 剔除 footer/sidebar 规则）；Unit 页新增"读教材正文"入口 |
| 修改文件 | `web/content.py`、`web/ui.py`、`web/app.py`（新增只读路由）；可选新增 1 个 builder 产出派生 JSON |
| 人工核验 | ⚠️ 抽检 12 篇阅读正文的板块归属与跨页连续性 |
| 修改正式数据 | 否（只读派生） |
| 修改 DB | **否** |
| 风险 | **低**（纯读、纯展示；不影响学习语义） |
| 真机可见变化 | Unit 里能直接读到《The first lesson》这类教材原文（当前完全读不到） |

### F-2 Question 结构恢复

| 项 | 内容 |
| --- | --- |
| 输入 | PDF 文本层（确定性读取）、`exercise_catalog_v3`、活动号/页码、`sub_question` |
| 输出 | 新的练习结构数据（题干 / 选项 / 空位数 / 上下文锚点 activity_id），替换运行期的 v2 目录 |
| 修改文件 | 新增 builder；`web/exercises.py`（目录切换 + 删除 spelling 短路分支）、`web/ui.py` |
| 人工核验 | ✅ 必须：5 条无选项 + 3 条错误选项 + 1 条题型误判 + 侧栏噪声 |
| 修改正式数据 | 否（新增派生文件即可） |
| 修改 DB | **否** |
| 风险 | **中**：切换目录会同时改变 26 条 spelling 与 6 条 choice 的行为，必须同步回归 397 项测试 |
| 真机可见变化 | 选择题显示真实选项；不再出现 "new start 15 / 19 / 23" 这类页脚；填空空位数与教材一致 |

### F-3 答案来源补齐

| 项 | 内容 |
| --- | --- |
| 输入 | 教材 PDF 页面 + 官方音频 + **人工核验** |
| 输出 | `exercise_answer_key_v1`（每条答案带 `review_status=VERIFIED_BY_HUMAN`、核验人、核验依据页码/时间点） |
| 修改文件 | 新增答案数据文件（不改 contentpack、不改教材） |
| 人工核验 | ✅ **必须，不可绕过** |
| 修改正式数据 | **是**（新增正式答案数据） |
| 修改 DB | 否 |
| 风险 | **高**：答案错误会直接伤害孩子 → 必须先小批量（choice + judge 33 题）验证流程 |
| 真机可见变化 | 客观题出现真实判分（correct / incorrect / partial） |

### F-4 音频 / 文字 / 上下文锚定

| 项 | 内容 |
| --- | --- |
| 输入 | `audio_asset`（54）、`audio_mapping`（CONFIRMED）、`exercise_audio_map_v3`、活动 id |
| 输出 | 统一的 `context_anchor = activity_id`（**不切割音频**）；练习页同时呈现"教材文字 + 官方音频" |
| 修改文件 | `web/app.py`（把音频挂到锚点）、`web/ui.py`（呈现）；可选派生锚定表 |
| 人工核验 | ⚠️ 抽样听审（确认音频与印刷结构对应） |
| 修改正式数据 | 否 |
| 修改 DB | **否** |
| 风险 | **低** |
| 真机可见变化 | 听力练习页同时出现教材原文结构与 🎧 官方音频（当前只有指令 + 音频） |

### F-5 UI 作答控件

| 项 | 内容 |
| --- | --- |
| 输入 | F-2 的结构 + F-4 的锚点 |
| 输出 | 选择（radio）/ 判断（F-O）/ 填空（按空位数）/ 匹配（左右列）/ 写作（textarea）/ 口语（最小动作） |
| 修改文件 | `web/ui.py`、`web/exercises.py` |
| 人工核验 | ✅ 真机验收（S24+）+ 视觉检查 |
| 修改正式数据 | 否 |
| 修改 DB | **否** |
| 风险 | **中**（布局与可点区域） |
| 真机可见变化 | 59 条"只有自评"的练习里，可作答的那部分出现真实控件 |

### F-6 AI 批改（主观题）

| 项 | 内容 |
| --- | --- |
| 输入 | 教材证据包 + 孩子原文 + 人工定义的评分要点 |
| 输出 | `correct / partial / incorrect` + 教材依据引用 |
| 修改文件 | `web/ai_grading.py`（注入 provider）、提交路径 |
| 人工核验 | ✅ 必须先定义评分要点；AI 输出需抽样复核 |
| 修改正式数据 | 否 |
| 修改 DB | **否** |
| 风险 | **中高**（成本、幻觉、"用教材依据约束"是否严格） |
| 真机可见变化 | 简答 / 写作提交后得到"依据教材的分析" |

### F-7 Evidence 接入

| 项 | 内容 |
| --- | --- |
| 输入 | 批改结果（`correct / partial / incorrect`） |
| 输出 | `learning_record` → 既有 `evidence_service` 判定 → LO Mastery / Diagnosis / Review 建议 |
| 修改文件 | `web/app.py`（提交路径）；**不改** `learning/` 冻结服务 |
| 人工核验 | 否（回归测试覆盖） |
| 修改正式数据 | 否 |
| 修改 DB | **否**（沿用既有 schema） |
| 风险 | **低**（复用既有冻结接口） |
| 真机可见变化 | `/review` 的教材学习建议开始有真实内容 |

---

## 12. NEEDS_REVIEW 清单（§十五）

> 以下内容**无法从现有教材事实自动确定**，不得为提高完成率而强行补齐。

| # | 类别 | 数量 | 具体对象 | 需要什么才能定案 |
| --- | --- | ---: | --- | --- |
| N-01 | 选择题选项归属 | 1 | `X:1C4143922B1C`（Starter A10 "Listen and choose."）的 9 项 ☐ 词表是否属于本题 | 人工看教材 p5 页面图 |
| N-02 | 选项错误需删除 | 3 | `X:7ABB5256D7ED`、`X:3DCE713706DE`、`X:BEF04AA1DF4C` | 人工确认（本次已给出真值来源） |
| N-03 | 选项含侧栏噪声 | 1 | `X:8AA3C10E358E`（U5 A3 第 5 条选项） | 人工确认 |
| N-04 | 题型误判 | 1 | `X:BEF04AA1DF4C`（其实是 pair-work 口语，不是 choice） | 人工确认题型 |
| N-05 | 客观题标准答案 | 173 题 | choice 30 / judge 3 / fill 124 / match 14 / order 2 | **人工依据教材 + 音频核验** |
| N-06 | 主观题评分要点 | 127 题 | short_answer 111 / writing 16 | 人工定义评分要点（不是唯一答案） |
| N-07 | 其它题型先分类 | 20 题 | `other`（语法小结 / 项目页 / 测验） | 人工逐条分类后再处理 |
| N-08 | 音频与题目语义对应 | 41 条 | 41 条活动级音频（含 8 条"只有音频 + 自评"） | 人工听审 |
| N-09 | 板块/活动 → 文本块归属 | 若干 | 同页跨活动（实测 A9/A10）、`text_references` 未覆盖的 13 个 contentpack 活动 | 人工抽检 + 重建规则 |
| N-10 | 阅读正文板块边界 | 12 篇 | U1–U6 ×（Understanding ideas + Reading for writing） | 人工抽检（页首/页尾跨板块） |
| N-11 | 依赖图片的题目 | ≥2 | `X:FB47DD21DABE`（order pictures）等 | 图片资源进入数据后才能确定 |
| N-12 | 听力原文 | 41 条音频 | `transcript` 表 0 行 | 官方脚本（不存在）或 ASR（本阶段禁止） |

---

## 13. 最终产品视角（§十六）

> **问题**：按照当前真实教材数据，最小代价怎样才能把 APP 从"教材数据 + 部分练习"推进到"真正的教材学习工具"？

**答案**：先做"不需要答案就能做"的三件事（正文可见、题目结构正确、音频上下文完整），把教材变成**可读、可听、可看原题**的产品；把"真实判分"严格留到人工核验答案之后。

### 第一批（应该马上修；不需要人工核验、不需要 AI、不改 DB）

1. **F-1 教材正文接入**（Unit 里能读教材原文）—— 数据已完整、风险最低、孩子感受最直接。
2. **F-2 的零风险子集**：删除 4 条噪声选项；恢复 `X:8D3E1E4E1B31` / `X:74BDDE140FAE` / `X:36ECBA5AD565` / `X:C2D62A46BE36` 的结构；修正 6 条 `blanks=0` 与 3 条 `blanks=9`。
3. **F-4 音频锚定**：把官方音频挂到活动锚点，并在页面同时呈现教材印刷结构。
4. **停止用词表拼写替换教材任务**（26 条）—— 至少在结构恢复前不要"替换"，而是"并存 / 降级"。

### 第二批（结构做完之后）

5. **F-2 全量结构恢复 + F-5 UI 作答控件**（选择 / 判断 / 填空 / 匹配）。
6. **F-3 答案补齐**：先做 **35 题**（choice 30 + judge 3 + order 2），再由人工判断 match 里可确定的部分，跑通"人工核验 → 规则判分 → Evidence"这条链。
7. **F-7 Evidence 接入**，让 `/review` 真正有内容。

### 必须人工核验（不可自动化）

- 173 道客观题的标准答案（N-05）
- 127 道主观题的评分要点（N-06）
- Exercise 10 的选项归属（N-01）、3 条错误选项（N-02）、1 条题型误判（N-04）
- 41 条音频与题目的语义对应（N-08）

### 以后再做

- F-6 AI 批改（主观题）
- 口语任务的最小载体（"我说完了 / 再说一次"）
- Reflection 的 1/2/3 三档自评还原
- Grammar 条目（13 条指针 → 语法内容页）

### 目前明确不做

- ❌ AI 猜答案 / AI 生成教材内容
- ❌ 音频切割（无一条需要）
- ❌ 为提高映射覆盖率强行归属（68 条 unmapped 保持 unmapped）
- ❌ 把自评（`done`）当证据
- ❌ 修改 contentpack schema / 教材 / 音频 / 冻结服务 / Android

---

## 14. 保护基线（§十七）

| 对象 | 审计前 | 审计后 | 结论 |
| --- | --- | --- | --- |
| `structured/learning/learning.db` SHA256 | `DBAB743BF6D8F0A3832E599CBD5DD2267F008FD9FB3903BACEA93780A466D633` | **同左** | ✅ 未变 |
| `learning.db` mtime | 2026-09-12 23:15:13 | **同左** | ✅ 未变 |
| `learning.db` 表数 / 记录 | 7 表 / learning_record 20 / mastery_state 7 | **同左** | ✅ 未变 |
| `learning.db` integrity / FK | ok / 0 | **同左** | ✅ 未变 |
| contentpack v5 SHA256 | `ACEBC8C29CF5D11BAB50BF7962FBEE5DE42CD9CFC7FE48AB6316699D265E1A3F` | **同左** | ✅ 未变 |
| `exercise_catalog_v3.json` SHA256 | `EB2D8E7BD0BD71404FBE2B3C010289158CCB8A12F4DF031ED7444B4BE9570A39` | **同左** | ✅ 未变 |
| V1.2 docx SHA256 | `6D3595CF7D83879ADF3E6452C5E5A74C5300E89265DE1B4F2FA8A1EBDBB861A9` | **同左** | ✅ 未变 |
| `web/` 四个文件 SHA256 | app `CB2984D2…` / ui `F95D8AE5…` / flow `E74D8925…` / exercises `6EE339F0…` | **同左** | ✅ 未变 |
| Android | `applicationId=com.zhixueenglish.app.dev`；`zhixue.webBaseUrl=http://192.168.2.3:8770/`；APK `app-debug.apk`（2026-09-12 18:23:32） | **同左** | ✅ 未变 |
| 测试 | 397 PASS（learning 112 / workbench 50 / web 235） | **397 PASS / 0 FAIL / 0 SKIP** | ✅ 未变 |
| AI 调用 | 0 | **0** | ✅ |
| 代码修改 | 0 | **0** | ✅ |

**本次新增文件（仅这两个，符合任务书 §十八）**：

- `audit/P2-6-F-0_textbook_exercise_repair_readiness.md`（本文件）
- `audit/P2-6-F-0_textbook_exercise_repair_readiness.json`

---

## 15. 审计结论

**P2-6-F-0 审计执行：PASS（只读、零修改、AI = 0）**
**修复可实施性：CONDITIONAL PASS**

- **可立即实施（依据充分、风险低）**：F-1 教材正文接入、F-4 音频锚定、F-2 的噪声清理与 4 条结构恢复。
- **必须人工核验后才能实施**：F-3 答案补齐（173 道客观题）→ 这是 P1-01 的唯一真实出口。
- **本阶段不做**：AI 批改、音频切割、schema 变更、教材数据修改。

> **一句话**：教材正文和音频是"已经躺在仓库里没人用"的资产，**马上就能修**；教材练习的答案**根本不存在**，**必须先由人核验**——这两件事必须分开决策，否则一定会退化成"用 AI 猜答案"。

### 本次审计未修改任何文件（除以上两个归档文件），AI 调用 0。立即停止，不进入 F-1。
