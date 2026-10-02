# P3-06 Step 8B AU13 Faster-Whisper 离线候选时间戳生成

> 本步骤仅对 AU13 原始 MP3 执行一次有效 Faster-Whisper 转写；只生成审计/候选文件。
> 未修改正式代码、learning.db、contentpack、P3-05、Android、原始教材或原始 MP3；未切音频、未调用云端 AI、未下载模型。

## 1. 结论

```text
PASS（9 句全部生成 CANDIDATE）
```

同时存在一个**覆盖层**告警：

```text
coverage.status = MATCH_REVIEW_REQUIRED
```

含义：

- Step 8B-0 的 9 句权威文本基准**全部命中**，9/9 均为 `CANDIDATE`。
- 但 AU13 原始音频实际还包含标题、instruction 和后续书信正文；Step 8B-0 的 9 句只覆盖其中的**对话部分**。
- 因此不能把 AU13 整段 101.4 秒都宣布为“已对齐”；书信正文需要先补充权威文本核验，后续才能单独生成候选。

## 2. 运行记录

| 项目 | 结果 |
| --- | --- |
| audio_id | `FLTRP-EN-7A-2022CUR:AU13` |
| 原始 MP3 | `13_Unit 1_Developing ideas _Reading for writing_2 Read the passage and find out the meaning of the title.mp3` |
| 原始素材根目录 | `D:\ZhixueEnglish\2025年度初一外研版英语教材\` |
| 文件大小 | 2,433,836 B |
| SHA256 | `DE4BCEC92B8E9293FA755F875924B04722663B8313778E8D2AFECAF105300CEF` |
| 音频时长 | 101,355 ms（Whisper 解码口径；既有映射记录约 101,381 / 101,407 ms） |
| 模型 | `small`（`Systran/faster-whisper-small`，本地 D 盘 snapshot） |
| 运行方式 | **CPU + int8**，`local_files_only=True` |
| 模型加载 | 1.4 s |
| 有效转写 | 23.1 s |
| 有效 ASR 运行次数 | **1 次** |
| 是否下载模型 | 否 |
| 云端 AI / cloud calls | **0** |

补充说明：另有 1 次前置尝试在 PowerShell 中文路径编码错误时、进入音频解码之前终止；未产生 segment / word / sentence 结果，未修改任何正式数据。成功转写只执行了 1 次。

## 3. ASR 输出规模

| 项目 | 结果 |
| --- | ---: |
| segment 数 | 23 |
| word 数 | 173 |
| 对话 9 句所在范围 | 13.940 s – 44.420 s |
| 其余音频内容 | 0 – 12.580 s（instruction / 标题）、46.200 – 98.120 s（书信正文） |

完整 segment / word-level timestamps 已保存在结果 JSON 中。

## 4. AU13 9 句候选表

教材原文是唯一权威文本；Whisper 只提供时间位置。

| # | 教材原句 | start_ms | end_ms | duration_ms | 匹配 | status |
| ---: | --- | ---: | ---: | ---: | --- | --- |
| 1 | Mia, how do you feel about your first day in junior high tomorrow? | 13940 | 20260 | 6320 | 13/13 | CANDIDATE |
| 2 | Well, I'm a little nervous. | 21080 | 24300 | 3220 | 6/6 | CANDIDATE |
| 3 | Don't worry. | 25200 | 26280 | 1080 | 3/3 | CANDIDATE |
| 4 | We've got something for you! | 26900 | 28940 | 2040 | 6/6 | CANDIDATE |
| 5 | Look! | 28940 | 29720 | 780 | 1/1 | CANDIDATE |
| 6 | A paper boat? | 30840 | 32400 | 1560 | 3/3 | CANDIDATE |
| 7 | Yes, and it's also a letter from Mum and me. | 33380 | 38300 | 4920 | 11/11 | CANDIDATE |
| 8 | We want to share some thoughts with you. | 39040 | 41600 | 2560 | 8/8 | CANDIDATE |
| 9 | Oh, thank you! | 42280 | 44420 | 2140 | 3/3 | CANDIDATE |

匹配方式：教材句子 → 归一化词序列（大小写、标点、`I'm` / `it's` / `don't` / `we've` 展开）→ 在 Whisper word-level 时间轴上按教材顺序做连续窗口匹配 → `start_ms` 取首个匹配词起点，`end_ms` 取末个匹配词终点。

## 5. 句间边界检查

| 前句 | 后句 | gap_ms | 判断 |
| --- | --- | ---: | --- |
| 1 | 2 | 820 | 自然停顿 |
| 2 | 3 | 900 | 自然停顿 |
| 3 | 4 | 620 | 自然停顿 |
| 4 | 5 | 0 | 同一 ASR segment 内连续分句；word-level 边界未重叠 |
| 5 | 6 | 1120 | 自然停顿 |
| 6 | 7 | 980 | 自然停顿 |
| 7 | 8 | 740 | 自然停顿 |
| 8 | 9 | 680 | 自然停顿 |

- `start_ms` 单调递增：通过
- `end_ms > start_ms`：通过
- 相邻句 overlap：0
- 时间范围落在原始音频内：通过
- 单句最大 duration：6320 ms；最小 duration：780 ms；未发现异常超长区间

## 6. 自动检查

| 检查项 | 结果 |
| --- | --- |
| 9/9 是否有候选 | 通过 |
| 教材文本与 Step 8B-0 完全一致 | 通过 |
| `start_ms >= 0` | 通过 |
| `end_ms > start_ms` | 通过 |
| `end_ms <= duration_ms` | 通过 |
| duration = end - start | 通过 |
| sentence start/end 单调 | 通过 |
| 相邻句 overlap | 0 |
| 负时间 | 0 |
| word timestamps 正数 / 单调 | 通过 |
| 明显异常超长区间 | 未发现 |
| 明显漏句（整个 AU13 活动范围） | **MATCH_REVIEW_REQUIRED** |

## 7. ASR 局限与注意点

1. `Don't worry.` 与 `We've got something for you.` 在 ASR 中被合并进同一 segment，但 word-level timestamps 正确给出两句边界。
2. `Look,` 与 `a paper boat?` 在 ASR 中被合并进同一 segment，但 word-level timestamps 正确拆出 `Look!` 与 `A paper boat?`。
3. ASR 将 instruction 中的 “Activity 2” 识别成 “Activity too.”；仅属于 instruction，未进入训练句。
4. ASR 输出 `mum` 小写，教材为 `Mum`；教材文本未被修改。
5. 9 句对话全部 100% 归一化词匹配，但仍只能标记 `CANDIDATE`，必须经过 Step 8C 人工逐句试听。

## 8. 覆盖层问题：AU13 音频还包含书信正文

转写证明 AU13 原始音频不只是 9 句对话，而是包含：

1. `Reading for writing. Activity 2.`（ASR 将 2 识别为 too）
2. `Read the passage and find out the meaning of the title.`
3. `Before your journey starts`（标题）
4. 9 句对话（本步骤已生成候选）
5. 后续书信正文，例如 `Dear Mia, time flies.`、`Primary school is like a small pool.`、`With love, dad and mum.` 等

项目既有结构化教材记录也包含这些书信文本，因此它们不是 Whisper 凭空生成的内容，而是 AU13 官方音频对应的教材正文的一部分。Step 8B-0 的 9 句基准实际只覆盖了**对话部分**，没有覆盖完整 passage。

本步骤按任务要求没有再扩展匹配书信正文，也没有生成其时间候选；该缺口标记为 `MATCH_REVIEW_REQUIRED`。后续如需覆盖完整 AU13，应先补做一次只读权威文本核验，再另行生成书信句级候选。

## 9. 数据安全确认

| 项目 | 结果 |
| --- | --- |
| 原始教材 | 未修改 |
| 原始 MP3 | 未修改，SHA256 与转写前一致 |
| learning.db | 未修改 |
| contentpack | 未修改 |
| P3-05 | 未修改 |
| Android / 正式学习流程 | 未修改 |
| 正式代码 | 未修改 |
| 音频切片 / 转码 / 复制 | 0 |
| 模型下载 | 0 |
| 依赖安装 | 0 |
| 云端 AI / cloud calls | 0 |
| 自动 VERIFIED | 0 |

## 10. 最终判断

```text
AU13 9 句基准：PASS
9 句候选数：9/9
per-sentence MATCH_REVIEW_REQUIRED：0
coverage MATCH_REVIEW_REQUIRED：1（书信正文未纳入本次 9 句基准）
```

下一步可以进入 **P3-06 Step 8C：AU13 候选时间测试页 + 真机逐句试听**，但测试页应只使用本报告的 9 条对话候选，并明确标注：AU13 音频中的书信正文尚未完成权威文本补核和时间候选生成。

不得自动升级为 VERIFIED。
