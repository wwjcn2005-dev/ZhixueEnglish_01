"""P1-02 · AI Question Library 最小测试（T1–T16）。

测试全部使用临时数据库；**绝不向正式 question_library.db 写入任何题目**。
T1 / T2 / T15 只读检查正式库结构，T16 校验 learning.db SHA256 未变化。
"""
import hashlib
import os
import sqlite3
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ql_schema as S  # noqa: E402

BASE = r"D:\ZhixueEnglish"
OFFICIAL_DB = os.path.join(BASE, "structured", "ai", "question_library.db")
LEARNING_DB = os.path.join(BASE, "structured", "learning", "learning.db")

SECTION_ID = "FLTRP-EN-7A-2022CUR:U1:UNDERSTANDING_IDEAS"
ACTIVITY_ID = "FLTRP-EN-7A-2022CUR:U1:UNDERSTANDING_IDEAS:A2"
TEXTBOOK_ID = "FLTRP-EN-7A-2022CUR"
SNAPSHOT_ID = "FLTRP-EN-7A-2022CUR:S20260912T151307"
PROMPT_VERSION = "P1-test"
CONTEXT_HASH = "A" * 64


def sha256_file(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest().upper()


class Base(unittest.TestCase):
    """提供一个临时库连接。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self._tmp.name, "ql_test.db")
        self.conn = sqlite3.connect(self.db_path)
        S.create_schema(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self._tmp.cleanup()

    # -------------------------------------------------- helpers
    def add_run(self, run_id="AIRUN:T1:0001", question_count=0, status="OK",
                insufficient_evidence=0, **kw):
        cols = {
            "run_id": run_id,
            "generation_scope_key": S.generation_scope_key(SECTION_ID, ACTIVITY_ID,
                                                            PROMPT_VERSION, CONTEXT_HASH),
            "textbook_id": TEXTBOOK_ID,
            "snapshot_id": SNAPSHOT_ID,
            "unit_id": "Unit 1",
            "section_id": SECTION_ID,
            "activity_id": ACTIVITY_ID,
            "model": "deepseek-v4-pro",
            "prompt_version": PROMPT_VERSION,
            "context_hash": CONTEXT_HASH,
            "question_count": question_count,
            "status": status,
            "insufficient_evidence": insufficient_evidence,
            "usage_json": '{"prompt_tokens": 1, "completion_tokens": 1}',
            "generated_at": "2026-09-17T16:00:00+08:00",
        }
        cols.update(kw)
        keys = ", ".join(cols)
        marks = ", ".join("?" for _ in cols)
        self.conn.execute("INSERT INTO generation_run (%s) VALUES (%s)" % (keys, marks),
                          list(cols.values()))
        self.conn.commit()
        return run_id

    def add_question(self, question_id="AIQ:000000000001", version=1, run_id="AIRUN:T1:0001",
                     qtype="fill", text="That is an ___ lesson!", answer="important",
                     options=None, fingerprint=None, status="GENERATED", **kw):
        fp = fingerprint or S.question_fingerprint(SECTION_ID, ACTIVITY_ID, qtype, text,
                                                   "That is an important lesson!")
        cols = {
            "question_id": question_id,
            "version": version,
            "question_type": qtype,
            "question_text": text,
            "options_json": options,
            "correct_answer": answer,
            "textbook_id": TEXTBOOK_ID,
            "snapshot_id": SNAPSHOT_ID,
            "unit_id": "Unit 1",
            "section_id": SECTION_ID,
            "activity_id": ACTIVITY_ID,
            "page": 17,
            "generation_run_id": run_id,
            "generated_at": "2026-09-17T16:00:00+08:00",
            "question_fingerprint": fp,
            "lifecycle_status": status,
            "active": 1 if status == "ACTIVE" else 0,
            "created_at": "2026-09-17T16:00:00+08:00",
            "updated_at": "2026-09-17T16:00:00+08:00",
        }
        cols.update(kw)
        keys = ", ".join(cols)
        marks = ", ".join("?" for _ in cols)
        self.conn.execute("INSERT INTO ai_question (%s) VALUES (%s)" % (keys, marks),
                          list(cols.values()))
        self.conn.commit()
        return fp

    def add_event(self, qid="AIQ:000000000001", version=1, event_type="VALIDATED",
                  actor="validator_v2", actor_kind="machine", to_status="VALIDATED",
                  reason_code=None, event_id=None, event_at="2026-09-17T16:05:00+08:00"):
        eid = event_id or ("AIEV:%s:%04d" % (event_type, self.conn.execute(
            "select count(*) from question_event").fetchone()[0] + 1))
        self.conn.execute(
            "INSERT INTO question_event (event_id, question_id, version, event_type, "
            "to_status, event_at, actor, actor_kind, reason_code) VALUES (?,?,?,?,?,?,?,?,?)",
            (eid, qid, version, event_type, to_status, event_at,
             actor, actor_kind, reason_code))
        self.conn.commit()

    def approve_and_activate(self, qid="AIQ:000000000001", version=1, stale=0,
                             stale_reason=None):
        self.add_event(qid=qid, version=version, event_type="REVIEW_APPROVED",
                       actor="reviewer-A", actor_kind="human", to_status="APPROVED")
        self.conn.execute(
            "UPDATE ai_question SET lifecycle_status='ACTIVE', active=1, "
            "stale=?, stale_reason=? WHERE question_id=? AND version=?",
            (stale, stale_reason, qid, version))
        self.conn.commit()


class StructureTests(Base):
    """T1 / T2 / T15：正式库结构（只读）。"""

    def test_T1_database_can_be_opened(self):
        self.assertTrue(os.path.exists(OFFICIAL_DB), "正式题库文件不存在")
        conn = sqlite3.connect("file:" + OFFICIAL_DB + "?mode=ro", uri=True)
        self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        conn.close()

    def test_T2_six_tables_exist(self):
        conn = sqlite3.connect("file:" + OFFICIAL_DB + "?mode=ro", uri=True)
        got = {r[0] for r in conn.execute(
            "select name from sqlite_master where type='table' and name not like 'sqlite_%'")}
        conn.close()
        self.assertEqual(got, set(S.TABLE_NAMES))

    def test_T15_official_db_has_no_real_questions(self):
        conn = sqlite3.connect("file:" + OFFICIAL_DB + "?mode=ro", uri=True)
        counts = {t: conn.execute("select count(*) from %s" % t).fetchone()[0]
                  for t in S.TABLE_NAMES}
        conn.close()
        self.assertEqual(counts["ai_question"], 0, "正式题库中不得存在任何真实题目")
        self.assertEqual(counts["question_evidence"], 0)
        self.assertEqual(counts["question_learning_object"], 0)
        self.assertEqual(counts["question_validation"], 0)
        self.assertEqual(counts["generation_run"], 0)
        self.assertEqual(counts["question_event"], 0)


class ConstraintTests(Base):
    """T3：主键 / UNIQUE / CHECK / FOREIGN KEY。"""

    def test_T3_primary_key_and_checks(self):
        self.add_run()
        self.add_question()

        # 主键唯一
        with self.assertRaises(sqlite3.IntegrityError):
            self.add_question()

        # 外键：generation_run_id 必须存在
        with self.assertRaises(sqlite3.IntegrityError):
            self.add_question(question_id="AIQ:000000000002", run_id="AIRUN:NOT-EXIST",
                              text="Another ___ item.", fingerprint="B" * 64)

        # CHECK：非法 question_type
        with self.assertRaises(sqlite3.IntegrityError):
            self.add_question(question_id="AIQ:000000000003", qtype="essay",
                              text="Write an ___ .", fingerprint="C" * 64)

        # CHECK：非法 lifecycle_status
        with self.assertRaises(sqlite3.IntegrityError):
            self.add_question(question_id="AIQ:000000000004", status="WHATEVER",
                              text="Yet another ___ .", fingerprint="D" * 64)

        # CHECK：active 与 lifecycle_status 必须一致
        with self.assertRaises(sqlite3.IntegrityError):
            self.add_question(question_id="AIQ:000000000005", status="GENERATED",
                              text="Inconsistent ___ state.", fingerprint="E" * 64,
                              active=1)

        # CHECK：stale=1 必须给出 stale_reason
        with self.assertRaises(sqlite3.IntegrityError):
            self.add_question(question_id="AIQ:000000000006", text="Stale without ___ .",
                              fingerprint="F" * 64, stale=1)

    def test_T3b_learning_object_cannot_be_a_question_id(self):
        self.add_run()
        self.add_question()
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO question_learning_object (question_id, version, item_id) "
                "VALUES ('AIQ:000000000001', 1, 'AIQ:000000000001')")


class CardinalityTests(Base):
    """T4–T7：0..N / 1:N 基数。"""

    def test_T4_run_with_zero_questions(self):
        self.add_run(run_id="AIRUN:ZERO", question_count=0, status="INSUFFICIENT_EVIDENCE",
                     insufficient_evidence=1, note="evidence insufficient")
        n = self.conn.execute(
            "select count(*) from ai_question where generation_run_id='AIRUN:ZERO'").fetchone()[0]
        self.assertEqual(n, 0)

    def test_T5_run_with_multiple_questions(self):
        self.add_run(question_count=3)
        self.add_question(question_id="AIQ:000000000011", text="One ___ here.",
                          fingerprint="1" * 64)
        self.add_question(question_id="AIQ:000000000012", text="Two ___ here.",
                          fingerprint="2" * 64)
        self.add_question(question_id="AIQ:000000000013", text="Three ___ here.",
                          fingerprint="3" * 64)
        n = self.conn.execute(
            "select count(*) from ai_question where generation_run_id='AIRUN:T1:0001'").fetchone()[0]
        self.assertEqual(n, 3)

    def test_T6_question_with_multiple_evidence(self):
        self.add_run()
        self.add_question()
        self.conn.executemany(
            "INSERT INTO question_evidence (question_id, version, ordinal, evidence_block_id, "
            "evidence_quote, is_primary) VALUES (?,?,?,?,?,?)",
            [("AIQ:000000000001", 1, 1, "FLTRP-EN-7A-2022CUR:P22:B9",
              "That is an important lesson!", 1),
             ("AIQ:000000000001", 1, 2, "FLTRP-EN-7A-2022CUR:P22:B5",
              "But then I think about the meaning of the sentence.", 0)])
        self.conn.commit()
        n = self.conn.execute("select count(*) from question_evidence "
                              "where question_id='AIQ:000000000001'").fetchone()[0]
        self.assertEqual(n, 2)
        # ordinal 唯一
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO question_evidence (question_id, version, ordinal, "
                "evidence_block_id, evidence_quote) VALUES (?,?,?,?,?)",
                ("AIQ:000000000001", 1, 2, "X", "Y"))

    def test_T7_question_with_multiple_learning_objects(self):
        self.add_run()
        self.add_question()
        self.conn.executemany(
            "INSERT INTO question_learning_object (question_id, version, item_id, is_primary) "
            "VALUES (?,?,?,?)",
            [("AIQ:000000000001", 1, "FLTRP-EN-7A-2022CUR:V:EAB999ECEC5C", 1),
             ("AIQ:000000000001", 1, "FLTRP-EN-7A-2022CUR:V:EAB999ECEC5D", 0)])
        self.conn.commit()
        n = self.conn.execute("select count(*) from question_learning_object "
                              "where question_id='AIQ:000000000001'").fetchone()[0]
        self.assertEqual(n, 2)
        # 关系唯一
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO question_learning_object (question_id, version, item_id) "
                "VALUES ('AIQ:000000000001', 1, 'FLTRP-EN-7A-2022CUR:V:EAB999ECEC5C')")


class ReuseTests(Base):
    """T8 / T9 / T13：fingerprint 去重与抑制。"""

    def test_T8_same_position_allows_multiple_distinct_questions(self):
        self.add_run(question_count=2)
        f1 = self.add_question(question_id="AIQ:000000000021", text="First ___ question.",
                               fingerprint="A1" * 32)
        f2 = self.add_question(question_id="AIQ:000000000022", text="Second ___ question.",
                               fingerprint="B1" * 32)
        self.assertNotEqual(f1, f2)
        n = self.conn.execute(
            "select count(*) from ai_question where section_id=? and activity_id=?",
            (SECTION_ID, ACTIVITY_ID)).fetchone()[0]
        self.assertEqual(n, 2, "同一教材位置必须允许多道不同题目")

    def test_T9_identical_fingerprint_rejected(self):
        self.add_run()
        fp = "AB" * 32
        self.add_question(question_id="AIQ:000000000031", text="Dup ___ one.", fingerprint=fp)
        # 相同 fingerprint、不同 question_id → 必须失败
        with self.assertRaises(sqlite3.IntegrityError):
            self.add_question(question_id="AIQ:000000000032", text="Dup ___ one.", fingerprint=fp)
        # 相同 fingerprint、同 question_id 的另一个版本 → 也必须失败
        with self.assertRaises(sqlite3.IntegrityError):
            self.add_question(question_id="AIQ:000000000031", version=2,
                              text="Dup ___ one.", fingerprint=fp)

    def test_T13_rejected_fingerprint_suppresses_regeneration(self):
        self.add_run()
        fp = "CD" * 32
        self.add_question(question_id="AIQ:000000000041", text="Rejected ___ item.",
                          fingerprint=fp, status="REJECTED", disabled_reason="LOW_VALUE")
        self.add_event(qid="AIQ:000000000041", event_type="REVIEW_REJECTED",
                       actor="reviewer-B", actor_kind="human", to_status="REJECTED",
                       reason_code="LOW_VALUE")
        # 抑制查询：按 fingerprint 能查到被驳回的题
        row = self.conn.execute(
            "select lifecycle_status from ai_question where question_fingerprint=?",
            (fp,)).fetchone()
        self.assertEqual(row[0], "REJECTED")
        # 结构性抑制：同指纹无法再次写入
        with self.assertRaises(sqlite3.IntegrityError):
            self.add_question(question_id="AIQ:000000000042", text="Rejected ___ item.",
                              fingerprint=fp)


class LifecycleTests(Base):
    """T10 / T11 / T12 / T14：版本、STALE、事件流、EXACT 陷阱。"""

    def test_T10_versions_coexist_without_overwrite(self):
        self.add_run()
        self.add_question(question_id="AIQ:000000000051", version=1,
                          text="Version one ___ text.", fingerprint="E1" * 32)
        self.add_question(question_id="AIQ:000000000051", version=2,
                          text="Version two ___ text.", fingerprint="E2" * 32)
        rows = self.conn.execute(
            "select version, question_text from ai_question where question_id=? "
            "order by version", ("AIQ:000000000051",)).fetchall()
        self.assertEqual([r[0] for r in rows], [1, 2])
        self.assertEqual(rows[0][1], "Version one ___ text.")
        self.assertEqual(rows[1][1], "Version two ___ text.")

    def test_T11_active_can_be_stale(self):
        self.add_run()
        self.add_question()
        self.add_event()   # VALIDATED
        self.approve_and_activate(stale=1, stale_reason="PROMPT_CHANGED")
        row = self.conn.execute(
            "select lifecycle_status, active, stale, stale_reason from ai_question").fetchone()
        self.assertEqual(row, ("ACTIVE", 1, 1, "PROMPT_CHANGED"))

    def test_T11b_validator_pass_never_becomes_active_automatically(self):
        self.add_run()
        self.add_question()
        self.conn.execute(
            "INSERT INTO question_validation (question_id, version, validator_version, "
            "validation_result, validated_at, answer_support_type, checks_json) "
            "VALUES (?,?,?,?,?,?,?)",
            ("AIQ:000000000001", 1, "v2", "PASS", "2026-09-17T16:04:00+08:00",
             "VERIFIABLE_REPHRASE", '{"1_location": true}'))
        self.conn.commit()
        # 没有人工审核事件时，不允许转为 ACTIVE
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("UPDATE ai_question SET lifecycle_status='ACTIVE', active=1 "
                              "WHERE question_id='AIQ:000000000001' AND version=1")
        # 新插入的题也不能直接是 ACTIVE
        with self.assertRaises(sqlite3.IntegrityError):
            self.add_question(question_id="AIQ:000000000061", text="Direct ___ active.",
                              fingerprint="F1" * 32, status="ACTIVE")

    def test_T12_event_stream_records_transitions_and_is_immutable(self):
        self.add_run()
        self.add_question()
        self.add_event(event_type="VALIDATED", to_status="PENDING_REVIEW",
                       event_at="2026-09-17T16:05:00+08:00")
        self.add_event(event_type="REVIEW_APPROVED", actor="reviewer-A",
                       actor_kind="human", to_status="APPROVED",
                       event_at="2026-09-17T16:06:00+08:00")
        self.add_event(event_type="ACTIVATED", actor="reviewer-A", actor_kind="human",
                       to_status="ACTIVE", event_at="2026-09-17T16:07:00+08:00")
        types = [r[0] for r in self.conn.execute(
            "select event_type from question_event order by event_at, event_id")]
        self.assertEqual(types, ["VALIDATED", "REVIEW_APPROVED", "ACTIVATED"])
        # 事件不可改写、不可删除
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("UPDATE question_event SET actor='hacker'")
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("DELETE FROM question_event")
        # 题目不可删除
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("DELETE FROM ai_question")

    def test_T14_exact_trap_forces_human_review(self):
        self.add_run()
        # 题干/选项中出现与答案相同的文本 → EXACT 命中可能只是“教材印着这个选项”
        self.add_question(question_id="AIQ:000000000071", qtype="vocab_choice",
                          text="It is hard to ___ their time.",
                          answer="plan", options='["plan", "hope", "join", "help"]',
                          fingerprint="A2" * 32)
        self.conn.execute(
            "INSERT INTO question_validation (question_id, version, validator_version, "
            "validation_result, validated_at, answer_support_type, checks_json, "
            "needs_human_review) VALUES (?,?,?,?,?,?,?,0)",
            ("AIQ:000000000071", 1, "v2", "PASS", "2026-09-17T16:06:00+08:00",
             "EXACT", '{"1_location": true}'))
        self.conn.commit()
        v = self.conn.execute("select needs_human_review from question_validation "
                              "where question_id='AIQ:000000000071'").fetchone()[0]
        q = self.conn.execute("select needs_human_review from ai_question "
                              "where question_id='AIQ:000000000071'").fetchone()[0]
        self.assertEqual(v, 1, "EXACT + 选项命中必须强制 needs_human_review=1")
        self.assertEqual(q, 1)

    def test_T14b_exact_without_option_hit_is_not_forced(self):
        self.add_run()
        # 答案是句子本身、且不出现在题干/选项中 → 不应被误判为陷阱
        self.add_question(question_id="AIQ:000000000072", qtype="reading_choice",
                          text="What does Wang Han say about the sentence?",
                          answer="That sentence is from Confucius, not from Mencius.",
                          options='["It is from Mencius.", "It has no mistake.", "It is from Ms Chen."]',
                          fingerprint="B2" * 32)
        self.conn.execute(
            "INSERT INTO question_validation (question_id, version, validator_version, "
            "validation_result, validated_at, answer_support_type, checks_json, "
            "needs_human_review) VALUES (?,?,?,?,?,?,?,0)",
            ("AIQ:000000000072", 1, "v2", "PASS", "2026-09-17T16:07:00+08:00",
             "EXACT", '{"1_location": true}'))
        self.conn.commit()
        v = self.conn.execute("select needs_human_review from question_validation "
                              "where question_id='AIQ:000000000072'").fetchone()[0]
        self.assertEqual(v, 0)


class ProtectionTests(unittest.TestCase):
    """T16：learning.db 未修改。"""

    def test_T16_learning_db_unchanged(self):
        before = sha256_file(LEARNING_DB)
        after = sha256_file(LEARNING_DB)
        self.assertEqual(before, after)
        self.assertEqual(before, "0C27267BF83A70A75BB400F0055B62CB2985A83EDD120B9AC790A7FD5E59CF91",
                         "learning.db 哈希与 P1-01 基线不一致")


if __name__ == "__main__":
    unittest.main(verbosity=2)
