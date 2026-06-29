const cameraImage = document.querySelector("#cameraImage");
const viewerState = document.querySelector("#viewerState");
const statusText = document.querySelector("#status");
const stackchanUrl = document.querySelector("#stackchanUrl");
const audioBaseUrl = document.querySelector("#audioBaseUrl");
const sceneSelect = document.querySelector("#scene");
const providerSelect = document.querySelector("#provider");
const promptInput = document.querySelector("#prompt");
const sendToStackChan = document.querySelector("#sendToStackChan");
const playInBrowser = document.querySelector("#playInBrowser");
const audioUnlockButton = document.querySelector("#audioUnlockButton");
const useHistory = document.querySelector("#useHistory");
const analyzeButton = document.querySelector("#analyzeButton");
const demoStartButton = document.querySelector("#demoStartButton");
const demoStopButton = document.querySelector("#demoStopButton");
const demoState = document.querySelector("#demoState");
const autoInterval = document.querySelector("#autoInterval");
const scriptStartButton = document.querySelector("#scriptStartButton");
const scriptStopButton = document.querySelector("#scriptStopButton");
const scriptState = document.querySelector("#scriptState");
const scriptInterval = document.querySelector("#scriptInterval");
const scriptTable = document.querySelector("#scriptTable");
const pauseButton = document.querySelector("#pauseButton");
const refreshButton = document.querySelector("#refreshButton");
const resetHistoryButton = document.querySelector("#resetHistoryButton");
const historyList = document.querySelector("#historyList");
const jsonOutput = document.querySelector("#jsonOutput");
const reply = document.querySelector("#reply");
const phase = document.querySelector("#phase");
const safety = document.querySelector("#safety");
const audioKey = document.querySelector("#audioKey");
const latency = document.querySelector("#latency");

let paused = false;
let lastFrameAt = 0;
let autoTimer = null;
let autoRunning = false;
let analyzing = false;
let autoAbortController = null;
let scriptStates = [];
let scriptTimer = null;
let scriptRunning = false;
let scriptIndex = 0;
let statusHoldUntil = 0;
let audioContext = null;
let currentAudioSource = null;
let browserAudioUnlocked = false;
let frameRefreshTimer = null;

const stackchanStillnessBufferMs = 800;

const defaultPrompts = {
  desk:
    "StackChanのカメラ画像を見て、卓上作業の実況として次の一言を返して。手元、キーボード、PC、マグカップ、スマホ、姿勢、離席、照明、散らかり具合を読む。カップが端やPCに近い時、手の通り道にある時、暗い時は短く注意する。同じ認識結果が続く時は同じ発話を避ける。スマホ継続だけは「スマホ長すぎ」に切り替え、それ以外の連続状態は雑談にする。",
  tetris:
    "StackChanのカメラ画像を見て、テトリス盤面の実況として次の一言を返して。盤面、現在ミノ、ゴースト、ホールド、ネクスト、井戸、積み上がり、ライン消し、おじゃま、トップアウトを読む。読める時だけ具体的に、ホールド、回転、左右移動、ソフトドロップ、ハードドロップ、井戸を空ける、平積み、復旧、Tetris、T-spin、コンボなどの短い助言を出す。画面が暗い、ブレている、盤面が切れている場合は断定せず撮影調整を促す。同じ状況が続く時は同じ発話を避け、短い実況や雑談も挟む。",
};

function cameraUrl() {
  const base = stackchanUrl.value.trim() || "http://192.168.11.15";
  const params = new URLSearchParams({ stackchan_url: base, t: String(Date.now()) });
  return `/api/camera.jpg?${params}`;
}

function refreshFrame() {
  if (paused) return;
  const next = cameraUrl();
  viewerState.textContent = "更新中";
  cameraImage.src = next;
}

function setStatus(text, { holdMs = 0 } = {}) {
  statusText.textContent = text;
  statusHoldUntil = holdMs ? Date.now() + holdMs : 0;
}

cameraImage.addEventListener("load", () => {
  lastFrameAt = Date.now();
  viewerState.textContent = "";
  if (Date.now() > statusHoldUntil) {
    setStatus(`映像 ${new Date(lastFrameAt).toLocaleTimeString()}`);
  }
});

cameraImage.addEventListener("error", () => {
  viewerState.textContent = "取得失敗";
  statusText.textContent = "StackChan camera error";
});

pauseButton.addEventListener("click", () => {
  paused = !paused;
  pauseButton.textContent = paused ? "▶" : "⏸";
  pauseButton.title = paused ? "再開" : "一時停止";
  statusText.textContent = paused ? "停止中" : "映像更新中";
  if (!paused) refreshFrame();
});

refreshButton.addEventListener("click", refreshFrame);

function renderHistory(items) {
  historyList.innerHTML = "";
  if (!items || items.length === 0) {
    const empty = document.createElement("li");
    empty.textContent = "まだ履歴はありません。";
    empty.className = "empty-history";
    historyList.appendChild(empty);
    return;
  }
  for (const item of [...items].reverse()) {
    const li = document.createElement("li");
    li.innerHTML = `
      <div><strong>${item.time}</strong> ${item.game_phase} / ${item.safety_level}</div>
      <p>${item.reply}</p>
      <span>${item.audio_key}</span>
    `;
    historyList.appendChild(li);
  }
}

function renderResultPayload(payload) {
  jsonOutput.textContent = JSON.stringify(payload, null, 2);
  const data = payload.data;
  reply.textContent = data.reply;
  phase.textContent = data.game_phase;
  safety.textContent = data.safety_level;
  audioKey.textContent = data.stackchan.audio_key;
  latency.textContent = `${payload.latency_ms}ms`;
  renderHistory(payload.history || []);
  setStatus(payload.stackchan_post ? "StackChan送信済み" : "発火完了", { holdMs: 2000 });
  playAudioForPayload(payload);
  scheduleFrameRefreshWhenStill(payload);
}

function scheduleFrameRefreshWhenStill(payload) {
  if (frameRefreshTimer) {
    clearTimeout(frameRefreshTimer);
    frameRefreshTimer = null;
  }
  const delayMs = estimatedStillnessDelayMs(payload);
  if (delayMs <= 0) {
    refreshFrame();
    return;
  }
  frameRefreshTimer = setTimeout(() => {
    frameRefreshTimer = null;
    refreshFrame();
  }, delayMs);
}

function stopBrowserAudio() {
  if (!currentAudioSource) return;
  try {
    currentAudioSource.stop();
  } catch {
    // Already stopped.
  }
  currentAudioSource = null;
}

function audioSourceForPayload(payload) {
  const audio = payload?.stackchan_packet?.audio;
  if (!audio || audio.silent) return "";
  const src = audio.path || audio.url || "";
  if (!src) return "";
  if (src.startsWith("/")) {
    return `${src}?t=${Date.now()}`;
  }
  return src;
}

async function playAudioForPayload(payload) {
  if (!playInBrowser.checked) return;
  const src = audioSourceForPayload(payload);
  if (!src) {
    if (payload?.stackchan_packet?.audio?.silent) {
      setStatus("無音キー", { holdMs: 1200 });
    }
    return;
  }
  if (!(await ensureBrowserAudioUnlocked())) {
    setStatus("PC音声有効化を押してください", { holdMs: 3000 });
    return;
  }
  stopBrowserAudio();
  try {
    const response = await fetch(src);
    if (!response.ok) {
      throw new Error(`audio fetch failed: ${response.status}`);
    }
    const audioBuffer = await audioContext.decodeAudioData(await response.arrayBuffer());
    const source = audioContext.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(audioContext.destination);
    source.onended = () => {
      if (currentAudioSource === source) {
        currentAudioSource = null;
      }
    };
    currentAudioSource = source;
    source.start();
    setStatus("PC音声プレビュー中", { holdMs: 1800 });
  } catch (error) {
    setStatus("PC音声プレビューに失敗。もう一度ボタンを押してください", { holdMs: 3000 });
    console.warn("browser audio playback failed", error);
  }
}

async function ensureBrowserAudioUnlocked() {
  if (!audioContext) {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) {
      return false;
    }
    audioContext = new AudioContextClass();
  }
  if (audioContext.state === "suspended") {
    try {
      await audioContext.resume();
    } catch {
      return false;
    }
  }
  browserAudioUnlocked = audioContext.state === "running";
  return browserAudioUnlocked;
}

async function unlockBrowserAudio() {
  if (!(await ensureBrowserAudioUnlocked())) {
    setStatus("PC音声を有効化できませんでした", { holdMs: 3000 });
    return;
  }
  const buffer = audioContext.createBuffer(1, 1, audioContext.sampleRate);
  const source = audioContext.createBufferSource();
  source.buffer = buffer;
  source.connect(audioContext.destination);
  source.start();
  setStatus("PC音声プレビュー有効", { holdMs: 2000 });
}

async function loadHistory() {
  try {
    const response = await fetch("/api/history");
    const payload = await response.json();
    renderHistory(payload.history || []);
  } catch {
    renderHistory([]);
  }
}

async function loadDemoStates() {
  try {
    const response = await fetch("/api/demo-states");
    const payload = await response.json();
    scriptStates = payload.states || [];
    renderScriptTable();
    renderScriptControls();
  } catch {
    scriptStates = [];
    renderScriptTable();
    renderScriptControls();
  }
}

function renderScriptTable() {
  const tbody = scriptTable.querySelector("tbody");
  tbody.innerHTML = "";
  if (!scriptStates.length) {
    const row = document.createElement("tr");
    row.innerHTML = `<td colspan="5">台本がありません。</td>`;
    tbody.appendChild(row);
    return;
  }
  for (const item of scriptStates) {
    const row = document.createElement("tr");
    row.dataset.state = item.state;
    const lines = (item.variants || []).map((variant, index) => `${index + 1}. ${variant.text}`).join("<br>");
    row.innerHTML = `
      <td><strong>${item.state}</strong><span>${item.label || ""}</span></td>
      <td>${item.trigger || ""}</td>
      <td>${lines}</td>
      <td>${item.tone || ""}</td>
      <td><button type="button" data-demo-state="${item.state}">発火</button></td>
    `;
    tbody.appendChild(row);
  }
}

resetHistoryButton.addEventListener("click", async () => {
  resetHistoryButton.disabled = true;
  try {
    const response = await fetch("/api/reset-history", { method: "POST" });
    const payload = await response.json();
    renderHistory(payload.history || []);
    statusText.textContent = "履歴をリセット";
  } finally {
    resetHistoryButton.disabled = false;
  }
});

function renderDemoControls() {
  demoStartButton.disabled = autoRunning;
  demoStopButton.disabled = !autoRunning;
  demoState.textContent = autoRunning ? "実行中" : "停止中";
  demoState.dataset.running = autoRunning ? "true" : "false";
}

function renderScriptControls() {
  scriptStartButton.disabled = scriptRunning || scriptStates.length === 0;
  scriptStopButton.disabled = !scriptRunning;
  scriptState.textContent = scriptRunning ? `実行中 ${scriptIndex + 1}/${scriptStates.length}` : "停止中";
  scriptState.dataset.running = scriptRunning ? "true" : "false";
  for (const row of scriptTable.querySelectorAll("tbody tr")) {
    row.classList.toggle("active", scriptRunning && row.dataset.state === scriptStates[scriptIndex]?.state);
  }
}

async function runAnalysis({ auto = false } = {}) {
  if (analyzing) return null;
  analyzing = true;
  analyzeButton.disabled = true;
  analyzeButton.textContent = auto ? "自動認識中" : "認識中";
  statusText.textContent = auto ? "自動デモ実行中" : "Geminiへ送信中";
  const abortController = auto ? new AbortController() : null;
  if (auto) {
    autoAbortController = abortController;
  }
  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: abortController?.signal,
      body: JSON.stringify({
        provider: providerSelect.value,
        scene: sceneSelect.value,
        stackchan_url: stackchanUrl.value.trim(),
        stackchan_action_url: `${stackchanUrl.value.trim().replace(/\/$/, "")}/action`,
        audio_base_url: audioBaseUrl.value.trim(),
        prompt: promptInput.value.trim(),
        send_to_stackchan: sendToStackChan.checked,
        use_history: useHistory.checked,
        auto_mode: auto,
      }),
    });
    const payload = await response.json();
    if (!payload.ok) {
      throw new Error(payload.message || "analyze failed");
    }
    renderResultPayload(payload);
    return payload;
  } catch (error) {
    if (error.name === "AbortError") {
      statusText.textContent = "自動デモ停止";
      return null;
    }
    statusText.textContent = "認識失敗";
    reply.textContent = error.message;
    return null;
  } finally {
    if (auto && autoAbortController === abortController) {
      autoAbortController = null;
    }
    analyzing = false;
    analyzeButton.disabled = false;
    analyzeButton.textContent = "認識する";
    renderDemoControls();
  }
}

async function triggerDemoState(stateName, { variantIndex = null } = {}) {
  const response = await fetch("/api/demo-action", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      state: stateName,
      variant_index: variantIndex,
      stackchan_url: stackchanUrl.value.trim(),
      stackchan_action_url: `${stackchanUrl.value.trim().replace(/\/$/, "")}/action`,
      audio_base_url: audioBaseUrl.value.trim(),
      send_to_stackchan: sendToStackChan.checked,
    }),
  });
  const payload = await response.json();
  if (!payload.ok) {
    jsonOutput.textContent = JSON.stringify(payload, null, 2);
    throw new Error(payload.message || "demo action failed");
  }
  renderResultPayload(payload);
  return payload;
}

function startScriptDemo() {
  if (scriptRunning || !scriptStates.length) return;
  stopAutoDemo();
  useHistory.checked = true;
  scriptRunning = true;
  scriptIndex = 0;
  renderScriptControls();
  setStatus("台本デモ開始", { holdMs: 2000 });
  runScriptStep();
}

function stopScriptDemo() {
  scriptRunning = false;
  if (scriptTimer) {
    clearTimeout(scriptTimer);
  }
  scriptTimer = null;
  if (frameRefreshTimer) {
    clearTimeout(frameRefreshTimer);
  }
  frameRefreshTimer = null;
  stopBrowserAudio();
  renderScriptControls();
  setStatus("台本デモ停止", { holdMs: 2000 });
}

async function runScriptStep() {
  if (!scriptRunning) return;
  const item = scriptStates[scriptIndex];
  if (!item) {
    stopScriptDemo();
    statusText.textContent = "台本デモ完了";
    return;
  }
  renderScriptControls();
  try {
    const payload = await triggerDemoState(item.state, { variantIndex: 0 });
    if (!scriptRunning) return;
    scriptIndex += 1;
    if (scriptIndex >= scriptStates.length) {
      stopScriptDemo();
      setStatus("台本デモ完了", { holdMs: 3000 });
      return;
    }
    const intervalMs = Number(scriptInterval.value) * 1000;
    const stillnessMs = estimatedStillnessDelayMs(payload);
    const nextDelayMs = stillnessMs + intervalMs;
    scriptTimer = setTimeout(runScriptStep, nextDelayMs);
    renderScriptControls();
  } catch (error) {
    reply.textContent = error.message;
    stopScriptDemo();
    setStatus("台本デモ失敗", { holdMs: 3000 });
  }
}

function startAutoDemo() {
  if (autoRunning) return;
  useHistory.checked = true;
  sendToStackChan.checked = true;
  autoRunning = true;
  renderDemoControls();
  statusText.textContent = "自動デモ開始";
  runAutoTick();
}

function stopAutoDemo() {
  autoRunning = false;
  if (autoTimer) {
    clearTimeout(autoTimer);
  }
  autoTimer = null;
  if (frameRefreshTimer) {
    clearTimeout(frameRefreshTimer);
  }
  frameRefreshTimer = null;
  stopBrowserAudio();
  if (autoAbortController) {
    autoAbortController.abort();
    autoAbortController = null;
  }
  renderDemoControls();
  statusText.textContent = "自動デモ停止";
}

async function runAutoTick() {
  if (!autoRunning) return;
  if (autoTimer) {
    clearTimeout(autoTimer);
    autoTimer = null;
  }
  const payload = await runAnalysis({ auto: true });
  if (!autoRunning) return;
  const intervalMs = Number(autoInterval.value) * 1000;
  const stillnessMs = estimatedStillnessDelayMs(payload);
  const nextDelayMs = stillnessMs + intervalMs;
  statusText.textContent = `次の認識まで約${Math.max(1, Math.round(nextDelayMs / 1000))}秒`;
  autoTimer = setTimeout(runAutoTick, nextDelayMs);
}

function estimatedStillnessDelayMs(payload) {
  const busyMs = Math.max(estimatedSpeechMs(payload), estimatedMotionMs(payload));
  return busyMs > 0 ? busyMs + stackchanStillnessBufferMs : 0;
}

function estimatedSpeechMs(payload) {
  const audio = payload?.stackchan_packet?.audio;
  const sent = payload?.stackchan_post?.received?.audio_playing;
  if (!audio || sent === false) return 0;
  return Number(audio.estimated_stackchan_playback_ms || audio.duration_ms || 0);
}

function estimatedMotionMs(payload) {
  const packet = payload?.stackchan_packet;
  if (!packet) return 0;
  const reportedMs = Number(packet.estimated_stackchan_motion_ms || 0);
  if (reportedMs > 0) return reportedMs;

  const motion = String(packet.motion || "none");
  const intensity = Math.max(0, Math.min(3, Number(packet.intensity || 1)));
  const durationMs = 420 + intensity * 90;
  if (!motion || motion === "none" || motion === "stop") return 0;
  if (motion === "nod" || motion === "tilt_left" || motion === "tilt_right") {
    return durationMs + 450 + 550;
  }
  if (motion === "shake") return durationMs + 500 + 550;
  if (motion === "bounce") return durationMs + 420 + 550;
  if (motion === "rotate") return 900 + intensity * 220 + 600;
  return durationMs;
}

analyzeButton.addEventListener("click", () => {
  runAnalysis();
});

demoStartButton.addEventListener("click", startAutoDemo);
demoStopButton.addEventListener("click", stopAutoDemo);
audioUnlockButton.addEventListener("click", unlockBrowserAudio);
scriptStartButton.addEventListener("click", startScriptDemo);
scriptStopButton.addEventListener("click", stopScriptDemo);

scriptTable.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-demo-state]");
  if (!button) return;
  stopScriptDemo();
  try {
    await triggerDemoState(button.dataset.demoState);
  } catch (error) {
    reply.textContent = error.message;
    statusText.textContent = "発火失敗";
  }
});

autoInterval.addEventListener("change", () => {
  if (!autoRunning) return;
  stopAutoDemo();
  startAutoDemo();
});

sceneSelect.addEventListener("change", () => {
  promptInput.value = defaultPrompts[sceneSelect.value] || defaultPrompts.desk;
  resetHistoryButton.click();
  reply.textContent = "認識結果がここに出ます。";
  phase.textContent = "-";
  safety.textContent = "-";
  audioKey.textContent = "-";
  latency.textContent = "-";
});

loadHistory();
loadDemoStates();
renderDemoControls();
renderScriptControls();
refreshFrame();
setInterval(refreshFrame, 750);

window.deskChanDemo = {
  start: startAutoDemo,
  stop: stopAutoDemo,
  startScript: startScriptDemo,
  stopScript: stopScriptDemo,
  isRunning: () => autoRunning,
  isScriptRunning: () => scriptRunning,
};
