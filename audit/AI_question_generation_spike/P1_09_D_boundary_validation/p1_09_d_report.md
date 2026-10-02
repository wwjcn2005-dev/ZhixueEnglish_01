# P1-09-D 实施报告 · AI 英语质量复核边界样本验证

最终结论：**P1-09-D_STOP_AND_FIX**

理由一句话：

> 15 道人工设计的边界 fixture 全部完成复核，AI 在 5 个类别上表现干净（英语错误、错误干扰项、
> 上下文不足、现实常识克制、机械题不误杀），**但在本次最重要的类别"真正第二正确答案"上 0/2 全漏**，
> 而且两次都给出 `HIGH` 置信度与"无显著问题，答案与课文一致"的理由——
> 即 AI 会**高置信度地掩盖项目最关心的缺陷**。这不是继续调 Prompt 能解决的问题。

```text
AI 调用 = 1     retry_count = 0     finish_reason = stop     fixture = 15/15
question_library.db / learning.db / contentpack / 教材资产 / Web / Android / validator
  = 0 修改（1164 个正式文件 manifest 前后完全一致）
未写正式题库、未产生 question_event、未自动 APPROVED / ACTIVE、未安装依赖、未改 gold
```

---

## 1. 调用账目（真实数据）

| 项 | 值 |
| --- | --- |
| api_calls | **1** |
| retry_count | **0** |
| model | `deepseek-v4-pro` |
| temperature / max_tokens / reasoning_effort | `0.2` / `16384` / `low` |
| prompt_version | `P1-09-D-v1` |
| finish_reason | **stop** |
| prompt_tokens | 3,919 |
| completion_tokens | 11,452（其中 reasoning 9,875 = 86.2%） |
| total_tokens | **15,371**（15 题 → 约 **1,024.7 tokens/题**） |
| latency | 129,721 ms（129.7 秒，约 8.6 秒/题） |
| 结构状态 | PARSED（15/15、取值合法、无禁止字段） |

与 P1-09-B 对比：P1-09-B 为 9,146 tokens / 10 题 = 914.6 tokens/题；
本次 1,024.7 tokens/题，**每题高约 12%**（输入更完整、reasoning 占比更高）。
相对生成成本（P1-06 实测 3,756.4 tokens/题）约为 **27.3%**。

---

## 2. Fixture 设计（人工预先设计，非 AI 生成）

```text
15 道，7 类，全部 fixture_only = true
A 真正错误英语 ×2 · B 明显错误干扰项 ×2 · C 真正第二正确答案 ×2 · D 现实常识冲突 ×2
E 上下文不足 ×2 · F 高学习价值正常题 ×3 · G 机械但合理的重点词填空 ×2
```

设计原则与保护：

```text
全部由实验人员在调用前设计（build_fixtures.py），未调用 AI 生成 fixture
素材尽量取自教材真实原文（contentpack 只读块），自撰句子全部标记 fixture_only=true
不写入任何教材数据；fixture 不被当作教材事实
每道 fixture 在调用前都有 fixture_id / question / options / answer / textbook_context /
  hidden_gold_label / gold_reason / category
hidden_gold.json 与 ai_input_snapshot.json 物理分离；build_fixtures.py 内置 gold 泄漏断言
```

锁定值（调用前）：

```text
fixtures_sha256     = 2BA8A2C29DEA4903F8507EC361F20941C56214160F686F59C6E4837A7AD1BD1E
hidden_gold_sha256  = 966F62BD5037DEBFB2B87E26D0EFE88D9B249B0196EB348248B19A37450E29A9
ai_input_sha256     = AB129DDB913C07FBC9F149D1E83E2B5A75D94580A58CC001612C4EBF8B17EE68
ai_input_chars      = 7,862
gold 泄漏检查        = PASS（AI 输入中不含任何 gold 字段或 gold 文本）
```

AI 输入严格按 P1-09-C Review Context Contract V1 的 Minimal 级构造，只包含：
fixture_id、question_type、题干、选项、stored_answer、教材位置、**证据块全文**、作答标准、年级背景。
**不含** hidden_gold、gold_reason、validator 结论、mechanical_rewrite 程序标志、lifecycle、
生成 explanation、known_issue、P1-09-B/09-C 对照结论。

---

## 3. AI 复核原始结果（15/15 全部返回）

| fixture | 类别 | 英语 | 唯一性 | 自然 | 学习价值 | 干扰项 | 年级 | 机械等级 | 上下文 | 建议 | 置信 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FIX-A1 | A | **FAIL** | PASS | FAIL | CONCERN | N/A | PASS | DIRECT_REPRODUCTION | SUFFICIENT | REJECT | HIGH |
| FIX-A2 | A | **FAIL** | PASS | FAIL | CONCERN | N/A | PASS | NOT_APPLICABLE | SUFFICIENT | REJECT | HIGH |
| FIX-B1 | B | PASS | PASS | PASS | PASS | **CONCERN** | PASS | DIRECT_REPRODUCTION | SUFFICIENT | REVIEW | MEDIUM |
| FIX-B2 | B | FAIL | PASS | CONCERN | PASS | **CONCERN** | PASS | NOT_APPLICABLE | SUFFICIENT | REJECT | HIGH |
| FIX-C1 | C | PASS | **PASS** | PASS | PASS | PASS | PASS | DIRECT_REPRODUCTION | SUFFICIENT | **ACCEPT** | HIGH |
| FIX-C2 | C | PASS | **PASS** | PASS | PASS | PASS | PASS | MECHANICAL_REWRITE | SUFFICIENT | **ACCEPT** | HIGH |
| FIX-D1 | D | PASS | PASS | PASS | PASS | PASS | PASS | NOT_APPLICABLE | SUFFICIENT | ACCEPT | HIGH |
| FIX-D2 | D | PASS | PASS | PASS | PASS | PASS | PASS | NOT_APPLICABLE | SUFFICIENT | ACCEPT | HIGH |
| FIX-E1 | E | PASS | CONCERN | CONCERN | CONCERN | N/A | PASS | NOT_APPLICABLE | **CONTEXT_INSUFFICIENT** | REVIEW | LOW |
| FIX-E2 | E | PASS | CONCERN | PASS | CONCERN | N/A | PASS | NOT_APPLICABLE | **CONTEXT_INSUFFICIENT** | REVIEW | LOW |
| FIX-F1 | F | PASS | PASS | **CONCERN** | PASS | **CONCERN** | PASS | MECHANICAL_REWRITE | SUFFICIENT | **REVIEW** | MEDIUM |
| FIX-F2 | F | PASS | PASS | PASS | PASS | PASS | PASS | NOT_APPLICABLE | SUFFICIENT | ACCEPT | HIGH |
| FIX-F3 | F | PASS | PASS | PASS | PASS | PASS | PASS | NOT_APPLICABLE | SUFFICIENT | ACCEPT | HIGH |
| FIX-G1 | G | PASS | PASS | PASS | PASS | N/A | PASS | DIRECT_REPRODUCTION | SUFFICIENT | ACCEPT | HIGH |
| FIX-G2 | G | PASS | PASS | PASS | PASS | N/A | PASS | DIRECT_REPRODUCTION | SUFFICIENT | ACCEPT | HIGH |

**加粗** = 与 gold 不一致的位置。

---

## 4. 盲对照：维度级与决策级两套结果（任务书 §14–§16）

### 4.1 总览

```text
fixture 总数            15
参与评分的维度检查       41
维度命中                36 / 41
维度 FALSE_NEGATIVE     2   （FIX-C1、FIX-C2 的 answer_unique）
维度 FALSE_POSITIVE     0
维度 SOFT_DEVIATION     0
未分类偏离              3   （FIX-F1 的 naturalness / distractor_quality / mechanical_level；gold 未给这三项分类）

决策命中                12 / 15
决策 FALSE_NEGATIVE     2   （FIX-C1、FIX-C2 判 ACCEPT，gold 规则为 not_accept）
决策 FALSE_POSITIVE     0
完全命中（维度 + 决策）   12 / 15

决策掩盖维度错误         0 例（不存在"维度判错但决策恰好正确"的情况）
generic 中文理由        8 / 15（同一句话"无显著问题，答案与课文一致。"出现 7 次）
```

### 4.2 按类别

| 类别 | n | 维度命中 | 维度 FN | 维度 FP | 决策命中 | 完全命中 |
| --- | --- | --- | --- | --- | --- | --- |
| A 真正错误英语 | 2 | 2/2 | 0 | 0 | 2/2 | 2/2 |
| B 明显错误干扰项 | 2 | 4/4 | 0 | 0 | 2/2 | 2/2 |
| **C 真正第二正确答案** | 2 | **0/2** | **2** | 0 | **0/2** | **0/2** |
| D 现实常识冲突 | 2 | 2/2 | 0 | 0 | 2/2 | 2/2 |
| E 上下文不足 | 2 | 2/2 | 0 | 0 | 2/2 | 2/2 |
| F 高学习价值正常题 | 3 | 18/21 | 0 | 0 | 2/3 | 2/3 |
| G 机械但合理的重点词填空 | 2 | 8/8 | 0 | 0 | 2/2 | 2/2 |

### 4.3 逐题明细

| fixture | category | gold | ai_result | dimension_match | decision_match | FP | FN |
| --- | --- | --- | --- | --- | --- | --- | --- |
| FIX-A1 | A | english_correct=FAIL | FAIL | true | true | – | – |
| FIX-A2 | A | english_correct=FAIL | FAIL | true | true | – | – |
| FIX-B1 | B | distractor∈{FAIL,CONCERN}；answer_unique=PASS | CONCERN / PASS | true | true | – | – |
| FIX-B2 | B | 同上 | CONCERN / PASS | true | true | – | – |
| FIX-C1 | C | answer_unique=FAIL | **PASS** | **false** | **false** | – | **answer_unique** |
| FIX-C2 | C | answer_unique=FAIL | **PASS** | **false** | **false** | – | **answer_unique** |
| FIX-D1 | D | answer_unique=PASS | PASS | true | true | – | – |
| FIX-D2 | D | answer_unique=PASS | PASS | true | true | – | – |
| FIX-E1 | E | context=CONTEXT_INSUFFICIENT；决策不得 REJECT | CONTEXT_INSUFFICIENT / REVIEW | true | true | – | – |
| FIX-E2 | E | 同上 | CONTEXT_INSUFFICIENT / REVIEW | true | true | – | – |
| FIX-F1 | F | 六维 PASS、ACCEPT | 自然 CONCERN、干扰项 CONCERN、REVIEW | **false** | **false** | 未分类（见 §5.4） | – |
| FIX-F2 | F | 六维 PASS、ACCEPT | 全 PASS / ACCEPT | true | true | – | – |
| FIX-F3 | F | 六维 PASS、ACCEPT | 全 PASS / ACCEPT | true | true | – | – |
| FIX-G1 | G | learning_value∈{PASS,CONCERN}、不 REJECT | PASS / ACCEPT | true | true | – | – |
| FIX-G2 | G | 同上 | PASS / ACCEPT | true | true | – | – |

---

## 5. 七个类别的逐项结论（任务书 §14 的 7 个重点统计）

### 5.1 English：真正错误英语 2 道 → **2/2 全部发现** ✔

```text
FIX-A1  AI：english_correct=FAIL  "题干中 Grandpa like 应为 Grandpa likes，主谓不一致。"
FIX-A2  AI：english_correct=FAIL  "题干中 Plants is 应为 Plants are，主谓不一致。"
```

两条都准确指出**具体错在哪里**，并且都给出 `SUGGEST_REJECT`。这是本次最干净的能力证据。

### 5.2 Distractor：明显错误干扰项 2 道 → **2/2 全部发现**（判 CONCERN）✔

```text
FIX-B1  AI：distractor_quality=CONCERN  "三个干扰项在 in the school ___ 中都不自然，干扰性较弱。"
FIX-B2  AI：distractor_quality=CONCERN  "选项 to make rain 不能作 make 的宾语，语法上不可选。"
```

FIX-B2 的理由与实验人员设计的缺陷完全对应；同时两条的 `answer_unique` 都判 PASS（gold 也要求 PASS），
说明 AI 没有把"干扰项有缺陷"与"答案不唯一"混为一谈。

### 5.3 Answer uniqueness：真正第二正确答案 2 道 → **0/2 全漏** ✘（本次最重要发现）

```text
FIX-C1  "Grandpa likes playing the erhu in the park with his ___." 答案 friends
        设计的第二答案：students（语法成立、语义成立、不被课文排除）
        AI：answer_unique=PASS，SUGGEST_ACCEPT，confidence=HIGH
        理由："无显著问题，答案与课文一致。"

FIX-C2  "Ms Chen writes a ___ on the blackboard." 答案 sentence
        设计的第二答案：word（writes a word on the blackboard 完全成立）
        AI：answer_unique=PASS，SUGGEST_ACCEPT，confidence=HIGH
        理由："无显著问题，答案与课文一致。"
```

**这是本次实验最重要的负面结果，必须如实写明：**

```text
1. P1-09-C 的 Answer Uniqueness Contract V1 已经写进了本次 system prompt：
   "First try to find a second answer ... Never answer PASS merely because the stored answer
    appears in the textbook."
   → 模型**仍然**用了"答案与课文一致"作为通过理由。
2. 失败方向是**顺从教材**（textbook deference），不是漏读题干：
   两次都给了 HIGH 置信度，并且在 4 个维度上全部判 PASS。
3. 这与 P1-09-B 的结论形成明确对比：
   P1-09-B 里 answer_unique 表现最好（4/4），但那些题的第二答案是**显而易见的缺上下文**（I am ___, too.）；
   本次的第二答案需要**与教材语境对抗推理**（students / word 并不与课文矛盾），模型在这一档完全失手。
4. 对产品后果最严重的一点：AI 会用"无问题"的高置信结论**掩盖**项目最关心的这类缺陷，
   而人工审核人不是英语教师，很难自行发现。
```

### 5.4 Reality conflict：现实常识冲突 2 道 → **2/2 没有误造第二答案** ✔

```text
FIX-D1  （课文：trees can make their own rain；现实：sugar/oxygen/food 也成立）
        AI：answer_unique=PASS，SUGGEST_ACCEPT  → 正确，没有被现实常识带偏
FIX-D2  （课文：water from the root；现实：水来自土壤）
        AI：answer_unique=PASS，SUGGEST_ACCEPT  → 正确
```

配合 §5.3 一起读，可以得到一个更精确的画像：

> **模型能抵抗"现实常识"（D 类）干扰，却抵抗不了"教材原文"（B/C 类）的锚定效应。**

### 5.5 Context insufficient：上下文不足 2 道 → **2/2 正确输出 CONTEXT_INSUFFICIENT** ✔

```text
FIX-E1  AI：context_status=CONTEXT_INSUFFICIENT，confidence=LOW，SUGGEST_REVIEW
        "上下文未提供颜色信息，无法判断 grey 是否唯一。"
FIX-E2  AI：context_status=CONTEXT_INSUFFICIENT，confidence=LOW，SUGGEST_REVIEW
        "上下文未出现 stage，无法验证答案依据。"
```

两条都**没有**退化为 `SUGGEST_REJECT`，完全符合 P1-09-C §11 的要求；
而且理由直接说明了缺什么（颜色信息 / stage 未出现）。
这说明"上下文不足"这条新契约在真实调用中是**可执行且有效**的。

### 5.6 Learning value：高学习价值正常题 3 道 → **2/3 完全命中，1 条分歧**（见 §6）⚠

```text
FIX-F2（因果理解题）AI 全 PASS / ACCEPT   ✔
FIX-F3（两句整合题）AI 全 PASS / ACCEPT   ✔
FIX-F1（fans 重组题）AI 判 naturalness=CONCERN、distractor_quality=CONCERN、REVIEW  → 与 gold 不一致
```

### 5.7 Mechanical but valid：合理重点词填空 2 道 → **2/2 没有因为机械形式判 FAIL** ✔

```text
FIX-G1（名词性物主代词 hers）AI：mechanical_level=DIRECT_REPRODUCTION，learning_value=PASS，ACCEPT
FIX-G2（say + 直接引语）     AI：mechanical_level=DIRECT_REPRODUCTION，learning_value=PASS，ACCEPT
```

两条都被识别为机械形式，但**都判 learning_value=PASS 并建议通过**，
说明 P1-09-C 的"机械形式 ≠ 自动 FAIL"这条硬规则在真实调用中被遵守。

---

## 6. 必须单独说明的两处细节

### 6.1 FIX-F1：这一次更可能是 **fixture/gold 的缺陷**，不是 AI 误杀

AI 的理由是"fans of him 说法不自然，干扰项语法上无法填入"。离线核对：

```text
题干：Many people love the erhu player's music. There are many ___ of him in the park.
选项：fans / players / teachers / doctors
→ "many players of him" / "many teachers of him" 确实不自然（of him 与人称搭配受限）
→ 而 "fans of him" 虽然可以接受，但确实不如 "his fans" 自然
```

结论：**AI 的这一条批评有实际依据**。按 gold 的字面它属于"维度偏离"（gold 要求全 PASS），
但按语言事实它更接近于"实验人员设计的 fixture 本身有弱点"。
本次如实记录为**未分类偏离**，不把它算作 AI 的误杀，也**不修改 gold**。

### 6.2 解释质量：8/15 条理由属于泛化（EXPLANATION_WEAK）

```text
8 条被标记为泛化理由（含 7 次完全相同的"无显著问题，答案与课文一致。"）
FIX-C1 / FIX-C2 / FIX-D1 / FIX-D2 / FIX-F2 / FIX-F3 / FIX-G1 / FIX-G2
```

对 PASS 题使用统一短句本身不算错误，但关键在于：
**FIX-C1 / FIX-C2 正是用这句泛化理由掩盖了真正的缺陷**。
理由不带具体信息时，人工审核人无法据此复核——这与"AI 复核的价值是提供可核对的判断"直接冲突。

### 6.3 契约需要补一处定义：选项级语法错误算哪个维度？

FIX-B2 的 AI 同时给出 `english_correct=FAIL` 与 `distractor_quality=CONCERN`
（因为 `to make rain` 是"选项"，而契约里 english_correct 也覆盖选项）。
本次 gold 未把 english_correct 计入 B 类评分，所以不产生 ERROR，
但这是一处**契约歧义**，下一阶段需要明确：

```text
选项自身的语法错误：只计入 distractor_quality ？还是同时计入 english_correct ？
```

---

## 7. 正式资产保护（任务书 §19）

```text
调用前 manifest EA604045719475772D0703EC3D0906806044773DB0900338B5E7E3FF1E17742B
调用后 manifest EA604045719475772D0703EC3D0906806044773DB0900338B5E7E3FF1E17742B
新增 0 / 删除 0 / 修改 0            （1164 个正式资产文件）

question_library.db 7AA12CA5EB24417BF0AE7E97A8161920B501825D030D69A8E0863272AC695DA7 → 未变
learning.db         0C27267BF83A70A75BB400F0055B62CB2985A83EDD120B9AC790A7FD5E59CF91 → 未变
contentpack v5      65829CA73E41B75ACA010B93B7339EDDF0F666F919148F0F69ED898419700C39 → 未变

question_library 行数不变     = true
question_event 事件分布不变    = true
ACTIVE 1 / PENDING_REVIEW 19 / REJECTED 1 = 不变
stale = 1 的题数不变          = true
integrity_check = ok
```

AI 复核结果只写入本审计目录；未新增正式题库题目、未写 question_event、未自动 APPROVED / ACTIVE。

---

## 8. PASS 条件逐条核对（任务书 §21）

| # | 条件 | 结果 |
| --- | --- | --- |
| 1 | 15 道 fixture 全部完成 | **是**（15/15） |
| 2 | AI 调用 ≤ 2 | **是**（1 次） |
| 3 | 没有因为质量不满意而重试 | **是**（retry_count=0） |
| 4 | 输出完整且结构合法 | **是**（PARSED，15/15，枚举合法，无禁止字段） |
| 5 | fixture 标签在调用前锁定 | **是**（fixtures/hidden_gold/ai_input 三个 SHA256 均已记录，gold 独立存放） |
| 6 | AI 未看到 gold | **是**（内置泄漏断言通过；gold 与输入物理分离） |
| 7 | comparison 在调用后完成 | **是** |
| 8 | 至少能判断核心维度的真实能力 | **是**（结论明确，且包含负面结论） |
| 9 | question_library.db 0 修改 | **是** |
| 10 | learning.db 0 修改 | **是** |
| 11 | contentpack 0 修改 | **是** |
| 12 | 正式资产 manifest 0 变化 | **是**（mismatch=0，missing=0） |
| 13 | 无正式题库写入 | **是** |
| 14 | 无自动 APPROVED / ACTIVE | **是** |
| 15 | 没有为了结果好看而修改 gold | **是**（gold 未改；FIX-F1 的分歧按原样记录） |

**15 条 PASS 条件全部满足**，但按任务书 §20 的要求，能力出现"明显不可靠"时必须如实给出
`STOP_AND_FIX`，不得因为条件满足就写成 PASS。

---

## 9. 最终报告 11 问（任务书 §22）

### 1. AI 英语错误识别是否成立？
**成立。** 2/2 全部发现，且都准确指出具体错误位置（`Grandpa like`→`likes`；`Plants is`→`are`），
并给出 `SUGGEST_REJECT`。这是本次最可靠的能力。

### 2. AI 答案唯一性识别是否成立？
**不成立。** 关键的 2 道"真正第二正确答案"题 **0/2 全漏**，两次都判 `answer_unique=PASS` +
`SUGGEST_ACCEPT` + `HIGH` 置信度，理由是"无显著问题，答案与课文一致"。
失败模式是**顺从教材原文**：模型把"课文里出现过"当成"答案唯一"。
P1-09-C 契约里已经明确禁止这种做法，但本次实测显示**提示词层面禁止无效**。

### 3. AI 干扰项识别是否成立？
**成立（判定为 CONCERN 级）。** 2/2 都指出了缺陷（"in the school ___ 中都不自然"；
"to make rain 不能作 make 的宾语"），且没有与答案唯一性混淆。
注意：两条都判 CONCERN 而不是 FAIL——本次设计的是"可辨认但不致命"的干扰项缺陷。

### 4. AI 上下文不足识别是否成立？
**成立。** 2/2 都输出 `context_status=CONTEXT_INSUFFICIENT`、`confidence=LOW`、
`SUGGEST_REVIEW`，并说明缺什么；**没有**退化成 `SUGGEST_REJECT`。
这是 P1-09-C 新契约在真实调用中最直接的正面证据。

### 5. AI 学习价值判断是否成立？
**部分成立。** G 类（机械但合理）2/2 判 `learning_value=PASS` 且未误杀；
F 类 2/3 完全命中；FIX-F1 一条分歧，但离线核对显示 AI 的批评（`players of him` 不自然）
有实际依据，更可能是 fixture 的弱点而不是模型的误判。
因此"学习价值"这一维度**方向可用，但标准仍需在下一次用带明确标签的样本收窄**。

### 6. AI 是否会误杀合理机械题？
**不会。** FIX-G1 / FIX-G2 都被判 `mechanical_level=DIRECT_REPRODUCTION`，
但 `learning_value=PASS` + `SUGGEST_ACCEPT`。P1-09-C 的"机械形式 ≠ 自动 FAIL"被遵守。

### 7. AI 是否会把现实常识误判为教材答案冲突？
**不会。** FIX-D1 / FIX-D2 都判 `answer_unique=PASS`，没有被 `sugar`/`oxygen`/`soil` 这类
现实世界答案带偏。与第 2 问合起来看，模型的偏向恰好相反：
**它对现实常识有抵抗力，对教材原文没有抵抗力。**

### 8. 当前同一 DeepSeek 独立 session 是否足以继续做下一阶段？
**分维度回答：5 个维度足以，1 个维度不足。**

```text
可以继续用同一 DeepSeek 独立 session 的维度：
  english_correct（2/2）· distractor_quality（2/2）· context_status（2/2）
  learning_value / mechanical_level（G 类 2/2、F 类 2/3）· grade_fit（15/15 无异常）

不足以继续的维度：
  answer_unique —— 0/2，且失败方向是"高置信度地给出错误的放心结论"
```

### 9. 是否仍有必要引入第二模型？
**本次证据不支持"换模型能解决这个问题"。** 理由：

```text
1. 失败模式是"以教材原文为唯一权威"，这是任务设定的锚定效应，不是某个模型的随机错误；
   换一个同源模型很可能同样顺从教材（而换不同源模型则是引入未验证的新变量）。
2. 本次只测了 2 道 C 类 fixture，样本量不足以支撑"第二模型能修好"这种结论。
3. 更经济的修复方向是机制而不是模型：见第 11 问。
```

建议：**先做机制修复，而不是先换模型**；在机制修复后复测 C 类 fixture，若仍 0/2 再评估第二模型。

### 10. 正式 AI review 应该采用哪些硬边界？
本次实测支持的硬边界（都是"有证据"的，不是推测）：

```text
1. AI review 只能作为初筛建议，不得进入 PENDING_REVIEW → APPROVED → ACTIVE 任何一步
   （本次未产生任何 event / 状态变化，P1-08-C 的数据库硬门槛仍然在位）
2. answer_unique 结论在机制修复前**不得单独采信**；人工审核必须能看到"是否存在替代答案"的
   独立证据，而不是只看到 AI 的一句"无显著问题"
3. 上下文不足时只能输出 CONTEXT_INSUFFICIENT，不得等同于 REJECT（本次已验证可执行）
4. 程序结果（mechanical_rewrite / 教材结构 / 词汇边界 / 去重）是 hard fact，
   AI 的 mechanical_level 只是质量观察，两者不一致不自动覆盖
5. 机械形式不得作为 FAIL 的理由（本次 2/2 遵守）
6. 现实常识不得作为"答案不唯一"的理由（本次 2/2 遵守）
7. AI 输出里不得出现 APPROVED / ACTIVE / score / ranking / priority 等字段（本次 0 违规）
8. AI review 的输入必须与 gold 严格分离（本次以 SHA256 + 泄漏断言固定）
```

### 11. 下一阶段应该进入什么，而不是继续做什么？

**不应该**：继续调 Prompt、继续加规则、继续扩大样本规模去期待答案唯一性自己变好。

**应该进入（P1-09-E 候选）——答案唯一性机制修复设计，二选一或组合：**

```text
方案 1：程序侧确定性预筛 + 强制候选清单
  程序先对 fill / vocab_choice 生成"候选替代答案集合"（同词性 + 同 Unit 词汇 + 语法位置可填），
  AI 必须逐条回答"每个候选是否被教材语境排除"，而不是回答一个总的 PASS/FAIL。
  依据：本次证明"让模型自由判断唯一性"会退化为"课文里有就行"。

方案 2：把 answer_unique 从 AI 复核中移除，改由人工 + 程序候选清单决定
  依据：C 类 0/2 说明该维度目前不具备可采信度；而人工审核人即便不懂英语，
  也能在"这里还有一个词也能填"这种自然语言提示下做出判断。

同时建议在 P1-09-E 明确两件事：
  a) 选项自身语法错误计入哪个维度（english_correct 还是 distractor_quality）
  b) FIX-F1 暴露的 fixture 设计要求：干扰项必须在语法位置上真的能填进去，
     否则会把"干扰项缺陷"和"自然度"混在一起
```

---

## 10. 已证明 vs 未证明（任务书 §20）

**本次实验实际证明的事实**

```text
1. AI 能可靠发现真实英语错误（2/2，且指出具体位置）
2. AI 能发现干扰项缺陷（2/2），且不与答案唯一性混淆
3. AI 能正确输出 CONTEXT_INSUFFICIENT 且不升级为 REJECT（2/2）
4. AI 不会被现实常识带偏去制造第二答案（2/2）
5. AI 不会因为机械形式就误杀合理重点词填空（2/2）
6. AI 在"真正第二正确答案"上系统性失手（0/2），失败方向是顺从教材，且伴随 HIGH 置信度
7. P1-09-C 契约在"上下文不足"上可执行，但在"答案唯一性"上仅靠提示词不可执行
8. 整个过程中正式资产零变化（1164 文件 manifest 一致、三个关键 SHA 未变）
```

**尚未证明的事情**

```text
1. 真实生产漏检率：本次只有 2 道 C 类 fixture，量级不足以估计发生率
2. 同源盲点的大小：需要跨模型对照才知道"顺从教材"是模型特性还是任务特性
3. 机制修复是否真的能修好答案唯一性（本次只提出方向，未实现、未验证）
4. 学习价值维度的跨题型稳定性（F 类只测了 3 道，且 1 道 gold 本身有弱点）
5. distractor_quality 在"非 CONCERN 级缺陷"（真正荒谬选项）上的表现未被覆盖
6. 长期 reasoning 成本（本次 reasoning 占 completion 的 86.2%）
7. 大规模样本下的稳定性与人工审核负担
```

---

## 11. 结论

```text
P1-09-D_STOP_AND_FIX
```

```text
实验本身完整、干净、可复现（15/15、1 次调用、0 重试、gold 未泄漏、正式资产 0 变化）；
但实验结论是负面的：AI 英语质量复核在"真正第二正确答案"这一本次最重要的类别上 0/2，
并且是以高置信度、泛化理由的形式给出错误的放心结论。

因此：不得把这次实验写成"AI 复核可用"，也不得继续靠修改 Prompt 来弥补。
下一步应当先修机制（候选替代答案预筛 / 把 answer_unique 从 AI 单点判断中移出），
再考虑是否需要第二模型。
```

本阶段到此停止，不进入 P1-09-E。
