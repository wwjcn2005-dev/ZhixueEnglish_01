# P2-6-D-2 /review 最小接入实施报告

> 只读接入。**未修改 D-1 冻结服务、六个冻结服务、P2-6-B 四服务、mastery_rules_v1.json、learning.db、contentpack、P2-4/P2-5、V1.2、Android、教材、音频**；AI 调用 0。

- 实施时间：2026-09-13 ｜ 项目：`D:\ZhixueEnglish`

## 1. 实施结论

**PASS**

D-1 的 LO 派生结果已安全接入现有 `/review`：新增「教材学习建议」区块 + 空状态 + 异常降级；现有池分组、item 级教材建议、vocabulary revisit 与身份逻辑**完全未动**；测试 **397 PASS / 0 FAIL / 0 SKIP**（原有 386 全部保持）。

## 2. 修改文件（3 个）

| 文件 | 修改点 | SHA256 前 20 位（改后） |
| --- | --- | --- |
| `web/flow.py` | 新增 `lo_review_section(conn, learner_id, cp)`（只读；try 包裹；字段最小化）+ `logging` 导入 | `E74D89252F3A9898E15F` |
| `web/app.py` | `_review()` 内 +3 行：把 `flow.lo_review_section(...)` 结果作为 `lo_section` 传入 `ui.review_page` | `CB2984D2D48B0D0A4A79` |
| `web/ui.py` | `review_page()` 在现有内容**之后**追加「教材学习建议」区块（有内容/空态/降级三态） | `F95D8AE59813ECE41AB3` |

新增测试：`web/test_p2_6d2_review_integration.py`（11 项）。**无其它文件改动。**

## 3. D-1 调用方式与数据流

```
GET/POST /review → app._review()
    ├─ flow.need_relearn()                （既有，不动）
    ├─ flow.textbook_review_suggestions() （既有，不动）
    ├─ flow.lo_review_section(conn, learner_id, cp)   ← 新增
    │      └─ learning_object_service.needs_attention()  （D-1 冻结接口，只调用不复制规则）
    └─ flow.learner_name()
 → ui.review_page(ctx)（新增区块渲染 D-1 结果）
```

`lo_review_section()` 返回最小字段：`learning_object_id / object_type / title（取自 D-1 建议的 display_text）/ mastery_display_text（D-1 原样）/ mastery_stable / diagnosis_label / diagnosis_level / suggestions[{label, anchor_text, link, type}] / auto_execute=False`。

## 4. 三态 UI 与文案

- **有内容**：逐条显示 `title` → `mastery_display_text`（如"学习证据 1 次（不代表掌握）"）→ 诊断标签（如"最近这一次做错了"）→ 教材优先建议（含教材定位）→ `[去看看]` 普通 `<a>`；末尾提示"要不要看、先看哪一个，都由你自己决定"。
- **空态**（当前正式库即此态）：`暂时没有需要再看的教材学习对象` + 说明"这里只在你做过、并且出现过错误或没出现出来的内容时出现"。
- **降级态**（D-1 抛错）：`暂时无法生成教材学习建议` + "这不影响上面已有的内容"。

## 5. 边界落实

| 要求 | 落实 |
| --- | --- |
| UI 不重算 evidence/mastery/diagnosis | ✅ `ui.py` 未 import 任何学习服务（测试断言）；文案与建议顺序原样来自 D-1 |
| 不复制 D-1 规则 | ✅ flow 仅调用 `needs_attention()` |
| 无自动行为 | ✅ 无 `<script>`、无 `onclick`、无 `autoplay`、无 `setTimeout`、无自动跳转（测试断言） |
| 无命令式语言 | ✅ 测试断言"今日任务/必须完成/下一步必须学习/系统为你安排/推荐任务/立即开始/任务完成"均不出现 |
| 不暴露内部 id | ✅ 页面渲染 `title`（如 "eraser"），**不含内部 LO id**（测试断言） |
| vocabulary revisit 共存 | ✅ 池分组与 `学习这个词` 链路完全未改；LO 区独立并置（当前允许重复观感，按 D-2 审计 G1 延后处理） |
| 异常降级 | ✅ try/except + `logging.warning`（项目既有 logging 风格），其余内容不受影响 |

## 6. 测试结果

| 套件 | 数量 | 结果 |
| --- | --- | --- |
| **新增 D-2 测试** | **11** | PASS / 0 FAIL |
| learning | 112 | PASS |
| workbench | 50 | PASS |
| web（含新增） | 235 | PASS |
| **总计** | **397** | **PASS / 0 FAIL / 0 SKIP** |

新增测试覆盖任务书 §十五 的 8 项（LO 建议区渲染、文案来自 D-1、UI 不重算、建议顺序、普通 `<a>`、无自动执行、无命令式语言、GET 零写入）+ 空状态 + 异常降级 + 正式库未变。

## 7. 保护基线（实施后复核）

```
learning.db  DBAB743BF6D8F0A3832E…（mtime 2026-09-12 23:15 未变；7 表；record 20；integrity ok / FK 0；migration 0 / DML 0）
contentpack  ACEBC8C29CF5D11BAB50…（未变）
V1.2         6D3595CF7D83879ADF3E…（未变）
D-1 服务     learning/learning_object_service.py 56C4F4140EC6FE43…（FROZEN，未改）
未修改       六个冻结服务 / P2-6-B 四服务 / mastery_rules_v1.json / P2-4 / P2-5 / Android / 教材 / 音频
AI 调用      0
```

## 8. S24+ 验证

本轮未执行真机验证（按任务书：不修改 Android，仅必要时观察）。已通过 HTTP 级验证：`GET /review` 200、新区域/空态/降级三态渲染正常、无自动行为、零写入。

## 9. 未解决 GAP（保持）

G1 同一词的 item 级池展示与 LO 级建议可能重复（当前并置允许，待真机验证后再定）；G2 已在 flow 层解决异常包裹；G3 P2-6-B 建议块已由本次测试覆盖；G4 空态已实现。其余：Consolidation Action、Grammar LO、68 unmapped、LO mastery 持久化、UI 大改、AI 接入均**未触碰**。

## 10. 停止声明

D-2 完成即停止：未做 Consolidation Action、Grammar LO、unmapped 修复、mastery 持久化、AI 接入、音频处理、Android 重构、UI 大改、学习计划或游戏化。等待下一条任务指令。
