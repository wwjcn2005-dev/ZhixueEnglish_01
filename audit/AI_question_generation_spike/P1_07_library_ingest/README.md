# P1-07 · 正式题库入库闭环演练

```text
最终结论   P1-07_PASS
AI 调用    0
入库       19 道 → PENDING_REVIEW
未入库     3 道（EVIDENCE_INCOMPLETE）
ACTIVE     0     APPROVED 0     REVIEW_APPROVED 0
唯一被修改的正式资产：structured/ai/question_library.db
```

用 P1-06 已生成的 **22 道题作为固定 fixture**（未修改），走完
**证据 → 确定性判定 → 正式题库 PENDING_REVIEW → 只读验收** 的闭环。

---

## A · 22 道题判定

| 指标 | 数量 |
| --- | --- |
| 总数 | 22 |
| **可入库（PASS）** | **19** |
| **EVIDENCE_INCOMPLETE** | **3**（S3-Q2、S3-Q3、S4-Q4） |
| ORIGINAL_TEXTBOOK（标志） | 2（S3-Q2、S3-Q3） |
| MECHANICAL_REPRODUCTION（拒绝） | 0 |
| mechanical_rewrite=true（按 D1 允许） | 10 |
| DUPLICATE_CANDIDATE | 0 |
| NEEDS_REVIEW | 0 |
| rule4_waived_for_judge | 2 |

---

## B · 题库前后

| 表 | 前 | 后 |
| --- | --- | --- |
| generation_run | 8 | **12** |
| ai_question | 2 | **21** |
| question_evidence | 2 | **22** |
| question_learning_object | 4 | **37** |
| question_validation | 2 | **21** |
| question_event | 3 | **41** |
| PENDING_REVIEW / APPROVED / **ACTIVE** | 2 / 0 / **0** | 21 / 0 / **0** |

---

## C · 数据完整性

```text
integrity_check ok · foreign_key_check 空 · 悬空引用 0 · 非法 lifecycle/event 0
题目删除 0 · 已有 2 道题未变 · 保护项哈希全部匹配
learning.db / contentpack / validator / 教材 PDF / 54 MP3 / P1-05~P1-06 产物  未修改
```

---

## D · 重复检测

```text
dedupe_key = sha256(section_id × activity_id × question_type × normalized_answer × block set)
```

| 比对 | 命中 | 是否拦截 |
| --- | --- | --- |
| 批次内部 | 0 | — |
| vs 现库 2 道题 | 0 | — |

有效性与不误杀的证据（侦察阶段反事实比对）：

- `S1-Q1 ≡ P1-05-G-Q2`、`S1-Q5 ≡ P1-05-F-Q2` → **能捕捉措辞不同的同题**；
- `S1-Q4` vs `P1-05-G-Q3`（同答案同 block、activity 不同）→ **未误判为重复**。

---

## E · 结论

**`P1-07_PASS`** —— 系统能够判断“哪些题可以进入正式题库、哪些必须拦下”，
且全程可追溯、不污染正式学习系统。

### 本轮发现的问题

| 类别 | 问题 | 处理 |
| --- | --- | --- |
| **证据组装** | P1-06 的 S2（Unit 1 UI）上下文**缺教材第 17 页正文块**（该页无 activity，被页归属逻辑漏掉） | 未改任何产物；入库判定改用 contentpack 完整正文作 D3 基准 |
| **设计** | `answer_support_type` 四值枚举无法表达“判断题布尔答案被事实验证” | 按 D2 豁免规则 4，编码为 `VERIFIABLE_REPHRASE`，真实依据写入 checks_json 与 note；**未改 schema** |
| validator 口径 | EXACT 陷阱触发器对选择题必然触发（19 题中 8 题 `needs_human_review=1`） | 已知口径，未改 validator |
| 数据 | S3-Q2/Q3 引用不含答案词、S4-Q4 题干残缺 | 已被 Gate 1 拦下，未入库 |

未发现入库机制问题：事务、生命周期、事件、硬约束、已有题保护均按设计工作。

---

## 产物

| 文件 | 说明 |
| --- | --- |
| `recon_report.md` · `recon_data.json` · `recon.py` | 侦察（上一轮，只读） |
| `build_candidates.py` → `candidate_decision.json` | 五道闸门逐题判定（只读） |
| `ingest.py` → `ingest_result.json` | 唯一写库步骤（单事务 + 写后核对） |
| `verify.py` → `verify_result.json` | 只读验收 |
| `build_audit.py` → `p1_07_audit.json` | A–E 汇总 |
| `p1_07_report.md` | 完整报告 |
