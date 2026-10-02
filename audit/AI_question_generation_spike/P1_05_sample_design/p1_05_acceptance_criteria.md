# P1-05-B · 成功判据与停止条件（冻结）

本文件在 P1-05-B 执行**之前**冻结，执行过程中**不得放宽**。

---

## 一、什么**不是**成功

以下都不构成 P1-05-B 的成功：

- ❌ 生成了 X 道题
- ❌ validator 100% PASS
- ❌ 每个 Section 都出了题
- ❌ APPROVE 数量多

P1-05-B 要回答的是**机制问题**，不是产量问题。

---

## 二、六个必须回答的问题与通过条件

| # | 问题 | 通过条件（必须全部满足） |
| --- | --- | --- |
| **A** | 机制是否能够稳定阻止明显错误题？ | ① 已入库题中 **0 道**被人工判为 `REJECT_CONTENT`；② 所有 validator FAIL 的题**确实未入库**；③ 未出现 `教材外事实` 未拦截的情况 |
| **B** | AI 是否能够做到"有价值才生成"？ | ① **至少 1 个 Section 自然产出 0 题**；② 不存在人工判定为"为凑数而生成"的题（`REJECT_QUALITY` 且原因为凑数） |
| **C** | 人工审核后的 APPROVE 比例是否达到可继续扩大的程度？ | ① `Natural Value Rate = APPROVE / generated ≥ 60%`；② `APPROVE` 绝对数 `≥ 5` |
| **D** | 不同教材 Section 是否表现出明显差异？ | ① 题量分布**不是常数**（不同 Section 题量不同）；② 差异能被证据密度解释（低密度 Section 题量 ≤ 高密度 Section） |
| **E** | 当前成本与延迟是否可接受？ | ① 单次调用 ≤ 180 s；② 全部调用总耗时 ≤ 30 min；③ 无失败调用（HTTP 非 200 / 超时） |
| **F** | 是否暴露出新的必须先修正的机制问题？ | **S1–S8 任一条目均未被触发** |

### 关于 C 的阈值说明

`60%` 是**工程参考阈值**，用于判断"是否值得继续扩大实验"，**不是**统计学结论。
若 APPROVE 绝对数 < 5，即使比例高也必须标注"样本过小，不足以支撑扩大"。

---

## 三、停止条件（触发任一即立即停止，不得跑完剩余 Section）

| # | 条件 | 为什么必须停 |
| --- | --- | --- |
| **S1** | 任何已入库题被人工判为 `REJECT_CONTENT` | 说明确定性校验漏放了内容错误 |
| **S2** | 出现教材外事实而 validator 未拦截 | 同上；P1-03 已出现过一次（`Mozi`），必须确保是被拦截而不是碰巧 |
| **S3** | 出现 `ACTIVE` 题，或任何 `REVIEW_APPROVED` 事件 | 人工审核门槛被绕过 |
| **S4** | 出现跨库悬空引用（LearningObject / evidence block 不存在） | provenance 断裂 |
| **S5** | `learning.db` / contentpack / PDF / MP3 / Web / Android / V1.3 / V2.0 任一被修改 | 保护项被破坏 |
| **S6** | validator 出现误报（合规题被判 FAIL） | 校验器口径需要先修正 |
| **S7** | 单次调用 > 300 s，或出现需要重试的失败 | 成本/稳定性不可接受 |
| **S8** | 任一 Section 出现"为凑数而生成的明显低价值题" | 说明"不设配额"的约束没有被 AI 遵守 |

**停止后的动作**：先形成机制修正方案并说明修哪里（validator / prompt / 证据 / 流程），
**不得直接进入下一阶段，也不得自行降低判据**。

---

## 四、必须同时声明的边界

> 这是**工程质量小样本验证**。
> 6～7 个 Section 的结果**不能**推断整本教材（40 个 Section）的总体质量，
> 也不能推断长期稳定性。

它的作用是发现：

```text
机制缺陷 · prompt 缺陷 · validator 缺陷 · evidence 缺陷 · 人工审核瓶颈 · 成本问题
```

然后决定下一步——而不是宣布"AI 出题已经可用"。

---

## 五、指标计算口径（冻结）

| 指标 | 公式 | 分母说明 |
| --- | --- | --- |
| Evidence PASS Rate | `validator PASS / generated` | 分母含被拦截的题 |
| Human Value Rate | `APPROVE / generated` | 同上 |
| Natural Value Rate | `APPROVE / generated` | 同上 |
| Validator Interception | 按失败项分类计数 | vocabulary scope / evidence / answer support / duplicate / structure / option consistency / other |
| Question Count Distribution | 逐 Section `0/1/2/3/…` | `LISTENING_EVIDENCE_GAP` 组**不进分母** |
| Cost | 逐次调用记录并汇总 | 见 `generation_run` 字段 |

### 重复判定（冻结）

> **同一教材位置生成多道题本身不算重复。**
> 只有失去独立学习价值才算重复。

四个观察维度：① 同 Section 内 ② 跨 Section ③ 同一 evidence block 复用次数
④ 同一知识点换问法。

### 题量判定（冻结）

> **不设上限。** 某 Section 生成很多题不会因为"超出预期"自动判错；
> 需要看是否重复、是否覆盖不同知识点、是否有独立学习价值。

---

## 六、判据变更规则

本文件的任何条件在执行期间**不得修改**。
若发现某条判据本身不合理（例如阈值定错），必须：

1. 先停止 P1-05-B；
2. 在报告中写明"哪条判据、为什么不合理、建议改成什么"；
3. 由下一轮决定是否修改；
4. **不得**为了跑完实验而现场放宽判据。
