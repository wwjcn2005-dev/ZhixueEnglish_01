# P1-05-C · AI 题目生成预算与截断机制修正报告

最终状态：**CALIBRATION_BLOCKED**

校准结果：**`BUDGET_STILL_INSUFFICIENT`**

执行日期：2026-09-17
本轮真实 AI 调用：**1 次**（无重试、无第二次）

---

## 0. 一句话结论

> 把 `reasoning_effort` 设为 `low`、其余参数与 P1-05-B 完全一致后，
> **输出预算仍然被 reasoning 吃光**：`finish_reason=length`、`content` 为空、`reasoning_tokens = 8192`。

因此按 P1-05-C §九：**校准结果为 `BUDGET_STILL_INSUFFICIENT`，本轮不进行第二次调用**，
下一轮需要提高 `max_tokens`。

本状态**不是** `P1-05_PASS`，**不是** `PRODUCTION_READY`，也不是题目质量结论。

---

## 1. 只读审计（未修改任何配置）

### 1.1 6 次失败调用与历史成功调用的请求参数对照

| 项 | P1-05-B（6 次） | P0 / P1-03 成功样本 |
| --- | --- | --- |
| model | `deepseek-v4-pro` | `deepseek-v4-pro` |
| endpoint | `https://api.deepseek.com/chat/completions` | 同 |
| `max_tokens` | 8192 | 4096（P0 1610 失败） / **8192**（1630、1650、P1-03 成功） |
| temperature | 0.2 | 0.2 |
| top_p | 未设置 | 未设置 |
| `response_format` | 未使用（要求纯 JSON 文本） | 同 |
| `thinking` / `reasoning_effort` | **均未传** | **均未传** |
| prompt_version | `P1-05-v1` | `P0-v1` |
| context_hash | 每 Section 各自记录 | 各自记录 |
| 客户端额外 token 限制 | **无**（脚本只设 `max_tokens`） | 无 |

**结论：P1-05-B 与成功样本在传输参数上唯一实质差异是 prompt 版本**（`P1-05-v1` 去掉了题量配额），
`thinking` / `reasoning_effort` 过去从未使用过。

### 1.2 官方能力核查（非 AI 调用）

抓取 `api-docs.deepseek.com/guides/reasoning_model`（HTTP 200）确认，官方给出的请求形态是**顶层参数**：

```json
{
  "model": "deepseek-flash",
  "messages": [ "..." ],
  "thinking": { "type": "enabled" },
  "reasoning_effort": "high",
  "stream": false
}
```

即 `thinking` 与 `reasoning_effort` 都是顶层字段。

### 1.3 当前请求路径能否传递这两个参数

本项目的调用是**直连 HTTPS JSON**（`urllib.request` + 自建 payload），
**不经过 Codex provider 层**，因此 payload 可以自由携带任意字段。

校准请求因此携带：

```json
"thinking": { "type": "enabled" },
"reasoning_effort": "low"
```

服务端返回 **HTTP 200，无 400/422** -> **参数可传递且未被拒绝**。
**Codex 全局配置未被修改。**

---

## 2. 截断根因：数据是否支持"reasoning 抢占预算"

### 2.1 比值对照

| 样本 | prompt tokens | completion tokens | reasoning tokens | content 字符 | reasoning/completion | finish |
| --- | --- | --- | --- | --- | --- | --- |
| P1-05-B #1 U2 UI | 10,619 | 8,192 | **8,192** | 0 | **1.00** | length |
| P1-05-B #2 U6 RfW | 7,732 | 8,192 | **8,192** | 0 | **1.00** | length |
| P1-05-B #3 U1 UI | 8,680 | 8,192 | **8,192** | 0 | **1.00** | length |
| P1-05-B #4 U5 UI | 10,044 | 8,192 | **8,192** | 0 | **1.00** | length |
| P1-05-B #5 Starter | 9,160 | 8,192 | **8,192** | 0 | **1.00** | length |
| P1-05-B #6 U3 SO | 3,663 | 8,192 | **7,538** | 0 | 0.92 | length |
| P0 1450（成功） | 6,837 | 3,904 | 3,296 | >0 | 0.84 | stop |
| P0 1630（成功） | 9,451 | 6,123 | 5,648 | 1,685 | 0.92 | stop |
| P0 1650（成功拒答） | 4,154 | 243 | 179 | >0 | 0.74 | stop |
| P1-03（成功） | 9,451 | 7,332 | 6,638 | 2,436 | 0.91 | stop |

### 2.2 判据

**比值本身不是区分器**：成功样本 0.74–0.92，失败样本 0.92–1.00，区间重叠。

**真正的区分器是 reasoning 的绝对消耗**：

```text
成功样本 reasoning  ： 179 – 6,638   （全部低于 8,192 上限，留有预算给 content）
失败样本 reasoning  ：7,538 – 8,192  （全部触顶，content 无预算可用）
```

### 2.3 同 Section 对照（最强证据）

| 版本 | Section | prompt tokens | reasoning | content | finish |
| --- | --- | --- | --- | --- | --- |
| P0-v1（**有** 3 题上限） | Unit 1 UI | 9,451 | 5,648 | 1,685 字符 | **stop** |
| P1-05-v1（**无**题量上限） | Unit 1 UI | **8,680（更小）** | **8,192** | 0 | **length** |

同一个 Section、同一份教材证据；**去配额版本的提示词更小，reasoning 反而更大并触顶**。

### 2.4 结论

```text
ROOT_CAUSE_SUPPORTED
```

> P1-05-B 的 6 次截断确实由 reasoning 抢占输出预算导致。
>
> 精确表述：P1-05-v1 相对 P0-v1 共改了 4 处（去配额 / 阅读示例去 Unit 1 硬编码 / 页面活动参数化 /
> USER 结尾），其中**只有"去掉题量上限"在机制上合理地影响推理长度**；
> 因此根因判定为"去配额导致 reasoning 不再收敛"，其余 3 处属于必要的参数化，不改语义。

---

## 3. "截断即停"机制（本轮必须实现的工程保护）

实现于 `generation_guard.py`，规则：

```text
finish_reason == "length"            -> 状态 TRUNCATED
  且 content == ""                    -> 硬停止
  -> 不进入 validator
  -> 不进入 question_library
  -> 不 retry
  -> 不执行下一个 Section
  -> 立即返回明确状态（抛 TruncationStop）
```

设计要点：**"截断但 content 非空"同样停止**——那是最危险的情形（半截 JSON 可能被解析成残缺题目）。

### 合成用例验证（零成本，未消耗 AI 调用）

| 用例 | 判定 | 动作 |
| --- | --- | --- |
| `length` + content 空 | `TRUNCATED` | STOP |
| `length` + content 为半截 JSON | `TRUNCATED` | STOP（不进解析） |
| `stop` + content 非空 | `OK` | PROCEED |
| HTTP 错误 | `API_ERROR` | STOP |

本轮校准调用已实际套用该保护：guard 在解析之前就把这次调用判为 `TRUNCATED` 并终止，
**没有进入 validator 流程、没有写题库、没有重试**。

---

## 4. 单次隔离校准调用（CALIBRATION_ONLY）

### 4.1 变量纪律

| 项 | 处理 |
| --- | --- |
| 样本 | P1-05-B #1 · Unit 2 · UNDERSTANDING_IDEAS |
| context / prompt | **逐字节复用**，调用前用记录的 SHA256 断言验证通过 |
| model / temperature / max_tokens | **完全未变**（8192 未放大） |
| `response_format` | 未变（仍为纯 JSON 文本） |
| **唯一新增** | `thinking={"type":"enabled"}` + `reasoning_effort="low"` |

断言结果（`calibration_request.json`）：

```text
system_prompt_sha256_rebuilt = 193B43B8...  （与 P1-05-B 记录一致）
user_prompt_sha256_rebuilt   = 6846317B...  （与 P1-05-B 记录一致）
context_and_prompt_identical = true
```

### 4.2 调用结果

```text
api_calls        1        retry_count 0        api_error None
finish_reason    length
content          0 字符
reasoning        33,769 字符
prompt_tokens    10,540
completion       8,192
reasoning_tokens 8,192   <- 仍然占满
total_tokens     18,732
latency          190.7 s
```

**`reasoning_effort="low"` 没有产生任何可观测的降推理效果**：reasoning_tokens 与未传该参数的
P1-05-B #1 完全相同（都是 8,192）。

### 4.3 校准结果判定

```text
BUDGET_STILL_INSUFFICIENT
```

按 §九：**不进行第二次调用**，只报告"下一轮需要增加 max_tokens"。

---

## 5. 校准成功标准核对（§十）

| # | 标准 | 结果 |
| --- | --- | --- |
| 1 | `finish_reason == "stop"` | 未达成（`length`） |
| 2 | `content != ""` | 未达成（0 字符） |
| 3 | JSON 可解析 | 未达成（无 content 可解析） |
| 4 | `questions` 字段存在 | 未达成 |
| 5 | 每题符合 P1-05-v1 结构要求 | 未达成（无题目） |
| 6 | 无 token 截断导致的 JSON 不完整 | 未达成（直接截断） |

**本轮未进入正式 validator 流程**（§十），也未把任何结果当成质量结论。

---

## 6. §十四 报告必答

| # | 问题 | 回答 |
| --- | --- | --- |
| 1 | 6 次截断是否确实由 reasoning budget exhaustion 导致？ | **是** — `ROOT_CAUSE_SUPPORTED`。6/6 的 completion 恰为 8,192、reasoning 7,538–8,192、content 为 0；同 Section 对照证明去配额后 reasoning 触顶 |
| 2 | 当前 Codex/DeepSeek 路径是否支持 `reasoning_effort`？ | **可传递且被服务端接受**（HTTP 200，无 400/422）；但**未观察到生效**（reasoning 仍占满 8,192）。参数按官方文档以顶层字段发送，Codex 全局配置未改动 |
| 3 | `reasoning_effort=low + max_tokens=8192` 是否得到完整 content？ | **否**（content 0 字符） |
| 4 | 是否成功产生完整 JSON？ | **否**（无 content 可解析） |
| 5 | 本次实际消耗多少 tokens？ | prompt **10,540** / completion **8,192** / reasoning **8,192** / total **18,732**；延迟 190.7 s |
| 6 | 是否发生截断？ | **是**（`finish_reason=length`） |
| 7 | 是否调用了第 2 次 API？ | **否** — `api_calls=1`、`retry_count=0` |
| 8 | `question_library.db` 是否完全未修改？ | **是** — 哈希 `3970408E...`、mtime 19:16:03（P1-05-B 结束时的状态），题目 2 条、run 8 条、ACTIVE 0、事件 3 条，均未变。本轮脚本从未打开题库写入 |
| 9 | P1-05-A / P1-05-B 是否完全未修改？ | **是** — 本轮所有脚本只读这些文件；mtime 仍为 P1-05-B 结束时的时间（矩阵 18:54:05 / 运行脚本 19:03:31 / 报告 19:17:57 / 审计 19:17:28） |

---

## 7. 保护项

| 资产 | 结果 |
| --- | --- |
| `learning.db` | 未修改（`0C27267B...CF91`） |
| contentpack v5 | 未修改（`65829CA7...0C39`） |
| `validator_v2.py` / `validator_v3.py` | 未修改（`7C61585A...A683` / `EDB1AA54...900C`） |
| `question_library.db` | **未修改**（`3970408E...`，无新题、无新 run） |
| 教材 PDF / 54 个 MP3 / Web / Android / V1.3 / V2.0 | 未修改 |
| P1-05-A / P1-05-B 产物 | 未修改 |
| Codex 全局配置 | 未修改 |

---

## 8. 两处如实记录的观察

1. **`prompt_tokens` 与 messages 不完全一一对应**：校准调用为 10,540，而 P1-05-B #1 为 10,619，
   但两次的 messages 经 SHA256 断言**逐字节一致**。
   一个**未经验证**的假设是：显式传入 `thinking` 改变了服务端的提示模板。
   本轮不做进一步验证（受 1 次调用上限约束）。
2. **校准调用延迟 190.7 s**，超过 P1-05-A 的 180 s 正常目标，但未触及 300 s 硬停止线。

---

## 9. 下一轮方向（只记录，不在本轮实施）

1. **提高 `max_tokens`**：`reasoning_effort=low` 未能解决问题，预算必须上调；
   建议下一轮先用**单次**校准确认 `finish_reason=stop`。
2. **P1-05-B 需要新版本（例如 `P1-05-v2`）**，显式写入 reasoning 参数与"截断即停"规则。
   **不得修改 `P1-05-v1`**，不得修改历史实验报告。
3. **正式实验应当重新开始**，不能把 P1-05-B 的失败结果与新参数混在一起统计。

> 上述内容本轮**不实施**。

---

## 10. 产物

| 文件 | 说明 |
| --- | --- |
| `README.md` | 索引 |
| `p1_05_budget_calibration_report.md` | 本报告 |
| `p1_05_budget_calibration_audit.json` | 审计结果（含全部必答项与保护项） |
| `budget_comparison.json` | 6 次失败 vs 4 次成功样本的预算对照与根因判定 |
| `calibration_request.json` | 校准请求（含 SHA256 断言与唯一的参数增量） |
| `calibration_response.json` | 校准原始响应（未修改） |
| `calibration_result.json` | 校准结果（含 guard 判定与 `BUDGET_STILL_INSUFFICIENT` 标签） |
| `generation_guard.py` | "截断即停"保护模块 |
| `calibrate_budget.py` / `build_calibration_audit.py` | 校准与审计脚本 |

结果：**CALIBRATION_BLOCKED**（`BUDGET_STILL_INSUFFICIENT`）
