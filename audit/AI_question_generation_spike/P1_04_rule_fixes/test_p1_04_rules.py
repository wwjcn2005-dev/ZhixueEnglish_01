"""P1-04 专用测试（T1–T15 + §九 硬门槛复验）。

全部测试使用内存数据库；只读检查正式 question_library.db，绝不对其写入。
"""
import os
import sqlite3
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ql_schema_v2 as S2     # noqa: E402
import validator_v3 as V3     # noqa: E402

LIB = os.path.join(r"D:\ZhixueEnglish", "structured", "ai", "question_library.db")
TEXTBOOK_ID = "FLTRP-EN-7A-2022CUR"
SNAPSHOT = "FLTRP-EN-7A-2022CUR:S20260912T151307"
UNIT_ID = "FLTRP-EN-7A-2022CUR:U1"
SECTION_ID = "FLTRP-EN-7A-2022CUR:U1:UNDERSTANDING_IDEAS"
ACTIVITY_ID = "FLTRP-EN-7A-2022CUR:U1:UNDERSTANDING_IDEAS:A2"
BLOCK_ID = "FLTRP-EN-7A-2022CUR:P22:B2"
TS = "2026-09-17T19:00:00+08:00"
QUOTE = ('But is it OK to point out the mistake? Is that polite, in the first lesson?"')


class Base(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        S2.create_schema_v2(self.conn)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute(
            "INSERT INTO generation_run (run_id, generation_scope_key, textbook_id, snapshot_id, "
            "unit_id, section_id, model, prompt_version, context_hash, question_count, status, "
            "generated_at) VALUES ('AIRUN:T','SCOPE',?,?,?,?,'deepseek-v4-pro','P0-v1','CTX',0,'OK',?)",
            (TEXTBOOK_ID, SNAPSHOT, UNIT_ID, SECTION_ID, TS))
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def add_question(self, qid="AIQ:T0001", qtype="vocab_choice", text="Is that ___?",
                     answer="polite", options='["polite","dry","important","mistake"]',
                     correct_option="A", quote=QUOTE, with_evidence=True,
                     version=1):
        self.conn.execute(
            "INSERT INTO ai_question (question_id, version, question_type, question_text, "
            "options_json, correct_option, correct_answer, textbook_id, snapshot_id, unit_id, "
            "section_id, activity_id, page, generation_run_id, generated_at, question_fingerprint, "
            "lifecycle_status, active, stale, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,17,'AIRUN:T',?,?, 'GENERATED',0,0,?,?)",
            (qid, version, qtype, text, options, correct_option, answer, TEXTBOOK_ID, SNAPSHOT,
             UNIT_ID, SECTION_ID, ACTIVITY_ID, TS, "F" * 64, TS, TS))
        if with_evidence:
            self.conn.execute(
                "INSERT INTO question_evidence (question_id, version, ordinal, evidence_block_id, "
                "evidence_quote, is_primary) VALUES (?,?,1,?,?,1)", (qid, version, BLOCK_ID, quote))
        self.conn.commit()
        return qid

    def add_validation(self, qid="AIQ:T0001", support="EXACT", result="PASS", version=1):
        self.conn.execute(
            "INSERT INTO question_validation (question_id, version, validator_version, "
            "validation_result, validated_at, answer_support_type, checks_json, "
            "needs_human_review) VALUES (?,?,'v3',?,?,?,?,0)",
            (qid, version, result, TS, support, '{"8_type_rules": true}'))
        self.conn.commit()

    def nhr(self, qid="AIQ:T0001", version=1):
        return self.conn.execute("select needs_human_review from ai_question "
                                 "where question_id=? and version=?", (qid, version)).fetchone()[0]


class ExactRuleTests(Base):
    """T1–T4：EXACT 特殊人工复核条件（数据库触发器为权威实现）。"""

    def test_T1_plain_fill_exact_not_triggered(self):
        # 纯填空：无 options，答案在 quote 中 —— 不因题干/选项规则触发
        self.add_question(qid="AIQ:T1", qtype="fill", text="Is that ___?",
                          options=None, correct_option=None)
        self.add_validation("AIQ:T1")
        self.assertEqual(self.nhr("AIQ:T1"), 0)

    def test_T2_choice_answer_in_options_only_not_triggered(self):
        # 选择题：答案在 options，但 evidence_quote 中**没有**该答案 → 不触发
        self.add_question(qid="AIQ:T2", quote='"But is it OK to point out the mistake?"')
        self.add_validation("AIQ:T2")
        self.assertEqual(self.nhr("AIQ:T2"), 0)

    def test_T3_choice_answer_in_evidence_triggers(self):
        # 选择题：正确答案直接出现在 evidence_quote → 触发
        self.add_question(qid="AIQ:T3")
        self.add_validation("AIQ:T3")
        self.assertEqual(self.nhr("AIQ:T3"), 1)

    def test_T4_distractor_in_evidence_does_not_trigger(self):
        # 错误选项出现在 quote，正确答案不在 → 不触发
        q = '"But is it OK to point out the mistake?"'
        self.add_question(qid="AIQ:T4", answer="polite", quote=q)
        self.add_validation("AIQ:T4")
        self.assertEqual(self.nhr("AIQ:T4"), 0)

    def test_T4b_python_rule_matches_sql_semantics(self):
        self.assertTrue(V3.exact_print_risk("EXACT", ["polite"], "polite", [QUOTE]))
        self.assertFalse(V3.exact_print_risk("EXACT", ["polite"], "polite",
                                             ['"But is it OK to point out the mistake?"']))
        self.assertFalse(V3.exact_print_risk("EXACT", None, "polite", [QUOTE]))
        self.assertFalse(V3.exact_print_risk(
            "VERIFIABLE_REPHRASE", ["polite"], "polite", [QUOTE]))


class FillRuleTests(unittest.TestCase):
    """T5–T10：fill 结构规则（validator v3）。"""

    BASE = {"type": "fill", "question": "That's really an ___ lesson!",
            "answer": "important"}

    def test_T5_normal_fill_passes(self):
        ok, reason = V3.type_rules(dict(self.BASE))
        self.assertTrue(ok, reason)

    def test_T6_fill_with_options_fails(self):
        ok, reason = V3.type_rules(dict(self.BASE, options=["important", "meaning"]))
        self.assertFalse(ok)
        self.assertIn("options", reason)

    def test_T7_fill_with_correct_option_fails(self):
        ok, reason = V3.type_rules(dict(self.BASE, correct_option="A"))
        self.assertFalse(ok)
        self.assertIn("correct_option", reason)

    def test_T8_fill_with_options_and_correct_option_fails(self):
        ok, reason = V3.type_rules(dict(self.BASE, options=["important", "meaning"],
                                        correct_option="A"))
        self.assertFalse(ok)

    def test_T9_vocab_choice_may_carry_options(self):
        ok, _ = V3.type_rules({"type": "vocab_choice", "question": "Is that ___?",
                               "options": ["polite", "dry", "important", "mistake"],
                               "correct_option": "A", "answer": "polite"})
        self.assertTrue(ok)

    def test_T10_reading_choice_may_carry_options(self):
        ok, _ = V3.type_rules({"type": "reading_choice", "question": "What does he say?",
                               "options": ["A.", "B.", "C."], "correct_option": "B",
                               "answer": "B."})
        self.assertTrue(ok)

    def test_T10b_fill_without_blank_still_fails(self):
        ok, _ = V3.type_rules({"type": "fill", "question": "No blank here",
                               "answer": "x"})
        self.assertFalse(ok)

    def test_T10c_v2_fill_rule_unchanged_for_other_types(self):
        # v3 没有放宽 v2：reading_judge 仍需布尔答案
        ok, _ = V3.type_rules({"type": "reading_judge", "question": "Is it polite?",
                               "answer": "maybe"})
        self.assertFalse(ok)
        ok2, _ = V3.type_rules({"type": "reading_judge", "question": "Is it polite?",
                                "answer": "true"})
        self.assertTrue(ok2)


class EventSchemaTests(Base):
    """T11–T15：event 枚举 v2。"""

    def _ev(self, ev, eid):
        self.conn.execute(
            "INSERT INTO question_event (event_id, question_id, version, event_type, from_status,"
            " to_status, event_at, actor, actor_kind) VALUES (?,?,1,?,?,?,?,?,'machine')",
            (eid, "AIQ:T11", ev, None, ev, TS, "p1_04_test"))
        self.conn.commit()

    def setUp(self):
        super().setUp()
        self.add_question(qid="AIQ:T11")

    def test_T11_can_record_generated(self):
        self._ev("GENERATED", "AIEV:T11G")
        self.assertEqual(self.conn.execute("select event_type from question_event").fetchone()[0],
                         "GENERATED")

    def test_T12_can_record_validated(self):
        self._ev("VALIDATED", "AIEV:T11V")
        self.assertEqual(self.conn.execute("select event_type from question_event").fetchone()[0],
                         "VALIDATED")

    def test_T13_can_record_pending_review(self):
        self._ev("PENDING_REVIEW", "AIEV:T11P")
        self.assertEqual(self.conn.execute("select event_type from question_event").fetchone()[0],
                         "PENDING_REVIEW")

    def test_T14_events_remain_append_only(self):
        self._ev("GENERATED", "AIEV:T11G")
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("UPDATE question_event SET actor='x'")
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("DELETE FROM question_event")

    def test_T14b_invalid_event_type_still_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self._ev("NOT_A_REAL_EVENT", "AIEV:T11X")

    def test_T14c_review_approved_still_requires_human(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self._ev("REVIEW_APPROVED", "AIEV:T11A")


class HardGateTests(Base):
    """§九：v2 schema 上重新确认全部硬门槛。"""

    def test_gate_question_cannot_be_inserted_as_active(self):
        cols = ("question_id, version, question_type, question_text, correct_answer, textbook_id,"
                " snapshot_id, unit_id, section_id, generation_run_id, generated_at,"
                " question_fingerprint, lifecycle_status, active, stale, created_at, updated_at")
        vals = ("'AIQ:G1',1,'fill','Is that ___?','polite',?,?,?,?, 'AIRUN:T',?,?, 'ACTIVE',1,0,?,?")
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("INSERT INTO ai_question (%s) VALUES (%s)" % (cols, vals),
                              (TEXTBOOK_ID, SNAPSHOT, UNIT_ID, SECTION_ID, TS, "A" * 64, TS, TS))

    def test_gate_active_requires_human_review_approved(self):
        self.add_question(qid="AIQ:G2")
        self.add_validation("AIQ:G2")
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("UPDATE ai_question SET lifecycle_status='ACTIVE', active=1")
        # 机器不允许伪造人工审批事件（CHECK 约束更强：直接拒绝写入）
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO question_event (event_id, question_id, version, event_type, event_at,"
                " actor, actor_kind) VALUES ('AIEV:G2','AIQ:G2',1,'REVIEW_APPROVED',?, 'bot','machine')",
                (TS,))
        # 仅 VALIDATED（机器）不足以 ACTIVE
        self.conn.execute(
            "INSERT INTO question_event (event_id, question_id, version, event_type, event_at,"
            " actor, actor_kind) VALUES ('AIEV:G2V','AIQ:G2',1,'VALIDATED',?, 'validator_v3','machine')",
            (TS,))
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("UPDATE ai_question SET lifecycle_status='ACTIVE', active=1")
        # 人工事件后允许
        self.conn.execute(
            "INSERT INTO question_event (event_id, question_id, version, event_type, event_at,"
            " actor, actor_kind) VALUES ('AIEV:G2H','AIQ:G2',1,'REVIEW_APPROVED',?, 'human','human')",
            (TS,))
        self.conn.execute("UPDATE ai_question SET lifecycle_status='ACTIVE', active=1")
        self.assertEqual(self.conn.execute(
            "select lifecycle_status from ai_question where question_id='AIQ:G2'").fetchone()[0],
            "ACTIVE")

    def test_gate_question_cannot_be_deleted(self):
        self.add_question(qid="AIQ:G3")
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("DELETE FROM ai_question")

    def test_gate_unsupported_cannot_pass(self):
        self.add_question(qid="AIQ:G4")
        with self.assertRaises(sqlite3.IntegrityError):
            self.add_validation("AIQ:G4", support="UNSUPPORTED", result="PASS")

    def test_gate_aiq_cannot_be_learning_object(self):
        self.add_question(qid="AIQ:G5")
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("INSERT INTO question_learning_object "
                              "(question_id, version, item_id) VALUES ('AIQ:G5',1,'AIQ:G5')")
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("INSERT INTO question_learning_object "
                              "(question_id, version, item_id) VALUES ('AIQ:G5',1,'AIRUN:T')")

    def test_gate_v2_schema_has_extended_enum_and_new_trigger(self):
        sql = self.conn.execute("select sql from sqlite_master where name='question_event'").fetchone()[0]
        self.assertIn("GENERATED", sql)
        self.assertIn("PENDING_REVIEW", sql)
        trg = self.conn.execute(
            "select sql from sqlite_master where name='trg_validation_exact_trap'").fetchone()[0]
        self.assertIn("question_evidence", trg)
        self.assertIn("instr(", trg)
        self.assertNotIn("q.question_text", trg, "新规则不再依据 question_text 触发")


class FrozenV1SchemaTests(unittest.TestCase):
    """P1-02 T15 的原始意图：**建库脚本本身不得插入任何数据**。

    P1-02 的 T15 断言“正式题库为空”，该断言已被 P1-03 的合法入库取代；
    这里用同一 v1 schema 定义在内存库上复核其真正意图（建库 = 只建结构）。
    """

    def test_v1_schema_definition_inserts_no_data(self):
        import ql_schema as V1
        conn = sqlite3.connect(":memory:")
        V1.create_schema(conn)
        for t in V1.TABLE_NAMES:
            self.assertEqual(conn.execute("select count(*) from %s" % t).fetchone()[0], 0)
        self.assertEqual(V1.SCHEMA_VERSION, 1, "v1 schema 定义必须保持冻结")
        conn.close()

    def test_v2_schema_definition_inserts_no_data(self):
        conn = sqlite3.connect(":memory:")
        S2.create_schema_v2(conn)
        for t in S2.TABLE_NAMES:
            self.assertEqual(conn.execute("select count(*) from %s" % t).fetchone()[0], 0)
        conn.close()


class LiveDataTests(unittest.TestCase):
    """T15：正式库仍可读，且 P1-03 的两道题保持完好。"""

    def test_T15_existing_p103_questions_still_readable(self):
        conn = sqlite3.connect("file:" + LIB + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        qs = [dict(r) for r in conn.execute(
            "select question_id, version, question_type, question_text, options_json, "
            "correct_answer, question_fingerprint, lifecycle_status, needs_human_review "
            "from ai_question order by question_id")]
        ev = [dict(r) for r in conn.execute(
            "select question_id, version, event_type, from_status, to_status from question_event "
            "order by event_id")]
        lo = [r[0] for r in conn.execute("select distinct item_id from question_learning_object")]
        ver = conn.execute("PRAGMA user_version").fetchone()[0]
        conn.close()
        self.assertEqual(len(qs), 2, "P1-03 的两道真实题必须仍在")
        self.assertEqual([q["question_id"] for q in qs], ["AIQ:3179968E3E74", "AIQ:7EBCDBC29563"])
        for q in qs:
            self.assertEqual(q["lifecycle_status"], "PENDING_REVIEW")
            self.assertEqual(len(q["question_fingerprint"]), 64)
        self.assertEqual(
            {q["correct_answer"] for q in qs}, {"polite", "sentence"})
        self.assertEqual(len(lo), 3)
        self.assertEqual(ver, 2, "正式库应为 schema v2")
        validated = [e for e in ev if e["event_type"] == "VALIDATED"]
        self.assertEqual(len(validated), 2, "P1-03 的 VALIDATED 事件必须仍在")
        for e in validated:
            self.assertEqual(e["from_status"], "GENERATED")
            self.assertEqual(e["to_status"], "PENDING_REVIEW")
        # P1-04 追加的 MARKED_STALE 事件（派生字段修正），不改变 lifecycle
        stale_events = [e for e in ev if e["event_type"] == "MARKED_STALE"]
        self.assertEqual(len(stale_events), 1)
        self.assertEqual(stale_events[0]["question_id"], "AIQ:7EBCDBC29563")
        self.assertEqual(stale_events[0]["to_status"], "PENDING_REVIEW")


if __name__ == "__main__":
    unittest.main(verbosity=2)
