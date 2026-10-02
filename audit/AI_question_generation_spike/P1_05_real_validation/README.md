# P1-05-B · AI 题库多 Section 小规模真实质量验证

## 最终状态

### **VALIDATION_BLOCKED**

**不是** `QUALITY_NOT_READY`——`QUALITY_NOT_READY` 意味着"质量测过了但不够好"；
本轮是"质量没能被测到"。

---

## 发生了什么（一句话）

按 P1-05-A 冻结方案对 7 个 Section 执行，**跑完 6 个后按纪律停止**：
6 次调用**全部 `finish_reason=length`、content 为空、生成 0 题**——
输出预算在 reasoning 阶段被耗尽的技术性截断，与 P0 1610 同机理。

```text
已执行 Section    6 / 7
生成题目          0
入库题目          0
VALIDATION_PASS   0      （validator 没有任何输入）
APPROVE           0      （没有题可审）
ACTIVE            0
REVIEW_APPROVED   0
新增 generation_run 7    （6×TRUNCATED + 1×in-flight 占位）
已有 2 道题        完全未动
```

---

## 根因（本轮唯一有效的正向产出）

| 轮次 | 提示词 | max_tokens | reasoning | content | 结果 |
| --- | --- | --- | --- | --- | --- |
| P0 1630 | P0-v1（**有** 3 题上限） | 8192 | 5,648 | 1,685 字符 | ✅ 3 题 |
| P1-03 | P0-v1（有上限） | 8192 | 6,638 | 2,436 字符 | ✅ 3 题 |
| **P1-05-B** | **P1-05-v1（无上限）** | **8192** | **8,192 占满** | **0** | ❌ 6/6 截断 |

> **P1-05-A 冻结的两个参数互相冲突**：去掉题量配额后，模型在 reasoning 阶段失去收敛压力，
> 需要超过 8192 tokens 才能收手；而 P1-05-A 同时冻结了 `max_tokens = 8192`。

这不是模型变差、不是证据不足、也不是 validator 问题——validator 本轮没有任何输入。

---

## 为什么停止

**S1–S8 无一条被字面触发**（0 题入库、无超时 118.5–128.7 s、保护项未变）。
停止依据是 P1-05-B **§二**：

> 「如果发现机制问题：**停止并报告，不得现场修机制继续跑。**」

6 次调用给出完全一致的截断签名，已足以判定为系统性机制问题；
继续跑第 7 个 Section 只会以真实成本重复同一个空结果。
第 7 个 Section 因此**如实标注为未执行**，`generation_run` 保留为 in-flight 占位，不删除、不美化。

**没有**通过调大 `max_tokens` 再跑来"救"结果——那属于现场修机制。

---

## 核心统计（§十七）

```text
generated_count        0
validated_pass_count   0
validated_fail_count   0
Evidence PASS Rate     N/A（0/0，未定义；不是 0%）
APPROVE                0
REJECT_CONTENT         0
REJECT_QUALITY         0
REJECT_SCOPE           0
Natural Value Rate     N/A（0/0，未定义；不是 0%）
```

全部为 0 的含义是 **"无样本"**，不是"质量差"，也不是"没有重复"。

### Validator Interception（§十八）

```text
vocabulary scope 0 · evidence 0 · answer support 0 · duplicate 0
structure 0 · option consistency 0 · other 0
→ 不是"拦截率为 0"，而是"没有内容进入 validator"
```

### 重复分析（§十九）

四个维度（Section 内 / Section 间 / 同一 evidence block / 仅换问法）**均无样本**。

### 人工审核（§十五）

**没有可审核的对象。** 六项判断与四类归类都要求存在题目，本轮不伪造任何审核记录。

---

## 成本（§二十）

```text
模型              deepseek-v4-pro
完成调用           6（+1 次被终止）
重试               0
API 层失败         0
总 prompt tokens   49,898
总 completion      49,152（其中 reasoning 48,498）
总 tokens          99,050
总耗时             741.7 s（12.4 分钟）
平均单次           123.6 s   最长 128.7 s（≤180 s 正常目标）
每道生成题 tokens   未定义（分母为 0）
```

**为 0 道题花了约 9.9 万 tokens。** 预算不足时成本全额浪费——这不是"省一点"的问题。

---

## 验收（§二十一，严格判定）

| # | 条件 | 判定 |
| --- | --- | --- |
| A | 已入库题 `REJECT_CONTENT = 0` | 空转成立但**无验证力** |
| B | 至少 1 个正常 Section **自然**产出 0 题 | **FAIL**（0 题来自技术截断，§二十一明确排除） |
| C | `Natural Value Rate ≥ 60%` 且 `APPROVE ≥ 5` | **FAIL**（N/A 且 APPROVE = 0） |
| D | 题量分布不同且可由证据密度解释 | **FAIL**（常数为 0） |
| E | 单次 ≤180 s、总计 ≤30 min、失败调用 0 | **PASS** |
| F | 未触发任何停止条件 | 部分（S1–S8 未字面触发；因 §二 主动中止） |

```text
总体判定：NOT_PASS
```

---

## 保护项

```text
learning.db        未修改（SHA256 0C27267B…CF91）
contentpack v5     未修改（SHA256 65829CA7…0C39，ai_artifact = 0 行）
教材 PDF           未修改（C732051E…4F2F）
54 个官方 MP3       未修改
validator v2/v3    未修改（7C61585A…A683 / EDB1AA54…900C）
Web/Android/V1.3/V2.0 未修改
正式 8770 / Demo 8780  未被终止（只终止了 P1-05-B 进程）
已有 2 道题         完全未变（AIQ:3179968E3E74 / AIQ:7EBCDBC29563）
```

唯一被写入的正式资产是 `structured/ai/question_library.db`：新增 7 条 `generation_run`，**0 条新题**。

---

## 下一轮之前必须先解决（只记录，不实施）

1. `max_tokens` 与"无配额提示词"必须匹配——需要一次真实调用验证过的预算。
2. 增加"**截断即停**"前置规则：本轮 6 次截断才停，若首次 `length` 即停可省约 8.2 万 tokens / 10 分钟。
3. P1-05-A 冻结方案存在内部冲突，需在下一版显式标注参数依赖（提示词约束强度 ↔ 输出预算）。

---

## 任务输入的一处不完整

本轮任务书在「**二十四、正式题库保护**」处被截断。按既有各轮的保护约束执行：
仅允许写入 `question_library.db`，其余正式资产一律不动；执行前后均做哈希复验。

---

## 产物

| 文件 | 说明 |
| --- | --- |
| `README.md` | 本索引 |
| `p1_05_real_validation_report.md` | 完整报告（含根因、停止依据、验收） |
| `p1_05_real_validation_audit.json` | 审计结果 |
| `generation_summary.json` | 7 个 Section 执行摘要 |
| `human_review_results.json` | 人工审核（0 题） |
| `cost_summary.json` | 成本统计（逐次调用） |
| `question_distribution.json` | 题量分布 |
| `duplicate_analysis.json` | 重复分析 |
| `runs/` | 各 Section 的 context / prompt / 原始响应 / 解析 / validator 结果 |
| `run_p1_05b.py` · `build_report_data.py` | 执行与统计脚本 |
