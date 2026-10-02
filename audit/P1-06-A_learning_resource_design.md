# P1-06-A 教材派生学习资源设计与只读审计报告

- 生成时间：2026-09-12T11:27:41+08:00
- 结论：PASS WITH NOTES
- 审计对象：D:\ZhixueEnglish\structured\contentpack\v1\FLTRP-EN-7A-2022CUR.sqlite（只读）
- 数据库 SHA256：B7372AAC3782DF88D1965160B93A4F50E82A6364593497FB4B858BE645BA68E3

## 1. 资源来源证据

### Words and expressions p155-162
- 内容块 377 条；条目型 289 条；多词条目 46 条
- 分类分布：{'latin_only': 16, 'head_entry': 266, 'continuation_or_cjk': 68, 'latin_cjk_entry': 23, 'other': 4}
- 多词样例：['junior high 初级中学 3', 'red scarf 红领巾 5', 'T-shirt /ˈtiː ʃɜːt/ n. T恤衫,短袖运动衫 5', ' school uniform 校服 5', 'of course 当然 5', 'teaching building 教学楼 6', 'dining hall 食堂 6', 'each other 互相,彼此 9']

### Proper nouns p163-164
- 内容块 39 条；条目型 33 条；多词条目 10 条
- 分类分布：{'latin_only': 5, 'head_entry': 27, 'other': 1, 'latin_cjk_entry': 6}
- 多词样例：['Great Bear Rainforest 大熊雨林 83', 'the Indian /ˈɪndiən/ Ocean 印度洋 104', 'ethics /ˈeθɪks/ and the rule /ruːl/ of law /lɔː/ 道德与法治 4', 'students’ union 学生会 22', 'Beijing opera /ˈɒpərə/ 京剧 32', 'Dragon Boat Festival 端午节 67', 'Double Fifth Festival 重午节 67', 'lunar /ˈluːnə/ month 太阴月;朔望月 67']

### Vocabulary A-Z p165-173
- 内容块 395 条；条目型 289 条；多词条目 46 条
- 分类分布：{'latin_only': 34, 'head_entry': 266, 'latin_cjk_entry': 23, 'continuation_or_cjk': 67, 'other': 5}
- 多词样例：['a bit 有点儿,稍微 10', 'against the law 违法 65', 'appear /əˈpɪə/ v. (尤指突然)出现, ', 'area /ˈeəriə/ n. (国家,市镇等的) ', 'as dead as a dodo 彻底死亡 104', 'as happy as a clam 非常高兴的, ', 'character /ˈkærəktə/ n. (书、剧本、 ', 'corn silk 玉米须 87']

### Communication bank（句型/交际功能）
- 出现页：[4, 115, 117, 118]
- • 条目块：80；Useful expressions 块：30
- 样例：['•\t Ms Chen 1  a sentence on the blackboard. But ', '•\tMr / Ms... is our... teacher.', '•\tMr / Ms... tells us...', '•\tHis / Her... make(s) me feel...', '•\tI’m so lucky to have a teacher like...', '•\tWe need to...']

### Grammar
- Grammar rules 指针：['Grammar rules ⇢ p136', 'Grammar rules ⇢ p138', 'Grammar rules ⇢ p142', 'Grammar rules ⇢ p142', 'Grammar rules ⇢ p143', 'Grammar rules ⇢ p147']
- Guide to the language use 起始页：p.135
- 语法主题标题样例：['Guide to the language use', 'Starter  ', '可数名词和不可数名词', '1. 可数名词', '2. 不可数名词', '基数词和冠词', '1. 基数词', '2. 冠词', '一般现在时', 'Guide to the language use', '一般将来时', 'there be 句型的用法']
- 目录 Grammar 栏：['Welcome to junior high! p2nouns; numbers; articles; simple p', 'ReadingGrammar1 p14', 'Pronouns', 'Simple present tense', 'Simple future tense', 'Present continuous tense']

## 2. 四类资源可行性

| 类型 | 判定 | 自动 | 人工确认 | 禁止 |
| --- | --- | --- | --- | --- |
| Vocabulary | 可行（部分自动 + 部分人工） | 附录 head_entry 型条目（含音标或词性 + 中文释义） | 跨块续行条目合并、Proper nouns 归类 | 从正文/对话/语法说明自动抽词；AI 推荐词 |
| Phrase | 部分可行（以人工确认为主） | 附录词汇表中 headword 含空格的多词条目 | Communication bank / Useful expressions 中的交际表达 | 把普通连续文本机械切片成短语 |
| Sentence Pattern | 部分可行（需人工确认） | Communication bank 的 • 条目结构化定位 | 占位符规范化、归属 Unit 与功能、是否核心句型 | 把阅读课文/语法例句中的普通句子当作句型 |
| Grammar | 可行（结构证据明确） | Guide to the language use 主题标题 + Grammar rules 指针 + 目录 Grammar 栏 | 主题规范命名、绑定教学页范围 | 根据文本用法推断教材正在教授某语法点 |

## 3. NEED_REVIEW 影响
- Activity boundary：23
- Reading-order：88 页
- SubQuestion：13
- WordsAndExpressions：{'two_column|OK': 8}
- Vocabulary：{'two_column|OK': 9}
- CommunicationBank：{'mixed|NEED_REVIEW': 9, 'single_column|OK': 8, 'two_column|OK': 1}
- GuideToLanguageUse：{'mixed|NEED_REVIEW': 11, 'single_column|OK': 9}
- UnitContent：{'dense_visual|NEED_REVIEW': 3, 'mixed|NEED_REVIEW': 54, 'single_column|OK': 37, 'single_column_with_sidebar|OK_SIDEBAR_LAST': 2}

## 4. 当前底座不足
- block_kind 分布：{'exercise_item': 2984, 'sidebar_tip': 348, 'heading': 344, 'footer_text': 178}（dialogue=0，分类偏粗）
- evidence 缺 bbox / extraction_version（P1-05-C 已记录）
- 附录词汇表存在跨块续行（head entry 与中文续行分离）
- 部分 Unit 页 reading order 为 NEED_REVIEW，影响句级定位，不影响块内文本

## 5. learning_item 字段评估

- item_id：必需（稳定主键）
- textbook_id：必需（版本隔离）
- snapshot_id：必需（快照隔离）
- item_type：必需（vocabulary/phrase/sentence_pattern/grammar）
- canonical_text：必需（规范形式，用于去重检索）
- display_text：必需（保留教材原始写法）
- explanation：不放入 L2；解释属 L3 AI 辅助层
- source_ref：必需（至少一条，指向 content_block）
- review_status：必需（EXTRACTED/NEED_REVIEW/REVIEWED_OK/REJECTED）
- schema_version：必需
- content_hash：必需
- created_at/updated_at：必需

## 6. 边界

- sqlite_modified：False
- pdf_modified：False
- mp3_modified：False
- parser_modified：False
- builder_modified：False
- learning_item_created：False
- ai_calls：0
