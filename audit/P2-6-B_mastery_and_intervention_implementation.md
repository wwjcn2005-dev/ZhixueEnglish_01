# P2-6-B 掌握判定与“诊断 → 巩固”最小实施 —— 归档报告

> 归档时间：2026-09-13 ｜ 上游：P2-6-A 只读审计（PASS WITH GAPS）｜ 规范依据：最高指导原则与开发规范 **V1.2**
> 结论：**PASS** ｜ 测试：**363 PASS / 0 FAIL / 0 SKIP**（原有 332 全部保持 + 新增 31）

---

## 1. 实施结论

按 V1.2 实现最小闭环：`学习事实 → 有效证据 → 掌握判定 → 诊断 → 教材优先巩固建议 → 孩子主动选择`。
V1.2 未被修改，数据库 **schema 0 迁移**，正式教材数据未修改，AI 调用 **0**，正式学习数据未产生任何新记录。

---

## 2. 修改文件清单（含 SHA256 前 16 位）

| 文件 | 类型 | 大小 | SHA256(16) | 原因 |
| --- | --- | --- | --- | --- |
| `structured/learning/mastery_rules_v1.json` | 新增 | 2,652 | `E7EC99DB55DDCF04` | 机器可读工程参数 |
| `learning/evidence_service.py` | 新增 | 7,562 | `864536DEF937E4B3` | 有效证据 + 去重 |
| `learning/mastery_service.py` | 新增 | 5,750 | `8F7372A07E905EF4` | 五项条件的掌握判定 |
| `learning/diagnosis_service.py` | 新增 | 4,608 | `14CD114724982C7D` | 分层诊断 |
| `learning/intervention_service.py` | 新增 | 9,802 | `4E12CB1AAF429C81` | 教材优先建议 |
| `learning/test_p2_6b_mastery_diagnosis.py` | 新增 | 17,331 | `5AAA906ED6D80D0B` | 31 项专项测试 |
| `web/flow.py` | 修改 | 15,854 | `0534A2315299B738` | 建议编排（只读）+ 教材定位文案 |
| `web/app.py` | 修改 | 34,640 | `65261339A77534DD` | `/review` 传入建议 |
| `web/ui.py` | 修改 | 48,582 | `2FCF2FDE71D6DDB3` | `/review` 建议卡片 + 措辞修正 |
| `workbench/vocabulary_learning_v01.py` | 修改 | 51,758 | `2A0C73861BB1B705` | §十九 措辞：“学习证据 N 次（不代表掌握）” |
| `workbench/test_vocabulary_learning_v01.py` | 修改 | 71,397 | `EDDF14B86C39B58F` | 同步该措辞断言（任务书强制要求） |
| `web/test_p2_5c_spec_sync.py` | 修改 | 10,238 | `37782740174BE406` | 基线调整：P2-5 六份 JSON 必须仍在（允许授权新增） |

**未修改**：六个冻结学习服务（`learning_service` / `session_service` / `activity_service` / `behavior_service` / `vocabulary_service` / `resource_pool_service`）、`learning.db`（schema + 数据）、contentpack、P2-4/P2-5 成果、规范 V1.2、Android。

---

## 3. 各 service 职责

| Service | 职责 | 只读边界 |
| --- | --- | --- |
| `evidence_service` | LearningRecord → 有效判断证据；排除 `done/skipped/NULL`、仅接触（study）、仅自评；按 `(learner,item,自然日,task_type)` 去重（保留最新，其余入 `deduped_from`）；派生规范化 `task_type` | 仅 SELECT |
| `mastery_service` | 五项条件判定，输出 `not_started / learning / needs_review / stable` + 条件明细 + 证据 id；`display_text()` 保证文案合规 | 仅 SELECT |
| `diagnosis_service` | `current_error → suspected_weak → needs_textbook_review`；结论带 `evidence_ids`；另暴露冻结池事实 `pool_state` | 仅 SELECT |
| `intervention_service` | 按 V1.2 顺序给教材优先建议；缺定位返回 `requires_resource_mapping`；`action=child_click`、`auto_execute=false` | 仅 SELECT |

---

## 4. mastery_rules_v1.json 参数（工程初始参数，可验证、可调整）

```json
"stable": {
  "minimum_valid_evidence": 3,
  "minimum_task_types": 2,
  "minimum_natural_days": 2,
  "recent_attempt_window": 3,
  "recent_correct_minimum": 2,
  "require_no_unresolved_current_error": true
}
```

另有：`evidence.counted_results=[correct,incorrect,partial]`、`excluded_results=[done,skipped,null]`、
`dedupe_key=[learner_id,item_id,evidence_date,task_type]`、`dedupe_keep=latest`、
`self_assessment_alone_cannot_raise=true`；`diagnosis.suspected_weak={minimum_errors:2, or_error_task_types:2}`、
`diagnosis.textbook_review={minimum_partial_evidence:2, minimum_task_types:2}`；
`intervention.textbook_first_order=[reread_text, replay_audio, grammar_pointer, model_text_review, redo_exercise, cross_section_practice]`、`ai_assist=not_implemented`。
服务从 JSON 读取阈值，**不写死在 Python**（测试断言 `rules["stable"]`）。

---

## 5. 有效证据规则（实测）

| 情形 | 结果 | reason |
| --- | --- | --- |
| `done` / `skipped` / NULL | 不计证据 | `result_not_judged` |
| `study`（仅接触） | 不计证据 | `contact_only` |
| 仅自评（`self_check` 且无 q*/m* 作答） | 不计证据 | `self_assessment_only` |
| `correct` / `incorrect` / `partial` | 有效证据 | `judged_result` |
| 无法判断 | 标记不可判定，不强行计入 | `not_evaluable` |

---

## 6. 去重规则（实测）

同一 `(learner, item, 自然日, task_type)` 最多 1 条独立证据（保留最新）。
真实数据验证：词汇项 `V:C128262B65A0` 单日 8 条记录 → **1 条独立证据**（`suppressed_count=7`）；全库 3 组“同日同任务重复”全部合并。

---

## 7. 掌握判定结果（正式库现况）

7 个学习对象：`not_started 6 / learning 1`，**stable = 0**（验收 I 达成）。
原因：全部记录集中在 2026-09-12 单一自然日、有效证据最多 1 条；UI 文案样例 `学习证据 1 次（不代表掌握）`。

## 8. 诊断结果

正式库当前 `list_attention()` 为空（唯一 partial 来自仅自评提交，按 V1.2 不计为判断证据）。
测试内验证：单次错误 → `current_error`（不升级为薄弱）；2 次错误且跨任务类型 → `suspected_weak`；结论可追溯 `evidence_ids`。

## 9. 巩固建议结果（正式库现况）

Starter 练习项（`X:1C4143922B1C`）建议链：`reread_text`（教材第 5 页 · 练习 10）→ `replay_audio`（官方录音 AU03 🎧）→ `redo_exercise`（`/exercise/478514a69c05`）→ `cross_section_practice`（`/unit/starter/exercises`）；`missing=[]`，无伪造定位。

## 10. Web 最小接线

`/review` 在原有分组下新增“教材建议”卡片：建议类型 + 教材定位文本 + 可选链接（`去看看`），附“要不要做、先做哪一个，都由你自己决定”；无定位时说明“暂时定位不到教材位置，不提供跳转”。
无自动跳转 / 自动播放 / 自动进入练习；首页计数与既有路由行为不变。

---

## 11. 测试结果

| 套件 | 原有 | 新增 | 合计 | FAIL | SKIP |
| --- | --- | --- | --- | --- | --- |
| learning | 58 | 31 | **89** | 0 | 0 |
| workbench | 50 | 0 | **50** | 0 | 0 |
| web | 224 | 0 | **224** | 0 | 0 |
| **总计** | **332** | **31** | **363** | **0** | **0** |

新增测试覆盖任务书 §二十一 全部条目：Evidence 1–9、Mastery 10–19、Diagnosis 20–22、Intervention 23–26，另加 5 项安全测试（正式库/contentpack/规范哈希、schema 无迁移、参数外置）。全部使用临时库副本。

## 12. 正式数据库保护结果

`learning.db` SHA `DBAB743BF6D8F0A3832E599CBD5DD226…`、mtime 2026-09-12 23:15（测试前后一致）；schema 仍 **7 张表**；无新表/新字段；未产生新记录；未删除或清理历史（含验收测试数据，读取时判为不可判定）。

## 13. AI 调用次数

**0**。无新增网络/AI 调用点（测试断言源码不含 openai/deepseek/requests/urllib/socket）。

## 14. V1.2 保护结果

规范 V1.2 未修改（docx SHA `6D3595CF7D83879ADF3E6452C5E5A74C…`）；contentpack 未修改（`ACEBC8C29CF5D11BAB50BF7962FBEE5D…`）；未产生 V1.3。

## 15. 原有 332 测试是否全部保持 PASS

**是**。过程中两处断言因本任务强制要求而同步：workbench “掌握状态”措辞（§十九 明确要求）与 P2-5-C “6 份设计 JSON 计数”（改为“六份必须仍在”）。均为任务书要求的语义修正，非放宽标准。

## 16. 未解决问题

1. **同一学习对象跨任务类型证据难以自然形成**：词汇对象当前仅 `recall` 可构成有效证据，练习对象 `question_type` 固定；需要 `item_id → LearningObject` 映射才能让“≥2 种任务类型”常态可达。当前按 V1.2 原样判定，未擅自改规范。
2. **“未处理当前错误”暂无处理动作机制**（现以“最近一条有效判断为 incorrect”表达）。
3. 诊断阈值（错误 ≥2、partial ≥2 且跨任务）为工程初始参数，待真实数据校准。
4. 冻结池（当前错误/当前薄弱）与新诊断层并存，长期是否统一为一个只读视图待评审。

## 17. 下一阶段建议

①学习对象映射（item_id → LearningObject）；②“巩固动作记录”（孩子点击后产生），使“未处理当前错误”有闭合方式；③用真实使用数据校准 `mastery_rules_v1.json`；④再讨论冻结池与诊断层是否合并。**仍不加 AI、不加自动推进。**

---

**归档说明**：本文件与 `P2-6-B_mastery_and_intervention_implementation.json` 为 P2-6-B 的正式归档；P2-6-B 完成后停止，未进入 P2-6-C。
