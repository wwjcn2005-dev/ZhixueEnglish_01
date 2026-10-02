# P1-05-B 第一阶段 Dry-run 报告

- 生成时间：2026-09-12T11:11:45+08:00
- 结论：PASS
- textbook_id：FLTRP-EN-7A-2022CUR
- snapshot_id：FLTRP-EN-7A-2022CUR:S20260912T111145
- schema_version：p1-04-v1 / rule_set_version：P1-03-C

## 1. 环境与输入核验
- PDF：（根据2022年版课程标准修订）义务教育教科书·英语 七年级上册.pdf
- PDF SHA256：C732051E91121BC991DBDD01235662629620DF6BFCCBBBD834EAEA6FCECD4F2F
- MP3 数量：54
- 其他类型文件：无

## 2. 预计各表记录数

| 表 | 预计记录数 |
| --- | --- |
| activity | 96 |
| activity_content | 31 |
| ai_artifact | 0 |
| audio_asset | 54 |
| audio_mapping | 54 |
| content_asset | 628 |
| content_block | 3854 |
| evidence | 351 |
| image_block_total | 3793 |
| learner | 0 |
| learning_goal | 0 |
| learning_item | 0 |
| page | 178 |
| section | 46 |
| source_artifact | 55 |
| source_ref | 0 |
| sub_question | 13 |
| textbook_edition | 1 |
| unit | 8 |

## 3. 冻结统计复核

| 项目 | 实际 | 期望 | 结果 |
| --- | --- | --- | --- |
| unit | 8 | 8 | OK |
| section | 46 | 46 | OK |
| activity | 96 | 96 | OK |
| duplicate_anomaly | 0 | 0 | OK |
| boundary_need_review | 23 | 23 | OK |
| reading_order_need_review | 88 | 88 | OK |

## 4. 检查明细

| 检查 | 结果 | 说明 |
| --- | --- | --- |
| pdf_present | PASS | PDF 文件数 1 |
| pdf_sha256 | PASS | C732051E91121BC991DBDD01235662629620DF6BFCCBBBD834EAEA6FCECD4F2F (期望 C732051E91121BC991DBDD01235662629620DF6BFCCBBBD834EAEA6FCECD4F2F) |
| mp3_count | PASS | 54 (期望 54) |
| no_other_files | PASS | 其他类型文件 [] |
| frozen_unit | PASS | 8 (期望 8) |
| frozen_section | PASS | 46 (期望 46) |
| frozen_activity | PASS | 96 (期望 96) |
| frozen_duplicate | PASS | 0 (期望 0) |
| frozen_boundary_need_review | PASS | 23 (期望 23) |
| frozen_reading_order_need_review | PASS | 88 (期望 88) |
| parser_quality_control_chars | PASS | status=PASS |
| parser_quality_ligature | PASS | status=PASS |
| parser_quality_units | PASS | status=PASS |
| parser_quality_page_mapping | PASS | status=PASS |
| parser_quality_cross_unit | PASS | status=PASS |
| parser_quality_activity_numbering | PASS | status=PASS |
| parser_quality_activity_gaps | PASS | status=REVIEW（编号缺口保留待审，属预期） |
| pk_unique_textbook_edition | PASS | rows=1 dup=0 |
| pk_unique_source_artifact | PASS | rows=55 dup=0 |
| pk_unique_page | PASS | rows=178 dup=0 |
| pk_unique_unit | PASS | rows=8 dup=0 |
| pk_unique_section | PASS | rows=46 dup=0 |
| pk_unique_activity | PASS | rows=96 dup=0 |
| pk_unique_content_block | PASS | rows=3854 dup=0 |
| pk_unique_content_asset | PASS | rows=628 dup=0 |
| pk_unique_evidence | PASS | rows=351 dup=0 |
| pk_unique_audio_asset | PASS | rows=54 dup=0 |
| pk_unique_audio_mapping | PASS | rows=54 dup=0 |
| business_key_unique_page | PASS | 178 rows |
| business_key_unique_activity | PASS | 96 rows, dup=0 |
| fk_activity_section | PASS | activities=96 |
| fk_section_unit | PASS | sections=46 |
| fk_block_page | PASS | blocks=3854 |
| fk_asset_page | PASS | assets=628 |
| fk_audio_mapping_audio | PASS | mappings=54 |
| fk_audio_mapping_target | PASS | 候选目标必须存在或为空 |
| fk_activity_content | PASS | relations=31 |
| source_ref_completeness | PASS | L2 rows=0 source_ref rows=0（首次 Dry-run 未生成派生资源，规则暂为空集校验） |
| isolation_single_textbook | PASS | textbook_ids=['FLTRP-EN-7A-2022CUR'] |
| isolation_single_snapshot | PASS | FLTRP-EN-7A-2022CUR:S20260912T111145 |
| audio_all_candidate | PASS | 状态分布 {'CANDIDATE': 54}；CONFIRMED_BY_HUMAN=0 |
| content_hash_present | PASS | blocks=3854 empty_hash=0 |
| content_hash_deterministic | PASS | digest=8D1E451230FA4CFB… |
| need_review_preserved | PASS | boundary=23 order=88 |
| l3_ai_empty | PASS | ai_artifact rows=0 |
| l4_learner_empty | PASS | learner rows=0 |

## 5. Schema 探针

- 结果：OK
- 表数量：20
- 位置：in-memory (:memory:)，未创建任何 SQLite 文件

## 6. 音频

- audio_asset：54
- audio_mapping：54
- candidate：54
- confirmed：0
- target_resolved：23

## 7. AI 与正式数据库

- AI 调用次数：0
- 是否创建正式 contentpack SQLite：否
- 是否创建 learner.db：否
- 是否修改原始 PDF / MP3：否
- 是否修改 parser：否

## 8. 风险与待审项

- 无


## 10. 结论

Dry-run 全部硬性检查通过；未创建正式 contentpack SQLite，未创建 learner.db，未修改原始教材与 parser，AI 调用次数为 0。可以进入「P1-05-B 第二阶段：正式构建 contentpack v1 SQLite」
