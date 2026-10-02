# P3-01：教材官方音频句子级跟读库——小批量验证（Starter + Unit 1）

> **只读验证**：未修改 contentpack / 数据库 / 音频 / `web/` / `learning/` / Android / V1.2.1；**AI 调用 0**；**外部网络请求 0**。
> 本地分析全部离线：MP3 解码沿用项目既有 `builder/mp3_to_wav.ps1`（WinRT，离线），声学分析沿用 `builder/build_word_audio_v01.py` 的参数与算法。

- 验证时间：2026-09-13
- 范围：**仅 Starter + Unit 1**（未触碰 Unit 2–6）
- 临时分析产物：`audit/P3-01_tmp/`（`p301_analyze.py`、`p301_classify.py`、`p301_audio_analysis.json`、`p301_classified.json`、`wav/`）

---

## 1. 结论摘要（先说结果）

**本批次没有产出任何 CONFIRMED 句级跟读素材。**

| 等级 | 数量 |
| --- | ---: |
| A ｜ CONFIRMED | **0** |
| B ｜ CANDIDATE | **1 条音频 / 8 个句子**（AU06 Starter A4 自我介绍朗读） |
| C ｜ NEEDS_REVIEW | **14 条音频** |

原因不是算法差，而是**教材事实与音频之间缺少"句子级"的桥**：

1. **听力/填空类教材原题本身就不印完整句子**（空位处是空格），音频里的完整句子在教材事实里根本不存在 → 无法用教材事实确认；
2. **没有转写文本**（`transcript` 表 0 行），也没有可用的本地 ASR/ffmpeg → 无法把音频逐句对齐到文本；
3. **教材文本↔活动的关系层不完整**：`text_references` 只覆盖 96 个 contentpack 活动中的 83 个；阅读/听力材料常只挂到 instruction；音频映射里 **6/15 的 `target_id` 为空**（只有 unit/section/activity_no/exercise_id）。

**可行且不违背规范的替代路线**：先建**活动级**跟读库（官方完整音频 + 教材完整印刷文本），句级切分留到有转写或人工核验之后。这与 V1.2.1 六·9「官方完整音频优先于未经验证的切割」完全一致。

---

## 2. 资源清单（Starter + Unit 1）

共 **15** 条官方音频（Starter 7 条：AU01–AU06 + AU48；Unit 1 8 条：AU07–AU13 + AU49）。全部 SHA256 与 contentpack `audio_asset` 一致（本脚本实测）。

| # | audio | 文件 | Unit | Section | 活动 | 时长(s) | 音频归属 | 教材文本可解析 | 有作答空位 |
| ---: | --- | --- | --- | --- | --- | ---: | --- | --- | --- |
| 1 | AU01 | 01_Starter_Get ready_2 Read and complete… | Starter | Get ready | A2 | 60.7 | CONFIRMED（activity） | ✗（只解析到活动号） | — |
| 2 | AU02 | 02_…3 Listen and complete the conversation… | Starter | Get ready | A3 | 33.5 | CONFIRMED | ✓ 5 句 | ✓ |
| 3 | AU03 | 03_…10 Listen and choose | Starter | Get ready | A10 | 58.2 | CONFIRMED（P2-6-F-4 几何修正） | ✓ 13 句 | ✓ |
| 4 | AU04 | 04_…1 Read and complete | Starter | Know your school | A1 | 85.9 | CONFIRMED | ✓ 8 句 | ✓ |
| 5 | AU05 | 05_…1 Read and complete | Starter | Get to know each other | A1 | 56.3 | CONFIRMED | ✓ 16 句 | ✓ |
| 6 | AU06 | 06_…4 Read and check your answers | Starter | Get to know each other | A4 | 43.4 | CONFIRMED | ✓ **8 句（无空位）** | ✗ |
| 7 | AU07 | 07_Unit 1_…2 Read the passage | Unit 1 | Understanding ideas | A2 | 109.4 | CONFIRMED | ✓ 13 句（段落编号干扰） | ✓（段落号误判） |
| 8 | AU08 | 08_…8 Work in pairs. Talk about a teacher… | Unit 1 | Understanding ideas | A8 | 72.5 | CONFIRMED | ✓ 4 句（思维导图问句） | ✓ |
| 9 | AU09 | 09_…1 Listen to the radio… | Unit 1 | Developing ideas | A1 | 51.1 | CONFIRMED | ✗（音频内容不印在教材上） | — |
| 10 | AU10 | 10_…Phonetics in use | Unit 1 | Developing ideas | ——（板块级） | 68.3 | CONFIRMED（section） | ✗（语音板块） | — |
| 11 | AU11 | 11_…2 Listen again and complete the poster | Unit 1 | Developing ideas | A2 | 44.2 | CONFIRMED | ✓ 6 句 | ✓ |
| 12 | AU12 | 12_…3 Listen to the conversation… | Unit 1 | Developing ideas | A3 | 175.0 | CONFIRMED | ✓ 19 句 | ✓ |
| 13 | AU13 | 13_…Reading for writing_2 | Unit 1 | Reading for writing | A2 | 101.4 | CONFIRMED | ✓ 9 句（**文本有提取瑕疵**） | ✗ |
| 14 | AU48 | 48_Starter_Words and expressions | Starter | Words and expressions | ——（板块级） | 90.2 | CONFIRMED（section） | ✗（词表） | — |
| 15 | AU49 | 49_Unit 1_Words and expressions | Unit 1 | Words and expressions | ——（板块级） | 92.1 | CONFIRMED（section） | ✗（词表） | — |

> 归属依据：`structured/audio/exercise_audio_map_v3.json`（status=CONFIRMED，理由=文件名指令与教材指令一致，相似度 0.99–1.00）。其中 6 条的 `target_id` 为 **None**，本脚本用 `(unit, section, activity_no)` 做确定性回退解析。

教材文本侧口径：只取 `content_block` 原文，排除 instruction / heading / footer / sidebar 与排版标记；区分 dialogue / 正文 / 活动说明 / 题目 / 选项 / 页眉页脚（见 `p301_audio_analysis.json` 的 `material_blocks` 与 `material_text`）。

## 3. 完整句子候选集

可解析出完整句子的音频：**10 / 15**（AU02–AU08、AU11–AU13），共 **104 个候选句子**。

不能解析的 5 条：AU01（文本关系只到活动号）、AU09（音频内容不印在教材上）、AU10/AU48/AU49（板块级：语音 / 词表）。

## 4–5. 时间边界与等级判定（规则）

- 声学边界：本地 RMS 静音分析，`HOP=10ms / MIN_SPEECH=140ms / MIN_GAP=200ms`，阈值 `max(10 分位+12dB, −45dB)`（与项目既有词音频派生方法完全一致）。
- **声学边界只作辅助证据**，不单独证明教材句子边界（V1.2.1 六·8 / P3-01 §七）。
- 判定：
  - **CONFIRMED**：教材句子确定 + 音频归属确定 + 该音频范围内**只有这一句**（无需按顺序推断）。
  - **CANDIDATE**：教材句子确定 + 音频归属确定，但一段音频含多句 → 句级时间边界需人工/转写核验。
  - **NEEDS_REVIEW**：教材文本不完整（有作答空位）、文本提取有瑕疵、或音频内容不在教材文本内。

判定结果：**CONFIRMED 0 ｜ CANDIDATE 1（8 句）｜ NEEDS_REVIEW 14**。

关键实测：Starter A4（AU06）音频 43.4s，静音法得 **14 个语音段**，而教材文本是 **8 个完整句子** —— 说明"段数=句数"的假设不成立（朗读会在句内停顿），**必须靠转写或人工才能逐句对齐**。

## 6. 样板结果（真实数据，不凑数）

| Unit | Activity | Audio | 时间（声学段，ms） | 教材完整句子 | 状态 | 证据 |
| --- | --- | --- | --- | --- | --- | --- |
| Starter | Get to know each other A4 | AU06（43.4s） | 14 段：590–2060 / 2910–3400 / 3700–5430 / 7360–8730 / 9990–13100 … | "Hello everyone!"（8 句之一） | **CANDIDATE** | 教材文本完整（P15:B3，无空位）+ 活动级音频映射 CONFIRMED；句级边界待人工 |
| Starter | Get to know each other A1 | AU05（56.3s） | 18 段 | 对话 16 句（另一部分为填空摘要） | NEEDS_REVIEW | 同题含作答空位 → 音频覆盖的内容多于完整文本 |
| Starter | Get ready A10 | AU03（58.2s） | 21 段 | 8 空对话 | NEEDS_REVIEW | 教材原题是"听录音选择"，8 处空位（P2-6-F-0-A N-01） |
| Unit 1 | Understanding ideas A2 | AU07（109.4s） | 42 段 | 阅读短文 9 段 | NEEDS_REVIEW | 段落编号被误判为空位 + 文本关系只到 instruction，需几何重建 |
| Unit 1 | Reading for writing A2 | AU13（101.4s） | 42 段 | 对话 9 句 | NEEDS_REVIEW | 文本有提取瑕疵（"Mum MiaA paper boat? MiaA paper boat?" 重复） |
| Unit 1 | Developing ideas A1 | AU09（51.1s） | 18 段 | —— | NEEDS_REVIEW | 听力材料原文本不在教材（学生用书不印听力原文） |
| Unit 1 | Developing ideas（Phonetics in use） | AU10（68.3s） | 29 段 | —— | NEEDS_REVIEW | 板块级语音材料，不是完整句子 |

> 说明：**CONFIRMED 等级为 0**，因此无法按要求给出 5 条 CONFIRMED 样例 —— 这里如实记录，而不是把 CANDIDATE 升格。

## 7. 8 个必答问题

**Q1｜Starter + Unit 1 一共有多少官方音频？**
**15 条**（13 条活动级 + 2 条板块级；Starter 7 + Unit 1 8），另含 2 条词表板块音频（AU48/AU49）。

**Q2｜其中多少可以可靠定位到 Activity？**
**13 / 15** 可定位到活动（`exercise_audio_map_v3` 全部 CONFIRMED）；但其中 **6 条的 `target_id` 为空**，需用 `(unit, section, activity_no)` 回退解析；2 条（AU10/AU48/AU49 中的板块级）只到 section 级。

**Q3｜多少音频包含可以提取的完整教材句子？**
**10 / 15** 能解析出句子；但其中 **8 条含作答空位**（文本不完整），真正"完整无空位"的只有 **2 条**（AU06、AU13），而 AU13 还有文本提取瑕疵 → 实际可用 **1 条（AU06，8 句）**。

**Q4｜多少句子可以得到可靠 start/end？**
严格意义上 **0 句**（无转写 → 无法证明某段时间对应某句）。可给出"句级候选边界"的只有 AU06 的 **8 句**（CANDIDATE，边界待人工确认）。

**Q5｜CONFIRMED / CANDIDATE / NEEDS_REVIEW 各多少？**
**0 / 1 条音频（8 句）/ 14 条音频**。

**Q6｜一个音频包含多个完整句子的情况能否可靠处理？**
**当前不能可靠处理。** 实测 AU06：8 句 vs 14 个声学段；AU13：9 句 vs 42 段；AU07：9 段文字 vs 42 段语音。声学段数与句子数不成比例，且句内停顿会把一句话切成多段，**没有转写就无法确定句边界**。

**Q7｜当前最大的技术瓶颈是什么？**
按影响排序：
1. **没有音频转写**（`transcript` 表 0 行；本机无 ffmpeg、无本地 ASR）；
2. **教材文本↔活动关系不完整**：`text_references` 83/96、阅读/听力材料只挂 instruction、音频映射 6 条 `target_id` 为空；
3. **听力/填空类练习的教材文本本身不完整**（空位）——这类音频的"完整句子"只存在于音频里，永远无法用教材事实确认；
4. 版面文字提取的瑕疵（段落编号被当空位、对话说话人标签粘连、重复片段）。

**Q8｜Unit 2–6 批量处理时，哪些可自动化、哪些必须人工核验？**
- **可自动化**：音频清单与 SHA 校验、离线解码、声学段计算、教材句子候选抽取（按块）、按活动归属（先用 `(unit,section,activity_no)` 解析、再逐步补齐 `target_id`）、等级初判。
- **必须人工核验**：句级时间边界（听音频逐句确认）、教材文本提取瑕疵的清理、空位类练习是否可排除、以及所有 CANDIDATE→CONFIRMED 的升级。
- **建议**：若引入**本地转写（无需联网、可离线、成本可控）**或人工转写，句级对齐才可能规模化；否则 2–6 单元只会把"必须人工"的比例继续放大。

## 8. 建议的下一步（不实施，仅建议）

1. **先建活动级跟读库**（本批次已有可靠基础）：`活动 → 官方完整音频 → 教材完整印刷文本`，用于"听整段 + 对照原文跟读"。归属与音频均已有 CONFIRMED 证据，无需切割。
2. 若必须做**句级**：先补一层 `transcript`（人工或本地离线转写），再用文本对齐切分；**不接受**用静音段数/文本长度猜测对齐。
3. 同步修复文本关系层（`text_references` 全量几何重建 + 补齐音频映射 `target_id`），这是句级路线的**前置条件**。

## 9. 基线保护

| 对象 | 结果 |
| --- | --- |
| `structured/learning/learning.db` | **未修改**：SHA256 `0C27267BF83A70A75BB400F0055B62CB2985A83EDD120B9AC790A7FD5E59CF91`，mtime 2026-09-13 15:50:09，start 与 end 完全一致（详见 §10 说明） |
| contentpack v5 | **未修改**：`ACEBC8C29CF5D11BAB50BF7962FBEE5DE42CD9CFC7FE48AB6316699D265E1A3F` |
| 54 个官方 MP3 | **未修改**（本脚本只读取；SHA 与 `audio_asset` 逐一比对一致） |
| `web/`、`learning/`、Android、V1.2.1 | 未修改 |
| 测试 | 未运行、未修改（本任务纯只读） |
| AI 调用 / 外部网络请求 | **0 / 0** |
| 新增文件 | 仅 `audit/P3-01_tmp/`（分析脚本与中间结果）与本文档 2 个文件 |

## 10. 关于 learning.db 的说明（必须如实记录）

本任务开始时记录的 `learning.db` 与我此前 P2-6-F 阶段的基线**已经不同**：

- 当前：SHA256 `0C27267B…`、mtime `2026-09-13 15:50:09`、`learning_record` **21** 行、`learning_session` 33、`mastery_state` 7；
- 此前基线：`DBAB743B…`、mtime `2026-09-12 23:15:13`、record 20。

差异来自一条 **15:50:08 产生的词汇学习记录**（`item_id = FLTRP-EN-7A-2022CUR:V:EAB999ECEC5C`，`result = done`），即**在我开始 P3-01 之前由真机使用产生**，不是本任务写入。本任务全程只读，未执行任何 DML；如需以"record=20"为验收口径，请以本条说明为准。

## 11. 停止声明

本任务只做**只读验证与分析**：未切割音频、未建正式数据库表、未改 Web/APP、未接入跟读功能或 AI 评分、未处理 Unit 2–6。已完成，立即停止。
