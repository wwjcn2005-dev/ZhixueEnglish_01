# P1-05-D · AI 生成预算单次校准（max_tokens 8192 → 16384）

## 最终状态

### **CALIBRATION_PASS**

真实 AI 调用：**1 次**（`api_calls = 1`，`retry_count = 0`，无第二次）

---

## 一句话结论

> `max_tokens=16384` **成功避免截断**：`finish_reason = stop`、`content` 6,817 字符、
> JSON 完整解析、`questions` 字段存在（10 条）。
>
> `reasoning` 实际需要 **10,481 tokens**（超过 8192 约 2,289，远低于 16384），
> 因此 16384 留下约 **5,903 tokens** 余量。

**这是预算校准，不是题目质量实验。** 未进 validator、未人工审核、未入库、未计算质量指标。

---

## 单变量纪律

```text
测试对象      P1-05-A #1 · Unit 2 · UNDERSTANDING_IDEAS（未换 Section）
context/prompt 逐字节复用 P1-05-B #1（SHA256 断言通过：context_and_prompt_identical = true）
system SHA    193B43B8...FC8E      user SHA  6846317B...98F7
context_hash  D00F004A341D0927...0F25
model         deepseek-v4-pro      temperature 0.2
thinking      {"type":"enabled"}   reasoning_effort low   （与 P1-05-C 一致）
唯一变量      max_tokens 8192 -> 16384
              （与 P1-05-C payload 逐字段比对：other_field_diffs = []）
```

---

## 预算对照

| 运行 | max_tokens | finish_reason | reasoning | content | 延迟 |
| --- | --- | --- | --- | --- | --- |
| P0 1630（有题量上限） | 8192 | stop | 5,648 | 1,685 字符 | 113.3 s |
| P1-03（有题量上限） | 8192 | stop | 6,638 | 2,436 字符 | 116.6 s |
| P1-05-B #1（无配额） | 8192 | **length** | **8,192 触顶** | 0 | 123.4 s |
| P1-05-C（无配额 + low） | 8192 | **length** | **8,192 触顶** | 0 | 190.7 s |
| **P1-05-D（无配额 + low）** | **16384** | **stop** | **10,481 未触顶** | **6,817 字符** | 172.9 s |

把预算翻倍后 reasoning **没有继续膨胀到新上限**，而是停在 10,481 ——
这同时证实了 P1-05-C 的根因判定：此前是被 8192 的硬上限掐断，而非"无限推理"。

---

## 本次调用数据

```text
HTTP                200（api_error = None）
finish_reason       stop
content             6,817 字符
JSON               解析成功；questions 字段存在；10 条
truncated           false        guard 判定 PROCEED
prompt_tokens       10,540（cached 10,496）
completion_tokens   12,434
reasoning_tokens    10,481
total_tokens        22,974
latency             172.9 s
max_tokens(请求)     16,384
api_calls 1 · retry_count 0 · 第二次调用 无
```

结构抽查（**只读**，不进入正式 validator）：`fill 4 / vocab_choice 3 / reading_choice 3`，
覆盖教材第 32–34 页、Activity 1–3，必填字段无缺失（options 仅在 4 道 fill 上为空，符合定义）。

---

## 保护项（调用前后自动哈希比对，`all_unchanged = true`）

```text
question_library.db      3970408E...   （无新 generation_run、无 AIQ:*）
learning.db              0C27267B...
contentpack v5           65829CA7...
validator_v2 / v3        7C61585A... / EDB1AA54...
P1-05-A / B / C 产物      未修改
P1-05-C generation_guard  EBFE59E8...   （只读复用）
Codex 全局配置            未修改
教材 PDF / 54 MP3 / Web / Android / V1.3 / V2.0  未修改
```

---

## 本轮明确没有做

未重跑 P1-05-B；未跑其它 Section；未跑原计划 #7；未修改 P1-05-A/B 与 P1-05-v1；
未修改 validator；未写题库；未进 validator 流程；未做人工审核；未计算质量指标；
未宣布 P1-05 通过；未做第二次调用；未自行提高预算重试；未改 prompt / context / temperature。

---

## 下一轮可用的事实（仅记录，不自行推进）

1. 16384 在 Unit 2 UI 上足以收敛（余量约 5,903 tokens）；其余 Section 上下文规模相近但**尚未逐一验证**。
2. P1-05-B 需要新版本（如 `P1-05-v2`）显式写入 `max_tokens=16384`、reasoning 参数与"截断即停"规则；
   **不得修改 `P1-05-v1`**。
3. 正式实验应重新开始，不把失败结果与新预算混在一起统计。
4. 建议正式重跑保留 `generation_guard`，避免再次"连续多次重复同一错误才停"。

---

## 产物

| 文件 | 说明 |
| --- | --- |
| `README.md` | 本索引 |
| `p1_05_budget_calibration_v2_report.md` | 完整报告（含 §十三 全部必答项） |
| `p1_05_budget_calibration_v2_audit.json` | 审计结果与跨运行对照 |
| `calibration_request.json` | 请求（含逐字节断言 + 单变量字段比对） |
| `calibration_response.json` | 原始响应 |
| `calibration_result.json` | 结果（guard 判定 + 保护项前后哈希） |
| `calibration_parsed.json` | 解析后的 JSON（**未入库**） |
| `calibrate_budget_v2.py` | 校准脚本（含 `--dry-run` 零成本校验） |
| `build_v2_audit.py` | 审计与对照脚本 |
