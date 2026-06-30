const state = {
  mode: window.localStorage.getItem("bamboo.web.mode") || "chat",
  projectPath: window.localStorage.getItem("bamboo.web.projectPath") || "",
  sessions: [],
  currentSessionId: null,
  currentRecordDir: null,
  streaming: false,
};

const els = {
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
};

let pendingAssistant = null;
const toolRows = new Map();
let activeToolStack = null;

function applyModeUI() {
  const isProject = state.mode === "project";
  els.chatMode.classList.toggle("active", !isProject);
  els.projectMode.classList.toggle("active", isProject);
  els.projectPanel.hidden = !isProject;
  els.projectPath.value = state.projectPath;
  els.sessionScope.textContent = isProject ? "Project history" : "Chat history";
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
}

async function loadSidebar() {
  const url = new URL("/api/sidebar", window.location.origin);
  url.searchParams.set("mode", state.mode);
  if (state.mode === "project" && state.projectPath) {
    url.searchParams.set("project_path", state.projectPath);
  }
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
    empty.className = "empty";
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
  for (const msg of data.messages || []) appendMessage(msg.role, msg.content);
  els.chatTitle.textContent = session.label || "Conversation";
  els.chatMeta.textContent = `${state.mode === "project" ? "Project" : "Chat"} · ${session.session_id}`;
  scrollToBottom();
}

function newSession() {
  state.currentSessionId = null;
  state.currentRecordDir = null;
  pendingAssistant = null;
  resetToolEvents();
  els.chatHistory.innerHTML = "";
  els.chatTitle.textContent = "New chat";
  els.chatMeta.textContent = state.mode === "project" ? "Project mode" : "Chat mode";
  appendMessage("assistant", state.mode === "project"
    ? "已进入 Project 模式。发送需求后，我会按当前项目上下文处理。"
    : "已进入 Chat 模式。可以直接开始对话。");
  renderSessions();
}

function appendMessage(role, text) {
  const bubble = document.createElement("article");
  bubble.className = `message ${role}`;
  bubble.textContent = text;
  els.chatHistory.appendChild(bubble);
  scrollToBottom();
  return bubble;
}

function showSystem(text) {
  const bubble = appendMessage("system", text);
  return bubble;
}

function ensureAssistant() {
  if (!pendingAssistant) pendingAssistant = appendMessage("assistant", "");
  return pendingAssistant;
}

async function sendMessage(text) {
  state.streaming = true;
  setStatus("running", "Running");
  pendingAssistant = null;
  resetToolEvents();
  appendMessage("user", text);

  const payload = {
    message: text,
    mode: state.mode,
    project_path: state.mode === "project" ? state.projectPath : null,
    session_id: state.currentSessionId,
    record_dir: state.currentRecordDir,
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
  } finally {
    state.streaming = false;
    setStatus("idle");
  }
}

function handleEvent(event) {
  if (event.type === "session") {
    state.currentSessionId = event.session_id;
    state.currentRecordDir = event.record_dir || state.currentRecordDir;
    els.chatMeta.textContent = `${state.mode === "project" ? "Project" : "Chat"} · ${event.session_id}`;
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
    scrollToBottom();
    return;
  }
  if (event.type === "tool_call") {
    showToolCall(event);
    return;
  }
  if (event.type === "tool_result") {
    updateToolResult(event);
    return;
  }
  if (event.type === "tool_error") {
    updateToolError(event);
    return;
  }
  if (event.type === "error") {
    showSystem(event.message || "运行出错");
    return;
  }
  if (event.type === "status") {
    setStatus("running", event.status || "Running");
    return;
  }
  if (event.type === "complete") {
    state.currentRecordDir = event.record_dir || state.currentRecordDir;
    loadSidebar().catch(console.error);
  }
}

function resetToolEvents() {
  toolRows.clear();
  activeToolStack = null;
}

function ensureToolStack() {
  if (activeToolStack && document.body.contains(activeToolStack)) return activeToolStack;
  activeToolStack = document.createElement("section");
  activeToolStack.className = "tool-stack";
  activeToolStack.setAttribute("aria-label", "工具调用");
  els.chatHistory.appendChild(activeToolStack);
  scrollToBottom();
  return activeToolStack;
}

function showToolCall(event) {
  const id = toolEventId(event);
  const stack = ensureToolStack();
  const row = document.createElement("details");
  row.className = "tool-row running";

  const summary = document.createElement("summary");
  summary.className = "tool-summary";

  const name = document.createElement("span");
  name.className = "tool-name";
  name.textContent = event.name || "tool";

  const status = document.createElement("span");
  status.className = "tool-status";
  status.textContent = "运行中";

  const input = document.createElement("code");
  input.className = "tool-preview";
  input.textContent = formatToolInput(event.input);

  summary.append(toolIcon(), name, status, input);
  row.appendChild(summary);
  stack.appendChild(row);
  toolRows.set(id, { row, status, input });
  scrollToBottom();
}

function updateToolResult(event) {
  const refs = ensureToolRow(event);
  refs.row.classList.remove("running", "failed");
  refs.row.classList.add("done");
  refs.status.textContent = "完成";
  refs.input.textContent = summarizeToolOutput(event.output || "");
  setToolDetails(refs.row, event.output || "");
}

function updateToolError(event) {
  const refs = ensureToolRow(event);
  refs.row.classList.remove("running", "done");
  refs.row.classList.add("failed");
  refs.status.textContent = "失败";
  refs.input.textContent = event.error || "工具执行失败";
  setToolDetails(refs.row, event.error || "");
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
  output.textContent = content.length > 2400 ? `${content.slice(0, 2400)}\n...` : content;
  row.appendChild(output);
}

function toolIcon() {
  const icon = document.createElement("span");
  icon.className = "tool-icon";
  icon.textContent = ">";
  return icon;
}

function toolEventId(event) {
  return event.id || `${event.name || "tool"}-latest`;
}

function formatToolInput(input) {
  if (!input || typeof input !== "object") return "";
  const entries = Object.entries(input)
    .filter(([, value]) => value !== "" && value !== null && value !== undefined)
    .slice(0, 2);
  if (!entries.length) return "";
  return entries.map(([key, value]) => `${key}: ${compactValue(value)}`).join(" · ");
}

function summarizeToolOutput(output) {
  const text = String(output || "").trim();
  if (!text) return "无输出";
  if (text === "(no matches)") return "没有匹配结果";
  const firstLine = text.split("\n").find(Boolean) || text;
  return firstLine.length > 120 ? `${firstLine.slice(0, 120)}...` : firstLine;
}

function compactValue(value) {
  const text = typeof value === "string" ? value : JSON.stringify(value);
  return text.length > 72 ? `${text.slice(0, 72)}...` : text;
}

function bindEvents() {
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
  els.composer.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (state.streaming) return;
    const text = els.messageInput.value.trim();
    if (!text) return;
    els.messageInput.value = "";
    await sendMessage(text);
  });
  els.messageInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      els.composer.requestSubmit();
    }
  });
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

async function bootstrap() {
  bindEvents();
  applyModeUI();
  newSession();
  await loadSidebar();
}

bootstrap().catch((err) => {
  console.error(err);
  showSystem("初始化失败。");
});
