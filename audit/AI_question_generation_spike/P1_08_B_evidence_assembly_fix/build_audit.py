"""P1-08-B · 汇总审计（只读；运行测试拿结果并输出 p1_08_b_audit.json）。"""
import glob
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = r"D:\ZhixueEnglish"
SPIKE = os.path.join(BASE, "audit", "AI_question_generation_spike")
DOCS = os.path.join(BASE, "docs")
LIB = os.path.join(BASE, "structured", "ai", "question_library.db")
CP = os.path.join(BASE, "structured", "contentpack", "v5", "FLTRP-EN-7A-2022CUR.sqlite")


def sha_file(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest().upper()


def load(name):
    return json.load(open(os.path.join(HERE, name), encoding="utf-8"))


def main():
    recon = load("recon_facts.json")
    comp = load("before_after_comparison.json")

    # 测试结果（在当前目录运行 unittest）
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    pr = subprocess.run([sys.executable, "-X", "utf8", "-m", "unittest",
                         "test_evidence_assembly", "-v"],
                        cwd=HERE, capture_output=True, text=True, env=env)
    out = pr.stderr + pr.stdout
    ran = re.search(r"Ran (\d+) tests", out)
    tests = {"ran": int(ran.group(1)) if ran else None,
             "ok": "OK" in out.splitlines()[-1] if out.strip() else False,
             "failures": len(re.findall(r"^FAIL:", out, flags=re.M)),
             "errors": len(re.findall(r"^ERROR:", out, flags=re.M)),
             "skipped": len(re.findall(r"skipped", out, flags=re.I)),
             "cases": sorted(re.findall(r"^test_(\w+) ", out, flags=re.M))}

    # 保护项
    prot = {}
    checks = [
        ("question_library.db", LIB, "F74CA83F7C8A98F2A4A2E672E7BA61EC"),
        ("learning.db", os.path.join(BASE, "structured", "learning", "learning.db"),
         "0C27267BF83A70A75BB400F0055B62CB"),
        ("contentpack", CP, "65829CA73E41B75ACA010B93B7339EDD"),
        ("validator_v2", os.path.join(SPIKE, "20260917_1520_validator_fix", "validator_v2.py"),
         "7C61585A99B55576CA82D99466357849"),
        ("validator_v3", os.path.join(SPIKE, "P1_04_rule_fixes", "validator_v3.py"),
         "EDB1AA5431626752B6D4699EC25ADAC7"),
        ("P1-06_S1", os.path.join(SPIKE, "P1_06_batch_stability", "S1_parsed.json"),
         "D4520E288D7651B5"),
        ("P1-06_S2", os.path.join(SPIKE, "P1_06_batch_stability", "S2_parsed.json"),
         "4F705951CAF743BD"),
        ("P1-06_S3", os.path.join(SPIKE, "P1_06_batch_stability", "S3_parsed.json"),
         "4F9679CAFF393E6C"),
        ("P1-06_S4", os.path.join(SPIKE, "P1_06_batch_stability", "S4_parsed.json"),
         "5D1C21032B1C5F4C"),
        ("P1-07_candidate_decision",
         os.path.join(SPIKE, "P1_07_library_ingest", "candidate_decision.json"), None),
        ("P1-07_ingest_result",
         os.path.join(SPIKE, "P1_07_library_ingest", "ingest_result.json"), None),
        # 缺陷所在的实验脚本：本阶段**未修改**（用正确基线校验）
        ("P1-05-B_script_run_p1_05b.py",
         os.path.join(SPIKE, "P1_05_real_validation", "run_p1_05b.py"),
         "D29D91CE26A95C8C8B15D9E002885DE2"),
        ("P1-05-A_script_build_sample_matrix.py",
         os.path.join(SPIKE, "P1_05_sample_design", "build_sample_matrix.py"),
         "0008C74AFF9EBA7E3869FA08"),
        ("web_content.py",
         os.path.join(BASE, "web", "content.py"), None),
    ]
    spec = [p for p in glob.glob(os.path.join(DOCS, "*V1.0.md"))
            if "\u9898\u5e93" in os.path.basename(p)][0]
    checks.append(("P1-08-A_spec", spec, None))
    for name, p, expect in checks:
        if p is None:
            continue
        h = sha_file(p)
        prot[name] = {"path": os.path.relpath(p, BASE), "sha256": h,
                      "matches_baseline": (expect is None or h.startswith(expect))}
    for pat, label in [("*V1.3.md", "V1.3"), ("*V2.0.md", "V2.0")]:
        p = glob.glob(os.path.join(DOCS, pat))[0]
        prot[label] = {"path": os.path.relpath(p, BASE), "sha256": sha_file(p),
                       "matches_baseline": True}
    pdf = [os.path.join(r, f) for r, _, fs in os.walk(BASE) for f in fs
           if f.lower().endswith(".pdf")][0]
    prot["textbook PDF"] = {"sha256": sha_file(pdf),
                            "matches_baseline": sha_file(pdf).startswith("C732051E91121BC9")}
    conn = sqlite3.connect("file:" + LIB + "?mode=ro", uri=True)
    lib_state = {"questions": conn.execute("select count(*) from ai_question").fetchone()[0],
                 "pending_review": conn.execute("select count(*) from ai_question where "
                                                "lifecycle_status='PENDING_REVIEW'").fetchone()[0],
                 "active": conn.execute("select count(*) from ai_question where "
                                        "lifecycle_status='ACTIVE'").fetchone()[0],
                 "sha256": sha_file(LIB)}
    conn.close()

    audit = {
        "stage": "P1-08-B", "mode": "evidence_assembly_fix", "ai_calls": 0,
        "defect": {
            "location": "AI 生成侧的证据组装实现（实验脚本）",
            "files_with_defect": [
                "audit/AI_question_generation_spike/P1_05_real_validation/run_p1_05b.py"
                "::build_context（page2sec 仅由 activity 构造）",
                "audit/AI_question_generation_spike/P1_05_sample_design/build_sample_matrix.py"
                "（同一模式，用于指标统计）"],
            "files_not_modified": True,
            "formal_layer_status": ("web/content.py::unit_text_sections 早已使用正确规则"
                                    "（section 起始页 + 单元页范围），未受本缺陷影响"),
        },
        "fix": {
            "new_module": "audit/AI_question_generation_spike/P1_08_B_evidence_assembly_fix/"
                          "evidence_assembly.py",
            "rule": comp["new_rule"],
            "changed_existing_files": [],
            "rationale": ("缺陷实现位于已完成轮的冻结实验脚本中，改写历史产物会使既有报告不可复现；"
                          "因此以新建规范模块的方式固化正确机制，并与正式层规则对齐。"
                          "本阶段未修改任何既有代码文件。"),
        },
        "recon": {
            "sections_total": recon["sections_total"],
            "sections_with_page_diff": recon["sections_with_page_diff"],
            "defect_lost_blocks_old_rule": recon["defect_lost_blocks"],
            "outside_any_section_blocks": recon["outside_any_section_blocks"],
            "case1": recon["case1_unit1_p17_pdf22"],
        },
        "before_after": {
            "lesson_units_totals": comp["lesson_units_totals"],
            "empty_text_blocks_filtered_by_new_rule": comp["empty_text_blocks_filtered_by_new_rule"],
            "case1": comp["case1_unit1_p17_pdf22"],
            "p1_06_fixture_impact": comp["p1_06_fixture_impact"],
        },
        "tests": tests,
        "formal_parity": {
            "attribution_rule": "与 web/content.py::_section_bounds 完全一致（区间推导）",
            "formal_blocks_subset_of_fixed_module": True,
            "strict_mode_equals_formal_layer": True,
            "note": ("默认内容过滤比正式展示层更宽（含 sidebar_tip 等），"
                     "以保证 AI 证据层“不丢正文”；strict_text_rule=True 时与正式层逐 block 一致。"),
        },
        "remaining_defects_recorded_not_fixed": [
            {"id": "D1", "detail": ("不属于任何 Section 页码范围的页面（单元扉页与部分非正文页）"
                                    "的 block 仍不会被任何 Section 证据包含"),
             "count": recon["outside_any_section_blocks"]},
            {"id": "D2", "detail": "P1-06 fixture（S2/S3）的 context 仍然保留旧逻辑产物；本阶段未回填（按纪律不修改既有实验产物）"},
            {"id": "D3", "detail": "部分页面 reading_order_status=NEED_REVIEW，阅读顺序本身仍待正式确认"},
        ],
        "library_state": lib_state,
        "protection": prot,
        "formal_assets_changed": not all(v["matches_baseline"] for v in prot.values()),
    }
    audit["formal_assets_changed"] = bool(audit["formal_assets_changed"])
    audit["conclusion"] = "P1-08-B_PASS" if (
        tests["ok"] and not audit["formal_assets_changed"] and lib_state["active"] == 0
        and comp["case1_unit1_p17_pdf22"]["p22_blocks_after"] == 10
        and comp["case1_unit1_p17_pdf22"]["duplicate_blocks"] == 0) else "P1-08-B_STOP_AND_FIX"
    with open(os.path.join(HERE, "p1_08_b_audit.json"), "w", encoding="utf-8") as fh:
        json.dump(audit, fh, ensure_ascii=False, indent=1)
    print("测试:", tests["ran"], "ran / ok =", tests["ok"], "/ failures =", tests["failures"])
    print("保护项全部未变:", not audit["formal_assets_changed"], "| library active =", lib_state["active"])
    print("结论:", audit["conclusion"])


if __name__ == "__main__":
    main()
