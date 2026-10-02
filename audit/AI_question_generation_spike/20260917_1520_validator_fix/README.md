# P0 · 校验器口径修正与回归（2026-09-17 15:20）

## 状态：完成（0 次 AI 调用，原始 3 题回归 3/3 PASS）

本轮只做三件事：**修正两处已确认的校验器误报口径 → 用原始 3 题回归 → 补测试**。
未调用任何 AI（云端 0、本地 0），未重新生成题目，未修改原始 AI 输出。

## 修正内容

### 修正 1 · 词汇白名单（消除误报）

- 修正前：把 `explanation` 里的说明词（`states / correct / text` 等）与引号包裹的词（`'trailer'`）也当作题目词汇 → 误报"超纲"。
- 修正后：白名单**只检查** `question` + `options` + `answer`（`validator_v2.checked_language()`）；
  归一化处理大小写、标点、引号、常见缩写（`'trailer'` 与 `trailer` 视为同词）；
  `explanation` 与其它元数据字段完全不参与。

### 修正 2 · 答案支持（分级 + 确定性判定）

新增 `answer_support()`，返回四类 `answer_support_type`：

| 取值 | 判定规则（确定性，不采信 explanation 自述） |
| --- | --- |
| `EXACT` | answer 的词序列是 `evidence_quote` 的一段**连续片段** |
| `VERIFIABLE_REFERENCE` | 与引用的差异**只有代词**（≤2 个，且都在代词白名单内），去掉代词后仍是引用中的连续片段，且引用内含可作为先行词的复数/实体名词 |
| `VERIFIABLE_REPHRASE` | 差异只有**缩写展开**或**规则词形变化**（复数/三单/-ed/-ing），且答案的内容词按顺序连续命中引用的内容词窗口（功能词允许不同） |
| `UNSUPPORTED` | 其它一律不支持 |

只有前三类算通过；`UNSUPPORTED` 判 FAIL。**绝不因为 AI 的解释声称"这是指代"就放行。**

## 产物

| 文件 | 内容 |
| --- | --- |
| `validator_v2.py` | 修订后的校验器（含 `answer_support` / `checked_language` / `build_whitelist`） |
| `test_validator_v2.py` | 9 个单元测试（覆盖要求的 7 类情形） |
| `regression_v2.py` + `validation_result_v2.json` + `validation_report_v2.md` | 对原始 3 题的 8 项回归 |
| `adversarial_check_v2.py` + `adversarial_result.json` | 6 个合成坏样本的拦截验证 |

## 结果

- 单元测试：**9/9 PASS**
- 原始 3 题回归：**3/3 PASS**（q1 `EXACT`、q2 `EXACT`、q3 `VERIFIABLE_REFERENCE`）
- 对抗性检查：**6/6 全部拦截**（教材外选项词 / 无支持答案 / 编造引用 / 无效 block id / fill 无空位 / correct_option 不一致）
- 原始 AI 输出未被修改：`generated_questions.json` SHA256 = `055191F7…30AB`（与 1450 轮相同）

## 仍然欠缺的机制（不在本轮范围）

1. **干扰项是否被教材排除**尚未机器判定（当前只校验"选项不重复 + 正确答案唯一且与 answer 一致"）——q3 的干扰项 A/C/D 是人工确认与教材冲突的；
2. 跨多句的证据（一条 `evidence_quote` 覆盖两个不连续片段）暂不支持；
3. "题目自然度 / 学习价值"仍属人工或 AI 评审，不在确定性规则内。
