# P2-6-D-2 /review 最小接入只读审计报告

> **只读审计，不实施。** 未修改任何项目文件（含 web/ui.py、web/flow.py、learning_object_service.py、测试、数据库、contentpack、V1.2、Android）；未调用 AI。
> 唯一产出：本报告与 `P2-6-D-2_review_integration_audit.json`。

- 审计时间：2026-09-13 ｜ 项目：`D:\ZhixueEnglish`
- 依据：V1.2、C-4、C-4-A、D-0、D-1（均已冻结）

---

## 1. 审计结论

**PASS WITH GAPS**

D-1 的 LO 派生结果**可以最小增量接入现有 `/review`**，无阻塞；需明确记录 4 项非阻塞 GAP（重复显示风险、异常包裹、建议块缺 UI 测试、空态实现）。

## 2. 当前 /review 架构（实测）

| 环节 | 位置 |
| --- | --- |
| 路由（GET） | `web/app.py:173` → `self._review()` |
| 路由（POST，带 name） | `web/app.py:201` → `self._review(form)` |
| 数据准备 | `web/app.py:626 def _review()`：`flow.resolve_learner` → `flow.need_relearn()` → `flow.textbook_review_suggestions()` → `flow.learner_name()` |
| 页面生成 | `web/ui.py:881 def review_page(ctx)` |
| 现有内容 | ① "需要再学"（池分组：上次忘了 / 上次有点模糊；词汇卡片 + `学习这个词` 表单 → `/vocabulary/study`）② P2-6-B"教材建议"卡片（`去看看` 普通链接） |
| 现有样式组件 | `.card` / `.item` / `.hint` / `.meta` / `<a>` —— **无需新增 CSS 组件** |
| 自动行为 | **无**（无自动跳转、无自动播放、无自动执行；表单与链接均需孩子主动点击） |
| 是否依赖固定 item_id | 是（池分组与建议均以 `item_id` 为单位；LO 层以 `learning_object_id` 为单位，需并置而非替换） |

## 3. 当前 Review 数据流（实测）

```
GET/POST /review
    ↓  web/app.py:173 / :201
handler._review()
    ↓  flow.resolve_learner(conn, name)                        （仅 POST 带名字）
    ↓  flow.need_relearn(conn, learner_id, cp)                 → 池分组（item 级，frozen 池）
    ↓  flow.textbook_review_suggestions(conn, learner_id, cp)  → item 级教材建议（P2-6-B）
    ↓  flow.learner_name(conn, learner_id)
ui.review_page(ctx)                                            → HTML（无自动行为）
```

**调用点唯一性**：`need_relearn()` 仅被 `app._review()` 调用（全库仅定义 + 1 处调用）；首页"需要再学"计数走**另一条**池摘要路径 → 扩展 review 数据**不影响首页**。

## 4. D-1 LO 服务接口分析

| 函数 | 输入 | 输出 | 只读 | 访问 DB | 改状态 | AI | 异常风险 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `learning_object_service.needs_attention(conn, learner_id, contentpack_path=…)` | 只读连接、learner_id | LO 列表（diagnosis + mastery + suggestion） | ✅ | ✅ 仅 SELECT | ❌ | ❌ | ⚠️ 内部未包裹 try（`lo_suggestion` 可能上抛）→ D-2 在 flow 层包裹 |
| `summary(conn, learner_id)` | 同上 | 覆盖率 + 各 LO 证据/掌握 + attention | ✅ | ✅ | ❌ | ❌ | 同上 |
| `mapping_coverage()` | 无（读 structured 产物） | mapped/unmapped/coverage_ratio | ✅ | ❌ | ❌ | ❌ | 低 |

**推荐入口**：`needs_attention()`（一次调用即得"需要关注的 LO + 掌握 + 教材优先建议"）。`mapping_coverage()` 仅用于**诚实展示**，不得驱动映射或制造"必须学习"。

## 5. 最小接入点

```
现有 Review 数据（池分组 + item 级建议）
        +
D-1 LO 派生结果（needs_attention）
        ↓
现有 review_page 追加一个「教材学习建议」区块
```

原则：**不重写 Review、不新增路由、不改池逻辑、不新增 CSS、不引入 JS 自动行为。**

## 6. web/flow.py 是否需要修改

**需要（YES）**：① UI 层不得自行取数或计算（§九）；② 现有 flow 只提供 item 级函数；③ 故需新增 **1 个只读函数**（建议 `lo_review_section(conn, learner_id, cp)`），内部调用 `needs_attention()` 并做异常包裹与字段裁剪。

## 7. web/ui.py 是否需要修改

**需要（YES）**，仅新增**一个展示区块**（建议标题「**教材学习建议**」），条目显示：

```
LO 类型 + 教材位置（unit/section/page 或词表页）
学习证据 N 次（不代表掌握）        ← 原样取 D-1 的 display_text
诊断：最近这一次做错了 / 同一处反复出错 / 建议回到教材再看一遍
教材建议：回看原教材文本 → 重听官方音频 → …
[去看看]  ← 普通 <a>，孩子点击才进入
```

复用现有 `.card` / `.item` / `.hint` / `<a>`，不新增 CSS、不改导航。
**关于 web/app.py**：`review_page(ctx)` 的 ctx 由 `_review()` 构造 → 需 **app.py +2 行**传参，属同一最小增量。

## 8. vocabulary revisit 共存分析

| 问题 | 结论 |
| --- | --- |
| 与 LO 建议的关系 | 互补：词表区 = **最近一次判断的事实**（池，item 级）；LO 区 = **学习对象级诊断 + 教材优先建议** |
| 是否重复显示同一个词 | **存在风险**（同一词可能同时在两区出现） |
| 当前是否已发生 | **未发生**（正式库 `needs_attention()` 为空、池仅 1 条 item 级记录） |
| 是否保持现有 revisit 不动 | **是**（不动池逻辑与 `学习这个词` 链路） |
| D-2 是否可独立成区 | **可以**（并置 + 层级文案） |
| 旧逻辑 + 新逻辑是否冲突 | 无逻辑冲突，但**观感重复**需处理（G1） |

**建议（最小）**：先"并置 + 层级文案"（词表区标题保持"需要再学"，LO 区标题"教材学习建议"并标注"按学习对象"）；真机验证后若重复观感明显，再于同一任务内加**最小去重**（同一 LO 的来源 item 已在上方展示时，LO 区显示"（已在上面列出）"）。

## 9. UI 自动执行风险检查

| 检查项 | 现状 | D-2 必须保持 |
| --- | --- | --- |
| 自动跳转 / 自动播放 / 自动进入练习 / 自动执行建议 | 无 | ✅ 保持 |
| 自动选择下一对象 / 自动安排计划 | 无 | ✅ 保持 |
| 积分 / 排名 / 等级 / 倒计时 / 游戏化 | 无 | ✅ 保持 |
| 命令式措辞 | 现无（均为陈述式） | ✅ 禁用"必须/今日任务/下一步必须学习/系统为你安排/推荐任务" |

## 10. Evidence / Mastery 语义边界检查

- 现有 review 数据来自 frozen 池（事实层）与 P2-6-B 服务（结论层）；**UI 不重算**，仅渲染。
- D-2 必须保持单向：`learning_object_service → flow → ui`；**禁止** ui 直接 import `evidence_service` / `mastery_service` / `diagnosis_service`（现状 ui.py 未 import → 保持）。
- `display_text` 与"掌握较稳定"必须**原样取自 D-1**，UI 不得改写或加等级。

## 11. Review 测试现状（实测）

| 测试 | 位置 | 覆盖内容 | D-2 必须保持 |
| --- | --- | --- | --- |
| relearn 页复用同一 Study 链 | `web/test_vocabulary_flow.py:389` | "上次忘了" + 词 + `pick` 字段 + `/vocabulary/study` | ✅ |
| POST /review 带名字 | `test_vocabulary_flow.py:526 / :596 / :610` | 身份入口、只读、多学习者隔离 | ✅ |
| 首页计数跟随 Cookie learner | `test_vocabulary_flow.py`（约 :580） | "有 1 个内容需要再学" / 空状态 | ✅ |
| 列表 GET 零写入 | `test_vocabulary_flow.py`（test_09） | 只读保证 | ✅ |
| 路由清单含 `/review` | `test_vocabulary_flow.py:1024`、`test_web_app.py:460` | 路由存在 | ✅ |
| 空状态文案 | `test_web_app.py:132` | "目前还没有需要再学的内容" | ✅ |

**数量**：与 `/review` 直接相关的既有测试 **6 处**（分布于 2 个文件）。
**缺口（非阻塞）**：P2-6-B 的"教材建议"区块**目前无 UI 级测试** → D-2 新增区块时一并覆盖。
**D-2 最少新增测试**：**6 项**（+2 项可选，见 §13）。

---

## 12. D-2 最小修改文件清单（规划，不实施）

| 文件 | 为什么必须改 | 改什么 | 为什么不扩大 |
| --- | --- | --- | --- |
| `web/flow.py` | UI 不得取数；需 LO 级只读入口 | 新增 1 个只读函数 `lo_review_section(conn, learner_id, cp)`（调 `needs_attention()`，try 包裹，裁剪展示字段） | 仅新增函数，不改既有函数 |
| `web/ui.py` | 需渲染新区域 | `review_page()` 追加 1 个区块（复用现有 class 与 `<a>`） | 不改现有区块、不改 CSS、不加 JS |
| `web/app.py` | ctx 由 `_review()` 构造 | `_review()` +2 行把结果作为新 key 传入 | 不改路由与 handler 结构 |

**NO CHANGE REQUIRED**：`learning/learning_object_service.py`（D-1 冻结）、`learning/test_p2_6d_learning_object.py`、六个冻结服务、P2-6-B 四服务、`mastery_rules_v1.json`、`learning.db`、contentpack、P2-4、P2-5、V1.2、Android、教材、音频。

## 13. D-2 最少新增测试

1. `/review` 渲染「教材学习建议」区块（含 LO id 或教材位置）；
2. 文案取自 D-1（`display_text` 原样出现，如"学习证据 N 次（不代表掌握）"）；
3. 建议顺序与教材优先一致（`reread_text → …`）；
4. 无自动执行（HTML 无 `autoplay`、无自动跳转脚本、无自动提交）；
5. 无命令式语言（"必须 / 今日任务 / 下一步必须学习 / 系统为你安排 / 推荐任务"均不出现）；
6. `/review` GET 零写入（业务表行数不变）；
7. （可选）重复显示：同一 LO 的来源 item 与词表区并存时的展示行为被断言；
8. （可选）覆盖率为诚实展示（unmapped 存在时不出现"100% 覆盖"类断言）。

## 14. 阻塞与非阻塞问题

**阻塞问题：无。**

| 编号 | 类型 | 问题 | 处置 |
| --- | --- | --- | --- |
| G1 | 非阻塞 | 同一词的 item 级池展示与 LO 级建议可能重复 | D-2 先并置 + 文案区分；真机验证后按需最小去重 |
| G2 | 非阻塞 | `needs_attention()` 未包裹异常 | D-2 在 flow 层 try 包裹（与 `textbook_review_suggestions` 同风格，失败返回空） |
| G3 | 非阻塞 | P2-6-B"教材建议"区块缺 UI 测试 | D-2 新增区块时一并覆盖 |
| G4 | 非阻塞 | 正式库当前 `needs_attention()=0`，新区域实测为空 | D-2 必须实现空态文案（不伪造数据） |

## 15. 数据库 / 规范 / AI 保护检查（审计基线）

| 项目 | 值 |
| --- | --- |
| `learning.db` | SHA256 `DBAB743BF6D8F0A3832E599CBD5DD2267F008FD9FB3903BACEA93780A466D633`；mtime `2026-09-12 23:15:13`；7 表；learning_record 20 条；mastery_state 7 条；integrity `ok`；FK `0`（与 D-1 基线一致） |
| contentpack | `ACEBC8C29CF5D11BAB50BF7962FBEE5DE42CD9CFC7FE48AB6316699D265E1A3F` |
| V1.2 docx | `6D3595CF7D83879ADF3E6452C5E5A74C5300E89265DE1B4F2FA8A1EBDBB861A9` |
| `learning_object_service.py` | 21,274 B（D-1 冻结，本轮未改） |
| `web/ui.py` | SHA256 前 16 位 `2FCF2FDE71D6DDB3`（未改） |
| `web/flow.py` | SHA256 前 16 位 `0534A2315299B738`（未改） |
| AI 调用 | **0** ｜ 本轮 0 修改（仅新增 2 个 audit 文件） |

## 16. 15 项问题逐项回答

| # | 问题 | 回答 |
| --- | --- | --- |
| 1 | 当前 `/review` 路由在哪里 | `web/app.py:173`（GET）与 `:201`（POST 带 name） |
| 2 | 当前 Review 数据入口在哪里 | `web/app.py:626 _review()` → `flow.need_relearn` / `flow.textbook_review_suggestions` / `flow.learner_name` |
| 3 | 当前 Review UI 在哪里 | `web/ui.py:881 review_page(ctx)` |
| 4 | D-1 LO 服务最合适的调用点 | flow 层新增函数内调用 `learning_object_service.needs_attention()`（可选 `mapping_coverage()`） |
| 5 | 是否需要修改 `web/flow.py` | **需要**（+1 只读函数） |
| 6 | 是否只修改 `web/ui.py` 即可 | **否**（ui 不得取数与计算；且 app 需 +2 行传参） |
| 7 | 是否需要新增路由 | **否** |
| 8 | 是否需要新增数据库结构 | **否** |
| 9 | 是否需要修改 `learning.db` | **否** |
| 10 | vocabulary revisit 与 LO 建议如何共存 | 并置展示 + 层级文案；不动池逻辑 |
| 11 | 是否存在重复显示风险 | **存在**（G1；当前未触发；先并置，真机验证后按需最小去重） |
| 12 | 当前 Review 是否存在自动跳转/自动执行风险 | **否**（纯链接与表单），D-2 必须保持 |
| 13 | D-2 最少需要修改哪些文件 | `web/flow.py`、`web/ui.py`、`web/app.py` = **3 个文件** |
| 14 | D-2 最少需要增加多少测试 | **6 项**（+2 项可选） |
| 15 | 是否存在 D-2 的阻塞问题 | **无**（4 项非阻塞 GAP） |

## 17. D-2 推荐实施方案（仅方案，不实施）

1. **flow 层**：新增 `lo_review_section(conn, learner_id, contentpack_path)` → 调 `needs_attention()`，try/except 包裹（失败返回空），输出 `[{lo_id, lo_type, 教材位置, display_text, diagnosis_label, suggestions[]}]`。
2. **app 层**：`_review()` 内 +2 行，把结果作为 `lo_section` 传入 `ui.review_page(ctx)`。
3. **ui 层**：在现有区块**之后**追加「教材学习建议」区块：有内容则逐条渲染 LO + `display_text` + 诊断标签 + 教材优先建议 + `去看看` 链接；空态显示"暂时没有需要再看的教材学习对象"；禁止等级/分数/排名/进度条/倒计时/"必须完成"等措辞。
4. **测试**：新增 §13 的 6（+2）项；不改任何既有测试。
5. **验证**：`/review` GET 零写入、AI=0、learning.db/contentpack/V1.2 未变；S24+ 真机走一遍 `/review` 观察重复观感。

## 18. 停止声明

本次为**只读审计**：未修改任何项目文件、未实施 D-2、未改 UI/flow/app、未改测试、未改数据库/教材/音频、未接入 AI、未重构。**完成报告后立即停止，等待下一条任务指令。**
