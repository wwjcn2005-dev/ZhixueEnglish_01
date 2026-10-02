# -*- coding: utf-8 -*-
"""P1-09-D: dimension-level and decision-level blind comparison (runs AFTER the AI call only).

Writes comparison.json. Gold is never modified here.
"""

import collections
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
VAGUE = ["无显著问题", "语法不对", "感觉不自然", "可能有问题", "有问题"]


def load(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return json.load(fh)


def build_rows():
    fixtures = load("fixtures.json")
    gold = {g["fixture_id"]: g for g in load("hidden_gold.json")["gold"]}
    ai = {r["fixture_id"]: r for r in load("ai_review_output.json")["reviews"]}
    order = [f["fixture_id"] for f in fixtures["fixtures"]]

    rows = []
    for fid in order:
        g, r = gold[fid], ai[fid]
        dim_results, fp, fn, soft, unclassified = {}, [], [], [], []
        for dim, spec in g["scored"].items():
            v = r.get(dim)
            if v in spec["must_be_in"]:
                verdict = "MATCH"
            elif v in spec.get("fp_if", []):
                verdict = "FALSE_POSITIVE"
                fp.append(dim)
            elif v in spec.get("fn_if", []):
                verdict = "FALSE_NEGATIVE"
                fn.append(dim)
            elif v in spec.get("soft", []):
                verdict = "SOFT_DEVIATION"
                soft.append(dim)
            else:
                verdict = "UNCLASSIFIED_DEVIATION"
                unclassified.append(dim)
            dim_results[dim] = {"gold_expected": spec["must_be_in"], "ai": v, "verdict": verdict}

        rule = g["decision_rule"]
        dec = r["suggested_decision"]
        if rule == "not_accept":
            dec_ok = dec in ("SUGGEST_REVIEW", "SUGGEST_REJECT")
        elif rule == "not_reject":
            dec_ok = dec in ("SUGGEST_ACCEPT", "SUGGEST_REVIEW")
        else:
            dec_ok = dec == "SUGGEST_ACCEPT"
        fx = next(f for f in fixtures["fixtures"] if f["fixture_id"] == fid)
        rows.append({
            "fixture_id": fid, "category": g["category"], "subcategory": g["subcategory"],
            "question_type": fx["question_type"],
            "gold": {"scored": g["scored"], "decision_rule": rule, "gold_reason": g["gold_reason"]},
            "ai_result": r,
            "dimension_results": dim_results,
            "dimension_match": all(v["verdict"] == "MATCH" for v in dim_results.values()),
            "false_positive_dimensions": fp,
            "false_negative_dimensions": fn,
            "soft_deviation_dimensions": soft,
            "unclassified_dimensions": unclassified,
            "decision_match": dec_ok,
            "decision_false_negative": bool(not dec_ok and dec == "SUGGEST_ACCEPT"),
            "decision_false_positive": bool(not dec_ok and dec == "SUGGEST_REJECT"),
        })
    return rows, fixtures


def summarise(rows, fixtures):
    reasons = [r["ai_result"]["short_reason"] for r in rows]
    counts = collections.Counter(reasons)
    generic = []
    for row in rows:
        reason = row["ai_result"]["short_reason"]
        weak = any(v in reason for v in VAGUE) or counts[reason] >= 3
        row["explanation"] = {"short_reason": reason, "chars": len(reason),
                              "generic": weak, "same_text_count": counts[reason]}
        if weak:
            generic.append(row["fixture_id"])

    cats = collections.OrderedDict()
    for c in fixtures["category_labels"]:
        rs = [r for r in rows if r["category"] == c]
        scored = [d for r in rs for d in r["dimension_results"].values()]
        cats[c] = {
            "label": fixtures["category_labels"][c], "n": len(rs),
            "scored_dimension_checks": len(scored),
            "dimension_matches": sum(1 for d in scored if d["verdict"] == "MATCH"),
            "false_negative_dimensions": sum(1 for d in scored if d["verdict"] == "FALSE_NEGATIVE"),
            "false_positive_dimensions": sum(1 for d in scored if d["verdict"] == "FALSE_POSITIVE"),
            "soft_deviations": sum(1 for d in scored if d["verdict"] == "SOFT_DEVIATION"),
            "decision_matches": sum(1 for r in rs if r["decision_match"]),
            "fixtures_fully_matched": sum(1 for r in rs
                                          if r["dimension_match"] and r["decision_match"]),
        }

    summary = {
        "total_fixtures": len(rows),
        "dimension_checks": sum(len(r["dimension_results"]) for r in rows),
        "dimension_matches": sum(1 for r in rows for d in r["dimension_results"].values()
                                 if d["verdict"] == "MATCH"),
        "dimension_false_negative": sum(len(r["false_negative_dimensions"]) for r in rows),
        "dimension_false_positive": sum(len(r["false_positive_dimensions"]) for r in rows),
        "dimension_soft_deviation": sum(len(r["soft_deviation_dimensions"]) for r in rows),
        "dimension_unclassified": sum(len(r["unclassified_dimensions"]) for r in rows),
        "decision_matches": sum(1 for r in rows if r["decision_match"]),
        "decision_false_negative": sum(1 for r in rows if r["decision_false_negative"]),
        "decision_false_positive": sum(1 for r in rows if r["decision_false_positive"]),
        "fixtures_fully_matched": sum(1 for r in rows
                                      if r["dimension_match"] and r["decision_match"]),
        "generic_explanation_count": len(generic),
        "generic_explanation_ids": generic,
        "decision_masked_dimension_errors": [
            r["fixture_id"] for r in rows
            if (r["false_negative_dimensions"] or r["false_positive_dimensions"])
            and r["decision_match"]],
        "by_category": cats,
    }
    return summary


def report(summary, rows, fixtures):
    print(json.dumps({k: v for k, v in summary.items() if k != "by_category"},
                     ensure_ascii=False, indent=1))
    print()
    for v in summary["by_category"].values():
        print("%-28s n=%d dims=%d/%d FN=%d FP=%d soft=%d decision=%d/%d full=%d"
              % (v["label"], v["n"], v["dimension_matches"], v["scored_dimension_checks"],
                 v["false_negative_dimensions"], v["false_positive_dimensions"],
                 v["soft_deviations"], v["decision_matches"], v["n"],
                 v["fixtures_fully_matched"]))
    print()
    for r in rows:
        print("%-8s %-26s dim=%-5s dec=%-5s FN=%-20s FP=%-12s | %s"
              % (r["fixture_id"], r["category"], r["dimension_match"], r["decision_match"],
                 ",".join(r["false_negative_dimensions"]) or "-",
                 ",".join(r["false_positive_dimensions"]) or "-",
                 r["ai_result"]["short_reason"][:42]))


def main():
    rows, fixtures = build_rows()
    summary = summarise(rows, fixtures)
    with open(os.path.join(HERE, "comparison.json"), "w", encoding="utf-8") as fh:
        json.dump({"stage": "P1-09-D", "summary": summary, "rows": rows}, fh,
                  ensure_ascii=False, indent=2)
    report(summary, rows, fixtures)


if __name__ == "__main__":
    main()
