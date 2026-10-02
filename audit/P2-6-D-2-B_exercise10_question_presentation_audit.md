# P2-6-D-2-B Exercise 10 题目呈现专项只读审计

**结论：问题确认（P1）** — "练习 10" 在当前系统中**没有可作答的题目结构**，页面只呈现"一句指令 + 完整听力音频 + 自评按钮"，因此**无法产生有效 Evidence**。

- 审计时间：2026-09-13 ｜ 项目：`D:\ZhixueEnglish` ｜ 只读（0 修改），AI 调用 0

## 1. 审计结论

- **"一点文字 + 一大段语音"** = 教材原题（听录音选择）在当前数据下**选项/题干结构缺失**，UI 按设计降级为"自评"，而不是 CSS 隐藏或流程丢数据。
- **根因分类：R2 + R3 + R9**（教材解析/数据缺失 + 题目结构错位），**非** R5/R7。
- **严重程度：P1**（孩子无法完成该练习；且不能产生有效判断证据）。
- 同类问题共 **5 条**（choice/judge 共 13 条中 options 为空的 5 条），非孤例。

## 2. Exercise 10 身份定位

| 项 | 值 |
| --- | --- |
| exercise_id | `FLTRP-EN-7A-2022CUR:X:1C4143922B1C` |
| textbook | `FLTRP-EN-7A-2022CUR`（外研版七年级上册） |
| unit / section | `Starter` / `GET_READY` |
| activity | Starter GET_READY A10（教材第 5 页） |
| 题型 | `choice`（"Listen and choose."） |
| audio | `FLTRP-EN-7A-2022CUR:AU03`（`03_Starter_Get ready_10 Listen and choose.mp3`，58.2 s，耳机图标 ✅） |

**"练习 10"编号来源**：UI 卡片文本 `教材第 {textbook_page} 页 · 练习 {exercise_no}` → 孩子看到的"练习 10" = **`exercise_no = 10`**（Starter A10），不是数据库自增 id。

## 3. 教材原始事实

- 教材 Starter / Get ready / 第 5 页 A10 的指令为 **"Listen and choose."**，是一道**听力选择题**（教材页面提供题目与可选内容，音频为对应听力材料）。
- 因此"存在明确题目"这一事实成立；**"一点文字 + 长音频"不是教材原设计**，而是当前数据只取到了指令与音频、未取到题目/选项结构。

## 4. contentpack 数据

- `learning_item(item_type='exercise')` 中存在该练习条目（`item_id` 与 `exercise_id` 同为 `X:1C4143922B1C`）。
- `audio_asset` 含 `AU03`，`audio_mapping` 指向对应活动（P2-3 证据链 CONFIRMED）。
- contentpack **没有**该题的选项/题干结构化字段（其模型只有 activity / content_block / sub_question 13 行，不足以表达选择题选项）。

## 5. exercise_catalog_v3 数据（实测）

```text
exercise_id   FLTRP-EN-7A-2022CUR:X:1C4143922B1C
unit/section  Starter / GET_READY      exercise_no 10    textbook_page 5
question_type choice                   type listening_icon=True
instruction   "Listen and choose."
audio_id      FLTRP-EN-7A-2022CUR:AU03
questions     2 条，text 内容为"对话正文"（如 "Nana: Hi, Wang Tao. What are you going to wear…"）
options       []            ← 缺失
check_items   []            ← 缺失
blanks        8             ← 与"选择题"不符（应为对话中的空白计数被串入）
```

**关键判断**：catalog 中 `options` 为空、`questions[].text` 为对话原文而非题干 → 属**情况 B（catalog 无题目结构，但教材原始有题目）**并叠加**情况 D（题目结构被错误字段消费：对话文本当作 question、blanks 误计）**；**不属**情况 A（有数据未渲染）。

## 6. Question / Prompt 数据

- 现有模型没有独立 Question 实体：`exercise.questions[]` 仅为正文片段，无法支撑"题干 + 选项"渲染。
- `P2-4 exercise_question_relations_v3` 对该练习的 6 条题记录里 `related_vocabulary` 有值、无选项结构 → 说明 P2-4 也未抽到选项。

## 7. Audio 数据

| 项 | 值 |
| --- | --- |
| audio_id | `FLTRP-EN-7A-2022CUR:AU03` |
| 文件 | `03_Starter_Get ready_10 Listen and choose.mp3` |
| 时长 | 58.2 s（含 6 题材料，符合"完整听力材料"形态） |
| 类型 | 教材官方听力音频（非 TTS、非派生） |
| 与 Exercise 关系 | P2-3 证据链 CONFIRMED（指令文本一致 + 耳机图标） |
| 多题共享 | 一个音频服务该活动的多道题（`audio_scope=activity`，符合 P2-6-C-4-A 结论） |

**模型检查（Audit §九）**：`Audio Resource ≠ Exercise ≠ Question ≠ Evidence` — 本例中 Audio 正确、Exercise 存在，**缺的是 Question 结构**。

## 8. Exercise → Question → Audio 关系

```
教材 A10（有题目：听录音选择）
   ↓ 解析
contentpack：只有 activity / 对话块，无选项结构          ← 断点 1（R2/R3）
   ↓
exercise_catalog_v3：question_type=choice，options=[]，questions=对话正文，blanks=8
                                                          ← 断点 2（R9/R4）
   ↓
build_questions()：choice 且无 options → 降级 kind="self_check"
   ↓
HTML：指令 + 🎧 音频 + "我完成了这次练习"（无任何作答控件）  ← 断点 3（R6 表现，因数据缺失）
```

## 9. Web Flow 链路（实测）

- 路由：`app._exercise_get` → `ex_mod.build_questions(e, cp)` → `ui.exercise_page(ctx)`。
- 实测渲染结果：`kind=self_check`、`questions=0`、`options=0`、`items=0`；HTML 含音频与指令，**不含** `type="radio"` / `<input name=` / `<textarea`，含自评按钮。
- **Flow 未丢数据**：flow 忠实渲染了 catalog 提供的结构；问题是 catalog 里本就没有可作答结构。

## 10. HTML / DOM 呈现

| 检查 | 结果 |
| --- | --- |
| HTML 是否含 Question | ❌ 无（`questions=0`） |
| 是否含选项控件 | ❌ 无 |
| 是否含答题输入 | ❌ 无 |
| 是否含音频 | ✅ `🎧` + `/audio/official/AU03.mp3` |
| 是否含自评入口 | ✅ "我完成了这次练习" / "还想再看一遍" |
| HTML 长度 | 9,370 B（与真机"只有一点文字+音频"一致） |

## 11. CSS / 移动端观察

- 无 CSS 隐藏、无 `display:none`、无颜色与背景同色问题——因为**HTML 中本就没有题目元素**；
- 真机上看到的留白来自"卡片内容很少 + 音频元素占高"，不是布局溢出（无横向滚动）。

## 12. S24+ 观察

真机（SM-S9260）此前进入该练习时观察到"一点文字 + 一大段语音"；本次审计在服务端复现同一 HTML 结构（无题目控件），与真机表现一致 → **真机无额外 WebView 特有渲染问题**。

## 13. Evidence 可产生性

| 检查 | 结果 |
| --- | --- |
| Question 是否存在 | ❌ |
| answer / judgment 是否存在 | ❌（无作答控件） |
| task_type | ✅ 存在（`choice`，由 `exercise_catalog_v3.question_type` 派生） |
| exercise_id | ✅ 存在（`X:1C4143922B1C`） |
| learning_record 写入链 | ✅ 存在（自评提交会写 `done`） |
| 是否只有"听了音频"而没有作答证据 | ✅ **是** |

**结论**：孩子在该页面最多产生 `done`（自评）→ 按 V1.2 **不计为有效判断证据** → 该练习对 LO 掌握判定**无贡献**。这是本问题的实质影响（P1）。

## 14. LO 映射情况

- 该练习因 `listening_icon=True / audio_required=True` 命中 C-2 规则 **R1 → LISTENING LO**（`LO:…:LISTENING:<hash>`），映射本身正确。
- **映射并不会掩盖问题**：LO 映射只决定"证据归属哪个学习对象"，而本例**根本没有有效证据**（自评不计），因此该 LISTENING LO 永远拿不到这条练习的证据。

## 15. 根因分类 R1–R10

| 分类 | 判定 | 证据 |
| --- | --- | --- |
| R1 教材原始事实本身如此 | ❌ | 教材 A10 确有题目 |
| **R2 教材解析/数据缺失** | ✅ | contentpack 无选项/题干结构 |
| **R3 exercise_catalog_v3 数据缺失** | ✅ | `options=[]`、`questions` 为对话正文 |
| R4 Exercise → Question 映射错误 | ⚠️ 部分 | 对话文本被当作 question |
| R5 Flow 丢失 Question | ❌ | flow 忠实渲染，无丢数据 |
| R6 HTML/UI 未渲染 Question | ⚠️ 表现 | 因数据缺失而降级 self_check（非渲染 bug） |
| R7 CSS/移动端显示问题 | ❌ | HTML 中无题目元素 |
| R8 音频与 Exercise/Question 关系错误 | ❌ | 音频映射 CONFIRMED |
| **R9 多 Question / 单 Audio 建模问题** | ✅ | 6 题共享 1 音频；`blanks=8` 与选择题不符 |
| R10 需人工查看教材原页 | ⚠️ 建议 | 若将来补齐选项，需人工核对教材原页 |

---

## 16. 是否违反 V1.2 原则

| 原则 | 判定 |
| --- | --- |
| Exercise / Question / Evidence 三者分离 | ✅ **未违反**（当前实现严格分离；问题在于 Question 结构缺失） |
| Evidence-first | ⚠️ **实质受影响**：该练习无法产生有效证据（自评不计），与"教材练习应产生证据"的意图不符 |
| Listening LO 定义（一个教材听力任务 = 一个 LO） | ✅ 未违反 |
| Audio playback ≠ Evidence | ✅ 未违反（播放不产生证据） |
| Activity 是任务容器 | ✅ 未违反 |
| 教材是主线 | ⚠️ **受影响**：教材题目是主线内容，当前未进入数据与页面 |
| AI 不替代确定性教材事实 | ✅ 未违反（缺数据时降级为自评，未用 AI 猜选项） |
| 孩子做主 / 不自动学习 | ✅ 未违反（无自动行为） |

**规范冲突结论**：**无需修改 V1.2**；本问题是**数据与实现缺口**，不是规范缺陷。

## 17. 问题严重程度

**P1** —— 孩子看不到题目、无法完成该教材练习，且该练习无法产生有效判断证据（不满足"孩子能完成核心学习任务"与"能产生预期 Evidence"）。

**影响范围**：同类 `choice/judge` 且 `options=[]` 的练习共 **5 条**：
`Starter/GET_READY A10`、`Unit 1/UNDERSTANDING_IDEAS A6`、`Unit 3/UNDERSTANDING_IDEAS A3`、`Unit 4/DEVELOPING_IDEAS A2(judge)`、`Unit 6/UNDERSTANDING_IDEAS A1`。

## 18. 建议的最小修复方向（仅建议，不执行）

1. **数据层（首选）**：在 P2-3/P2-4 的教材练习解析中补齐这些活动的**选项/题干结构**（按教材版面提取 A/B/C 选项或图片选项标识），并修正 `blanks` 误计；**不使用 AI 猜测选项**，无法确认时标注 `options_status: NEEDS_REVIEW` 或 `interaction: textbook_only`。
2. **UI 层（数据未补齐前的诚实降级）**：当 `choice/judge` 缺 options 时，页面应**明确提示"请在教材上完成这道题"**，并保留自评（现状仅有自评按钮，孩子不知道要做什么）；
3. **LO/Evidence 影响**：修复前，此类练习的证据只能是 `done`（无效证据）；建议在 D 阶段的 LO 报告中对"不可作答练习"给出明确计数，避免误以为教材练习已全部可用。
4. **不扩大**：不做题库化、不补自造题、不改教材、不改音频。

## 19. 是否阻塞 P2-6-D 整体冻结

**不阻塞冻结，但必须作为 P1 缺陷记录并进入后续修复队列**：

- LO / Evidence / Mastery / Diagnosis / Suggestion 的**模型与实现**不因此问题失效（映射正确、规则正确）；
- 但"教材练习可在 APP 中按题型作答"这一产品目标在该 5 条练习上**未达成**，属于**内容与呈现缺口**，建议优先级高于其他 P2/P3 GAP。

## 20. 测试结果（只读运行）

| 套件 | 结果 |
| --- | --- |
| learning | 112 PASS |
| workbench | 50 PASS |
| web | 235 PASS |
| **合计** | **397 PASS / 0 FAIL / 0 SKIP**（与 D-2 基线一致，本次审计无回归） |

## 21. 保护基线（本次审计 0 修改）

```
learning.db  DBAB743BF6D8F0A3832E599C…（mtime 2026-09-12 23:15:13，未变）
contentpack  ACEBC8C29CF5D11BAB50…（未变）    V1.2 6D3595CF7D83879ADF3E…（未变）
exercise_catalog_v3.json 未修改 ｜ 业务代码未修改 ｜ 测试未修改 ｜ Android 未修改
数据库写入 0 ｜ 教材修改 0 ｜ 音频修改 0 ｜ 未制造学习记录 ｜ AI 调用 0
新增文件：仅本报告与 JSON
```

## 22. 停止声明

本轮为 **P2-6-D-2-B 只读专项审计**，未修改代码、数据库、教材、测试、Android 或规范；AI 调用 0。**未执行任何修复，不进入 P2-7，等待下一步任务指令。**
