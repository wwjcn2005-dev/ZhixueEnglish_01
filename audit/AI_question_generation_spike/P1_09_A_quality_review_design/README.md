# P1-09-A · AI 英语质量复核只读设计审计

阶段结论：**P1-09-A_PASS**

本阶段是 **READ-ONLY AUDIT + DESIGN**：不调用任何 AI、不生成题、不改任何数据库与正式资产。

## 本目录内容

| 文件 | 说明 |
| --- | --- |
| `p1_09_a_report.md` | 主报告（机制复核、四方案比较、维度压缩、存储分级、schema v3 分析、成本、样本设计、16 项验收） |
| `p1_09_a_audit.json` | 只读审计结果：schema/触发器/列清单、21 题全量明细、6 个硬门槛、validator 重算、保护项 |
| `validator_capability_check.json` | 对 21 道真实题只读重算 validator v2/v3（含 P1-08-C Sample B 的能力边界证据） |
| `sample_matrix.json` | 下一阶段测试样本矩阵（9 类，全部取自真实题库；不足的类别如实声明） |
| `triage_result.json` | 确定性 triage 规则与逐题命中结果（程序侧，无 AI） |
| `cost_model.json` | 成本模型：真实调用实测标定 + 复核输入规模 + 5 种方案对比 |
| `review_output_design.json` | AI 复核最小输出结构 + 字段 A/B/C 存储分级 + 审核 UI 最小信息 |
| `schema_v3_draft.sql` | **设计草案（未执行）**：纯增量的 `question_ai_review` 表与 append-only 触发器 |
| `protect_before.json` / `protect_after.json` / `protected_assets_check.json` | 1,099 个正式资产文件的哈希清单与前后比对 |
| `*.py` | 本轮只读审计脚本（`dump_db` / `probe_vocab` / `probe_contentpack` / `p1_09_a_audit` / `triage_and_cost` / `sample_matrix` / `protect_snapshot`） |

## 核心结论

```text
1. 机制仍在：question_library.db schema v2 + 6 个触发器 + validator v2/v3 + P1-07 五道闸门，全部实测复核通过
2. 推荐方案 D：生成 → 程序验证 → 第二次独立 AI 英语质量复核（只给建议）→ 人类最终确认 → APPROVED → ACTIVE
3. AI 复核 6 维：english_correct / answer_unique / naturalness / learning_value
                  distractor_quality / grade_fit
   程序保留 2 维：mechanical_reproduction（程序已算） / evidence_consistency（程序负责）
4. schema：本轮不升级；最终若要进正式审核链路，只新增 question_ai_review（纯增量）
5. 成本：批量复核约 8.4% 的生成成本；逐题复核 30.3%，不划算
6. 样本：9 类全部有真实题可覆盖；英语错误题 / 荒谬干扰项 / 超纲题三类"现有真实样本不足"
```

## 硬保护

```text
AI 调用 0 · 新题 0 · question_library.db 0 修改（SHA256 7AA12CA5…5DA7 前后一致）
learning.db 0 修改 · contentpack 0 修改 · 教材 PDF 0 修改 · 54 MP3 0 修改
Web / Android 0 修改 · validator v2/v3 0 修改 · P0–P1-08 既有产物 0 修改
V1.0 / V1.3 / V2.0 规范 0 修改 · 新依赖 0 · 未伪造任何 AI 复核结果
```

## 重新运行（只读）

```powershell
python -X utf8 -B audit\AI_question_generation_spike\P1_09_A_quality_review_design\protect_snapshot.py before
python -X utf8 -B audit\AI_question_generation_spike\P1_09_A_quality_review_design\p1_09_a_audit.py
python -X utf8 -B audit\AI_question_generation_spike\P1_09_A_quality_review_design\triage_and_cost.py
python -X utf8 -B audit\AI_question_generation_spike\P1_09_A_quality_review_design\sample_matrix.py
python -X utf8 -B audit\AI_question_generation_spike\P1_09_A_quality_review_design\protect_snapshot.py after
```

`-B` 用于避免写入任何 `__pycache__`；数据库一律以 `?mode=ro` 只读 URI 打开。
