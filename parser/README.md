# P1-03 教材结构解析器 V0.1

只读解析 `2025年度初一外研版英语教材` 中的 PDF，输出可审核的教材结构统计。
不会修改 PDF、MP3，不会建立数据库，不会导出图片。

## 运行

```powershell
python D:\ZhixueEnglish\parser\textbook_parser_v01.py
```

可选参数：

- `--focus 19,22,24`：只打印指定 PDF 页的重点验证信息
- `--json-out <path>`：额外写出结构化结果（默认不写任何文件）

## 已实现的解析规则

1. **页码映射**：优先读取页脚中真实印刷页码；封面/目录/封底等无页码页面记为 `None`，
   只有确实缺失时才用 `PDF 页码 - 5` 兜底，且记为 `derived_only`。
2. **文本归一化**：所有文本经过 `unicodedata.normalize("NFKC", ...)`，
   同时保留 `text_raw` 原始文本用于回溯。fi/fl 连字（U+FB01/U+FB02）会被还原为 `fi`/`fl`。
3. **Block 解析**：保留 block / line / span 层级以及 bbox、font、size、flags。
4. **图片过滤**：把 `page.get_images()` 的对象（带 xref、尺寸、色彩空间、滤镜）与
   版面中的图片 block 分开统计；`width < 50` 或 `height < 50` 标记为 `tiny_fragment`，
   原始信息保留不删除。
5. **阅读顺序重建**：先做版面分类
   （`single_column` / `two_column` / `mixed` / `dense_visual`），再按类型排序；
   复杂版面统一标记 `NEED_REVIEW`，不使用单一 y/x 排序。
6. **Unit 识别**：以 PDF 自带书签为主证据，标题取自单元起始页的真实大字号文本
   （自动去除“描边+填充”造成的重复行）。
7. **Section 识别**：按标题文本 + 字号 + 位置判断，允许标题与相邻文字合并绘制的情况。
8. **Activity 识别（P1-03-B 迭代）**：以教材排版特征为准——
   活动号是 **约 12pt 黑体**、位于左侧页边；
   课文段落编号 / 填空小问编号是 **7–8pt**，据此在候选阶段即排除。
   另外：
   - 段落编号组按“候选对象”删除，不再按编号值删除，避免误删同号的真实 Activity；
   - “Think and share” 框内的编号按 **框区域 bbox** 判定为小问题（该框有时在右上角）；
   - Activity 编号在同一 Section 的同一栏内递增，跨栏不复用该约束。
9. **缺口分级证据（P1-03-B 新增）**：每个编号缺口都会给出 PDF 取证与分级：
   - `A` 页面确实存在该编号且为任务指令（规则漏识别）
   - `B` 该 Section 页面范围内没有该编号的文本证据
   - `C` 存在类似数字，但属于课文段落 / 填空小问 / 表格编号
   - `D` 排版像活动号但文本无法判断，保留 NEED_REVIEW
10. **音频候选**：根据 MP3 文件名生成 Unit / Section / Activity 候选，
   一律标记 `mapping_status = CANDIDATE`，绝不自动确认。

### P1-03-C 定点审核后新增的规则

- **问题清单排除**：编号后直接是疑问句、且同一块内还有第二个编号
  （如 p.45 “1 What hobby do the pictures show? 2 What can you get…”）判为小问清单，不是 Activity。
- **标题行合并号**：Activity 1 与 Section 标题同行绘制时（如 “1 Reading for writing”）
  仍识别为 Activity，并取其下方最近文本块作为指令。
- **指令后置号**：编号写在指令句之后（如 “Complete the questionnaire.1”）时，
  以 12pt 黑体数字 span + 前置任务指令判定为 Activity。
- **侧栏几何关系**：辅助侧栏与 Activity 指令列在水平方向不相交时记为
  `sidebar_relation = separate_region`（独立区域，不并入 Activity）；
  同栏辅助内容记为 `auxiliary_same_column` 并保留 `NEED_REVIEW`。

### 版面类型

`single_column` / `two_column` / `single_column_with_sidebar`（正文 + 辅助侧栏，侧栏排在正文之后）
/ `mixed` / `dense_visual`。复杂版面统一标记 `NEED_REVIEW`。

## NEED_REVIEW 的含义

- 阅读顺序 `NEED_REVIEW`：该页为复杂版面（图文混排、双栏、密集视觉），
  block 顺序不能直接当作正文顺序。
- Activity 边界 `NEED_REVIEW`：区域内含 Grammar/侧栏元素，或活动抵达页底可能跨页。
- Activity 编号缺口：同一 Section 内编号不连续，提示可能漏识别，需人工比对。

## 已知限制（V0.1）

- 覆盖/封底是纯图像页，未做 OCR。
- NFKC 会把全角标点（如 `，`）规范化为半角；如需保留原标点，请使用 `text_raw`。
- 表格单元格、双栏词汇表的内部结构尚未拆分到单元格级。
- Activity 完整性依赖页边编号的绘制方式，存在编号缺口时必须人工复核。
