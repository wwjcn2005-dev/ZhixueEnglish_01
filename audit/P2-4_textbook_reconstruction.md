# P2-4 教材完整重构与学习关系建模报告

- 生成时间：2026-09-13T10:19:50+08:00
- 规则集：P2-4-textbook-reconstruction-v1
- 扫描范围：教材 PDF 第 8–114 页（正文），官方 MP3 54 个

## 1. 教材结构

| 项目 | 数量 |
| --- | --- |
| Unit / Starter | 7 |
| Section | 40 |
| Activity | 157 |
| Question | 360 |
| 听力活动 | 21 |
| 教材填空线 | 850 |

## 2. 纸面视觉语义

| 对象 | 数量 |
| --- | --- |
| 图片 | 139 |
| 色块/框线/下划线等矢量对象 | 2653 |
| 其中填空线 | 850 |
| 耳机图标 | 33 |
| 已判定语义角色 | 1210 |
| 仍为 unknown（NEEDS_REVIEW） | 1739 |

## 3. 上下文关系

- 关系总数：4220
- 其中 contains/belongs_to：1114
- 其中 precedes/follows：312
- 其中 audio_for：41
- 其中 image_for/supports：2753

## 4. 音频完整匹配

| 项目 | 数量 |
| --- | --- |
| 官方 MP3 | 54 |
| CONFIRMED | 54 |
| NEEDS_REVIEW | 0 |
| 活动级音频（audio_scope=activity） | 41 |
| 板块级音频（词表/语音） | 13 |
| 音频→题目关系 | 121 |

## 5. 练习与题目结构

- 题目总数：360
- 带音频的题：121 ｜ 带图片的题：344 ｜ 带文本依赖的题：315 ｜ 带词汇关联的题：303

- 教材答案来源：全部标记 NO_RELIABLE_SOURCE（教材未提供可核对答案）
- 每题均已生成 Textbook Evidence Package（360 份）

## 6. 一致性检查

- 问题总数：133 ｜ 分类：{'ambiguous': 133}

## 7. 模型判断（KEEP / EXTEND / REBUILD）

### KEEP

- **contentpack.unit / section 页边界**：与真实教材页范围一致，可直接作为教材骨架
- **contentpack.source_ref / textbook_emphasis**：教材事实可追溯（页码 + 引用 + 强调证据），继续使用
- **learning_item（vocabulary / phrase / sentence_pattern）**：教材词条与学习资源身份稳定，P2-4 未发现冲突
- **P2-3 官方音频证据链（54/54 CONFIRMED）**：本阶段重新验证未发现错误匹配，可继续作为音频事实

### EXTEND

- **activity（96 行 / P1-05 快照）**：真实教材有 157 个活动；P2-3/P2-4 以覆盖层表达，contentpack.activity 需要补齐活动与边界状态
- **audio_mapping（59 行）**：缺少 audio_scope（activity/question/section）与 question 级关系字段
- **question / sub_question（sub_question 仅 13 行）**：真实教材题目结构远多于现有 13 条，需要按活动层级扩展

### REBUILD

- **纸面视觉语义层（图片 / 色块 / 框线 / 填空线 / 图标）**：现有模型完全没有视觉对象表，无法表达“这张图属于哪个活动、这条下划线是第几个空”
- **教材上下文/内容关系图**：现有模型只有线性 page/block，没有关系表，无法表达 precedes/uses/tests/depends_on 等教材逻辑
- **教材证据包（AI 批改用）**：现有模型无法为单题提供“教材范围内证据”，下一阶段 AI 批改缺少依据

## 8. 数据安全

- 原始 PDF：未修改（只读）
- 原始 MP3：未修改（SHA256 已记录）
- learning.db：未写入
- contentpack：未修改
- AI 调用：0 ｜ 网络调用：0

