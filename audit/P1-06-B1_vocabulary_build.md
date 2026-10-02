# P1-06-B-1 教材 Vocabulary 首批构建报告

- 生成时间：2026-09-12T11:34:42+08:00
- 结论：PASS
- snapshot_id：FLTRP-EN-7A-2022CUR:S20260912T113441
- import_batch：FLTRP-EN-7A-2022CUR:S20260912T113441:B0
- schema_version：p1-04-v2 / rule_set：P1-06-B-1
- v1 SHA256（保持不变）：B7372AAC3782DF88D1965160B93A4F50E82A6364593497FB4B858BE645BA68E3

## contentpack v2

- 路径：D:\ZhixueEnglish\structured\contentpack\v2\FLTRP-EN-7A-2022CUR.sqlite
- SHA256：C97B0F4EB09811F2477723A40A01B695DA984DDF1BD5FA5668B59ADC61ED0430
- 大小：2211840 字节

## Vocabulary 数量

| 指标 | 数量 |
| --- | --- |
| candidates_raw | 574 |
| from_words_and_expressions | 287 |
| from_vocabulary_az | 287 |
| before_dedup | 574 |
| after_dedup | 287 |
| ok | 196 |
| need_review | 91 |
| rejected | 0 |
| proper_nouns_skipped | 36 |
| multiword_entries | 22 |
| cross_block_merged | 68 |
| multi_source_items | 287 |

## v2 受控增强

- evidence_textbook_id_snapshot_id：True
- evidence_extraction_version：True
- evidence_bbox_for_activity_targets：True
- text_normalized_control_chars_cleaned：22
- block_kind_refined_rows：851
- learning_item_extended_columns：['canonical_text', 'display_text', 'schema_version', 'content_hash', 'created_at', 'updated_at']
- need_review_preserved：True

## 校验

- [PASS] integrity：integrity_check
- [PASS] foreign_key：fk
- [PASS] vocabulary_items：vocabulary=287
- [PASS] source_ref_closure：无来源的 Vocabulary=0
- [PASS] source_ref_block_exists：断链=0
- [PASS] content_hash_present：缺 hash=0
- [PASS] need_review_preserved：activity NEED_REVIEW=23
- [PASS] block_kind_improved：{'dialogue': 132, 'exercise_item': 2133, 'footer_text': 178, 'heading': 344, 'instruction': 194, 'sidebar_tip': 348, 'vocabulary_entry': 525}
- [PASS] no_ai：ai_artifact=0

## 抽样

**words_and_expressions**（20 条）
- ready /ˈredi/ adj. 准备好(做某事)的 3
- textbook /ˈtekstbʊk/ n. 教科书,教材, 课本 3
- eraser /ɪˈreɪzə/ n. 橡皮 3
- junior high 初级中学 3
- geography /dʒiˈɒɡrəfi/ n. 地理 4
- biology /baɪˈɒlədʒi/ n. 生物 4
- history /ˈhɪstəri/ n. 历史 4
- grey /ɡreɪ/ adj. 灰色的 5
- jacket /ˈdʒækɪt/ n. 夹克,短上衣 5
- red scarf 红领巾 5
- T-shirt /ˈtiː ʃɜːt/ n. T恤衫,短袖运动衫 5
- uniform /ˈjuːnəfɔːm/ n. 制服 5
- school uniform 校服 5
- of course 当然 5
- forget /fəˈɡet/ v. 忘记,遗忘 5
- teaching building 教学楼 6
- dining hall 食堂 6
- together /təˈɡeðə/ adv. 一起,共同, 一齐,一块儿 6
- lab /læb/ n. 实验室 6
- start /stɑːt/ v. 开始 8

**vocabulary_az**（20 条）
- ready /ˈredi/ adj. 准备好(做某事)的 3
- textbook /ˈtekstbʊk/ n. 教科书,教材, 课本 3
- eraser /ɪˈreɪzə/ n. 橡皮 3
- junior high 初级中学 3
- geography /dʒiˈɒɡrəfi/ n. 地理 4
- biology /baɪˈɒlədʒi/ n. 生物 4
- history /ˈhɪstəri/ n. 历史 4
- grey /ɡreɪ/ adj. 灰色的 5
- jacket /ˈdʒækɪt/ n. 夹克,短上衣 5
- red scarf 红领巾 5
- T-shirt /ˈtiː ʃɜːt/ n. T恤衫,短袖运动衫 5
- uniform /ˈjuːnəfɔːm/ n. 制服 5
- school uniform 校服 5
- of course 当然 5
- forget /fəˈɡet/ v. 忘记,遗忘 5
- teaching building 教学楼 6
- dining hall 食堂 6
- together /təˈɡeðə/ adv. 一起,共同, 一齐,一块儿 6
- lab /læb/ n. 实验室 6
- start /stɑːt/ v. 开始 8

**multiword**（10 条）
- junior high 初级中学 3
- red scarf 红领巾 5
- school uniform 校服 5
- of course 当然 5
- teaching building 教学楼 6
- dining hall 食堂 6
- each other 互相,彼此 9
- a bit 有点儿,稍微 10
- take part in 参加,参与 13
- point out 指出,指明 17

**cross_block_merged**（10 条）
- textbook /ˈtekstbʊk/ n. 教科书,教材, 课本 3
- together /təˈɡeðə/ adv. 一起,共同, 一齐,一块儿 6
- everyone /ˈevriwʌn/ pron. 每个人, 人人 9
- introduce /ˌɪntrəˈdjuːs/ v. 介绍 9 你自己 9
- nervous /ˈnɜːvəs/ adj. 神经紧张的; 焦虑不安的 10
- meaning /ˈmiːnɪŋ/ n. 意义,意思, 含义 17
- important /ɪmˈpɔːtənt/ adj. 重要的, 重大的 17
- problem /ˈprɒbləm/ n. 问题,难题; 困难 22
- homework /ˈhəʊmwɜːk/ n. 家庭作业, 功课 22
- project /ˈprɒdʒekt/ n. (学校的) 课题,研究项目 23

**need_review**（10 条）
- textbook /ˈtekstbʊk/ n. 教科书,教材, 课本 3
- junior high 初级中学 3
- red scarf 红领巾 5
- school uniform 校服 5
- of course 当然 5
- teaching building 教学楼 6
- dining hall 食堂 6
- together /təˈɡeðə/ adv. 一起,共同, 一齐,一块儿 6
- each other 互相,彼此 9
- everyone /ˈevriwʌn/ pron. 每个人, 人人 9

## 边界

- v1_modified：False
- pdf_modified：False
- mp3_modified：False
- parser_modified：False
- builder_modified：False
- ai_calls：0
- learner_rows：0
