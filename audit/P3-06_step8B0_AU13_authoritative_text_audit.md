# P3-06 Step 8B-0 AU13 Authoritative Text Audit

> 只读核验：未修改任何代码 / DB / contentpack / 教材 / MP3 / P3-05 / Android；**未运行 Faster-Whisper**、未装依赖、未下载模型、未调用云端 AI、未生成切片。

## 1. 结论

```
PASS
```

- **AU13 是否已经得到可靠的权威教材文本基准**：**是**。已从**原始教材 PDF 第 29 页文本层**逐行核验出该活动对话的**权威 9 句**（含说话人归属），并查清 Step 8A 发现的两处抽取异常的**真实原因**。
- **是否可以进入 Faster-Whisper 对齐**：**可以（Whisper 准备状态 = READY）**，前提是使用本报告 §3 的 9 句文本（而非整页原始块文本）作为匹配基准。
- **无法确认的内容**：无（两处异常均已定位为**确定性的抽取问题**，非教材歧义）。

## 2. 原始素材信息

| 项目 | 结果 |
| --- | --- |
| 原始素材根目录 | `D:\ZhixueEnglish\2025年度初一外研版英语教材\`（本审计唯一原始素材来源） |
| audio_id | `FLTRP-EN-7A-2022CUR:AU13` |
| 原始 MP3 | `13_Unit 1_Developing ideas _Reading for writing_2 Read the passage and find out the meaning of the title.mp3`（2,433,836 B，SHA256 `DE4BCEC92B8E9293…`，未修改） |
| 时长 | 101,381 ms（≈101.4 s） |
| Module / Unit | （Starter 之后）**Unit 1** |
| Section | **READING_FOR_WRITING** |
| Activity | **A2** — *Read the passage and find out the meaning of the title.* |
| PDF page / 教材 page | **PDF 第 29 页 ／ 教材第 24 页** |

## 3. 权威正文句子（按教材实际顺序，来自 PDF 文本层 + 版面坐标）

该页对话在 PDF 中的版面为"说话人标签（左侧列 x≈75）+ 台词（x≈116）"两栏结构；下表按 y 坐标（自上而下）还原真实顺序。

| # | 权威教材文本 | 说话人 | 类型 | 来源 | 状态 |
| ---: | --- | --- | --- | --- | --- |
| — | *Activity A2 instruction:* Read the passage and find out the meaning of the title. | — | instruction | 原始教材 p24 | 非训练句 |
| — | *Page title:* Before your journey starts | — | 标题 | 原始教材 p24 | 非训练句 |
| 1 | Mia, how do you feel about your first day in junior high tomorrow? | **Dad** | 对话 | 原始教材 p24 | CONFIRMED |
| 2 | Well, I'm a little nervous. | **Mia** | 对话 | 原始教材 p24 | CONFIRMED |
| 3 | Don't worry. | **Mum** | 对话 | 原始教材 p24 | CONFIRMED |
| 4 | We've got something for you! | **Mum** | 对话 | 原始教材 p24 | CONFIRMED |
| 5 | Look! | **Mum** | 对话 | 原始教材 p24 | CONFIRMED |
| 6 | A paper boat? | **Mia** | 对话 | 原始教材 p24 | CONFIRMED |
| 7 | Yes, and it's also a letter from Mum and me. | **Dad** | 对话 | 原始教材 p24 | CONFIRMED |
| 8 | We want to share some thoughts with you. | **Dad** | 对话 | 原始教材 p24 | CONFIRMED |
| 9 | Oh, thank you! | **Mia** | 对话 | 原始教材 p24 | CONFIRMED |

> 说话人顺序（版面 y 坐标）：Dad 538.7 → Mia 556.7 → Mum 574.7 → Mia 592.7 → Dad 610.7 → Mia 646.7，共 6 个话轮、**9 句**（第 3 话轮 3 句、第 5 话轮 2 句）。

**同页但不属于 AU13 训练正文**（单独标识，勿混入）：A1 的词汇栏 `by yourself / problem / try your best / work hard`；侧栏指针 `Steps of looking up an entry in a dictionary ⇢ p116`。

## 4. 文本抽取问题（Step 8A 两处异常的真实原因）

**① `Mum MiaA paper boat?`**
并非"Mum 说话 + Mia 说话"的混合，而是**两个相邻元素的拼接**：说话人标签 **`Mum`**（x≈68.3，y≈574.7，对应"Don't worry…"那句）与下一行的说话人标签 **`Mia`**（x≈76.0，y≈592.7）+ 台词 **`A paper boat?`**（x≈116.4，同一行）被内容块合并成一个字符串 → 得到 `Mum`+`Mia`+`A paper boat?` = `Mum MiaA paper boat?`。
**正确形式**：`Mum` → `Don't worry. We've got something for you! Look!`；`Mia` → `A paper boat?`

**② `MiaA paper boat?`**
**说话人标签与台词粘连**：`Mia`（x≈76.0）与 `A paper boat?`（x≈116.4）本是同行的两栏，被抽成 `Mia`+`A paper boat?` → `MiaA paper boat?`。
**正确形式**：说话人 `Mia` ＋ 台词 `A paper boat?`

**③ 重复抽取**
`A paper boat?` 在 PDF 文本层中出现**两次**（同在 y≈592.7，x≈76.0/116.4），内容块也相应有 `B7` 与 `B17` 两条 → 这是**同一行被重复抽取**，**教材上只有一句**，不是两句。

**是否漏句/错断句**：未发现漏句；9 句与 AU13 音频的句数一致性（P3-01 用静音法也观测到"9 句"）互相印证。唯一风险是**说话人标签混入正文**与**重复块**，两者都可用确定性规则（按 x 坐标拆分标签/台词、去重）或人工核验收口。

## 5. P3-05 对照（不修改 P3-05）

| P3-05 条目 | 内容 | 判定 |
| --- | --- | --- |
| P3-05-S009（Dad） | Yes, and it's also a letter from Mum and me. | ✅ **正确**（对应本报告 #7；说话人标签已正确分离） |
| P3-05-S010 | We want to share some thoughts with you. | ✅ **正确**（对应本报告 #8） |

**整体判定**：P3-05 的两条**正确但不完整**——AU13 该活动实际有 **9 句**，P3-05 目前只收了 2 句（缺少 Dad 的两个话轮以外的 7 句）。**P3-05 未被修改**；本次仅记录差异，供后续（Step 8B）扩展使用。

## 6. Whisper 准备状态

```
READY
```

教材文本已经足够可靠，可以进入 **P3-06 Step 8B：AU13 Faster-Whisper 离线候选时间戳生成**。

执行建议（不实施）：① 以本报告 §3 的 **9 句**（去掉说话人标签、去掉重复块）作为匹配基准；② 说话人标签（Dad/Mia/Mum）单独保存，不进入句子文本；③ 仍按 Step 4→Step 6 流程只产出 **CANDIDATE**，人工试听后才能升级 VERIFIED。

---

## 最终输出

1. **PASS / FAIL**：**PASS**
2. **AU13 权威文本是否 READY**：**READY**
3. **实际确认的正文句子数量**：**9 句**（6 个话轮；不含 instruction / 标题 / 词汇栏 / 侧栏指针）
4. **发现的文本问题**：① 说话人标签与台词粘连（`MiaA paper boat?`）；② 相邻说话人标签被并入同一块（`Mum MiaA paper boat?`）；③ `A paper boat?` 被**重复抽取**（教材上只有一句）。三者均为确定性抽取问题，正确文本已确认，无 CHECK_REQUIRED 项。
5. **是否可以进入 Step 8B**：**可以（READY）**
6. **报告路径**：`D:\ZhixueEnglish\audit\P3-06_step8B0_AU13_authoritative_text_audit.md`
