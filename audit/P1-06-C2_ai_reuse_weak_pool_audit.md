# P1-06-C2 AI 数据复用机制 + 错误/薄弱资源池 只读审计与设计冻结

- 结论：**PASS**
- 性质：**只读审计 + 设计冻结**（未修改任何文件、未写任何数据库、未新增代码或表字段）
- 前置：P1-06-C1 PASS（学习层最小业务服务已落地）

## 0. 本轮新增并正式确立的 AI 原则

> **AI 已经调用并产生、且仍然有价值的数据，必须优先复用；禁止因为页面重新进入、刷新、重复分析、重复学习、任务重建、入口变化等原因而无意义地再次调用 AI。**

**重要说明**：本任务明令禁止修改最高指导原则文档，因此该原则**本轮只在本审计报告中正式确立**，尚未写入
`docs/初中英语AI辅助学习系统最高指导原则与开发规范_V1.0.md`。
该文档目前只有部分相关条款（第八章“静态页面浏览不应无意义调用 AI，应优先使用缓存和规则”；第六章第 5 节“发音资源与语音能力原则”中的缓存/复用要求）。
→ 建议后续以**受控文档任务**把本原则正式追加到规范中（见第 15 节 P3-01）。

## 1. 扫描方法与范围（只读）

```text
范围        ：D:\ZhixueEnglish 全项目（排除教材 PDF / MP3 / __pycache__）
文本扫描     ：*.md / *.json / *.py / *.txt / *.kt / *.java / *.js / *.ts / *.toml / *.cfg / *.ini
关键词       ：ai_artifact / deepseek / openai / ollama / anthropic / gemini / llm / claude /
               api_key / bearer / chat/completions / embedding / tiktoken / transformers / torch /
               tensorflow / requests / urllib / http:// / https:// / fastapi / flask / gradio /
               streamlit / prompt / cache / 缓存 / 复用 / 重新生成
数据库扫描   ：contentpack v1–v5 的 ai_artifact；learning.db 是否含 AI 表
候选数据扫描 ：全部 *.json / *.jsonl；可能的 cache / tmp / log 文件
```

## 2. 当前项目到底有哪些历史 AI 数据？——实测结果：**0 条**

| 位置 | 检查项 | 实测结果 |
| --- | --- | --- |
| `contentpack/v1–v5` | `ai_artifact` 表 | 表存在（v1 起即建），**行数 = 0 / 0 / 0 / 0 / 0** |
| `learning.db` | AI 相关表 | **无**（6 张表：5 业务表 + schema_migration） |
| 项目 JSON/JSONL | 24 个文件 | 全部为解析/构建/审计报告，**无 AI 生成结果**（无 provider/model/prompt 输出字段的业务数据） |
| 代码 | AI 调用入口 | **0 个**（见第 4 节） |
| 缓存文件 | cache / tmp / log | 仅 `learning/__pycache__`、`parser/__pycache__`（Python 字节码，非 AI 数据） |

**扫描到的“疑似”命中及其真实性质**（已逐条核实，均非 AI 数据）：

| 命中 | 出现位置 | 真实性质 |
| --- | --- | --- |
| `ai_artifact` | builder / validator / 各审计报告 | **表名引用**（建表 DDL、计数校验、报告说明），非 AI 产出数据 |
| `prompt_version` | `builder/build_content_db_v01.py:946` | `ai_artifact` 建表的**列定义**，非调用 |
| `llm` ×8 | `parser/textbook_parser_v01.py` | 实为 `re.fullmatch` 的子串误命中（全部 8 处均为正则调用） |
| `urllib` / `http://` | `workbench/review_workbench_v01.py` | **本机只读预览服务**（`http://127.0.0.1:8765/`，stdlib `http.server` + 内存 LRU 缓存 ≤40 页），无外部请求、无 AI |
| `openai/deepseek/ollama/torch/...` | `learning/test_learning_service.py` | C1 测试中的**禁用词静态检查清单**（用于断言服务不含 AI 依赖） |
| `缓存/复用` | 各设计审计报告 / 最高规范 | 设计文字，非运行时数据 |

结论：**当前项目不存在任何已持久化的 AI 数据，也不存在 AI 调用入口**；不存在“隐藏的 AI 资产”。

## 3. AI 数据复用分类（A–E）

| 类别 | 定义 | 当前数量 | 说明 |
| --- | --- | --- | --- |
| **A. 可直接复用** | 同一教材资源、同一需求、版本匹配的有效 AI 结果 | **0** | 尚无任何 AI 数据 |
| **B. 可条件复用** | 需校验 textbook_id / snapshot_id / prompt_version / model / 数据完整性后才能复用 | **0** | 同上 |
| **C. 只能作为历史参考** | 旧教材版本 / 旧规则 / 旧 prompt 下的结果 | **0** | 同上 |
| **D. 不应复用** | 临时测试数据、错误数据、无法可靠对应的数据 | **0** | 同上（且项目内无此类文件） |
| **E. 尚未持久化、未来应考虑持久化的数据** | 未来 AI 产物的类型清单 | 设计清单 | 见下 |

**E 类（未来需持久化并建立复用能力）**：

```text
1. AI 解释（针对某条教材资源 / 某个错误）
2. AI 诊断（错因分析、薄弱点判断）
3. AI 提示（分步提示，供 hints_used 计数引用）
4. AI 建议（“可能值得复习”等——仅建议，不执行）
5. AI 生成练习（题目/变式，须经审核后才可展示）
6. AI 生成例句 / 对比句（锚定教材资源）
```

## 4. AI 调用入口审计与重复调用风险

**实测：项目当前 AI 调用入口 = 0 个。**

据此：

```text
【高风险重复 AI 调用】：0
【中风险重复 AI 调用】：0
【当前无风险】        ：全部（因为不存在任何 AI 调用路径）
```

**未来入口设计审计（针对 13 问，供实现前冻结）**：

| # | 问题 | 现状 | 未来必须满足的设计要求 |
| --- | --- | --- | --- |
| 1 | 什么情况下调用 AI？ | 无入口 | 仅在“无可用缓存 + 明确需要分析/生成 + 孩子触发”时 |
| 2 | 调用前是否检查已有结果？ | — | **必须先查缓存**（Level 0/1/2），否则禁止调用 |
| 3 | 是否存在缓存？ | 无 | 必须存在（以 AIArtifact 表 + 缓存键） |
| 4 | 缓存键是什么？ | — | `(artifact_kind, target_layer, target_id, textbook_id, snapshot_id, prompt_version, model)` |
| 5 | 是否与 item_id 关联？ | — | 必须（`target_layer='textbook_resource'` + `target_id=item_id`） |
| 6 | 是否与 textbook_id / snapshot_id 关联？ | — | 必须（教材版本变化须能判定失效） |
| 7 | prompt 变化后如何处理？ | — | `prompt_version` 不同即视为**新产物**；旧产物保留为历史参考（Level 3，不无痕覆盖） |
| 8 | 模型变化后如何处理？ | — | 同 prompt：`model` 不同 → 新产物；旧产物保留 |
| 9 | 页面刷新是否重复调用？ | 无风险 | 刷新只读缓存；**禁止**刷新触发调用 |
| 10 | 页面重新进入是否重复调用？ | 无风险 | 同上（进入页面只读缓存） |
| 11 | 同一资源重复学习是否重复调用？ | 无风险 | 默认复用；仅当结果不适用或孩子明确要求才重新生成 |
| 12 | 同一任务重复进入是否重复调用？ | 无风险 | 同上（Task 维度只做读取） |
| 13 | 是否存在“为了显示结果而调用 AI”？ | 无风险 | **显式禁止**：展示层只允许读缓存，不得触发生成 |

**结论**：当前无重复调用风险，因为不存在 AI 调用路径；风险将随 AI 入口引入而出现，必须在实现前把上面的 13 条作为硬性验收项。

## 5. 错误/薄弱资源池设计（不新增表）

### 5.1 数据来源（冻结）

```text
错误/薄弱池的来源 = 真实学习行为（LearningRecord）
不是：AI 判断、TaskItem 存在、页面浏览
历史错误永久留痕（LearningRecord append-only）
“当前是否仍需复习” = 由当前学习证据动态判断（可变化的当前状态）
```

**不得**把历史错误永久等同于当前错题；**不得**新增 `wrong_question` 表。

### 5.2 当前池资格规则（冻结，非算法）

```text
参与判断的记录 result ∈ {correct, incorrect, partial}   ← 决定当前池资格
不参与判断的记录 result ∈ {done, skipped, NULL}          ← 既不加入，也不清除

规则：
  1. 最近一条“参与判断”的记录为 incorrect 或 partial → **当前在池**
  2. 最近一条“参与判断”的记录为 correct              → **当前出池**
  3. 多次 incorrect → 保持在池（仅历史累加）
  4. skipped / NULL / done → **不清除已有池资格**（被忽略）
  5. correct 之后再次 incorrect → 重新入池
  6. 历史 LearningRecord 永远保留（与池状态无关）
```

### 5.3 与 B1.15 的一致性检查

| B1.15 冻结项 | 本设计 | 是否冲突 |
| --- | --- | --- |
| `evidence_count` 只计 correct/incorrect/partial/done | 本池不写该字段，仅查询 Record | 否 |
| `correct_count` 只计 correct（partial 不计） | 同上 | 否 |
| `last_result` / `last_practiced_at` 仅由参与判断的结果更新 | 本池读取该字段仅作辅助，判定以 Record 为准 | 否 |
| `review_needed` 不自动计算、AI 不得修改 | 本池**不写** `review_needed`；池是查询视图，不是字段 | 否 |
| Record append-only | 本池只读 Record | 否 |

**结论：本池与 B1.15 完全兼容，无需新增字段或表。**

### 5.4 池的读取方式（设计示例，本轮不执行）

```sql
-- 方式一：窗口函数（SQLite ≥ 3.25）
WITH judged AS (
  SELECT learner_id, item_id, result,
         ROW_NUMBER() OVER (PARTITION BY learner_id, item_id
                            ORDER BY created_at DESC, record_id DESC) AS rn
  FROM learning_record
  WHERE result IN ('correct','incorrect','partial')
)
SELECT learner_id, item_id, result AS last_judged_result
FROM judged
WHERE rn = 1 AND result IN ('incorrect','partial');
```

```sql
-- 方式二：无窗口函数（兼容写法，父查询取最近一条参与判断的记录）
SELECT r.learner_id, r.item_id, r.result
FROM learning_record r
WHERE r.result IN ('correct','incorrect','partial')
  AND NOT EXISTS (
        SELECT 1 FROM learning_record x
        WHERE x.learner_id = r.learner_id AND x.item_id = r.item_id
          AND x.result IN ('correct','incorrect','partial')
          AND (x.created_at > r.created_at
               OR (x.created_at = r.created_at AND x.record_id > r.record_id)))
  AND r.result IN ('incorrect','partial');
```

说明：第一阶段不建视图、不加索引（数据量小）；若未来需要，再受控评审（`learning_record(learner_id,item_id,created_at)` 索引已存在，可支撑该查询）。

## 6. AI 与错误/薄弱池的关系（冻结）

```text
孩子学习 → LearningRecord → 当前错误/薄弱状态 → 孩子查看/选择
        → （必要时）AI 分析 → AI 结果缓存/复用 → 孩子决定是否继续
        → 系统创建新的 Task / Record
```

| AI 可以 | AI 不可以 |
| --- | --- |
| 分析已有错误、解释为什么错 | 凭空制造错误 |
| 给出学习提示、复习建议 | 修改 LearningRecord / 历史事实 |
| 辅助孩子理解薄弱点 | 直接修改 MasteryState |
| 生成（经审核的）辅助练习 | 自动创建 Task / TaskItem / 自动安排学习 |

## 7. AI 复用优先级（冻结）

```text
Level 0：已有完全匹配且有效的 AI 数据                        → 直接复用（0 次调用）
Level 1：已有数据可经 item_id/textbook_id/snapshot_id/版本判定仍适用 → 复用（0 次调用）
Level 2：已有数据部分可复用，仅缺一部分                      → 只补缺失部分，禁止整包重新生成
Level 3：因教材版本 / 规则 / prompt / 模型实质变化而失效      → 才允许重新生成（旧数据保留）
Level 4：完全没有可用数据                                    → 才允许首次生成
Level 5：用户明确要求“重新分析/重新生成”                     → 才允许主动重新生成（保留旧数据关系，不无痕覆盖）
```

## 8. AI 数据身份设计（未来；本轮不改 schema）

每份 AI 数据必须能回答“它是针对什么产生的”：

| 维度 | 说明 | 现有 `ai_artifact` 列是否覆盖 |
| --- | --- | --- |
| `textbook_id` | 哪本教材 | ✅ 有 |
| `snapshot_id` | 哪次教材快照 | ✅ 有 |
| `target_layer` + `target_id` | 针对哪条教材资源 / 任务 / 记录 | ✅ 有（`textbook_resource` → item_id） |
| `artifact_kind` | 解释 / 诊断 / 提示 / 建议 / 练习 / 例句 | ✅ 有（需冻结枚举） |
| `prompt_version` | 提示词版本 | ✅ 有 |
| `model` | 模型标识 | ✅ 有 |
| `created_at` | 生成时间 | ⚠️ **无独立列**（本轮不改；建议未来评审，或由外部/文件名承载） |
| 数据版本 / 是否可复用 / 失效原因 | 复用决策元数据 | ❌ 无（建议未来评审，LATER） |
| `confidence` / `review_status` / `is_visible_to_child` | 质量与可见性 | ✅ 有 |
| `context_ref_ids` | 上下文引用（含 record_id 等） | ✅ 有 |

**缓存键（设计）**：`(artifact_kind, target_layer, target_id, textbook_id, snapshot_id, prompt_version, model)`
**复用判定**：键完全匹配且 `review_status` 允许 → Level 0；仅版本兼容 → Level 1；缺部分内容 → Level 2。

当前 `ai_artifact` = 0 行，暂无迁移与回填需求。

## 9. 教材冻结原则检查

```text
正确：教材资源 → AI 分析 → AI Artifact（side-channel）
禁止：教材资源 → AI 分析 → 修改教材资源
```

实测：项目无 AI 调用入口、无 AI 写入路径；C1 服务对 contentpack 仅 `mode=ro` 只读。
**未发现违反该原则的现有代码。**（如未来发现，只报告、不修改。）

## 10. 孩子做主检查

```text
禁止：AI 自动选择学科 / 自动创建 Task / TaskItem / 学习记录 / 自动安排复习 / 自动改变学习状态
允许：AI 建议 → 孩子确认 → 系统执行
```

实测：AI 调用入口 = 0；C1 服务所有写入均由显式业务调用触发（无自动创建逻辑）。
**该原则已写入本轮设计结论。**

## 11. C1 现状与兼容性

```text
C1 已提供：create_learner / get_learner / create_task / get_task / complete_task / drop_task /
          add_task_item / remove_task_item / list_task_items /
          record_learning_event / get_record / list_records / get_mastery
C1 未提供（有意）：update_record / delete_record / Mastery 算法 / Review 算法 / AI 入口
```

结论：**C1 与本轮设计完全兼容**——错误/薄弱池可由 `learning_record`（+ `mastery_state` 缓存）直接推导，无需改动 C1 服务与其数据库。

## 12. 最终报告必须回答的 14 个问题

| # | 问题 | 回答 |
| --- | --- | --- |
| 1 | C1 当前状态是否与本轮设计兼容？ | **兼容**（池为只读查询视图，C1 无需改动） |
| 2 | 当前项目到底有哪些历史 AI 数据？ | **0 条**（v1–v5 `ai_artifact` 全为 0 行；learning.db 无 AI 表；24 个 JSON 均为审计报告；无 AI 调用入口） |
| 3 | 哪些 AI 数据可以复用？ | 目前**无**（A/B 类均为 0） |
| 4 | 哪些数据不能复用？ | 目前**无** D 类数据；未来规则：教材版本/prompt/model 已失效 → 仅历史参考（C 类） |
| 5 | 当前有哪些 AI 重复调用风险？ | **当前无风险**（AI 入口 = 0）；未来风险清单见第 4 节 13 条 |
| 6 | AI 数据未来应该如何建立身份？ | `artifact_kind + target_layer/target_id + textbook_id + snapshot_id + prompt_version + model` 组成缓存键；建议未来评审 `created_at / data_version / reusable / invalid_reason` |
| 7 | 错误/薄弱池是否可完全由 LearningRecord + MasteryState 支撑？ | **可以**：以 LearningRecord 为唯一事实源推导；MasteryState 仅作缓存参考；无需新表/新字段 |
| 8 | 是否需要新增 `wrong_question` 表？ | **NO**（历史错误永久留在 LearningRecord；当前池是动态查询结果） |
| 9 | AI 与错误/薄弱池的边界是什么？ | AI 只能分析/解释/建议；不得制造错误、不得修改 Record/MasteryState、不得自动建 Task |
| 10 | 什么情况下允许 AI 新调用？ | Level 3（实质失效）/ Level 4（无数据）/ Level 5（用户明确要求） |
| 11 | 什么情况下必须复用？ | Level 0（完全匹配）/ Level 1（版本兼容）/ Level 2（仅补缺失，禁止整包重生成） |
| 12 | 页面刷新/重新进入/重复学习是否会重复调用？ | **当前不会**（无 AI 入口）；未来必须“只读缓存”，禁止刷新/进入/重复学习触发调用 |
| 13 | 当前是否存在 schema 需要立即修改的问题？ | **否**（`ai_artifact` 现有列已覆盖核心身份；`created_at`、复用元数据属 LATER 评审项） |
| 14 | 下一阶段最小实施范围是什么？ | 见第 14 节 |

## 13. 验收标准核对

| 验收项 | 结果 |
| --- | --- |
| 只读扫描完成 | ✅ 全项目文本 + 全部 SQLite |
| 未修改任何既有文件 | ✅ |
| learning.db SHA256 前后一致 | ✅ `16E3952D…14E9` |
| contentpack SHA256 前后一致 | ✅ `FF3FD568…452A` |
| AI / OCR / TTS / 网络 = 0 | ✅ 0/0/0/0 |
| 新增依赖 = 0 | ✅ |
| 未新增数据库表 / 字段 | ✅ |
| C1 服务源码未修改 | ✅ |
| 明确列出 AI 数据资产 | ✅（0 条，含“疑似命中”逐条澄清） |
| 明确判断可复用数据 | ✅（A/B = 0） |
| 明确指出重复调用风险 | ✅（当前 0；未来 13 条清单） |
| 形成“复用优先、缺失才生成”正式规则 | ✅（Level 0–5） |
| 明确错误/薄弱池与 AI 边界 | ✅ |
| 明确下一阶段实施边界 | ✅ |

## 14. 下一阶段最小实施范围（建议，不实施）

```text
C2-A（最小）：错误/薄弱池只读查询服务（无 AI）
  - 功能：list_weak_items(learner_id) → 依据第 5.2 节规则返回当前池
  - 约束：只读 learning_record；不写 review_needed、不建表、不改 schema

C2-B（可选，仍无 AI）：池的展示/导出（只读）

C3（未来）：AI 数据层最小实现（必须先满足第 4 节 13 条与 Level 0–5）
  - 先建立缓存键与查询，再接入任何模型
  - 任何 AI 产物一律写 ai_artifact（side-channel），永不写教材库与 learning.db 的教材字段

建议文档任务（与本轮并行的独立受控任务）：
  - 把“AI 复用优先原则”正式追加到最高指导原则文档（本轮因禁令未做）
```

## 15. 风险

```text
P0：0
P1：0
P2：1
    - 未来 AI 入口若未先实现缓存键与“先查缓存”流程，将出现高频重复调用（本次已在第 4 节冻结 13 条硬性要求）
P3：3
    - “AI 复用优先原则”尚未写入最高指导原则文档（本轮禁止修改文档）→ 建议受控文档任务追加
    - `ai_artifact` 缺少独立 created_at / data_version / reusable / invalid_reason 列（LATER 设计评审）
    - 项目存在 Python 字节码缓存目录（learning/__pycache__、parser/__pycache__），非 AI 数据、非源码
```

## 16. 实施边界确认

```text
learning.db ：未修改（SHA256 / 大小 / 表结构 / 行数均未变）
v5（及 v1–v4）：未修改
源码        ：未新增、未修改（含 C1 服务）
规范 / P1-04 / 既有审计报告：未修改
新增文件    ：仅本报告（md）+ JSON 摘要
AI = 0 ｜ OCR = 0 ｜ TTS = 0 ｜ 网络 = 0 ｜ 新依赖 = 0 ｜ 未新增表/字段 ｜ 未触碰 Android 与 D:\ZhixueAI
```
