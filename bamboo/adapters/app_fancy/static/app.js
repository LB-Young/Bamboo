const state = {
  sessions: [],
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
  stopRequested: false,
};

const els = {
  projectPath: document.getElementById("projectPath"),
  modelSelect: document.getElementById("modelSelect"),
  applyProject: document.getElementById("applyProject"),
  newSession: document.getElementById("newSession"),
  sessionScope: document.getElementById("sessionScope"),
  sessionCount: document.getElementById("sessionCount"),
  sessionList: document.getElementById("sessionList"),
  agentScope: document.getElementById("agentScope"),
  chatTitle: document.getElementById("chatTitle"),
  statusPill: document.getElementById("statusPill"),
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
  changeSummary: document.getElementById("changeSummary"),
  changeList: document.getElementById("changeList"),
  fileTree: document.getElementById("fileTree"),
  sourceList: document.getElementById("sourceList"),
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
  els.projectPath.value = state.projectPath;
  renderScope();
  renderSessions(data.sessions || []);
  renderChanges(data.changes || {});
  renderContext(data.context || {});
  renderModels(data.models || {});
  newSessionView();
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
    item.innerHTML = `<span>${escapeHtml(session.label || session.session_id)}</span><small>${escapeHtml(formatTime(session.updated_at || session.created_at))}</small>`;
    els.sessionList.appendChild(item);
  }
}

async function loadSession(session) {
  const data = await apiCall("load_session", session.record_dir);
  if (!data.ok) return showSystem(data.error || "Load failed", "error");
  state.currentSessionId = data.session_id;
  state.mode = data.mode || "chat";
  state.projectPath = data.project_path || "";
  els.projectPath.value = state.projectPath;
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
}

async function newSession() {
  renderScope();
  const data = await apiCall("new_session", state.projectPath);
  if (!data.ok) return showSystem(data.error || "New session failed", "error");
  state.currentSessionId = data.session_id;
  renderSessions(data.sessions || []);
  renderChanges(data.changes || {});
  renderContext(data.context || {});
  renderModels(data.models || {});
  newSessionView();
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
  appendMessage("user", message);
  bumpContextEstimate(message, 0);
  els.messageInput.value = "";
  resetTurnState();
  resetRunTimeline();
  state.stopRequested = false;
  setStatus("running", "Executing");
  els.runTitle.textContent = message || "Image task";
  updateRunStage("planning", "active", "Preparing request");
  const result = await apiCall("send_message", message, state.projectPath, [], els.modelSelect.value || "");
  if (!result.ok) {
    showSystem(result.error || "Send failed", "error");
    setStatus("idle");
  } else if (result.model) {
    setSelectedModel(result.model);
  }
}

function handleEvent(event) {
  addLog(event);
  if (event.type === "run_start") {
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
    const cancelled = Boolean(event.cancelled || state.stopRequested);
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
  if (event.type === "permission_request") {
    updateRunStage("review", "active", `Permission: ${event.name}`);
    return showPermission(event);
  }
  if (event.type === "permission_result") {
    updateRunStage("review", event.approved ? "done" : "error", event.approved ? "Approved" : "Rejected");
    return closePermission();
  }
  if (event.type === "context_usage") return renderContext(event.context || {});
}

function appendMessage(role, text) {
  const article = document.createElement("article");
  article.className = `message ${role}`;
  const body = document.createElement("div");
  body.className = "message-body";
  const copy = document.createElement("button");
  copy.className = "copy-message";
  copy.type = "button";
  copy.textContent = "Copy";
  copy.addEventListener("click", () => copyMessage(article, copy));
  article.append(body, copy);
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
  return `<pre><code${language ? ` data-lang="${escapeHtml(language)}"` : ""}>${escapeHtml(code)}</code></pre>`;
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

function renderMermaidBlocks(root) {
  const nodes = Array.from(root.querySelectorAll(".mermaid:not([data-processed])"));
  if (!nodes.length || !window.mermaid?.run) return;
  try {
    window.mermaid.run({ nodes });
  } catch (error) {
    console.warn("mermaid render failed", error);
  }
}

function inlineMarkdown(text) {
  return escapeHtml(text)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>")
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2">$1</a>');
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
  state.toolCount += 1;
  els.toolCount.textContent = `${state.toolCount}`;
  const row = createDetails(`Tool · ${event.name}`, "running");
  row.output.textContent = JSON.stringify(event.input || {}, null, 2);
  state.toolRows.set(event.id || event.name, row);
}

function showToolResult(event) {
  const row = state.toolRows.get(event.id || event.name) || createDetails(`Tool · ${event.name}`, "done");
  row.status.textContent = "done";
  row.output.textContent = event.output || "";
  row.preview.textContent = summarize(event.output || "");
  bumpContextEstimate(event.output || "", 0);
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

function renderChanges(changes) {
  const files = changes.files || [];
  els.changeSummary.textContent = `+${changes.additions || 0} -${changes.deletions || 0}`;
  els.fileTree.innerHTML = "";
  els.changeList.innerHTML = "";
  els.sourceList.innerHTML = "";
  if (!files.length) {
    els.changeList.innerHTML = `<div class="empty">No changes</div>`;
    els.sourceList.innerHTML = `<div class="empty">No sources</div>`;
    els.fileTree.innerHTML = `<li class="empty">Open a project to list files</li>`;
    els.diffFile.textContent = "Workspace Preview";
    els.diffCount.textContent = changes.project_path ? "Clean working tree" : "Chat mode";
    renderDiffText(changes.project_path ? "No git changes in this project." : "Open a project to review git changes.");
    return;
  }
  for (const file of files) {
    addFileRow(file);
    addChangeRow(file);
    addSourceRow(file);
  }
}

function addFileRow(file) {
  const item = document.createElement("li");
  item.innerHTML = `${escapeHtml(file.file)} <b>${file.additions || file.deletions ? "M" : ""}</b>`;
  item.addEventListener("click", () => loadDiff(file.file));
  els.fileTree.appendChild(item);
}

function addChangeRow(file) {
  const row = document.createElement("button");
  row.type = "button";
  row.className = "change-row";
  row.innerHTML = `<span>${escapeHtml(file.file)}</span><code>+${file.additions} -${file.deletions}</code>`;
  row.addEventListener("click", () => loadDiff(file.file));
  els.changeList.appendChild(row);
}

function addSourceRow(file) {
  const row = document.createElement("button");
  row.type = "button";
  row.className = "source-row";
  row.innerHTML = `<span>${escapeHtml(file.file)}</span>`;
  row.addEventListener("click", () => loadDiff(file.file));
  els.sourceList.appendChild(row);
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
  for (const item of state.logs.slice().reverse()) {
    const details = document.createElement("details");
    details.className = "log-row";
    const summary = document.createElement("summary");
    summary.innerHTML = `<time>${escapeHtml(item.time)}</time><strong>${escapeHtml(item.type)}</strong><span>${escapeHtml(item.summary)}</span>`;
    const pre = document.createElement("pre");
    pre.textContent = JSON.stringify(item.payload, null, 2);
    details.append(summary, pre);
    els.logList.appendChild(details);
  }
}

function logSummary(event) {
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

els.applyProject.addEventListener("click", async () => {
  renderScope();
  await refreshSidebar();
  renderChanges(await apiCall("get_changes", state.projectPath));
});
els.newSession.addEventListener("click", newSession);
els.sendButton.addEventListener("click", sendMessage);
els.stopButton.addEventListener("click", stopCurrentTask);
els.modelSelect.addEventListener("change", () => {
  state.models.selected = els.modelSelect.value;
  updateContextWindowForSelectedModel();
});
els.messageInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
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
document.querySelectorAll("[data-project]").forEach((button) => {
  button.addEventListener("click", async () => {
    els.projectPath.value = button.dataset.project || "";
    await refreshSidebar();
    renderChanges(await apiCall("get_changes", state.projectPath));
  });
});

window.addEventListener("pywebviewready", () => {
  init().catch((error) => {
    console.error(error);
    showSystem(String(error), "error");
    setStatus("idle");
  });
});
