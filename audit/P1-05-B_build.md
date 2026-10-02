# P1-05-B 第二阶段正式建库报告

- 生成时间：2026-09-12T11:11:50+08:00
- 结论：PASS
- 正式数据库：D:\ZhixueEnglish\structured\contentpack\v1\FLTRP-EN-7A-2022CUR.sqlite
- staging：D:\ZhixueEnglish\structured\staging\FLTRP-EN-7A-2022CUR.sqlite
- textbook_id：FLTRP-EN-7A-2022CUR
- snapshot_id：FLTRP-EN-7A-2022CUR:S20260912T111145
- import_batch：FLTRP-EN-7A-2022CUR:S20260912T111145:B0
- parser：v01-P1-03-C / rule_set：P1-03-C / schema：p1-04-v1
- PDF SHA256：C732051E91121BC991DBDD01235662629620DF6BFCCBBBD834EAEA6FCECD4F2F
- MP3 数量：54
- 正式库 SHA256：B7372AAC3782DF88D1965160B93A4F50E82A6364593497FB4B858BE645BA68E3

## 1. 各表最终数量

| 表 | 数量 |
| --- | --- |
| activity | 96 |
| activity_content | 31 |
| ai_artifact | 0 |
| audio_asset | 54 |
| audio_mapping | 54 |
| content_asset | 628 |
| content_block | 3854 |
| evidence | 351 |
| import_batch | 1 |
| import_batch_stage | 20 |
| learning_goal | 6 |
| learning_item | 0 |
| page | 178 |
| parse_snapshot | 1 |
| section | 46 |
| source_artifact | 55 |
| source_ref | 6 |
| sub_question | 13 |
| textbook_edition | 1 |
| transcript | 0 |
| unit | 8 |

## 2. 校验明细

| 检查 | 结果 | 说明 |
| --- | --- | --- |
| integrity_check | PASS | ok |
| foreign_key_check | PASS | violations=0 |
| count_textbook_edition | PASS | 1 (期望 1) |
| count_source_artifact | PASS | 55 (期望 55) |
| count_parse_snapshot | PASS | 1 (期望 1) |
| count_page | PASS | 178 (期望 178) |
| count_unit | PASS | 8 (期望 8) |
| count_section | PASS | 46 (期望 46) |
| count_activity | PASS | 96 (期望 96) |
| count_content_block | PASS | 3854 (期望 3854) |
| count_content_asset | PASS | 628 (期望 628) |
| count_evidence | PASS | 351 (期望 351) |
| count_activity_content | PASS | 31 (期望 31) |
| count_audio_asset | PASS | 54 (期望 54) |
| count_audio_mapping | PASS | 54 (期望 54) |
| count_ai_artifact | PASS | 0 (期望 0) |
| count_sub_question | PASS | 13（候选记录，全部 NEED_REVIEW） |
| business_key_page | PASS | duplicates=0 |
| pk_unique_page | PASS | duplicates=0 |
| pk_unique_unit | PASS | duplicates=0 |
| pk_unique_section | PASS | duplicates=0 |
| pk_unique_activity | PASS | duplicates=0 |
| pk_unique_content_block | PASS | duplicates=0 |
| pk_unique_content_asset | PASS | duplicates=0 |
| pk_unique_audio_asset | PASS | duplicates=0 |
| pk_unique_audio_mapping | PASS | duplicates=0 |
| pk_unique_evidence | PASS | duplicates=0 |
| textbook_id_consistent | PASS | distinct textbook_id in page = 1 |
| snapshot_id_consistent | PASS | distinct snapshot_id in page = 1 |
| source_ref_completeness | PASS | learning_goal=6 learning_item=0 source_ref=6 linked_goals=6 |
| content_hash_complete | PASS | empty=0 |
| audio_mapping_candidate | PASS | {'CANDIDATE': 54} |
| audio_mapping_total_54 | PASS | total=54 |
| ai_artifact_zero | PASS | 0 |
| need_review_preserved | PASS | activity=23 page_reading_order=88 |

## 3. 独立验收（重新打开正式库）

- integrity_check：ok
- foreign_key_check：0
- audio_mapping：54
- audio_confirmed：0
- ai_artifact：0
- learning_item：0
- learning_goal：6
- source_ref：6
- sub_question：13

## 4. staging → 正式库

- 临时文件：D:\ZhixueEnglish\structured\contentpack\v1\FLTRP-EN-7A-2022CUR.sqlite.tmp
- 原子替换为：D:\ZhixueEnglish\structured\contentpack\v1\FLTRP-EN-7A-2022CUR.sqlite
- staging SHA256：B7372AAC3782DF88D1965160B93A4F50E82A6364593497FB4B858BE645BA68E3
- 正式库 SHA256：B7372AAC3782DF88D1965160B93A4F50E82A6364593497FB4B858BE645BA68E3

## 5. 边界

- AI 调用次数：0
- learner 数据：0（L4 不入 contentpack）
- 原始 PDF / MP3：未修改
- parser：未修改
