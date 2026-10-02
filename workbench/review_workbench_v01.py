#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P1-06-B1.6-A Vocabulary 人工审核工作台（只读原型）

用途：在本地浏览器中查看 25 条「缺词性」Vocabulary 候选的教材证据，并做人工判断。

严格边界：
  - 只读打开 contentpack v2（SQLite mode=ro）
  - 不写入任何数据库、不修改任何教材文件
  - 审核结论只保存在浏览器本地（localStorage），可导出 JSONL 供后续写回 v3 使用
  - 不调用 AI、不访问互联网
  - PDF 原页预览（GET /api/page-preview?page=<pdf_page>）：只读渲染为 PNG，
    在内存中完成，不产生临时文件、不重新解析文本、不做 OCR、不修改 PDF

用法：
  python D:\ZhixueEnglish\workbench\review_workbench_v01.py
  浏览器打开 http://127.0.0.1:8765/
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sqlite3
import sys
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pymupdf

BASE = Path(r"D:\ZhixueEnglish")
V2 = BASE / "structured" / "contentpack" / "v2" / "FLTRP-EN-7A-2022CUR.sqlite"
EVIDENCE = BASE / "audit" / "P1-06-B1.6_vocabulary_pos_review_candidates.json"
PDF = (BASE / "2025年度初一外研版英语教材"
       / "（根据2022年版课程标准修订）义务教育教科书·英语 七年级上册.pdf")

# 仅用于“原页预览”的只读渲染：内存缓存，不产生任何临时文件
_preview_lock = threading.Lock()
_preview_cache: dict = {}
_preview_doc = None


def render_page_png(page_no: int, scale: float = 2.0) -> bytes:
    """将教材 PDF 指定页渲染为 PNG 字节（只读，内存中完成，不写文件）。"""
    global _preview_doc
    with _preview_lock:
        if page_no in _preview_cache:
            return _preview_cache[page_no]
        if _preview_doc is None:
            _preview_doc = pymupdf.open(str(PDF))
        if not (1 <= page_no <= _preview_doc.page_count):
            raise ValueError("page out of range: %d" % page_no)
        page = _preview_doc.load_page(page_no - 1)
        pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale))
        data = pix.tobytes("png")
        if len(_preview_cache) < 40:          # 仅内存缓存，避免重复渲染
            _preview_cache[page_no] = data
        return data

EVIDENCE_TYPE_MEANING = {
    "A": "教材词汇表确实没有提供词性（多为多词条目，只有 headword + 中文释义 + 页码）",
    "B": "PDF/抽取结构导致词性可能丢失（教材版面有词性标记，但未被抽取）",
    "C": "跨块结构导致词性归属不明确",
    "D": "无法仅凭当前结构判断",
}


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def load_candidates() -> dict:
    """以 v2 数据库为主数据源，合并 B1.6 已审计的「词性证据类型」标注。"""
    conn = sqlite3.connect(f"file:{V2.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    items = [dict(r) for r in conn.execute(
        "SELECT * FROM learning_item WHERE item_type='vocabulary' "
        "AND review_status='NEED_REVIEW' AND (part_of_speech IS NULL OR part_of_speech='') "
        "ORDER BY canonical_text")]

    units = [dict(r) for r in conn.execute(
        "SELECT unit_id, unit_code, pdf_page_start, pdf_page_end FROM unit "
        "ORDER BY pdf_page_start")]
    sections = [dict(r) for r in conn.execute(
        "SELECT section_id, unit_id, title, pdf_page_start FROM section ORDER BY pdf_page_start")]

    def locate(pdf_page):
        u = next((u for u in units if u["pdf_page_start"] <= pdf_page <= u["pdf_page_end"]), None)
        if not u:
            return "UNKNOWN", "UNKNOWN"
        cand = [s for s in sections
                if s["unit_id"] == u["unit_id"] and s["pdf_page_start"] <= pdf_page]
        return u["unit_code"], (cand[-1]["title"] if cand else "UNKNOWN")

    evidence_types = {}
    if EVIDENCE.exists():
        try:
            ev = json.loads(EVIDENCE.read_text(encoding="utf-8"))
            for c in ev.get("candidates", []):
                evidence_types[c["item_id"]] = {
                    "type": c.get("pos_evidence_type"),
                    "marker": c.get("pos_marker_found_in_pdf"),
                }
        except Exception:
            pass

    out = []
    for n, it in enumerate(items, 1):
        refs = [dict(r) for r in conn.execute(
            "SELECT source_ref_id, source_id, quote_raw, textbook_id, snapshot_id "
            "FROM source_ref WHERE item_id=? ORDER BY source_ref_id", (it["item_id"],))]
        blocks, pages = [], []
        for r in refs:
            b = conn.execute(
                "SELECT block_id, page_id, text_raw, text_normalized, block_kind, layout_role, "
                "reading_order FROM content_block WHERE block_id=?", (r["source_id"],)).fetchone()
            if not b:
                continue
            b = dict(b)
            p = conn.execute("SELECT pdf_page, textbook_page, layout_type, "
                             "reading_order_status FROM page WHERE page_id=?",
                             (b["page_id"],)).fetchone()
            b["pdf_page"] = p["pdf_page"]
            b["textbook_page"] = p["textbook_page"]
            b["layout_type"] = p["layout_type"]
            pages.append(p["pdf_page"])
            blocks.append(b)

        context = []
        if blocks:
            head = blocks[0]
            same = [dict(x) for x in conn.execute(
                "SELECT block_id, text_raw, block_kind, reading_order FROM content_block "
                "WHERE page_id=? ORDER BY reading_order", (head["page_id"],))]
            idx = [i for i, x in enumerate(same) if x["block_id"] == head["block_id"]]
            if idx:
                i = idx[0]
                for j in (i - 1, i + 1):
                    if 0 <= j < len(same) and same[j]["block_id"] not in [b["block_id"] for b in blocks]:
                        context.append(same[j])

        pdf_page = blocks[0]["pdf_page"] if blocks else None
        unit_code, section_title = locate(pdf_page) if pdf_page else ("UNKNOWN", "UNKNOWN")
        ev = evidence_types.get(it["item_id"], {})
        out.append({
            "review_id": "VOC-%03d" % n,
            "item_id": it["item_id"],
            "learning_item": {
                "canonical_text": it["canonical_text"],
                "display_text": it["display_text"],
                "surface_form": it["surface_form"],
                "lemma": it["lemma"],
                "phonetic": it["phonetic"],
                "part_of_speech": it["part_of_speech"],
                "meaning_zh": it["meaning_zh"],
                "item_type": it["item_type"],
                "review_status": it["review_status"],
                "content_hash": it["content_hash"],
                "derivation_type": it["derivation_type"],
                "textbook_id": it["textbook_id"],
                "snapshot_id": it["snapshot_id"],
            },
            "textbook_location": {
                "pdf_page": pdf_page,
                "textbook_page": blocks[0]["textbook_page"] if blocks else None,
                "unit": unit_code,
                "section": section_title,
            },
            "source_refs": refs,
            "source_blocks": blocks,
            "context_blocks": context,
            "pos_evidence_type": ev.get("type"),
            "pos_marker_found_in_pdf": ev.get("marker"),
            "merge_count": len(refs),
        })

    conn.close()
    return {
        "meta": {
            "phase": "P1-06-B1.6-A",
            "database": str(V2),
            "database_sha256": sha256_file(V2),
            "candidate_count": len(out),
            "criteria": ("item_type=vocabulary AND review_status=NEED_REVIEW "
                         "AND part_of_speech IS NULL"),
            "evidence_type_meaning": EVIDENCE_TYPE_MEANING,
            "read_only": True,
        },
        "candidates": out,
    }


HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>教材资源人工审核工作台（Vocabulary 缺词性候选）</title>
<style>
  :root{--bg:#f6f7f9;--card:#fff;--line:#e3e6ea;--text:#1f2328;--muted:#6b7280;
        --ok:#1a7f37;--rej:#b42318;--warn:#9a6700;--blue:#0969da;}
  *{box-sizing:border-box}
  body{margin:0;font:14px/1.6 -apple-system,Segoe UI,Microsoft YaHei,sans-serif;color:var(--text);background:var(--bg)}
  header{background:#fff;border-bottom:1px solid var(--line);padding:10px 16px;position:sticky;top:0;z-index:5}
  header h1{margin:0 0 4px;font-size:16px}
  .banner{background:#fff8e5;border:1px solid #f0d999;color:#7a5b00;padding:6px 10px;border-radius:6px;margin:6px 0;font-size:13px}
  .meta{color:var(--muted);font-size:12px}
  main{display:grid;grid-template-columns:300px 1fr;gap:12px;padding:12px;align-items:start}
  .list{background:var(--card);border:1px solid var(--line);border-radius:8px;max-height:calc(100vh - 200px);overflow:auto}
  .item{padding:8px 10px;border-bottom:1px solid var(--line);cursor:pointer;display:flex;gap:8px;align-items:center}
  .item:hover{background:#f0f4f8}.item.active{background:#e7f0fb}
  .rid{font-family:ui-monospace,Consolas,monospace;font-size:12px;color:var(--muted);min-width:62px}
  .word{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .badge{font-size:11px;padding:1px 6px;border-radius:10px;border:1px solid var(--line);background:#fafbfc;color:var(--muted)}
  .badge.A{background:#eef7ee;color:#1a7f37;border-color:#cfe8cf}
  .badge.B{background:#fff4e5;color:#9a6700;border-color:#f0dcb5}
  .badge.dec{background:#e7f0fb;color:#0969da;border-color:#c9def7}
  .panel{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px}
  h2{font-size:18px;margin:0 0 8px}
  h3{font-size:13px;margin:16px 0 6px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
  table{border-collapse:collapse;width:100%;font-size:13px}
  td,th{border:1px solid var(--line);padding:4px 8px;text-align:left;vertical-align:top}
  th{background:#fafbfc;width:110px;color:var(--muted);font-weight:600}
  pre{background:#f6f8fa;border:1px solid var(--line);border-radius:6px;padding:8px;white-space:pre-wrap;word-break:break-word;margin:4px 0;font-size:13px}
  .block{border:1px solid var(--line);border-radius:6px;padding:8px;margin:6px 0;background:#fcfcfd}
  .block .tag{font-size:11px;color:var(--muted);font-family:ui-monospace,Consolas,monospace}
  .btns{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
  button{font:inherit;padding:7px 14px;border-radius:6px;border:1px solid var(--line);background:#fff;cursor:pointer}
  button.ok{border-color:#1a7f37;color:#1a7f37}button.rej{border-color:#b42318;color:#b42318}
  button.pri{background:#0969da;color:#fff;border-color:#0969da}
  textarea,input{font:inherit;width:100%;padding:6px;border:1px solid var(--line);border-radius:6px}
  .warn{color:var(--warn);font-size:12px}
  .footer{margin-top:12px;color:var(--muted);font-size:12px}
  .pdfwrap{margin-top:6px;padding:8px;border:1px solid var(--line);border-radius:6px;background:#eef1f4;
           max-height:560px;overflow:auto;text-align:center}
  #pdfimg{max-width:100%;height:auto;border:1px solid #c8ccd1;background:#fff;box-shadow:0 1px 4px rgba(0,0,0,.10)}
</style>
</head>
<body>
<header>
  <h1>教材资源人工审核工作台 · Vocabulary「缺词性」候选（只读原型）</h1>
  <div class="banner"><b>审核范围说明：</b>本工作台只判断「该词条是否确实作为教材派生学习资源成立」，
  <b>不判断</b>「现在是否适合孩子学习」。学习推荐由教材进度、当前年级、学习状态与《AI 反馈水平与阶段适配原则》另行决定。</div>
  <div class="meta" id="meta"></div>
</header>
<main>
  <div class="list" id="list"></div>
  <div class="panel" id="panel">正在加载…</div>
</main>
<script>
const DEC_KEY='p1-06-b1.6a-decisions-v1';
let DATA=null, DECISIONS=JSON.parse(localStorage.getItem(DEC_KEY)||'{}'), CUR=0;
function esc(s){return (s==null?'':String(s)).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
function save(){localStorage.setItem(DEC_KEY,JSON.stringify(DECISIONS));}
function decide(rid,d){DECISIONS[rid]=Object.assign(DECISIONS[rid]||{},{decision:d,reviewed_at:new Date().toISOString()});save();renderList();renderPanel();}
function renderList(){
  const el=document.getElementById('list'); el.innerHTML='';
  DATA.candidates.forEach((c,i)=>{
    const d=DECISIONS[c.review_id]||{};
    const div=document.createElement('div');
    div.className='item'+(i===CUR?' active':'');
    div.innerHTML=`<span class="rid">${c.review_id}</span><span class="word">${esc(c.learning_item.canonical_text)}</span>`
      +`<span class="badge ${c.pos_evidence_type||''}">${c.pos_evidence_type||'?'}</span>`
      +(d.decision?`<span class="badge dec">${d.decision==='REVIEWED_OK'?'通过':'拒绝'}</span>`:'');
    div.onclick=()=>{CUR=i;renderList();renderPanel();};
    el.appendChild(div);
  });
}
function renderPanel(){
  const c=DATA.candidates[CUR], li=c.learning_item, L=c.textbook_location, d=DECISIONS[c.review_id]||{};
  let html=`<h2>${c.review_id} · ${esc(li.canonical_text)}</h2>`;
  html+=`<table>
    <tr><th>display_text</th><td>${esc(li.display_text)}</td></tr>
    <tr><th>lemma / surface</th><td>${esc(li.lemma)} / ${esc(li.surface_form)}</td></tr>
    <tr><th>音标</th><td>${esc(li.phonetic)||'<span class="warn">NULL</span>'}</td></tr>
    <tr><th>词性</th><td>${esc(li.part_of_speech)||'<span class="warn">NULL（教材未提供 / 未被抽取）</span>'}</td></tr>
    <tr><th>中文释义</th><td>${esc(li.meaning_zh)}</td></tr>
    <tr><th>资源类型 / 状态</th><td>${esc(li.item_type)} / ${esc(li.review_status)}</td></tr>
    <tr><th>教材位置</th><td>Unit ${esc(L.unit)} · ${esc(L.section)} · PDF p.${esc(L.pdf_page)} · 教材 p.${esc(L.textbook_page)}</td></tr>
    <tr><th>来源引用</th><td>${c.source_refs.length} 条 source_ref（${c.merge_count>=3?'跨块合并':c.merge_count} 个来源块）</td></tr>
    <tr><th>content_hash</th><td><code>${esc(li.content_hash)}</code></td></tr>
  </table>`;
  html+=`<h3>词性证据类型</h3><p><span class="badge ${c.pos_evidence_type||''}">${c.pos_evidence_type||'?'}</span> ${esc(DATA.meta.evidence_type_meaning[c.pos_evidence_type]||'')}`
    +(c.pos_marker_found_in_pdf?` <b>PDF 中发现标记：${esc(c.pos_marker_found_in_pdf)}</b>`:'')+`</p>`;
  html+=`<h3>原始 ContentBlock（text_raw 原文，未修改）</h3>`;
  c.source_blocks.forEach(b=>{html+=`<div class="block"><div class="tag">${esc(b.block_id)} · ${esc(b.layout_role)} / ${esc(b.block_kind)} · PDF p.${esc(b.pdf_page)}</div>
    <pre>${esc(b.text_raw)}</pre><div class="tag">text_normalized</div><pre>${esc(b.text_normalized)}</pre></div>`;});
  if(c.context_blocks.length){html+=`<h3>同页前后文</h3>`;
    c.context_blocks.forEach(b=>{html+=`<div class="block"><div class="tag">${esc(b.block_id)} · ${esc(b.block_kind)}</div><pre>${esc(b.text_raw)}</pre></div>`;});}
  html+=`<h3>教材原页预览</h3>`;
  if(L.pdf_page){
    html+=`<p class="footer">教材页码：${esc(L.textbook_page==null?'—':L.textbook_page)} ｜ PDF 页：${esc(L.pdf_page)}（仅供人工核对，不参与自动判断）</p>
      <div class="pdfwrap">
        <img id="pdfimg" alt="教材原页" src="/api/page-preview?page=${encodeURIComponent(L.pdf_page)}" onerror="pdfFail()">
        <div id="pdferr" class="warn" style="display:none">教材原页暂时无法加载（不影响结构化证据与审核操作）</div>
      </div>`;
  }else{
    html+=`<p class="warn">暂无对应教材原页</p>`;
  }
  html+=`<h3>人工审核（不写数据库）</h3>
    <div class="btns">
      <button class="ok" onclick="decide('${c.review_id}','REVIEWED_OK')">确认为教材资源（REVIEWED_OK）</button>
      <button class="rej" onclick="decide('${c.review_id}','REJECTED')">拒绝（REJECTED）</button>
      <button onclick="decide('${c.review_id}','NEED_REVIEW')">保持待审（NEED_REVIEW）</button>
      <button onclick="decide('${c.review_id}','')">清除</button>
    </div>
    <p class="footer">审核人：<input id="by" value="${esc(d.reviewed_by||'')}" oninput="DECISIONS['${c.review_id}']=Object.assign(DECISIONS['${c.review_id}']||{},{reviewed_by:this.value});save();" placeholder="填写审核人标识"></p>
    <p class="footer">审核备注：<textarea id="note" rows="2" oninput="DECISIONS['${c.review_id}']=Object.assign(DECISIONS['${c.review_id}']||{},{review_note:this.value});save();" placeholder="记录判断依据（例如：教材原文只有 headword+释义，确无词性）">${esc(d.review_note||'')}</textarea></p>
    <p class="footer">当前记录：${d.decision?esc(d.decision):'未决定'} ${d.reviewed_at?('· '+esc(d.reviewed_at)):''}</p>
    <div class="btns"><button class="pri" onclick="exportJSONL()">导出审核结果（JSONL 下载）</button></div>`;
  document.getElementById('panel').innerHTML=html;
}
function pdfFail(){
  const e=document.getElementById('pdferr'); if(e) e.style.display='block';
  const i=document.getElementById('pdfimg'); if(i) i.style.display='none';
}
function exportJSONL(){
  const lines=DATA.candidates.map(c=>{
    const li=c.learning_item,L=c.textbook_location,d=DECISIONS[c.review_id]||{};
    return JSON.stringify({review_id:c.review_id,item_id:c.item_id,item_type:'vocabulary',
      canonical_text:li.canonical_text,current_status:'NEED_REVIEW',decision:d.decision||'',
      pos_evidence_type:c.pos_evidence_type,source_blocks:c.source_blocks.map(b=>b.block_id),
      textbook_page:L.textbook_page,pdf_page:L.pdf_page,quote_raw:c.source_blocks.map(b=>b.text_raw).join(' '),
      review_note:d.review_note||'',reviewed_by:d.reviewed_by||'',reviewed_at:d.reviewed_at||'',
      review_version:'review_v1'});
  });
  const blob=new Blob([lines.join('\\n')+'\\n'],{type:'application/x-ndjson'});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);
  a.download='P1-06-B1.6-A_review_decisions.jsonl';a.click();
}
fetch('/api/candidates').then(r=>r.json()).then(d=>{
  DATA=d;
  document.getElementById('meta').textContent='候选 '+d.meta.candidate_count+' 条 · 数据源 '+d.meta.database
    +' · SHA256 '+d.meta.database_sha256.slice(0,16)+'… · 只读';
  renderList();renderPanel();
});
</script>
</body></html>
"""


class Handler(BaseHTTPRequestHandler):
    payload = None

    def _send(self, code, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/api/candidates"):
            body = json.dumps(self.payload, ensure_ascii=False).encode("utf-8")
            self._send(200, body, "application/json; charset=utf-8")
        elif self.path.startswith("/api/health"):
            self._send(200, b'{"ok":true,"read_only":true}', "application/json")
        elif self.path.startswith("/api/page-preview"):
            # 只读：读取教材 PDF → 渲染当前页 → 返回 PNG（内存完成，不落盘、不写数据库）
            params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            raw = (params.get("page") or params.get("pdf_page") or ["0"])[0]
            try:
                page_no = int(raw)
            except ValueError:
                page_no = 0
            if page_no <= 0:
                self._send(400, b'{"error":"invalid page"}',
                           "application/json; charset=utf-8")
                return
            try:
                png = render_page_png(page_no)
            except Exception as exc:
                payload = json.dumps({"error": str(exc)}, ensure_ascii=False).encode("utf-8")
                self._send(404, payload, "application/json; charset=utf-8")
                return
            self._send(200, png, "image/png")
        elif self.path in ("/", "/index.html"):
            self._send(200, HTML.encode("utf-8"), "text/html; charset=utf-8")
        else:
            self._send(404, b"not found", "text/plain; charset=utf-8")

    def do_POST(self):
        self._send(405, b"read-only workbench: POST not allowed", "text/plain")

    def log_message(self, fmt, *args):
        pass


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Vocabulary 人工审核工作台（只读）")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    if not V2.exists():
        print("STOP: contentpack v2 不存在:", V2)
        return 2
    Handler.payload = load_candidates()
    n = len(Handler.payload["candidates"])
    print("数据源:", V2)
    print("候选数量:", n)
    print("只读模式：不写数据库；审核结论保存在浏览器本地，可导出 JSONL")
    url = f"http://127.0.0.1:{args.port}/"
    print("打开:", url)
    if not args.no_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    with ThreadingHTTPServer(("127.0.0.1", args.port), Handler) as srv:
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("已停止")
    return 0


if __name__ == "__main__":
    sys.exit(main())
