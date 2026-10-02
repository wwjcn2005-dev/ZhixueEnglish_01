# P1-08-A 实施报告 · AI 教材习题生成与题库入库流程定版

```text
最终结论   P1-08-A_PASS
AI 调用    0
正式交付    docs/AI教材习题生成与题库入库流程规范_V1.0.md
正式资产变化 仅新增该规范文档 + 本审计目录
```

---

## 0. 一句话结论

> P0～P1-07 已经实际跑通的生成 / 验证 / 入库 / 审核流程，已按"**已验证事实**与**设计目标**严格区分"
> 的方式写入正式规范 V1.0；`question_library.db`、`learning.db`、contentpack、validator、
> 教材 PDF/MP3 以及 V1.3 / V2.0 **全部未被修改**。

报告中的那处治理边界（V1.3 九与二十二·1 的原句）已由项目决策者**裁决为解读 A**
（2026-09-17），裁决记录见 §5.2 与 `p1_08_a_decision_record.md`；**V1.3 / V2.0 本轮仍不修改**。

---

## 1. 交付物

| 文件 | 说明 |
| --- | --- |
| `docs/AI教材习题生成与题库入库流程规范_V1.0.md` | **正式规范**，15,501 字符，SHA256 `2FED351363644EA5…` |
| `audit/.../P1_08_A_process_baseline/p1_08_a_audit.json` | 只读审计结果 |
| `audit/.../P1_08_A_process_baseline/p1_08_a_report.md` | 本报告 |
| `audit/.../P1_08_A_process_baseline/README.md` | 索引 |
| `audit/.../P1_08_A_process_baseline/p1_08_a_decision_record.md` | **V1.3 九 适用域裁决记录（解读 A）** |
| `audit/.../P1_08_A_process_baseline/build_audit.py` 等 | 只读审计脚本 |

### DOCX 决策：**不生成**

```text
docs/ 目录现有 14 份正式规范全部为 .md，不存在 DOCX 文档体系
本机无 python-docx、无 pandoc
→ 按任务"不要因为生成 DOCX 而安装新软件"的要求，本轮不生成 DOCX
```

（如后续项目建立 DOCX 体系，可再据此 Markdown 归档版本生成，无需改动本规范内容。）

---

## 2. 只读审计结果

### 2.1 P0～P1-07 产物核对

```text
P0_closeout / P1_01 / P1_02 / P1_03 / P1_04 / P1_05-A(sample_design) /
P1_05-B(real_validation) / P1_05-C(budget_calibration) / P1_05-D(budget_calibration_v2) /
P1_05-E(manual_review) / P1_05-F(prompt_v2) / P1-05-G(prompt_v3) /
P1_06_batch_stability / P1_07_library_ingest
→ 14 / 14 全部在位，且未被本轮修改
```

### 2.2 题库现状（只读）

```text
question_library.db  schema v2 · integrity_check ok
题目 21 · PENDING_REVIEW 21 · APPROVED 0 · ACTIVE 0 · generation_run 12
```

### 2.3 本轮把"已实测"与"未验证"严格分开

规范 §16 用两张表明确区分，**不把设计目标写成已验证事实**：

- **§16.1 已验证（17 项）**：Section 级生成、无固定题量、可生成 0 题、DeepSeek 链路、
  16384 预算（5 个 Section 实测 `stop`）、截断即停、证据真实性、词汇边界口径、
  deterministic dedupe key、独立题库、PENDING_REVIEW、ACTIVE 硬门槛、单事务入库、
  provenance、人工审核前不进入学习、正式资产保护等；
- **§16.2 未验证（14 项）**：大规模批量稳定性、低证据 Section 行为、listening / grammar /
  writing / speaking 题型、规模化干扰项质量、长文本 Section、长期成本吞吐、
  教材版本 stale 实跑、schema v3 对判断题的正式改进、**证据组装层缺陷**、
  **APPROVED → ACTIVE 全流程尚未实跑**、learning_record 迁移、以及 §5.3 的边界裁决。

---

## 3. 规范固定的核心内容

| 章节 | 内容 |
| --- | --- |
| §2 | 一句话总纲 + AI / 程序 / 人工三方角色分工 |
| §3 | 12 步核心流程（教材 → 证据 → 生成 → 完整性检查 → 确定性验证 → 合格候选 → 题库 → PENDING_REVIEW → 人工 → APPROVED → ACTIVE → 学习系统） |
| §4 | 五条冻结规则（教材唯一内容边界 / Section 为 generation boundary / 不设固定题量 / **生成前必须先建立完整教材证据** / 质量责任分层） |
| §6–§10 | 证据组装、AI 生成、确定性验证（A–G）、合格候选判定（五道闸门 + 六种判定）、单事务入库 |
| §11 | 生命周期（正常链 + REJECTED/DISABLED/STALE）与"VALIDATED ≠ APPROVED ≠ ACTIVE" |
| §12 | 数据边界（contentpack 只读 / learning.db 不写 / 只有 question_library.db 可写） |
| §13 | 人工审核职责（只审教育质量，不重复机器检查） |
| §14 | Provenance 可追溯链与必留字段 |
| §15 | 失败与停止条件（11 类，禁止放宽规则） |
| §16 | **已验证 vs 尚未验证** |
| §17 | 特殊题型口径（reading_judge 的兼容处理 + fill 的合法形态） |
| §18 | 技术元数据不得暴露给孩子 |
| §19 | 变更与复用规则（复用优先、STALE、prompt 版本只增） |
| §20 | 与 V1.3 / V2.0 的同步结论 |

其中两条来自**实测教训**、写成了硬性要求：

1. **规则 4（证据组装完整性）**：不得用 `activity → page → text` 反推正文；
   "页面没有 activity"不能意味着该页正文被自动丢弃 —— 依据是 P1-07 暴露的
   Unit 1 UI 课文主体页（P17/P22）被漏掉的真实缺陷；
2. **截断即停**：`finish_reason=length` 必须立即停止，不得解析、不得入库、不得继续下一个 Section
   —— 依据是 P1-05-B 连续 6 次截断。

---

## 4. 保护资产核对（执行前后一致）

```text
question_library.db   F74CA83F…（与 P1-07 结束时完全一致，未新增/修改/删除任何行）
learning.db           0C27267B…CF91
contentpack v5        65829CA7…0C39
validator v2 / v3     7C61585A… / EDB1AA54…
P1-06 S1–S4 fixture   D4520E28… / 4F705951… / 4F9679CA… / 5D1C2103…
P1-07 产物             candidate_decision.json / ingest_result.json 未变
教材 PDF              C732051E…4F2F
54 个 MP3             54/54 与 audio_asset.sha256 一致
Web / Android / V1.3 / V2.0   未修改
```

**本阶段正式资产变化仅有：新增 1 份规范文档 + 本审计目录。**

---

## 5. V1.3 / V2.0 同步检查结果（含一处需裁决的边界）

### 5.1 只读比较实测

| 关键词 | V1.3 | V2.0 |
| --- | --- | --- |
| `question_library` | 0 | 0 |
| 题库 | **6** | 0 |
| 生成题 | **3** | 0 |
| AI 生成题 | **1** | 0 |
| 无限题库 | **1** | 0 |

→ **V2.0：全文未涉及，无需修改。**
→ **V1.3：有涉及**，绝大多数条款与本规范一致（规范 §5.2 已逐条对齐）：
不做无限/大型题库、AI 生成内容须与教材明确区分、AI 生成训练须服务明确学习目标、
AI 数据与教材资源隔离、AI 数据复用优先、静态页面不得无意义调用 AI、AI 角色边界。

### 5.2 边界裁决：**已于 2026-09-17 采用解读 A**（V1.3 本轮不改动）

V1.3 原句：

> **九**："AI 可以批改、分析、解释、归纳错误并给出建议，但**不得创造教材事实**——
> **不得生成或改写教材正文、题干、选项、答案**、音频与音频片段，也不得把 AI 生成的结论写入教材内容事实。"
>
> **二十二·1**："本产品不是：**AI 题库**；自动作业系统；自动学习路径系统；刷题系统……"

| 解读 | 与本规范 |
| --- | --- |
| **A（教材事实层）**：禁止把 AI 生成的题干/选项/答案**当作教材事实**写入教材数据 | **完全一致** |
| **B（绝对禁止）**：任何 AI 生成的题干/选项/答案都不得存在 | **直接冲突**；且与同节"提供**少量针对性训练**""AI 生成训练必须服务于明确的学习目标或薄弱点"存在内部张力 |

**裁决原文（2026-09-17）**：

> "同意采用解读 A：AI 可以生成教材训练题，但 AI 生成的题干、选项、答案不得冒充教材事实，
> 不得写入教材数据；AI 题独立存放，经审核后才能进入学习流程。"

**生效后的执行口径**（裁决直接要求 + 本规范加设的更严格限制）：
AI 题只存在于 `question_library.db`；绝不写入教材数据；必须经确定性校验；
只有 `ACTIVE` 才允许进入学习流程，而 `ACTIVE` 的前置是人工审核；
孩子端不得呈现"题库/刷题"概念；不允许"随机大量生成"。

**对 V1.3 / V2.0 的影响**：解读 A 下不存在实质矛盾 →
**V1.3 / V2.0 本轮均不修改**；规范 §5.3 保留一份**可选**的措辞澄清文本，
供下一次 V1.3 修订时纳入（非阻塞）。裁决记录见 `p1_08_a_decision_record.md`。

---

## 6. 最终结论

### `P1-08-A_PASS`

V1.0 规范**能够准确表达已经验证的实际流程**：

- 已验证部分逐项标注了验证方式；
- 未验证部分单独列出且明确不得写成已解决；
- 一处治理层边界如实上报并附带建议文本，未强行"定版"掩盖。

**遗留待办（不在本轮处理）**：

```text
① （已裁决 2026-09-17：采用解读 A）V1.3 九 的措辞澄清为可选、非阻塞项，可留待下一次 V1.3 修订
② 教材证据组装层缺陷修复（页面无 activity 导致正文被漏）
③ schema v3：判断题 answer_support 的正式取值
④ 人工审核 → APPROVED → ACTIVE 全流程实跑
⑤ learning_record 的 source_kind / source_ref / source_version 迁移
⑥ 未验证题型与规模化稳定性（规范 §16.2）
```
