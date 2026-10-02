# P1-08-B · 教材证据组装层机制修复

```text
最终结论   P1-08-B_PASS
AI 调用    0
修复对象   教材正文归属：页面没有 Activity 时正文被丢弃
代码变化   新建 1 个规范模块 + 只读核查脚本；未修改任何既有代码文件
数据变化   learning.db / question_library.db / contentpack / structured 全部未修改
formal_assets_changed = false
```

---

## 缺陷是什么

AI 生成侧的证据组装（`P1_05_real_validation/run_p1_05b.py::build_context`）用 **`activity → page → text`** 反推正文归属：

```python
page2sec = {}                      # 只由 activity 构造
for r in cp.execute("select distinct pdf_page, section_id from activity"): ...
for s in page2sec.get(r["pdf_page"], []):   # 页面无 activity ⇒ 该页正文被丢弃
```

**正式展示层 `web/content.py::unit_text_sections()` 一直用的是正确规则**（section 起始页 + unit 页范围），缺陷只存在于 AI 侧的重复实现里。

### 已知案例（本阶段实测确认）

| 项 | 值 |
| --- | --- |
| page_id / PDF / 教材页 | `FLTRP-EN-7A-2022CUR:P22` / 22 / **第 17 页** |
| page_role / text_chars | `content` / **659**（正式数据里就是正文页） |
| 该页 Activity 数 | **0** |
| 该页 content_block 数 | **10**（课文主体 B0–B9） |
| 旧归属 → 新归属 | `[]` → `U1:UNDERSTANDING_IDEAS` |

同类缺陷规模：**35 / 46 个 Section 的页集合有差异**；旧规则共丢弃 **2,217** 个 block（落在 Section 页码范围内但该页无 Activity 的正文）。课内 Section（Starter + U1–U6）净增 **373** 个 block（补回 398、过滤纯空白 25）。另发现第二个真实受害 Section：**Unit 5 · UNDERSTANDING_IDEAS 缺 PDF 86**。

---

## 修复方式（最小改动）

新建规范模块 `evidence_assembly.py`，规则为：

```text
Section 页码范围 = 该 unit 内按 pdf_page_start 排序的 [start, next_start-1]（末节到 unit 末尾）
   ∪ 该 Section 的 activity 页
   ↓ 按 block_id 去重（稳定主键，不用字符串比较）
   ↓ 按 (pdf_page, reading_order) 排序
```

> **Activity 仍然决定"这个任务需要哪些证据"，但不再决定"这一页有没有正文"。**

与正式层的一致性（实测）：

```text
正式层 block 集合 ⊆ 修正模块默认输出                    → True
修正模块 strict_text_rule=True 与正式层逐 block 一致     → True
```

**本阶段未修改任何既有代码文件** —— 缺陷在已完成轮的冻结实验脚本中，改写会使其报告不可复现；故以新建规范模块固化正确机制（P1-08-A 已把"缺统一 builder 契约"记为缺口）。

---

## 验证结果

```text
Ran 6 tests
OK      PASS 6 / FAIL 0 / ERROR 0 / SKIP 0
```

| 测试 | 覆盖 |
| --- | --- |
| `test_A` | Test A + Case 1：U1 第 17 页（10 个 block 全部进入证据） |
| `test_B` | Test B + Case 2：原有非空证据不被破坏（差异仅 25 个纯空白 block） |
| `test_C` | Test C：同 Section 不重复 + 每个 block 只属一个 Section |
| `test_D` | Test D + Case 3：多页合并、顺序单调 |
| `test_E` | Test E + Case 4：Activity 证据不重复 |
| `test_case5` | Case 5：P1-06 fixture 为新证据子集，其 evidence block 全部存在 |

### Case 1 前后对照

```text
U1 · UNDERSTANDING_IDEAS
  页集合   [21,23,24,25] → [21,22,23,24,25]
  block    55 → 63（+10 来自 P22，−2 纯空白）
  P22 block 0 → 10
  重复     0
```

### P1-06 fixture 影响

```text
S1 U2 UI   78 → 78（+0）
S2 U1 UI   53 → 63（+10，补回 P22）
S3 U5 UI   75 → 82（+7，补回 P86）
S4 Starter 77 → 77（+0）
```

---

## 仍存在、只记录不修（3 项）

| # | 现象 |
| --- | --- |
| D1 | 不属于任何 Section 页码范围的页面（单元扉页等，194 个 block）仍不进任何 Section 证据 |
| D2 | P1-06 的 S2/S3 context 仍是旧逻辑产物；按纪律不回填既有实验产物 |
| D3 | 部分页面 `reading_order_status = NEED_REVIEW`，同页阅读顺序仍待正式确认 |

---

## 保护项

```text
learning.db  0C27267B…CF91     contentpack 65829CA7…0C39
question_library.db F74CA83F…（21 题 / PENDING_REVIEW 21 / ACTIVE 0）
validator v2/v3 未变 · P1-06 fixture（S1–S4）未变 · P1-07 产物未变
教材 PDF 未变 · V1.3 / V2.0 / P1-08-A 规范未变 · 54 MP3 未变
formal_assets_changed = false
```

---

## 产物

| 文件 | 说明 |
| --- | --- |
| `README.md` | 本索引 |
| `p1_08_b_report.md` | 完整报告（逐条回答任务的 11 个问题） |
| `p1_08_b_audit.json` | 审计结果 |
| `before_after_comparison.json` | 修复前后对照 |
| `recon_facts.json` | 侦察事实 |
| `evidence_assembly.py` | **修正后的规范证据组装模块** |
| `test_evidence_assembly.py` | 机制测试（6 项） |
| `compare_before_after.py` · `recon_probe.py` · `check_formal_parity.py` · `check_formal_layers.py` · `build_audit.py` | 只读核查脚本 |
