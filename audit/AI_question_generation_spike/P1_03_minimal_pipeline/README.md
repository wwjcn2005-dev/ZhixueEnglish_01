# P1-03 · AI Question 最小生产流水线验证

最终状态：**PIPELINE_PASS**

---

## 一句话结果

用一份**已经验证过的**教材证据（Unit 1 · A new start · UNDERSTANDING_IDEAS），
完成了一次真实的

```text
教材证据 → DeepSeek（1 次）→ AI 题目 → Validator v2 → question_library.db
```

最小闭环，题目**停在人工审核之前**。

---

## 关键数字

```text
AI 调用次数            1        （deepseek-v4-pro，无 retry / 无第二模型 / 未用本地 Qwen）
生成题目               3
Validator v2          2 PASS / 1 FAIL
入库题目               2        （全部 PENDING_REVIEW）
ACTIVE 题目            0
REVIEW_APPROVED 事件   0
跨库悬空引用           0
learning.db            零修改
```

未入库的第 3 题：`reading_choice`，答案本身有教材支持，但干扰项里出现了
**教材之外的人物 `Mozi`**，被 Validator v2 的 `5_vocab_scope` 拦下。
这是本轮最有价值的一条端到端证据——**“教材外知识”被确定性地挡住了。**

---

## 复用的东西（没有重新组装）

| 复用项 | 值 |
| --- | --- |
| 输入上下文 | `471E6FA7AA82E03B99E31A43265944D2D8CA98C6924DCB6D38D196474677DFA4`（与 P0 逐字节一致） |
| system prompt SHA | `32E77851C6AEE69BE3…`（与 P0 1630 记录一致） |
| user prompt SHA | `8AA866CC9BF8707A…`（与 P0 1630 记录一致） |
| snapshot | `FLTRP-EN-7A-2022CUR:S20260912T151307`（active） |
| Validator | `validator_v2.py`（未修改，SHA256 `7C61585A…A683`） |

---

## 入库的两道题（真实回读）

| | 题 A | 题 B |
| --- | --- | --- |
| question_id | `AIQ:7EBCDBC29563` | `AIQ:3179968E3E74` |
| 题型 | `fill` | `vocab_choice` |
| 答案 | `sentence` | `polite` |
| 教材页 | 17 | 17 |
| evidence block | `…:P22:B0` | `…:P22:B2` |
| LearningObject | `…:V:3571476C132A` + `…:X:0F6BF1CC2913` | `…:V:813A79C77A94` + `…:X:0F6BF1CC2913` |
| validator | PASS（v2） | PASS（v2） |
| answer_support_type | `EXACT` | `EXACT` |
| lifecycle | `PENDING_REVIEW` | `PENDING_REVIEW` |

---

## 本轮发现的三条真实问题（交接给 P1-04）

1. **`EXACT` 陷阱触发器对选择题过度触发**：P1-02 的条件是“答案出现在题干/选项中”，
   而选择题的正确答案本来就在选项里，导致两道入库题都被标记 `needs_human_review=1`。
   方向保守（不会漏放风险题），但削弱了该标记的区分度。
   建议收窄为「**选项文本本身出现在教材证据里**」。
2. **`fill` 题携带 options / correct_option**：本轮 fill 题自带词库与 `correct_option='A'`，
   题型规则未拦截。需要明确 fill 是否允许选项。
3. **事件枚举缺 `GENERATED` / `PENDING_REVIEW`**：为不改动 P1-01/P1-02 的 schema，
   本轮用一条 `VALIDATED` 事件、以 `from_status=GENERATED → to_status=PENDING_REVIEW` 表达该迁移；
   建议后续 schema 版本补齐枚举。

---

## 成本

```text
model              deepseek-v4-pro
calls              1
prompt_tokens      9,451（cache hit 9,344）
completion_tokens  7,332（reasoning 6,638）
total_tokens       16,783
latency            116.6 s
finish_reason      stop
```

---

## 保护项（执行后复验）

```text
learning.db       未修改（SHA256 0C27267B…CF91）
contentpack v5    未修改（ai_artifact = 0 行）
教材 PDF          未修改（SHA256 C732051E…4F2F）
54 个 MP3         未修改（54 / 54 与 audio_asset.sha256 一致）
validator v2      未修改（SHA256 7C61585A…A683）
Web / Android / V1.3 / V2.0   未修改
重新解析 PDF       否
本地 Qwen          未使用
第二次 AI 调用      未发生
```

本轮被修改的正式资产**只有** `structured/ai/question_library.db`。

---

## 产物

| 文件 | 说明 |
| --- | --- |
| `README.md` | 本索引 |
| `p1_03_pipeline_report.md` | 完整流水线报告 |
| `p1_03_pipeline_audit.json` | 入库后审计结果（A–H + 真实回读 + 保护项） |
| `run_pipeline.py` | 流水线脚本 |
| `dump_pipeline_audit.py` | 审计导出工具 |
| `raw_response.json` | 原始 API 响应（审计留档；报告不引用其中 reasoning） |
| `generated_questions.json` | 解析后的原始 AI 输出 |
| `validation_result.json` | Validator v2 逐题结果 |

---

## 边界

- 题目**未进入孩子学习流程**：`learning_record` 仍缺 `source_kind` / `source_ref` / `source_version`，
  AI 题目当前只是**后台待审核学习资源**。
- 未来孩子页面**不得显示**任何技术元数据（model / prompt_version / context_hash /
  generation_run_id / validator_version / evidence_block_id / lifecycle_status /
  question_fingerprint / 内部 ID）；需要说明来源时只用「教材第 17 页」这类自然语言。
