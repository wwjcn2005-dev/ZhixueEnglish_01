# AI 教材题目生成 P0 Spike · 收口只读审计报告

审计日期：2026-09-17
审计模式：**只读**（AI 调用 0，文件修改 0，正式数据写入 0）
审计对象：`20260917_1450_deepseek_min3`、`20260917_1520_validator_fix`、
`20260917_1610_deepseek_second_section`、`20260917_1630_deepseek_second_section_8192`、
`20260917_1650_evidence_insufficient`

---

## 0. 结论

### **P0_CLOSE**

P0 要回答的问题只有一个：

> 能不能用**正式教材证据**驱动 AI 生成**可回溯、可机器校验**的题目，并且这条链路**可控、可复用、不污染正式数据**？

答案是**能**，且已有 4 次真实云端调用、6 道真实生成题、9 个单元测试、6 个对抗样本的实测支撑。

但必须同时冻结一条纪律：

> **P0_CLOSE 只代表“机制成立”，不代表“批量质量已稳定”。**
> 6 道题来自 2 个 Section，只占全册 40 个 Section 的 5%。

---

## 1. 审计范围与只读声明

### 1.1 只读检查过的正式结构

| 资源 | 关键事实 |
| --- | --- |
| `structured/ai/textbook_evidence_map_v1.json` | 1,484,385 B；`rule_set = P2-4-textbook-reconstruction-v1`；**360 个证据包**；每包含 scope / textbook_reference / original_question / related_text / related_vocabulary / related_listening |
| `structured/textbook/textbook_structure_v2.json` | 书级结构：`pdf_sha256 = C732051E…4F2F`、178 页、7 units / 40 sections / 157 activities |
| `structured/textbook/textbook_content_relations_v2.json` | 词汇/语法/文本关系（`vocabulary_in` / `grammar_in` / `text_references`） |
| `structured/exercises/exercise_catalog_v3.json` | 416,453 B；157 exercises / 360 questions / **21 个 listening activities（`audio_required = true`）** / 850 个教材空位 |
| `structured/learning/learning.db` | 118,784 B；表：learner、learning_task、task_item、learning_record、mastery_state、learning_session、schema_migration；**无任何 AI 表** |
| `structured/contentpack/v5/FLTRP-EN-7A-2022CUR.sqlite` | 2,715,648 B；`ai_artifact` **0 行**；`transcript` **0 行**；`audio_token_annotation` **0 行**；`audio_sentence_annotation` **15 行**；54 MP3 / 59 audio_mapping |
| validator v2 | `20260917_1520_validator_fix/validator_v2.py`（本次审计**重跑单测：Ran 9 tests，OK**） |

### 1.2 本次审计的零写入确认

- AI 调用（云端 / 本地）：**0**
- 修改正式文件 / 代码 / validator：**0**
- 创建正式 AI 题库表：**0**
- 写入正式 `ai_artifact`：**0**
- 重新解析 PDF：**否**
- 重启 Web 服务：**否**
- 唯一写入位置：`audit/AI_question_generation_spike/P0_closeout/`

---

## 2. 已验证事实

> 以下全部为**可直接复核的事实**，不是推断。

### 2.1 四次 Spike 的真实账目

| Spike | 范围 | 云端生成调用 | 本地调用 | max_tokens | finish_reason | 题数 | validator | 耗时 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1450 | Unit 3 · RfW | 1 | 0 | 4096 | `stop` | 3 | v1：1/3（2 处误报） | 63.0 s |
| 1520 | 同 1450 的 3 题（**0 次 AI**） | 0 | 0 | — | — | 3 | **v2：3/3 PASS** | — |
| 1610 | Unit 1 · UI | 1 | 0 | 4096 | **`length`** | **0** | 未执行（无输入） | 73.1 s |
| 1630 | 同 Unit 1 · UI（仅 max_tokens 变） | 1 | 0 | **8192** | `stop` | **3** | **v2：3/3 PASS** | 113.3 s |
| 1650 | Unit 1 · DI · A1（证据不足） | 1 | 0 | 8192 | `stop` | **0** | 未执行（无输入） | 6.5 s |
| 1410 / 1430_cpu | 本地 qwen3:8b 路线 | 0 | **1 + 1** | — | — | 0 | — | 58.8 s / 超时 |

### 2.2 单变量对照（Spike 2A vs 2B）

| 项 | 1610 | 1630 |
| --- | --- | --- |
| `input_context.json` SHA256 | `471E6FA7…DFA4` | `471E6FA7…DFA4`（**字节一致**） |
| system / user prompt | 同机制 | 由 AST 从上一轮脚本字面量重建，**逐字一致** |
| `max_tokens` | 4096 | **8192（唯一变化）** |
| reasoning tokens | 4096（占满） | 5648 |
| `content` | 0 字符 | 1,685 字符 |
| 结果 | 0 题 | 3 题，3/3 PASS |

结论：**4096 是本上下文下的临界不足值；8192 足以完成 reasoning + 结构化输出。**

### 2.3 validator 能力实测

| 验证 | 结果 |
| --- | --- |
| 单元测试 | **9/9 PASS**（本次审计实机重跑确认） |
| 原始 3 题回归 | **3/3 PASS**（q1 `EXACT`、q2 `EXACT`、q3 `VERIFIABLE_REFERENCE`） |
| 对抗性坏样本 | **6/6 全部拦截**（超纲选项词 / 无支持答案 / 编造引用 / 无效 block id / fill 无空位 / correct_option 不一致） |
| 修正前后对比 | v1 对同一批真实题目误报 2 题；v2 修正后 0 误报，**且未出现新的漏检** |

### 2.4 真实生成题目（6 道）的证据回溯

| 题 | 范围 | evidence_quote 是否命中教材原文 | answer_support_type |
| --- | --- | --- | --- |
| 1450 q1 fill | Unit 3 P56 | 是 | `EXACT` |
| 1450 q2 vocab_choice | Unit 3 P56 | 是 | `EXACT` |
| 1450 q3 reading_choice | Unit 3 P57 | 是 | `VERIFIABLE_REFERENCE`（They = the brothers） |
| 1630 q1 fill | Unit 1 P17 | 是 | `EXACT` |
| 1630 q2 vocab_choice | Unit 1 P17 | 是 | `EXACT` |
| 1630 q3 reading_choice | Unit 1 P17 | 是 | `EXACT` |

### 2.5 正式数据零污染

- `learning.db`：118,784 B、mtime `2026-09-13 15:50:09`、SHA256 `0C27267B…CF91` —— **全程未变**
- contentpack v5：`ai_artifact` = **0 行**
- `learning.db` 中**不存在任何 AI 题表**
- 教材 PDF 未重新解析；54 个官方 MP3 未修改
- 正式 Web 8770、Demo 8780 均未重启

---

## 3. A. P0 数据链是否可以冻结？

实际成立的链条：

```text
教材原始数据（PDF → contentpack v5 / structured）
        ↓  ✅ 已存在
structured textbook evidence（textbook_evidence_map_v1.json，360 包）
        ↓  ✅ 已存在
input_context.json（仅脚本组装，尚无正式 builder 契约）
        ↓  ✅ 已验证可复现（字节一致）
AI generation（云端 deepseek-v4-pro，max_tokens 8192）
        ↓  ✅ 已验证可完整输出
generated_questions.json（原始输出，未人工修改）
        ↓  ✅ 已存在
validator v2（8 项确定性校验）
        ↓  ✅ 已验证有效，且有单测 + 对抗样本
database_candidate.json（程序判定 + 人工判定）
        ↓  ✅ 已存在
human review（人工逐题复核）
        ↓  ✅ 已完成 6 题
【缺口】正式题库 / 生命周期 / 缓存 —— ❌ 尚不存在
```

### 判断

**可以冻结为“P0 数据链成立”**，但必须同时承认三个真实缺口：

1. **答案来源缺口**：360 个证据包与 157 个 exercise 的 `answer_source` / `answer_status`
   **全部为 `NO_RELIABLE_SOURCE`**。全册没有官方标准答案可供机器核对，
   AI 生成答案只能回溯到**教材正文**，不能与官方答案比对。
2. **听力文本缺口**：`transcript` 0 行、`audio_token_annotation` 0 行、
   `audio_sentence_annotation` 仅 15 行，而 exercise catalog 中有 **21 个 `audio_required = true`**
   的听力活动。**依赖音频内容的题目目前无法从文本证据生成**（Spike 3 已实测印证）。
3. **上下文组装的契约缺口**：`input_context.json` 目前由各轮脚本自行组装，
   尚无统一的、带版本号的 builder 契约（P1 需补）。

---

## 4. B. AI 模型路线是否可以冻结？

只根据工程证据判断（不评价模型聪明与否）：

| 判断项 | 证据 | 结论 |
| --- | --- | --- |
| 本地 Qwen3:8B 是否继续保留 | 1410：CUDA 加载失败 / HTTP 500 / 0 输出；1430_cpu：CPU 约 2.02 tok/s，客户端超时 | **不保留为当前路线**（可冻结为“P0 期间不可用”） |
| 云端 `deepseek-v4-pro` 是否作为当前正式生成路线 | 3 次生成调用全部 HTTP 200；2 次成功产出结构化 JSON；1 次因 max_tokens 不足截断（已定位为参数问题） | **冻结为当前验证路线**，但**不等于已批准为生产路线** |
| `max_tokens = 8192` 是否可作为当前默认值 | 1630 用 5,648 reasoning + 而仍有余额完成输出；1610 用 4096 即截断 | **可作为当前默认值**，但需保留“不足则上调/重试”的工程预案 |
| 成本相关的工程风险 | 单次成功生成 **113.3 s**、15,574 tokens；一旦按页面实时生成，孩子要等近 2 分钟 | **必须坚持“先查库、后生成”**，禁止页面实时生成 |
| 稳定性是否已得到足够验证 | 成功样本 2 次（不同 Section），失败 1 次（参数），证据不足 1 次 | **不足**。样本量太小，不能宣称“批量稳定” |

---

## 5. C. validator v2 能保证什么，不能保证什么？

### 5.1 可以作为**确定性硬门槛**（可冻结）

1. **定位真实性**：`unit` / `section` / `page` / `activity` 必须落在提供的证据范围内
2. **evidence_block_ids 真实性**：引用的 block 必须真实存在于上下文
3. **evidence_quote 可回溯**：引文必须是引用 block 文本的（归一化后）逐字子串
4. **答案支持分级**：`answer_support()` 返回 `EXACT` / `VERIFIABLE_REFERENCE` /
   `VERIFIABLE_REPHRASE` / `UNSUPPORTED`，只有前三类通过；**绝不采信 explanation 的自述**
5. **词汇边界**：只检查 `question + options + answer`，越出白名单即 FAIL
   （`explanation` 与元数据**不参与**，避免误报）
6. **选项一致性与唯一正确项**：`correct_option` 必须存在且与 `answer` 一致
7. **结构完整性**：题型规则（fill 必须含空位、choice 必须有选项等）
8. **重复检测**：题干与引文去重

实测证明这 8 项**确实能拦真实错误**（6/6 对抗样本），也**确实消除过误报**（v1→v2）。

### 5.2 **不能**可靠保证的部分（必须人工或后续机制兜底）

| 不能保证 | 原因 |
| --- | --- |
| 教育价值 / 是否值得练 | 属教学判断，无确定性规则 |
| 语言自然度 | 同上 |
| 干扰项质量 | 只校验“不重复 + 唯一正确项”，不校验“干扰项是否被教材排除” |
| 答案唯一性 | `answer_support` 判断“答案是否被支持”，**不判断“是否还有其他同样合理的答案”** |
| AI 是否“猜中”教材选项 | **结构性缺陷，重点见 5.3** |
| 跨句证据 | 一条 `evidence_quote` 目前只支持连续片段 |
| 语义同义改写 | 只支持代词指代与规则词形变化，自由改写判 `UNSUPPORTED` |
| 题型多样性 / 是否集中在同一段落 | 无覆盖度约束（1630 的 3 题全在第 17 页同一段落） |
| 是否真的适合初一 | 需要教学判断 |

### 5.3 【必须记录】`EXACT` 的语义陷阱

> **当选项文本本身已经存在于教材证据中时，`answer_support = EXACT` 只表示
> “这个字符串能在证据里找到”，不等于模型真的证明了答案的正确性。**

具体表现：

- 听力选择题的三个选项**本身就印在教材上**（例如 Spike 3 的
  `a It’s hard to make new friends. / b … / c …`）；
- 若模型猜中其中一项，`answer ∈ evidence_quote` 会成立，validator 判 `EXACT` → **PASS**；
- 但模型并没有任何证据能证明哪一项才是广播里说的。

Spike 3 的 reasoning 恰好证明了这一点：模型自述“有音频引用但没有转写，无法确定答案”，
于是选择 0 题——**如果它当时选择猜一个，validator 很可能拦不住。**

结论：**validator PASS ≠ 答案被证明。** 这条必须写进 P1 的质量门槛设计。

---

## 6. 自动入库的安全边界：候选题生命周期（设计，不实现）

```text
GENERATED            AI 原始输出，未做任何校验
    ↓ 确定性校验（validator v2，8 项）
VALIDATED            机器校验通过；仍不可见给孩子
    ↓ 进入待审队列
PENDING_REVIEW       等待人工复核
    ↓ 人工通过
APPROVED             已获批准，但尚未被任何学习场景启用
    ↓ 显式启用（指定 unit/section/activity）
ACTIVE               允许进入正式学习系统

任意状态 → REJECTED   人工驳回或机器硬失败，永久不再自动复用
任意状态 → DISABLED   已启用后因质量问题/教材变更下线
```

### 回答八个问题

1. **哪个状态才允许进入正式学习系统？**
   学习系统**只能读取 `ACTIVE`**。`APPROVED` 只是“已批准”，还必须经过一次**显式启用**
   才能变成 `ACTIVE`。这样即使批次批准出错，也不会瞬间全网生效。
2. **validator PASS 是否足够？**
   **不够。** PASS 只能把题目推进到 `PENDING_REVIEW`，不能直接 `APPROVED`。
3. **人工复核是否必须？**
   **P1 阶段必须。** 依据：validator 无法判断干扰项质量、答案唯一性，也无法识别
   “猜中教材选项”（5.3）。人工复核是当前唯一的兜底。
4. **已 APPROVED 的题目以后是否还需要重新验证？**
   需要，但**是增量重验，不是重新生成**：当教材证据、validator 版本或题型规则变化时，
   对存量题目重跑确定性校验；不通过则自动降级为 `PENDING_REVIEW` 或 `DISABLED`。
5. **如果 prompt / model / context 变化，旧题如何处理？**
   旧题**保留**（不删除、不静默替换），但标记为 `stale`（记录 `stale_reason`），
   需要重跑确定性校验；只有通过重验才回到 `APPROVED`。旧题与新题**并存**，靠 `version` 区分。
6. **如何保留题目的生成来源和教材证据？**
   必须同时保存：`context_hash`（教材证据快照）、`evidence_block_ids`、
   `evidence_quote`、`model`、`prompt_version`、`generation_run_id`、`generated_at`、
   `validator_version`。缺任何一项都会让题目**不可再审计**。

---

## 7. AI 题库所需的数据字段（字段级设计，不建库）

### 7.1 必须保留（缺一项即不可审计 / 不可复用）

| 分类 | 字段 |
| --- | --- |
| 基础身份 | `question_id`、`question_type`、`question_text`、`options`、`correct_answer`、`explanation` |
| 教材来源 | `unit_id`、`section_id`、`activity_id`、`page`、`evidence_block_ids`、`evidence_quote` |
| AI 来源 | `model`、`prompt_version`、`context_hash`、`generated_at`、`generation_run_id` |
| 审核 | `validation_status`、`review_status`、`reviewer`、`reviewed_at`、`review_note` |
| 生命周期 | `active`、`disabled_reason`、`version` |

### 7.2 可以后续再加

- `difficulty`、`ai_confidence`（模型自评，仅供参考，不进质量门槛）
- `answer_support_type`（`EXACT` / `VERIFIABLE_REFERENCE` / `VERIFIABLE_REPHRASE`）——建议 P1 就加，因为它直接对应 5.3 的陷阱
- `stale_reason`、`revalidated_at`
- `usage_count`、`first_used_at`（用于复用与淘汰）
- `distractor_review_note`（干扰项人工结论）

### 7.3 建议的唯一键（复用键）

```text
reuse_key = hash(section_id, activity_id, question_type, prompt_version, context_hash)
```

同一 `reuse_key` 下只允许存在有限条题目；重复命中时**必须复用，不得再次调用 AI**。

---

## 8. 复用优先：什么时候调用 AI？

**可以冻结为：**

```text
孩子进入学习场景
        ↓
查 ACTIVE 题库（按 section/activity/题型/难度）
        ↓ 有可用题目
直接复用 ——【0 次 AI 调用】
        ↓ 没有
判断该场景是否允许生成（是否在允许批次内、证据是否充足、当日预算是否用尽）
        ↓ 允许
离线/后台生成 → VALIDATED → PENDING_REVIEW → APPROVED → ACTIVE
        ↓ 不允许
回退到已有教材题目（exercise_catalog_v3）或提示“稍后再试”
```

### 硬性纪律

> **禁止页面打开就调用 AI。**

### 必须一并设计的问题

| 风险 | 处理方式 |
| --- | --- |
| 同一教材证据重复生成 | 以 `reuse_key` 去重；命中即复用 |
| 同一 prompt/version 重复生成 | `reuse_key` 已含 `prompt_version`；同版本同上下文只生成一次 |
| 已被拒绝的题目再次生成 | `REJECTED` 必须记录 `reject_signature`（题干 + evidence_quote 指纹），下次生成命中即**直接丢弃**，不再送审 |
| AI 费用失控 | 以“批次 + 预算上限 + 每日调用上限”三重限制；单次 113.3 s / 15.6k tokens 的成本必须按批次核算 |
| 缓存与唯一键 | 缓存粒度 = `reuse_key`；`context_hash` 变化即视为新缓存条目，旧条目保留但标记 `stale` |

---

## 9. 证据不足机制

Spike 3 证明了模型**可以**在真实缺口场景返回 0 题。但**不能**把它当作唯一安全机制。

建议的分层结构：

```text
① evidence sufficiency check（确定性程序）
   - 该 activity 是否 audio_required 但 transcript 缺失？
   - evidence package 的 answer_source 是否为 NO_RELIABLE_SOURCE？
   - 该 Section 的 content_block 是否为空 / 是否只有页眉页脚？
        ↓ 通过
② AI generation（并在 prompt 中保留“证据不足则少生成/不生成”条款）
        ↓
③ deterministic validation（validator v2，8 项）
        ↓
④ human review
```

### 必须写明的一条纪律

> **“AI 自己说证据不足”只能作为一个信号，不能作为系统唯一的安全判断。**

理由（基于实测）：

- Spike 3 只有 **1 次**观测；样本量为 1，不具备统计意义；
- 反向风险同样存在：模型**可能不认为**证据不足而直接猜答案，且当选项文本印在教材上时
  validator 会判 `EXACT` 放行（5.3）；
- 因此，**程序侧的前置充分性检查（①）必须存在**，用来在 AI 之前就拦掉结构上不可能出题的场景
  （典型就是“听力活动但没有 transcript”这一类，全册共 21 个）。

---

## 10. 基于证据的工程判断（推断，非事实）

以下是从实测数据推出的判断，**不是已验证事实**：

1. 8192 在当前两个 Section 的上下文规模下够用；若上下文继续变大（例如整 Unit 或跨 Section），
   需要重新验证，不能直接沿用。
2. 推理型模型的 reasoning 占比很高（1630：5648 / 6123 ≈ 92%），
   这意味着**输出预算主要由 reasoning 决定**，题量对 token 的影响反而较小。
3. 由于全册没有官方答案来源，AI 题目在可预见的未来**只能是“教材正文驱动”的补充题**，
   不能替代教材原有练习。
4. 人工复核是当前唯一能覆盖“答案唯一性 / 干扰项质量 / 教育价值”的环节，
   因此复核成本会成为规模化的真正瓶颈，而**不是** AI 调用成本。

---

## 11. 尚未验证的风险

| # | 风险 | 现状 |
| --- | --- | --- |
| R1 | 批量生成质量稳定性 | 只有 6 道真实题、2 个 Section；**未验证** |
| R2 | 题干/题型多样性 | 1630 三题集中在同一页同一段落；**未验证** |
| R3 | 干扰项是否被教材排除 | 无机器判定，靠人工；**未验证** |
| R4 | 答案唯一性 | 无机器判定；**未验证** |
| R5 | “选项在证据中 → EXACT 放行”的漏检 | 结构上确知存在，**尚无对抗样本** |
| R6 | 听力类活动出题 | 21 个 audio_required 活动无文本证据；**当前不可行** |
| R7 | 语法 / 写作 / 口语类 Section | 未做任何生成验证 |
| R8 | 成本与延迟 | 单次 113.3 s；批次规模下的总成本未测算 |
| R9 | 教材改版 | `context_hash` 变化后的重验流程未设计 |
| R10 | 跨句证据 | validator 不支持，未验证 |

---

## 12. P0 结论

### `P0_CLOSE`

### 已在本轮 P0 验证通过的内容

1. 正式教材证据可只读组装为 AI 上下文，且**可字节级复现**（M01、M02、M03）
2. 云端 `deepseek-v4-pro` 可完成 reasoning + 结构化 JSON 输出（M04）
3. `max_tokens` 是真实工程变量：4096 截断、8192 成功（M05、M06）
4. 生成题目受教材证据约束，6 道全部可逐字回溯（M07）
5. validator v2 有效：9/9 单测、3/3 回归、6/6 对抗样本拦截（M09、M10、M11）
6. 证据不足场景下模型有一次主动拒题的正确观测（M12，单样本）
7. 正式数据全程零污染（M22）

### 明确留到 P1 的问题（不在 P0 继续消耗样本）

1. 批量质量稳定性（R1）——**不得用“3 个样本都成功”推断稳定**
2. 题型多样性 / 段落覆盖度（R2）
3. 干扰项与答案唯一性的机器或流程保障（R3、R4）
4. `EXACT` 语义陷阱的专门检测规则（R5）
5. 听力类活动的证据补齐或明确排除策略（R6）
6. 语法 / 写作 / 口语类 Section 的可出题性（R7）
7. 成本与延迟的批次级测算（R8）
8. 教材改版后的重验流程（R9）
9. 正式题库数据模型、生命周期、缓存与复用键（P1-01 ~ P1-03）
10. 人工复核的最小界面与流程（P1-05）

---

## 13. 保护项与零写入确认

```text
learning.db           未修改（SHA256 0C27267B…CF91，mtime 2026-09-13 15:50:09）
contentpack v5        未修改（ai_artifact = 0 行）
structured/ 正式数据   未修改
教材 PDF              未重新解析
54 个官方 MP3         未修改
正式 Web 8770         未修改 / 未重启（PID 36848）
Demo Web 8780         未修改 / 未重启（PID 107044）
Android               未修改
V1.3 / V2.0 规范       未修改
validator v2          未修改
AI 调用（审计期间）     0
正式 AI 题库表          未创建
```

本次唯一写入位置：`audit/AI_question_generation_spike/P0_closeout/`
