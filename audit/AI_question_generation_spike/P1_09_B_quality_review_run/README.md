# P1-09-B · AI 英语质量复核真实小样本验证

阶段结论：**P1-09-B_PASS**（能力评估：可用但有明确边界，见报告 §9 / §10）

```text
api_calls = 1 · retry_count = 0 · finish_reason = stop
model = deepseek-v4-pro · temperature = 0.2 · max_tokens = 16384 · reasoning_effort = low
prompt_version = P1-09-B-v1
latency = 51,050 ms · tokens = prompt 2,104 / completion 7,042 (reasoning 5,523) / total 9,146
审核题数 = 10（全部为正式题库真实题）· false_positive = 0 · false_negative = 1
```

## 本目录内容

| 文件 | 说明 |
| --- | --- |
| `p1_09_b_report.md` | 主报告（调用账目、盲测输入、样本、AI 结果、盲对照矩阵、成本修正、12 问、已证明 vs 未证明） |
| `p1_09_b_audit.json` | 汇总审计（调用账目 + 样本 + AI 结果 + 对照 + 成本 + 零改动验证 + 输入契约） |
| `sample_selection.json` | 样本选择与**实验人员侧对照标签**（只在 AI 返回后使用），含调用前逐题快照 |
| `input_snapshot.json` | **实际发给复核模型的盲测输入**（无 explanation / 无 validator 结论 / 无已知问题标签） |
| `reviewer_prompt.py` | 复核提示词 `P1-09-B-v1` 全文（含"拿掉原答案主动找替代答案"的反向策略） |
| `review_request.json` / `review_response.json` | 真实请求（含各类 SHA256）与原始响应 |
| `ai_review_output.json` | 模型返回的 10 条结构化复核结果（原样保存，未人工修改） |
| `call_accounting.json` | 调用账目：api_calls / retry / finish_reason / token / latency |
| `comparison.json` | 盲对照矩阵与统计（FP / FN / 各维度检出率 / 按题型分布） |
| `no_change_verification.json` | 调用前后数据库 SHA、10 题逐字段、行数、生命周期、事件、完整性 |
| `cross_check_prior_manifests.json` | 用 P1-09-A / P1-08-C 在调用前记录的哈希逐文件复核（1,095 文件 0 不一致） |
| `review_cost.json` | 真实成本 + 与 P1-09-A 估算的偏差修正 |
| `protect_before.json` / `protect_after.json` / `protected_assets_check.json` | 本阶段正式资产清单与前后比对 |
| `*.py` | 只读/审计脚本（select_samples / run_review / blind_compare / verify_no_change / cost_analysis / build_audit / protect_* / cross_check_prior_manifests） |

## 关键结果

```text
已确认问题题（P1-08-C 人工驳回的 AIQ:1B3AF72923C4）：AI 判 SUGGEST_REJECT + answer_unique=FAIL  ✔ 命中
答案唯一性：期望 2 题 → 检出 2 题；另有 2 题被判 FAIL/CONCERN（共 4/4 缺语境题被标出）
低学习价值：期望 2 题 → 检出 1 题（learning_value 为最弱维度）
干扰项风险：期望 2 题 → 检出 1 题（漏检 1 条属标签口径差异）
机械等级：与程序 mechanical_rewrite 标志 9/10 一致（1 条为定义差异，说明不应强行对齐）
正常题误伤：FALSE_POSITIVE = 0；1 条正常题被判"需人工复核"（因我方只给单条证据）
输出克制：无分数/总分/星级/排名/优先级/APPROVED/ACTIVE；中文理由可读
```

## 硬保护

```text
question_library.db   0 修改（调用前后 SHA256 均为 7AA12CA5…5DA7）
learning.db           0 修改        contentpack 0 修改
教材 PDF / 54 MP3     0 修改        Web / Android 0 修改
validator v2/v3       0 修改        P0～P1-09-A 冻结产物 0 修改
自动 APPROVED 0 · 自动 ACTIVE 0 · 写入 question_event 0 · 新依赖 0
```

AI 复核结果只保存在本审计目录，**未写入正式题库**。

## 重新运行（注意：`run_review.py` 会真实调用 DeepSeek 一次）

```powershell
python -X utf8 -B audit\AI_question_generation_spike\P1_09_B_quality_review_run\select_samples.py
python -X utf8 -B audit\AI_question_generation_spike\P1_09_B_quality_review_run\run_review.py 1   # 真实 API 调用
python -X utf8 -B audit\AI_question_generation_spike\P1_09_B_quality_review_run\verify_no_change.py
python -X utf8 -B audit\AI_question_generation_spike\P1_09_B_quality_review_run\blind_compare.py
python -X utf8 -B audit\AI_question_generation_spike\P1_09_B_quality_review_run\cost_analysis.py
python -X utf8 -B audit\AI_question_generation_spike\P1_09_B_quality_review_run\build_audit.py
```
