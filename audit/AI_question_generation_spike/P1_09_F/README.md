# P1-09-F · 选择题逐候选协议最小真实验证

结论：**`P1-09-F_PASS`**

```text
AI 调用 = 1 · retry_count = 0 · finish_reason = stop · 测试对象 = P1-09-D 的 FIX-C1 / FIX-C2
FIX-C1 第二答案 students：以前 ACCEPT → 现在 UNIQUE_RISK（检出）
FIX-C2 第二答案 word    ：以前 ACCEPT → 现在 UNIQUE_RISK（检出）
false negative = 0 · 真实正确选项被错误排除 = 0
最终状态由程序汇总产生 · AI 未输出任何整体唯一性结论
```

## 本目录内容

| 文件 | 说明 |
| --- | --- |
| `p1_09_f_report.md` | 主报告（13 节，含逐候选原始结果、程序汇总、锚定检查、FP/FN、成本、保护） |
| `ai_input_snapshot.json` | 实际发给模型的逐候选盲测输入（无 gold / 无分类标签 / 无历史回答） |
| `candidate_map.json` / `input_manifest.json` | 选项映射与调用前锁定值（含禁用词扫描结果） |
| `reviewer_prompt_f.py` | 提示词 `P1-09-F-v1`（只要求逐候选判断，明确禁止整体唯一性结论） |
| `review_request.json` / `review_response.json` | 真实请求与原始响应 |
| `ai_review_output.json` | 模型返回的 8 条逐候选判断（原样保存） |
| `call_accounting.json` | 调用账目（1 次 / 0 重试 / tokens / latency / finish_reason） |
| `assessment.json` | **程序侧汇总**（重算 valid_alternative + 三态判定，不照抄模型结论） |
| `comparison.json` | 与 P1-09-D gold 的对照、FP/FN、锚定模式扫描、成本对比 |
| `protection_check.json` | 1,160 个正式资产文件复核（mismatched=0 / missing=0） |
| `build_input.py` / `run_review_f.py` / `aggregate_f.py` / `compare_f.py` / `protect_crosscheck.py` | 本轮脚本 |

## 程序汇总规则（本阶段落地版）

```text
program_valid_alternative := grammar=YES AND semantic=YES AND textbook_context=YES
任一非当前答案选项 valid   → UNIQUE_RISK
任一候选 need_more_context → UNIQUE_UNCERTAIN
全部被排除且 coverage=COMPLETE → UNIQUE_SUPPORTED
```

```text
FIX-C1  coverage=COMPLETE  assessment=UNIQUE_RISK  flagged=[students, parents, teachers]
FIX-C2  coverage=COMPLETE  assessment=UNIQUE_RISK  flagged=[word, name]（picture 被正确排除）
```

## 成本

```text
input 1,216 / output 9,088（reasoning 8,533 = 93.9%）/ total 10,304 / latency 147.6 s
2 题 → 5,152 tokens/题（P1-09-D 基线 1,024.7 tokens/题 → 5.03×；
按输出侧单题比较约 6×，差异来自"每候选独立推理"；
P1-09-E 每候选 +35 output tokens 的估算被实测推翻，实际约 1,136 tokens/候选）
```

## 两条必须一起读的限制

```text
LIMITATION-1 精度：语法语义站得住的并行选项几乎都会被标为有效 →
  选择题 UNIQUE_RISK 比例会很高，人工复核负担不会下降；它防的是"误报唯一"。
LIMITATION-2 成本：每候选约 1.1k tokens（reasoning 为主），需按实测重新建模。
LIMITATION-3 样本：仅 2 道 vocab_choice；reading_choice 与其它 Unit 未验证。
```

## 硬保护

```text
1,160 个正式资产文件复核 mismatched=0 / missing=0
question_library.db 7AA12CA5…5DA7 / learning.db 0C27267B…CF91 / contentpack v5 65829CA7…0C39 均未变
未生成正式题目、未写 question_library、未改教材资产 / Web / Android / validator / lifecycle
未做 schema migration、未新增依赖、未安装软件；AI 结果只写入本目录
```
