# P3-06 Step 5：AU06 现有 Whisper 时间戳离线候选重算验证

> **未重新运行 Whisper**、未下载模型、未安装依赖、未调用云端 AI、未修改 learning.db / contentpack / 原始 MP3 / P3-05、未处理 AU48–AU54 与 288 条词汇时间标记。

## 1. 执行结论

```
PASS
```

仅用 Step 4 已生成的 55 个 word-level timestamps，按教材原句顺序重算，**6 个训练句 + 1 条活动说明全部命中（每句词级匹配率 100%）**，时间单调递增、无重叠，唯一的大间隔有明确解释（见 §5）。

## 2. 输入

| 文件 | 用途 |
| --- | --- |
| `audit/P3-06_step4_au06_alignment_result.json` | **唯一时间来源**：55 个 words（含 start/end）+ 4 个 segment + 原始 MP3 元信息 |
| `audit/P3-06_step4_au06_alignment_report.md` | 上一步结论（PARTIAL PASS）与设备/模型信息 |
| `audit/P3-05_samples/shadowing_manifest.json` | 教材原句来源（Starter Activity 4，逐字取自 content_block） |

匹配只在**归一化副本**上进行（小写、去标点、`I'm`→`I am`、`13`→`thirteen`）；**教材原句一字未改**。

## 3. Activity 4 开场说明

✅ **识别到**：`Activity 4. Read and check your answers.` → **0 – 5140 ms**，7/7 词匹配。
按任务要求标记为 **instruction / non_training_sentence**，**不作为跟读训练句**。
与用户人工听音一致：正文确实在约 0:07 才开始（首训练句 7000 ms）。

## 4. 句子候选表

| # | 教材原句 | start_ms | end_ms | duration_ms | 匹配情况 | status |
| ---: | --- | ---: | ---: | ---: | --- | --- |
| — | *Activity 4. Read and check your answers.*（说明，非训练句） | 0 | 5140 | 5140 | 7/7 | instruction |
| 1 | Hello everyone. | **7000** | **8540** | 1539 | 2/2 | CANDIDATE |
| 2 | My name is Zhu Xiaomeng. | **9220** | **12880** | 3660 | 5/5 | CANDIDATE |
| 3 | I'm 13 years old. | **13360** | **16200** | 2840 | 5/5 | CANDIDATE |
| 4 | I like running, playing football and swimming. | **24380** | **29500** | 5120 | 7/7 | CANDIDATE |
| 5 | I'm a bit nervous now, but I'm also happy to meet you. | **30580** | **36140** | 5560 | **14/14** | CANDIDATE |
| 6 | I want to make friends with you all. | **37000** | **40040** | 3039 | 8/8 | CANDIDATE |

匹配到的 ASR 词（供人工核对，节选）：

```
1  Hello everyone.
2  My name is Zhu Xiaomeng.
3  I'm 13 years old.
4  I like running, playing football and swimming.
5  I'm a bit nervous now, but I'm also happy to meet you.
6  I want to make friends with you all.
```

## 5. 句间边界表

| 前句 | 后句 | gap_ms | overlap | 判断 |
| --- | --- | ---: | --- | --- |
| Hello everyone. | My name is Zhu Xiaomeng. | **680** | 无 | ✅ 正常换句停顿 |
| My name is Zhu Xiaomeng. | I'm 13 years old. | **480** | 无 | ✅ 正常 |
| I'm 13 years old. | I like running, playing football and swimming. | **8180** | 无 | ⚠️ 看似大空白，**已解释**：中间还夹着教材另外两句 —— ASR 词表在该区间连续出现 `My birthday is in May.` 与 `I love sports very much.`（16.2–24.4s），即"第 4 句"其实是教材第 6 句，空白由未纳入本次匹配的两句填充 |
| I like running, playing football and swimming. | I'm a bit nervous now, but I'm also happy to meet you. | **1080** | 无 | ✅ 正常 |
| I'm a bit nervous now, but I'm also happy to meet you. | I want to make friends with you all. | **860** | 无 | ✅ 正常 |

（A：`Activity 4…` → `Hello everyone.` 的 gap = **1860 ms**，符合"说明结束后停顿约 2 秒再开始正文"。）

**结论：没有任何重叠；唯一大间隔由同一音频中未被本次任务纳入的两句教材句填充，属正常。**

## 6. 第 5 句重点分析

> `I'm a bit nervous now, but I'm also happy to meet you.`

**✅ 可以通过现有 word timestamps 得到完整候选**：**30580 – 36140 ms（5560 ms）**，**14/14 词全部匹配**。

- 该句在 ASR 词表中是**连续的一段**（`I'm | a | bit | nervous | now, | but | I'm | also | happy | to | meet | you.`），**没有跨句截断**；
- 用户人工听到的"约 0:32 处 `now, but I'm also happy to meet you.`"落在该区间内部（30.58–36.14s），**与人工听音完全吻合**；
- 因此**不得**把它截断成 `I'm a bit nervous`（该半句只到约 32.5s 附近）；本步骤已按整句匹配，未产生半句候选。

## 7. Whisper 局限（如实记录）

| 类别 | 实测 |
| --- | --- |
| 识别错误的词 | 未见明显错误；`Zhu Xiaomeng`、`Xiaomeng.` 均正确；数字以 `13` 出现（未写成 thirteen，归一化后不影响匹配） |
| 缺失的句子 | **无缺失**：ASR 词表包含全部 8 句（`Hello everyone.` / `My name is Zhu Xiaomeng.` / `I'm 13 years old.` / `My birthday is in May.` / `I love sports very much.` / `I like running…` / `I'm a bit nervous…` / `I want to make friends with you all.`） |
| 可信边界 | 本次 7 条的 start/end 均由**词级**时间戳首末词决定，句内无空洞；句间 gap 480–1080 ms，符合朗读换句节奏 |
| 必须人工听音确认的边界 | ① 第 1 句起点 7000ms 是否已包含全部语音（前 1.86s 是活动说明的尾音）；② 未被本次匹配的两句（`My birthday is in May.` / `I love sports very much.`）的边界；③ 各句末尾是否多含少量尾音（词级时间戳通常贴词尾，建议听一遍确认是否含呼吸/连读） |
| 其他 | segment 只有 4 段（模型把它们合并成大段），**本次全部改用 word 级时间**，未使用 segment 边界——这正是上一轮仅靠 segment 会出错的地方 |

## 8. 下一步建议（最小）

**只做一件事**：由人工在 43.3s 的 AU06 上，按本报告 §4 的 6 条候选逐句听一遍（重点：句 1 起点 7000ms、句 5 的 30580–36140ms 是否完整覆盖），确认后即可把这 6 条从 `CANDIDATE` 升级为 `VERIFIED`；同时补上未纳入的两句（`My birthday is in May.` / `I love sports very much.`）形成 AU06 完整 8 句候选。

**不进入 Step 6**，不批量处理，不写入正式数据。

## 报告纪律

1. **修改了什么**：仅新增本报告；未修改任何项目代码/数据。
2. **是否重新运行 Whisper**：**否**（只读取 Step 4 的 JSON）。
3. **AI 调用次数**：**0**（无云端、无模型推理）。
4. **正式数据是否修改**：**否**（learning.db / contentpack / P3-05 / 原始 MP3 全部未动）。
5. **Step 5 报告路径**：`D:\ZhixueEnglish\audit\P3-06_step5_au06_candidate_recheck.md`
6. **最终结论**：**PASS**
