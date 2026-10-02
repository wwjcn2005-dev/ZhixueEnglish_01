# -*- coding: utf-8 -*-
"""P1-09-E: read-only audit of existing data capability for a candidate-answer pool.

AI calls = 0. No database or asset is modified. Writes data_capability_audit.json.
"""

import collections
import json
import os
import sqlite3

BASE = r"D:\ZhixueEnglish"
HERE = os.path.dirname(os.path.abspath(__file__))
ST = os.path.join(BASE, "structured")
CP = os.path.join(ST, "contentpack", "v5", "FLTRP-EN-7A-2022CUR.sqlite")
LEARN = os.path.join(ST, "learning", "learning.db")
LIB = os.path.join(ST, "ai", "question_library.db")


def ro(path):
    con = sqlite3.connect("file:" + path.replace("\\", "/") + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def keys_union(rows, limit=None):
    ks = set()
    for r in (rows[:limit] if limit else rows):
        ks |= set(r.keys())
    return sorted(ks)


def main():
    out = {"stage": "P1-09-E", "ai_calls": 0, "resources": {}}

    # 1 textbook_structure_v2.json
    ts = json.load(open(os.path.join(ST, "textbook", "textbook_structure_v2.json"),
                        encoding="utf-8"))
    units = ts["units"]
    sec_keys = keys_union([s for u in units for s in u.get("sections", [])])
    act_keys = keys_union([a for u in units for s in u.get("sections", [])
                           for a in s.get("activities", [])])
    q_keys = keys_union([q for u in units for s in u.get("sections", [])
                         for a in s.get("activities", []) for q in a.get("questions", [])])
    out["resources"]["textbook_structure_v2"] = {
        "path": "structured/textbook/textbook_structure_v2.json", "size": os.path.getsize(
            os.path.join(ST, "textbook", "textbook_structure_v2.json")),
        "top_keys": sorted(ts.keys()), "counts": ts["counts"],
        "unit_keys": keys_union(units), "section_keys": sec_keys, "activity_keys": act_keys,
        "question_keys": q_keys,
        "usable_for_candidate_pool": "indirect",
        "note": "提供 Unit/Section/Activity/Question 的层级与定位；不含答案、不含词性。",
    }

    # 2 exercise_catalog_v3.json
    cat = json.load(open(os.path.join(ST, "exercises", "exercise_catalog_v3.json"),
                         encoding="utf-8"))
    exs = cat["exercises"]
    out["resources"]["exercise_catalog_v3"] = {
        "path": "structured/exercises/exercise_catalog_v3.json",
        "size": os.path.getsize(os.path.join(ST, "exercises", "exercise_catalog_v3.json")),
        "top_keys": sorted(cat.keys()), "counts": cat["counts"],
        "exercise_keys": keys_union(exs),
        "question_type_distribution": dict(collections.Counter(
            e.get("question_type") for e in exs)),
        "answer_status_distribution": dict(collections.Counter(
            e.get("answer_status") for e in exs)),
        "check_items_present": sum(1 for e in exs if e.get("check_items")),
        "options_present": sum(1 for e in exs if e.get("options")),
        "blank_line_total": sum(e.get("blanks") or 0 for e in exs),
        "usable_for_candidate_pool": "yes_for_exercise_types",
        "note": "check_items 是教材自带的匹配/清单型答案项（例如文具词），"
                "可作为候选来源之一；但 answer_status 全部为 NO_RELIABLE_SOURCE。",
    }

    # 3 exercise_question_relations_v3.json
    eq = json.load(open(os.path.join(ST, "exercises", "exercise_question_relations_v3.json"),
                        encoding="utf-8"))
    qs = eq["questions"]
    rv = [len(q.get("related_vocabulary") or []) for q in qs]
    out["resources"]["exercise_question_relations_v3"] = {
        "path": "structured/exercises/exercise_question_relations_v3.json",
        "size": os.path.getsize(os.path.join(ST, "exercises",
                                            "exercise_question_relations_v3.json")),
        "count": eq["count"], "top_keys": sorted(eq.keys()),
        "question_keys": keys_union(qs),
        "question_type_distribution": dict(collections.Counter(q["question_type"] for q in qs)),
        "answer_source_distribution": dict(collections.Counter(q["answer_source"] for q in qs)),
        "related_vocabulary_present": sum(1 for n in rv if n > 0),
        "related_vocabulary_avg": round(sum(rv) / len(rv), 2),
        "related_vocabulary_max": max(rv),
        "related_text_present": sum(1 for q in qs if q.get("related_text")),
        "usable_for_candidate_pool": "yes_vocabulary_links",
        "note": "related_vocabulary 是教材问答 → 词汇的正式关联（303/360），"
                "是候选池最直接的现成来源；但它只给词，不给词性、不给屈折形式。",
    }

    # 4 textbook_evidence_map_v1.json
    em = json.load(open(os.path.join(ST, "ai", "textbook_evidence_map_v1.json"),
                        encoding="utf-8"))
    pkgs = em["packages"]
    rvp = [len(p.get("related_vocabulary") or []) for p in pkgs]
    out["resources"]["textbook_evidence_map_v1"] = {
        "path": "structured/ai/textbook_evidence_map_v1.json",
        "size": os.path.getsize(os.path.join(ST, "ai", "textbook_evidence_map_v1.json")),
        "package_count": em["package_count"], "package_keys": keys_union(pkgs),
        "answer_source_distribution": dict(collections.Counter(
            p["answer_source"] for p in pkgs)),
        "ai_rules_sample": pkgs[0].get("ai_rules"),
        "related_vocabulary_present": sum(1 for n in rvp if n > 0),
        "related_text_kinds": dict(collections.Counter(
            t.get("kind") for p in pkgs for t in (p.get("related_text") or []))),
        "usable_for_candidate_pool": "yes_vocabulary_and_text_links",
        "note": "每个题一个证据包，含 related_text（block 级）与 related_vocabulary；"
                "answer_source 全部 NO_RELIABLE_SOURCE。",
    }

    # 5 contentpack
    cp = ro(CP)
    cur = cp.cursor()
    lit = {}
    for r in cur.execute("SELECT item_type, COUNT(*) n FROM learning_item GROUP BY 1 ORDER BY 2 DESC"):
        lit[r["item_type"]] = r["n"]
    fields = {}
    for r in cur.execute("""
            SELECT item_type,
                   SUM(CASE WHEN lemma IS NULL OR lemma='' THEN 1 ELSE 0 END) no_lemma,
                   SUM(CASE WHEN surface_form IS NULL OR surface_form='' THEN 1 ELSE 0 END) no_surface,
                   SUM(CASE WHEN part_of_speech IS NULL OR part_of_speech='' THEN 1 ELSE 0 END) no_pos,
                   SUM(CASE WHEN meaning_zh IS NULL OR meaning_zh='' THEN 1 ELSE 0 END) no_meaning
            FROM learning_item GROUP BY 1"""):
        fields[r["item_type"]] = {"no_lemma": r["no_lemma"], "no_surface_form": r["no_surface"],
                                 "no_part_of_speech": r["no_pos"], "no_meaning_zh": r["no_meaning"]}
    em2 = {r[0]: r[1] for r in cur.execute(
        "SELECT textbook_emphasis, COUNT(*) FROM source_ref GROUP BY 1")}
    req = {r[0]: r[1] for r in cur.execute(
        "SELECT learning_requirement, COUNT(*) FROM learning_item GROUP BY 1")}
    der = {r[0]: r[1] for r in cur.execute(
        "SELECT derivation_type, COUNT(*) FROM learning_item GROUP BY 1")}
    vocab_bold = cur.execute("""
        SELECT COUNT(DISTINCT i.item_id) FROM learning_item i
        JOIN source_ref s ON s.item_id = i.item_id
        WHERE i.item_type='vocabulary' AND s.textbook_emphasis='BOLD'""").fetchone()[0]
    vocab_total = cur.execute(
        "SELECT COUNT(*) FROM learning_item WHERE item_type='vocabulary'").fetchone()[0]
    pos_dist = {r[0]: r[1] for r in cur.execute(
        "SELECT part_of_speech, COUNT(*) FROM learning_item WHERE item_type='vocabulary'"
        " GROUP BY 1 ORDER BY 2 DESC")}
    out["resources"]["contentpack_v5"] = {
        "path": "structured/contentpack/v5/FLTRP-EN-7A-2022CUR.sqlite",
        "size": os.path.getsize(CP),
        "learning_item_by_type": lit, "missing_field_by_type": fields,
        "textbook_emphasis_distribution": em2,
        "learning_requirement_distribution": req,
        "derivation_type_distribution": der,
        "vocabulary_total": vocab_total,
        "vocabulary_with_BOLD": vocab_bold,
        "vocabulary_part_of_speech_distribution": pos_dist,
        "learning_item_columns": [c[1] for c in cur.execute("PRAGMA table_info(learning_item)")],
        "source_ref_columns": [c[1] for c in cur.execute("PRAGMA table_info(source_ref)")],
        "usable_for_candidate_pool": "yes_primary",
        "note": "learning_item 同时有 lemma / surface_form / part_of_speech / "
                "learning_requirement / derivation_type；source_ref 带 textbook_emphasis(BOLD) "
                "与 emphasis_source_list（Words and expressions / Vocabulary A-Z）。"
                "这是候选池唯一同时具备词性 + 重点词标记的来源。",
    }
    cp.close()

    # 6 learning.db (read-only inventory)
    ld = ro(LEARN)
    lcur = ld.cursor()
    tabs = [r[0] for r in lcur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        " ORDER BY name")]
    out["resources"]["learning_db"] = {
        "path": "structured/learning/learning.db", "size": os.path.getsize(LEARN),
        "tables": tabs,
        "row_counts": {t: lcur.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
                       for t in tabs},
        "usable_for_candidate_pool": "no",
        "note": "学习行为数据；与答案唯一性判定无关，只作为边界确认。",
    }
    ld.close()

    # 7 question_library.db (read-only)
    lib = ro(LIB)
    lcur = lib.cursor()
    out["resources"]["question_library_db"] = {
        "path": "structured/ai/question_library.db", "size": os.path.getsize(LIB),
        "user_version": lcur.execute("PRAGMA user_version").fetchone()[0],
        "tables": [r[0] for r in lcur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")],
        "question_type_distribution": {r[0]: r[1] for r in lcur.execute(
            "SELECT question_type, COUNT(*) FROM ai_question GROUP BY 1")},
        "answer_support_distribution": {r[0]: r[1] for r in lcur.execute(
            "SELECT answer_support_type, COUNT(*) FROM question_validation GROUP BY 1")},
        "storage_available_for_candidates": "none_today",
        "note": "question_validation 只能存 validator 结论与 4 值 answer_support_type，"
                "没有候选答案的位置（详见 §11）。",
    }
    lib.close()

    # 8 P1-08-B evidence_assembly
    p1_08_b = os.path.join(BASE, "audit", "AI_question_generation_spike",
                           "P1_08_B_evidence_assembly_fix", "evidence_assembly.py")
    out["resources"]["evidence_assembly_p1_08_b"] = {
        "path": "audit/AI_question_generation_spike/P1_08_B_evidence_assembly_fix/"
                "evidence_assembly.py",
        "exists": os.path.exists(p1_08_b), "size": os.path.getsize(p1_08_b),
        "public_api": ["section_page_ranges", "pages_of_section", "blocks_of_section",
                       "activities_of_section", "build_section_evidence",
                       "blocks_by_activity_only"],
        "usable_for_candidate_pool": "yes_context",
        "note": "可从 contentpack 只读重建 Section / Activity 级连续正文，"
                "是候选判定的上下文来源，P1-09-C 已采用。",
    }

    # 9 P1-09-C contracts
    cdir = os.path.join(BASE, "audit", "AI_question_generation_spike",
                        "P1_09_C_review_contract")
    out["resources"]["p1_09_c_contracts"] = {
        "files": {n: os.path.getsize(os.path.join(cdir, n))
                  for n in sorted(os.listdir(cdir)) if n.endswith(".md")},
        "usable_for_candidate_pool": "yes_contract_baseline",
    }

    # 10 P1-09-D fixtures + report
    ddir = os.path.join(BASE, "audit", "AI_question_generation_spike",
                        "P1_09_D_boundary_validation")
    dsum = json.load(open(os.path.join(ddir, "comparison.json"), encoding="utf-8"))["summary"]
    out["resources"]["p1_09_d_boundary_validation"] = {
        "fixtures": len(json.load(open(os.path.join(ddir, "fixtures.json"),
                                       encoding="utf-8"))["fixtures"]),
        "dimension_matches": dsum["dimension_matches"],
        "dimension_checks": dsum["dimension_checks"],
        "answer_unique_false_negative": dsum["dimension_false_negative"],
        "by_category": {k: v["fixtures_fully_matched"] for k, v in dsum["by_category"].items()},
        "usable_for_candidate_pool": "yes_fixtures",
    }

    # 11 existing validator / gate / fingerprint code
    val_dir = os.path.join(BASE, "audit", "AI_question_generation_spike",
                           "20260917_1520_validator_fix")
    v3 = os.path.join(BASE, "audit", "AI_question_generation_spike", "P1_04_rule_fixes",
                      "validator_v3.py")
    ing = os.path.join(BASE, "audit", "AI_question_generation_spike", "P1_07_library_ingest",
                       "build_candidates.py")
    out["resources"]["validator_and_gates"] = {
        "validator_v2": {"path": os.path.join(val_dir, "validator_v2.py"),
                         "helpers": ["tokens", "_lemmas", "_same_lemma", "answer_support",
                                     "out_of_scope", "checked_language", "build_whitelist"],
                         "inflection_support": "normalize_only(_lemmas: ies/es/s/ed/ing 归并)"},
        "validator_v3": {"path": v3, "helpers": ["type_rules", "exact_print_risk",
                                                "validate_question", "validate_batch"]},
        "candidate_gate_p1_07": {"path": ing},
        "fingerprint": "ai_question.question_fingerprint（64 hex，唯一索引）",
        "usable_for_candidate_pool": "yes_reusable_helpers",
        "note": "validator_v2._lemmas 只能把词形归并到词元方向，"
                "不能反向生成屈折形式；候选池需要另外的词形生成规则。",
    }

    with open(os.path.join(HERE, "data_capability_audit.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    for k, v in out["resources"].items():
        print("%-34s %s" % (k, v.get("usable_for_candidate_pool", "")))
    print()
    print("contentpack vocabulary:", out["resources"]["contentpack_v5"]["vocabulary_total"],
          "| BOLD:", out["resources"]["contentpack_v5"]["vocabulary_with_BOLD"],
          "| POS dist:", json.dumps(
              out["resources"]["contentpack_v5"]["vocabulary_part_of_speech_distribution"],
              ensure_ascii=False))
    print("questions with related_vocabulary:",
          out["resources"]["exercise_question_relations_v3"]["related_vocabulary_present"],
          "/", eq["count"])
    print("all answer_source values:",
          out["resources"]["exercise_question_relations_v3"]["answer_source_distribution"])


if __name__ == "__main__":
    main()
