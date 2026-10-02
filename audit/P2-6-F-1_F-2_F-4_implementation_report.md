# P2-6-F-1 / F-2 / F-4 实施报告：教材正文 + Question 结构 + 音频活动锚定（第一批最小修复）

> 依据：V1.2.1（六·8 锚定原则 / 六·9 音频边界 / 七·3 原题型还原 / 七·9 答案事实）
> 本批只做 F-0/F-0-A 判定为**确定性可实施**的部分：不补答案、不接 AI、不切音频、不改教材事实。

- 实施时间：2026-09-13
- 项目根目录：`D:\ZhixueEnglish`
- 交付归档：本报告 `.md` / `.json`

---

## 1. 实施结论

**P2-6-F-1 / F-2 / F-4 第一批：PASS（含 1 项已确认的 NEEDS_REVIEW 与 1 处测试断言更正）**

| 验收项 | 结果 |
| --- | --- |
| A 孩子进入 Unit 后能看到真实教材正文 | ✅ 通过（新增 `/unit/<slug>/text`，S24+ 真机已打开） |
| B 练习 10 能看到题目 / 选项 / 回答控件 / 官方音频 | ✅ 通过（8 个选择控件 + 教材本页词框 + AU03） |
| C fill 能看到真实空位 | ✅ 通过（4 条以内联空位呈现，其余按教材空位数出输入框） |
| D match 能看到真实匹配结构 | ✅ 通过（教材项目 + 逐项作答框） |
| E judge 能看到判断控件 | ✅ 通过（6 个 F/O 判断组） |
| F 教材题不会偷偷变成 Vocabulary 拼写题 | ✅ 通过（26 条词汇型练习的教材原题全部可见） |
| G 同页多活动不互相串题 | ✅ 通过（按活动锚点取题；无法锚定则不返回题目） |
| H 音频仍是官方完整音频 | ✅ 通过（54 条不变，未切割；真机 206 分片请求成功） |
| I 无 AI 猜答案 / 猜切点 | ✅ 通过（AI 调用 0） |
| J 孩子不再被要求自行判断正式练习结果 | ✅ 通过（choice/fill/match 不再出现自评按钮，改为"提交作答"） |

**测试**：`web` 256 PASS / `learning` 112 PASS / `workbench` 50 PASS = **418 PASS / 0 FAIL / 0 SKIP**（原 397 项全部保留）。

---

## 2. 修改文件清单

| 文件 | 类型 | 说明 |
| --- | --- | --- |
| `web/exercises.py` | 修改 | 新增教材结构修正层（材料锚定 / 选项修正 / 空位修正 / 活动锚点取题）+ 重写 `build_questions` / `grade`（旧实现保留为 `_legacy_*`） |
| `web/ui.py` | 修改 | 新增 `unit_text_page`、教材原文入口卡、按原题型的练习页（`exercise_page` 重写，旧实现保留为 `_legacy_exercise_page`）、结果页措辞 |
| `web/app.py` | 修改 | 新增只读路由 `/unit/<slug>/text`；Unit 上下文新增 `text_block_count` |
| `web/content.py` | 修改 | 新增只读函数 `unit_text_sections()`（教材正文按 Unit → Section 读取） |
| `web/test_p2_6f_structure.py` | 新增 | 本批 21 项新测试 |
| `web/test_p2_3_exercises.py` | 修改（1 处断言） | 见 §22 说明：原断言依赖被确认为错误的目录选项值 |

> 未修改：`learning/`、`structured/`、`contentpack`、`learning.db`、Android、V1.2 / V1.2.1、教材与音频文件。

## 3. 每个文件具体修改

**`web/exercises.py`**

- 新增 `STRUCTURE_VERSION = "P2-6-F-1/F-2/F-4"`。
- 新增 `NOISE_OPTION_TEXTS`（5 个已确认噪声值）。
- 新增 `BLANK_FIX`（9 条空位修正，逐条附教材证据）。
- 新增 `EXERCISE_MATERIAL`（15 条教材原题材料 → contentpack `block_id`，含 A9/A10 几何重建）。
- 新增 `PAGE_WORD_BOX`（教材本页词框，A10 的选项来源，标注待人工核验）。
- 新增只读读取与解析：`_blocks`、`textbook_material`、`_checkbox_items`、`_slash_pairs`、`page_word_box`、`textbook_options`、`blank_count`、`_inline_blanks`、`_inline_choices`。
- 新增活动锚定：`_structure_v2`、`resolve_activity_id`、`_block_activity_map`（含 A9/A10 修正）、`sub_questions_for_activity`。
- 重写 `build_questions()`：教材原题按原题型产出 `textbook_task`；词汇自测改为 `vocab_selftest` 并存。
- 重写 `grade()`：教材原题只记录作答（`done`），不判分；词汇自测仍按词表规则判分。

**`web/ui.py`**

- `unit_page`：新增"教材原文"入口卡（显示真实段数）。
- 新增 `_material_block` / `_task_controls` / `_option_control` / `_record_block` / `exercise_page` / `unit_text_page`。
- 练习页结构改为：教材原题（要求 + 🎧 官方音频 + 教材原文 + 教材本页词框 + 待核验提示）→ 按原题型作答 → 词汇自测（若为词汇型练习）。
- 结果页：choice / fill / match 分支措辞为"教材没有提供可核对的答案，所以这里不判对错；你可以对照教材自己核对"。

**`web/app.py`**

- `_unit_path`：读取教材正文（只读）并注入 `text_block_count`；新增 `/unit/<slug>/text` 路由。

**`web/content.py`**

- 新增 `unit_text_sections()`：按「section 起始页 + 单元页范围」确定性读取 `content_block`，剔除页眉/页脚/侧栏与排版标记（活动号、图片标签）。

## 4. Question 恢复数量

| 教材原题型 | 练习数 | 已恢复为教材原题结构 | 说明 |
| --- | ---: | ---: | --- |
| choice | 12 | 12 | 其中 1 条（Unit 1 A4）经核验**不是选择题**，按口语任务呈现（不再伪装成选择） |
| judge | 1 | 1 | F / O 判断，6 个判断组 |
| fill | 45 | 45 | 教材空位按原题呈现 |
| match / order | 10 | 10 | 教材项目 + 逐项作答 |
| short_answer | 34 | 34 | 按活动锚点取题（无法锚定则不取题） |
| 合计 | 102 | 102 | 其余 56 条为反思 / 口语 / 写作等本无 Question 结构的任务 |

## 5. Choice 恢复数量

- 现在渲染真实选项控件的练习：**10** 条（kind=choice）+ 2 条词汇型练习的教材原题卡（`textbook_task.kind=choice`）= **12 条 choice 全部按教材事实呈现**。
- 其中 3 条为**勾选型**（教材原题是 "Read and tick"），使用复选框；其余为单选。
- **内联选择**（教材原题是"在正文中圈出正确词"）：`X:8D3E1E4E1B31`（Unit 1 A6，4 处）、`X:3DCE713706DE`（Unit 1 A7，6 处）→ 正文逐处呈现 2 选 1。

## 6. Fill 恢复数量

- 45 条 fill 全部产出 `textbook_task.kind == "fill"`。
- 其中 **4 条**以内联空位呈现（教材原句里直接出空），其余按教材空位数出输入框。
- 词汇型 fill（18 条）不再被词汇拼写替换；教材填空结构同时可见。

## 7. Match 恢复数量

- 9 条 match + 1 条 order = **10 条**全部按教材原题呈现（教材项目 + 逐项作答框）。
- 其中 6 条原本被降级为词汇拼写，本轮恢复。

## 8. Judge 恢复数量

- **1 条**（Unit 4 Developing ideas A2）：按教材原题生成 **6 个 F/O 判断组**（教材 6 个空）。

## 9. 噪声删除数量

| 噪声值 | 来源（教材证据） | 处理 |
| --- | --- | --- |
| `great teacher` | Unit 1 p19 页面小标题 | 删除 |
| `new start 19` | Unit 1 p19 页脚 | 删除 |
| `new start 23` | Unit 1 p23 页脚 | 删除 |
| `new start 15` | Unit 1 p15 页脚 | 删除 |
| `pun is a word with more than one` | Unit 5 p82 "Learning to think" 侧栏 | 删除 |
| Starter A2 的 a/b/c 三句 | 实为**同册 PDF 第 13 页**活动 3（Match the sentences…）的句子 | 以教材原页 ☐ 四句替换（原值不再作为选项） |

删除后的选项来源一律改为教材原页 ☐ 清单（`textbook_options`），共影响 5 条练习；U5 A3 保留 a–d 四个真实选项。

## 10. Blank 修正数量

| # | 练习 | 原值 | 修正 | 教材证据 |
| --- | --- | ---: | ---: | --- |
| 1 | `X:88C641F5FA05` Starter A1 | 0 | **6** | P14 印刷书写线 6 条（y=515.2 / 533.2×3 / 551.2 / 569.2） |
| 2 | `X:F21C9E2036F7` Unit 1 Starting out A2 | 0 | **6** | P20 表格 3 列 × 3 行，第 1 行为示例 |
| 3 | `X:2CA1B9F43CB3` Unit 1 RfW A5 | 0 | **6** | P32 Mia 回信印刷书写线 6 条 |
| 4 | `X:24C80DAE6FAE` Unit 2 U-I A6 | 0 | **6** | P40 印刷书写线 6 条 |
| 5 | `X:6BB271F5F101` Unit 5 U-I A6 | 0 | **3** | P88 印刷书写线 3 条 |
| 6 | `X:5BCC4D6DC928` Unit 6 U-I A6 | 0 | **3** | P104 印刷书写线 3 条 |
| 7 | `X:AC02902827A8` Unit 1 U-I A1 | 9（被截成 8） | **9** | 恢复教材原题空位数 |
| 8 | `X:41B8D362116C` Unit 2 U-I A7 | 9（被截成 8） | **9** | P40 正文 9 处编号空位 |
| 9 | `X:0AD8920218D8` Unit 5 RfW A3 | 9（被截成 8） | **9** | P95 印刷书写线 9 条 |

共修正 **9 条**（其中 6 条修正计数、3 条解除 8 的上限）；其余 fill 保持原目录值不动。

## 11. 词汇短路修复数量

- 受影响练习：**26 条**（fill 18 + match 6 + choice 2），全部按教材原题型呈现。
- 词汇自测**能力保留**：词汇型练习仍带本单元词表自测（4 题，按词表规则判分），作为独立卡片与教材原题并存。

## 12. 音频锚定修复数量

- **题目按活动锚定**：`sub_questions_for_activity()` 取代"按页取题"；contentpack `sub_question` 13 条全部改走「题面 → 教材内容块 → 活动」链路，无法唯一锚定时**不返回题目**。
  - 实例：Starter A4（`X:FA515DD3ECF0`）此前会拿到同页 A3 的题，现在返回空。
- **A9 / A10 几何重建**：2 条活动（Starter GET_READY A9 / A10）按教材原页 y 区间修正块归属。
- 音频本身：**0 条修改**（54 条不变，未切割）。

## 13. A9 / A10 结果

| 活动 | 修正前（旧 `text_references`） | 修正后（教材原页几何） | 验证 |
| --- | --- | --- | --- |
| A9 Match the words and expressions with the pictures | 含 A10 的 8 空对话块 | 只含 A9 的指令 + 词框（P10:B1 / P10:B14） | 新测试 `test_06`：A9 材料含 `sports trousers`，不含 `Nana` |
| A10 Listen and choose. | 只剩活动号块 | 含指令 + 8 空对话（P10:B15 + B5–B13） | 新测试 `test_06`：A10 材料含 `Nana`，不含 `sports trousers` |

> 结论：A9/A10 的块归属**可由教材原页几何确定性修正**，已修复；A10 的"词框是否属于本题"仍保留人工核验标记（见 §14）。

## 14. NEEDS_REVIEW 数量

- 练习页携带待核验说明的练习：**6 条**，共 **7 条说明**：
  - A10（2 条：教材原题只说"听录音并选择"；本页词框归属待核验）
  - Unit 1 A4（教材原题是结对口语任务，不是选择题）
  - Unit 4 A2（每空填什么、F/O 需听音频后人工核验）
  - Unit 1 Starting out A2（表格填空结构）
  - Unit 1 RfW A5（补全回信：印刷书写线 6 条）
  - order 类（依赖图片顺序）
- 页面**不出现英文串 `NEEDS_REVIEW`**（V1.2.1 七·6：待确认信息不进入孩子界面），只出现自然中文说明。
- 仍未闭合、需人工核验的全局事项（继承 F-0/F-0-A）：173 道客观题答案、127 道主观题评分要点、41 条音频与题目语义对应、A10 词框归属。

## 15. 答案事实 = 0 的保护结果

- `BLANK_FIX` / `EXERCISE_MATERIAL` / `PAGE_WORD_BOX` **不含任何答案**（只有空位数、教材原文块、教材原页词框）。
- `build_questions()` 不产生 `answer` 字段（词汇自测的 `answer` 来自**教材词表**，是既有能力）。
- `grade()` 对 choice / fill / match 只返回 `result="done"`（事实记录），`answer_available=False`，`answer_status=NO_RELIABLE_SOURCE`。
- 新测试 `test_13` 逐条验证：157 条练习均 `answer_available == False`。

## 16. AI 调用

**0**（未接入任何模型；`web/ai_grading.py` 的 provider 仍为 `None`，未修改）。

## 17. 网络请求

**0**（除局域网内 S24+ 与本机 Web 服务之间的本地请求外，无任何外部网络请求）。

## 18. 测试结果

| 套件 | 结果 |
| --- | --- |
| `web/`（含新增 `test_p2_6f_structure.py` 21 项） | **256 PASS** |
| `learning/` | 112 PASS |
| `workbench/` | 50 PASS |
| 合计 | **418 PASS / 0 FAIL / 0 SKIP** |

新增测试覆盖（任务书 §十九 15 项要求全部覆盖）：Exercise 10 结构 / 选项 / 作答控件 / AU03 音频；同页不串题；A9·A10 锚定；choice 不退化为自评；fill / match 不退化为词汇拼写；judge 有真实控件；噪声不进选项；9 条空位修正；不生成答案；教材练习不因词汇变成词汇题；词汇能力保留；另加 F-1 正文页 3 项 + 真机 HTTP 冒烟 3 项。

## 19. 正式 DB 保护结果

| 对象 | 实施前 | 实施后 | 结论 |
| --- | --- | --- | --- |
| `learning.db` SHA256 | `DBAB743BF6D8F0A3832E599CBD5DD2267F008FD9FB3903BACEA93780A466D633` | **同左** | ✅ 未变 |
| `learning.db` mtime / 大小 | 2026-09-12 23:15:13 / 118,784 B | **同左** | ✅ 未变 |
| contentpack SHA256 | `ACEBC8C29CF5D11BAB50BF7962FBEE5DE42CD9CFC7FE48AB6316699D265E1A3F` | **同左** | ✅ 未变 |
| `structured/` / `learning/` / Android / 教材 / 音频 | — | 未修改 | ✅ |

所有测试均使用 `%TEMP%` 下的 learning.db 副本。

## 20. S24+ 结果

真机：**SM-S9260（Samsung S24+，Android 16）**，通过无线调试连接（设备 IP 192.168.2.7）。

| 验证项 | 证据 | 结果 |
| --- | --- | --- |
| App 启动 | logcat：`ZhixueWebView: 页面加载完成: http://192.168.2.3:8770/` | ✅ |
| 首页 → 教材中心 | 服务端日志：`GET /textbook 200` | ✅ |
| 教材中心 → Starter Unit | `GET /unit/starter 200` | ✅ |
| Unit → 教材原文 | `GET /unit/starter/text 200`；页面含 `Ms Chen`，不含页脚 "A new start  17" | ✅ |
| Unit → 教材练习 | `GET /unit/starter/exercises 200` | ✅ |
| 进入练习 10 | `GET /exercise/478514a69c05 200`（App 日志：页面加载完成） | ✅ |
| 题目 / 选项 / 回答控件 | 设备侧抓取页面：8 个 `<select name="t1..t8">`、教材本页词框、`提交作答` 按钮 | ✅ |
| 官方音频 | 设备侧 `curl -r 0-2048 /audio/official/AU03.mp3` → **206**；页面含 🎧 | ✅ |
| fill 真实空位 | 设备侧抓取 Starter A1 页：6 个内联空位输入 + 教材原文（`Mr Pan`） | ✅ |
| 无黑屏 | 练习 10 截图：dark=4.98%、near-black=3.77%、文本行 277 → 正常渲染 | ✅ |
| 无 500 / 404 | 上述所有 URL 均 200 | ✅ |
| 无崩溃 | logcat 无本应用 FATAL EXCEPTION / ANR（仅有其它 App 的 Google 服务网络告警） | ✅ |

> 说明：服务端在验证前需要重启以加载新代码（原 0.0.0.0:8770 进程为先前启动的旧代码实例），已重启；验证结束后新实例**保持运行**，可直接用手机继续体验。
> 受环境限制（本次无法查看图片），真机验证采用「盲点击 + 服务端访问日志/设备侧抓取 + 截图程序化分析」闭环，未做人工目视检查。

## 21. 孩子可见变化

1. **Unit 里多了一张"教材原文"卡**：点进去能直接读到教材原页的对话与短文（例：Unit 1《The first lesson》整篇），页眉页脚不会混进来。
2. **练习 10 不再是"一段音频 + 我完成了"**：现在能看到"Listen and choose."、教材原页的 8 空对话、本页词框的 9 个词，每个空都能从词框里选一个，并保留官方录音 🎧。
3. **选择题看到真选项**：Unit 3 A3、Unit 6 A1、Starter A2 这类"打勾"题出现真正的勾选清单；Unit 1 A6/A7 在正文里逐处二选一。
4. **填空题看到真空位**：例如 Starter A1 的四个句子直接带着空格出现，孩子在被挖空的原句上填写。
5. **判断题出现 F/O 控件**：Unit 4 A2 的 6 个空各有"F（事实）/ O（观点）"两个选择。

## 22. 未解决问题（诚实记录）

| # | 问题 | 状态 |
| --- | --- | --- |
| 1 | 教材练习仍**不能正式判分**（157 练习 / 360 题无可靠答案） | 等 F-3 人工核验答案 |
| 2 | A10 的"本页词框是否属于本题" | NEEDS_REVIEW（已按教材原页词框呈现并标注） |
| 3 | Unit 1 A4 是结对口语任务，尚无口语作答载体 | 归入 F-5 |
| 4 | writing 7 条仍无文本作答框；speaking 16 条无载体 | 归入 F-5 |
| 5 | 45 条 fill 中 41 条未以内联空位呈现（仅按空位数出输入框） | 需要逐条确认教材材料块，属后续批次 |
| 6 | 1 处既有测试断言被更正 | 见下 |

**关于 test_p2_3_exercises.py 的 1 处断言更正**：原断言要求页面出现"目录里第一条选项的文本"，而该文本经核验属于**同册 PDF 第 13 页另一个活动**（并非本练习的选项）。本轮把它改为"页面必须出现**本练习渲染出的**第一条选项文本"，语义仍是"选择题要渲染选项"。这不是掩盖问题，而是原先的断言把错误数据当成了正确期望；其余 255 项 web 测试与 162 项 learning/workbench 测试未做任何修改。

## 23. 下一阶段建议

1. **F-3 答案补齐（人工核验，优先级最高）**：先做 choice + judge 共 **33 题**（体量小、规则判分确定），跑通"人工核验 → 规则判分 → Evidence"链路，再把 fill 124 题分批补。
2. **F-5 UI 作答控件**：为 writing 增加文本输入框、为 speaking 设计最小动作（"我说完了 / 再说一次"）。
3. **F-7 Evidence 接入**：答案补齐后让教材练习真正产出 `correct / partial / incorrect`，进入既有 `evidence_service`，`/review` 才会有真实内容。
4. **后续批次**：把内联空位渲染扩展到其余 fill（需要逐条确认材料块）；把教材正文按活动粒度细分（当前按 Section 粒度）。
5. **不要做**：不要用 AI 猜答案或猜音频切点；不要为了让页面"看起来有题"而引入未经验证的选项。

---

## 附：文件 SHA256（本批修改/新增）

| 文件 | SHA256（前 16 位） |
| --- | --- |
| `web/exercises.py` | `71B62DCC52C6502D…` |
| `web/ui.py` | `0D86391E57CE9E7A…` |
| `web/app.py` | `07E9B01FC61DAB61…` |
| `web/content.py` | `FE203CD345175AA7…` |
| `web/test_p2_3_exercises.py` | `92DD20E16D8474DD…` |
| `web/test_p2_6f_structure.py` | `FD34192B27BD1286…` |

**本次实施未修改教材事实、未新增答案、未接入 AI、未切割音频、未改动数据库与 Android。**
