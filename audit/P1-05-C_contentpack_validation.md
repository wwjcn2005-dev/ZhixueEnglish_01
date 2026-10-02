# P1-05-C contentpack v1 独立验收报告

- 生成时间：2026-09-12T11:22:40+08:00
- 结论：PASS WITH NOTES
- 数据库：D:\ZhixueEnglish\structured\contentpack\v1\FLTRP-EN-7A-2022CUR.sqlite
- SHA256：B7372AAC3782DF88D1965160B93A4F50E82A6364593497FB4B858BE645BA68E3
- 大小：1835008 字节
- 失败项：0  提示项：6

## 检查明细

| 组 | 检查 | 结果 | 说明 |
| --- | --- | --- | --- |
| file | db_exists | PASS | D:\ZhixueEnglish\structured\contentpack\v1\FLTRP-EN-7A-2022CUR.sqlite |
| file | db_sha256 | PASS | B7372AAC3782DF88D1965160B93A4F50E82A6364593497FB4B858BE645BA68E3（P1-05-B 构建值 B7372AAC3782DF88…） |
| sqlite | integrity_check | PASS | ok |
| sqlite | foreign_key_check | PASS | 0 rows |
| sqlite | journal_mode | PASS | delete |
| sqlite | encoding | PASS | UTF-8 |
| schema | schema_required_tables | PASS | missing=[] |
| schema | schema_no_unexpected_tables | PASS | extra=[] |
| schema | schema_no_temp_tables | PASS | suspicious=[] |
| schema | schema_every_table_has_pk | PASS | no_pk=[] |
| schema | schema_foreign_keys_present | PASS | tables_with_fk=['import_batch_stage', 'section', 'activity', 'content_block', 'content_asset', 'activity_content', 'sub_question', 'audio_mapping'] |
| schema | schema_indexes | NOTE | 当前仅有 PRIMARY KEY / UNIQUE 隐式索引，未建显式查询索引（首次构建可接受，建议后续版本按查询路径补索引） |
| identity | textbook_edition_count | PASS | 1 rows |
| identity | textbook_id | PASS | FLTRP-EN-7A-2022CUR |
| identity | textbook_publisher | PASS | 外语教学与研究出版社 |
| identity | textbook_grade_volume | PASS | grade=7 volume=A title=义务教育教科书·英语 七年级上册 |
| identity | textbook_curriculum | PASS | 义务教育英语课程标准（2022年版） |
| identity | textbook_id_single_in_pages | PASS | distinct=1 |
| artifact | source_artifact_total | PASS | 55（pdf=1 audio=54） |
| artifact | source_artifact_pdf_sha256 | PASS | C732051E91121BC991DBDD01235662629620DF6BFCCBBBD834EAEA6FCECD4F2F |
| artifact | source_artifact_pdf_on_disk | PASS | D:\ZhixueEnglish\2025年度初一外研版英语教材\（根据2022年版课程标准修订）义务教育教科书·英语 七年级上册.pdf |
| structure | count_page | PASS | 178 (期望 178) |
| structure | count_unit | PASS | 8 (期望 8) |
| structure | count_section | PASS | 46 (期望 46) |
| structure | count_activity | PASS | 96 (期望 96) |
| structure | unit_codes | PASS | ['Appendix', 'Starter', 'Unit 1', 'Unit 2', 'Unit 3', 'Unit 4', 'Unit 5', 'Unit 6'] |
| structure | structure_no_orphan_section | PASS | 0 |
| structure | structure_no_orphan_activity | PASS | 0 |
| structure | structure_activity_page_traceable | PASS | activity 无对应 page 的数量=0 |
| structure | structure_activity_fields | PASS | 缺字段行数=0 |
| page | page_sample_size | PASS | 21 页 |
| page | page_mapping_consistency | PASS | 异常=[] |
| page | page_special_pages | PASS | [(1, None, 'front_matter'), (2, None, 'front_matter'), (3, None, 'front_matter'), (4, None, 'front_matter'), (5, None, 'front_matter'), (6, None, 'front_matter'), (115, None, 'no_printed_page_number'), (177, None, 'no_printed_page_number'), (178, None, 'back_cover')] |
| block | count_content_block | PASS | 3854 |
| block | block_raw_not_replaced | PASS | text_raw 为空但 normalized 非空=0 |
| block | block_hash_present | PASS | 0 |
| block | block_page_fk | PASS | 0 |
| block | block_hash_recompute | PASS | checked=3854 mismatch=0 |
| block | block_control_chars | NOTE | 全库含控制字符的 block = 22/3854，字符集 ['0x7']，样例 [{'block_id': 'FLTRP-EN-7A-2022CUR:P2:B5', 'snippet': '编    者:\x07王德美  刘敬雯  何润青  宋靖霞 '}, {'block_id': 'FLTRP-EN-7A-2022CUR:P8:B11', 'snippet': '1 ?Li Ming:\t \x07Here it is. And look a'}, {'block_id': 'FLTRP-EN-7A-2022CUR:P8:B16', 'snippet': '\tMum:\t How about you, Li Meng?Li Men'}]（来自 PDF 文本层原始标记，text_raw 保留原文；建议后续在 text_normalized 中清理） |
| block | block_kind_distribution | NOTE | {'exercise_item': 2984, 'sidebar_tip': 348, 'heading': 344, 'footer_text': 178}（dialogue=0 说明构建器的 block_kind 启发式未命中教材中的弯引号对话，属分类精度问题，不影响原文保全） |
| asset | count_content_asset | PASS | 628 (期望 628) |
| asset | asset_unique_page_xref | PASS | duplicates=0 |
| asset | asset_page_fk | PASS | 0 |
| asset | asset_placement_count | PASS | 0 |
| asset | asset_tiny_fragment_preserved | PASS | tiny_fragment=352 |
| evidence | count_evidence | PASS | 351 |
| evidence | evidence_page_fk | PASS | 0 |
| evidence | evidence_extraction_version | NOTE | 缺少 extraction_version 的行数=351 |
| evidence | evidence_bbox | NOTE | 缺少 bbox 的行数=351 |
| evidence | evidence_textbook_page | PASS | textbook_page 为空 9 条，其中因对应页面本身无印刷页码（特殊页）9 条属预期；真实缺失 0 条 |
| evidence | evidence_isolation_fields | NOTE | 缺少 textbook_id/snapshot_id 的行数=351 |
| evidence | evidence_source_types | PASS | {'parser_rule': 69, 'pdf_text': 274, 'pdf_toc': 8} |
| activity_content | count_activity_content | PASS | 31 |
| activity_content | activity_content_types | PASS | {'auxiliary_same_column': 22, 'separate_region': 9} |
| activity_content | activity_content_no_orphan | PASS | 0 |
| sub_question | count_sub_question | PASS | 13 |
| sub_question | sub_question_all_need_review | PASS | {'NEED_REVIEW': 13} |
| sub_question | sub_question_no_guessed_activity | PASS | activity_id 为空=13 |
| audio | count_audio_asset | PASS | 54 |
| audio | audio_asset_fields | PASS | 0 |
| audio | audio_file_set_match | PASS | disk=54 db=54 |
| audio | audio_disk_cross_check | PASS | checked=54 mismatches=[] |
| audio | count_audio_mapping | PASS | 54 |
| audio | audio_mapping_status | PASS | {'CANDIDATE': 54} |
| audio | audio_mapping_targets | PASS | 有目标=23 无效目标=0 |
| learning | count_learning_goal | PASS | 6 |
| learning | learning_goal_origin | PASS | {'TEXTBOOK_EXPLICIT'} |
| learning | learning_goal_scopes | PASS | ['FLTRP-EN-7A-2022CUR:U1', 'FLTRP-EN-7A-2022CUR:U2', 'FLTRP-EN-7A-2022CUR:U3', 'FLTRP-EN-7A-2022CUR:U4', 'FLTRP-EN-7A-2022CUR:U5', 'FLTRP-EN-7A-2022CUR:U6'] |
| learning | learning_goal_source_ref | PASS | goals=6 refs=6 |
| learning | learning_goal_trace_chain | PASS | 断链=0 |
| learning | learning_item_zero | PASS | 0 |
| ai | ai_artifact_zero | PASS | 0 |
| ai | transcript_zero | PASS | 0 |
| ai | l4_not_in_contentpack | PASS | contentpack 内 L4 表=[] |
| ai | no_learner_db | PASS | [] |
| need_review | need_review_activity_boundary | PASS | 23 (期望 23) |
| need_review | need_review_reading_order | PASS | 88 (期望 88) |
| need_review | need_review_sub_question | PASS | 13 (期望 13) |
| pollution | pollution_scan | PASS | 无命中 |
| readonly | readonly_open | PASS | mode=ro 只读打开成功，page=178 |
| readonly | readonly_suitability | PASS | 数据库为单文件、无外部依赖、可用 mode=ro 打开；适合作为随 APP 发布的只读内容包 |
| independence | independence | PASS | 验收脚本仅使用标准库 sqlite3/hashlib/json/re/struct/os/pathlib，未 import parser、未 import builder |
