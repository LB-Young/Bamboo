const state = {
  sessions: [],
  sessionFilter: localStorage.getItem("bamboo.app.sessionFilter") || "user",
  currentSessionId: null,
  mode: "chat",
  projectPath: "",
  pendingAssistant: null,
  activeReasoning: null,
  reasoningCount: 0,
  toolCount: 0,
  toolRows: new Map(),
  startedAt: null,
  timer: null,
  context: { used_tokens: 0, context_window: 128000, percent: 0, estimated: true },
  models: { selected: "", configured: "", options: [] },
  activeView: "chat",
  logs: [],
  runningSessions: new Set(),
  pendingPermissions: new Map(),
  knowledgeUpdates: new Map(),
  pendingMemoryToolCalls: new Map(),
  knowledgeView: localStorage.getItem("bamboo.app.knowledgeView") || "session",
  scopeKnowledge: { projectPath: "", loading: false, files: [], error: "" },
  collapsedKnowledgeFiles: new Set(),
  stopRequested: false,
  theme: localStorage.getItem("bamboo.app.theme") || "dark",
  permissionMode: localStorage.getItem("bamboo.app.permissionMode") || "default",
  sessionMessagesPath: "",
  recentProjects: [],
  projectMenuOpen: false,
};

window.BambooFancyVersion = "latex-v1";

const MATH_ENVIRONMENTS = [
  "equation",
  "equation*",
  "align",
  "align*",
  "aligned",
  "gather",
  "gather*",
  "multline",
  "multline*",
  "split",
];

applyTheme(state.theme);

const els = {
  projectPath: document.getElementById("projectPath"),
  projectMenuToggle: document.getElementById("projectMenuToggle"),
  projectMenu: document.getElementById("projectMenu"),
  modelSelect: document.getElementById("modelSelect"),
  permissionMode: document.getElementById("permissionMode"),
  copySessionPath: document.getElementById("copySessionPath"),
  applyProject: document.getElementById("applyProject"),
  sessionFilterButtons: Array.from(document.querySelectorAll("[data-session-filter]")),
  newSession: document.getElementById("newSession"),
  sessionScope: document.getElementById("sessionScope"),
  sessionCount: document.getElementById("sessionCount"),
  sessionList: document.getElementById("sessionList"),
  agentScope: document.getElementById("agentScope"),
  chatTitle: document.getElementById("chatTitle"),
  statusPill: document.getElementById("statusPill"),
  themeToggle: document.getElementById("themeToggle"),
  runTimer: document.getElementById("runTimer"),
  runTitle: document.getElementById("runTitle"),
  runBadge: document.getElementById("runBadge"),
  chatHistory: document.getElementById("chatHistory"),
  permissionDock: document.getElementById("permissionDock"),
  messageInput: document.getElementById("messageInput"),
  stopButton: document.getElementById("stopButton"),
  sendButton: document.getElementById("sendButton"),
  contextPercent: document.getElementById("contextPercent"),
  contextRing: document.querySelector(".ring"),
  contextSpirit: document.getElementById("contextSpirit"),
  reasoningCount: document.getElementById("reasoningCount"),
  toolCount: document.getElementById("toolCount"),
  knowledgeSummary: document.getElementById("knowledgeSummary"),
  knowledgeList: document.getElementById("knowledgeList"),
  knowledgeViewButtons: Array.from(document.querySelectorAll("[data-knowledge-view]")),
  fileTree: document.getElementById("fileTree"),
  diffFile: document.getElementById("diffFile"),
  diffCount: document.getElementById("diffCount"),
  diffView: document.getElementById("diffView"),
  reviewText: document.getElementById("reviewText"),
  diffViewPane: document.getElementById("diffViewPane"),
  chatViewPane: document.getElementById("chatViewPane"),
  logsViewPane: document.getElementById("logsViewPane"),
  diffChatSlot: document.getElementById("diffChatSlot"),
  logList: document.getElementById("logList"),
  tabs: Array.from(document.querySelectorAll("[data-view]")),
  timelineItems: Array.from(document.querySelectorAll(".timeline li")),
};

window.BambooDesktop = {
  onEvent(event) {
    handleEvent(event);
  },
};

initMermaid();
installExternalLinkHandler();

async function apiCall(name, ...args) {
  if (!window.pywebview?.api) throw new Error("pywebview bridge is not ready");
  return await window.pywebview.api[name](...args);
}

async function init() {
  setStatus("loading", "Loading");
  setActiveView("chat");
  resetRunTimeline();
  const data = await apiCall("get_initial_state");
  state.projectPath = data.project_path || "";
  state.mode = data.mode || "chat";
  state.currentSessionId = data.session_id || null;
  setSessionMessagesPath(data.messages_path || "");
  state.recentProjects = Array.isArray(data.recent_projects) ? data.recent_projects : [];
  els.projectPath.value = state.projectPath;
  renderProjectOptions();
  renderScope();
  renderSessions(data.sessions || []);
  renderChanges(data.changes || {});
  renderContext(data.context || {});
  renderModels(data.models || {});
  renderPermissionState(data.permission_state || {}, { preferStored: true });
  await refreshKnowledgePanel();
  newSessionView();
  updateActiveRunStatus();
  setStatus("idle");
  if (data.initial_message || (data.initial_image_paths || []).length) {
    els.messageInput.value = [data.initial_message || "", ...(data.initial_image_paths || [])].filter(Boolean).join("\n");
    await sendMessage();
  }
}

function renderScope() {
  state.projectPath = els.projectPath.value.trim();
  state.mode = state.projectPath ? "project" : "chat";
  const label = state.mode === "project" ? state.projectPath : "Chat mode";
  els.agentScope.textContent = label;
  els.sessionScope.textContent = state.mode === "project" ? "Project Sessions" : "Recent Sessions";
}

function renderProjectOptions() {
  if (!els.projectMenu) return;
  const paths = uniqueProjectPaths(state.recentProjects);
  els.projectMenu.innerHTML = "";
  els.projectMenu.appendChild(projectMenuItem("Chat mode", "", "空路径，使用 Chat 模式"));
  for (const path of paths) {
    els.projectMenu.appendChild(projectMenuItem(path, path, path));
  }
}

function projectMenuItem(label, value, title) {
  const item = document.createElement("button");
  item.type = "button";
  item.className = "project-menu-item";
  item.dataset.projectPath = value;
  item.textContent = label;
  item.title = title;
  item.addEventListener("click", async () => {
    els.projectPath.value = value;
    closeProjectMenu();
    await applyProjectPath();
  });
  return item;
}

async function applyProjectPath() {
  renderScope();
  rememberProjectPath(state.projectPath);
  await newSession();
}

function toggleProjectMenu() {
  if (state.projectMenuOpen) {
    closeProjectMenu();
  } else {
    openProjectMenu();
  }
}

function openProjectMenu() {
  renderProjectOptions();
  state.projectMenuOpen = true;
  els.projectMenu.hidden = false;
  els.projectMenuToggle.setAttribute("aria-expanded", "true");
}

function closeProjectMenu() {
  state.projectMenuOpen = false;
  els.projectMenu.hidden = true;
  els.projectMenuToggle.setAttribute("aria-expanded", "false");
}

function rememberProjectPath(path) {
  const normalized = String(path || "").trim();
  if (!normalized) return;
  state.recentProjects = uniqueProjectPaths([normalized, ...state.recentProjects]);
  renderProjectOptions();
}

function uniqueProjectPaths(paths) {
  const seen = new Set();
  const result = [];
  for (const raw of paths || []) {
    const path = String(raw || "").trim();
    if (!path || seen.has(path)) continue;
    seen.add(path);
    result.push(path);
  }
  return result;
}

function toggleTheme() {
  applyTheme(state.theme === "dark" ? "light" : "dark");
}

function applyTheme(theme) {
  state.theme = theme === "light" ? "light" : "dark";
  document.body.dataset.theme = state.theme;
  localStorage.setItem("bamboo.app.theme", state.theme);
  const toggle = document.getElementById("themeToggle");
  if (!toggle) return;
  const nextTheme = state.theme === "dark" ? "light" : "dark";
  toggle.textContent = nextTheme === "light" ? "Light" : "Dark";
  toggle.setAttribute("aria-label", `Switch to ${nextTheme} theme`);
}

async function refreshSidebar() {
  renderScope();
  const sessions = await apiCall("list_sessions", state.projectPath);
  renderSessions(sessions || []);
}

function renderSessions(sessions) {
  state.sessions = dedupeSessions(sessions);
  const visibleSessions = filterSessions(state.sessions);
  els.sessionCount.textContent = `${visibleSessions.length}`;
  els.sessionList.innerHTML = "";
  renderSessionFilter();
  if (!visibleSessions.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = state.sessionFilter === "all" ? "No sessions" : "No user sessions";
    els.sessionList.appendChild(empty);
    return;
  }
  for (const session of visibleSessions) {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "session-item";
    const needsPermission = state.pendingPermissions.has(session.session_id);
    item.classList.toggle("active", session.session_id === state.currentSessionId);
    item.classList.toggle("running", state.runningSessions.has(session.session_id));
    item.classList.toggle("needs-permission", needsPermission);
    if (needsPermission) item.title = "Waiting for permission approval";
    item.addEventListener("click", () => loadSession(session));
    const status = needsPermission ? " · approval needed" : (state.runningSessions.has(session.session_id) ? " · running" : "");
    item.innerHTML = `<span>${escapeHtml(session.label || session.session_id)}</span><small>${escapeHtml(formatTime(session.updated_at || session.created_at))}${status}</small>`;
    els.sessionList.appendChild(item);
  }
}

function dedupeSessions(sessions) {
  const seen = new Set();
  const deduped = [];
  for (const session of sessions || []) {
    const key = session.session_id || session.record_dir || "";
    if (!key || seen.has(key)) continue;
    seen.add(key);
    deduped.push(session);
  }
  return deduped;
}

function filterSessions(sessions) {
  if (state.sessionFilter === "all") return sessions || [];
  return (sessions || []).filter((session) => isUserAppSession(session));
}

function isUserAppSession(session) {
  if (isSubagentSession(session)) return false;
  const metadata = session?.metadata || {};
  const platform = String(metadata.platform || "").toLowerCase();
  return platform === "app";
}

function isSubagentSession(session) {
  const metadata = session?.metadata || {};
  return Boolean(metadata.subagent_name || metadata.parent_session_id || metadata.parent_task_id);
}

function renderSessionFilter() {
  for (const button of els.sessionFilterButtons) {
    const selected = button.dataset.sessionFilter === state.sessionFilter;
    button.classList.toggle("selected", selected);
    button.setAttribute("aria-pressed", selected ? "true" : "false");
  }
}

async function loadSession(session) {
  const data = await apiCall("load_session", session.record_dir);
  if (!data.ok) return showSystem(data.error || "Load failed", "error");
  state.currentSessionId = data.session_id;
  setSessionMessagesPath(data.messages_path || session.messages_path || "");
  state.mode = data.mode || "chat";
  state.projectPath = data.project_path || "";
  setSessionKnowledgeUpdates(state.currentSessionId, data.knowledge_updates || []);
  els.projectPath.value = state.projectPath;
  rememberProjectPath(state.projectPath);
  renderScope();
  els.chatHistory.innerHTML = "";
  resetTurnState();
  resetRunTimeline();
  for (const msg of data.messages || []) appendRestoredMessage(msg);
  els.chatTitle.textContent = session.label || "Conversation";
  renderSessions(state.sessions);
  renderChanges(data.changes || {});
  renderContext(data.context || {});
  renderModels(data.models || {});
  renderPermissionState(data.permission_state || {});
  if (data.running) state.runningSessions.add(state.currentSessionId);
  updateActiveRunStatus();
  renderLogs();
  renderActivePermission();
  await refreshKnowledgePanel();
}

async function newSession() {
  renderScope();
  rememberProjectPath(state.projectPath);
  const data = await apiCall("new_session", state.projectPath);
  if (!data.ok) return showSystem(data.error || "New session failed", "error");
  state.currentSessionId = data.session_id;
  setSessionMessagesPath(data.messages_path || "");
  state.knowledgeUpdates.set(state.currentSessionId, []);
  renderSessions(data.sessions || []);
  renderChanges(data.changes || {});
  renderContext(data.context || {});
  renderModels(data.models || {});
  renderPermissionState(data.permission_state || {});
  newSessionView();
  updateActiveRunStatus();
  renderLogs();
  renderActivePermission();
  await refreshKnowledgePanel();
}

function newSessionView() {
  els.chatHistory.innerHTML = "";
  resetTurnState();
  setActiveView("chat");
  els.runTitle.textContent = "No active task";
  els.reviewText.textContent = "Bamboo will ask before applying risky file or shell changes.";
  resetRunTimeline();
  showSystem(state.mode === "project" ? "Project mode is active." : "Chat mode is active.");
}

async function sendMessage() {
  const message = els.messageInput.value.trim();
  if (!message) return;
  renderScope();
  rememberProjectPath(state.projectPath);
  appendMessage("user", message);
  bumpContextEstimate(message, 0);
  els.messageInput.value = "";
  resetTurnState();
  resetRunTimeline();
  state.stopRequested = false;
  setStatus("running", "Executing");
  els.runTitle.textContent = message || "Image task";
  updateRunStage("planning", "active", "Preparing request");
  const result = await apiCall(
    "send_message",
    message,
    state.projectPath,
    [],
    els.modelSelect.value || "",
    state.permissionMode || "default",
  );
  if (!result.ok) {
    showSystem(result.error || "Send failed", "error");
    setStatus("idle");
  } else if (result.model) {
    if (result.session_id) state.runningSessions.add(result.session_id);
    if (result.messages_path) setSessionMessagesPath(result.messages_path);
    setSelectedModel(result.model);
    if (result.permission_state) renderPermissionState(result.permission_state);
    updateActiveRunStatus();
  }
}

function handleEvent(event) {
  addLog(event);
  const current = isCurrentSessionEvent(event);
  if (event.type === "run_start") {
    if (event.session_id) state.runningSessions.add(event.session_id);
    if (!current) {
      renderSessions(state.sessions);
      return;
    }
    state.currentSessionId = event.session_id;
    if (event.model) setSelectedModel(event.model);
    state.startedAt = Date.now();
    startTimer();
    renderScope();
    renderSessions(state.sessions);
    els.runTitle.textContent = event.message || els.runTitle.textContent;
    setStatus("running", "Executing");
    updateRunStage("planning", "done", "Request prepared");
    updateRunStage("executing", "active", "Running agent");
    return;
  }
  if (event.type === "run_finish") {
    if (event.session_id) {
      state.runningSessions.delete(event.session_id);
      state.pendingPermissions.delete(event.session_id);
    }
    if (!current) {
      renderSessions(event.sessions || state.sessions);
      return;
    }
    const cancelled = Boolean(event.cancelled || state.stopRequested);
    if (event.messages_path) setSessionMessagesPath(event.messages_path);
    setStatus("idle");
    state.stopRequested = false;
    stopTimer();
    renderSessions(event.sessions || []);
    renderChanges(event.changes || {});
    refreshContext();
    updateRunStage("executing", cancelled ? "error" : "done", cancelled ? "Cancelled" : "Task finished");
    updateRunStage("review", cancelled ? "idle" : ((event.changes?.files || []).length ? "active" : "done"), cancelled ? "Cancelled by user" : ((event.changes?.files || []).length ? "Review changes" : "No changes"));
    return;
  }
  if (event.type === "permission_request") {
    if (event.session_id) state.pendingPermissions.set(event.session_id, event);
    renderSessions(state.sessions);
    if (current) {
      updateRunStage("review", "active", `Permission: ${event.name}`);
      showPermission(event);
    }
    return;
  }
  if (event.type === "permission_result") {
    if (event.session_id) state.pendingPermissions.delete(event.session_id);
    renderSessions(state.sessions);
    if (current) {
      updateRunStage("review", event.approved ? "done" : "error", event.approved ? "Approved" : "Rejected");
      closePermission();
    }
    return;
  }
  if (event.type === "knowledge_update") {
    addKnowledgeUpdate(event);
    if (current) void refreshKnowledgePanel();
    return;
  }
  if (event.type === "knowledge_error") {
    addKnowledgeUpdate({ ...event, status: "error", operation: "error", content: event.reason || "" });
    if (current) void refreshKnowledgePanel();
    return;
  }
  if (event.type === "tool_call" && event.name === "memory_update") {
    rememberMemoryToolCall(event);
  }
  if (event.type === "tool_result" && event.name === "memory_update") {
    addKnowledgeUpdateFromMemoryTool(event);
  }
  if (event.type === "tool_error" && event.name === "memory_update") {
    state.pendingMemoryToolCalls.delete(toolCallKey(event));
  }
  if (!current) return;
  if (event.type === "cancelled") {
    state.stopRequested = true;
    setStatus("running", "Stopping");
    showSystem(event.message || "cancelled by user");
    updateRunStage("executing", "error", "Cancelling");
    return;
  }
  if (event.type === "error") {
    showSystem(event.error || "Error", "error");
    setStatus("idle");
    stopTimer();
    updateRunStage("executing", "error", event.error || "Task failed");
    return;
  }
  if (event.type === "agent_status") {
    setStatus("running", event.status);
    updateRunStage("executing", "active", event.reason || event.status || "Running");
    return;
  }
  if (event.type === "task_create") {
    els.runTitle.textContent = event.title || els.runTitle.textContent;
    updateRunStage("planning", "active", event.title || "Task created");
    return;
  }
  if (event.type === "task_status") {
    const done = ["completed", "failed", "cancelled"].includes(event.to_status);
    updateRunStage("executing", done ? "done" : "active", event.to_status || "Running");
    return;
  }
  if (event.type === "step_start") {
    updateRunStage("executing", "active", event.step_id || "Step started");
    return;
  }
  if (event.type === "step_finish") {
    updateRunStage("executing", "done", event.summary || "Step finished");
    updateRunStage("review", "active", event.files_changed?.length ? `${event.files_changed.length} files changed` : "Checking changes");
    return;
  }
  if (event.type === "reasoning_start") return startReasoning();
  if (event.type === "reasoning_delta") return appendReasoning(event.text || "");
  if (event.type === "reasoning_finish") return finishReasoning(event.text || "");
  if (event.type === "text_delta") {
    appendAssistantText(event.text || "");
    bumpContextEstimate(event.text || "", 0);
    return scrollToBottom();
  }
  if (event.type === "text_finish") {
    if (event.text) renderMessageContent(ensureAssistant(), "assistant", event.text);
    state.pendingAssistant = null;
    return scrollToBottom();
  }
  if (event.type === "tool_call") {
    updateRunStage("executing", "active", `Tool: ${event.name}`);
    return showToolCall(event);
  }
  if (event.type === "tool_result") return showToolResult(event);
  if (event.type === "tool_error") {
    updateRunStage("executing", "error", `Tool failed: ${event.name}`);
    return showToolError(event);
  }
  if (event.type === "context_usage") return renderContext(event.context || {});
}

function isCurrentSessionEvent(event) {
  return !event.session_id || event.session_id === state.currentSessionId;
}

function appendMessage(role, text) {
  const article = document.createElement("article");
  article.className = `message ${role}`;
  const icon = messageIcon(role);
  const body = document.createElement("div");
  body.className = "message-body";
  const copy = document.createElement("button");
  copy.className = "copy-message";
  copy.type = "button";
  copy.textContent = "Copy";
  copy.addEventListener("click", () => copyMessage(article, copy));
  article.append(icon, body, copy);
  renderMessageContent(article, role, text);
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

function messageIcon(role) {
  const meta = messageIconMeta(role);
  const icon = document.createElement("span");
  icon.className = `message-icon ${meta.className}`;
  icon.textContent = meta.text;
  icon.title = meta.title;
  icon.setAttribute("aria-label", meta.title);
  return icon;
}

function messageIconMeta(role) {
  const normalized = String(role || "system").toLowerCase();
  if (normalized === "user") return { text: "U", title: "User message", className: "user-icon" };
  if (normalized === "assistant") return { text: "B", title: "Bamboo response", className: "assistant-icon" };
  if (normalized === "tool") return { text: "T", title: "Tool message", className: "tool-icon" };
  if (normalized === "error") return { text: "!", title: "Error message", className: "error-icon" };
  return { text: "i", title: "System message", className: "system-icon" };
}

function ensureAssistant() {
  if (!state.pendingAssistant) state.pendingAssistant = appendMessage("assistant", "");
  return state.pendingAssistant;
}

function appendAssistantText(text) {
  const article = ensureAssistant();
  renderMessageContent(article, "assistant", `${article.dataset.raw || ""}${text}`);
}

function renderMessageContent(element, role, text) {
  element.dataset.raw = text || "";
  const body = element.querySelector(".message-body") || element;
  if (role === "assistant") {
    body.innerHTML = markdownToHtml(text || "");
    renderMermaidBlocks(body);
    renderMathBlocks(body);
  } else {
    body.textContent = text || "";
  }
}

async function copyMessage(article, button) {
  const text = article.dataset.raw || "";
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    textarea.remove();
  }
  const previous = button.textContent;
  button.textContent = "Copied";
  setTimeout(() => {
    button.textContent = previous;
  }, 1200);
}

function markdownToHtml(markdown) {
  const lines = String(markdown || "").replace(/\r\n/g, "\n").split("\n");
  const html = [];
  let paragraph = [];
  let listItems = [];
  let codeLines = [];
  let inCode = false;
  let codeLang = "";

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    const fence = /^```([\w-]*)\s*$/.exec(line);
    if (fence) {
      if (inCode) {
        html.push(renderCodeBlock(codeLang, codeLines.join("\n")));
        codeLines = [];
        codeLang = "";
        inCode = false;
      } else {
        flushParagraph();
        flushList();
        inCode = true;
        codeLang = fence[1] || "";
      }
      continue;
    }
    if (inCode) {
      codeLines.push(line);
      continue;
    }
    if (!line.trim()) {
      flushParagraph();
      flushList();
      continue;
    }
    const mathEnvironment = collectMathEnvironment(lines, index);
    if (mathEnvironment) {
      flushParagraph();
      flushList();
      html.push(renderMathBlock(mathEnvironment.code));
      index = mathEnvironment.nextIndex - 1;
      continue;
    }
    if (isTableStart(lines, index)) {
      flushParagraph();
      flushList();
      const table = collectTable(lines, index);
      html.push(table.html);
      index = table.nextIndex - 1;
      continue;
    }
    const heading = /^(#{1,4})\s+(.+)$/.exec(line);
    if (heading) {
      flushParagraph();
      flushList();
      const level = heading[1].length;
      html.push(`<h${level}>${inlineMarkdown(heading[2])}</h${level}>`);
      continue;
    }
    const bullet = /^\s*[-*]\s+(.+)$/.exec(line);
    if (bullet) {
      flushParagraph();
      listItems.push(`<li>${inlineMarkdown(bullet[1])}</li>`);
      continue;
    }
    paragraph.push(line);
  }
  if (inCode) html.push(renderCodeBlock(codeLang, codeLines.join("\n")));
  flushParagraph();
  flushList();
  return html.join("");

  function flushParagraph() {
    if (!paragraph.length) return;
    html.push(`<p>${inlineMarkdown(paragraph.join("\n"))}</p>`);
    paragraph = [];
  }

  function flushList() {
    if (!listItems.length) return;
    html.push(`<ul>${listItems.join("")}</ul>`);
    listItems = [];
  }
}

function renderCodeBlock(language, code) {
  const normalized = String(language || "").toLowerCase();
  if (normalized === "mermaid" || normalized === "mmd") {
    return `<div class="mermaid-wrap"><div class="mermaid">${escapeHtml(code)}</div></div>`;
  }
  if (isMathOnlyCodeBlock(normalized, code)) {
    return renderMathBlock(code);
  }
  const mathPreviews = extractMathEnvironments(code).map((math) => renderMathBlock(math)).join("");
  return `<pre><code${language ? ` data-lang="${escapeHtml(language)}"` : ""}>${escapeHtml(code)}</code></pre>${mathPreviews}`;
}

function renderMathBlock(code) {
  return `<div class="math-wrap"><div class="math-block">${escapeHtml(code.trim())}</div></div>`;
}

function collectMathEnvironment(lines, startIndex) {
  const line = lines[startIndex] || "";
  const env = mathEnvironmentName(line);
  if (!env) return null;
  const endPattern = new RegExp(`\\\\end\\{${escapeRegExp(env)}\\}`);
  const collected = [];
  for (let index = startIndex; index < lines.length; index += 1) {
    collected.push(lines[index]);
    if (endPattern.test(lines[index])) {
      return { code: collected.join("\n"), nextIndex: index + 1 };
    }
  }
  return null;
}

function mathEnvironmentName(line) {
  const match = /^\s*\\begin\{([^}]+)\}/.exec(line || "");
  if (!match) return "";
  return MATH_ENVIRONMENTS.includes(match[1]) ? match[1] : "";
}

function isMathOnlyCodeBlock(language, code) {
  const normalized = String(code || "").trim();
  if (!normalized) return false;
  if (["math", "latex-math", "tex-math"].includes(language)) return true;
  if (["latex", "tex"].includes(language) && extractMathEnvironments(normalized).join("\n\n").trim() === normalized) {
    return true;
  }
  return extractMathEnvironments(normalized).join("\n\n").trim() === normalized;
}

function extractMathEnvironments(code) {
  const source = String(code || "");
  const environments = MATH_ENVIRONMENTS.map(escapeRegExp).join("|");
  const pattern = new RegExp(`\\\\begin\\{(${environments})\\}[\\s\\S]*?\\\\end\\{\\1\\}`, "g");
  return source.match(pattern) || [];
}

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function initMermaid() {
  if (!window.mermaid) return;
  try {
    window.mermaid.initialize({
      startOnLoad: false,
      theme: "dark",
      securityLevel: "strict",
      flowchart: { useMaxWidth: true, curve: "basis" },
      sequence: { useMaxWidth: true },
    });
  } catch (error) {
    console.warn("mermaid init failed", error);
  }
}

function installExternalLinkHandler() {
  els.chatHistory.addEventListener("click", async (event) => {
    const target = event.target instanceof Element ? event.target : event.target?.parentElement;
    const link = target?.closest?.("a[href]");
    if (!link || !els.chatHistory.contains(link)) return;
    const href = link.href || "";
    if (!/^https?:\/\//i.test(href)) return;
    event.preventDefault();
    try {
      if (window.pywebview?.api?.open_external_url) {
        const result = await window.pywebview.api.open_external_url(href);
        if (result?.ok) return;
      }
    } catch (error) {
      console.warn("external link open failed", error);
    }
    window.open(href, "_blank", "noopener,noreferrer");
  });
}

function renderMermaidBlocks(root) {
  const nodes = Array.from(root.querySelectorAll(".mermaid:not([data-processed])"));
  if (!nodes.length || !window.mermaid?.run) return;
  try {
    window.mermaid.run({ nodes });
  } catch (error) {
    console.warn("mermaid render failed", error);
  }
}

function renderMathBlocks(root) {
  renderExplicitMathBlocks(root);
  if (!window.renderMathInElement) return;
  try {
    window.renderMathInElement(root, {
      delimiters: [
        { left: "$$", right: "$$", display: true },
        { left: "\\[", right: "\\]", display: true },
        { left: "\\(", right: "\\)", display: false },
        { left: "$", right: "$", display: false },
      ],
      ignoredTags: ["script", "noscript", "style", "textarea", "pre", "code"],
      throwOnError: false,
      strict: false,
    });
  } catch (error) {
    console.warn("math render failed", error);
  }
}

function renderExplicitMathBlocks(root) {
  if (!window.katex?.render) return;
  const nodes = Array.from(root.querySelectorAll(".math-block:not([data-processed])"));
  for (const node of nodes) {
    const source = node.textContent || "";
    try {
      window.katex.render(source, node, {
        displayMode: true,
        throwOnError: false,
        strict: false,
      });
      node.dataset.processed = "true";
    } catch (error) {
      console.warn("math block render failed", error);
    }
  }
}

function inlineMarkdown(text) {
  return escapeHtml(text)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>")
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
}

function isTableStart(lines, index) {
  return splitTableRow(lines[index]).length > 1 && isTableDivider(lines[index + 1] || "");
}

function collectTable(lines, startIndex) {
  const headers = splitTableRow(lines[startIndex]);
  const alignments = splitTableRow(lines[startIndex + 1]).map((cell) => {
    const trimmed = cell.trim();
    if (trimmed.startsWith(":") && trimmed.endsWith(":")) return "center";
    if (trimmed.endsWith(":")) return "right";
    return "left";
  });
  const rows = [];
  let index = startIndex + 2;
  while (index < lines.length && splitTableRow(lines[index]).length > 1) {
    rows.push(splitTableRow(lines[index]));
    index += 1;
  }
  const headerHtml = headers
    .map((cell, cellIndex) => `<th style="text-align:${alignments[cellIndex] || "left"}">${inlineMarkdown(cell.trim())}</th>`)
    .join("");
  const bodyHtml = rows
    .map((row) => `<tr>${headers.map((_, cellIndex) => `<td style="text-align:${alignments[cellIndex] || "left"}">${inlineMarkdown((row[cellIndex] || "").trim())}</td>`).join("")}</tr>`)
    .join("");
  return {
    html: `<div class="md-table-wrap"><table><thead><tr>${headerHtml}</tr></thead><tbody>${bodyHtml}</tbody></table></div>`,
    nextIndex: index,
  };
}

function splitTableRow(line) {
  const trimmed = String(line || "").trim();
  if (!trimmed.includes("|")) return [];
  return trimmed.replace(/^\|/, "").replace(/\|$/, "").split("|");
}

function isTableDivider(line) {
  const cells = splitTableRow(line);
  return cells.length > 1 && cells.every((cell) => /^:?-{3,}:?$/.test(cell.trim()));
}

function resetTurnState() {
  state.pendingAssistant = null;
  state.activeReasoning = null;
  state.reasoningCount = 0;
  state.toolCount = 0;
  state.toolRows.clear();
  els.reasoningCount.textContent = "0";
  els.toolCount.textContent = "0";
}

function startReasoning() {
  state.reasoningCount += 1;
  els.reasoningCount.textContent = `${state.reasoningCount}`;
  const row = createDetails("Reasoning", "thinking", "reasoning");
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
  state.toolCount += 1;
  els.toolCount.textContent = `${state.toolCount}`;
  const row = createDetails(`Tool · ${event.name}`, "running", "tool");
  row.output.textContent = JSON.stringify(event.input || {}, null, 2);
  state.toolRows.set(event.id || event.name, row);
}

function showToolResult(event) {
  const row = state.toolRows.get(event.id || event.name) || createDetails(`Tool · ${event.name}`, "done", "tool");
  row.status.textContent = "done";
  row.output.textContent = event.output || "";
  row.preview.textContent = summarize(event.output || "");
  bumpContextEstimate(event.output || "", 0);
}

function showToolError(event) {
  const row = state.toolRows.get(event.id || event.name) || createDetails(`Tool · ${event.name}`, "error", "tool");
  row.status.textContent = "error";
  row.details.classList.add("failed");
  row.output.textContent = event.error || "";
}

function createDetails(titleText, statusText, kind = "event") {
  const details = document.createElement("details");
  details.className = `event-row ${kind}-event`;
  const summary = document.createElement("summary");
  const icon = eventIcon(kind);
  const title = document.createElement("span");
  title.className = "event-title";
  title.textContent = titleText;
  const status = document.createElement("span");
  status.className = "event-status";
  status.textContent = statusText;
  const preview = document.createElement("code");
  preview.className = "event-preview";
  const output = document.createElement("pre");
  output.className = "event-output";
  summary.append(icon, title, status, preview);
  details.append(summary, output);
  els.chatHistory.appendChild(details);
  scrollToBottom();
  return { details, status, preview, output };
}

function eventIcon(kind) {
  const meta = kind === "tool"
    ? { text: "T", title: "Tool event", className: "tool-icon" }
    : kind === "reasoning"
      ? { text: "R", title: "Reasoning event", className: "reasoning-icon" }
      : { text: "i", title: "Runtime event", className: "system-icon" };
  const icon = document.createElement("span");
  icon.className = `message-icon event-icon ${meta.className}`;
  icon.textContent = meta.text;
  icon.title = meta.title;
  icon.setAttribute("aria-label", meta.title);
  return icon;
}

function showPermission(event) {
  els.permissionDock.hidden = false;
  els.permissionDock.innerHTML = "";
  const body = document.createElement("div");
  body.className = "permission-text";
  const title = document.createElement("strong");
  title.textContent = `Permission required: ${event.name}`;
  const meta = document.createElement("span");
  meta.textContent = `${event.risk || "unknown"} · ${event.reason || ""}`;
  body.append(title, meta);
  const actions = document.createElement("div");
  actions.className = "permission-actions";
  const allow = document.createElement("button");
  allow.textContent = "Allow";
  allow.addEventListener("click", () => submitPermission(event.request_id, "allow"));
  const deny = document.createElement("button");
  deny.textContent = "Deny";
  deny.addEventListener("click", () => submitPermission(event.request_id, "deny"));
  actions.append(allow, deny);
  els.permissionDock.append(body, actions);
}

async function submitPermission(requestId, decision) {
  await apiCall("submit_permission", requestId, decision);
}

function closePermission() {
  els.permissionDock.hidden = true;
  els.permissionDock.innerHTML = "";
}

function renderActivePermission() {
  const pending = state.pendingPermissions.get(state.currentSessionId);
  if (pending) {
    updateRunStage("review", "active", `Permission: ${pending.name}`);
    showPermission(pending);
  } else {
    closePermission();
  }
}

function renderChanges(changes) {
  const files = changes.files || [];
  els.fileTree.innerHTML = "";
  if (!files.length) {
    els.fileTree.innerHTML = `<li class="empty">Open a project to list files</li>`;
    els.diffFile.textContent = "Workspace Preview";
    els.diffCount.textContent = changes.project_path ? "Clean working tree" : "Chat mode";
    renderDiffText(changes.project_path ? "No git changes in this project." : "Open a project to review git changes.");
    return;
  }
  for (const file of files) {
    addFileRow(file);
  }
}

function addFileRow(file) {
  const item = document.createElement("li");
  item.innerHTML = `${escapeHtml(file.file)} <b>${file.additions || file.deletions ? "M" : ""}</b>`;
  item.addEventListener("click", () => loadDiff(file.file));
  els.fileTree.appendChild(item);
}

function toolCallKey(event) {
  return `${event.session_id || ""}:${event.task_id || ""}:${event.id || ""}`;
}

function rememberMemoryToolCall(event) {
  const input = normalizeToolInput(event.input);
  state.pendingMemoryToolCalls.set(toolCallKey(event), {
    session_id: event.session_id,
    task_id: event.task_id,
    scope: input.scope || "auto",
    file: input.file || "",
    operation: input.operation || "append",
    content: input.content || "",
  });
}

function addKnowledgeUpdateFromMemoryTool(event) {
  const pending = state.pendingMemoryToolCalls.get(toolCallKey(event));
  state.pendingMemoryToolCalls.delete(toolCallKey(event));
  if (!pending || !pending.content) return;
  if (String(event.output || "").includes("changed=False")) return;
  addKnowledgeUpdate({
    session_id: event.session_id || pending.session_id,
    task_id: event.task_id || pending.task_id,
    scope: pending.scope,
    file: pending.file,
    operation: pending.operation,
    status: "applied",
    content: pending.content,
    timestamp: event.timestamp,
  });
  if (isCurrentSessionEvent(event)) void refreshKnowledgePanel();
}

function normalizeToolInput(input) {
  if (!input) return {};
  if (typeof input === "object") return input;
  try {
    const parsed = JSON.parse(input);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function addKnowledgeUpdate(event) {
  const sessionId = event.session_id || state.currentSessionId;
  if (!sessionId) return;
  const updates = state.knowledgeUpdates.get(sessionId) || [];
  updates.push({
    scope: event.scope || "auto",
    file: event.file || "knowledge.md",
    operation: event.operation || "append",
    status: event.status || "applied",
    content: event.content || "",
    reason: event.reason || "",
    timestamp: event.timestamp || new Date().toISOString(),
  });
  state.knowledgeUpdates.set(sessionId, updates);
}

function setSessionKnowledgeUpdates(sessionId, updates) {
  if (!sessionId) return;
  const existing = state.knowledgeUpdates.get(sessionId) || [];
  const merged = [...existing];
  const seen = new Set(existing.map(knowledgeUpdateKey));
  for (const update of updates || []) {
    const normalized = {
      session_id: update.session_id || sessionId,
      task_id: update.task_id || "",
      scope: update.scope || "auto",
      file: update.file || "knowledge.md",
      operation: update.operation || "append",
      status: update.status || "applied",
      content: update.content || "",
      reason: update.reason || "",
      timestamp: update.timestamp || "",
    };
    const key = knowledgeUpdateKey(normalized);
    if (seen.has(key)) continue;
    seen.add(key);
    merged.push(normalized);
  }
  state.knowledgeUpdates.set(sessionId, merged);
}

function knowledgeUpdateKey(update) {
  return [
    update.task_id || "",
    update.scope || "",
    update.file || "",
    update.operation || "",
    update.status || "",
    update.content || "",
    update.reason || "",
    update.timestamp || "",
  ].join("\u001f");
}

function renderKnowledgePanel() {
  renderKnowledgeViewButtons();
  if (state.knowledgeView === "project") {
    renderScopeKnowledgePanel();
    return;
  }
  renderSessionKnowledgePanel();
}

function renderKnowledgeViewButtons() {
  for (const button of els.knowledgeViewButtons) {
    const selected = button.dataset.knowledgeView === state.knowledgeView;
    button.classList.toggle("selected", selected);
    button.setAttribute("aria-pressed", selected ? "true" : "false");
  }
}

async function refreshKnowledgePanel() {
  renderKnowledgeViewButtons();
  if (state.knowledgeView !== "project") {
    renderSessionKnowledgePanel();
    return;
  }
  await loadScopeKnowledge();
}

function renderSessionKnowledgePanel() {
  const updates = state.knowledgeUpdates.get(state.currentSessionId) || [];
  const grouped = new Map();
  for (const update of updates) {
    const fileKey = `${update.scope || "auto"}/${update.file || "knowledge.md"}`;
    if (!grouped.has(fileKey)) grouped.set(fileKey, []);
    grouped.get(fileKey).push(update);
  }
  els.knowledgeSummary.textContent = `${grouped.size} ${grouped.size === 1 ? "file" : "files"}`;
  els.knowledgeList.innerHTML = "";
  if (!updates.length) {
    els.knowledgeList.innerHTML = `<div class="empty">No knowledge learned in this session</div>`;
    return;
  }
  for (const [file, fileUpdates] of grouped.entries()) {
    const collapsedKey = `session:${file}`;
    const collapsed = state.collapsedKnowledgeFiles.has(collapsedKey);
    const list = document.createElement("ul");
    if (collapsed) list.hidden = true;
    for (const update of fileUpdates) {
      const status = update.status === "error" ? "error" : update.operation || "append";
      const content = update.content || update.reason || "Knowledge update recorded, but this older event did not persist the content.";
      const item = document.createElement("li");
      const meta = document.createElement("small");
      meta.textContent = status;
      const paragraph = document.createElement("p");
      paragraph.textContent = content;
      item.append(meta, paragraph);
      list.appendChild(item);
    }
    els.knowledgeList.appendChild(createKnowledgeFileSection({
      key: collapsedKey,
      title: file,
      badge: String(fileUpdates.length),
      collapsed,
      body: list,
    }));
  }
}

async function loadScopeKnowledge() {
  const projectPath = state.projectPath || "";
  state.scopeKnowledge = { ...state.scopeKnowledge, projectPath, loading: true, error: "" };
  renderScopeKnowledgePanel();
  const data = await apiCall("get_knowledge", projectPath);
  if (!data.ok) {
    state.scopeKnowledge = { projectPath, loading: false, files: [], error: data.error || "Failed to load knowledge" };
    renderScopeKnowledgePanel();
    return;
  }
  state.scopeKnowledge = { projectPath, loading: false, files: data.files || [], error: "" };
  renderScopeKnowledgePanel();
}

function renderScopeKnowledgePanel() {
  const snapshot = state.scopeKnowledge;
  els.knowledgeSummary.textContent = `${(snapshot.files || []).length} ${(snapshot.files || []).length === 1 ? "file" : "files"}`;
  els.knowledgeList.innerHTML = "";
  if (snapshot.loading) {
    els.knowledgeList.innerHTML = `<div class="empty">Loading scope knowledge...</div>`;
    return;
  }
  if (snapshot.error) {
    els.knowledgeList.innerHTML = `<div class="empty">${escapeHtml(snapshot.error)}</div>`;
    return;
  }
  if (!snapshot.files.length) {
    els.knowledgeList.innerHTML = `<div class="empty">No scope knowledge files</div>`;
    return;
  }
  for (const file of snapshot.files) {
    const fileLabel = file.relative_path || file.file || "knowledge.md";
    const collapsedKey = `scope:${fileLabel}`;
    const collapsed = state.collapsedKnowledgeFiles.has(collapsedKey);
    const content = file.content || "No knowledge in this file yet.";
    const body = document.createElement("div");
    body.className = "knowledge-full-content";
    body.textContent = content;
    if (collapsed) body.hidden = true;
    els.knowledgeList.appendChild(createKnowledgeFileSection({
      key: collapsedKey,
      title: fileLabel,
      badge: file.scope || "",
      collapsed,
      body,
    }));
  }
}

function createKnowledgeFileSection({ key, title, badge, collapsed, body }) {
  const section = document.createElement("div");
  section.className = "knowledge-file";
  section.classList.toggle("collapsed", collapsed);
  const head = document.createElement("div");
  head.className = "knowledge-file-head";
  head.setAttribute("role", "button");
  head.setAttribute("tabindex", "0");
  head.setAttribute("aria-expanded", collapsed ? "false" : "true");
  head.textContent = `${collapsed ? "▸" : "▾"} ${title}${badge ? `  ${badge}` : ""}`;
  head.title = `${title}${badge ? ` (${badge})` : ""}`;
  head.addEventListener("click", () => toggleKnowledgeFile(key));
  head.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    toggleKnowledgeFile(key);
  });
  body.classList.add("knowledge-file-body");
  body.hidden = collapsed;
  section.append(head, body);
  return section;
}

function toggleKnowledgeFile(key) {
  if (state.collapsedKnowledgeFiles.has(key)) {
    state.collapsedKnowledgeFiles.delete(key);
  } else {
    state.collapsedKnowledgeFiles.add(key);
  }
  renderKnowledgePanel();
}

async function loadDiff(file) {
  const data = await apiCall("get_diff", state.projectPath, file);
  els.diffFile.textContent = file;
  els.diffCount.textContent = data.ok ? "Diff view" : "Diff failed";
  renderDiffText(data.ok ? data.diff || "No diff." : data.error || "Diff failed");
}

function renderDiffText(diffText) {
  const rows = parseUnifiedDiff(diffText);
  if (!rows.length) {
    els.diffView.textContent = diffText || "No diff.";
    return;
  }
  els.diffView.innerHTML = "";
  const table = document.createElement("div");
  table.className = "split-diff";
  table.appendChild(diffHeader("Before"));
  table.appendChild(diffHeader("After"));
  for (const row of rows) {
    table.appendChild(diffCell(row, "old"));
    table.appendChild(diffCell(row, "new"));
  }
  els.diffView.appendChild(table);
}

function diffHeader(text) {
  const header = document.createElement("div");
  header.className = "split-diff-header";
  header.textContent = text;
  return header;
}

function diffCell(row, side) {
  const cell = document.createElement("div");
  const line = side === "old" ? row.oldLine : row.newLine;
  const text = side === "old" ? row.oldText : row.newText;
  cell.className = `diff-cell ${row.kind} ${side}`;
  const number = document.createElement("span");
  number.className = "diff-line-number";
  number.textContent = line ? String(line) : "";
  const code = document.createElement("code");
  code.textContent = text || "";
  cell.append(number, code);
  return cell;
}

function parseUnifiedDiff(diffText) {
  if (!diffText || !diffText.includes("@@")) return [];
  const rows = [];
  let oldLine = 0;
  let newLine = 0;
  let pendingDeletes = [];
  for (const line of diffText.split("\n")) {
    if (line.startsWith("@@")) {
      const match = /@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/.exec(line);
      if (match) {
        oldLine = Number(match[1]);
        newLine = Number(match[2]);
      }
      flushDeletes();
      rows.push({ kind: "hunk", oldLine: "", newLine: "", oldText: line, newText: line });
      continue;
    }
    if (line.startsWith("diff --git") || line.startsWith("index ") || line.startsWith("--- ") || line.startsWith("+++ ") || line.startsWith("new file mode")) {
      continue;
    }
    if (line.startsWith("-")) {
      pendingDeletes.push({ oldLine: oldLine++, oldText: line.slice(1) });
      continue;
    }
    if (line.startsWith("+")) {
      if (pendingDeletes.length) {
        const deleted = pendingDeletes.shift();
        rows.push({
          kind: "changed",
          oldLine: deleted.oldLine,
          newLine: newLine++,
          oldText: deleted.oldText,
          newText: line.slice(1),
        });
      } else {
        rows.push({ kind: "added", oldLine: "", newLine: newLine++, oldText: "", newText: line.slice(1) });
      }
      continue;
    }
    flushDeletes();
    if (line.startsWith(" ")) {
      rows.push({ kind: "context", oldLine: oldLine++, newLine: newLine++, oldText: line.slice(1), newText: line.slice(1) });
    } else if (line.trim()) {
      rows.push({ kind: "meta", oldLine: "", newLine: "", oldText: line, newText: line });
    }
  }
  flushDeletes();
  return rows;

  function flushDeletes() {
    for (const deleted of pendingDeletes) {
      rows.push({ kind: "removed", oldLine: deleted.oldLine, newLine: "", oldText: deleted.oldText, newText: "" });
    }
    pendingDeletes = [];
  }
}

async function refreshContext() {
  try {
    renderContext(await apiCall("get_context_usage"));
  } catch (error) {
    console.warn(error);
  }
}

function renderContext(context) {
  const used = Number(context.used_tokens || 0);
  const total = Number(context.context_window || 128000);
  const percent = Math.max(0, Math.min(100, Number(context.percent || 0)));
  state.context = { used_tokens: used, context_window: total, percent, estimated: Boolean(context.estimated) };
  els.contextPercent.textContent = `${percent}%`;
  const label = formatTokens(used, total);
  const small = els.contextRing.querySelector("small");
  if (small) small.textContent = `${label}${state.context.estimated ? " est." : ""}`;
  els.contextRing.style.setProperty("--context-percent", `${percent}%`);
  els.contextRing.classList.remove("context-calm", "context-warning", "context-critical");
  const mood = contextMood(percent);
  els.contextRing.classList.add(mood);
  renderContextSpirit(mood);
}

function contextMood(percent) {
  if (percent >= 90) return "context-critical";
  if (percent >= 40) return "context-warning";
  return "context-calm";
}

function renderContextSpirit(mood) {
  const sources = {
    "context-calm": "./assets/bamboo_context_spirit_calm.png",
    "context-warning": "./assets/bamboo_context_spirit_warning.png",
    "context-critical": "./assets/bamboo_context_spirit_critical.png",
  };
  if (els.contextSpirit) els.contextSpirit.src = sources[mood] || sources["context-calm"];
}

function renderModels(models) {
  const options = Array.isArray(models.options) ? models.options : [];
  state.models = {
    selected: models.selected || "",
    configured: models.configured || "",
    options,
  };
  els.modelSelect.innerHTML = "";
  for (const option of options) {
    const item = document.createElement("option");
    item.value = option.name || "";
    item.textContent = option.name || "";
    const type = option.model_type ? ` · ${option.model_type}` : "";
    const provider = option.provider ? `${option.provider}` : "";
    const actualModel = option.model && option.model !== option.name ? ` · ${option.model}` : "";
    item.title = `${provider}${actualModel}${type}`.replace(/^ · /, "");
    if (option.name === state.models.configured) item.textContent = `${item.textContent} (default)`;
    els.modelSelect.appendChild(item);
  }
  setSelectedModel(state.models.selected || state.models.configured);
  updateContextWindowForSelectedModel();
}

function setSelectedModel(modelName) {
  if (!modelName) return;
  const existing = Array.from(els.modelSelect.options).some((option) => option.value === modelName);
  if (existing) {
    els.modelSelect.value = modelName;
    state.models.selected = modelName;
  }
}

function renderPermissionState(permissionState, options = {}) {
  const stored = localStorage.getItem("bamboo.app.permissionMode");
  const mode = options.preferStored && stored ? stored : permissionStateToMode(permissionState);
  state.permissionMode = mode;
  if (els.permissionMode) els.permissionMode.value = mode;
  localStorage.setItem("bamboo.app.permissionMode", mode);
}

function setSessionMessagesPath(path) {
  state.sessionMessagesPath = path || "";
  if (!els.copySessionPath) return;
  els.copySessionPath.disabled = !state.sessionMessagesPath;
  els.copySessionPath.title = state.sessionMessagesPath
    ? `Copy ${state.sessionMessagesPath}`
    : "Session messages path is not available yet";
}

async function copySessionMessagesPath() {
  if (!state.sessionMessagesPath) return;
  const value = state.sessionMessagesPath;
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(value);
    } else {
      fallbackCopyText(value);
    }
    showCopySessionPathStatus("Copied");
  } catch (error) {
    fallbackCopyText(value);
    showCopySessionPathStatus("Copied");
  }
}

function fallbackCopyText(value) {
  const area = document.createElement("textarea");
  area.value = value;
  area.setAttribute("readonly", "");
  area.style.position = "fixed";
  area.style.opacity = "0";
  document.body.appendChild(area);
  area.select();
  document.execCommand("copy");
  area.remove();
}

function showCopySessionPathStatus(text) {
  if (!els.copySessionPath) return;
  const original = els.copySessionPath.textContent;
  els.copySessionPath.textContent = text;
  window.setTimeout(() => {
    els.copySessionPath.textContent = original || "Copy log path";
  }, 1200);
}

function permissionStateToMode(permissionState) {
  if (!permissionState || typeof permissionState !== "object") return state.permissionMode || "default";
  const permission = String(permissionState.permission || "default").toLowerCase();
  if (permissionState.yes_all && ["", "default", "auto", "strict"].includes(permission)) return "auto-approve";
  if (["read-only", "readonly", "deny"].includes(permission)) return "read-only";
  if (["bypass", "yolo", "full-auto", "dangerously-skip-permissions"].includes(permission)) return "bypass";
  return "default";
}

function updateContextWindowForSelectedModel() {
  const selected = state.models.options.find((option) => option.name === els.modelSelect.value);
  if (!selected?.context_window) return;
  renderContext({
    used_tokens: state.context.used_tokens || 0,
    context_window: selected.context_window,
    percent: Math.round(((state.context.used_tokens || 0) / selected.context_window) * 100),
    estimated: state.context.estimated,
  });
}

function bumpContextEstimate(text, imageCount = 0) {
  const total = state.context.context_window || 128000;
  const added = estimateTokens(text) + imageCount * 1024;
  if (!added) return;
  const used = Math.min(total, (state.context.used_tokens || 0) + added);
  renderContext({
    used_tokens: used,
    context_window: total,
    percent: Math.round((used / total) * 100),
    estimated: true,
  });
}

function estimateTokens(text) {
  if (!text) return 0;
  return Math.max(1, Math.ceil(new Blob([String(text)]).size / 4));
}

function formatTokens(used, total) {
  return `${compactNumber(used)} / ${compactNumber(total)} tokens`;
}

function compactNumber(value) {
  if (value >= 1000000) return `${(value / 1000000).toFixed(1)}m`;
  if (value >= 1000) return `${(value / 1000).toFixed(value >= 10000 ? 0 : 1)}k`;
  return `${value}`;
}

function setStatus(status, text = "") {
  const busy = status !== "idle";
  els.statusPill.textContent = busy ? text || status : "Idle";
  els.statusPill.classList.toggle("busy", busy);
  els.statusPill.classList.toggle("idle", !busy);
  els.runBadge.textContent = busy ? "Executing" : "Idle";
  els.runBadge.classList.toggle("busy", busy);
  els.sendButton.disabled = busy;
  els.stopButton.hidden = !busy;
  els.stopButton.disabled = !busy || state.stopRequested;
}

function updateActiveRunStatus() {
  const activeRunning = state.currentSessionId && state.runningSessions.has(state.currentSessionId);
  if (activeRunning) {
    setStatus("running", "Executing");
    if (!state.startedAt) {
      els.runTimer.textContent = "Running";
    }
  } else {
    setStatus("idle");
    stopTimer();
  }
  renderSessions(state.sessions);
}

function startTimer() {
  stopTimer();
  state.timer = setInterval(() => {
    const elapsed = Math.max(0, Date.now() - state.startedAt);
    els.runTimer.textContent = `${Math.floor(elapsed / 60000)}m ${Math.floor((elapsed % 60000) / 1000)}s`;
  }, 1000);
}

function stopTimer() {
  if (state.timer) clearInterval(state.timer);
  state.timer = null;
  els.runTimer.textContent = "Ready";
}

function summarize(text) {
  const value = String(text || "").replace(/\s+/g, " ").trim();
  return value.length > 96 ? `${value.slice(0, 93)}...` : value;
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

function setActiveView(view) {
  state.activeView = view;
  els.tabs.forEach((tab) => tab.classList.toggle("selected", tab.dataset.view === view));
  els.diffViewPane.hidden = view !== "diff";
  els.chatViewPane.hidden = view !== "chat";
  els.logsViewPane.hidden = view !== "logs";
  if (view === "chat") {
    els.chatViewPane.appendChild(els.chatHistory);
    els.chatTitle.textContent = "Chat";
  } else {
    els.diffChatSlot.appendChild(els.chatHistory);
    els.chatTitle.textContent = view === "logs" ? "Logs" : "Review Diff";
  }
  els.chatHistory.classList.toggle("chat-full", view === "chat");
  scrollToBottom();
}

function resetRunTimeline() {
  setTimelineState("planning", "idle", "Analyze request");
  setTimelineState("executing", "idle", "Waiting for task");
  setTimelineState("review", "idle", "Pending changes");
}

function updateRunStage(stage, status, detail) {
  const order = ["planning", "executing", "review"];
  const index = order.indexOf(stage);
  if (index === -1) return;
  order.forEach((name, itemIndex) => {
    if (itemIndex < index && status !== "idle") setTimelineState(name, "done");
    if (itemIndex === index) setTimelineState(name, status, detail);
  });
}

function setTimelineState(stage, status, detail = "") {
  const index = { planning: 0, executing: 1, review: 2 }[stage];
  const item = els.timelineItems[index];
  if (!item) return;
  item.classList.remove("active", "done", "error");
  if (status && status !== "idle") item.classList.add(status);
  if (detail) {
    const small = item.querySelector("small");
    if (small) small.textContent = detail;
  }
}

function addLog(event) {
  const entry = {
    time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
    type: event.type || "event",
    summary: logSummary(event),
    payload: event,
  };
  state.logs.push(entry);
  if (state.logs.length > 400) state.logs.shift();
  renderLogs();
}

function renderLogs() {
  els.logList.innerHTML = "";
  const visibleLogs = state.logs.filter((item) => !item.payload.session_id || item.payload.session_id === state.currentSessionId);
  if (!visibleLogs.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "No logs for this session";
    els.logList.appendChild(empty);
    return;
  }
  for (const item of visibleLogs.slice().reverse()) {
    const details = document.createElement("details");
    details.className = "log-row";
    const summary = document.createElement("summary");
    summary.innerHTML = `<time>${escapeHtml(item.time)}</time><strong>${escapeHtml(item.type)}</strong><span>${escapeHtml(item.summary)}</span>`;
    details.appendChild(summary);
    if (item.type === "llm_request" && item.payload.full_prompt) {
      const promptTitle = document.createElement("strong");
      promptTitle.className = "log-section-title";
      promptTitle.textContent = "Full prompt";
      const prompt = document.createElement("pre");
      prompt.className = "log-prompt";
      prompt.textContent = item.payload.full_prompt || "";
      details.append(promptTitle, prompt);
    }
    const pre = document.createElement("pre");
    pre.textContent = JSON.stringify(item.payload, null, 2);
    details.appendChild(pre);
    els.logList.appendChild(details);
  }
}

function logSummary(event) {
  if (event.type === "llm_request") {
    return `${event.role || "main"} · ${event.model_name || event.provider || "model"} · ${event.input_chars || 0} chars`;
  }
  if (event.type === "llm_response") {
    return event.success === false
      ? `${event.role || "main"} failed · ${event.error_type || "error"}`
      : `${event.role || "main"} done · ${event.output_chars || 0} chars`;
  }
  if (event.type === "tool_call") return `${event.name || "tool"} started`;
  if (event.type === "tool_result") return `${event.name || "tool"} success`;
  if (event.type === "tool_error") return `${event.name || "tool"} error`;
  if (event.type === "text_delta") return summarize(event.text || "");
  if (event.type === "reasoning_delta") return summarize(event.text || "");
  if (event.type === "agent_status") return event.reason || event.status || "";
  if (event.type === "step_finish") return event.summary || "";
  if (event.type === "permission_request") return `${event.name || "tool"} needs approval`;
  return event.message || event.title || event.error || "";
}

function isComposingInput(event) {
  return Boolean(event.isComposing || event.keyCode === 229);
}

els.applyProject.addEventListener("click", async () => {
  await applyProjectPath();
});
for (const button of els.sessionFilterButtons) {
  button.addEventListener("click", () => {
    state.sessionFilter = button.dataset.sessionFilter || "user";
    localStorage.setItem("bamboo.app.sessionFilter", state.sessionFilter);
    renderSessions(state.sessions);
  });
}
for (const button of els.knowledgeViewButtons) {
  button.addEventListener("click", () => {
    state.knowledgeView = button.dataset.knowledgeView || "session";
    localStorage.setItem("bamboo.app.knowledgeView", state.knowledgeView);
    void refreshKnowledgePanel();
  });
}
els.newSession.addEventListener("click", newSession);
els.sendButton.addEventListener("click", sendMessage);
els.stopButton.addEventListener("click", stopCurrentTask);
els.themeToggle.addEventListener("click", toggleTheme);
els.projectMenuToggle.addEventListener("click", (event) => {
  event.preventDefault();
  event.stopPropagation();
  toggleProjectMenu();
});
els.projectMenu.addEventListener("click", (event) => {
  event.stopPropagation();
});
els.projectPath.addEventListener("change", async () => {
  await applyProjectPath();
});
els.projectPath.addEventListener("keydown", async (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    closeProjectMenu();
    await applyProjectPath();
  }
  if (event.key === "ArrowDown") {
    event.preventDefault();
    openProjectMenu();
  }
  if (event.key === "Escape") {
    closeProjectMenu();
  }
});
document.addEventListener("click", (event) => {
  const target = event.target instanceof Element ? event.target : null;
  if (target?.closest?.(".project-picker")) return;
  closeProjectMenu();
});
els.modelSelect.addEventListener("change", () => {
  state.models.selected = els.modelSelect.value;
  updateContextWindowForSelectedModel();
});
if (els.permissionMode) {
  els.permissionMode.value = state.permissionMode;
  els.permissionMode.addEventListener("change", () => {
    state.permissionMode = els.permissionMode.value || "default";
    localStorage.setItem("bamboo.app.permissionMode", state.permissionMode);
  });
}
if (els.copySessionPath) {
  els.copySessionPath.addEventListener("click", (event) => {
    event.preventDefault();
    void copySessionMessagesPath();
  });
}
els.messageInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !isComposingInput(event)) {
    event.preventDefault();
    sendMessage();
  }
});
els.tabs.forEach((tab) => tab.addEventListener("click", () => setActiveView(tab.dataset.view)));

async function stopCurrentTask() {
  if (state.stopRequested) return;
  state.stopRequested = true;
  setStatus("running", "Stopping");
  try {
    const result = await apiCall("stop_current_task");
    if (!result.ok) throw new Error(result.error || "stop failed");
  } catch (error) {
    state.stopRequested = false;
    setStatus("running", "Executing");
    showSystem(`停止任务失败：${error.message || error}`, "error");
  }
}
window.addEventListener("pywebviewready", () => {
  init().catch((error) => {
    console.error(error);
    showSystem(String(error), "error");
    setStatus("idle");
  });
});
