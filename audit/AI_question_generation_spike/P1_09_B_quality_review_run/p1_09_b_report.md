# P1-09-B 实施报告 · AI 英语质量复核真实小样本验证

结论：**P1-09-B_PASS**

但必须同时明确：本次**只证明**"第二次独立 AI 调用能在真实题上发现一部分程序发现不了的问题，
且没有误伤已确认的正常题"；**尚未证明**它已经足够可靠到可以进入正式生产，
也**尚未证明**它在所有维度上都可信（学习价值与阅读题干扰项两项各有 1 例漏检）。

```text
AI 调用 = 1      retry_count = 0      finish_reason = stop
审核题数 = 10    （全部来自当前正式题库的真实题）
question_library.db 修改 = 0   learning.db 修改 = 0   contentpack 修改 = 0
Web / Android 修改 = 0         validator v2/v3 修改 = 0   P0～P1-09-A 冻结产物修改 = 0
自动 APPROVED = 0   自动 ACTIVE = 0   写入 question_event = 0
```

---

## 1. 调用账目（真实数据，无编造）

| 项 | 值 |
| --- | --- |
| api_calls | **1** |
| retry_count | **0** |
| model | `deepseek-v4-pro` |
| temperature | `0.2` |
| max_tokens | `16384` |
| reasoning_effort | `low` |
| prompt_version | `P1-09-B-v1` |
| prompt_tokens | 2,104 |
| completion_tokens | 7,042（其中 reasoning 5,523 = 78%） |
| total_tokens | 9,146 |
| latency | 51,050 ms（51.1 秒） |
| finish_reason | **stop** |
| content_chars | 4,584 |
| 结构状态 | PARSED（10/10 题，取值合法，无禁止字段） |

第一次调用即返回完整可解析结果，**因此没有发生第二次调用**。

---

## 2. 盲测输入（本次实验设计的核心）

发给复核模型的输入**只有**这几类信息（`input_snapshot.json`，3,173 字符）：

```text
1. question_id          5. answer
2. question_type        6. textbook_position（第 X 页 · Activity Y，自然语言）
3. question_text        7. textbook_evidence（教材原句）
4. options（如有）
   + grade_context（外研版七年级上册）
```

**没有**发给模型：

```text
生成阶段的 explanation        validator 的 PASS/FAIL 结论
生成时的 system prompt        生成模型的 reasoning
已知问题标签（P1-08-C / P1-09-A 的对照标签）
evidence_block_id / question_fingerprint / lifecycle_status 等内部字段
```

对照标签（`sample_selection.json` 中的 `ground_truth_label`）是实验人员依据 P1-08-C / P1-09-A
**既有证据**写下的，只在 AI 返回**之后**才用于对照（`blind_compare.py`），未进入 AI 输入。

---

## 3. 样本选择（10 题，覆盖要求全部满足）

| 覆盖要求 | 要求 | 实际 | 题目 |
| --- | --- | --- | --- |
| A 已知正常题 | ≥3 | **5** | `AIQ:BD59C5958D45`、`04CC9B1CF690`、`6ECD02B9D381`、`879007FA4FC7`、`7EAC0ED29A0A` |
| B 已知低学习价值 / 机械题 | ≥2 | **2** | `AIQ:1B3AF72923C4`、`1BA260727793` |
| C 已知答案唯一性风险 | ≥1 | **1** | `AIQ:120FFEECA78F` |
| D 已知干扰项风险 | ≥1 | **2** | `AIQ:75AAEBFE06DF`、`B6463523F9E5` |
| E 题型覆盖 | fill + vocab_choice + (reading_choice/judge 之一种) | **4 种** | fill 4、vocab_choice 2、reading_choice 3、reading_judge 1 |

对照标签分布：`KNOWN_NORMAL 5` / `RECORDED_RISK 4` / `CONFIRMED_PROBLEM 1`。

标签口径必须说清楚：**只有 `AIQ:1B3AF72923C4` 一条是"已被人工确认的问题题"**
（P1-08-C `REVIEW_REJECTED`，reason_code=`LOW_VALUE`，审核记录同时写下"题干单独看不唯一"）；
其余 4 条是 P1-09-A 记录下来的**风险特征**，不是已确认的缺陷。
这一区分直接影响下面的漏检统计口径。
本次没有出现需要伪造 fixture 的类别（未触发 `EXISTING_SAMPLE_INSUFFICIENT`）。

---

## 4. AI 复核原始结果（10/10 全部返回）

| question_id | 题型 | 英语 | 答案唯一 | 自然 | 学习价值 | 干扰项 | 年级 | 机械等级 | 建议 | 置信 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `AIQ:BD59C5958D45` | vocab_choice | PASS | PASS | PASS | PASS | PASS | PASS | DIRECT_REPRODUCTION | ACCEPT | HIGH |
| `AIQ:04CC9B1CF690` | fill | PASS | PASS | PASS | PASS | N/A | PASS | DIRECT_REPRODUCTION | ACCEPT | HIGH |
| `AIQ:6ECD02B9D381` | reading_choice | PASS | PASS | PASS | PASS | PASS | PASS | NOT_APPLICABLE | REVIEW | LOW |
| `AIQ:879007FA4FC7` | reading_choice | PASS | PASS | PASS | PASS | PASS | PASS | NOT_APPLICABLE | ACCEPT | HIGH |
| `AIQ:7EAC0ED29A0A` | reading_judge | PASS | PASS | PASS | PASS | N/A | PASS | NOT_APPLICABLE | ACCEPT | HIGH |
| `AIQ:1B3AF72923C4` | fill | PASS | **FAIL** | PASS | CONCERN | N/A | PASS | DIRECT_REPRODUCTION | **REJECT** | HIGH |
| `AIQ:1BA260727793` | fill | PASS | CONCERN | PASS | PASS | N/A | PASS | DIRECT_REPRODUCTION | REVIEW | MEDIUM |
| `AIQ:120FFEECA78F` | fill | PASS | **FAIL** | PASS | CONCERN | N/A | PASS | DIRECT_REPRODUCTION | **REJECT** | HIGH |
| `AIQ:75AAEBFE06DF` | vocab_choice | PASS | **FAIL** | PASS | CONCERN | **FAIL** | PASS | DIRECT_REPRODUCTION | **REJECT** | HIGH |
| `AIQ:B6463523F9E5` | reading_choice | PASS | PASS | PASS | PASS | PASS | PASS | NOT_APPLICABLE | ACCEPT | HIGH |

其中三条被驳回的中文理由（原文）：

```text
AIQ:1B3AF72923C4  该题无上下文，'ready' 并非唯一可填词，学生可填 happy 等。
AIQ:120FFEECA78F  该题无上下文，颜色词可随意填，答案不唯一。
AIQ:75AAEBFE06DF  无上下文，'traditional' 等选项也可填入，题目存在歧义。
```

输出结构完全符合约定：顶层只有 `review_version` 与 `reviews` 两个键；
未出现 `score / total_score / ranking / priority / automatic_status / approve / activate`；
没有对题干、选项、答案做任何改写（模型只输出判断）。

---

## 5. 盲对照矩阵

| question_id | known_issue（实验人员标签） | ai_finding | match | FP | FN |
| --- | --- | --- | --- | --- | --- |
| `AIQ:1B3AF72923C4` | CONFIRMED_PROBLEM：答案不唯一 + 低学习价值 | REJECT；uniq=FAIL；learn=CONCERN | **命中** | 否 | 否 |
| `AIQ:120FFEECA78F` | RECORDED_RISK：答案唯一性 | REJECT；uniq=FAIL | **命中** | 否 | 否 |
| `AIQ:75AAEBFE06DF` | RECORDED_RISK：干扰项 | REJECT；uniq=FAIL；distr=FAIL | **命中** | 否 | 否 |
| `AIQ:1BA260727793` | RECORDED_RISK：低学习价值 + 机械 | REVIEW；uniq=CONCERN；learn=**PASS** | **部分命中** | 否 | 否 |
| `AIQ:B6463523F9E5` | RECORDED_RISK：干扰项 | **ACCEPT**；distr=PASS | **未命中** | 否 | **是** |
| `AIQ:BD59C5958D45` | KNOWN_NORMAL（已人工审核并 ACTIVE） | ACCEPT（全 PASS） | 一致 | 否 | 否 |
| `AIQ:04CC9B1CF690` | KNOWN_NORMAL | ACCEPT | 一致 | 否 | 否 |
| `AIQ:879007FA4FC7` | KNOWN_NORMAL | ACCEPT | 一致 | 否 | 否 |
| `AIQ:7EAC0ED29A0A` | KNOWN_NORMAL | ACCEPT | 一致 | 否 | 否 |
| `AIQ:6ECD02B9D381` | KNOWN_NORMAL | **REVIEW**（evidence_concern=true） | 偏离 | 否 | 否 |

补充说明（逐条）：

- `AIQ:1B3AF72923C4`：AI 明确写出"可填 happy 等"，与 P1-08-C 人工审核记录一致。
- `AIQ:120FFEECA78F`：AI 理由"颜色词可随意填"。
- `AIQ:75AAEBFE06DF`：AI 直接点名 `traditional` 也可填。
- `AIQ:1BA260727793`：抓到了答案不唯一，但**没有**指出学习价值低。
- `AIQ:B6463523F9E5`：见 §6.4，属于判定口径差异。
- `AIQ:BD59C5958D45`：唯一一条 ACTIVE 题没有被误伤。
- `AIQ:6ECD02B9D381`：见 §6.3，不是误判为"题目有问题"，而是拒绝为不可验证的题干前提背书。

### 5.1 统计

```text
total_samples 10   known_normal 5   recorded_risk 4   confirmed_problem 1
FALSE_NEGATIVE 1  （B6463523F9E5，RECORDED_RISK 被判 ACCEPT）
FALSE_POSITIVE 0  （没有任何 KNOWN_NORMAL 题被判 SUGGEST_REJECT）
soft deviation 1  （6ECD02B9D381 被判 SUGGEST_REVIEW）

答案唯一性  期望 2 题 → 检出 2 题（100%）；另外 75AAEBFE06DF 判 FAIL，1BA260727793 判 CONCERN
学习价值    期望 2 题 → 检出 1 题（50%）
干扰项      期望 2 题 → 检出 1 题（50%）
机械等级    与程序 mechanical_rewrite 标志 9/10 一致

建议分布    ACCEPT 5 · REVIEW 2 · REJECT 3
```

---

## 6. 逐项事实与必须如实说明的细节

### 6.1 已确认问题题被真的抓到了

`AIQ:1B3AF72923C4`（P1-08-C 人工驳回的那道题）得到
`answer_unique=FAIL` + `learning_value=CONCERN` + `SUGGEST_REJECT`，理由"该题无上下文，'ready' 并非唯一可填词，学生可填 happy 等"。
这正是 P1-08-C 审核记录里人工写下的同一件事，而**程序 validator 对这道题的 8 项判定全部 PASS**。
这是本次实验最关键的一条证据：**AI 复核确实发现了程序无法发现的问题**。

### 6.2 答案唯一性：本次最可靠的维度

对 4 道"题干缺乏语境"的题（`1B3AF72923C4`、`120FFEECA78F`、`1BA260727793`、`75AAEBFE06DF`），
AI 分别给出 FAIL / FAIL / CONCERN / FAIL，**4/4 全部被标出**，且给出的替代答案具体可行
（happy、任意颜色词、`By the way`、`traditional`）。
说明提示词里"把原答案拿掉，主动去找其他同样自然的答案"这条反向策略确实生效——
模型没有因为"答案在教材里出现过"就判 PASS。

### 6.3 唯一一条"偏离"其实是一次正确的保守判断

`AIQ:6ECD02B9D381` 被判 `SUGGEST_REVIEW` + `evidence_concern=true`，理由是
"题干提到学校艺术节，但所给教材证据句子未提及"。
核对数据库：该题的 `question_evidence` **只有 1 条**（`P38:B3` "I nod to Grandpa and we fire up our instruments."），
而题干里的 "school art festival" 来自同一 Section 的**另一段**教材内容。
也就是说，AI 的判断在**它看到的输入范围内**是正确的：它拒绝为一条无法验证的题干前提背书，并给了 LOW 置信度。
这条不算误伤（不是 SUGGEST_REJECT），但它暴露了一个真实的机制问题：

> **只给单条 evidence_quote 的复核输入，会让复核者无法验证题干中来自其他教材块的语境。**

这是下一阶段必须先修的输入契约问题（属于证据组装层，不属于模型能力）。

### 6.4 唯一一次漏检，以及它为什么"看起来像"漏检

`AIQ:B6463523F9E5`（"In the Great Bear Rainforest, what can the trees make?" → "their own rain"）
在 P1-09-A 被记录为干扰项风险（`sugar` / `oxygen` / `food` 在现实世界里对树木同样成立），
但 AI 判 `SUGGEST_ACCEPT`，理由"阅读理解题，答案直接从教材中得出，无问题"。

如实说明：这道题是**阅读理解题**，任务本身是"从课文里找答案"，因此"答案由课文唯一确定"这一标准是成立的；
P1-09-A 记录的是"用现实常识衡量时干扰项不公平"这一**另一个标准**。两种口径都能自洽。
按本次实验的对照规则（RECORDED_RISK + SUGGEST_ACCEPT），它**必须记为 FALSE_NEGATIVE**，本文如实记录；
同时必须承认：**这条漏检有相当一部分来自标签口径不一致，而不是模型判断错误。
如果下一阶段要精确测量漏检率，必须先把"干扰项是否公平"的判定标准写清楚（阅读题只看课文，还是也看现实常识）。**

### 6.5 学习价值维度：本次最弱

期望命中 2 题，实际只命中 1 题（漏掉 `1BA260727793`，AI 给了 `learning_value=PASS`）。
AI 同时正确地把"机械挖空"与"不可接受"区分开了：它把 `BD59C5958D45`、`04CC9B1CF690`
都标成 `DIRECT_REPRODUCTION`，但 `learning_value=PASS` + `SUGGEST_ACCEPT`——
这与人工审核结论一致（机械挖空本身不等于不合格）。
问题在另一个方向：对 `1BA260727793`（双空挖空的 `In fact`）它没有指出"学习增量低"。
**结论：`learning_value` 是本轮可信度最低的维度，需要更明确的判定标准才能进入正式使用。**

### 6.6 机械等级与程序标志：9/10 一致，不一致的那 1 条说明两者不是同一件事

唯一不一致的是 `AIQ:120FFEECA78F`：程序 `mechanical_rewrite=False`，AI 判 `DIRECT_REPRODUCTION`。
原因是定义不同：程序看"题干是否为教材句的逐字片段再挖空"，
AI 看"这题本质上是不是把教材句挖了个空"（题干 "What colour is it? It's ___." 相对证据 "It's grey." 明显是原文挖空）。
这恰好验证了 P1-09-A 的设计决定是对的：**程序的 `mechanical_rewrite` 是事实标志，
AI 的 `mechanical_level` 是判断；两者不应当互相覆盖，也不应当强行对齐。**

---

## 7. "AI 没有修改题目"的验证（硬门槛）

```text
调用前 source_sha256 = 7AA12CA5EB24417BF0AE7E97A8161920B501825D030D69A8E0863272AC695DA7
调用后 db_sha256     = 7AA12CA5EB24417BF0AE7E97A8161920B501825D030D69A8E0863272AC695DA7
db_sha256_unchanged            = true
all_sample_questions_unchanged = true
  （10/10 题的 question_text / options_json / correct_answer / correct_option /
    lifecycle_status / active / question_event 数 全部一致）
row_counts 与预期一致 = true
  （generation_run 12 / ai_question 21 / evidence 22 / learning_object 37 /
    validation 21 / event 44）
lifecycle ACTIVE 1 · PENDING_REVIEW 19 · REJECTED 1 = 与 P1-08-C 收口完全相同
events 无新增（无新的 REVIEW_APPROVED / ACTIVATED）
integrity_check = ok        foreign_key_check = 空
```

另外做了一次**跨阶段锚定核对**（`cross_check_prior_manifests.py`）：
用 P1-09-A 在**本次 AI 调用之前**记录的 1,095 个文件哈希（以及 P1-08-C 记录的同一批哈希）
逐一重算比对：

```text
P1-09-A protect_after.json（调用前记录）  checked=1095  mismatched=0  missing=0  all_match=true
P1-08-C protect_after.json                checked=1095  mismatched=0  missing=0  all_match=true
```

```text
AI 复核结果只落在本审计目录；formal question_library.db 未写入任何 AI 审核结果
未产生 APPROVED / ACTIVE；未写入任何 question_event
```

---

## 8. 成本：实测，以及与 P1-09-A 估算的偏差（必须如实修正）

```text
本次真实调用（批量，10 题）：1 次调用 / 9,146 tokens / 51.1 秒
  输入 2,104 tokens   输出 7,042 tokens（其中 reasoning 5,523 = 78%）
  平均每题 914.6 tokens；本次调用延迟 51.1 秒
```

| 方案 | 调用次数 | 每题 tokens | 相对生成成本 |
| --- | --- | --- | --- |
| 批量复核（本次实测） | **1** | **914.6** | **24.3%** |
| 逐题复核（理论估算，未执行） | 10 | ~2,248 | ~59.9% |
| 只审核程序 PASS 的题 | 1 | 同批量 | 同批量（本批 22/22 全部 program PASS，过滤不出任何题） |

（生成基准 = P1-06 真实数据 82,641 tokens / 22 题 = 3,756.4 tokens/题。）

**必须修正 P1-09-A 的估算**：P1-09-A 估批量复核为 8.4%（约 314 tokens/题），
实测为 **24.3%（914.6 tokens/题）**，总量超出估算 1.32 倍。
原因很具体：P1-09-A 按"每题输出 220 tokens"估算，**没有给 reasoning 留预算**；
本次实测 reasoning 占 completion 的 78%，输出被低估约 3.2 倍。
结论：**批量复核不是"几乎免费"，而是大约占生成成本的四分之一**；逐题复核约六成，明显不划算。

---

## 9. 最终报告 12 问

1. **AI 是否发现已知答案不唯一？** **是。** 期望 2 题全部检出（100%）；另外 2 题被判 FAIL/CONCERN，共 4 题被标出。
2. **AI 是否发现低学习价值？** **部分。** 期望 2 题，检出 1 题（`1B3AF72923C4` 判 learn=CONCERN），漏掉 `1BA260727793`（判 PASS）。
3. **AI 是否发现机械挖空？** **是，但口径与程序不同。** 6 题被判 `DIRECT_REPRODUCTION`，与程序 `mechanical_rewrite=True` 的 5 题对比为 **9/10 一致**；差异 1 条是定义差异，不是错误。
4. **AI 是否发现干扰项风险？** **部分。** 2 题中检出 1 题（`75AAEBFE06DF` 判 distr=FAIL 并点名 `traditional`）；`B6463523F9E5` 漏检（口径差异，见 §6.4）。
5. **正常题误判多少？** 误判为"应驳回"= **0 条**（FALSE_POSITIVE = 0）；另有 1 条正常题被判"需人工复核"（`6ECD02B9D381`，原因是我方只提供了单条证据）。
6. **漏检多少？** **1 条**（`B6463523F9E5`，且属标签口径差异）；**已确认问题题的漏检 = 0 条**。
7. **哪些维度最可靠？** `answer_unique`（4/4 标出，替代答案具体可行）；`english_correct` / `naturalness` / `grade_fit` 无一条被误判；`mechanical_level` 与程序标志 9/10 一致。
8. **哪些维度不可靠？** `learning_value`（1/2）最弱；`distractor_quality` 在"阅读题标准 vs 现实常识标准"两种口径下不稳（1/2）。
9. **批量审核是否可行？** **可行。** 一次调用完成 10 题，`finish_reason=stop`，输出结构合法，51 秒返回，成本为生成的 24.3%。
10. **是否值得进入 P1-09-C 正式设计？** **值得，但带前置修正。** 必须先修复核输入契约（§6.3：把该题所属 Section 的完整证据一起给复核者），并把 `learning_value` 与"干扰项公平性"的判定标准写成可对照口径，否则漏检率无法被准确测量。
11. **是否还需要第二个模型？** **本阶段证据不支持"必须换模型"。** 同一 `deepseek-v4-pro` 独立 session 已做到：已确认问题 1/1 命中、0 误伤正常题。当前漏检都能被"标签口径不一致"或"输入信息不足"解释，而不是同源盲点。建议**下一步仍用同一 DeepSeek 独立 session 作基线，先修口径与输入，再决定是否需要第二模型**；10 题样本量不足以支撑"同源盲点不存在"的结论。
12. **当前阶段应继续还是停止？** **本阶段到此停止**（不自行进入 P1-09-C）。是否继续做多 Section 的正式设计，由项目方基于这份证据决定。

---

## 10. 本次实验实际证明的事实 vs 尚未证明的事情

**已经证明（有真实数据支撑）**

```text
1. 第二次独立 AI 调用可以在真实题上发现程序 validator 发现不了的问题：
   AIQ:1B3AF72923C4 程序 8 项全 PASS，AI 判 answer_unique=FAIL + SUGGEST_REJECT，
   理由与 P1-08-C 人工审核记录一致。
2. 反向搜索策略有效：4 道缺语境题全部被标出，替代答案具体
   （happy / 颜色词 / By the way / traditional）。
3. 没有误伤已确认的正常题：FALSE_POSITIVE = 0，包括唯一一条已人工审核通过的 ACTIVE 题。
4. AI 没有修改任何题目：数据库 SHA 未变，10/10 题逐字段未变，未产生事件或状态变化。
5. 批量审核可行：1 次调用完成 10 题，finish_reason=stop，结构合法，51 秒，24.3% 生成成本。
6. 输出克制：没有 100 分制/总分/星级/排名/优先级，没有 APPROVED/ACTIVE 字段，中文理由可读。
```

**尚未证明（不得写成已解决）**

```text
1. 漏检率的真实水平：只有 1 条 CONFIRMED_PROBLEM 样本，样本量太小；
   RECORDED_RISK 4 条中 1 条漏检，但属判定口径差异，不能直接当作模型能力下限。
2. learning_value 维度是否可用：1/2 命中、标准不清，必须重新定义后再测。
3. 干扰项公平性在"阅读题"与"现实常识"两种口径下如何统一，未解决。
4. 同一模型自我复核的同源盲点是否存在、有多大：需要更多样本 + 跨题型对照。
5. 单条证据输入导致的 evidence_concern 是否会在大批量中变成系统性噪声，未验证。
6. reasoning 成本的真实规模：本次 78% 的输出 token 是 reasoning，比 P1-09-A 估算高 3.2 倍，
   长期成本必须按真实数据重算。
7. AI 复核结论与人类最终审核结论的一致率：本次只有 1 条人工结论可对照。
```

---

## 11. 结论

```text
P1-09-B_PASS
```

依据任务书 §20 的 13 条 PASS 条件逐条满足：10 题完成审核、AI 调用 1 次、无因不满意的重试、
输出完整且结构合法、已知问题有可分析结果、FP/FN 对照已完成、原题未改、
`question_library.db` / `learning.db` / contentpack / Web / Android 均 0 修改、
无自动 APPROVED/ACTIVE、无伪造样本或结果。

本阶段的正确读法：

> **AI 英语质量复核作为"初筛助手"是有价值的，且能发现程序发现不了的问题；
> 它的答案唯一性判断在本轮表现最好，学习价值与干扰项判断还需要明确口径才能进入正式使用。**

不进入 P1-09-C，等待下一步指令。
