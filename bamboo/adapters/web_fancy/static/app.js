const state = {
  mode: window.localStorage.getItem("bamboo.web.mode") || "chat",
  projectPath: window.localStorage.getItem("bamboo.web.projectPath") || "",
  sessions: [],
  currentSessionId: null,
  currentRecordDir: null,
  currentTaskId: null,
  stopRequested: false,
  streaming: false,
  toolCount: 0,
  engaged: false,
};

const els = {
  app: document.getElementById("app"),
  panelToggle: document.getElementById("panelToggle"),
  activityToggle: document.getElementById("activityToggle"),
  chatMode: document.getElementById("chatMode"),
  projectMode: document.getElementById("projectMode"),
  projectPanel: document.getElementById("projectPanel"),
  projectPath: document.getElementById("projectPath"),
  applyProject: document.getElementById("applyProject"),
  sessionScope: document.getElementById("sessionScope"),
  sessionCount: document.getElementById("sessionCount"),
  sessionList: document.getElementById("sessionList"),
  newSession: document.getElementById("newSession"),
  chatTitle: document.getElementById("chatTitle"),
  chatMeta: document.getElementById("chatMeta"),
  statusPill: document.getElementById("statusPill"),
  chatHistory: document.getElementById("chatHistory"),
  composer: document.getElementById("composer"),
  messageInput: document.getElementById("messageInput"),
  composerHint: document.getElementById("composerHint"),
  sendButton: document.getElementById("sendButton"),
  stopButton: document.getElementById("stopButton"),
  activityList: document.getElementById("activityList"),
  toolMetric: document.getElementById("toolMetric"),
  modeMetric: document.getElementById("modeMetric"),
  orbCanvas: document.getElementById("orbCanvas"),
};

let pendingAssistant = null;
const toolRows = new Map();

const orb = {
  ctx: els.orbCanvas.getContext("2d"),
  width: 0,
  height: 0,
  dpr: 1,
  t: 0,
  sparks: Array.from({ length: 26 }, (_, index) => ({
    seed: index * 19.73,
    speed: 0.25 + (index % 5) * 0.035,
    phase: index * 0.37,
  })),
};

function setEngaged(value) {
  state.engaged = value;
  els.app.classList.toggle("engaged", value);
  els.app.classList.toggle("landing", !value);
}

function applyModeUI() {
  const isProject = state.mode === "project";
  els.chatMode.classList.toggle("active", !isProject);
  els.projectMode.classList.toggle("active", isProject);
  els.projectPanel.hidden = !isProject;
  els.projectPath.value = state.projectPath;
  els.sessionScope.textContent = isProject ? "Project history" : "Chat history";
  els.modeMetric.textContent = isProject ? "Project" : "Chat";
  els.composerHint.textContent = isProject
    ? `Project: ${state.projectPath || "当前目录"}`
    : "当前为 Chat 模式";
}

function setStatus(status, detail = "") {
  const busy = status !== "idle";
  els.statusPill.textContent = busy ? (detail || "Running") : "Idle";
  els.statusPill.classList.toggle("busy", busy);
  els.statusPill.classList.toggle("idle", !busy);
  els.sendButton.disabled = busy;
  els.stopButton.hidden = !busy;
  els.stopButton.disabled = !busy || state.stopRequested || !state.currentTaskId;
}

async function loadSidebar() {
  const url = new URL("/api/sidebar", window.location.origin);
  url.searchParams.set("mode", state.mode);
  if (state.mode === "project" && state.projectPath) url.searchParams.set("project_path", state.projectPath);
  const res = await fetch(url);
  if (!res.ok) throw new Error("sidebar failed");
  const data = await res.json();
  state.sessions = data.sessions || [];
  renderSessions();
}

function renderSessions() {
  els.sessionCount.textContent = `${state.sessions.length} sessions`;
  els.sessionList.innerHTML = "";
  if (!state.sessions.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "暂无会话记录";
    els.sessionList.appendChild(empty);
    return;
  }
  for (const session of state.sessions) {
    const item = document.createElement("button");
    item.className = "session-item";
    item.type = "button";
    item.classList.toggle("active", session.session_id === state.currentSessionId);
    item.addEventListener("click", () => selectSession(session));

    const title = document.createElement("span");
    title.className = "session-title";
    title.textContent = session.label || session.session_id;

    const meta = document.createElement("span");
    meta.className = "session-meta";
    meta.textContent = formatTime(session.updated_at || session.created_at);

    item.append(title, meta);
    els.sessionList.appendChild(item);
  }
}

async function selectSession(session) {
  setEngaged(true);
  state.currentSessionId = session.session_id;
  state.currentRecordDir = session.record_dir || null;
  renderSessions();

  const url = new URL(`/api/sessions/${session.session_id}`, window.location.origin);
  url.searchParams.set("mode", state.mode);
  if (state.currentRecordDir) url.searchParams.set("record_dir", state.currentRecordDir);
  if (state.mode === "project" && state.projectPath) url.searchParams.set("project_path", state.projectPath);

  const res = await fetch(url);
  if (!res.ok) {
    showSystem("无法加载该会话。");
    return;
  }
  const data = await res.json();
  state.currentRecordDir = data.record_dir || state.currentRecordDir;
  els.chatHistory.innerHTML = "";
  resetActivity();
  for (const msg of data.messages || []) appendMessage(msg.role, msg.content);
  els.chatTitle.textContent = session.label || "Conversation";
  els.chatMeta.textContent = `${state.mode === "project" ? "Project" : "Chat"} · ${session.session_id}`;
  scrollToBottom();
}

function newSession() {
  state.currentSessionId = null;
  state.currentRecordDir = null;
  state.currentTaskId = null;
  state.stopRequested = false;
  pendingAssistant = null;
  resetToolEvents();
  resetActivity();
  els.chatHistory.innerHTML = "";
  els.chatTitle.textContent = "New chat";
  els.chatMeta.textContent = state.mode === "project" ? "Project mode" : "Chat mode";
  setEngaged(false);
  renderSessions();
  requestAnimationFrame(() => els.messageInput.focus());
}

function appendMessage(role, text) {
  const row = document.createElement("article");
  row.className = `message-row ${role}`;

  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = role === "user" ? "U" : role === "assistant" ? "B" : "!";

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";
  bubble.textContent = text;

  row.append(avatar, bubble);
  els.chatHistory.appendChild(row);
  scrollToBottom();
  return bubble;
}

function showSystem(text) {
  return appendMessage("system", text);
}

function ensureAssistant() {
  if (!pendingAssistant) pendingAssistant = appendMessage("assistant", "");
  return pendingAssistant;
}

async function sendMessage(text, imagePaths = null) {
  imagePaths = imagePaths ?? parseImagePaths(document.getElementById("imagePathsInput")?.value || "");
  setEngaged(true);
  state.streaming = true;
  state.stopRequested = false;
  state.currentTaskId = null;
  state.toolCount = 0;
  updateMetrics();
  setStatus("running", "Running");
  pendingAssistant = null;
  resetToolEvents();
  resetActivity();
  appendMessage("user", imagePaths.length ? `${text}\n\n[images: ${imagePaths.length}]` : text);

  const payload = {
    message: text,
    mode: state.mode,
    project_path: state.mode === "project" ? state.projectPath : null,
    session_id: state.currentSessionId,
    record_dir: state.currentRecordDir,
    image_paths: imagePaths,
  };

  try {
    const res = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok || !res.body) throw new Error("stream failed");
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let index;
      while ((index = buffer.indexOf("\n")) >= 0) {
        const line = buffer.slice(0, index).trim();
        buffer = buffer.slice(index + 1);
        if (line) handleEvent(JSON.parse(line));
      }
    }
  } catch (err) {
    console.error(err);
    showSystem("请求失败，请检查服务端或模型配置。");
    addActivity("error", "Request failed");
  } finally {
    state.streaming = false;
    state.currentTaskId = null;
    state.stopRequested = false;
    setStatus("idle");
  }
}

function parseImagePaths(value) {
  return value
    .split(/[\n,]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function handleEvent(event) {
  if (event.type === "session") {
    state.currentSessionId = event.session_id;
    state.currentTaskId = event.task_id || state.currentTaskId;
    state.currentRecordDir = event.record_dir || state.currentRecordDir;
    els.chatMeta.textContent = `${state.mode === "project" ? "Project" : "Chat"} · ${event.session_id}`;
    setStatus("running", state.stopRequested ? "Stopping" : "Running");
    addActivity("session", "Session started");
    return;
  }
  if (event.type === "task") {
    state.currentTaskId = event.task_id || state.currentTaskId;
    setStatus("running", state.stopRequested ? "Stopping" : "Running");
    addActivity("task", event.title || "Task created");
    return;
  }
  if (event.type === "task_status" && event.to === "cancelled") {
    showSystem("已停止当前任务。");
    state.stopRequested = true;
    setStatus("running", "Stopping");
    addActivity("stop", "Cancellation requested");
    return;
  }
  if (event.type === "cancelled") {
    showSystem(event.message || "已停止当前任务。");
    state.stopRequested = true;
    setStatus("running", "Stopping");
    addActivity("stop", "Cancelled");
    return;
  }
  if (event.type === "delta") {
    ensureAssistant().textContent += event.text || "";
    scrollToBottom();
    return;
  }
  if (event.type === "message") {
    ensureAssistant().textContent = event.text || "";
    pendingAssistant = null;
    addActivity("message", "Assistant response completed");
    scrollToBottom();
    return;
  }
  if (event.type === "tool_call") return showToolCall(event);
  if (event.type === "permission_request") return showPermissionRequest(event);
  if (event.type === "permission_result") return updatePermissionResult(event);
  if (event.type === "tool_result") return updateToolResult(event);
  if (event.type === "tool_error") return updateToolError(event);
  if (event.type === "error") {
    showSystem(event.message || "运行出错");
    addActivity("error", event.message || "Runtime error");
    return;
  }
  if (event.type === "status") {
    setStatus("running", event.status || "Running");
    addActivity("status", event.status || "Status changed");
    return;
  }
  if (event.type === "step_start") return addActivity("step", `Step ${event.step_id || ""}`.trim());
  if (event.type === "step_finish") return addActivity("done", event.summary || "Step completed");
  if (event.type === "subagent_start") return addActivity("agent", `${event.name || "subagent"} started`);
  if (event.type === "subagent_finish") {
    return addActivity("agent", `${event.name || "subagent"} ${event.status || "finished"}`);
  }
  if (event.type === "complete") {
    state.currentRecordDir = event.record_dir || state.currentRecordDir;
    addActivity("done", "Run completed");
    loadSidebar().catch(console.error);
  }
}

function resetToolEvents() {
  toolRows.clear();
  updateMetrics();
}

function showToolCall(event) {
  const id = toolEventId(event);
  const row = document.createElement("details");
  row.className = "tool-card running";
  row.open = false;

  const summary = document.createElement("summary");
  const name = document.createElement("span");
  name.className = "tool-name";
  name.textContent = event.name || "tool";
  const status = document.createElement("span");
  status.className = "tool-status";
  status.textContent = "Running";
  const input = document.createElement("code");
  input.textContent = formatToolInput(event.input);
  summary.append(name, status, input);
  row.appendChild(summary);
  els.chatHistory.appendChild(row);
  toolRows.set(id, { row, status, input });
  state.toolCount += 1;
  updateMetrics();
  addActivity("tool", `${event.name || "tool"} called`);
  scrollToBottom();
}

function showPermissionRequest(event) {
  const refs = ensureToolRow(event);
  refs.row.classList.remove("done", "failed");
  refs.row.classList.add("awaiting-permission");
  refs.row.open = true;
  refs.status.textContent = "Confirm";
  refs.input.textContent = `${event.risk || "unknown"} · ${event.reason || "需要确认"}`;
  refs.row.querySelector(".permission-actions")?.remove();

  const actions = document.createElement("div");
  actions.className = "permission-actions";
  const detail = document.createElement("span");
  detail.textContent = `${event.name || "tool"} 请求 ${event.risk || "unknown"} 权限`;
  const allow = document.createElement("button");
  allow.type = "button";
  allow.className = "allow";
  allow.textContent = "Allow";
  allow.addEventListener("click", () => submitPermission(event, "allow", actions));
  const deny = document.createElement("button");
  deny.type = "button";
  deny.className = "deny";
  deny.textContent = "Deny";
  deny.addEventListener("click", () => submitPermission(event, "deny", actions));
  actions.append(detail, allow, deny);
  refs.row.appendChild(actions);
  addActivity("permission", `${event.name || "tool"} needs approval`);
  scrollToBottom();
}

async function submitPermission(event, decision, actions) {
  if (!event.request_id) return;
  actions.querySelectorAll("button").forEach((button) => {
    button.disabled = true;
  });
  try {
    const res = await fetch(`/api/permissions/${encodeURIComponent(event.request_id)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision }),
    });
    if (!res.ok) throw new Error("permission submit failed");
    const refs = ensureToolRow(event);
    refs.status.textContent = decision === "allow" ? "Allowed" : "Denied";
    refs.row.open = false;
  } catch (err) {
    console.error(err);
    actions.querySelectorAll("button").forEach((button) => {
      button.disabled = false;
    });
    showSystem("权限审批提交失败。");
  }
}

function updatePermissionResult(event) {
  const refs = ensureToolRow(event);
  refs.row.querySelector(".permission-actions")?.remove();
  refs.row.classList.remove("awaiting-permission");
  refs.row.open = false;
  if (event.approved) {
    refs.row.classList.add("running");
    refs.status.textContent = "Approved";
  } else {
    refs.row.classList.add("failed");
    refs.status.textContent = "Denied";
    refs.input.textContent = event.reason || "用户拒绝权限";
  }
}

function updateToolResult(event) {
  const refs = ensureToolRow(event);
  refs.row.classList.remove("running", "failed", "awaiting-permission");
  refs.row.classList.add("done");
  refs.status.textContent = "Done";
  refs.input.textContent = summarizeToolOutput(event.output || "");
  setToolDetails(refs.row, event.output || "");
  addActivity("done", `${event.name || "tool"} completed`);
}

function updateToolError(event) {
  const refs = ensureToolRow(event);
  refs.row.classList.remove("running", "done", "awaiting-permission");
  refs.row.classList.add("failed");
  refs.status.textContent = "Failed";
  refs.input.textContent = event.error || "工具执行失败";
  setToolDetails(refs.row, event.error || "");
  addActivity("error", `${event.name || "tool"} failed`);
}

function ensureToolRow(event) {
  const id = toolEventId(event);
  const existing = toolRows.get(id);
  if (existing) return existing;
  showToolCall(event);
  return toolRows.get(id);
}

function setToolDetails(row, text) {
  row.querySelector(".tool-output")?.remove();
  const content = String(text || "").trim();
  if (!content) return;
  const output = document.createElement("pre");
  output.className = "tool-output";
  output.textContent = content.length > 3200 ? `${content.slice(0, 3200)}\n...` : content;
  row.appendChild(output);
}

function resetActivity() {
  els.activityList.innerHTML = "";
  addActivity("ready", "Ready");
}

function addActivity(kind, label) {
  const item = document.createElement("div");
  item.className = `activity-item ${kind}`;
  const dot = document.createElement("span");
  const text = document.createElement("strong");
  text.textContent = label;
  const time = document.createElement("small");
  time.textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  item.append(dot, text, time);
  els.activityList.prepend(item);
}

function updateMetrics() {
  els.toolMetric.textContent = `${state.toolCount} tools`;
}

function toolEventId(event) {
  return event.id || `${event.name || "tool"}-latest`;
}

function formatToolInput(input) {
  if (!input || typeof input !== "object") return "";
  const entries = Object.entries(input)
    .filter(([, value]) => value !== "" && value !== null && value !== undefined)
    .slice(0, 3);
  return entries.map(([key, value]) => `${key}: ${compactValue(value)}`).join(" · ");
}

function summarizeToolOutput(output) {
  const text = String(output || "").trim();
  if (!text) return "No output";
  const firstLine = text.split("\n").find(Boolean) || text;
  return firstLine.length > 140 ? `${firstLine.slice(0, 140)}...` : firstLine;
}

function compactValue(value) {
  const text = typeof value === "string" ? value : JSON.stringify(value);
  return text.length > 86 ? `${text.slice(0, 86)}...` : text;
}

function bindEvents() {
  els.panelToggle.addEventListener("click", () => els.app.classList.toggle("panels-collapsed"));
  els.activityToggle.addEventListener("click", () => els.app.classList.toggle("activity-collapsed"));
  els.chatMode.addEventListener("click", () => switchMode("chat"));
  els.projectMode.addEventListener("click", () => switchMode("project"));
  els.applyProject.addEventListener("click", async () => {
    state.projectPath = els.projectPath.value.trim();
    window.localStorage.setItem("bamboo.web.projectPath", state.projectPath);
    applyModeUI();
    newSession();
    await loadSidebar();
  });
  els.newSession.addEventListener("click", newSession);
  els.stopButton.addEventListener("click", stopCurrentTask);
  els.composer.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (state.streaming) return;
    const text = els.messageInput.value.trim();
    if (!text) return;
    const imagePaths = parseImagePaths(document.getElementById("imagePathsInput")?.value || "");
    els.messageInput.value = "";
    const imagePathsInput = document.getElementById("imagePathsInput");
    if (imagePathsInput) imagePathsInput.value = "";
    await sendMessage(text, imagePaths);
  });
  els.messageInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !isComposingInput(event)) {
      event.preventDefault();
      els.composer.requestSubmit();
    }
  });
}

function isComposingInput(event) {
  return Boolean(event.isComposing || event.keyCode === 229);
}

async function stopCurrentTask() {
  if (!state.currentTaskId || state.stopRequested) return;
  state.stopRequested = true;
  setStatus("running", "Stopping");
  try {
    const res = await fetch(`/api/tasks/${encodeURIComponent(state.currentTaskId)}/stop`, { method: "POST" });
    if (!res.ok) throw new Error("stop failed");
  } catch (err) {
    console.error(err);
    state.stopRequested = false;
    setStatus("running", "Running");
    showSystem("停止任务失败。");
  }
}

async function switchMode(mode) {
  state.mode = mode;
  window.localStorage.setItem("bamboo.web.mode", mode);
  applyModeUI();
  newSession();
  await loadSidebar();
}

function formatTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 19);
  return date.toLocaleString([], { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function scrollToBottom() {
  requestAnimationFrame(() => {
    els.chatHistory.scrollTop = els.chatHistory.scrollHeight;
  });
}

function resizeOrb() {
  const rect = els.orbCanvas.getBoundingClientRect();
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const width = Math.max(1, Math.floor(rect.width * dpr));
  const height = Math.max(1, Math.floor(rect.height * dpr));
  if (orb.width === width && orb.height === height && orb.dpr === dpr) return;
  orb.width = width;
  orb.height = height;
  orb.dpr = dpr;
  els.orbCanvas.width = width;
  els.orbCanvas.height = height;
}

function drawOrb() {
  resizeOrb();
  const ctx = orb.ctx;
  const w = orb.width;
  const h = orb.height;
  const cx = w / 2;
  const cy = h / 2;
  const radius = Math.min(w, h) * 0.36;
  orb.t += 0.012;

  ctx.clearRect(0, 0, w, h);
  ctx.save();
  ctx.globalCompositeOperation = "lighter";

  const aura = ctx.createRadialGradient(cx, cy, radius * 0.1, cx, cy, radius * 1.35);
  aura.addColorStop(0, "rgba(255, 210, 246, 0.78)");
  aura.addColorStop(0.25, "rgba(255, 102, 199, 0.26)");
  aura.addColorStop(0.72, "rgba(112, 86, 255, 0.08)");
  aura.addColorStop(1, "rgba(0, 0, 0, 0)");
  ctx.fillStyle = aura;
  ctx.beginPath();
  ctx.arc(cx, cy, radius * 1.45, 0, Math.PI * 2);
  ctx.fill();

  const shell = ctx.createRadialGradient(cx - radius * 0.22, cy - radius * 0.26, radius * 0.18, cx, cy, radius);
  shell.addColorStop(0, "rgba(255, 255, 255, 0.22)");
  shell.addColorStop(0.52, "rgba(255, 102, 199, 0.14)");
  shell.addColorStop(0.86, "rgba(255, 102, 199, 0.30)");
  shell.addColorStop(1, "rgba(255, 255, 255, 0.06)");
  ctx.fillStyle = shell;
  ctx.beginPath();
  ctx.arc(cx, cy, radius, 0, Math.PI * 2);
  ctx.fill();

  drawShellRipples(ctx, cx, cy, radius);
  drawNeuralArcs(ctx, cx, cy, radius);
  drawCore(ctx, cx, cy, radius);

  ctx.restore();
  requestAnimationFrame(drawOrb);
}

function drawShellRipples(ctx, cx, cy, radius) {
  for (let i = 0; i < 18; i += 1) {
    const angle = orb.t * 0.45 + i * 0.68;
    const wobble = Math.sin(orb.t * 1.7 + i) * radius * 0.045;
    const x = cx + Math.cos(angle) * (radius * 0.86 + wobble);
    const y = cy + Math.sin(angle * 1.23) * (radius * 0.82 - wobble);
    ctx.strokeStyle = i % 2 ? "rgba(255, 116, 207, 0.26)" : "rgba(255, 255, 255, 0.14)";
    ctx.lineWidth = radius * 0.018;
    ctx.beginPath();
    ctx.arc(x, y, radius * (0.055 + (i % 4) * 0.012), 0, Math.PI * 2);
    ctx.stroke();
  }

  ctx.strokeStyle = "rgba(255, 238, 250, 0.84)";
  ctx.lineWidth = Math.max(1.4, radius * 0.018);
  ctx.beginPath();
  ctx.arc(cx, cy, radius * 1.005, 0, Math.PI * 2);
  ctx.stroke();

  ctx.strokeStyle = "rgba(255, 102, 199, 0.48)";
  ctx.lineWidth = Math.max(3, radius * 0.04);
  ctx.beginPath();
  ctx.arc(cx, cy, radius * 0.96, Math.PI * 0.12, Math.PI * 1.78);
  ctx.stroke();
}

function drawNeuralArcs(ctx, cx, cy, radius) {
  for (const spark of orb.sparks) {
    const base = spark.seed + orb.t * spark.speed;
    const angle = base % (Math.PI * 2);
    const endRadius = radius * (0.62 + 0.30 * Math.sin(base * 0.83 + spark.phase) ** 2);
    const startRadius = radius * 0.12;
    const endX = cx + Math.cos(angle) * endRadius;
    const endY = cy + Math.sin(angle) * endRadius;
    const midAngle = angle + Math.sin(base * 2.1) * 0.26;
    const midRadius = radius * (0.32 + 0.14 * Math.sin(base * 1.4));
    const cp1x = cx + Math.cos(midAngle - 0.34) * midRadius;
    const cp1y = cy + Math.sin(midAngle - 0.34) * midRadius;
    const cp2x = cx + Math.cos(midAngle + 0.24) * (midRadius + radius * 0.24);
    const cp2y = cy + Math.sin(midAngle + 0.24) * (midRadius + radius * 0.24);

    ctx.strokeStyle = "rgba(230, 232, 255, 0.92)";
    ctx.lineWidth = Math.max(1, radius * 0.012);
    ctx.shadowColor = "rgba(143, 123, 255, 0.9)";
    ctx.shadowBlur = radius * 0.08;
    ctx.beginPath();
    ctx.moveTo(cx + Math.cos(angle + Math.PI) * startRadius, cy + Math.sin(angle + Math.PI) * startRadius);
    ctx.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, endX, endY);
    ctx.stroke();

    ctx.strokeStyle = "rgba(84, 78, 255, 0.34)";
    ctx.lineWidth = Math.max(0.8, radius * 0.006);
    ctx.shadowBlur = radius * 0.03;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, endX * 1.01 - cx * 0.01, endY * 1.01 - cy * 0.01);
    ctx.stroke();

    const pulse = 0.65 + 0.35 * Math.sin(base * 4);
    ctx.fillStyle = `rgba(255, 102, 199, ${0.42 + pulse * 0.35})`;
    ctx.shadowColor = "rgba(255, 102, 199, 0.95)";
    ctx.shadowBlur = radius * 0.10;
    ctx.beginPath();
    ctx.arc(endX, endY, radius * (0.015 + pulse * 0.014), 0, Math.PI * 2);
    ctx.fill();
  }
}

function drawCore(ctx, cx, cy, radius) {
  const core = ctx.createRadialGradient(cx, cy, radius * 0.02, cx, cy, radius * 0.18);
  core.addColorStop(0, "rgba(255, 255, 255, 1)");
  core.addColorStop(0.34, "rgba(255, 214, 247, 0.95)");
  core.addColorStop(1, "rgba(255, 102, 199, 0)");
  ctx.fillStyle = core;
  ctx.shadowColor = "rgba(255, 102, 199, 1)";
  ctx.shadowBlur = radius * 0.22;
  ctx.beginPath();
  ctx.arc(cx, cy, radius * (0.16 + Math.sin(orb.t * 3) * 0.012), 0, Math.PI * 2);
  ctx.fill();
}

async function bootstrap() {
  bindEvents();
  applyModeUI();
  resetActivity();
  setEngaged(false);
  drawOrb();
  await loadSidebar();
  requestAnimationFrame(() => els.messageInput.focus());
}

bootstrap().catch((err) => {
  console.error(err);
  showSystem("初始化失败。");
});
