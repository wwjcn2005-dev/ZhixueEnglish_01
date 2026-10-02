# P1-06-C1 学习层最小业务服务实施报告

- 结论：**P1-06-C1 PASS**
- 性质：**实施任务**（新增最小业务服务 + 最小自动化测试；未修改 Schema、未修改教材库、未写正式学习数据）
- 基线：

```text
learning.db : 16E3952D64E749879D8FF78814F0434D544D4CBAD7D52AAC7E0B145DE43414E9 ｜ 73,728 bytes
              user_version=1 ｜ 6 表 ｜ 5 FK ｜ 6 索引 ｜ 业务表 0 行 ｜ integrity=ok ｜ fk=0
v5          : FF3FD568F4DA5348DB1F9DE7D68818CBEFD6A7E36A67C68EEF7F8386F4CE452A ｜ 2,457,600 bytes
              21 表 ｜ 362 教材资源 ｜ source_ref 815 ｜ integrity=ok
```

实施后复核：两者**均未改变**（见第 7、8 节）。

## 1. 修改 / 新增的文件

| 文件 | 类型 | 说明 |
| --- | --- | --- |
| `learning/learning_service.py` | **新增** | 学习层最小业务服务（Learner / Task / TaskItem / Record+Mastery） |
| `learning/test_learning_service.py` | **新增** | 最小自动化测试（stdlib `unittest`，覆盖 A–M） |
| `audit/P1-06-C1_learning_service_implementation.md` | **新增** | 本报告 |
| `audit/P1-06-C1_learning_service_implementation.json` | **新增** | 机器可读摘要 |

**未修改任何既有文件**（parser / builder / workbench / contentpack / learning.db / 规范 / 既有报告 全部未动）。

## 2. 每个文件为什么新增

- `learning_service.py`：B1.9–B1.15 已冻结设计，但项目**没有**任何 service / repository / 数据访问层（现存 Python 均为 parser / builder / workbench 脚本），因此必须新增**最小**服务层，把冻结规则变成可复用、可测试的代码。未另起框架、未引入 ORM。
- `test_learning_service.py`：项目**没有**测试框架；按“不引入新依赖”的要求，使用 Python 标准库 `unittest`，并强制使用**临时测试数据库**（正式库副本），保证正式 learning.db 不被污染。

## 3. 实现的接口

```text
连接
  connect_learning_db(path=DEFAULT_LEARNING_DB)        # 显式事务；PRAGMA foreign_keys=ON
  connect_contentpack_db(path=DEFAULT_CONTENTPACK_DB)  # 教材库只读（mode=ro）

Learner
  create_learner(conn, display_name, learner_id=None, created_at=None)
  get_learner(conn, learner_id)

LearningTask
  create_task(conn, learner_id, task_kind, item_ids, textbook_id,
              goal_id=None, title=None, task_id=None, created_at=None)
  get_task(conn, task_id)
  complete_task(conn, task_id, completed_at=None)
  drop_task(conn, task_id, completed_at=None)

TaskItem
  add_task_item(conn, task_id, item_id, ordinal=None, created_at=None)
  remove_task_item(conn, task_id, item_id) -> 删除行数
  list_task_items(conn, task_id)

LearningRecord + MasteryState（核心）
  record_learning_event(conn, learner_id, task_id, item_id, activity_type,
                        result=None, response_raw=None, hints_used=0,
                        snapshot_id=None, created_at=None)
  get_record(conn, record_id)
  list_records(conn, learner_id=None, task_id=None, item_id=None)
  get_mastery(conn, learner_id, item_id)

异常
  LearningServiceError / ValidationError / NotFoundError / ConflictError
```

**未提供**（按 append-only 与边界要求）：`update_record` / `delete_record` / 任何 Mastery 算法入口 / 任何 AI 入口。

## 4. 已落地的业务规则

| 来源 | 规则 | 落地情况 |
| --- | --- | --- |
| B1.14 | Learner 显式创建；`display_name` 必填非空；`status` 默认 active；不创建默认 Learner | `create_learner` 校验 + 无默认写入 |
| B1.14 | Learner 禁止物理删除 | 服务层**不提供**删除接口 |
| B1.14 | Task 必须绑定存在且 active 的 Learner | `create_task` 校验 |
| B1.14 | `task_kind ∈ {learn, review}`；`status ∈ {active, completed, dropped}` | 枚举校验 |
| B1.14 | `textbook_id` 必须来自当前教材库（禁止用户乱填） | 通过 contentpack 只读校验 `textbook_edition` |
| B1.14 | 创建 Task 至少 1 个 TaskItem，且**同一事务** | `create_task` 单事务写入 Task + TaskItem |
| B1.14 | 状态单向：`active → completed / dropped`，不可逆 | `_set_task_status` 校验 |
| B1.14 | 离开/中断不自动改状态 | 无任何自动状态变更代码 |
| B1.15 | TaskItem 只存 `task_id / item_id / ordinal / created_at` | 表结构未变，服务不写其他字段 |
| B1.15 | `item_id` 必须存在于当前教材库 | `_contentpack_item` 只读校验（创建 Task / 新增 TaskItem / 写 Record 三处） |
| B1.15 | Record 前校验：learner 存在、task 存在、task 属于 learner、task 为 active、item 是该 Task 的 TaskItem | `_validate_event` |
| B1.15 | `activity_type` 九种枚举；`result` 五种 + NULL | 应用层校验（DB 无 CHECK） |
| B1.15 | `response_raw` 仅文本；空字符串**不落库**（保存 NULL） | `raw = ... if response_raw.strip() else None` |
| B1.15 | `hints_used` 非负整数，默认 0 | 校验 |
| B1.15 | `attempt_no` = 同一 (learner, task, item, activity_type) 内递增，从 1 开始；换上下文重新从 1 | `_next_attempt_no`，在 `BEGIN IMMEDIATE` 事务内计算（非无保护 MAX+1） |
| B1.15 | `INSERT Record + UPSERT Mastery` **同一事务**，失败整体回滚 | `record_learning_event` |
| B1.15 | `evidence_count` 只计 correct / incorrect / partial / done | `_upsert_mastery` |
| B1.15 | `correct_count` 只计 correct（**partial 不计**） | 同上 |
| B1.15 | `last_result` / `last_practiced_at` 仅由参与判断的结果更新 | 同上 |
| B1.15 | `skipped` / NULL 只写 Record，不改变掌握派生字段 | 同上（并有测试 H / I 验证） |
| B1.15 | 不在 Learner / Task / TaskItem 创建时预建 MasteryState | 无预建逻辑 |
| B1.15 | `review_needed` 不自动计算；AI 不得修改 | 服务不触碰该字段 |
| B1.15 | Record append-only | 无 update / delete 接口 |
| B1.14/15 | completed / dropped 后不得继续写 Record 或改 TaskItem | `ConflictError` |
| 最高原则 | contentpack 只读；AI = 0 | 仅 `mode=ro` 打开教材库；服务无网络 / AI 依赖 |

## 5. 留待后续（本轮明确不做）

```text
1. Mastery 算法（unknown → learning → familiar → stable 的升级/降级规则、阈值、正确率、衰减）
2. Review 算法（间隔重复、next_review_at、自动排程、自动选题）
3. LearningActivity / Question / Exercise / ReviewItem 实体
4. AI 建议入口（AI 建议 → 孩子确认 → 系统创建 Task）
5. 多 Learner UI（新增 / 切换）
6. 按 unit / section 组织学习计划（当前可由 item_id 推导）
7. MasteryState 重建工具（当前记录保证可重建，工具未实现）
```

## 6. 测试结果

测试文件：`learning/test_learning_service.py`（stdlib `unittest`，无新依赖）
测试数据库：`%TEMP%\zhixue_c1_*\learning_test.db`（正式 learning.db 的副本）→ 测试结束自动清理（已验证临时目录无残留）

```text
Ran 14 tests — OK（全部 PASS）

A  create_learner 成功 / 空名拒绝 / 不存在查询报错           PASS
B  create_task 成功（含 2 个 TaskItem、ordinal=1,2）/ 空 item、非法 kind、
   不存在 textbook、不存在 item、不存在 learner 全部拒绝      PASS
C  add_task_item / 重复拒绝 / remove_task_item / list        PASS
D  record_learning_event 产生 Record（字段完整、快照自动填充） PASS
E  同时写入 MasteryState（evidence=1、correct=1、last_result=correct） PASS
F  连续两次同活动 attempt_no = 1 → 2；换 activity_type / 换 Task 重新从 1 PASS
G  partial：evidence+1，correct_count 不增加，last_result=partial PASS
H  skipped：产生 Record，evidence / correct / last_result / last_practiced_at 均不变 PASS
I  NULL：产生 Record，不影响掌握派生字段；空字符串 response_raw 落库为 NULL PASS
J  故意让 Mastery 更新失败 → Record 与 Mastery 全部回滚（库中 0 条），随后可正常写入 PASS
K  completed Task：拒绝新增 Record，TaskItem 只读，状态不可逆         PASS
L  dropped Task：拒绝新增 Record                                PASS
M  AI 依赖静态检查：无 openai/deepseek/ollama/requests/urllib/socket/
   transformers/torch 等；无 Record update/delete 入口            PASS
额外：跨 Learner、非本 Task item、非法 activity_type、非法 result、负 hints_used 全部拒绝 PASS
额外：正式 learning.db 与 contentpack v5 在测试前后 SHA256 一致、业务表仍 0 行 PASS
```

## 7. learning.db 是否被污染

**未被污染。**

```text
测试前 SHA256：16E3952D64E749879D8FF78814F0434D544D4CBAD7D52AAC7E0B145DE43414E9
测试后 SHA256：16E3952D64E749879D8FF78814F0434D544D4CBAD7D52AAC7E0B145DE43414E9
业务表行数：learner 0 ｜ learning_task 0 ｜ task_item 0 ｜ learning_record 0 ｜ mastery_state 0
schema_migration：1 ｜ user_version：1 ｜ integrity_check：ok ｜ foreign_key_check：0 ｜ 表数量：6
```

所有测试数据写入临时副本，测试结束已清理（临时目录无残留）。

## 8. contentpack 是否被修改

**未修改。** SHA256 前后一致：`FF3FD568F4DA5348DB1F9DE7D68818CBEFD6A7E36A67C68EEF7F8386F4CE452A`（2,457,600 bytes，21 表，362 资源，source_ref 815）。服务仅以 `mode=ro` 打开教材库用于**只读校验**（textbook_id / item_id / active snapshot），无任何写语句。

## 9. AI / OCR / TTS 调用次数

```text
AI  ：0（服务与测试均无 AI/网络依赖；测试 M 做静态检查验证）
OCR ：0
TTS ：0
网络：0（未访问任何远端）
```

## 10. 新增依赖

**0**。仅使用 Python 标准库：`sqlite3` / `uuid` / `datetime` / `pathlib`（服务）与 `unittest` / `tempfile` / `shutil` / `hashlib` / `sys`（测试）。

## 11. 风险

```text
P0：0
P1：0
P2：2
    - Mastery 算法未实现（本轮有意为之；mastery_level 保持 unknown，仅维护基础派生计数）
    - MasteryState 重建工具未实现（数据可重建，工具属后续）
P3：3
    - ordinal 在同一 Task 内的唯一性由应用层保证（B1.12 已冻结不加 DB 约束）
    - review 作为 activity_type 的归类规则需在 Activity 阶段复核
    - 运行测试会生成 learning/__pycache__（Python 字节码缓存）；已在测试中设置
      sys.dont_write_bytecode=True 防止后续再生成，但本次产生的缓存目录因环境策略
      禁止删除操作而保留（非源码、非数据文件）
```

## 12. 下一阶段建议

```text
1. 在 C1 服务之上实现最小“学习会话”入口（选择资源 → 建 Task → 逐项记录），仍不接 AI
2. 设计并实现 MasteryState 重建工具（从 Record 重算派生计数）——属 P2
3. 之后才进入：Activity / Question 阶段、AI 建议入口（须孩子确认）、多 Learner UI
4. 任何 Schema 变更（如 next_review_at）一律另立受控设计 + 迁移审计，不在业务实现中顺手添加
```

## 13. 边界确认

```text
Schema        ：未变更（6 表、user_version=1、无新增字段/表/索引）
contentpack   ：只读，未修改
learning.db   ：未污染（业务表 0 行）
Android / UI  ：未触碰
D:\ZhixueAI   ：未触碰
AI/OCR/TTS    ：0 / 0 / 0
新增依赖      ：0
```
