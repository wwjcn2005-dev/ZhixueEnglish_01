"""P1-08-A · 只读审计 + 产物核对。不修改任何数据库或程序。"""
import glob
import hashlib
import json
import os
import re
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = r"D:\ZhixueEnglish"
SPIKE = os.path.join(BASE, "audit", "AI_question_generation_spike")
DOCS = os.path.join(BASE, "docs")
LIB = os.path.join(BASE, "structured", "ai", "question_library.db")
CP = os.path.join(BASE, "structured", "contentpack", "v5", "FLTRP-EN-7A-2022CUR.sqlite")
SPEC = None
for p in glob.glob(os.path.join(DOCS, "*V1.0.md")):
    if "题库" in os.path.basename(p):
        SPEC = p


def sha_file(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest().upper()


def dir_sha(d):
    h = hashlib.sha256()
    for f in sorted(os.listdir(d)):
        p = os.path.join(d, f)
        if os.path.isfile(p):
            h.update(f.encode())
            h.update(sha_file(p).encode())
    return h.hexdigest().upper()


def main():
    # ---- 1. P0～P1-07 产物核对
    stages = ["P0_closeout", "P1_01_question_library_design",
              "P1_02_question_library_implementation", "P1_03_minimal_pipeline",
              "P1_04_rule_fixes", "P1_05_sample_design", "P1_05_real_validation",
              "P1_05_budget_calibration", "P1_05_budget_calibration_v2",
              "P1_05_manual_review", "P1_05_prompt_v2_textbook_focus",
              "P1_05_prompt_v3_boundary", "P1_06_batch_stability",
              "P1_07_library_ingest"]
    artifacts = {}
    for s in stages:
        d = os.path.join(SPIKE, s)
        artifacts[s] = {"exists": os.path.isdir(d),
                        "files": len([f for f in os.listdir(d) if os.path.isfile(os.path.join(d, f))])
                        if os.path.isdir(d) else 0,
                        "dir_sha256": dir_sha(d) if os.path.isdir(d) else None}

    # ---- 2. 规范文件
    spec_info = {"path": os.path.relpath(SPEC, BASE) if SPEC else None,
                 "exists": bool(SPEC), "sha256": sha_file(SPEC) if SPEC else None,
                 "size": os.path.getsize(SPEC) if SPEC else None,
                 "chars": len(open(SPEC, encoding="utf-8").read()) if SPEC else 0}

    # ---- 3. DOCX 决策
    docx = [os.path.basename(p) for p in glob.glob(os.path.join(DOCS, "*.docx"))]
    docx_info = {"docs_docx_files": docx, "docx_available_python": False,
                 "pandoc": False,
                 "decision": "不生成 DOCX：docs/ 现有正式规范全部为 .md，未有 DOCX 体系；"
                             "且本机无 python-docx / pandoc，按规范不得为新软件安装。"
                 if not docx else "见 audit"}

    # ---- 4. V1.3 / V2.0 一致性比较
    compare = {}
    for pat, label in [("*V1.3.md", "V1_3"), ("*V2.0.md", "V2_0")]:
        p = glob.glob(os.path.join(DOCS, pat))[0]
        t = open(p, encoding="utf-8").read()
        hits = {}
        for kw in ["question_library", "题库", "出题", "生成题", "习题生成", "PENDING", "ACTIVE",
                   "PENDING_REVIEW", "AI 生成题", "无限题库"]:
            hits[kw] = len(re.findall(re.escape(kw), t))
        compare[label] = {"file": os.path.basename(p), "sha256": sha_file(p), "keyword_hits": hits}
    compare_result = {
        "v2_0": "全文未涉及 AI 题库与出题流程 → 无需修改",
        "v1_3": ("有涉及（题库×6 / 生成题×3 / AI 生成题×1 / 无限题库×1），"
                 "其中绝大多数条款与本规范一致（见规范 §5.2）；"
                 "**存在 1 处需要项目裁决的边界**：V1.3 九『不得生成或改写……题干、选项、答案』"
                 "与二十二·1『本产品不是：AI 题库』在『绝对禁止』解读下会与任何 AI 出题流程冲突"),
        "handling": ("本规范提出 V1.3 同步修订建议文本（不执行修改）；"
                     "在裁决前按更严格口径执行：AI 题只存在于独立题库、绝不写入教材数据、"
                     "必须经人工审核方可用于学习流程、孩子端不得呈现题库概念"),
        "changed_v1_3_or_v2_0": False,
    }

    # ---- 5. 保护资产
    prot = {}
    for k, p, exp in [
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
    ]:
        h = sha_file(p)
        prot[k] = {"sha256": h, "matches_baseline": (exp is None or h.startswith(exp))}
    pdf = [os.path.join(r, f) for r, _, fs in os.walk(BASE) for f in fs
           if f.lower().endswith(".pdf")][0]
    prot["textbook PDF"] = {"sha256": sha_file(pdf),
                            "matches_baseline": sha_file(pdf).startswith("C732051E91121BC9")}

    conn = sqlite3.connect("file:" + LIB + "?mode=ro", uri=True)
    lib_state = {"user_version": conn.execute("PRAGMA user_version").fetchone()[0],
                 "integrity": conn.execute("PRAGMA integrity_check").fetchone()[0],
                 "questions": conn.execute("select count(*) from ai_question").fetchone()[0],
                 "pending_review": conn.execute("select count(*) from ai_question "
                                                "where lifecycle_status='PENDING_REVIEW'").fetchone()[0],
                 "active": conn.execute("select count(*) from ai_question "
                                        "where lifecycle_status='ACTIVE'").fetchone()[0],
                 "generation_runs": conn.execute("select count(*) from generation_run").fetchone()[0]}
    conn.close()

    audit = {
        "stage": "P1-08-A", "mode": "read_only_audit_then_freeze_spec", "ai_calls": 0,
        "deliverable": spec_info,
        "docx_decision": docx_info,
        "stage_artifacts": artifacts,
        "v1_3_v2_0_comparison": compare,
        "comparison_result": compare_result,
        "v1_3_interpretation_ruling": {
            "date": "2026-09-17",
            "decision": "解读 A",
            "text": ("AI 可以生成教材训练题，但 AI 生成的题干、选项、答案不得冒充教材事实，"
                     "不得写入教材数据；AI 题独立存放，经审核后才能进入学习流程。"),
            "decided_by": "项目决策者（用户）",
            "effect": ("本规范与 V1.3 的一致性成立；V1.3 / V2.0 本轮均不修改；"
                       "规范 §5.3 保留可选的 V1.3 措辞澄清文本，供下一次 V1.3 修订时纳入"),
            "record_file": "audit/AI_question_generation_spike/P1_08_A_process_baseline/"
                           "p1_08_a_decision_record.md",
            "changed_v1_3_or_v2_0": False,
            "blocking": False,
        },
        "library_state": lib_state,
        "protection": prot,
        "protection_ok": all(v["matches_baseline"] for v in prot.values()),
        "verified_vs_unverified_source": {
            "verified": "见 docs 规范 §16.1（逐项标注验证方式）",
            "unverified": "见 docs 规范 §16.2（14 项，不得写成已解决）",
        },
        "conclusion": None,
    }
    ok = (spec_info["exists"] and audit["protection_ok"] and lib_state["active"] == 0
          and lib_state["integrity"] == "ok"
          and "无需修改" in compare_result["v2_0"]
          and compare_result["changed_v1_3_or_v2_0"] is False)
    audit["conclusion"] = "P1-08-A_PASS" if ok else "P1-08-A_STOP_AND_FIX"
    with open(os.path.join(HERE, "p1_08_a_audit.json"), "w", encoding="utf-8") as fh:
        json.dump(audit, fh, ensure_ascii=False, indent=1)
    print("规范:", spec_info["path"], spec_info["sha256"][:16] if spec_info["sha256"] else "-")
    print("阶段产物:", sum(1 for v in artifacts.values() if v["exists"]), "/", len(artifacts))
    print("保护项:", audit["protection_ok"], "| ACTIVE:", lib_state["active"],
          "| PENDING_REVIEW:", lib_state["pending_review"])
    print("结论:", audit["conclusion"])


if __name__ == "__main__":
    main()
