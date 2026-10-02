# P1-05-C · AI 题目生成预算与截断机制修正

## 最终状态

### **CALIBRATION_BLOCKED**

校准结果：**`BUDGET_STILL_INSUFFICIENT`**

本轮真实 AI 调用：**1 次**（无重试、无第二次）

---

## 一句话结论

> `reasoning_effort="low"` + `max_tokens=8192`（其余参数与 P1-05-B 完全一致）
> **仍然截断**：`finish_reason=length`、`content` 为空、`reasoning_tokens=8192`。

按 §九结论：**下一轮需要提高 `max_tokens`**；本轮**不做第二次调用**。

**不是** `P1-05_PASS`，**不是** `PRODUCTION_READY`，也不是题目质量结论。

---

## 本轮做了什么

| 步骤 | 结果 |
| --- | --- |
| 只读审计（6 次失败 + 4 次历史成功样本） | 完成 |
| 官方能力核查（非 AI 调用） | 确认 `thinking` / `reasoning_effort` 为**顶层参数** |
| 实现"截断即停"保护 | `generation_guard.py`，含合成用例验证 |
| 单次隔离校准（CALIBRATION_ONLY） | 1 次调用，仍截断 |
| 是否写正式题库 | **否**（没有 generation_run、没有 AIQ:*） |

---

## 根因判定：`ROOT_CAUSE_SUPPORTED`

```text
成功样本 reasoning ： 179 – 6,638   （全部低于 8,192，留有预算给 content）
失败样本 reasoning ：7,538 – 8,192  （全部触顶，content 无预算）
```

比值（reasoning/completion）**不是**区分器（成功 0.74–0.92，失败 0.92–1.00，区间重叠）；
真正区分的是 reasoning 的**绝对消耗**。

同 Section 对照（Unit 1 UI）：

| 版本 | prompt tokens | reasoning | content | finish |
| --- | --- | --- | --- | --- |
| P0-v1（有 3 题上限） | 9,451 | 5,648 | 1,685 字符 | **stop** |
| P1-05-v1（无题量上限） | **8,680（更小）** | **8,192** | 0 | **length** |

去配额后 prompt 更小、reasoning 反而更大并触顶 -> 支持"去配额导致 reasoning 不收敛"。

---

## 校准调用数据

```text
api_calls        1        retry_count 0        api_error None
finish_reason    length
content          0 字符
reasoning_tokens 8,192（与未传 reasoning_effort 的 P1-05-B #1 完全相同）
prompt_tokens    10,540
total_tokens     18,732
latency          190.7 s
```

`reasoning_effort="low"` **可传递、被服务端接受**（HTTP 200，无 400/422），
但**没有可观测的降推理效果**。

---

## "截断即停"保护规则

```text
finish_reason == "length"
  -> TRUNCATED
  -> 不进入 validator
  -> 不写 question_library
  -> 不 retry
  -> 不执行下一个 Section
  -> 立即返回明确状态

（"截断但 content 非空"同样停止 —— 防止半截 JSON 被当成题目）
```

---

## 保护项（全部未被修改）

```text
learning.db            0C27267B...CF91
contentpack v5         65829CA7...0C39
validator v2 / v3      7C61585A...A683 / EDB1AA54...900C
question_library.db    3970408E...（题目 2、run 8、ACTIVE 0、事件 3，均未变）
P1-05-A / P1-05-B 产物  未修改（mtime 保持 P1-05-B 结束时的状态）
Codex 全局配置          未修改
教材 PDF / 54 MP3 / Web / Android / V1.3 / V2.0  未修改
```

---

## 下一轮方向（只记录，不实施）

1. **提高 `max_tokens`**（`reasoning_effort=low` 未解决问题），建议先单次校准确认 `stop`。
2. **P1-05-B 需要新版本 `P1-05-v2`**，显式写入 reasoning 参数与"截断即停"规则；
   不得修改 `P1-05-v1`，不得修改历史实验。
3. **正式实验应重新开始**，不能把失败结果与新参数混在一起统计。

---

## 产物

| 文件 | 说明 |
| --- | --- |
| `README.md` | 本索引 |
| `p1_05_budget_calibration_report.md` | 完整报告（含 §十四 全部必答项） |
| `p1_05_budget_calibration_audit.json` | 审计结果 |
| `budget_comparison.json` | 失败 vs 成功样本预算对照与根因判定 |
| `calibration_request.json` | 校准请求（含逐字节一致性断言） |
| `calibration_response.json` | 校准原始响应（未修改） |
| `calibration_result.json` | 校准结果 + guard 判定 + 结果标签 |
| `generation_guard.py` | "截断即停"保护模块 |
| `calibrate_budget.py` | 校准脚本 |
| `build_calibration_audit.py` | 审计与对照脚本 |
