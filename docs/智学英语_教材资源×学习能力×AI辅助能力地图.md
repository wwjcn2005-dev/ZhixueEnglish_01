# 智学英语｜教材资源 × 学习能力 × AI 辅助能力地图

> 性质：**只读整理**（产品能力梳理，不是审计、不是新阶段开发）。
> 本轮未调用任何 AI、未修改任何代码 / 数据库 / JSON / V1.3 / V2.0 / 题库、未生成新题、未重新解析 PDF。
> 所有数量均来自现有正式数据的实际统计，单位为「条 / 字符 / 活动数」。

---

## 0. 实际读取的正式资料

| 类别 | 实际读取对象 |
| --- | --- |
| 教材结构 | `structured/textbook/textbook_structure_v2.json` |
| 教材练习目录 | `structured/exercises/exercise_catalog_v3.json`（157 exercise） |
| 教材题目关系 | `structured/exercises/exercise_question_relations_v3.json`（360 question） |
| 教材证据包 | `structured/ai/textbook_evidence_map_v1.json`（360 package） |
| 教材数据库 | `contentpack v5`：`unit`（8 行，含 Starter 与 Appendix）、`section`（46 行）、`activity`（96 行）、`content_block`（3,854 行）、`page`（177 行）、`learning_item`（520 行：vocabulary 288 / exercise 157 / sentence_pattern 52 / phrase 23）、`source_ref`（带 `textbook_emphasis`）、`learning_goal`（6 行）、`sub_question`、`transcript`、`audio_asset`（54）、`audio_mapping`（59）、`audio_sentence_annotation`（15）、`audio_token_annotation`（0） |
| 词汇 / 短语 / 句式 | contentpack 的 `learning_item` + `source_ref`；教材附录 `Words and expressions`（pdf155–162）、`Vocabulary A-Z`（pdf165–173）、`Communication bank`（pdf117–118）、各 Unit 的 `Presenting ideas` 页（pdf25/41/57/73/89/105） |
| 语法 / 语言运用 | 教材附录 `Guide to the language use`（pdf135–154，tb130–149）实际内容 |
| 阅读资源 | `web/reading_map.py`（教材点读链路与规则）+ contentpack 各 Section 正文块 + `audit/P3-07_preview`（47 份词级 ASR、960 条音频↔文本匹配候选，其中 HIGH 422 条） |
| 学习数据 | `structured/learning/learning.db`（`learner` 1、`learning_task` 33、`task_item` 33、`learning_record` 21、`mastery_state` 7、`learning_session` 33） |
| 正式规范 | `初中英语AI辅助学习系统最高指导原则与开发规范 V1.3`、`产品与UI架构总纲 V2.0`、`AI教材习题生成与题库入库流程规范 V1.0` |

**说明**：本轮不做审计、不重新验证既有机制；以下整理中的「资源不足」均只作如实记录，不据此启动新的设计或验证。

---

## 1. 教材资源总览

```text
Starter  Welcome to junior high!   tb2–13    （4 个 Section：Get ready / Know your school /
                                              Get to know each other / Make a wishing tree）
Unit 1   A new start               tb14–29   （6 个 Section）
Unit 2   More than fun             tb30–45
Unit 3   Family ties               tb46–61
Unit 4   Time to celebrate         tb62–77
Unit 5   The power of plants        tb78–93
Unit 6   Fantastic friends         tb94–109
附录     Appendix                  tb111–171 （Communication bank / Guide to the language use /
                                              Words and expressions / Proper nouns /
                                              Vocabulary / Pronunciation guide）

每个 Unit 的 6 个 Section（固定结构）：
  Starting out → Understanding ideas → Developing ideas → Reading for writing →
  Presenting ideas → Reflection
```

### 1.1 词汇资源（教材自己的 Words and expressions 分组统计）

| Unit | 词表条目 | BOLD 重点词（课标三级词） | 普通认识词 | 词性分布（前三位） |
| --- | --- | --- | --- | --- |
| Starter | 32 | 23 | 9 | n 12 · v 5 · adj 3 |
| Unit 1 | 35 | 31 | 4 | n 16 · v 6 · adj 4 |
| Unit 2 | 46 | 41 | 5 | n 21 · v 11 · adj 8 |
| Unit 3 | 41 | 36 | 5 | n 17 · v 12 · adj 7 |
| Unit 4 | 45 | 42 | 3 | n 25 · v 10 · adj 7 |
| Unit 5 | 46 | 38 | 8 | n 26 · v 11 · adj 4 |
| Unit 6 | 45 | 35 | 10 | n 19 · adj 9 · v 5 |
| **合计** | **290** | **246** | **44** | — |

> 教材原文注明：**加粗词汇为义务教育英语课程标准三级词汇**（Words and expressions 页脚注）。
> 因此 BOLD = 必须掌握的重点词，非 BOLD = 需要认识的词。这是本项目「BOLD 优先」口径的教材依据。

### 1.2 短语资源（`item_type = phrase`，23 条）

```text
分布：集中在 Starter 与 Unit 1 的教材表达上，例如
  junior high（初级中学）、red scarf（红领巾）、school uniform（校服）、
  teaching building（教学楼）、dining hall（食堂）、each other（互相）、
  a bit（有点儿）、take part in（参加）、of course（当然）……
特点：以「名词短语 / 固定搭配」为主，几乎都能直接用在句子与短段里。
```

### 1.3 句式资源（`item_type = sentence_pattern`，52 条，来自两处）

| 来源 | 条数 | 性质 | 示例 |
| --- | --- | --- | --- |
| Communication bank（pdf117–118，按 Unit 编排的功能表达） | 19 | 交流功能句：描述问题、提建议、表达感受与观点、同意/不同意 | `... is a problem for me.` / `One way is to...` / `We can learn... because...` / `I agree. Another idea is to...` / `I see it differently, because...` |
| 各 Unit 的 Presenting ideas 页（pdf25/41/57/73/89/105） | 33 | **带空位的表达骨架**，用于口头/书面表达产出 | `It feels great to...` / `As a... lover, I...` / `Without plants, ... will / won't...` / `It looks like...` / `It is about...` |

> 这两类句式的差别很重要：前者是「怎么和人交流」，后者是「怎么把话说完、说清楚」。
> 后者（带 `...` 的骨架）才是写作与口语迁移的主要抓手。

### 1.4 语言运用（语法）资源：教材附录 `Guide to the language use` 实际覆盖

| 归属 | 教材实际给出的语言运用主题 |
| --- | --- |
| Starter（tb130–135） | 可数名词和不可数名词（含复数变化规则）· 基数词和冠词 · 一般现在时（第三人称单数变化规则）· 一般将来时（两种结构可互换）· there be 句型的用法 · 简单句的基本句型（主+系+表 / 主+谓 / 主+谓+宾）· 形容词的基本形式（分类与比较） |
| Unit 1（tb136–137） | 人称代词和物主代词（主格/宾格/人称代词顺序；形容词性物主代词、名词性物主代词） |
| Unit 2（tb138–141） | 一般现在时（be 动词：be+形容词/名词/介词短语/副词；行为动词：否定形式、第三人称单数加 -s、疑问句与答句） |
| Unit 3（tb142） | 名词的所有格 |
| Unit 4（tb142） | 频度副词（含频度副词之间的比较） |
| Unit 5（tb143–146） | 一般将来时：be going to / will（含否定句、一般疑问句与答句） |
| Unit 6（tb147–148） | 现在进行时（含动词 -ing 形式变化规律） |

```text
结论：教材自带的语言运用资源是**明确且有边界**的 12 个主题
     （Starter 7 个 + 每个 Unit 各 1 个）。
     本图只使用这些主题；不自行建立教材之外的语法课程。

---

## 2. Unit 能力地图（主表）

表中「AI批改 / AI分析 / AI指导」三列写的是**该 Unit 的资源可以支撑的 AI 能力**，不是已经实现的功能。

| Unit | 词汇 / 短语 | 句式 | 语言运用 | 阅读资源与能力 | 写作资源与能力 | 适合练习 | AI 批改 | AI 分析 | AI 指导 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Starter** | 32 条（BOLD 23）· 短语 junior high / red scarf / school uniform / teaching building / dining hall / each other / a bit / take part in / of course | 无独立句式数据 | 名词可数性 · 数词与冠词 · 一般现在时 · 一般将来时 · there be · 简单句三句型 · 形容词形式 | Get ready 2,344 字符（对话/指令）· Know your school 1,470 · Get to know each other 1,690 → 以信息匹配与对话理解为主 | `Write about yourself.`（A6）；个人介绍短句 | 词汇与图片匹配 · 数字/冠词填空 · there be 句型操练 · 自我介绍短句 | 匹配/选择/填空：程序直接判定；`Write about yourself`：AI 批改 | 基础词识别（学科名、文具、数字、颜色）· 冠词与数词使用 | 指回教材对应图片与句子；提示"先说他有什么，再说他喜欢什么" |
| **Unit 1** | 35 条（BOLD 31）· 短语 point out / in fact / a bit / each other | Presenting ideas 6 条（`That's really a(n)... lesson!` / `Mr / Ms... is our... teacher.` / `...tells us...` / `His / Her... make(s) me feel...` / `I'm so lucky to have a teacher like...` / `We need to...`）· bank 5 条（`... is a problem for me.` / `One way is to...` / `It makes me feel...` / `Also, you can...` / `What are some solutions for...?`） | 人称代词与物主代词（主格/宾格/顺序；形容词性·名词性物主代词） | Understanding ideas 3,508 字符（Read the passage：老师写句子—学生指出错误）· Developing ideas 1,975（听力：新生的最大问题）· Reading for writing 2,652（Mia 与父母的故事）→ 信息定位、因果理解、代词指代 | Reading for writing A5 `Complete Mia's reply to her parents.` · Presenting ideas：`Make a poster about your first week in junior high.` | 原句填空（重点词）· 代词指代题 · 短答（他为什么这样做）· 回复父母（多句表达） | 填空/选择：程序；短答与回复：AI 批改（含"是否用上本单元代词"） | 物主代词混用 · 主格/宾格误用 · 只答事实不答原因 · 未用上教材表达 | 指出"你找到了人物，但还需要找到他为什么这样做"；指回课文原句；提示先用教材句式再说自己想法 |
| **Unit 2** | 46 条（BOLD 41）· 短语 rock music / take part in 等 | Presenting ideas 4 条（`I like...` / `There is so much fun in...` / `As a... lover, I...` / `It feels great to...`）· bank 3 条（`We can learn... because...` / `As a result, ...` / `So...`） | 一般现在时（be 动词四种补足语；行为动词否定、第三人称单数 -s、疑问句） | Understanding ideas 3,713（两篇博客：摇滚与爷爷的二胡）· Developing ideas 1,807（听力：Wang Chen 参加观鸟俱乐部）· Reading for writing 2,362（Emma 的笔记本故事）→ 人物关系、对比理解、上下文猜测 | Reading for writing：续写 notebook（`Please write more!`）· Presenting ideas：`Make a plan for a school club.`（含 Introduction / Body / Conclusion 提纲与现成表达） | 重点词填空 · 人物关系与对比选择 · 第三人称单数专项 · 续写 2–4 句 · 俱乐部方案（短段） | 填空/选择：程序；续写与方案：AI 批改 | 三单 -s 遗漏 · 兴趣爱好词汇缺乏 · 段落没有"先说目的再说好处" · 抄袭原句未改写 | 指出缺哪个 -s；提示"用 First / Second / Third 把理由排好"；指回教材提纲 |
| **Unit 3** | 41 条（BOLD 36）· 短语 along / follow / bring back 等 | Presenting ideas 4 条（`It is about...` / `It brings back my memory of...` / `I'm happy about...` / `...'s love may be...`）· bank 6 条（`I'd rather not.` / `Yes, but now...` / `It's a bit difficult to talk about. But...` / `I hope you're not hurt.` / `I feel... because...` / `Thank you.`） | 名词的所有格 | Understanding ideas 3,771（家人与理解）· Developing ideas 2,277（听力：family hotline，Tina 与妈妈）· Reading for writing 2,736（Robert 与 trailer）→ 情感理解、代词指代（`it` 指代）、人物关系 | Reading for writing：围绕"家人"的书面表达（writing 4 题）· Presenting ideas：`Make a photo album about your family.` | 所有格专项 · 指代理解（`What does "it" refer to?`）· 情感类短答 · 照片相册说明文字 | 所有格/指代：程序可判；情感短答与相册说明：AI 批改 | 所有格 's 与 of 混用 · 指代对象找错 · 情感词单一（只会 happy/sad）· 表达不含原因 | 提示"你写的是结果，教材里还给了原因"；指回 `I feel... because...`；让孩子自己补 because |
| **Unit 4** | 45 条（BOLD 42）· 短语 hang / treat / dumpling 等 | Presenting ideas 6 条（`My family always have... at...` / `The best part of the festival is...` / `... is a must for...` / `I feel like...` / `I often..., but I never...` / `... hang(s) balloons and lanterns...`）· bank 5 条（`I think... is a new way to celebrate, because...` / `That's a(n)... idea!` / `I agree. Another idea is to...` / `I'm not sure about that.` / `I see it differently, because...`） | 频度副词（含比较） | Understanding ideas 3,870（本册最长）· Developing ideas 2,367（听力：news，圣诞节带来的问题）· Reading for writing 2,814（Leng 节日值班）→ 要点概括、观点与理由 | Reading for writing A5 `Write a short paragraph about a person on duty during festivals.` · Presenting ideas：`Make a poster about a festival or holiday.` | 频度副词填空 · 判断题（本 Unit 唯一有 judge 资源）· 短段落写作 · 节日海报 | 填空/判断：程序；短段落与海报文字：AI 批改 | 频度副词位置（always/never 与实义动词、be 动词的顺序）· 段落只有事实没有感受 · 观点句与理由句脱节 | 提示"先说你觉得怎样，再说为什么"；指回 bank 的 `I think... because...`；建议孩子自己重写一句 |
| **Unit 5** | 46 条（BOLD 38）· 短语 take a… / collect 等 | Presenting ideas 6 条（`Without plants, ... will / won't...` / `... mean a lot to...` / `... is useful for...` / `... need... to...` / `... can make...` / `... give more than...`） | 一般将来时 be going to / will | Understanding ideas 3,352（Great Bear Rainforest 指南）· Developing ideas 2,084（听力：vlog，Jason 谈玉米的重要性）· Reading for writing 2,721（茶与中国、英国人）→ 事实定位、说明文理解、重要性概括 | Presenting ideas：`Make a poster about plants.` · Reading for writing（writing 7 题，本册写作资源最丰富） | 说明性填空 · 事实定位选择 · 概括"植物为什么重要" · 海报说明 | 填空/选择：程序；概括与海报：AI 批改 | will / be going to 混用 · 只会抄课文不概括 · 说明理由缺"因为—所以" · 名词单复数 | 提示"用 will 说未来，用 be going to 说打算"；指回 `Without plants, ... will...`；让孩子改用教材句式重说一遍 |
| **Unit 6** | 45 条（BOLD 35 / 普通 10，非重点词最多）· 短语 knock around 等 | Presenting ideas 8 条（`It is a...` / `It looks like...` / `Look, it's...` / `It eats...` / `It's amazing / clever / ...` / `It can...` 等） | 现在进行时（含 -ing 变化规律） | Understanding ideas 3,539（动物博客）· Developing ideas 2,273（听力：radio programme，Goodbye to a hero）· Reading for writing 2,558（dodo 的故事）→ 描述性理解、因果与"为什么消失" | Reading for writing A5 `Write a short paragraph about dodos.` · Presenting ideas：`Make a profile of an animal.` | 现在进行时专项 · 描述性短答 · 动物档案短段（含外形、习性、需要帮助） | 填空/选择：程序；短段与档案：AI 批改 | 现在进行时缺 be 或动词形态错 · 描述只有外形没有习性 · 说明"需要帮助"的理由不充分 · 普通认识词（非 BOLD）掌握弱 | 提示"先描述，再说它需要什么帮助"；指回 `It looks like...` / `It can...` 骨架；让孩子自己补一句 |

---

## 3. 教材练习资源与题型分布（真实数据）

### 3.1 教材自己出了什么题（`exercise_question_relations_v3`，360 题）

| 题型 | 题数 | 占比 | 说明 |
| --- | --- | --- | --- |
| fill（填空/完成句子） | **124** | 34% | 教材主力题型，与 246 个 BOLD 重点词高度匹配 |
| short_answer（短答/简答） | **111** | 31% | 教材第二大题型，也是 AI 批改价值最高的地方 |
| choice（选择） | 30 | 8% | 资源有限，集中在 Starter（15） |
| speaking（口语/朗读） | 22 | 6% | 需要音频配套 |
| other | 20 | 6% | 各类操作性任务 |
| reflection（自评） | 18 | 5% | 每个 Unit 3 题 |
| writing（写作） | 16 | 4% | U5 最多（7），U3 次之（4） |
| match（匹配） | 14 | 4% | 集中在 Starter（9） |
| judge（判断） | **3** | 0.8% | 只在 Unit 4 |
| order（排序） | 2 | 0.6% | 只在 Unit 2 |

```text
关键结论：教材的题型结构是「填空 + 短答为主，选择很少，判断几乎没有」。
→ 资源丰富的题型：fill、short_answer、writing/speaking（读写与表达任务）
→ 资源稀少的题型：choice（8%）、judge（0.8%）
这一点直接决定：本项目不应把"选择题数量"当作质量指标。
```

### 3.2 每个 Unit 的题型分布

| Unit | 题型分布（题数） |
| --- | --- |
| Starter | fill 16 · choice 15 · speaking 10 · match 9 · other 5 · short_answer 3 · writing 1 |
| Unit 1 | fill 27 · short_answer 12 · choice 7 · speaking 3 · reflection 3 · match 1 · other 1 |
| Unit 2 | short_answer 24 · fill 15 · speaking 3 · reflection 3 · order 2 · choice 1 · match 1 · writing 1 · other 1 |
| Unit 3 | short_answer 23 · fill 14 · writing 4 · reflection 3 · other 2 · choice 1 · speaking 1 |
| Unit 4 | short_answer 24 · fill 11 · judge 3 · reflection 3 · match 2 · writing 2 · speaking 2 · choice 1 · other 1 |
| Unit 5 | fill 23 · short_answer 14 · writing 7 · reflection 3 · choice 2 · speaking 2 · other 2 · match 1 |
| Unit 6 | fill 18 · short_answer 11 · other 8 · choice 3 · reflection 3 · writing 1 · speaking 1 |

### 3.3 各 Section 的教材功能与活动量

| Section | 教材活动数 | 教材自己要求孩子做什么（指令原文摘要） | 本图判定的能力定位 |
| --- | --- | --- | --- |
| Starting out | 5 | `Look at the pictures and answer the questions.` / `Guess and match the sentences with the countries.` | 激活与预判（看图/连线） |
| Understanding ideas | **40** | `Read the passage. What does the writer do in his first lesson?` / `Read the blogs and find out the words Henry used.` | **阅读主区**（信息定位与理解） |
| Developing ideas | 17 | `Listen to the radio. What's the biggest problem for new students?` / `Listen to the family hotline...` / `Listen to the vlog...` | **听力主区**（听 + 短答） |
| Reading for writing | 23 | `Look at the pictures and answer the questions. Use the words to help you.` → `Read the story...` → `Write a short paragraph about...` | **读写结合区** |
| Presenting ideas | **未被结构化为 activity**（只有正文与句式） | `Make a poster about your first week in junior high.` / `Make a plan for a school club.`（含 Introduction / Body / Conclusion 提纲） | **表达产出区**（口语 + 书面） |
| Reflection | **未被结构化为 activity** | `After completing this unit, I understand more about...` / `To express my understanding, I can...` / `I still need to improve:` | **自评区**（教材自带的自评结构） |

### 3.4 各 Section 的正文体量（字符数，程序只读重建）

| Unit | Starting out | Understanding ideas | Developing ideas | Reading for writing | Presenting ideas | Reflection |
| --- | --- | --- | --- | --- | --- | --- |
| Starter | — | Get ready 2,344 / Know your school 1,470 / Get to know each other 1,690 | — | — | — | — |
| Unit 1 | 538 | **3,508** | 1,975 | 2,652 | 807 | 588 |
| Unit 2 | 296 | **3,713** | 1,807 | 2,362 | 1,139 | 539 |
| Unit 3 | 330 | **3,771** | 2,277 | 2,736 | 932 | 544 |
| Unit 4 | 349 | **3,870（最长）** | 2,367 | 2,814 | 885 | 674 |
| Unit 5 | 288 | 3,352 | 2,084 | 2,721 | 996 | 580 |
| Unit 6 | 622 | 3,539 | 2,273 | 2,558 | 1,139 | 612 |

### 3.5 音频与语音资源的实际状态（必须如实记录）

```text
官方音频：54 个 MP3 全部在位（audio_asset 54 行）
教材侧音频↔活动映射：audio_mapping 59 行，其中 target_type='activity' 28 行（MATCHED）、
                      31 行没有 target_type（CANDIDATE）
音频文字化：transcript 0 行 · audio_token_annotation 0 行 ·
            audio_sentence_annotation 仅 15 行（只在 Unit 1，其中 VERIFIED 12 / REJECTED 3）

另有既有点读资源（Demo 专用，仅供只读复用）：
  audit/P3-07_preview/asr/ 47 份「官方音频」词级 ASR 时间轴
  audit/P3-07_preview/matched_candidates.json 960 条音频↔教材文本匹配候选，其中 HIGH 422 条
  web/reading_map.py 只使用 HIGH 匹配，且要求块文本被 ASR 区间覆盖 ≥0.9

结论：
  可以支撑「教材音频 ↔ 教材文本」的对齐（点读、跟读锚定：读哪一句、对应哪段文字）。
  但目前**不存在**面向孩子录音的正式评测数据与评分规则，
  因此不能声称具备「发音评分 / 单词遗漏检测 / 流利度评分」能力。
```

### 3.6 学习侧资源（`learning.db`）

```text
learner 1 · learning_task 33 · task_item 33 · learning_session 33
learning_record 21  ← 学习证据表：activity_type / result / response_raw / attempt_no / hints_used
mastery_state 7     ← 聚合表：mastery_level / evidence_count / correct_count / last_result /
                      last_practiced_at / review_needed

说明：AI 批改与分析可以落在 learning_record（孩子这一次怎么答）与 mastery_state（长期状态），
不需要新建表；具体字段迁移属于既有流程议题，本图不展开。

---

## 4. 整体资源规律

### 4.1 哪些资源丰富

```text
① 词汇：290 条（BOLD 246 = 课标三级词），每 Unit 32–46 条，词性以名词与动词为主
② 阅读文本：每个 Unit 的 Understanding ideas 3.3k–3.9k 字符 +
   Reading for writing 2.4k–2.8k 字符 + Developing ideas 听力文本 1.8k–2.4k
③ 句式骨架：33 条 Presenting ideas「带空位表达」+ 19 条 Communication bank「功能句」
④ 教材自带的书面表达任务：16 个 writing 题 + 6 个 Presenting ideas 任务（含提纲）
⑤ 短答资源：111 题 short_answer，是教材最大题型，也是 AI 批改价值最高处
⑥ 自评结构：每 Unit 3 题 reflection（含"我还需要提高"），与 V1.3「孩子做主」天然一致
```

### 4.2 哪些资源不足（如实记录，不强行扩展）

```text
① 选择题资源少：360 题中只有 30 题（8%），且一半集中在 Starter
   → 干扰项素材有限，不适合为了"题型平衡"强行增加选择题
② 判断题资源极少：只有 3 题（0.8%），只在 Unit 4
   → 不适合把 judge 当作常规题型铺开
③ 音频文字化不足：transcript 0 行、token 级标注 0 行、句子级标注仅 15 行
   → 听力题的"答案依据"大多无法由正式文本证据支撑；不适合在证据不足处硬出听力题
④ 口语评测资源缺失：没有儿童录音数据、没有评分规则、没有发音标注
   → 不适合做"发音评分/流利度评分"；只能做"跟读锚定 + 自评/教师确认"这一类
⑤ Presenting ideas 与 Reflection 未结构化为 activity
   → 这两个 Section 的表达与自评只能基于正文文本，无法像 Understanding ideas 那样出结构化题
⑥ 语法资源有限但完整：Starter 7 个主题 + 每 Unit 1 个主题，共 12 个
   → 不自行建立教材之外的语法课程；语法练习必须在这些主题范围内
```

### 4.3 哪些题型自然适合增加

```text
· 重点词语境填空（fill）：246 个 BOLD 词 + 教材 124 个 fill 题 → 天然匹配
· 阅读短答（short_answer）：教材 111 题 + 大文本量 → 天然匹配，且是 AI 批改主战场
· 句式迁移与短段表达：33 条骨架 + 16 个写作任务 + 6 个 Presenting 任务 → 天然匹配
· 词汇语境选择：词表充足，但必须有可靠教材证据支撑（干扰项不足时不要硬凑）
· 自评与回顾：教材自带 reflection 结构，可直接复用其口径
```

### 4.4 哪些题型不适合硬凑

```text
· 大量选择题（资源 8%，干扰项素材不足）
· 判断题（资源 0.8%）
· 长作文（教材写作任务是海报/计划/相册/回复/短段落，没有长文要求）
· 听力题（音频文字化不足，答案依据无法由正式文本证据支撑）
· 发音评分类口语题（无评测数据与规则）
· 教材之外的语言点（如未出现的语法专题）
```

---

## 5. 阅读路线（以实际教材资源为依据）

**信息定位 → 理解 → 上下文/关系 → 简单推断/概括 → 阅读后表达**

| 层级 | 教材资源依据 | 可以训练的能力 | 合适的练习形式 | 现有题库中的真实例子 |
| --- | --- | --- | --- | --- |
| ① 信息定位 | Understanding ideas（3.3k–3.9k 字符，Read the passage/blogs） | 找到人物、地点、时间、动作 | 细节选择 / 短答 / 完成句子 | `Grandpa likes playing the erhu ___.`（in the park） |
| ② 信息理解 | 同上 + Developing ideas 听力文本 | 理解同义改写、把课文句子换成另一种说法 | 完成句子 / 判断说法是否一致 | `At the school art festival, the writer and Grandpa ___.`（fire up instruments） |
| ③ 上下文理解 | Reading for writing（2.4k–2.8k）与长段落 | 代词指代、词义猜测、句子之间怎么连 | 短答（`What does "it" refer to?`） | 教材 U3 A4、U4 A4、U5 A3 的原题型 |
| ④ 人物/事物关系 | Understanding ideas（人物、家人、师生、动物） | 谁和谁是什么关系、谁做了什么、为什么 | 关系类选择 / 因果短答 | `Why do questions jump into the writer's mind?`（因果短答） |
| ⑤ 简单推断与要点概括 | U4（本册最长 3,870 字符）、U5（说明文） | 从两句话推出结论；用一句话说出"这段主要讲了什么" | 推断短答 / 概括一句话 | `What can the trees make?`、`Why are plants important?` |
| ⑥ 阅读后表达 | Reading for writing 的 A5 写作任务 + Presenting ideas | 把读到的内容变成自己的话 | 续写 / 回复 / 海报说明 / 短段落 | U1 `Complete Mia's reply to her parents.`；U4/U6 `Write a short paragraph about...` |

```text
落地原则：
  ①–② 用程序即可判定的题型（填空/选择/完成句子）承担；
  ③–⑤ 用短答承担，由 AI 批改 + 证据定位（这正是教材 111 道短答题的用武之地）；
  ⑥ 只在 Reading for writing 与 Presenting ideas 资源处做，不额外造写作任务。
```

---

## 6. 写作路线（以实际教材资源为依据）

**句子 → 句式迁移 → 多句 → 短段 → 简短完整表达**

| 层级 | 教材资源依据 | 代表练习 | 说明 |
| --- | --- | --- | --- |
| ① 句子 | Presenting ideas 的 33 条带空位骨架 | `It feels great to...` / `I like...` / `It is about...` | 先把一个句子说完整、写完整 |
| ② 句式迁移 | Communication bank 的 19 条功能句 | `... is a problem for me.` → 换成自己的问题；`I feel... because...` → 换成自己的感受与原因 | 把教材句换成自己的内容 |
| ③ 多句 | U1 `Complete Mia's reply to her parents.` / U2 续写 notebook | 用 2–4 句回应一段情境 | 开始出现句子之间的连接（because / but / and） |
| ④ 短段 | U4 `Write a short paragraph about a person on duty during festivals.` / U6 `Write a short paragraph about dodos.` | 一段 3–5 句的短段落 | 教材明确要求"short paragraph"，不是长作文 |
| ⑤ 简短完整表达 | Presenting ideas 的提纲式任务 | U2 `Make a plan for a school club.`（Introduction / Body / Conclusion 提纲 + 现成表达） | 教材已给出结构，孩子只需把内容填进去 |

```text
六个 Presenting ideas 任务（教材自带的"完整表达"目标）：
  U1 Make a poster about your first week in junior high.
  U2 Make a plan for a school club.
  U3 Make a photo album about your family.
  U4 Make a poster about a festival or holiday.
  U5 Make a poster about plants.
  U6 Make a profile of an animal.
→ 全部是"海报 / 计划 / 相册 / 档案"，没有长篇作文要求。
   因此本项目不做长篇作文，写作训练止于"短段落 + 提纲式完整表达"。

---

## 7. AI 批改 · AI 分析 · AI 指导

### 7.1 AI 批改：哪些任务值得 AI 参与

| 任务类型 | 教材资源量 | 谁来判断 | 原因 |
| --- | --- | --- | --- |
| 选择题（choice） | 30 题 | **程序直接判断** | 答案唯一、可确定性比对；不需要为了"AI 感"让 AI 参与 |
| 填空 / 完成句子（fill） | 124 题 | **程序判断对错**（+ AI 只在必要时判断"语境是否唯一"） | 字面比对是确定性的；语境唯一性才是 AI 的补充价值 |
| 匹配 / 排序（match / order） | 14 + 2 题 | **程序直接判断** | 一一对应关系可确定性校验 |
| 判断题（judge） | 3 题 | **程序直接判断** | True/False 由教材事实决定 |
| 词汇 / 短语 / 句式填空 | 290 词 + 23 短语 + 52 句式 | 程序判断 + **AI 判断语境与表达是否自然** | AI 补的是"这条句子像不像话、是不是只能用这个词" |
| **阅读短答（short_answer）** | **111 题** | **AI 批改**（程序只做基础校验） | 答案不是字符串；需要判断内容对不对、有没有答到点上 |
| **句子表达 / 短段落写作（writing）** | 16 题 + 6 个 Presenting 任务 | **AI 批改** | 需要判断内容是否完整、表达是否清楚、是否用上教材语言 |
| **口语 / 朗读（speaking）** | 22 题 | **AI 辅助 + 孩子/教师确认**（受限，见 §3.5） | 当前没有儿童语音评测资源；只能做"读的是哪一句"的锚定与自评 |

```text
一句话：客观题优先交给确定性程序；短答、写作、口语才是 AI 批改真正值钱的地方。
```

### 7.2 AI 分析：能从孩子的实际作答中看出什么

| 层面 | 可以分析什么 | 依赖的学习证据 | 教材依据 |
| --- | --- | --- | --- |
| 知识层 | 哪个词不会 / 哪个短语容易混 / 哪个句式不会用 / 哪个语言点反复出错 | 填空答案、词汇题答案、句子、历史 `learning_record` + `mastery_state` | 290 词表（BOLD 246）、23 短语、52 句式、12 个语言运用主题 |
| 阅读层 | 找信息困难 / 理解上下文困难 / 人物关系理解错误 / 推断错误 / 概括不到重点 | 阅读短答文本 + 选择答案 | §5 的 6 层阅读能力与对应 Section |
| 写作层 | 内容是否完整 / 表达是否清楚 / 句式使用情况 / 词汇使用情况 / 语法问题 / 重复表达 / 是否用上已学教材语言 | 句子、短段落、Presenting 产出 | 33 条骨架 + 19 条功能句 + 6 个教材写作任务 |
| 口语层 | **受限**：当前只能分析"读的是教材哪一句/哪一段"（音频↔文本锚定），**不能**分析发音、流利度、增漏词 | 现有 47 份官方音频 ASR + 422 条 HIGH 匹配 | §3.5 的音频资源状态 |

```text
重要边界（与 V1.3「没有证据，不评价」一致）：
  AI 不能凭空判断孩子"哪里不会"，必须基于已经产生的学习证据
  （做题答案 / 填空 / 句子 / 阅读回答 / 写作 / 口语录音 / Recall / 历史表现）。
  证据不足时，只能输出"目前记录较少，暂时无法形成可靠评价"。
```

### 7.3 AI 指导：可以怎么帮，不可以怎么帮

| 类型 | 可以做什么 | 示例（用教材语言） |
| --- | --- | --- |
| ① 结果解释 | 告诉孩子哪儿对了、哪儿有问题 | "这道题你找到了人物，但还没写他为什么这样做。" |
| ② 问题定位 | 说清问题属于哪个词 / 短语 / 句式 / 阅读理解 / 表达问题 | "问题不在理解，而在 `because` 后面没有给出原因。" |
| ③ 学习提示 | 指回教材的具体位置与句子 | "再看看教材第 19 页 `I feel... because...` 这一句。" |
| ④ 修改建议 | **不替孩子完成**，只让孩子自己修改、重答、重读 | "把 `I am happy.` 改成教材里的句式，自己补一句原因。" |

```text
明确不做：
  · AI 不自动给孩子布置学习计划（V1.3：AI 只能建议，孩子做决定）
  · AI 不直接替孩子写答案
  · AI 不用分数、等级、排名评价孩子
  · AI 不因为"题目好"就替孩子决定是否继续
```

---

## 8. 学习证据 → AI 判断（对应关系表）

| 学习证据 | 来源 | 可以支持什么 AI 判断 | 不可以支持什么 |
| --- | --- | --- | --- |
| 填空答案 | 教材 fill（124 题）/ AI 题 | 词汇与词形是否掌握、搭配是否正确、是否只会在原句里认词 | 不能据此判断"这个孩子口语如何" |
| 选择答案 | 教材 choice（30 题）/ AI 题 | 是否读懂题干、是否被干扰项带走 | 不能单独判断真实表达能力 |
| 匹配 / 排序答案 | 教材 match（14）/ order（2） | 句型结构与信息对应是否清楚 | 不能判断自由表达 |
| 判断题答案 | 教材 judge（3 题） | 教材事实记忆与理解 | 样本太少，不能推断整体 |
| **阅读短答文本** | 教材 short_answer（**111 题**） | 是否找到信息、是否答到点上、是否用上教材表达、因果是否说清 | 不能评价发音 |
| **句子 / 短段落写作** | 教材 writing（16 题）+ Presenting ideas（6 个任务） | 内容完整度、表达清楚度、句式使用、词汇使用、语法、重复、是否用上教材语言 | 不能代替教师给最终评价（V1.3：AI 只给建议） |
| 口语录音 | 教材 speaking（22 题） | **当前仅能**：锚定"读的是教材哪一句"、与教材目标表达对照（受限） | 不能做发音评分、流利度评分、增漏词检测（无资源） |
| Recall（回忆）结果 | 教材 reflection / 回顾类任务 | 记忆保持、是否需再巩固 | 不能单独作为掌握结论 |
| 历史表现 | `learning_record`（21 行）· `mastery_state`（7 行） | 哪些词/句式反复出错、是否标记 `review_needed` | 记录少时不能形成可靠评价（V1.3：「没有证据，不评价」） |

---

## 9. AI 闭环（正式形态）

```text
教材资源
   ↓
孩子学习 / 作答（教材原题优先 → AI 练习题作为补充）
   ↓
学习证据（答案·填空·句子·阅读回答·写作·口语录音·Recall·历史表现）
   ↓
AI 批改（客观题先由程序判定；短答/写作/口语由 AI 批改）
   ↓
AI 分析（知识层·阅读层·写作层·口语层，全部基于证据）
   ↓
AI 指导（结果解释 → 问题定位 → 学习提示 → 修改建议；不替孩子完成）
   ↓
孩子自己决定是否继续 / 是否巩固 / 是否换个内容
   ↓
（孩子选择巩固时）回到教材对应 Unit / Section 的同一句、同一词
```

三条与 V1.3 一致的红线：

```text
1. AI 只建议，孩子做决定（不自动排计划、不自动推进）
2. 没有证据不评价（证据不足时输出"暂时无法形成可靠评价"）
3. AI 不替代教材：讲解与练习都要回到教材原句、原词、原题型
```

---

## 10. AI 与确定性程序的边界

### 10.1 程序直接判断（不让 AI 参与）

```text
选择题正确性 · 填空字面匹配 · 匹配与排序 · 判断题 True/False
词汇边界（是否用了教材之外的词）· 证据是否存在与是否命中教材原文
题目去重 · 定位是否真实 · 生命周期（PENDING_REVIEW → APPROVED → ACTIVE）
```

### 10.2 适合 AI 判断

```text
英语表达是否自然 · 学习价值高低 · 干扰项是否合理 · 年级是否适配
答案是否可能存在第二个合理解法（只作风险提示，不作证明）
阅读短答与写作的内容质量、句式与词汇使用、是否用上教材语言
（口语分析受 §3.5 资源限制，暂不承诺）
```

### 10.3 需要程序 + AI 共同判断

| 任务 | 程序负责 | AI 负责 |
| --- | --- | --- |
| 重点词填空 | 答案字面对错、词汇是否越界 | 这个空是否只有这个词合理（语境是否唯一） |
| 阅读短答 | 是否为空、是否用上规定的教材词、长度是否合理 | 内容对不对、有没有答到点上、因果是否说清 |
| 句子 / 短段写作 | 字数、是否用上目标句式/词 | 内容完整性、表达清楚度、语法与重复问题 |
| 词汇语境选择 | 选项是否来自教材素材、是否有重复选项 | 干扰项是否合理、是否只有一个答案 |

```text
判断原则（沿用已确认口径）：
  程序负责「硬边界」——答案事实、证据、词汇范围、结构、去重、生命周期；
  AI 负责「语言与教育质量」——自然度、学习价值、表达质量、答案唯一性风险；
  人负责「是否采用」——最终决定权只在人手里。
```

---

## 11. 与 V1.3 / V2.0 的一致性

| 规范要求 | 本图的对应落地 |
| --- | --- |
| 教材是主线，AI 是辅助 | 所有练习与指导都以教材的 Unit / Section / 原句 / 词表为依据；AI 只在批改、分析、指导上出现 |
| 孩子拥有学习主动权 | AI 只给建议与提示；是否继续、是否巩固由孩子决定（§9 红线 1） |
| 没有证据不评价（V1.3 §二十四·2） | §8 的学习证据对照表；证据不足时只输出"暂时无法形成可靠评价" |
| 不用分数/排名/等级评价孩子 | §7.3 明确不做分数量化；沿用统一评价语言（未开始 / 学习中 / 基本掌握 / 掌握较稳定 / 需要巩固） |
| 不做无限题库（V1.3 §二·2、§九） | 题型与数量服从资源（§4）；选择题与判断题资源少就不硬凑 |
| 教材练习优先于自建练习（V1.3 §七·5） | §5/§6 的路线全部以教材原题型与写作任务为起点 |
| AI 建议 → 孩子决定 → 系统执行 | §9 的闭环与 §10 的边界表 |

---

## 12. 本图的一句话总结

```text
教材能支持的，是「词汇（246 个重点词）→ 阅读（每 Unit 3k+ 字符）→ 听力（17 个活动）→
读写结合（23 个活动）→ 表达产出（33 条句式骨架 + 6 个 Presenting 任务）→ 自评」这条链；

AI 能做的，是替孩子批改「没有唯一字符串答案」的那部分（教材 111 道短答 + 16 个写作任务 +
33 条句式骨架的表达），并把结果翻译成"哪一句教材原文没掌握"，再把修改权交还孩子；

资源不足的地方（选择题干扰项、判断题、音频文字化、口语评测），
如实记录为"当前正式资源不足，不适合强行扩展"，不为了数量而新建机制。
```
```
```
```
