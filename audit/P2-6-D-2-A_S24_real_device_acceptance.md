# P2-6-D-2-A S24+ 真机体验验收报告

**结论：PASS WITH GAPS**（唯一 GAP：G1 观察项未能在正式库触发）

- 验收时间：2026-09-13 ｜ 项目：`D:\ZhixueEnglish`
- 真机：**Samsung SM-S9260（S24+）**，`adb` 在线（"adb-R5CWC411C0K…"）
- APP：`com.zhixueenglish.app.dev`，`versionName=0.1-dev`；WebView → `http://192.168.2.3:8770/`
- 本轮为**只读验收**：未修改代码/测试/数据库/教材/音频/规范/Android；AI 调用 **0**

## 1. 冻结基线（验收前后一致）

| 项 | 值 |
| --- | --- |
| learning.db | SHA256 `DBAB743BF6D8F0A3832E599C…`，mtime `2026-09-12 23:15:13`（**前后一致**；7 表；record 20；mastery_state 7；integrity ok；FK 0） |
| contentpack | `ACEBC8C29CF5D11BAB50…` ｜ V1.2 `6D3595CF7D83879ADF3E…` |
| D-1 服务 | `learning/learning_object_service.py` `56C4F4140EC6FE431634…`（FROZEN） |
| D-2 改动 | `web/flow.py` `E74D89252F3A9898E15F…`、`web/app.py` `CB2984D2D48B0D0A4A79…`、`web/ui.py` `F95D8AE59813ECE41AB3…` |

## 2. `/review` 真机验证

服务按现有方式启动（`web/app.py --host 0.0.0.0 --port 8770`），以**既有学习者身份（王彬彬）**访问，不新建数据。

| 检查项 | 结果 |
| --- | --- |
| 页面打开 | ✅ 200；WebView 正常加载 `/review`（CDP 实测 `location.href`） |
| 黑屏 / 500 / 崩溃 | ✅ 无（`logcat -b crash` 0 行） |
| 教材学习建议区块 | ✅ 真机 DOM 含「教材学习建议」 |
| 空状态 | ✅ 真机 DOM 含「暂时没有需要再看的教材学习对象」 |
| 原有 Vocabulary Review | ✅ 真机 DOM 含「需要再学」（池区正常） |
| 自动行为 | ✅ 真机 `document.querySelectorAll('script').length = 0`；`onclick` 属性数 = **0**；无 `autoplay`/`setTimeout` |
| 命令式语言 | ✅ 无「今日任务 / 必须完成 / 下一步必须学习 / 系统为你安排 / 推荐任务」 |
| 「去看看」入口 | ✅ 仅普通 `<a href>`，需用户主动点击（未观察到自动跳转） |
| 决策权文案 | ✅ "要不要看、先看哪一个，都由你自己决定" |

截图已保存：`%TEMP%\p26d2a\p26d2a_review.png`（真机 `/review` 页面）。

## 3. G1 真实观察

正式库当前 `needs_attention()` = 0、池内 1 条 item 级记录 → **"同一个词同时出现在 Vocabulary 复习池与 LO 教材学习建议"的并置场景未被触发**。

> **G1：OBSERVED / NOT FULLY CLOSED**（未制造数据；仅完成结构与视觉检查）

## 4. 空状态 / 降级 / 日志 / AI

- 空状态：真机显示自然（"暂时没有需要再看的教材学习对象"），未与池区冲突，符合"没有就不制造任务"。
- 异常降级：真机未人为触发（**已由 D-2 自动化测试覆盖**：`available=False` + 降级文案 + 其余内容正常）。
- 日志：无 500、无崩溃、无循环请求、无 AI 请求。
- **AI 调用 = 0**。

## 5. 测试回归

| 套件 | 结果 |
| --- | --- |
| learning | 112 PASS |
| workbench | 50 PASS |
| web | 235 PASS |
| **合计** | **397 PASS / 0 FAIL / 0 SKIP**（与 D-2 基线完全一致） |

## 6. 文件与数据变更

```
代码修改：0 ｜ 测试修改：0 ｜ 数据库写入：0（SHA/mtime 前后一致）
教材/音频修改：0 ｜ 规范修改：0 ｜ Android 修改：0 ｜ AI 调用：0
新增文件：仅本报告与 JSON
```

## 7. 遗留 GAP

G1（并置重复观感）未在真机触发 → 待真实数据出现后观察；Consolidation Action、Grammar LO、68 unmapped、LO mastery 持久化、UI 大改、AI 接入均未触碰。

## 8. 停止声明

本轮为**只读真机验收**：未修改代码、数据库、教材、音频、规范及 Android 工程；AI 调用 0。**验收完成即停止，等待下一条任务指令。**
