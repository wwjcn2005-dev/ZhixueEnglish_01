/* P3-07 sentence screening + sentence interval annotation. No token logic. */
"use strict";

let candidates = [];
let drafts = {};
let screenIndex = 0;
let positionIndex = 0;
let positionList = [];
let audio = null;
let audioCtx = null;
let audioBuffer = null;
let peaks = [];
let viewStart = 0;
let viewEnd = 1;
let selectionStart = null;
let selectionEnd = null;
let dragHandle = null;
let playUntil = null;
let silenceRuns = [];
let suggestedStart = null;
let suggestedEnd = null;

const wave = document.getElementById("wave");
const wctx = wave.getContext("2d");

function fmt(ms) {
  ms = Math.max(0, Number(ms) || 0);
  const m = Math.floor(ms / 60000);
  const s = Math.floor((ms % 60000) / 1000);
  const x = Math.floor(ms % 1000);
  return String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0") + "." + String(x).padStart(3, "0");
}
function setMsg(id, text, cls) {
  const el = document.getElementById(id);
  el.textContent = text || "";
  el.className = "save-message" + (cls ? " " + cls : "");
}
function statusOf(c) {
  return (drafts[c.sentence_id] && drafts[c.sentence_id].status) || c.status || "CANDIDATE";
}
function sentenceOf(c) {
  const d = drafts[c.sentence_id] || {};
  return d.sentence_text || c.sentence_text || "";
}
function isCompleteSentence(text) {
  return !!text && text.indexOf("___") < 0;
}
function currentScreen() { return candidates[screenIndex]; }
function currentPosition() { return positionList[positionIndex]; }

function renderCandidateList() {
  const filter = document.getElementById("screenFilter").value;
  const box = document.getElementById("candidateList");
  box.innerHTML = "";
  candidates.forEach((c, i) => {
    const st = statusOf(c);
    if (filter !== "ALL" && filter !== st) return;
    const div = document.createElement("div");
    div.className = "candidate" + (i === screenIndex ? " active" : "");
    div.innerHTML = '<div class="id">' + c.sentence_id + ' <span class="st ' + st + '">' + st + '</span></div>' +
      '<div class="txt"></div>';
    div.querySelector(".txt").textContent = (sentenceOf(c) || c.prompt_text || "").slice(0, 90);
    div.onclick = () => showScreen(i);
    box.appendChild(div);
  });
  const counts = {CANDIDATE: 0, VERIFIED: 0, REJECTED: 0};
  candidates.forEach((c) => counts[statusOf(c)]++);
  document.getElementById("screenStats").textContent =
    "C:" + counts.CANDIDATE + "  V:" + counts.VERIFIED + "  R:" + counts.REJECTED;
}

function showScreen(i) {
  screenIndex = Math.max(0, Math.min(candidates.length - 1, i));
  const c = currentScreen();
  const d = drafts[c.sentence_id] || {};
  document.getElementById("screenMeta").textContent =
    c.sentence_id + " ｜ " + c.audio_id + " ｜ " + c.unit + " / " + c.chapter + " ｜ " +
    c.activity + " ｜ " + c.text_status;
  document.getElementById("screenSentence").value = d.sentence_text || c.sentence_text || c.prompt_text || "";
  document.getElementById("screenContext").value = d.context_text || c.context_text || c.source_text || "";
  document.getElementById("selectionReason").value = d.selection_reason || "";
  document.getElementById("rejectReason").value = d.reject_reason || "";
  document.getElementById("patternKey").value = d.pattern_key || "";
  document.getElementById("functionTag").value = d.function_tag || "";
  document.getElementById("duplicateOf").value = d.duplicate_of || "";
  renderCandidateList();
}

function screenPayload(status) {
  const c = currentScreen();
  const old = drafts[c.sentence_id] || {};
  const existing = c.existing_sentence_timing || {};
  const text = document.getElementById("screenSentence").value.trim();
  const reason = document.getElementById("selectionReason").value;
  const reject = document.getElementById("rejectReason").value;
  if (status === "CANDIDATE" && !isCompleteSentence(text)) {
    throw new Error("保留前必须形成完整句子，不能保留 ___ fragment。");
  }
  if (status === "CANDIDATE" && !reason) {
    throw new Error("保留时必须选择 selection_reason。");
  }
  if (status === "REJECTED" && !reject) {
    throw new Error("舍弃时必须选择 reject_reason。");
  }
  return {
    candidate_id: c.candidate_id,
    audio_id: c.audio_id,
    audio_num: c.audio_num,
    unit: c.unit,
    chapter: c.chapter,
    activity: c.activity,
    page: c.textbook_page,
    sentence_index: screenIndex + 1,
    sentence_text: text || c.prompt_text || c.sentence_id,
    source_text: c.source_text,
    context_text: document.getElementById("screenContext").value,
    status: status,
    selection_reason: status === "CANDIDATE" ? reason : null,
    reject_reason: status === "REJECTED" ? reject : null,
    pattern_key: document.getElementById("patternKey").value.trim() || null,
    function_tag: document.getElementById("functionTag").value.trim() || null,
    duplicate_of: document.getElementById("duplicateOf").value.trim() || null,
    start_ms: old.start_ms !== undefined ? old.start_ms : (existing.start_ms === undefined ? null : existing.start_ms),
    end_ms: old.end_ms !== undefined ? old.end_ms : (existing.end_ms === undefined ? null : existing.end_ms),
    reviewer: "local-human",
  };
}

async function saveScreen(status) {
  try {
    const payload = screenPayload(status);
    setMsg("screenMessage", "正在保存…");
    const r = await fetch("/api/save", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
    });
    const out = await r.json();
    if (!out.ok) throw new Error(out.error || "save failed");
    drafts[payload.candidate_id] = payload;
    setMsg("screenMessage", "已保存：" + out.status + " ｜ " + out.saved_at, "ok");
    renderCandidateList();
  } catch (err) {
    setMsg("screenMessage", "保存失败：" + err.message, "err");
  }
}

function rebuildPositionList() {
  positionList = candidates.filter((c) => {
    const st = statusOf(c);
    return st !== "REJECTED" && isCompleteSentence(sentenceOf(c));
  });
  const sel = document.getElementById("positionSelect");
  sel.innerHTML = "";
  positionList.forEach((c, i) => {
    const o = document.createElement("option");
    o.value = String(i);
    o.textContent = c.sentence_id + " ｜ " + sentenceOf(c).slice(0, 60);
    sel.appendChild(o);
  });
  document.getElementById("positionStats").textContent = positionList.length + " 条入选句";
  if (positionIndex >= positionList.length) positionIndex = 0;
  sel.value = String(positionIndex);
}

function showPosition(i) {
  rebuildPositionList();
  if (!positionList.length) return;
  positionIndex = Math.max(0, Math.min(positionList.length - 1, i));
  const c = currentPosition();
  const d = drafts[c.sentence_id] || {};
  const existing = c.existing_sentence_timing || {};
  document.getElementById("positionSelect").value = String(positionIndex);
  document.getElementById("positionMeta").textContent =
    c.sentence_id + " ｜ " + c.audio_id + " ｜ " + c.unit + " / " + c.activity + " ｜ " +
    (d.selection_reason || c.selection_reason || "");
  document.getElementById("positionSentence").textContent = sentenceOf(c);
  document.getElementById("posRejectReason").value = "low_value";
  const startVal = d.start_ms !== undefined ? d.start_ms : existing.start_ms;
  const endVal = d.end_ms !== undefined ? d.end_ms : existing.end_ms;
  selectionStart = startVal === null || startVal === undefined ? null : Number(startVal) / 1000;
  selectionEnd = endVal === null || endVal === undefined ? null : Number(endVal) / 1000;
  document.getElementById("startMs").value = startVal === null || startVal === undefined ? "" : startVal;
  document.getElementById("endMs").value = endVal === null || endVal === undefined ? "" : endVal;
  suggestedStart = suggestedEnd = null;
  silenceRuns = [];
  applyProvidedSuggestions();
  if (!c.audio_id || !c.audio_num || !c.original_audio_path) {
    setMsg("positionMessage", "当前候选没有可用的原始音频映射。", "err");
    return;
  }
  audioBuffer = null;
  peaks = [];
  if (audio) {
    audio.pause();
    audio.src = "/audio/" + c.audio_num + ".mp3";
    audio.load();
  } else {
    audio = new Audio("/audio/" + c.audio_num + ".mp3");
    audio.preload = "metadata";
    audio.addEventListener("timeupdate", onAudioTime);
    audio.addEventListener("ended", () => { playUntil = null; });
  }
  viewStart = 0;
  viewEnd = 1;
  loadWaveform();
}

async function loadWaveform() {
  try {
    audioCtx = audioCtx || new AudioContext();
    const resp = await fetch("/audio/" + currentPosition().audio_num + ".mp3");
    const ab = await resp.arrayBuffer();
    audioBuffer = await audioCtx.decodeAudioData(ab.slice(0));
    peaks = computePeaks(audioBuffer, 3200);
    viewStart = 0;
    viewEnd = audioBuffer.duration;
    computeSuggestions();
    applyProvidedSuggestions();
    draw();
  } catch (err) {
    peaks = [];
    draw();
    setMsg("positionMessage", "波形解码失败：" + err.message, "err");
  }
}

function computePeaks(buffer, bins) {
  const data = buffer.getChannelData(0);
  const step = Math.max(1, Math.floor(data.length / bins));
  const out = [];
  for (let i = 0; i < data.length; i += step) {
    let lo = 1, hi = -1;
    const end = Math.min(data.length, i + step);
    for (let j = i; j < end; j++) {
      const v = data[j];
      if (v < lo) lo = v;
      if (v > hi) hi = v;
    }
    out.push([lo, hi]);
  }
  return out;
}

function percentile(values, q) {
  if (!values.length) return 0;
  const a = values.slice().sort((x, y) => x - y);
  return a[Math.min(a.length - 1, Math.max(0, Math.floor((a.length - 1) * q)))];
}

function findLowEnergyRuns(buffer) {
  const data = buffer.getChannelData(0);
  const sr = buffer.sampleRate;
  const frameMs = 10;
  const frameSize = Math.max(1, Math.round(sr * frameMs / 1000));
  const rms = [];
  for (let i = 0; i < data.length; i += frameSize) {
    let sum = 0, n = 0;
    const end = Math.min(data.length, i + frameSize);
    for (let j = i; j < end; j++) { sum += data[j] * data[j]; n++; }
    rms.push(Math.sqrt(sum / Math.max(1, n)));
  }
  const base = percentile(rms, 0.20);
  const threshold = Math.max(0.006, base * 1.8);
  const runs = [];
  let start = null;
  for (let i = 0; i < rms.length; i++) {
    const low = rms[i] <= threshold;
    if (low && start === null) start = i;
    if ((!low || i === rms.length - 1) && start !== null) {
      const end = low && i === rms.length - 1 ? i + 1 : i;
      const startMs = start * frameMs;
      const endMs = end * frameMs;
      if (endMs - startMs >= 70) runs.push({start_ms: startMs, end_ms: endMs, duration_ms: endMs - startMs});
      start = null;
    }
  }
  return runs;
}

function nearestRun(runs, targetMs, side) {
  let best = null;
  runs.forEach((r) => {
    if (side === "before" && r.end_ms <= targetMs + 180) {
      if (!best || r.end_ms > best.end_ms) best = r;
    }
    if (side === "after" && r.start_ms >= targetMs - 180) {
      if (!best || r.start_ms < best.start_ms) best = r;
    }
  });
  return best;
}

function computeSuggestions() {
  const c = currentPosition && currentPosition();
  if (!audioBuffer || !c) return;
  const d = drafts[c.sentence_id] || {};
  const existing = c.existing_sentence_timing || {};
  const anchorStart = d.start_ms !== undefined && d.start_ms !== null ? Number(d.start_ms) :
    (existing.start_ms !== undefined && existing.start_ms !== null ? Number(existing.start_ms) : null);
  const anchorEnd = d.end_ms !== undefined && d.end_ms !== null ? Number(d.end_ms) :
    (existing.end_ms !== undefined && existing.end_ms !== null ? Number(existing.end_ms) : null);
  silenceRuns = findLowEnergyRuns(audioBuffer);
  if (anchorStart === null || anchorEnd === null) {
    suggestedStart = suggestedEnd = null;
    document.getElementById("analysisStatus").textContent =
      "无已有定位锚点；需要人工先找到大致位置（低能量区已显示）";
  } else {
    const before = nearestRun(silenceRuns, anchorStart, "before");
    const after = nearestRun(silenceRuns, anchorEnd, "after");
    const useBefore = before && (anchorStart - before.end_ms) <= 1000;
    const useAfter = after && (after.start_ms - anchorEnd) <= 1800;
    suggestedStart = useBefore ? Math.max(before.start_ms, before.end_ms - 80) : Math.max(0, anchorStart - 120);
    suggestedEnd = useAfter ? Math.min(after.end_ms, after.start_ms + 100) : Math.min(audioBuffer.duration * 1000, anchorEnd + 140);
    document.getElementById("analysisStatus").textContent =
      "已分析 " + silenceRuns.length + " 个低能量区；建议值需人工试听确认";
  }
  document.getElementById("suggestedStart").value = suggestedStart === null ? "" : Math.round(suggestedStart);
  document.getElementById("suggestedEnd").value = suggestedEnd === null ? "" : Math.round(suggestedEnd);
  draw();
}

function applyProvidedSuggestions() {
  const c = currentPosition && currentPosition();
  if (!c || c.suggested_start_ms === undefined || c.suggested_end_ms === undefined ||
      c.suggested_start_ms === null || c.suggested_end_ms === null) return;
  suggestedStart = Number(c.suggested_start_ms);
  suggestedEnd = Number(c.suggested_end_ms);
  document.getElementById("suggestedStart").value = Math.round(suggestedStart);
  document.getElementById("suggestedEnd").value = Math.round(suggestedEnd);
  // Seed the editable player state only when no saved/anchored interval exists.
  if (selectionStart === null || selectionEnd === null) {
    selectionStart = suggestedStart / 1000;
    selectionEnd = suggestedEnd / 1000;
    document.getElementById("startMs").value = Math.round(suggestedStart);
    document.getElementById("endMs").value = Math.round(suggestedEnd);
  }
  document.getElementById("analysisStatus").textContent =
    "已加载建议区间（" + (c.suggested_status || "") + "）；仍需人工试听确认";
  draw();
}

function timeToX(sec) {
  return ((sec - viewStart) / Math.max(0.0001, viewEnd - viewStart)) * wave.clientWidth;
}
function xToTime(x) {
  return viewStart + (x / Math.max(1, wave.clientWidth)) * (viewEnd - viewStart);
}

function draw() {
  const dpr = window.devicePixelRatio || 1;
  const w = wave.clientWidth, h = 300;
  if (wave.width !== Math.floor(w * dpr) || wave.height !== Math.floor(h * dpr)) {
    wave.width = Math.floor(w * dpr);
    wave.height = Math.floor(h * dpr);
  }
  wctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  wctx.fillStyle = "#0f172a";
  wctx.fillRect(0, 0, w, h);
  if (peaks.length && audioBuffer) {
    wctx.strokeStyle = "#7dd3fc";
    wctx.beginPath();
    for (let x = 0; x < w; x++) {
      const t = xToTime(x);
      const i = Math.max(0, Math.min(peaks.length - 1, Math.floor((t / audioBuffer.duration) * peaks.length)));
      const lo = peaks[i][0], hi = peaks[i][1];
      const y1 = h / 2 - hi * h * 0.42;
      const y2 = h / 2 - lo * h * 0.42;
      wctx.moveTo(x + 0.5, y1);
      wctx.lineTo(x + 0.5, y2);
    }
    wctx.stroke();
  }
  silenceRuns.forEach((r) => {
    const x1 = timeToX(r.start_ms / 1000);
    const x2 = timeToX(r.end_ms / 1000);
    wctx.fillStyle = "rgba(34,197,94,.10)";
    wctx.fillRect(x1, 0, Math.max(1, x2 - x1), h);
  });
  const span = viewEnd - viewStart;
  const step = span > 20 ? 5 : span > 10 ? 2 : span > 4 ? 1 : span > 1.5 ? 0.5 : span > 0.6 ? 0.2 : 0.1;
  wctx.font = "12px Segoe UI";
  for (let t = Math.ceil(viewStart / step) * step; t <= viewEnd + 0.0001; t += step) {
    const x = timeToX(t);
    wctx.strokeStyle = "#334155";
    wctx.beginPath(); wctx.moveTo(x, 0); wctx.lineTo(x, h); wctx.stroke();
    wctx.fillStyle = "#cbd5e1";
    wctx.fillText(t.toFixed(1) + "s", x + 3, h - 7);
  }
  if (selectionStart !== null && selectionEnd !== null) {
    const x1 = timeToX(Math.min(selectionStart, selectionEnd));
    const x2 = timeToX(Math.max(selectionStart, selectionEnd));
    wctx.fillStyle = "rgba(250,204,21,.28)";
    wctx.fillRect(x1, 0, Math.max(1, x2 - x1), h);
  }
  if (selectionStart !== null) {
    const x = timeToX(selectionStart);
    wctx.fillStyle = "#22c55e";
    wctx.fillRect(x - 1, 0, 3, h);
    wctx.beginPath(); wctx.arc(x, 12, 7, 0, 6.3); wctx.fill();
  }
  if (selectionEnd !== null) {
    const x = timeToX(selectionEnd);
    wctx.fillStyle = "#f97316";
    wctx.fillRect(x - 1, 0, 3, h);
    wctx.beginPath(); wctx.arc(x, 12, 7, 0, 6.3); wctx.fill();
  }
  if (suggestedStart !== null) {
    const x = timeToX(suggestedStart / 1000);
    wctx.strokeStyle = "#a3e635";
    wctx.setLineDash([5, 4]);
    wctx.beginPath(); wctx.moveTo(x, 0); wctx.lineTo(x, h); wctx.stroke();
    wctx.setLineDash([]);
  }
  if (suggestedEnd !== null) {
    const x = timeToX(suggestedEnd / 1000);
    wctx.strokeStyle = "#facc15";
    wctx.setLineDash([5, 4]);
    wctx.beginPath(); wctx.moveTo(x, 0); wctx.lineTo(x, h); wctx.stroke();
    wctx.setLineDash([]);
  }
  if (audio) {
    const x = timeToX(audio.currentTime);
    wctx.strokeStyle = "#ef4444";
    wctx.lineWidth = 2;
    wctx.beginPath(); wctx.moveTo(x, 0); wctx.lineTo(x, h); wctx.stroke();
    wctx.lineWidth = 1;
  }
  const dur = audioBuffer ? audioBuffer.duration : (audio ? audio.duration || 1 : 1);
  document.getElementById("viewLabel").textContent =
    fmt(viewStart * 1000) + " – " + fmt(viewEnd * 1000) + " ｜ 总长 " + fmt(dur * 1000);
}

function onAudioTime() {
  if (playUntil !== null && audio.currentTime >= playUntil) {
    audio.pause(); audio.currentTime = playUntil; playUntil = null;
  }
  document.getElementById("timeHint").textContent =
    fmt(audio.currentTime * 1000) + (playUntil !== null ? "  /  播放至 " + fmt(playUntil * 1000) : "");
  draw();
}
function playFrom(sec, until) {
  if (!audio) return;
  audioCtx = audioCtx || new AudioContext();
  if (audioCtx.state === "suspended") audioCtx.resume();
  audio.currentTime = Math.max(0, sec);
  playUntil = Number.isFinite(until) ? until : null;
  audio.play();
  draw();
}
function playSelection() {
  const nums = currentNumbers();
  if (nums.start !== null && nums.end !== null) {
    selectionStart = nums.start / 1000;
    selectionEnd = nums.end / 1000;
  }
  if (selectionStart === null || selectionEnd === null) return;
  playFrom(Math.min(selectionStart, selectionEnd), Math.max(selectionStart, selectionEnd));
}
function currentNumbers() {
  return {
    start: document.getElementById("startMs").value === "" ? null : Number(document.getElementById("startMs").value),
    end: document.getElementById("endMs").value === "" ? null : Number(document.getElementById("endMs").value),
  };
}
function setStartFromPlayhead() {
  selectionStart = audio.currentTime;
  document.getElementById("startMs").value = Math.round(selectionStart * 1000);
  draw();
}
function setEndFromPlayhead() {
  selectionEnd = audio.currentTime;
  document.getElementById("endMs").value = Math.round(selectionEnd * 1000);
  draw();
}
function syncSelectionFromInputs() {
  const nums = currentNumbers();
  selectionStart = nums.start === null ? null : nums.start / 1000;
  selectionEnd = nums.end === null ? null : nums.end / 1000;
  draw();
}
function setZoom(mult) {
  const center = audio ? audio.currentTime : (viewStart + viewEnd) / 2;
  const span = Math.max(0.08, Math.min(200, (viewEnd - viewStart) * mult));
  viewStart = Math.max(0, center - span / 2);
  viewEnd = Math.min(audioBuffer ? audioBuffer.duration : 200, viewStart + span);
  viewStart = Math.max(0, viewEnd - span);
  draw();
}
function canvasTime(ev) { return xToTime(ev.clientX - wave.getBoundingClientRect().left); }
function handleAt(x) {
  if (selectionStart !== null && Math.abs(x - timeToX(selectionStart)) < 9) return "start";
  if (selectionEnd !== null && Math.abs(x - timeToX(selectionEnd)) < 9) return "end";
  return null;
}

wave.addEventListener("mousedown", (ev) => {
  const x = ev.clientX - wave.getBoundingClientRect().left;
  const h = handleAt(x);
  if (h) dragHandle = h;
  else {
    dragHandle = null;
    if (audio) { audio.currentTime = canvasTime(ev); draw(); }
  }
});
wave.addEventListener("mousemove", (ev) => {
  if (!dragHandle) return;
  const t = canvasTime(ev);
  if (dragHandle === "start") { selectionStart = t; document.getElementById("startMs").value = Math.round(t * 1000); }
  if (dragHandle === "end") { selectionEnd = t; document.getElementById("endMs").value = Math.round(t * 1000); }
  draw();
});
window.addEventListener("mouseup", () => { dragHandle = null; });
wave.addEventListener("wheel", (ev) => { ev.preventDefault(); setZoom(ev.deltaY > 0 ? 1.25 : 0.8); }, {passive: false});

async function savePosition(status) {
  try {
    const c = currentPosition();
    if (!c) throw new Error("当前没有入选句子");
    const old = drafts[c.sentence_id] || {};
    const text = sentenceOf(c).trim();
    if (!isCompleteSentence(text)) throw new Error("当前句子不是完整句");
    let payload = {
      candidate_id: c.candidate_id,
      audio_id: c.audio_id,
      audio_num: c.audio_num,
      unit: c.unit,
      chapter: c.chapter,
      activity: c.activity,
      page: c.textbook_page,
      sentence_index: positionIndex + 1,
      sentence_text: text,
      source_text: c.source_text,
      context_text: old.context_text || c.context_text,
      selection_reason: old.selection_reason || null,
      reject_reason: null,
      pattern_key: old.pattern_key || null,
      function_tag: old.function_tag || null,
      duplicate_of: old.duplicate_of || null,
      start_ms: null,
      end_ms: null,
      status: status,
      reviewer: "local-human",
    };
    if (status === "VERIFIED") {
      const nums = currentNumbers();
      payload.start_ms = nums.start;
      payload.end_ms = nums.end;
    } else {
      payload.reject_reason = document.getElementById("posRejectReason").value;
    }
    setMsg("positionMessage", "正在保存…");
    const r = await fetch("/api/save", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
    });
    const out = await r.json();
    if (!out.ok) throw new Error(out.error || "save failed");
    drafts[payload.candidate_id] = payload;
    setMsg("positionMessage", "已保存：" + out.status + " ｜ " + out.saved_at, "ok");
    renderCandidateList();
    rebuildPositionList();
  } catch (err) {
    setMsg("positionMessage", "保存失败：" + err.message, "err");
  }
}

function switchTab(mode) {
  document.getElementById("screenView").hidden = mode !== "screen";
  document.getElementById("positionView").hidden = mode !== "position";
  const tabScreen = document.getElementById("tabScreen");
  if (tabScreen) tabScreen.className = mode === "screen" ? "active" : "";
  document.getElementById("tabPosition").className = mode === "position" ? "active" : "";
  if (mode === "position") showPosition(positionIndex);
}

if (document.getElementById("tabScreen")) {
  document.getElementById("tabScreen").onclick = () => switchTab("screen");
}
document.getElementById("tabPosition").onclick = () => switchTab("position");
document.getElementById("screenFilter").onchange = renderCandidateList;
document.getElementById("btnKeep").onclick = () => saveScreen("CANDIDATE");
document.getElementById("btnReject").onclick = () => saveScreen("REJECTED");
document.getElementById("btnScreenPrev").onclick = () => showScreen(screenIndex - 1);
document.getElementById("btnScreenNext").onclick = () => showScreen(screenIndex + 1);
document.getElementById("positionSelect").onchange = (ev) => showPosition(Number(ev.target.value));
document.getElementById("btnPositionPrev").onclick = () => showPosition(positionIndex - 1);
document.getElementById("btnPositionNext").onclick = () => showPosition(positionIndex + 1);
document.getElementById("btnPlay").onclick = () => playFrom(0, null);
document.getElementById("btnPause").onclick = () => { if (audio) audio.pause(); playUntil = null; draw(); };
document.getElementById("btnPlaySelection").onclick = playSelection;
document.getElementById("btnPlayAround").onclick = () => playFrom(Math.max(0, audio.currentTime - 0.4), Math.min(audio.duration || 999, audio.currentTime + 1.4));
document.getElementById("btnZoomIn").onclick = () => setZoom(0.65);
document.getElementById("btnZoomOut").onclick = () => setZoom(1.55);
document.getElementById("btnFit").onclick = () => { viewStart = 0; viewEnd = audioBuffer ? audioBuffer.duration : 200; draw(); };
document.getElementById("btnSetStart").onclick = setStartFromPlayhead;
document.getElementById("btnSetEnd").onclick = setEndFromPlayhead;
document.getElementById("startMs").addEventListener("input", syncSelectionFromInputs);
document.getElementById("endMs").addEventListener("input", syncSelectionFromInputs);
document.getElementById("btnVerify").onclick = () => savePosition("VERIFIED");
document.getElementById("btnPositionReject").onclick = () => savePosition("REJECTED");
document.getElementById("btnAnalyze").onclick = computeSuggestions;
document.getElementById("btnApplySuggestedStart").onclick = () => {
  if (suggestedStart === null) return;
  selectionStart = suggestedStart / 1000;
  document.getElementById("startMs").value = Math.round(suggestedStart);
  draw();
};
document.getElementById("btnApplySuggestedEnd").onclick = () => {
  if (suggestedEnd === null) return;
  selectionEnd = suggestedEnd / 1000;
  document.getElementById("endMs").value = Math.round(suggestedEnd);
  draw();
};
document.addEventListener("keydown", (ev) => {
  const tag = (ev.target && ev.target.tagName) || "";
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
  if (ev.code === "Space") { ev.preventDefault(); audio && !audio.paused ? audio.pause() : playFrom(audio ? audio.currentTime : 0, null); }
  else if (ev.key === "ArrowLeft" && audio) { audio.currentTime = Math.max(0, audio.currentTime - 0.05); draw(); }
  else if (ev.key === "ArrowRight" && audio) { audio.currentTime = audio.currentTime + 0.05; draw(); }
  else if (ev.key === "Enter") { ev.preventDefault(); if (!document.getElementById("positionView").hidden) savePosition("VERIFIED"); }
  else if (ev.key === "ArrowUp") { ev.preventDefault(); if (!document.getElementById("positionView").hidden) showPosition(positionIndex - 1); else showScreen(screenIndex - 1); }
  else if (ev.key === "ArrowDown") { ev.preventDefault(); if (!document.getElementById("positionView").hidden) showPosition(positionIndex + 1); else showScreen(screenIndex + 1); }
});

Promise.all([
  fetch("/api/candidates").then((r) => r.json()),
  fetch("/api/annotations").then((r) => r.json()),
]).then(([candData, draftData]) => {
  candidates = candData.candidates || [];
  drafts = draftData || {};
  showScreen(0);
  rebuildPositionList();
  switchTab("position");
});
