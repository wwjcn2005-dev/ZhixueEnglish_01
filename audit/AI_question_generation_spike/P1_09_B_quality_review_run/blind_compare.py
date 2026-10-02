# -*- coding: utf-8 -*-
"""P1-09-B: blind comparison between the experimenter ground truth and the AI review.

Runs AFTER the AI call only. Writes comparison.json.
The ground truth is derived from P1-08-C / P1-09-A evidence; it is never sent to the model.
"""

import json
import os
import re
import sqlite3

BASE = r"D:\ZhixueEnglish"
LIB = os.path.join(BASE, "structured", "ai", "question_library.db")
HERE = os.path.dirname(os.path.abspath(__file__))

# experimenter-side expectations (evidence: P1-08-C human rejection record, P1-09-A sample matrix)
EXPECT = {
    "AIQ:1B3AF72923C4": {"answer_unique_problem": True, "low_learning_value": True,
                         "distractor_problem": False, "source":
                         "P1-08-C REVIEW_REJECTED(LOW_VALUE) + 审核记录记录题干不唯一"},
    "AIQ:120FFEECA78F": {"answer_unique_problem": True, "low_learning_value": False,
                         "distractor_problem": False, "source": "P1-09-A C3 答案不唯一风险"},
    "AIQ:1BA260727793": {"answer_unique_problem": False, "low_learning_value": True,
                         "distractor_problem": False,
                         "source": "P1-09-A C2/C4 低学习价值 + 机械挖空（双空）"},
    "AIQ:75AAEBFE06DF": {"answer_unique_problem": False, "low_learning_value": False,
                         "distractor_problem": True,
                         "source": "P1-09-A C5 干扰项 traditional/electric/weak 均为 BOLD 核心形容词"},
    "AIQ:B6463523F9E5": {"answer_unique_problem": False, "low_learning_value": False,
                         "distractor_problem": True,
                         "source": "P1-09-A C5 干扰项 sugar/oxygen/food 在他处同样成立"},
}


def main():
    sel = json.load(open(os.path.join(HERE, "sample_selection.json"), encoding="utf-8"))
    ai = json.load(open(os.path.join(HERE, "ai_review_output.json"), encoding="utf-8"))
    ai_by_id = {r["question_id"]: r for r in ai["reviews"]}

    con = sqlite3.connect("file:" + LIB.replace("\\", "/") + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    program_mech = {}
    for r in con.execute("SELECT question_id, note FROM question_validation"):
        m = re.search(r"mechanical_rewrite=(\w+)", r["note"] or "")
        program_mech[r["question_id"]] = (m.group(1) == "True") if m else None
    con.close()

    matrix = []
    for s in sel["samples"]:
        qid = s["question_id"]
        r = ai_by_id.get(qid)
        exp = EXPECT.get(qid, {"answer_unique_problem": False, "low_learning_value": False,
                               "distractor_problem": False, "source": "P1-09-A 已知正常题"})
        ai_uniq = r["answer_unique"]
        ai_learn = r["learning_value"]
        ai_distr = r["distractor_quality"]
        ai_dec = r["suggested_decision"]
        ai_mech = r["mechanical_level"]

        uniq_detected = ai_uniq in ("FAIL", "CONCERN") if exp["answer_unique_problem"] else None
        learn_detected = ai_learn in ("FAIL", "CONCERN") if exp["low_learning_value"] else None
        distr_detected = ai_distr in ("FAIL", "CONCERN") if exp["distractor_problem"] else None

        labelled_problem = s["ground_truth_label"] in ("CONFIRMED_PROBLEM", "RECORDED_RISK")
        false_negative = bool(labelled_problem and ai_dec == "SUGGEST_ACCEPT")
        false_positive = bool(s["ground_truth_label"] == "KNOWN_NORMAL"
                              and ai_dec == "SUGGEST_REJECT")
        soft_deviation = bool(s["ground_truth_label"] == "KNOWN_NORMAL"
                              and ai_dec == "SUGGEST_REVIEW")
        # mechanical comparison: AI marks DIRECT_REPRODUCTION vs program mechanical_rewrite flag
        prog = program_mech.get(qid)
        mech_agree = None
        if prog is not None:
            mech_agree = (ai_mech == "DIRECT_REPRODUCTION") == bool(prog) or (
                ai_mech in ("MECHANICAL_REWRITE",) and bool(prog))

        matrix.append({
            "question_id": qid, "question_type": s["question_type"],
            "ground_truth_label": s["ground_truth_label"],
            "known_issue": exp["source"],
            "expected": {"answer_unique_problem": exp["answer_unique_problem"],
                         "low_learning_value": exp["low_learning_value"],
                         "distractor_problem": exp["distractor_problem"],
                         "program_mechanical_rewrite": prog},
            "ai_finding": {"answer_unique": ai_uniq, "learning_value": ai_learn,
                           "distractor_quality": ai_distr, "mechanical_level": ai_mech,
                           "english_correct": r["english_correct"], "naturalness": r["naturalness"],
                           "grade_fit": r["grade_fit"],
                           "suggested_decision": ai_dec, "confidence": r["confidence"],
                           "evidence_concern": r.get("evidence_concern"),
                           "short_reason": r["short_reason"]},
            "answer_uniqueness_detected": uniq_detected,
            "learning_value_detected": learn_detected,
            "distractor_detected": distr_detected,
            "mechanical_agrees_with_program_flag": mech_agree,
            "false_positive": false_positive,
            "false_negative": false_negative,
            "soft_deviation_review_on_known_normal": soft_deviation,
        })

    def count(pred):
        return sum(1 for m in matrix if pred(m))

    summary = {
        "total_samples": len(matrix),
        "known_normal": count(lambda m: m["ground_truth_label"] == "KNOWN_NORMAL"),
        "recorded_risk": count(lambda m: m["ground_truth_label"] == "RECORDED_RISK"),
        "confirmed_problem": count(lambda m: m["ground_truth_label"] == "CONFIRMED_PROBLEM"),
        "false_negative": count(lambda m: m["false_negative"]),
        "false_positive": count(lambda m: m["false_positive"]),
        "soft_deviation_review_on_known_normal":
            count(lambda m: m["soft_deviation_review_on_known_normal"]),
        "answer_uniqueness_problems_expected":
            count(lambda m: m["expected"]["answer_unique_problem"]),
        "answer_uniqueness_detected":
            count(lambda m: m["answer_uniqueness_detected"] is True),
        "low_learning_value_expected":
            count(lambda m: m["expected"]["low_learning_value"]),
        "low_learning_value_detected":
            count(lambda m: m["learning_value_detected"] is True),
        "distractor_problems_expected":
            count(lambda m: m["expected"]["distractor_problem"]),
        "distractor_detected":
            count(lambda m: m["distractor_detected"] is True),
        "mechanical_flag_pairs":
            count(lambda m: m["mechanical_agrees_with_program_flag"] is not None),
        "mechanical_flag_agreements":
            count(lambda m: m["mechanical_agrees_with_program_flag"] is True),
        "decision_distribution": {
            d: count(lambda m, d=d: m["ai_finding"]["suggested_decision"] == d)
            for d in ("SUGGEST_ACCEPT", "SUGGEST_REVIEW", "SUGGEST_REJECT")},
        "by_question_type": {
            t: {"n": count(lambda m, t=t: m["question_type"] == t),
                "accept": count(lambda m, t=t: m["question_type"] == t
                                and m["ai_finding"]["suggested_decision"] == "SUGGEST_ACCEPT"),
                "review": count(lambda m, t=t: m["question_type"] == t
                                and m["ai_finding"]["suggested_decision"] == "SUGGEST_REVIEW"),
                "reject": count(lambda m, t=t: m["question_type"] == t
                                and m["ai_finding"]["suggested_decision"] == "SUGGEST_REJECT")}
            for t in sorted({m["question_type"] for m in matrix})},
    }
    with open(os.path.join(HERE, "comparison.json"), "w", encoding="utf-8") as fh:
        json.dump({"stage": "P1-09-B", "summary": summary, "matrix": matrix}, fh,
                  ensure_ascii=False, indent=2)

    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print()
    for m in matrix:
        print("%-20s %-14s %-18s FP=%-5s FN=%-5s uniq=%-7s learn=%-7s distr=%-16s"
              % (m["question_id"], m["question_type"], m["ground_truth_label"],
                 m["false_positive"], m["false_negative"], m["ai_finding"]["answer_unique"],
                 m["ai_finding"]["learning_value"], m["ai_finding"]["distractor_quality"]))


if __name__ == "__main__":
    main()
