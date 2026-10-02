# P0 收口只读审计 · 产物索引

状态：**P0_CLOSE**（详见 `p0_closeout_report.md`）

本次为**只读审计**：未调用任何 AI（云端 0 / 本地 0），未修改任何正式文件，
未创建正式 AI 题库表，未向 `learning.db` 写入任何题目，未改动 validator v2。
本目录仅存放审计报告与只读分析产物。

## 产物

| 文件 | 内容 |
| --- | --- |
| `README.md` | 本索引 |
| `p0_closeout_report.md` | 完整审计结论（含 A–I 全部问题与 P0 结论） |
| `p0_evidence_matrix.json` | 结构化证据矩阵（验证项 / Spike / 证据 / 结果 / 可否冻结 / 未解决风险） |
| `p1_design_recommendations.md` | P1-01 ~ P1-05 设计建议（只设计，不实施） |

## 被审计的四次 Spike（只读，未修改）

| Spike | 目录 | 一句话结果 |
| --- | --- | --- |
| Spike 1 | `../20260917_1450_deepseek_min3/` | 云端 DeepSeek 首次真实生成 3 题；v1 校验 1/3（2 处口径误报） |
| Spike 1b | `../20260917_1520_validator_fix/` | validator v2 修正 + 9/9 单测 + 3/3 回归 + 6/6 对抗样本拦截 |
| Spike 2A | `../20260917_1610_deepseek_second_section/` | Unit 1 UI；`max_tokens=4096` 被 reasoning 占满，生成 0 题 |
| Spike 2B | `../20260917_1630_deepseek_second_section_8192/` | 同一上下文仅把 `max_tokens` 改 8192 → 3 题 3/3 PASS |
| Spike 3 | `../20260917_1650_evidence_insufficient/` | 证据不足场景 → 模型主动返回 0 题并说明理由 |

## 只读检查过的正式结构（未修改）

```text
structured/ai/textbook_evidence_map_v1.json
structured/textbook/textbook_structure_v2.json
structured/textbook/textbook_content_relations_v2.json
structured/textbook/textbook_context_relations_v2.json
structured/textbook/textbook_visual_relations_v2.json
structured/exercises/exercise_catalog_v3.json
structured/exercises/exercise_question_relations_v3.json
structured/learning/learning.db
structured/contentpack/v5/FLTRP-EN-7A-2022CUR.sqlite
```

## 一条重要的口径提醒

> 当**选项文本本身存在于教材证据中**时，`answer_support = EXACT` 只表示
> “该字符串能在证据里找到”，**不等于**模型真的证明了答案的正确性。

这是 validator v2 已知的、必须由人工复核兜底的结构性边界。

## 如实披露：本次审计产生的唯一非报告类副作用

为核实 Spike 1b 的“9/9 单测”结论，本次审计**实机重跑了**
`20260917_1520_validator_fix/test_validator_v2.py`（Ran 9 tests，OK）。
该动作可能刷新了同目录下的 Python 字节码缓存
`__pycache__/validator_v2.cpython-312.pyc`。

- 这是**派生的字节码缓存**，可随时重新生成，不含任何业务数据；
- 源文件 `validator_v2.py` **未被修改**（size 5,910 B，mtime 2026-09-17 14:31:02，
  SHA256 `7C61585A99B55576CA82D9946635784964322236BA145A23FBDFA2A1F8DCA683`）；
- 未触碰 `learning.db`、contentpack、教材 PDF、MP3、Web、Android。
