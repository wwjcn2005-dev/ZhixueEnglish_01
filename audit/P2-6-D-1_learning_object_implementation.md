# P2-6-D-1 实施报告
## Learning Object + LO Evidence + LO Mastery + LO Diagnosis + Textbook-first Suggestion

> 只读派生业务层实施。未修改任何既有文件；未建表；未迁移数据库；未调用 AI。
> 归档：本文件 + `P2-6-D-1_learning_object_implementation.json`

- 实施时间：2026-09-13 ｜ 项目：`D:\ZhixueEnglish`
- 依据：V1.2 + C-1/C-2/C-3/C-4/C-4-A/D-0（均已冻结）

---

## 1. 实施结论

**PASS**

只读派生链已跑通：`教材事实 → Learning Object → LO Evidence → LO Mastery → LO Diagnosis → 教材优先建议`；**未污染任何冻结层**（数据库、contentpack、教材、音频、V1.2、P2-4/P2-5、Android、六个冻结服务、P2-6-B 四个服务均未改动）。

## 2. 实际新增 / 修改文件

| 类型 | 文件 |
| --- | --- |
| **新增** | `learning/learning_object_service.py`（只读派生业务层） |
| **新增** | `learning/test_p2_6d_learning_object.py`（23 项测试） |
| **修改** | **无** |
| **明确未改** | `web/ui.py`、`web/flow.py`、六个冻结服务、P2-6-B 四服务、`mastery_rules_v1.json`、`learning.db`、contentpack、P2-4、P2-5、V1.2、Android、教材、54 个 MP3 |

## 3. Learning Object 数量与映射结果（实测）

| 项目 | 数值 |
| --- | --- |
| 词条类 LO | **363**（VOCAB 288 + PHRASE 23 + PATTERN 52） |
| 练习派生 LO（去重后） | **106**（LISTENING / READING / WRITING） |
| **LO 总数（去重）** | **416** |
| Grammar LO | **DEFERRED**（不产出伪 LO） |
| Exercise 映射 | **mapped 89 / unmapped 68**（coverage 0.5669） |
| 规则分布 | R1 21 ／ R2 7 ／ R3 37 ／ R4 12 ／ R5 12 ／ unmapped 68 |

`unmapped` 保持显式（`lo_ids=[]`、`rule=None`），覆盖率仅用于诚实报告，未做任何强行归属。

## 4. LO Evidence 聚合与去重（实测）

- 复用 `evidence_service`（未修改）：有效证据仅 `correct / incorrect / partial`；排除 `done / skipped / NULL / contact-only / self-assessment-only`。
- **新增第二层去重**：`learner + LO + 自然日 + task_type` 只计 1 条独立证据；同日同类型**换题不增值**，但**全部来源 item/record 保留在 `sources[]`**（一条证据 + 多 LO 引用，不复制证据）。
- 跨自然日 → 独立；跨 task_type → 独立（测试已验证 `recall` 与 `match` 同日各计 1 条）。
- Provenance 字段：`learner_id / item_id / source_record_id / task_type / evidence_date / result / sources[]`。

**正式库结果**：1 个 LO 有证据（`LO:…:VOCAB:9CA0EA2C7E70`，证据 1 条，类型 `recall`，自然日 1 天，去重压缩 0）。其余 LO 暂无证据（真实数据仅 1 个自然日）。

## 5. LO Mastery / LO Diagnosis 结果

- **Mastery**：复用 `mastery_service`（未修改），阈值来自 `mastery_rules_v1.json`（未修改）；返回 `object_type = "learning_object"`；`mastery_state`（frozen item 级缓存）**未被触碰**，LO mastery 为读时派生。
- 实测：上述 LO 状态 `learning`，显示文案 `学习证据 1 次（不代表掌握）`；未满足条件为 `minimum_valid_evidence / minimum_task_types / minimum_natural_days / recent_correct_minimum`——**未出现任何 stable**（符合"单次正确不等于掌握"）。
- **Diagnosis**：复用 `diagnosis_service`（未修改）；规则不变（current_error / suspected_weak（≥2 错误或跨 ≥2 类型）/ needs_textbook_review（≥2 partial 且跨 ≥2 类型））；`pool_state` 允许为 `None`（D-0 N-1），不伪造 item 池信息；`evidence_ids` 保留 provenance。
- 实测：正式库当前 `attention = 0`（无 current_error / suspected_weak / needs_textbook_review）。

## 6. Textbook-first Suggestion 结果

- 复用 `intervention_service`（未修改），六类顺序固定：`reread_text → replay_audio → grammar_pointer → model_text_review → redo_exercise → cross_section_practice`。
- 每条建议：`action = "child_click"`、`auto_execute = false`；不自动跳转/播放/开始/推进；无 AI 兜底。
- 测试用构造证据验证：建议顺序严格按 V1.2 顺序，且必须由孩子点击。

## 7. Re-diagnosis（读时派生）

`LearningRecord → Evidence → LO Evidence → LO Mastery → LO Diagnosis → Suggestion` 全部在**读取时重新计算**；新增证据后再次读取即得到新结果。**Diagnosis / Suggestion 不持久化**；**Consolidation Action = DEFERRED**（无 action 表、无 attribution）。

## 8. 测试结果

| 套件 | 数量 | 结果 |
| --- | --- | --- |
| **新增 D-1 测试** | **23** | PASS / 0 FAIL |
| learning（含新增） | 112 | PASS / 0 FAIL |
| workbench | 50 | PASS / 0 FAIL |
| web | 224 | PASS / 0 FAIL |
| **总计** | **386** | **PASS / 0 FAIL / 0 SKIP** |

原有 **363 项全部继续 PASS**；未修改任何既有测试以迎合新实现（新增测试覆盖任务书 §二十三 的 20 项要求：LO ID 确定性、288 词条稳定 LO、exercise 映射确定性、mapped/unmapped、无伪 LO、Listening LO 任务级、音频不产生证据、多 LO 不复制证据、第二层去重、跨日/跨类型独立、Mastery 复用规则、单次错误不判薄弱、provenance、建议顺序、`object_type`、`pool_state=None` 合法、不写库、AI=0）。

## 9. 保护基线（实施后复核）

```
learning.db   DBAB743BF6D8F0A3832E…（SHA16 DBAB743BF6D8F0A3；mtime 2026-09-12 23:15:13 未变；7 表；integrity ok / FK 0）
contentpack   ACEBC8C29CF5D11BAB50…（未变）
V1.2 docx     6D3595CF7D83879ADF3E…（未变）
mastery_rules E7EC99DB55DDCF04BA7C…（未变）
冻结六服务    learning_service 01341A05… / session 0CF7A206… / activity AAFF907C… /
              behavior 0C6EF482… / vocabulary D06DCC76… / resource_pool D4488E1F…（与 D-0 基线一致）
P2-6-B 四服务 evidence 864536DE… / mastery 8F7372A0… / diagnosis 14CD1147… / intervention 4E12CB1A…（未变）

DB migration = 0 ｜ DML = 0 ｜ 教材修改 = 0 ｜ 音频修改 = 0（54 MP3 未触碰）
Android 修改 = 0 ｜ P2-4 修改 = 0 ｜ P2-5 修改 = 0 ｜ web/ui.py 与 web/flow.py 未改
AI 调用 = 0（源码不含任何外部 AI/网络调用）
```

## 10. 未解决问题（保持 DEFERRED，不在本阶段处理）

1. 68/157 unmapped 练习（显式保留，如实报告覆盖率）；
2. Grammar LO（等待教材语法对象数据）；
3. Consolidation Action 持久化与 attribution（DEFERRED）；
4. G-Audio-1（12 条音频文字侧关联缺口）、G-Audio-2（无转写，无法声学确认）；
5. Web UI 接入（`web/ui.py` 本阶段明确不改）；
6. LO 级 mastery 是否持久化（当前为读时派生）。

## 11. 停止声明

D-1 完成即停止：**未修改 `web/ui.py`、未改 Android、未建 Action 表、未实现 Grammar LO、未修复 unmapped、未切音频、未做 AI、未做 UI 重构**。下一阶段等待新任务指令。
