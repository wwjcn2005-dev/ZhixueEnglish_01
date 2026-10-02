# P1-02 · AI Question Library 最小数据库实现

最终状态：**IMPLEMENTATION_PASS**

---

## 本次创建了什么

**唯一新建的正式文件**：

```text
D:\ZhixueEnglish\structured\ai\question_library.db
size    = 126,976 B
SHA256  = 5FECB38F20303723F4231EBB3406C97ED5F5DD2DE35C17253525D16968CEA9D8
user_version = 1
integrity_check = ok
foreign_key_check = 空
数据行数 = 0（6 张表全部为空，不含任何真实 AI 题目）
```

6 张表：

```text
generation_run            一次 AI 调用 = 一行（question_count 允许为 0）
ai_question               题目实体，PK = (question_id, version)
question_evidence         题目 ↔ 教材证据块（1:N）
question_learning_object  题目 ↔ LearningObject（1:N）
question_validation       validator 结果，PK 含 validator_version
question_event            生命周期 / 审核事件（append-only）
```

---

## 四个用 SQLite 原生机制保证的硬门槛

1. **validator PASS ≠ ACTIVE**：新题不允许以 ACTIVE 插入；转为 ACTIVE 时必须有
   `actor_kind='human'` 的 `REVIEW_APPROVED` 事件（两个触发器）。
2. **question_event 不可篡改**：UPDATE / DELETE 均被触发器拒绝。
3. **题目不可删除**：下线只能走 `DISABLED`。
4. **EXACT 陷阱自动升级**：当 `answer_support_type='EXACT'` 且答案文本同时出现在题干/选项中时，
   自动置 `needs_human_review = 1`。

另有一条防语义污染的约束：

```sql
CHECK (item_id NOT LIKE 'AIQ:%' AND item_id NOT LIKE 'AIRUN:%')
```

即 **question_id / run_id 不可能被塞进 LearningObject 位置**。

---

## 测试

```text
Ran 19 tests in 5.438s
OK
```

19 个测试方法覆盖任务要求的 T1–T16。测试全部运行在临时数据库上，
**正式题库始终保持为空**。

---

## 跨库检查

```text
question_learning_object.item_id       refs=0 ok=0 dangling=0
question_evidence.evidence_block_id    refs=0 ok=0 dangling=0
跨库检查结果：PASS（无悬空引用）
```

---

## 两条必须遵守的边界

**一、AI 题目暂不得进入孩子学习流程。**
`learning_record` 目前还没有 `source_kind` / `source_ref` / `source_version`，
无法回答“做的是哪一道题的哪个版本”。本阶段未执行该迁移，也未修改 `learning.db`。

**二、前台不得显示技术元数据。**
`model`、`prompt_version`、`context_hash`、`generation_run_id`、`validator_version`、
`evidence_block_id`、`lifecycle_status`、`stale_reason`、`question_fingerprint`
以及任何数据库内部 ID，都不得出现在孩子页面；需要说明来源时只用「教材第 17 页」这类自然语言。

---

## 产物

| 文件 | 说明 |
| --- | --- |
| `README.md` | 本索引 |
| `p1_02_implementation_report.md` | 完整实施报告 |
| `p1_02_schema_audit.json` | schema 审计结果（从真实库导出） |
| `ql_schema.py` | DDL 模块与复用键计算 |
| `create_question_library.py` | 建库脚本（拒绝覆盖既有库） |
| `test_question_library.py` | 19 个最小测试 |
| `check_cross_db_refs.py` | 跨库引用只读检查 |
| `dump_schema_audit.py` | schema 审计导出工具 |

---

## 保护项

```text
learning.db       未修改（SHA256 0C27267B…CF91，mtime 2026-09-13 15:50:09）
contentpack v5    未修改（ai_artifact = 0 行）
教材 PDF          未修改（SHA256 C732051E…4F2F，与正式记录一致）
54 个 MP3         未修改（54 / 54 与 audio_asset.sha256 完全一致）
validator v2      未修改（SHA256 7C61585A…A683）
Web / Android / V1.3 / V2.0   未修改
AI 调用            0
重新解析 PDF       否
正式学习数据写入     无
```

## 如实披露：本目录内的一个派生缓存文件

运行 `create_question_library.py` / `dump_schema_audit.py` / `check_cross_db_refs.py` 时，
Python 在本目录下生成了字节码缓存：

```text
__pycache__/ql_schema.cpython-312.pyc
```

- 它是**派生的字节码缓存**，内容仅为本目录 `ql_schema.py` 的编译结果，可随时重新生成；
- 不含任何业务数据，也不影响任何正式文件；
- 源文件 `ql_schema.py` 未被修改；
- 清理该缓存的操作被本机命令策略拦截，因此保留原样并在此如实披露。
