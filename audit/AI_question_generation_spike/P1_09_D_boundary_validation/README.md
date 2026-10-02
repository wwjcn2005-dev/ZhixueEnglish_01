# P1-09-D · AI 英语质量复核边界样本验证

最终结论：**P1-09-D_STOP_AND_FIX**

一句话：

> 15 道人工设计的边界 fixture 全部完成、流程干净；AI 在 5 个维度上表现可靠，
> **但在"真正第二正确答案"（本次最重要类别）上 0/2 全漏，且以 HIGH 置信度给出"无显著问题"的放心结论**。
> 这不是继续调 Prompt 能解决的问题，必须先修机制。

```text
api_calls = 1 · retry_count = 0 · finish_reason = stop · fixture = 15/15
model = deepseek-v4-pro · temperature 0.2 · max_tokens 16384 · reasoning_effort low
prompt_version = P1-09-D-v1 · latency 129.7 s
tokens = prompt 3,919 / completion 11,452 (reasoning 9,875) / total 15,371
维度命中 36/41 · 维度 FN 2 · 维度 FP 0 · 决策命中 12/15 · 完全命中 12/15
```

## 本目录内容

| 文件 | 说明 |
| --- | --- |
| `p1_09_d_report.md` | 主报告：fixture 设计、AI 结果、维度级/决策级双套对照、11 问、已证明 vs 未证明 |
| `fixtures.json` | **15 道人工设计的 fixture**（含 category / fixture_only / introduced_defect） |
| `hidden_gold.json` | **实验人员侧 gold**，与 AI 输入物理分离，绝未进入 AI 输入 |
| `ai_input_snapshot.json` | 实际发给模型的盲测输入（按 P1-09-C Review Context Contract V1 Minimal 级） |
| `fixture_manifest.json` | 调用前锁定的三个 SHA256 + gold 泄漏检查结果 |
| `reviewer_prompt_d.py` | 本次复核提示词 `P1-09-D-v1`（实现 P1-09-C 三份契约） |
| `review_request.json` / `review_response.json` | 真实请求与原始响应 |
| `ai_review_output.json` | 模型返回的 15 条结构化结果（原样保存） |
| `call_accounting.json` | 调用账目（api_calls / retry / finish_reason / token / latency） |
| `comparison.json` | 逐维 + 决策双套对照结果、按类别统计、泛化理由统计 |
| `protection_manifest.json` | 调用前后正式资产比对（0 变化）与 question_library 状态核对 |
| `protect_before.json` / `protect_after.json` | 1164 个正式资产文件的哈希快照 |
| `build_fixtures.py` / `run_review_d.py` / `compare_d.py` / `protect_snapshot.py` / `protect_compare.py` | 本轮脚本 |

## 七类结果速览

| 类别 | n | 结论 |
| --- | --- | --- |
| A 真正错误英语 | 2 | **2/2 全部发现**（并指出具体错误位置） |
| B 明显错误干扰项 | 2 | **2/2 全部发现**（判 CONCERN，未与唯一性混淆） |
| **C 真正第二正确答案** | 2 | **0/2 全漏**（判 PASS + ACCEPT + HIGH）← 关键失败 |
| D 现实常识冲突 | 2 | **2/2 正确克制**（未被现实常识带偏） |
| E 上下文不足 | 2 | **2/2 正确输出 CONTEXT_INSUFFICIENT**，未升级为 REJECT |
| F 高学习价值正常题 | 3 | 2/3 完全命中；1 条分歧更可能是 fixture 弱点 |
| G 机械但合理的重点词填空 | 2 | **2/2 未因机械形式误杀** |

## 硬保护

```text
manifest 前后一致 EA604045719475772D0703EC3D0906806044773DB0900338B5E7E3FF1E17742B
question_library.db 7AA12CA5…5DA7 / learning.db 0C27267B…CF91 / contentpack v5 65829CA7…0C39 均未变
行数、events、ACTIVE 1 / PENDING_REVIEW 19 / REJECTED 1、stale 均不变
未写正式题库、未写 question_event、未自动 APPROVED/ACTIVE、未装依赖、未改 gold
```

## 下一步（不自动执行）

```text
P1-09-E 应做"答案唯一性机制修复设计"：
  方案 1 程序侧生成候选替代答案集合 + 强制 AI 逐条判断是否被教材语境排除
  方案 2 把 answer_unique 从 AI 单点判断中移出，改为"程序候选清单 + 人工确认"
另需明确：选项自身语法错误计入 english_correct 还是 distractor_quality。
```
