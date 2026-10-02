# P1-06 实施报告 · P1-05-v3 跨 Section 批量稳定性验证

样本：4 个不同类型的 Section（S1 Unit 2 UI / S2 Unit 1 UI / S3 Unit 5 UI / S4 Starter GET_READY）
提示词：**`P1-05-v3`（冻结，未修改）** · 模型 `deepseek-v4-pro` · `max_tokens=16384` · `thinking{enabled}` · `reasoning_effort=low`

```text
api_calls = 4        retry_count = 0        formal_assets_changed = false
```

---

## 0. 结论速览

| 项 | 值 |
| --- | --- |
| AI 调用 | **4 次**（每 Section 1 次） |
| retry | **0** |
| finish_reason | 4 次全部 `stop`（无 TRUNCATED） |
| 生成题数 | **22**（S1 6 / S2 5 / S3 6 / S4 5） |
| 总 token | **82,641**（prompt 41,575 / completion 41,066 / reasoning 37,524） |
| 总耗时 | **582.5 s（9.7 分钟）**，平均每次 145.6 s |
| 质量分层 | **A 8 · B 11 · C 0 · D 3**（共 22） |
| 真正教材外词汇 | **0** |
| evidence_quote 失效 | **0**（22/22 均为对应 block 的逐字子串） |
| location 失效 | **0** |
| 正式资产 | **0 修改**（85 个受保护文件前后哈希一致） |

---

## 1. 四个 Section 的独立结果

### S1 · Unit 2 · UNDERSTANDING_IDEAS（丰富阅读 / 基准）

```text
题数 6   题型 fill2 / vocab_choice2 / reading_choice2
教材学习点命中 6/6   词汇表答案 5/6   BOLD 答案 5/6   教材素材合法 6/6
真正教材外词汇 0     真正重新组合 3   机械挖空 3       教材原题复现 0   低价值 0
block 复用: B12（Q4 different / Q5 in the park，考查点不同）
分层: A3 / B3
```

值得注意：Q4 把 P1-05-G 里那道**答案不唯一的填空**（different / traditional 都成立）
改成了**选择题**，并把 traditional 当作干扰项——歧义被自然消除。

### S2 · Unit 1 · UNDERSTANDING_IDEAS（对话 / B）

```text
题数 5   题型 fill3 / vocab_choice2（无阅读题）
教材学习点命中 5/5   词汇表答案 5/5   BOLD 答案 5/5   教材素材合法 5/5
真正教材外词汇 0     真正重新组合 3   机械挖空 2       教材原题复现 0   低价值 0
block 复用: 无
分层: A3 / B2
```

对话型内容同样适配：Q1 考语法聚焦句里的物主代词 `hers`，
Q4 考教材重点表达 `In fact`（两空填空），Q2/Q3/Q5 都是重组题干后的语境题。

### S3 · Unit 5 · UNDERSTANDING_IDEAS（词汇 / 语言运用）

```text
题数 6   题型 vocab_choice1 / fill2 / reading_choice1 / reading_judge2
教材学习点命中 6/6   词汇表答案 3/6   BOLD 答案 2/6   教材素材合法 6/6
真正教材外词汇 0     真正重新组合 3   机械挖空 3       教材原题复现 2   低价值 2
block 复用: B7 / B12（Q1 与 Q3 是同一句的两个空）
分层: A1 / B3 / D2
```

**本轮最值得注意的一节。** 该 Section 的教材练习 a4 本身就是
“Complete the texts with the words and expression from the passage”的填空，
AI 直接把它的两个空原样搬了过来（`Sunlight and CO2 come into the ___.` → leaf；
`Water from the root will ___ to the leaf through the stem.` → rise），
而且 `evidence_quote` 只截取了空位之前的片段，**不含答案词** →
按 P0 规则 `answer_support = UNSUPPORTED`。两题判 **D**。

另外两题（判断题）的布尔答案使 `answer_support` 无法判定，属**分析工具局限**，不是题目问题。

### S4 · Starter · GET_READY（信息匹配 + 部分音频证据）

```text
题数 5   题型 fill3 / vocab_choice1 / reading_choice1
教材学习点命中 5/5   词汇表答案 5/5   BOLD 答案 5/5   教材素材合法 5/5
真正教材外词汇 0     真正重新组合 1   机械挖空 4       教材原题复现 0   低价值 1
block 复用: 无
分层: A1 / B3 / D1
```

**该 Section 的听力练习在 content pack 里是碎片化 block**（P10:B5–B13 被切成带序号空位的碎片），
于是 AI 产出了残缺题干：`Oh, don't ___ your ...`（源 block 结束于 `your`，下一空位在 B13）。
判 **D**，根因是**证据抽取碎片化**，不是提示词规则问题。
其余 4 题（ready / eraser / grey / school uniform）全部正常。

---

## 2. 跨 Section 汇总

| 指标 | S1 Unit2 UI | S2 Unit1 UI | S3 Unit5 UI | S4 Starter | 合计 |
| --- | --- | --- | --- | --- | --- |
| 生成题数 | 6 | 5 | 6 | 5 | **22** |
| 0 题是否合理 | — | — | — | — | 无 0 题样本 |
| 教材学习点命中 | 6/6 | 5/5 | 6/6 | 5/5 | **22/22** |
| 词汇表答案 | 5/6 | 5/5 | 3/6 | 5/5 | 18/22 |
| BOLD 答案 | 5/6 | 5/5 | 2/6 | 5/5 | 17/22 |
| 教材素材合法率 | 6/6 | 5/5 | 6/6 | 5/5 | **22/22** |
| 真正教材外词汇 | 0 | 0 | 0 | 0 | **0** |
| 答案唯一率 | 6/6 | 5/5 | 6/6 | 5/5 | 22/22 |
| 真正重新组合 | 3 | 3 | 3 | 1 | 10 |
| 机械挖空 | 3 | 2 | 3 | 4 | 12 |
| 教材原题复现 | 0 | 0 | **2** | 0 | 2 |
| 明显低价值题 | 0 | 0 | 2 | 1 | 3 |
| 题型分布 | fill2/vocab2/read2 | fill3/vocab2 | vocab1/fill2/read1/judge2 | fill3/vocab1/read1 | — |
| 明显重复 | B12 复用（可接受） | 无 | B7/B12 复用（同句两空） | 无 | 见 §3.5 |
| 分层 A/B/C/D | 3/3/0/0 | 3/2/0/0 | 1/3/0/2 | 1/3/0/1 | **8/11/0/3** |

---

## 3. 批量稳定性观察（对应 §九）

### 3.1 是否出现固定模板化？——**没有**

```text
S1  fill2 / vocab2 / reading2
S2  fill3 / vocab2（完全没有阅读题）
S3  vocab1 / fill2 / reading1 / judge2
S4  fill3 / vocab1 / reading1
```

组合明显不同。fill 在 22 题中占 9 题（41%），是最常见题型，但没有形成固定套餐。

### 3.2 是否“有词表就疯狂考词”？——**没有**

BOLD 答案占比 17/22。值得注意的是**词汇最密集的 S3 反而最低（2/6）**：
该段两道 fill 来自教材 a4 填空原题，答案 root 还是 **PLAIN 词**。
说明模型确实在按证据形态选题型，而不是无脑套 BOLD 词。

### 3.3 是否“没有合适题就硬出”？——**本轮无法完整验证**

4 个 Section 都产出 5–6 题，没有 0 题样本。
更关键的是：**本轮 4 个样本的证据体量都很大**（blocks 53–78、packages 19–21），
P1-05-A 里真正的低证据样本（Unit 3 STARTING_OUT，仅 11 blocks）**未被纳入本轮**。
唯一证据不完整的 S4 仍然产出 5 题，其中 1 题因证据碎片不可用 —— 这是“硬出”的轻度迹象。

### 3.4 是否出现教材外素材？——**真正教材外词汇 = 0**

检查器标出的所有 token 逐条回查后都成立：

```text
points  ← point（Unit 1 词表 point out）
writes  ← write（Unit 1 正文 "Please write this down"）
student ← students（Unit 1 教材 a3 选项 "Students need to think for themselves."）
```

即全部是**词形变化/单复数**造成的假阳性，**真正教材外词汇为 0**，达到本轮要求。

### 3.5 是否出现重复？——**跨 Section 无；跨轮明显**

- **跨 Section**：无同答案 + 同 block 的重复。
- **Section 内**：S3 的 Q1/Q3 是同一句的两个空（`Water from the root will rise…`），
  属机械重复；S1 的 B12 被两道题使用，但考查点不同（形容词 vs 状语），可接受。
- **跨轮（与 P1-05-D/F/G）**：S1 与历史有 **3 处相同题**：

```text
S1-Q1 ≡ F-Q7 ≡ G-Q2   (sound, P37:B11)
S1-Q4 ≡ G-Q3           (different, P37:B12)
S1-Q5 ≡ D-Q8 ≡ F-Q2    (in the park, P37:B12)
```

S1 与 P1-05-G 是**同一 Section + 同一提示词的重跑**，模型收敛到相同题目
（题干措辞略有差异，因此 P1-02 的 `question_fingerprint` 未必能拦住）。

---

## 4. 与历史轮次对照（含 P1-06 四个 Section）

| 指标 | P1-05-D | P1-05-F | P1-05-G | **S1** | **S2** | **S3** | **S4** |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 题量 | 10 | 7 | 8 | 6 | 5 | 6 | 5 |
| fill 数量 | 4 | 0 | 4 | 2 | 3 | 2 | 3 |
| 词汇表答案 | 5/10 | 4/7 | 4/7 | 5/6 | 5/5 | 3/6 | 5/5 |
| BOLD 答案 | 4/10 | 4/7 | 4/7 | 5/6 | 5/5 | 2/6 | 5/5 |
| 真正教材外词汇 | 4 | 9 | 0 | **0** | **0** | **0** | **0** |
| 真正重新组合 | 5/10 | 6/7 | 3/8 | 3 | 3 | 3 | 1 |
| 机械挖空 | 7/10 | 3/7 | 4/8 | 3 | 2 | 3 | 4 |
| 教材原题复现 | 1 | 1 | 0 | 0 | 0 | **2** | 0 |
| 明显低价值题 | 4 | 1 | 1 | 0 | 0 | 2 | 1 |

**趋势**：题量从“10 题强出”回落到 5–6 题的自然水平；
真正教材外词汇从 D(4)/F(9) 一路降到 G 以后持续 **0**；
机械挖空比例稳定在 40–55%，且其中绝大多数答案是 BOLD 重点词（10/12）。

---

## 5. 成本与性能（§十三）

| Section | prompt | completion | reasoning | total | latency |
| --- | --- | --- | --- | --- | --- |
| S1 | 11,387 | 12,021 | 10,823 | 23,408 | 176.5 s |
| S2 | 9,448 | 7,852 | 7,111 | 17,300 | 111.3 s |
| S3 | 10,812 | 11,796 | 10,884 | 22,608 | 161.5 s |
| S4 | 9,928 | 9,397 | 8,706 | 19,325 | 133.2 s |
| **合计** | **41,575** | **41,066** | **37,524** | **82,641** | **582.5 s** |

```text
API calls 4 · retry 0 · 平均每 Section 20,660 tokens · 平均每题 3,756 tokens · 平均每次 145.6 s
```

按此推算，全册 40 个 Section 约需 40 次调用、约 83 万 tokens、约 97 分钟（**估算，非实测**）。

---

## 6. 五个最终判断（§十四）

### A · P1-05-v3 是否在不同类型 Section 上仍保持教材学习点优先？

**是。** 22/22 题都能对应到一个教材学习点（词汇表词 / 重点表达 / 语法聚焦句 / 课文重要事实）；
location 与 evidence_quote **0 处失效**。对话型（S2）、词汇型（S3）、
信息匹配型（S4）都遵循了同一优先级。

### B · 教材外英语素材是否保持在可接受范围，真正教材外词汇是否为 0？

**是，真正教材外词汇 = 0。** 检查器标出的 token 全部是词形变化或单复数
（points←point、writes←write、student←students），逐条回查教材 block 后均成立。

### C · 填空、词汇题、阅读题是否随 Section 类型自然变化，而不是固定模板？

**是。** 四种组合各不相同：S2 完全没有阅读题，S3 出现两道判断题，
S4 以填空为主。fill 占 41% 但未形成固定套餐。

### D · 低证据 Section 能否真正做到“少出/不出”，而不是硬凑？

**未验证。** 本轮 4 个样本的证据体量都较大（blocks 53–78、packages 19–21），
**没有纳入低证据样本**（P1-05-A 的 Unit 3 STARTING_OUT 只有 11 blocks）。
唯一证据不完整的 S4 仍产出 5 题，其中 1 题因证据碎片不可用——这是轻度“硬出”迹象，
但不足以证明低证据场景的行为。

### E · 当前方法是否已达到“可以进入小规模正式 AI 题库建设”的条件？

**已达到，但有 3 个阻塞项，且都应在入库/校验层面解决，而不是继续改提示词。**

**已验证部分**

- 学习点优先在 4 个不同类型的 Section 上稳定成立；
- 真正教材外词汇 0，每题的 evidence 均可追溯；
- 题型组合随 Section 变化，没有固定模板；
- 22 题中 **19 题（A8+B11）可直接或基本可用**；
- 成本可控：4 次调用 82,641 tokens / 9.7 分钟。

**未验证部分**

- 低证据 Section 是否会自然少出（本轮无此类样本）；
- 跨轮重复的自动拦截（见阻塞项 ③）；
- 人工审核成本（本轮未做人工审核）。

**阻塞项**

| # | 阻塞项 | 证据 | 应该在哪一层解决 |
| --- | --- | --- | --- |
| ① | 教材练习本身是填空时，AI 直接复现该题，且 `evidence_quote` 不含答案词 | S3-Q2 / S3-Q3（教材 a4 原空 + answer_support=UNSUPPORTED） | **校验/引用层面**：要求 fill 的 evidence_quote 必须包含答案词；并识别“与教材练习逐字重合”的题 |
| ② | content_block 碎片化会产生残缺题干 | S4-Q4（`Oh, don't ___ your ...`；源 block 止于 `your`） | **证据抽取层面**：把碎片化 block 合并成完整句，或在生成前排除这类 block |
| ③ | 同一 Section 重跑会收敛到相同题，且措辞差异使 fingerprint 失效 | S1-Q1/Q4/Q5 与 F/G/D 相同 | **题库去重层面**：需要比 question_fingerprint 更强的“同答案+同 block”去重键 |

---

## 7. 正式资产保护

脚本对 **85 个受保护文件**在调用前后做 SHA256 比对：

```text
formal_assets_changed = false
changed = []
```

覆盖 `question_library.db`（题目 2 / run 8 / ACTIVE 0 / 事件 3，未变）、`learning.db`、
contentpack v5、`structured/textbook/*`、validator v2/v3、
**P1-05-A~G 全部既有产物**、教材 PDF、54 个 MP3；正式 Web / Android 未触碰。

本轮唯一写入位置：`audit/AI_question_generation_spike/P1_06_batch_stability/`。

---

## 8. 产物

| 文件 | 说明 |
| --- | --- |
| `p1_06_report.md` | 本报告 |
| `S1_request.json` / `S1_response.json` / `S1_parsed.json` | S1 的请求 / 原始响应 / 解析结果 |
| `S2_*` / `S3_*` / `S4_*` | 同上（每个 Section 独立一套） |
| `p1_06_result.json` | 4 次调用的执行结果与保护项哈希 |
| `p1_06_analysis.json` | 逐题判定 + 稳定性观察 + 历史对照 + 成本 + 五个判断 |
| `run_p1_06.py` · `analyze_p1_06.py` | 执行与只读分析脚本 |
