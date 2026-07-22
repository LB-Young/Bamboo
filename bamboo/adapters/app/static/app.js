const state = {
  sessions: [],
  currentSessionId: null,
  currentRecordDir: null,
  mode: "chat",
  projectPath: "",
  streaming: false,
  pendingAssistant: null,
  activeReasoning: null,
  toolRows: new Map(),
};

const els = {
  projectPath: document.getElementById("projectPath"),
  applyProject: document.getElementById("applyProject"),
  newSession: document.getElementById("newSession"),
  sessionScope: document.getElementById("sessionScope"),
  sessionCount: document.getElementById("sessionCount"),
  sessionList: document.getElementById("sessionList"),
  chatTitle: document.getElementById("chatTitle"),
  chatMeta: document.getElementById("chatMeta"),
  statusPill: document.getElementById("statusPill"),
  chatHistory: document.getElementById("chatHistory"),
  permissionDock: document.getElementById("permissionDock"),
  messageInput: document.getElementById("messageInput"),
  imagePaths: document.getElementById("imagePaths"),
  sendButton: document.getElementById("sendButton"),
  refreshChanges: document.getElementById("refreshChanges"),
  envRows: document.getElementById("envRows"),
  changeSummary: document.getElementById("changeSummary"),
  changeList: document.getElementById("changeList"),
  diffTitle: document.getElementById("diffTitle"),
  diffView: document.getElementById("diffView"),
};

window.BambooDesktop = {
  onEvent(event) {
    handleEvent(event);
  },
};

async function apiCall(name, ...args) {
  if (!window.pywebview?.api) throw new Error("pywebview bridge is not ready");
  return await window.pywebview.api[name](...args);
}

async function init() {
  setStatus("loading", "Loading");
  const data = await apiCall("get_initial_state");
  state.projectPath = data.project_path || "";
  state.mode = data.mode || "chat";
  state.currentSessionId = data.session_id || null;
  els.projectPath.value = state.projectPath;
  renderScope();
  renderSessions(data.sessions || []);
  renderChanges(data.changes || {});
  newSessionView();
  setStatus("idle");
  if (data.initial_message || (data.initial_image_paths || []).length) {
    els.messageInput.value = data.initial_message || "";
    els.imagePaths.value = (data.initial_image_paths || []).join(", ");
    await sendMessage();
  }
}

function renderScope() {
  state.projectPath = els.projectPath.value.trim();
  state.mode = state.projectPath ? "project" : "chat";
  els.sessionScope.textContent = state.mode === "project" ? "Project history" : "Chat history";
  els.chatMeta.textContent = state.mode === "project" ? `Project · ${state.projectPath}` : "Chat mode";
}

async function refreshSidebar() {
  renderScope();
  const sessions = await apiCall("list_sessions", state.projectPath);
  renderSessions(sessions || []);
}

function renderSessions(sessions) {
  state.sessions = sessions;
  els.sessionCount.textContent = `${sessions.length}`;
  els.sessionList.innerHTML = "";
  if (!sessions.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "No sessions";
    els.sessionList.appendChild(empty);
    return;
  }
  for (const session of sessions) {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "session-item";
    item.classList.toggle("active", session.session_id === state.currentSessionId);
    item.addEventListener("click", () => loadSession(session));
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

async function loadSession(session) {
  const data = await apiCall("load_session", session.record_dir);
  if (!data.ok) return showSystem(data.error || "Load failed", "error");
  state.currentSessionId = data.session_id;
  state.currentRecordDir = session.record_dir;
  state.mode = data.mode || "chat";
  state.projectPath = data.project_path || "";
  els.projectPath.value = state.projectPath;
  renderScope();
  els.chatHistory.innerHTML = "";
  resetTurnState();
  for (const msg of data.messages || []) appendRestoredMessage(msg);
  els.chatTitle.textContent = session.label || "Conversation";
  renderSessions(state.sessions);
  renderChanges(data.changes || {});
}

async function newSession() {
  renderScope();
  const data = await apiCall("new_session", state.projectPath);
  if (!data.ok) return showSystem(data.error || "New session failed", "error");
  state.currentSessionId = data.session_id;
  state.currentRecordDir = null;
  renderSessions(data.sessions || []);
  renderChanges(data.changes || {});
  newSessionView();
}

function newSessionView() {
  els.chatHistory.innerHTML = "";
  resetTurnState();
  els.chatTitle.textContent = "New chat";
  renderScope();
  showSystem(state.mode === "project" ? "Project mode is active." : "Chat mode is active.");
}

async function sendMessage() {
  const message = els.messageInput.value.trim();
  const images = els.imagePaths.value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  if (!message && !images.length) return;
  renderScope();
  appendMessage("user", message || images.join("\n"));
  els.messageInput.value = "";
  resetTurnState();
  setStatus("running", "Running");
  const result = await apiCall("send_message", message, state.projectPath, images);
  if (!result.ok) {
    showSystem(result.error || "Send failed", "error");
    setStatus("idle");
  }
}

function handleEvent(event) {
  if (event.type === "run_start") {
    state.currentSessionId = event.session_id;
    renderScope();
    renderSessions(state.sessions);
    return;
  }
  if (event.type === "run_finish") {
    setStatus("idle");
    renderSessions(event.sessions || []);
    renderChanges(event.changes || {});
    return;
  }
  if (event.type === "error") {
    showSystem(event.error || "Error", "error");
    setStatus("idle");
    return;
  }
  if (event.type === "agent_status") {
    setStatus("running", event.status);
    return;
  }
  if (event.type === "reasoning_start") {
    startReasoning();
    return;
  }
  if (event.type === "reasoning_delta") {
    appendReasoning(event.text || "");
    return;
  }
  if (event.type === "reasoning_finish") {
    finishReasoning(event.text || "");
    return;
  }
  if (event.type === "text_delta") {
    ensureAssistant().textContent += event.text || "";
    scrollToBottom();
    return;
  }
  if (event.type === "text_finish") {
    if (event.text) ensureAssistant().textContent = event.text;
    state.pendingAssistant = null;
    scrollToBottom();
    return;
  }
  if (event.type === "tool_call") {
    showToolCall(event);
    return;
  }
  if (event.type === "tool_result") {
    showToolResult(event);
    return;
  }
  if (event.type === "tool_error") {
    showToolError(event);
    return;
  }
  if (event.type === "permission_request") {
    showPermission(event);
    return;
  }
  if (event.type === "permission_result") {
    closePermission(event);
  }
}

function appendMessage(role, text) {
  const article = document.createElement("article");
  article.className = `message ${role}`;
  article.textContent = text;
  els.chatHistory.appendChild(article);
  scrollToBottom();
  return article;
}

function appendRestoredMessage(message) {
  const reasoning = message?.metadata?.reasoning_content || "";
  if (message.role === "assistant" && reasoning.trim()) {
    startReasoning();
    finishReasoning(reasoning);
  }
  appendMessage(message.role, message.content || "");
}

function showSystem(text, kind = "system") {
  return appendMessage(kind, text);
}

function ensureAssistant() {
  if (!state.pendingAssistant) state.pendingAssistant = appendMessage("assistant", "");
  return state.pendingAssistant;
}

function resetTurnState() {
  state.pendingAssistant = null;
  state.activeReasoning = null;
  state.toolRows.clear();
}

function startReasoning() {
  const row = createDetails("Reasoning", "thinking");
  row.details.classList.add("reasoning-row");
  state.activeReasoning = row;
}

function appendReasoning(text) {
  if (!state.activeReasoning) startReasoning();
  state.activeReasoning.output.textContent += text;
  state.activeReasoning.preview.textContent = summarize(state.activeReasoning.output.textContent);
}

function finishReasoning(text) {
  if (!state.activeReasoning && text) startReasoning();
  if (!state.activeReasoning) return;
  if (text && !state.activeReasoning.output.textContent.trim()) state.activeReasoning.output.textContent = text;
  state.activeReasoning.status.textContent = "collapsed";
  state.activeReasoning.preview.textContent = summarize(state.activeReasoning.output.textContent);
  state.activeReasoning = null;
}

function showToolCall(event) {
  const row = createDetails(`Tool · ${event.name}`, "running");
  row.output.textContent = JSON.stringify(event.input || {}, null, 2);
  state.toolRows.set(event.id || event.name, row);
}

function showToolResult(event) {
  const row = state.toolRows.get(event.id || event.name) || createDetails(`Tool · ${event.name}`, "done");
  row.status.textContent = "done";
  row.output.textContent = event.output || "";
  row.preview.textContent = summarize(event.output || "");
}

function showToolError(event) {
  const row = state.toolRows.get(event.id || event.name) || createDetails(`Tool · ${event.name}`, "error");
  row.status.textContent = "error";
  row.details.classList.add("failed");
  row.output.textContent = event.error || "";
}

function createDetails(titleText, statusText) {
  const details = document.createElement("details");
  details.className = "event-row";
  const summary = document.createElement("summary");
  const title = document.createElement("span");
  title.className = "event-title";
  title.textContent = titleText;
  const status = document.createElement("span");
  status.className = "event-status";
  status.textContent = statusText;
  const preview = document.createElement("code");
  preview.className = "event-preview";
  preview.textContent = "";
  const output = document.createElement("pre");
  output.className = "event-output";
  summary.append(title, status, preview);
  details.append(summary, output);
  els.chatHistory.appendChild(details);
  scrollToBottom();
  return { details, status, preview, output };
}

function showPermission(event) {
  els.permissionDock.hidden = false;
  els.permissionDock.innerHTML = "";
  const title = document.createElement("strong");
  title.textContent = `Permission required: ${event.name}`;
  const meta = document.createElement("span");
  meta.textContent = `${event.risk || "unknown"} · ${event.reason || ""}`;
  const allow = document.createElement("button");
  allow.textContent = "Allow";
  allow.addEventListener("click", () => submitPermission(event.request_id, "allow"));
  const deny = document.createElement("button");
  deny.textContent = "Deny";
  deny.addEventListener("click", () => submitPermission(event.request_id, "deny"));
  els.permissionDock.append(title, meta, allow, deny);
}

async function submitPermission(requestId, decision) {
  await apiCall("submit_permission", requestId, decision);
}

function closePermission() {
  els.permissionDock.hidden = true;
  els.permissionDock.innerHTML = "";
}

function renderChanges(changes) {
  const files = changes.files || [];
  els.envRows.innerHTML = "";
  addEnvRow("Mode", state.projectPath ? "Project" : "Chat");
  addEnvRow("Project", changes.project_path || "none");
  addEnvRow("Branch", changes.branch || "-");
  els.changeSummary.textContent = `+${changes.additions || 0} -${changes.deletions || 0}`;
  els.changeList.innerHTML = "";
  if (!files.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "No changes";
    els.changeList.appendChild(empty);
    return;
  }
  for (const file of files) {
    const row = document.createElement("button");
    row.className = "change-row";
    row.type = "button";
    row.innerHTML = `<span>${escapeHtml(file.file)}</span><code>+${file.additions} -${file.deletions}</code>`;
    row.addEventListener("click", () => loadDiff(file.file));
    els.changeList.appendChild(row);
  }
}

function addEnvRow(label, value) {
  const row = document.createElement("div");
  row.className = "env-row";
  row.innerHTML = `<span>${escapeHtml(label)}</span><code>${escapeHtml(value)}</code>`;
  els.envRows.appendChild(row);
}

async function loadDiff(file) {
  const data = await apiCall("get_diff", state.projectPath, file);
  els.diffTitle.textContent = file;
  els.diffView.textContent = data.ok ? data.diff || "No diff." : data.error || "Diff failed";
}

function setStatus(status, text = "") {
  const busy = status !== "idle";
  els.statusPill.textContent = busy ? text || status : "Idle";
  els.statusPill.classList.toggle("busy", busy);
  els.statusPill.classList.toggle("idle", !busy);
  els.sendButton.disabled = busy;
}

function summarize(text) {
  const value = String(text || "").replace(/\s+/g, " ").trim();
  return value.length > 90 ? `${value.slice(0, 87)}...` : value;
}

function formatTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString([], { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  })[char]);
}

function scrollToBottom() {
  els.chatHistory.scrollTop = els.chatHistory.scrollHeight;
}

els.applyProject.addEventListener("click", async () => {
  renderScope();
  await refreshSidebar();
  renderChanges(await apiCall("get_changes", state.projectPath));
});
els.newSession.addEventListener("click", newSession);
els.sendButton.addEventListener("click", sendMessage);
els.refreshChanges.addEventListener("click", async () => renderChanges(await apiCall("get_changes", state.projectPath)));
els.messageInput.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
    event.preventDefault();
    sendMessage();
  }
});

window.addEventListener("pywebviewready", () => {
  init().catch((error) => {
    console.error(error);
    showSystem(String(error), "error");
    setStatus("idle");
  });
});
