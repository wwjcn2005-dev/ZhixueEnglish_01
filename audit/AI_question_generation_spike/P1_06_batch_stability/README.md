# P1-06 · P1-05-v3 跨 Section 批量稳定性验证

```text
api_calls = 4        retry_count = 0        formal_assets_changed = false
```

用**冻结的 `P1-05-v3`** 在 4 个不同类型的 Section 上各调用 1 次，验证
「教材学习点优先 + 教材素材边界 + AI 重新组合」能否跨 Section 稳定工作。
**不修改任何提示词、validator 或正式数据；不写入 question_library.db。**

---

## 样本与结果

| Section | 性质 | 题数 | 题型 | BOLD 答案 | 真正教材外词汇 | 分层 A/B/C/D |
| --- | --- | --- | --- | --- | --- | --- |
| **S1** Unit 2 · UNDERSTANDING_IDEAS | 丰富阅读（基准） | 6 | fill2 / vocab2 / read2 | 5/6 | 0 | 3/3/0/0 |
| **S2** Unit 1 · UNDERSTANDING_IDEAS | 对话 / B | 5 | fill3 / vocab2 | 5/5 | 0 | 3/2/0/0 |
| **S3** Unit 5 · UNDERSTANDING_IDEAS | 词汇 / 语言运用 | 6 | vocab1 / fill2 / read1 / judge2 | 2/6 | 0 | 1/3/0/2 |
| **S4** Starter · GET_READY | 信息匹配 + 部分音频证据 | 5 | fill3 / vocab1 / read1 | 5/5 | 0 | 1/3/0/1 |
| **合计** | — | **22** | — | 17/22 | **0** | **8/11/0/3** |

```text
教材学习点命中 22/22 · evidence_quote 失效 0 · location 失效 0 · 教材原题复现 2 · 低价值题 3
总 token 82,641（prompt 41,575 / completion 41,066 / reasoning 37,524）· 总耗时 582.5 s
平均每 Section 20,660 tokens · 平均每题 3,756 tokens · 平均每次 145.6 s
```

---

## 批量稳定性观察

1. **没有固定模板**：S2 完全没有阅读题，S3 出现两道判断题，S4 以填空为主。
2. **没有“有词表就疯狂考词”**：BOLD 答案 17/22；词汇最密集的 S3 反而最低（2/6）。
3. **低证据行为未验证**：4 个样本证据体量都大（blocks 53–78、packages 19–21），
   未纳入 P1-05-A 里真正的低证据样本。
4. **真正教材外词汇 = 0**：被检查器标出的 token 全是词形变化
   （points←point、writes←write、student←students）。
5. **跨 Section 无重复，跨轮明显重复**：S1 与历史有 3 处同答案同 block
   （S1-Q1≡F-Q7≡G-Q2、S1-Q4≡G-Q3、S1-Q5≡D-Q8≡F-Q2）。

---

## 五个最终判断

| | 问题 | 结论 |
| --- | --- | --- |
| **A** | 是否仍保持教材学习点优先 | **是**（22/22；location/quote 0 失效） |
| **B** | 真正教材外词汇是否为 0 | **是**（0） |
| **C** | 题型是否随 Section 自然变化 | **是**（四种组合各不相同） |
| **D** | 低证据 Section 能否少出/不出 | **未验证**（本轮无低证据样本；S4 仍出 5 题，其中 1 题不可用） |
| **E** | 是否可进入小规模正式题库建设 | **已达到，但有 3 个阻塞项** |

### E 的阻塞项（都应在入库/校验层面解决，不要再改提示词）

| # | 阻塞项 | 证据 | 解决层面 |
| --- | --- | --- | --- |
| ① | 教材练习本身是填空时 AI 直接复现，且 `evidence_quote` 不含答案词 | S3-Q2/Q3（教材 a4 原空 + `answer_support=UNSUPPORTED`） | 校验/引用层 |
| ② | `content_block` 碎片化会产生残缺题干 | S4-Q4 `Oh, don't ___ your ...`（源 block 止于 `your`） | 证据抽取层 |
| ③ | 同一 Section 重跑收敛到相同题，措辞差异使 fingerprint 失效 | S1 与 F/G/D 有 3 处相同 | 题库去重层 |

---

## 保护检查

```text
formal_assets_changed = false        changed = []
```

85 个受保护文件在调用前后哈希完全一致：`question_library.db`（题目 2 / run 8 / ACTIVE 0 / 事件 3）、
`learning.db`、contentpack v5、`structured/textbook/*`、validator v2/v3、
**P1-05-A~G 全部既有产物**、教材 PDF、54 个 MP3；正式 Web / Android 未触碰。

---

## 产物

| 文件 | 说明 |
| --- | --- |
| `README.md` | 本索引 |
| `p1_06_report.md` | 完整总报告 |
| `p1_06_analysis.json` | 逐题判定 + 稳定性观察 + 历史对照表 + 成本 + 五个判断 |
| `p1_06_result.json` | 4 次调用执行结果与保护项 |
| `S1/S2/S3/S4_request.json` | 每个 Section 的请求（含 system/user SHA、pages、activity 范围） |
| `S1/S2/S3/S4_response.json` | 每个 Section 的原始响应 |
| `S1/S2/S3/S4_parsed.json` | 每个 Section 的解析结果（均未入库） |
| `run_p1_06.py` · `analyze_p1_06.py` | 执行与只读分析脚本 |
