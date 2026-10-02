# P1-09-G · 选择题唯一性风险分层设计（只读机制设计与离线验证）

结论：**`P1-09-G_BLOCKED`**

```text
含义：现有数据（且不新增依赖）不足以进行有意义的"程序预筛"。
AI 调用 = 0 · 全部只读离线分析 · 新增产物只写入本目录
```

## 三条决定性实测结果

```text
① 预筛过宽：10 道真实选择题中 8 道被标为 AI_REVIEW_CANDIDATE（80%），
   其中包含已经人工审核通过、处于 ACTIVE 的 AIQ:BD59C5958D45。
② 预筛过窄：FIX-C1（真实第二答案 students）被判 NO_AI_SIGNAL → 漏检；
   FIX-C2 被 R5 捕获 → 1 中 1 漏。
③ 规则价值不均：R1（选项重复/包含）与 R2（词形变化对）在 12 例上触发 0 次；
   大面积触发的是 R3/R4（同词性）与 R5（教材来源），而它们正是"连正常题一起标"的规则。
```

根因不在规则写法，而在数据：答案词性缺失（全教材正文 87% 的词无词性）→ R3/R4 直接失效；
没有语义资源 → "爷爷还能和谁一起拉二胡"这种开放集合无法刻画；
没有可靠答案来源（360/360 教材题 answer_source 均为 NO_RELIABLE_SOURCE）。

## 本目录内容

| 文件 | 说明 |
| --- | --- |
| `p1_09_g_report.md` | 主报告（15 节：题型分布、R1–R7 规则、fixture 验证、反向验证、候选率、成本、产品定位、fill 方案、库结构、10 项"PASS 但不好用"检查、架构修正、下一步） |
| `prescreen_rules.py` | R1–R7 确定性预筛实现（只读 contentpack + question_library） |
| `prescreen_result.json` | 12 例逐题逐规则结果（含触发原因与证据） |
| `risk_layer_analysis.json` | 分层判别力分析：候选率、已知风险命中/漏检、ACTIVE 误标、规则触发统计 |
| `cost_model.json` | 4 档成本模型（基准 = P1-09-F 实测 5,152 tokens/题） |
| `layers_and_cost.py` | 分层分析与成本估算脚本 |
| `protection_check.json` | 正式资产零变化复核（锚点 = P1-09-D 调用前清单） |

## 关键数字

```text
21 道现有题：fill 9 · vocab_choice 6 · reading_choice 4 · reading_judge 2
（ACTIVE 1 · PENDING_REVIEW 19 · REJECTED 1）

AI 候选率：12 例 9/12 = 75.0%；真实选择题 8/10 = 80.0%
已知风险命中：FIX-C2 中 / FIX-C1 漏
已人工通过题被误标：1 / 1
R1/R2 有效触发：0 / 0

成本（每 100 道选择题，纯模型估算）：
  A 100% → 100 次调用 / 515,200 tokens / 5.03×（P1-09-D 基准）
  B  50% →  50 次调用 / 257,600 tokens / 2.51×
  C  30% →  30 次调用 / 154,560 tokens / 1.51×
  D  20% →  20 次调用 / 103,040 tokens / 1.01×
```

## 两个设计结论

```text
1. answer_unique 定位 = 风险检测器（方案 2），不是硬质量门禁（方案 1）。
   禁止 "没有发现风险 = 答案唯一"（NO_RISK = UNIQUE_CERTIFIED）。
2. 填空题单独处理：answer_unique_status = NOT_PROVABLE（+ coverage = NONE），
   不得使用逐候选证明机制，不得输出 UNIQUE_SUPPORTED。
```

架构修正：去掉"程序风险预筛 → 低风险正常进入"这一分支（分不出来），
选择题改为"人工直接看选项（可选：AI 逐候选作为阅读辅助，非闸门）"，
填空题走 NOT_PROVABLE，生命周期完全不变。

## 硬保护

```text
AI 调用 0 · question_library.db / learning.db / contentpack / 教材资产 / Web / Android
/ V1.3 / V2.0 = 0 修改 · 未新增依赖 · 未做 schema migration · 未生成正式题目
```
