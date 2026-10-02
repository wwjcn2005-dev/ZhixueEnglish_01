# P1-05-D · AI 生成预算单次校准报告

最终状态：**CALIBRATION_PASS**

执行日期：2026-09-17
本轮真实 AI 调用：**1 次**（`api_calls = 1`，`retry_count = 0`）

---

## 0. 一句话结论

> `max_tokens` 由 8192 提高到 **16384** 后，同一 Section、同一 context、同一 prompt
> **正常收敛**：`finish_reason = stop`、`content` 6,817 字符、JSON 完整解析、`questions` 字段存在（10 道）。

`reasoning` 实际需要 **10,481 tokens** —— 超过 8192 上限约 **2,289**，但远低于 16384，
因此 16384 留下约 **5,903 tokens** 余量。

**本阶段只是预算校准，不是题目质量实验。** 未进入正式 validator、未做人工审核、
未写入题库、未计算任何质量指标、未宣布 P1-05 通过。

---

## 1. 单变量纪律（可机械复核）

| 项 | 值 |
| --- | --- |
| 测试对象 | P1-05-A #1 · **Unit 2 · UNDERSTANDING_IDEAS**（未换 Section） |
| context / prompt | **逐字节复用** P1-05-B #1 |
| `context_and_prompt_identical` | **true** |
| system prompt SHA256 | `193B43B80BBB564D…FC8E`（与 P1-05-B 记录一致） |
| user prompt SHA256 | `6846317BE314EF44…98F7`（与 P1-05-B 记录一致） |
| context_hash | `D00F004A341D0927…0F25` |
| model | `deepseek-v4-pro`（未变） |
| temperature | 0.2（未变） |
| thinking | `{"type":"enabled"}`（与 P1-05-C 一致） |
| reasoning_effort | `low`（与 P1-05-C 一致） |
| response_format | 未使用（与 P1-05-B/C 一致） |
| prompt_version | `P1-05-v1`（未修改） |
| **唯一变量** | **`max_tokens` 8192 → 16384** |

与 P1-05-C 的 payload **逐字段比对**：除 `max_tokens` 外**其它字段差异为 0**
（`other_field_diffs = []`，见 `calibration_request.json`）。

---

## 2. 校准结果

```text
HTTP               200（api_error = None）
finish_reason      stop
content            6,817 字符
JSON 解析           成功
questions 字段      存在（10 条）
truncated          false
guard 判定          PROCEED
api_calls          1        retry_count 0      第二次调用 无
latency            172.9 s
```

token 明细：

| 项 | 值 |
| --- | --- |
| prompt_tokens | 10,540（其中 cached 10,496 —— P1-05-C 的调用已预热缓存） |
| completion_tokens | **12,434** |
| reasoning_tokens | **10,481** |
| total_tokens | **22,974** |
| max_tokens（请求） | 16,384 |

---

## 3. 预算对照（与本轮之前的所有相关样本）

| 运行 | max_tokens | finish_reason | reasoning | completion | content 字符 | 延迟 |
| --- | --- | --- | --- | --- | --- | --- |
| P0 1630（有题量上限） | 8192 | stop | 5,648 | 6,123 | 1,685 | 113.3 s |
| P1-03（有题量上限） | 8192 | stop | 6,638 | 7,332 | 2,436 | 116.6 s |
| P1-05-B #1（无配额） | 8192 | **length** | **8,192（触顶）** | 8,192 | 0 | 123.4 s |
| P1-05-C（无配额 + low） | 8192 | **length** | **8,192（触顶）** | 8,192 | 0 | 190.7 s |
| **P1-05-D（无配额 + low）** | **16384** | **stop** | **10,481（未触顶）** | 12,434 | **6,817** | 172.9 s |

### 关键观察

```text
8192 上限  → reasoning 必然触顶 → 截断、content 为空（B/C 两次独立复现）
16384 上限 → reasoning 在 10,481 处自然收敛 → 剩余 5,903 tokens 用于输出 content
```

这同时**证实了 P1-05-C 的根因判定**（reasoning 抢占预算）：
把预算翻倍后，reasoning 并没有继续膨胀到新上限，而是停在 10,481，
说明它此前是被 8192 的硬上限掐断的，而不是"无限推理"。

---

## 4. 结构抽查（只读，不进入正式 validator）

```text
questions 数量   : 10
题型分布         : fill 4 / vocab_choice 3 / reading_choice 3
覆盖教材页        : 32, 33, 34
覆盖 Activity     : 1, 2, 3
必填字段缺失      : 无（options 仅在 4 道 fill 上为空，符合"纯填空不带选项"的定义）
```

> 以上**只是"JSON 是否完整、字段是否存在"的只读检查**。
> 本轮**未运行 validator_v3**、**未做人工审核**、**未评价题目质量**（P1-05-D §十一）。
> 10 道题这个数量本身也不构成任何质量结论。

---

## 5. §十三 报告必答

| # | 问题 | 回答 |
| --- | --- | --- |
| 1 | `max_tokens=16384` 是否成功避免截断？ | **是** |
| 2 | `finish_reason` 是什么？ | **`stop`** |
| 3 | 是否获得完整 content？ | **是**，6,817 字符 |
| 4 | 是否得到完整 JSON？ | **是**，解析成功且 `questions` 字段存在（10 条） |
| 5 | `reasoning_tokens` 是多少？ | **10,481**（未触顶，距 16384 还有 5,903） |
| 6 | `completion_tokens` 是多少？ | **12,434** |
| 7 | `total_tokens` 是多少？ | **22,974**（prompt 10,540 + completion 12,434） |
| 8 | 延迟是多少？ | **172.9 s** |
| 9 | 与 P1-05-C 对比，reasoning 是否仍触顶？ | **否**。P1-05-C 触顶（8,192/8,192）；本轮 10,481/16,384，**未触顶** |
| 10 | 是否发生第二次 API 调用？ | **否**（`api_calls=1`、`retry_count=0`） |
| 11 | `question_library.db` 是否完全未修改？ | **是**（哈希 `3970408E…`、mtime 19:16:03，均与本轮开始前一致） |
| 12 | 所有正式数据和项目文件是否保持不变？ | **是**（见 §6） |
| 13 | 最终状态 | **`CALIBRATION_PASS`** |

---

## 6. 保护项（调用前后哈希比对）

本轮在校准脚本内**自动比对**下列文件在调用前后的 SHA256，结果 `all_unchanged = true`、`changed = []`：

```text
question_library.db     3970408E...   （未新增 generation_run、未产生 AIQ:*）
learning.db             0C27267B...
contentpack v5          65829CA7...
validator_v2.py         7C61585A...
validator_v3.py          EDB1AA54...
P1-05-A 样本矩阵         1AAE8263...
P1-05-B 报告             33BDEB8D...
P1-05-C 报告             C2967116...
P1-05-C 请求/响应        9C731463... / 5B351E07...
P1-05-C generation_guard EBFE59E8...  （只读复用，未修改）
```

教材 PDF、54 个 MP3、Web、Android、V1.3、V2.0 均未被本轮的写入路径触碰。
**Codex 全局配置未修改。**

---

## 7. 本轮明确没有做的事

- 未重新运行 P1-05-B，未运行其它 Section，未运行原计划 #7
- 未修改 P1-05-A / P1-05-B / P1-05-v1 / validator v2 / validator v3
- 未写入 `question_library.db`（无 `generation_run`、无 `AIQ:*`）
- 未进入正式 validator 流程，未做人工审核
- 未计算 Natural Value Rate / APPROVE Rate，未宣布 P1-05 通过
- 未进行第二次 API 调用，未自动提高预算重试
- 未修改 prompt / context / temperature / thinking / reasoning_effort

---

## 8. 下一轮可用的事实（仅记录，不自行推进）

1. **预算结论**：`16384` 在 Unit 2 · UNDERSTANDING_IDEAS 上足以收敛（余量约 5,903 tokens）。
   其它 6 个样本 Section 的上下文规模相近（prompt 3.6k–10.6k），但**尚未逐一验证**。
2. **P1-05-B 需要新版本**（例如 `P1-05-v2`），显式写入 `max_tokens=16384`、
   `thinking` / `reasoning_effort` 与"截断即停"规则；**不得修改 P1-05-v1**。
3. **正式实验应重新开始**，不能把 P1-05-B 的失败结果与新预算混在一起统计。
4. 建议在正式重跑中**保留 `generation_guard` 的截断即停**：
   本轮已验证 budgets 不足时它会立即终止，避免再次出现"连续 6 次重复同一错误才停"。

> 以上仅作记录，本轮不执行。

---

## 9. 产物

| 文件 | 说明 |
| --- | --- |
| `README.md` | 索引 |
| `p1_05_budget_calibration_v2_report.md` | 本报告 |
| `p1_05_budget_calibration_v2_audit.json` | 审计结果（含跨运行对照与全部必答项） |
| `calibration_request.json` | 请求（含逐字节断言与单变量字段比对） |
| `calibration_response.json` | 原始响应（未修改） |
| `calibration_result.json` | 结果（含 guard 判定与保护项前后哈希） |
| `calibration_parsed.json` | 解析后的 JSON（预算校准产物，**未入库**） |
| `calibrate_budget_v2.py` / `build_v2_audit.py` | 校准与审计脚本 |

结果：**CALIBRATION_PASS**
