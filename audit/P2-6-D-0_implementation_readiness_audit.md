# P2-6-D-0 实施前只读检查报告
## Learning Object + LO Evidence + LO Mastery + LO Diagnosis + Textbook-first Suggestion

> **AUDIT ONLY。** 本轮未修改任何 `.py / .json / .md / .docx`、数据库、教材、contentpack、音频、测试、Android；未新增业务代码与数据库结构；未调用 AI。
> 唯一产出：本报告与其 JSON 归档。

- 检查时间：2026-09-13 ｜ 项目：`D:\ZhixueEnglish`
- 最高约束：V1.2（`初中英语AI辅助学习系统_最高指导原则与开发规范_V1.2.docx` + `docs/…V1.2.md`）
- 输入基线：C-1 / C-2 / C-3 / C-4 / C-4-A（均只读引用）

---

## 1. 执行结论

**PASS WITH GAPS**

D 具备**最小、安全、可控**的实施条件：**零数据库迁移、零冻结服务修改、零 contentpack/V1.2/P2-4/P2-5/Android 修改、零 AI**；需在实施前确认 3 项**实现口径**（不阻塞，见 §9）。

## 2. 检查范围

只针对 D 的 MUST 范围：D-1 LO 映射、D-2 LO Evidence 聚合、D-3 两层去重、D-4 LO Mastery、D-5 LO Diagnosis、D-6 教材优先 Suggestion、D-7 Re-diagnosis，以及 Consolidation Action 的取舍与音频边界。

## 3. 基线核实（本轮实测）

| 项目 | 结果 |
| --- | --- |
| `learning.db` | SHA256 前 20 位 `DBAB743BF6D8F0A3832E`，mtime `2026-09-12 23:15:13` |
| 表 | **7 张**：learner / learning_record / learning_session / learning_task / mastery_state / schema_migration / task_item |
| 行数 | learner 1、learning_record 20、learning_session 31、learning_task 31、task_item 31、mastery_state 7、schema_migration 2 |
| integrity / FK | `ok` / `0` |
| contentpack | `ACEBC8C29CF5D11BAB50…`（未变） |
| V1.2 docx | `6D3595CF7D83879ADF3E…`（未变） |
| 冻结六服务 SHA（前 20） | learning_service `01341A05231EFCA6E0C8`、session_service `0CF7A20615780831F544`、activity_service `AAFF907C869797EE697D`、behavior_service `0C6EF4822F60D9251B68`、vocabulary_service `D06DCC76A5A4CCAF5C0B`、resource_pool_service `D4488E1FFBA6B553EB69` |
| 测试（只读运行） | learning 89 + workbench 50 + web 224 = **363 PASS / 0 FAIL / 0 SKIP**（与基线一致） |

## 4. D-1 LO 映射就绪性

| 检查项 | 结论 |
| --- | --- |
| 确定性键是否具备 | ✅ VOCAB/PHRASE/PATTERN（`lex|<textbook>|<kind>|<lexeme>|<pos>|<sense>`）、LISTENING（`listen|<textbook>|<unit>|<section>|<activity_no>`）、READING（`read|…|<page>`）、WRITING（`write|…|<activity_no>`） |
| 词条唯一性 | ✅ 288 词面 100% 唯一（无重名、无多 item_id） |
| 练习→词汇解析 | ✅ 1,512 条 `related_vocabulary` 引用 100% 唯一解析（0 未命中 / 0 歧义） |
| 映射覆盖率 | ✅ 89/157（56.7%）已可确定性归属；**68 条保持 `unmapped`** |
| 是否需要 AI | ❌ 不需要（纯教材事实 + 规则） |
| 是否需要新数据文件 | ❌ 不需要（可由教材事实运行时派生；如需缓存，可另出只读 JSON，非必需） |

**结论**：**YES — LO 映射可确定性实施**。

## 5. D-2/D-3 LO Evidence 聚合与去重就绪性

| 检查项 | 结论 |
| --- | --- |
| 现有有效证据规则 | ✅ 已实现（`evidence_service`：仅 correct/incorrect/partial；排除 done/skipped/NULL/contact-only/self-assessment-only） |
| provenance | ✅ 保留 `source_record_id` + `item_id` |
| 是否可派生到 LO | ✅ 可（LO 映射 + 分组聚合，无需改库） |
| 一证据多 LO | ✅ 支持（引用多 LO，不复制证据） |
| 两层去重 | ⚠️ 现为 item 级；**D 需实现 LO 级第二层**（`LO + 自然日 + task_type`） |
| 是否需要改 learning_record | ❌ 不需要 |

## 6. D-4/D-5 LO Mastery 与 Diagnosis 就绪性（重要发现：可零修改复用）

**现有 P2-6-B 服务已具备"接收任意证据集合"的能力**，因此可用 **LO id + LO 级聚合证据** 直接复用，**无需修改任何文件**：

```
mastery_service.evaluate(conn, learner_id, lo_id, rules, evidence=lo_evidence)   → LO 掌握状态
diagnosis_service.diagnose(conn, learner_id, lo_id, rules, evidence=lo_evidence) → LO 诊断
intervention_service.suggest(conn, learner_id, representative_item_id, rules)     → 教材优先建议
```

| 检查项 | 结论 |
| --- | --- |
| 五项稳定条件 | ✅ 规则文件 `mastery_rules_v1.json` 已冻结，**不改阈值** |
| LO 级可获得五项条件 | ✅ 证据集合按 LO 聚合后直接套用 |
| Diagnosis 规则 | ✅ current_error（最新有效 incorrect）/ suspected_weak（≥2 错误或跨 ≥2 类型）/ needs_textbook_review（≥2 partial 且跨 ≥2 类型）均可复用 |
| 是否需改 frozen | ❌ 不需要（复用 `evidence_service` / `mastery_service` / `diagnosis_service` / `intervention_service`，四者均非冻结） |
| 单次错误/单次正确 | ✅ 不会直接判薄弱/掌握（规则已保证） |
| Audio 播放 | ✅ 不产生 Evidence（现有实现无此路径） |

## 7. D-6 教材优先 Suggestion 就绪性

| 检查项 | 结论 |
| --- | --- |
| 六类建议 | ✅ 已实现（`intervention_service`，顺序与 V1.2 一致） |
| 教材定位 | ✅ 已实现（词表页 p150 / 官方音频 / 语法指针页 / 范文 / 原题链接 / 跨 Section 列表） |
| 缺定位时 | ✅ 返回 `requires_resource_mapping` + `missing`，不伪造 |
| 是否自动执行/跳转/播放 | ❌ 全部否（仅链接，需孩子点击） |
| AI 兜底 | ❌ 无（`ai_assist = not_implemented`） |

## 8. D-7 Re-diagnosis 与 Consolidation Action

| 检查项 | 结论 |
| --- | --- |
| 新证据能否进入 LO 聚合 | ✅ 能（读时重新聚合） |
| 重新诊断是否读时计算 | ✅ 是（无需事件/异步/持久化） |
| 是否需持久化 diagnosis / suggestion | ❌ 不需要（派生层） |
| **Consolidation Action 是否必须在 D 实现** | ❌ **不必须 → DEFERRED** |
| 不实现 Action，闭环是否成立 | ✅ 成立（新证据自会到达并触发读时再诊断） |
| Action attribution 是否阻塞 | ❌ 不阻塞（仅"区分未处理/已尝试"与展示需要它） |

## 9. 需在 D 实施前确认的 3 项口径（**非阻塞**，来自本轮新发现）

| 编号 | 口径 | 说明 | 处置 |
| --- | --- | --- | --- |
| **N-1** | LO 诊断不携带 item 级池事实 | `diagnosis_service.diagnose()` 内部调用 `pool.get_item_pool_status(conn, learner, item_id)`；传 LO id 会查不到 → `pool_state=None`（非错误） | D 明确：LO 诊断的 `pool_state` 允许为空；如需展示 item 级池事实，由调用方按代表 item 附加 |
| **N-2** | 复用 `mastery_service.evaluate(item_id=…)` 时参数语义变为 LO id | 若直接把 LO id 塞进 `item_id` 参数，会产生"字段名与语义不符"的漂移风险 | D 在返回结构中显式加入 `object_type: "learning_object"`，或在新服务内做包装，避免对外暴露歧义 |
| **N-3** | `learning_record` 无 `session_id` | 现有两层去重（日 + 类型）不需要会话；但将来若要做 Action 归因，需经 `task_id → learning_session` 间接关联 | 记录为已知约束；D 不依赖会话级去重 |

## 10. 文件级实施计划（**只规划，不实施**）

### 新增文件（必须）

| 文件 | 为什么必须 | 改什么 | 为什么不扩大 |
| --- | --- | --- | --- |
| `learning/learning_object_service.py` | D-1/D-2/D-3 的唯一落点：LO 键、item→LO 映射、LO 证据聚合与两层去重、LO mastery/diagnosis 包装、LO 建议入口 | 只读派生（SELECT + 读 structured JSON） | 单一职责；不新增表、不写库、不改冻结层 |
| `learning/test_p2_6d_learning_object.py` | D 的验收测试（约 16 项，见 §11） | 只读测试 + 临时库副本 | 不写正式库 |

### 修改文件（最小）

| 文件 | 为什么必须改 | 改什么 | 为什么不扩大 |
| --- | --- | --- | --- |
| `web/flow.py` | 让 LO 级"需要再学"分组与建议可被页面读取 | 新增 1 个只读函数（LO 分组 + 建议） | 仅新增函数，不改既有函数行为 |
| `web/ui.py`（可选） | 展示 LO 分组与"掌握较稳定"文案 | 在 `/review` 现有卡片内追加 1 个区块 | 不新增路由、不改导航、不加分数/等级 |

### 明确 NO CHANGE REQUIRED

```
learning/learning_service.py            NO CHANGE REQUIRED
learning/session_service.py             NO CHANGE REQUIRED
learning/activity_service.py            NO CHANGE REQUIRED
learning/behavior_service.py            NO CHANGE REQUIRED
learning/vocabulary_service.py          NO CHANGE REQUIRED
learning/resource_pool_service.py       NO CHANGE REQUIRED
learning/evidence_service.py            NO CHANGE REQUIRED（复用）
learning/mastery_service.py             NO CHANGE REQUIRED（复用）
learning/diagnosis_service.py           NO CHANGE REQUIRED（复用）
learning/intervention_service.py        NO CHANGE REQUIRED（复用）
structured/learning/mastery_rules_v1.json  NO CHANGE REQUIRED（阈值冻结）
structured/learning/learning.db          NO CHANGE REQUIRED（无迁移）
contentpack / P2-4 / P2-5 / V1.2 / Android / 教材 / 音频   NO CHANGE REQUIRED
```

### 影响面汇总

| 维度 | 结论 |
| --- | --- |
| 数据库影响 | **0**（无迁移、无新表、无新字段） |
| AI 影响 | **0**（D 不实现 AI） |
| 教材影响 | **0**（只读 contentpack/P2-4 产物） |
| 音频影响 | **0**（不切分、不派生、不修改） |
| Android 影响 | **0** |
| 测试影响 | 新增约 **16** 项；现有 363 项必须保持通过 |

## 11. 需新增的测试（规划，约 16 项）

1. LO 键确定性（同输入同输出，跨进程一致）；2. 词面唯一性断言（288/288）；3. VOCAB→LO 映射确定性；4. LISTENING/READING/WRITING→LO 映射确定性；5. Exercise→LO 映射确定性（含 `unmapped` 明确标记）；6. `unmapped` 不参与 LO 判定；7. 一证据多 LO 不复制证据；8. item 级去重（同日同题同类型=1）；9. LO 级去重（同日同 LO 同类型换题仍=1）；10. 跨自然日独立；11. 跨 task_type 独立；12. done/skipped/self-assessment-only 不计证据（LO 层复核）；13. LO mastery 五项条件（缺一不判 stable）；14. LO diagnosis 单次错误不判薄弱；15. LO 建议教材优先且不自动执行；16. 只读保证（调用后 learning.db SHA/mtime 不变）+ AI=0。

## 12. 21 个必答问题

| # | 问题 | 结论 |
| --- | --- | --- |
| 1 | D 是否可以开始 | **YES WITH GAP**（无阻塞；先确认 §9 的 3 项口径） |
| 2 | 是否需要数据库迁移 | **NO** |
| 3 | 是否需要修改 frozen learning services | **NO** |
| 4 | 是否需要修改 contentpack | **NO** |
| 5 | 是否需要修改 V1.2 | **NO** |
| 6 | 是否需要修改 P2-4/P2-5 | **NO** |
| 7 | 是否需要修改 Android | **NO** |
| 8 | LO mapping 是否可确定性实现 | **YES** |
| 9 | 68/157 unmapped 是否阻塞 | **NO**（保持显式状态并如实报告覆盖率） |
| 10 | Audio mapping 是否阻塞 | **NO**（C-4-A：0 错配） |
| 11 | Grammar LO 是否阻塞 | **NO**（DEFERRED） |
| 12 | LO Evidence 是否可只读派生 | **YES** |
| 13 | LO Mastery 是否可只读派生 | **YES**（零修改复用） |
| 14 | LO Diagnosis 是否可只读派生 | **YES**（零修改复用；`pool_state` 可为空） |
| 15 | Suggestion 是否可只读派生 | **YES** |
| 16 | Re-diagnosis 是否可以成立 | **YES**（读时派生） |
| 17 | Consolidation Action 是否必须在 D 实现 | **NO → DEFERRED** |
| 18 | 最小新增文件 | `learning/learning_object_service.py`、`learning/test_p2_6d_learning_object.py` |
| 19 | 最小修改文件 | `web/flow.py`（+1 函数）；`web/ui.py`（可选展示） |
| 20 | 需要新增多少测试 | **约 16 项** |
| 21 | 是否存在 C-4/C-4-A 未发现的新阻塞项 | **NO**（新增 3 项实现口径 N-1/N-2/N-3，均非阻塞） |

## 13. 保护基线（本轮实测，全部为 0）

```
代码修改：0 ｜ 数据库修改：0 ｜ contentpack 修改：0 ｜ 教材修改：0 ｜ 音频修改：0
V1.2 修改：0 ｜ P2-4 修改：0 ｜ P2-5 修改：0 ｜ Android 修改：0
AI 调用：0 ｜ 新增业务代码：0 ｜ 新增数据库结构：0

learning.db : DBAB743BF6D8F0A3832E599CBD5DD2267F008FD9FB3903BACEA93780A466D633（mtime 2026-09-12 23:15:13）
contentpack : ACEBC8C29CF5D11BAB50BF7962FBEE5DE42CD9CFC7FE48AB6316699D265E1A3F
V1.2 docx   : 6D3595CF7D83879ADF3E6452C5E5A74C5300E89265DE1B4F2FA8A1EBDBB861A9
测试        : learning 89 / workbench 50 / web 224 = 363 PASS / 0 FAIL / 0 SKIP
新增文件    : 仅 P2-6-D-0 两个 audit 文件
```

## 14. 最终判定

**PASS WITH GAPS**

- **无阻塞项**（21 问中 2/3/4/5/6/7/9/10/11/17/21 均为 NO 或 DEFERRED；模型/数据/代码/安全四类均无红线）。
- **可延期 GAP**：68/157 练习保持 `unmapped`、Grammar LO 暂缓、Consolidation Action DEFERRED、12 条音频文字侧关联缺口（G-Audio-1）、无转写（G-Audio-2）。
- **D 实施前置**：确认 N-1/N-2/N-3 三项口径（`pool_state` 允许为空、LO id 与 item_id 语义区分、不依赖会话级去重）。

**完成本检查后立即停止：不进入 D 实施、不修改代码、不建表、不修复任何问题、不修改 UI/Android、不切音频。**
