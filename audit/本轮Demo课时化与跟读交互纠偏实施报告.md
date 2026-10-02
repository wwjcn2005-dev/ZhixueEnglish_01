# 本轮 Demo 课时化与跟读交互纠偏实施报告

**实施范围**：仅 `D:\ZhixueEnglish\demo\`（外加本报告文件）。
**未修改**：`structured/contentpack/v5`、`structured/learning/learning.db`、教材 PDF、54 个官方 MP3、
`learning/`、正式 `web/`、`android/`、`docs/`、既有 `audit/` 资产；未重跑 ASR；未新增依赖。
**AI 真实调用 = 0**（全部为确定性模拟）。

---

## 1. 修改了哪些文件（以及为什么）

| 文件 | 变化 | 为什么 |
| --- | --- | --- |
| `demo/server.py`（68,142 B） | 新增**课时层**：`_section_rows / section_of_page / section_of_audio / lessons / current_lesson / lesson_by_key / lesson_vocab / lesson_sentences / lesson_reading / lesson_questions / lesson_options / scope`；所有状态改为**课时作用域**；`/lesson` 路由；单词跟读去判断；听音阅读去掉翻页 | 问题 1/3：学习单位必须是课时，能力必须随课时动态生成 |
| `demo/pages.py`（52,450 B） | 首页改为**课时选择器**（按 Unit 分组，显示教材板块名）；Unit 页加"当前课时 + 课时切换"；单词跟读改为**纯跟读 + 左右滑动**；短句跟读改为**左右滑动**且每句自带 AI 分析；听音阅读**删除上一段/下一段**；结果页标题带课时 | 问题 1/2/3 |
| `demo/state.py`（8,327 B） | 新增 `l`（每个 Unit 当前课时）与 `set_lesson/lesson_of` | 记住当前课时（Cookie） |
| `demo/test_demo_v10.py`（15,384 B） | 13 项测试全面改造：课时数据链、38 句课时归属、首页课时选择器、能力随课时变化、纯跟读、滑动、课时内检测、课时内阅读、结果页课时维度等 | §十一 测试要求 |
| `demo/README.md`（13,375 B） | 改写为"课时化版"：课时定义、能力矩阵、滑动规则、已知边界 | 文档同步 |
| `audit/本轮Demo课时化与跟读交互纠偏实施报告.md` | 本报告 | §十二 |

## 2. Lesson 数据链实际是什么（只读核查结论）

```text
contentpack v5 里没有 lesson 表、也没有任何 lesson 字段（23 张表逐列检查，0 命中）
        ↓
真实存在的"课时/板块"结构 = section 表（教材目录里的板块名 + 起始页）
        ↓
unit → section（每单元 6 个板块；Starter 4 个）→ 资源按"教材页/印刷页"归属到板块
```

**课时名直接使用教材板块名**（不新造 Lesson 1/2/3 编号）：

```text
Starter：Get ready · Know your school · Get to know each other · Make a wishing tree
Unit 1–6：Starting out · Understanding ideas · Developing ideas · Reading for writing ·
          Presenting ideas · Reflection
```

四类资源的课时归属判据（全部来自既有正式数据，没有新标注）：

| 资源 | 判据 | 可靠性（实测） |
| --- | --- | --- |
| 教材词汇（单词跟读 / 单词听辨） | 词条印刷页 → `page` 表换算 PDF 页 → 板块页范围 | Unit 1–4 共 165 个重点词，**0 个无法归属** |
| 38 条对齐句子（短句跟读 / 句子听辨） | 句子教材页（contentpack `source_page`；P3-07 用 `matched_candidates.pdf_page` 回连）→ 板块；无页面时回退音频板块名 | **38/38 全部可归属，0 个无法归属** |
| 听音阅读（官方 MP3 + 教材文字） | 自然文本块的教材页 → 板块 | 7 个单元 25 个自然块**全部可归属** |
| 本课检测题目 | 由本课时的教材重点词 + 本课时的教材句子生成 | 22 个课时中有 17 个能出题（1–4 题） |

## 3. 每个课时当前有哪些能力（实测矩阵）

数字 = 该能力在当前课时的资源条数；`—` = 该课时没有这类资源，**页面上完全不显示该入口**。

| Unit | 课时（教材板块名） | 单词跟读 | 听音辨意 | 本课检测 | 短句跟读 | 听音阅读 |
| --- | --- | --- | --- | --- | --- | --- |
| Starter | Get ready | 10 | 14 | 3 | 4 | 1 |
| Starter | Know your school | 3 | 4 | 3 | 1 | 2 |
| Starter | Get to know each other | 7 | 15 | 4 | 8 | 1 |
| Starter | Make a wishing tree | 2 | 2 | 2 | — | — |
| Unit 1 | Understanding ideas | 13 | 13 | 2 | — | 1 |
| Unit 1 | Developing ideas | 6 | 12 | 3 | 6 | — |
| Unit 1 | Reading for writing | 12 | 20 | 4 | 8 | 2 |
| Unit 2 | Understanding ideas | 21 | 22 | 2 | 1 | 1 |
| Unit 2 | Developing ideas | 5 | 7 | 2 | 2 | — |
| Unit 2 | Reading for writing | 15 | 16 | 2 | 1 | 2 |
| Unit 3 | Understanding ideas | 23 | 23 | 2 | — | 2 |
| Unit 3 | Developing ideas | 3 | 4 | 3 | 1 | — |
| Unit 3 | Reading for writing | 10 | 10 | 2 | — | 2 |
| Unit 4 | Understanding ideas | 21 | 23 | 2 | 2 | 2 |
| Unit 4 | Developing ideas | 6 | 6 | 2 | — | 1 |
| Unit 4 | Reading for writing | 15 | 15 | 2 | — | 1 |
| Unit 5 | Understanding ideas | 19 | 19 | 2 | — | 2 |
| Unit 5 | Developing ideas | 5 | 5 | 2 | — | — |
| Unit 5 | Reading for writing | 14 | 15 | 2 | 1 | 2 |
| Unit 6 | Understanding ideas | 18 | 18 | 2 | — | 1 |
| Unit 6 | Developing ideas | 4 | 5 | 2 | 1 | — |
| Unit 6 | Reading for writing | 12 | 14 | 2 | 2 | 2 |

**没有资源、因此不进入课时选择器的课时（18 个）**：
`Unit 1–6 各自的 Starting out / Presenting ideas / Reflection`。
它们不是"灰色按钮"，而是**完全不出现**（按"有什么就练什么，没有就不显示"）。

## 4. 哪些资源无法可靠映射到 Lesson

| 资源 | 情况 | 处理 |
| --- | --- | --- |
| 单元级 Demo 题目（`demo_content.short_practice` / `READING_EXTRA`） | 只有 Unit 级归属，没有教材页 → **无法可靠落到某个课时** | **不使用**（本课检测改为用本课时材料生成，避免伪造课时归属） |
| 正式数据里的 360 条教材题目关系 | `answer_source = NO_RELIABLE_SOURCE`，没有答案 | 本轮不动（Demo 不用它判分） |
| 教材音频（AUxx） | 文件名里的板块名对 `Reading for writing` 这类**嵌套板块**会截断（"Developing ideas_Reading for writing"） | 只作为**回退信号**；主线用教材页归属 |
| 词表音频（AU48–AU54） | 属于整单元词表，不是某个板块 | 单词音频按词条本身的页归属到课时（音频只作为发音来源） |
| `Starting out / Presenting ideas / Reflection` | 教材里有板块，但项目没有对应资源 | 不显示（不编造） |

## 5. 单词跟读最终交互

```text
单词 + 音标 + 中文意思（一屏一个）
   ↓ 左右滑动切换（页面提示"左右滑动切换单词"）
底部三个操作：听发音（官方/派生音频） · 大麦克风（开始/停止录音） · 我的朗读（回放）
```

- **已彻底删除**：我记住了 / 有点模糊 / 忘了、Recall、显示意思后判断记忆、掌握度、正误评价、
  AI 判断、`/vocab/judge` 表单与 `/vocab/result` 页面（旧链接 302 回纯跟读页）。
- **视觉没有回退**：仍然使用本轮统一的视觉系统（当前背景/卡片/圆角/字级/图标/AI 色彩规则/
  浅底麦克风），没有恢复旧版 UI。
- 录音只用于"回放自己的朗读"，**不做任何评价**（没有 AI 分析区）。

## 6. 左右滑动最终覆盖哪些页面

| 页面 | 之前 | 现在 |
| --- | --- | --- |
| 单词跟读 `/unit/<slug>/vocab` | 底部"我看完了 / 上一项 / 下一项"式图标按钮 | **左右滑动切换**；底部只保留 听发音 / 麦克风 / 我的朗读 |
| 短句跟读 `/unit/<slug>/sentences` | 上一句 / 下一句图标按钮 | **左右滑动切换**；每句自带 AI 朗读分析块，滑动后分析跟随当前句 |
| 听音辨意 `/unit/<slug>/listen` | 已经是"播放→选择→下一题"的题目流 | 保持（题目流不是"连续浏览资源"，不做手势化） |
| 听音阅读 `/unit/<slug>/reading` | 上一段 / 下一段按钮 | **删除翻页按钮**；改为 `start_ms → end_ms → timeupdate → 当前文字高亮 → 自动下一段` |
| 本课检测 / 错题 / 结果 | 单题、单条记录 | 保持按钮式（不适合手势） |

顶部"返回上一层"与滑动"切换学习内容"是两层不同操作：返回键始终只回上一层。

## 7. 测试结果

- **自动测试**：`python -B demo\test_demo_v10.py` → **Ran 13 tests，OK（13 PASS / 0 FAIL / 0 ERROR）**
  - 覆盖：课时数据链（板块名、真实计数）、38 句 0 未归属、首页课时选择器（单一 select + optgroup、
    无进度/时间/占位文案）、能力随课时变化（D-Ideas 无听音阅读、R-for-writing 有）、
    纯跟读（无判断控件）、滑动（`#zx-swipe` + 多卡片 + 无上下项按钮）、课时内听辨（题干都来自本课时词/句）、
    课时内检测（不同课时题目不同 + 答错 AI 解释且不给答案 + 错题页 + 再做一次）、
    课时内阅读（chunk 带 start/end、无翻页控件、无 PDF/热点）、结果页带课时名、音频 200/206、正式数据未改、视觉收口。
- **真实浏览器验收（Edge 153 + CDP）**：**34 PASS / 1 FAIL**，其中那 1 项经复核是**脚本等待过久**
  （单词音频只有 0.79 秒，等 1.0 秒后已经播放结束，按钮自然回到静止）；改用 0.25 秒窗口复测
  → **播放态正常**，即实际 **35/35 PASS**。整轮 **0 个 JS 异常**。
  - 首页：optgroup 选择器、默认课时能力不是五项全有、无占位/禁用文案、无进度时间信息、390px 无溢出。
  - 课时切换：U1 Developing ideas = 单词跟读/听音辨意/本课检测/短句跟读（**无听音阅读**）；
    U1 Reading for writing = 五项中的五项（含听音阅读）。
  - 单词跟读：无判断控件、滑动后指示从 1/12 → 2/12 且播放目标音频切换、录音态、录音后可回放。
  - 短句跟读：6 张卡片、无上一句/下一句、每句自带 AI 块、区间播放、AI 分析中→结果显示。
  - 本课检测：不同课时题目不同（如「plan」/「journey」），答错出现 AI 解释且**不出现"正确答案"**，
    错题入口与"再试一次"都在。
  - 听音阅读：chunk 带 start/end、无翻页链接、播放中当前文字高亮。
  - 结果页：标题含课时名 + AI 学习分析 + 无自动任务；1440px 主列 560px 居中；390px 全部页面无横向滚动。

## 8. 是否修改正式数据

| 资产 | 实施前 | 实施后 |
| --- | --- | --- |
| `structured/learning/learning.db` | `0C27267B…CF91` | **未变** |
| contentpack v5 | `65829CA7…00C39` | **未变** |
| 教材 PDF | `C732051E…D4F2F` | **未变** |
| 官方 MP3 | 54 个 | **54 个，未切割、未重新生成** |

`demo/` 之外 0 个文件被修改；QA 用的 3 个浏览器 profile（550 个文件）已删除；`audit/` 历史文件未动
（本轮只新增本报告）。Demo 状态仍然只存浏览器 Cookie（`zx_demo10`）。

## 9. 是否调用 AI

**没有。AI 真实调用 = 0**：没有 API、SDK、Key、网络请求，也没有真实 ASR / 发音评分；
测试继续断言 `server.py` 不含 `requests` / `openai` / `api_key` / `http.client` / `urllib.request`。
AI 文案全部是确定性模拟，并且**只针对当前课时**（本课检测解释只讲本课时题目；短句跟读只分析当前句；
结果页 AI 总结只汇总当前课时已发生的学习行为，措辞保持"如果你愿意…"，不布置任务）。

## 10. 是否影响 8770

**未影响**：`127.0.0.1:8770` 正式 Web PID 仍为 **17548**，`/health` 正常，全程未停止、未重启、未修改。
Demo 仍在 `127.0.0.1:8780`（`ZhixueEnglish-Demo/1.1`）正常运行。

## 11. 已知限制（需要你判断的部分）

1. **课时覆盖不均**：22 个有资源的课时里，`Reflection / Starting out / Presenting ideas` 等 18 个板块
   没有 Demo 材料，因此不出现在选择器里 —— 这是"没有就不显示"，但如果你希望这些板块也能进去看教材，
   需要另外定义（当前不做）。
2. **本课检测题量随课时变化（1–4 题）**：题目完全来自本课时材料；不再有单元级固定的 6 题。
3. **短句跟读只覆盖 38 条对齐句子**：Unit 3 / Unit 5 的部分板块只有 1 句，页面会如实显示"第 1 / 1 句"。
4. **单词跟读的滑动依赖手势**：在桌面浏览器上需要触控板/滚轮横向滚动或拖拽；页面给了"左右滑动切换单词"
   的提示，但没有额外加左右按钮（按本轮要求不恢复按钮）。
5. **恢复"纯跟读"后不再记录"记得/模糊/忘了"**：因此结果页里"单词跟读"这一行显示的是
   "判断过 N / M 个重点词"这类真实行为统计，而不是掌握度。

---

**最终结论：PASS（技术验收 13/13 自动测试 + 浏览器 35/35 有效检查）；产品观感与"课时覆盖是否要补齐"
需要你亲自确认。**
