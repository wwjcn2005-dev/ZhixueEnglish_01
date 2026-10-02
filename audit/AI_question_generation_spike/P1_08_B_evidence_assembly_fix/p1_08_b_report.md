# P1-08-B 实施报告 · 教材证据组装层机制修复

```text
最终结论   P1-08-B_PASS
AI 调用    0
修复对象   教材正文归属：页面没有 Activity 时正文被丢弃
代码变化   新建 1 个规范模块 + 3 个只读脚本；**未修改任何既有代码文件**
数据变化   learning.db / question_library.db / contentpack / structured 全部未修改
```

---

## 1. 原来的证据组装链是什么？

项目里存在**两条**正文归属链，规则不同：

### （A）正式展示层 —— `web/content.py::unit_text_sections()`（正确）

```text
unit 页范围（unit.pdf_page_start .. pdf_page_end）
   ＋ section 起始页（section.pdf_page_start，按页排序）
   ↓  _section_bounds() 推出每个 Section 的 [start, next_start-1]（末节到 unit 末尾）
content_block（按 page_id 的页码归入对应区间）
   ↓ 过滤：空文本 / 页眉页脚 / 侧栏 / 纯排版标记
Section 正文
```

该函数的文档字符串已经明确写了这条规则：
> "板块归属**只用**「section 起始页 + 单元页范围」这一确定性依据"

### （B）AI 生成侧 —— 实验脚本（错误）

```text
activity（取 distinct pdf_page, section_id）
   ↓  page → section 映射（page2sec）
content_block（只取落在这些 activity 页上的 block）
   ↓
input_context.json（送给 AI 的教材证据）
```

即在 `audit/AI_question_generation_spike/P1_05_real_validation/run_p1_05b.py::build_context()`：

```python
page2sec = {}
for r in cp.execute("select distinct pdf_page, section_id from activity"):
    page2sec.setdefault(r["pdf_page"], set()).add(r["section_id"])
...
for s in page2sec.get(r["pdf_page"], []):      # ← 页面没有 activity 就没有 section
    blocks_by_sec.setdefault(s, []).append(...)
```

**结果：AI 侧另写了一套归属规则，且这套规则把"页面是否有 Activity"当成了"该页正文是否属于该 Section"。**
正式层（A）一直是对的 —— 缺陷只存在于 AI 侧的重复实现里。

---

## 2. 具体哪个机制导致"无 Activity 页面正文丢失"？

> **`build_context()` 内的 `page2sec` 映射：它只由 `activity` 表构造，
> 并在遍历 `content_block` 时用 `page2sec.get(pdf_page)` 决定该 block 归入哪个 Section。
> 页面不在 `page2sec` 中 ⇒ 该页所有 block 被静默丢弃。**

同一模式也出现在 `P1_05_sample_design/build_sample_matrix.py`（用于样本矩阵指标统计）。

这两个文件都是**已完成轮的实验脚本**，本阶段**未修改**（见 §4）。

---

## 3. 为什么 Unit 1 第 17 页会漏？（实际数据）

| 项 | 实际值 |
| --- | --- |
| page_id | `FLTRP-EN-7A-2022CUR:P22` |
| PDF page / 教材页 | 22 / **17** |
| `page_role` | `content` |
| `text_chars` | **659** |
| `review_status` | `EXTRACTED`（正式数据里这页就是正文页） |
| **该页 Activity 数** | **0** |
| **该页 content_block 数** | **10**（B0–B9，即课文主体） |
| 旧逻辑归属（page2sec） | **`[]` → 全部被丢弃** |
| 新逻辑归属（页码范围） | `FLTRP-EN-7A-2022CUR:U1:UNDERSTANDING_IDEAS` ✔ |

**根因**：Unit 1 的 Activity 分布在教材页 16/18/19/20（PDF 21/23/24/25），
**第 17 页恰好没有 Activity**，因此旧逻辑的 `page2sec` 里没有 `22`，该页 10 个 block（整篇课文）被丢弃。

**旁证**：P1-06 的 S2（Unit 1 UI）实际 context 只覆盖 `P21, P23, P24, P25` —— 没有 P22。

### 同类缺陷的真实规模（本次量化）

| 指标 | 数量 |
| --- | --- |
| Section 总数 | 46 |
| 页集合在旧/新规则下有差异的 Section | **35** |
| 因旧规则被丢弃的 block（落在 Section 页码范围内、但该页无 Activity） | **2,217** |
| 其中属于课内 Section（Starter + U1–U6）的 block | 旧 1,265 → 新 1,638（补回 **398**，过滤纯空白 **25**，净增 373） |
| 不属于任何 Section 页码范围的 block（非本缺陷） | 194 |

除 Unit 1 第 17 页外，还发现另一个**真实受害 Section**：Unit 5 · UNDERSTANDING_IDEAS 缺 PDF 86（P1-06 的 S3 context 只有 P85/87/88/89）。

---

## 4. 实际修改了哪些代码文件？

### 本阶段**没有修改任何既有代码文件**。

原因：缺陷实现位于**已完成轮的实验脚本**中（P1-05-A / P1-05-B 的产物）。
改写这些脚本会让已完成轮的报告无法从其脚本复现（等同于改写历史）；而项目**尚无正式的证据组装模块**
（P1-08-A 已把"缺少统一 builder 契约"记录为缺口）。

因此本阶段采用**新建规范模块**的方式固化正确机制：

| 文件（均在 `audit/AI_question_generation_spike/P1_08_B_evidence_assembly_fix/`） | 性质 | 说明 |
| --- | --- | --- |
| `evidence_assembly.py` | **新建（规范模块）** | 修正后的证据组装参考实现：页码范围归属 + 按 `block_id` 去重 + 顺序保证；并提供 `blocks_by_activity_only()` 复现旧逻辑用于对照 |
| `test_evidence_assembly.py` | 新建（机制测试） | Test A–E + Case 5 |
| `compare_before_after.py` | 新建（对照） | 生成修复前后对照数据 |
| `recon_probe.py` / `check_formal_parity.py` / `check_formal_layers.py` / `build_audit.py` | 新建（只读核查） | 侦察、与正式层一致性校验、正式层缺陷排查、审计汇总 |

**未修改**：`web/`、`demo/`、`structured/`、任何既有 audit 脚本、任何数据库。

---

## 5. 有没有修改数据？

| 资产 | 是否修改 | 证据 |
| --- | --- | --- |
| `learning.db` | **否** | SHA256 `0C27267B…CF91` 未变 |
| `question_library.db` | **否** | SHA256 `F74CA83F…` 未变（21 题 / PENDING_REVIEW 21 / ACTIVE 0） |
| `contentpack` | **否** | SHA256 `65829CA7…0C39` 未变（全程只读连接） |
| `structured/` 正式教材数据 | **否** | 未写入任何文件 |

本阶段只**读取** contentpack 与既有 context/fixture；所有输出都在审计目录内。

---

## 6. Unit 1 第 17 页修复后是否 PASS？

**PASS。** 实际证据：

```text
U1 · UNDERSTANDING_IDEAS
  页范围(新)     : 21,22,23,24,25
  页集合(旧→新)   : [21,23,24,25] → [21,22,23,24,25]
  block 数(旧→新) : 55 → 63
    ├ 新增         : 10（全部来自 P22，即课文主体）
    └ 过滤         : 2（P21 上的纯空白 block，无证据价值）
  P22 block(旧→新): 0 → 10
  重复 block      : 0
  该页仍无 Activity: 是（前提未被改动）
```

关键 block 已在证据中：`P22:B2`（"That's not right. But is it OK to point out the mistake?…"）、
`P22:B6`（"…That sentence is from Confucius, not from Mencius."）、`P22:B9`（"That's really an important lesson!"）。

---

## 7. 有没有重复正文？

**没有。**

- 同一 Section 内 `block_id` 唯一（逐 Section 断言通过）；
- 每个 `block_id` **只归属于一个 Section**（全库 3,854 个 block 的归属检查通过）；
- 去重使用的是 contentpack 稳定主键 `block_id`，不是字符串比较；
- Activity 页上的 block 与页面正文合并后仍只出现一次（Test E）。

---

## 8. 有没有破坏原有 Activity 证据？

**没有。**

- 对全部课内 Section 断言：旧逻辑给出的**非空** block 全部仍在新证据中；
- 唯一的差异是 **25 个纯空白 block**（`text_raw` 仅含空白字符，长度 1–4）被新规则过滤 ——
  这类 block 不携带任何教材文本，过滤是**有意为之的更严格行为**，已单独计数并记录，不是静默丢弃；
- 该差异在测试中以「允许的差异必须全部是纯空白 block」的形式被断言。

---

## 9. 回归测试结果

```text
Ran 6 tests
OK
PASS 6 / FAIL 0 / ERROR 0 / SKIP 0
```

| 测试 | 覆盖 | 结果 |
| --- | --- | --- |
| `test_A_case1_page_has_text_but_no_activity` | Test A + Case 1（U1 第17页） | PASS |
| `test_B_page_has_activity_and_text_unchanged` | Test B + Case 2（原有证据不被破坏；差异仅纯空白） | PASS |
| `test_C_same_block_not_duplicated` | Test C（同 Section 不重复 + 每 block 只属一个 Section） | PASS |
| `test_D_multi_page_section_order_preserved` | Test D + Case 3（多页合并、顺序单调） | PASS |
| `test_E_activity_evidence_not_duplicated_by_page_text` | Test E + Case 4（Activity 证据不重复） | PASS |
| `test_case5_p1_06_fixture_regression` | Case 5（P1-06 fixture 超集 + 其 evidence block 全部存在） | PASS |

### 与正式层的一致性（额外验证）

```text
正式层 web/content.py 的 block 集合 ⊆ 修正模块默认输出     → True
修正模块 strict_text_rule=True 时与正式层逐 block 一致      → True
归属规则（section 起始页 + unit 页范围）与正式层完全一致      → True
```

> 修正模块默认内容过滤比正式展示层更宽（额外包含侧栏提示等），以保证 AI 证据层"不丢正文"；
> 需要与展示层完全对齐时可显式使用 `strict_text_rule=True`。

---

## 10. 正式资产 SHA 是否保持不变？

**全部保持不变**：

```text
learning.db        0C27267B…CF91        contentpack      65829CA7…0C39
question_library.db F74CA83F…           validator v2/v3  7C61585A… / EDB1AA54…
P1-06 S1–S4 fixture D4520E28… / 4F705951… / 4F9679CA… / 5D1C2103…
P1-07 产物          candidate_decision.json / ingest_result.json 未变
教材 PDF            C732051E…4F2F        V1.3 / V2.0 / P1-08-A 规范 未变
54 个 MP3           54/54 与 audio_asset.sha256 一致（沿用既有校验）
缺陷所在脚本（证明未修改任何既有代码）：
  run_p1_05b.py            D29D91CE26A95C8C8B15D9E0…（mtime 仍为 19:03:31）
  build_sample_matrix.py   0008C74AFF9EBA7E3869FA08…
  web/content.py           BEE8E33B89BFBF3B669C4298…（正式展示层，未修改）
```

```text
formal_assets_changed = false
（审计脚本对 18 个受保护文件逐一做了 SHA256 比对，全部匹配基线）
```

---

## 11. 是否仍存在其他证据组装缺陷？（只记录，不顺手修）

| # | 现象 | 说明 | 是否本次处理 |
| --- | --- | --- | --- |
| **D1** | 不属于任何 Section 页码范围的页面（单元扉页、部分非正文页）仍不会被任何 Section 证据包含 | 194 个 block | 否（记录） |
| **D2** | P1-06 的 S2 / S3 context 仍是旧逻辑产物（缺 P22 / P86） | 本阶段按纪律**不回填**既有实验产物 | 否（记录） |
| **D3** | 部分页面 `reading_order_status = NEED_REVIEW`（如 P21/P23），同页阅读顺序本身仍待正式确认 | 与本次归属缺陷无关 | 否（记录） |

**没有发现必须立即阻塞后续工作的同类机制缺陷**：归属规则缺陷已修复，且修正模块与正式层规则一致。

---

## 12. 产物

| 文件 | 说明 |
| --- | --- |
| `README.md` | 索引 |
| `p1_08_b_report.md` | 本报告 |
| `p1_08_b_audit.json` | 审计结果 |
| `before_after_comparison.json` | 修复前后对照（逐 Section + Case 1 + fixture 影响） |
| `recon_facts.json` | 侦察事实（含旧/新页集合差异、缺陷规模） |
| `evidence_assembly.py` | **修正后的规范模块** |
| `test_evidence_assembly.py` | 机制测试（6 项） |
| `compare_before_after.py` / `recon_probe.py` / `check_formal_parity.py` / `check_formal_layers.py` / `build_audit.py` | 只读核查与审计脚本 |

**结论：`P1-08-B_PASS`**
