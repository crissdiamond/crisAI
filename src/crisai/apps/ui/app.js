const tabs = document.getElementById("tabs");
const tabContent = document.getElementById("tabContent");
const decision = document.getElementById("decision");
const runBtn = document.getElementById("runBtn");
const sessionSelect = document.getElementById("sessionSelect");
const createSessionBtn = document.getElementById("createSessionBtn");
const newSessionNameInput = document.getElementById("newSessionName");
const currentSessionText = document.getElementById("currentSessionText");
const sessionHistory = document.getElementById("sessionHistory");
const messageInput = document.getElementById("message");
const uiStatus = document.getElementById("uiStatus");

let stageData = [];
let sessions = [];
let currentSession = "default";
let currentJobId = null;
let pollingTimer = null;
let activeFlowKey = null;

function setUiStatus(text) {
  if (uiStatus) uiStatus.textContent = `UI status: ${text}`;
}

function handleUiError(error) {
  const message = String(error);
  if (tabContent) tabContent.textContent = message;
  setUiStatus(`error - ${message}`);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function markdownToSafeHtml(markdown) {
  let html = String(markdown || "");
  // Markdown links: visible text is only [label]; URL lives only in href.
  const linkAnchors = [];
  html = html.replace(/\[([^\]]*)\]\(([^)\s]+)\)/g, (full, label, url) => {
    const u = String(url).trim();
    if (!/^(https?:\/\/|file:\/\/)/i.test(u)) return full;
    const i = linkAnchors.length;
    linkAnchors.push(
      '<a href="' +
        escapeHtml(u) +
        '" target="_blank" rel="noopener noreferrer">' +
        escapeHtml(String(label)) +
        "</a>"
    );
    return "XLINK" + i + "XEND";
  });
  html = escapeHtml(html);
  linkAnchors.forEach((anchor, i) => {
    html = html.split("XLINK" + i + "XEND").join(anchor);
  });
  html = html.replace(/```([\s\S]*?)```/g, (_match, code) => `<pre><code>${code}</code></pre>`);
  html = html.replace(/^### (.*)$/gm, "<h4>$1</h4>");
  html = html.replace(/^## (.*)$/gm, "<h3>$1</h3>");
  html = html.replace(/^# (.*)$/gm, "<h2>$1</h2>");
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/\n/g, "<br>");
  return html;
}

function renderTabs(records) {
  tabs.innerHTML = "";
  stageData = records || [];
  if (!stageData.length) {
    tabContent.textContent = "No stage output captured for this run.";
    return;
  }

  stageData.forEach((record, index) => {
    const btn = document.createElement("button");
    const colorIndex = index % 7;
    btn.className = "tab-btn tab-color-" + colorIndex;
    const labelAgent = record.agent_id || "system";
    btn.textContent = `${index + 1}. ${labelAgent}`;
    btn.dataset.colorIndex = String(colorIndex);
    btn.onclick = () => selectTab(index);
    tabs.appendChild(btn);
  });

  const activeIndex = stageData.findIndex((item) => (item.key || item.agent_id) === activeFlowKey);
  selectTab(activeIndex >= 0 ? activeIndex : 0);
}

function selectTab(index) {
  Array.from(tabs.children).forEach((child, idx) => child.classList.toggle("active", idx === index));
  const record = stageData[index];
  if (!record) return;
  activeFlowKey = record.key || record.agent_id;

  const selectedTab = tabs.children[index];
  const colorIndex = selectedTab && selectedTab.dataset ? Number(selectedTab.dataset.colorIndex || "0") : 0;
  tabContent.className = "tab-content-panel flow-shade-" + (colorIndex % 7);
  const header = `**${record.agent_id || "system"}**  \n\`${record.event_type}\` - \`${record.stage}\`\n\n`;
  tabContent.innerHTML = markdownToSafeHtml(header + (record.content || ""));
}

function renderSessionSelector() {
  sessionSelect.innerHTML = "";
  sessions.forEach((sessionName) => {
    const option = document.createElement("option");
    option.value = sessionName;
    option.textContent = sessionName;
    option.selected = sessionName === currentSession;
    sessionSelect.appendChild(option);
  });
  currentSessionText.textContent = `Current session: ${currentSession}`;
}

function renderSessionHistory(items) {
  if (!items || !items.length) {
    sessionHistory.textContent = "No history for this session yet.";
    return;
  }
  const entryHtml = items.map((entry, index) => {
    const role = entry.role === "assistant" ? "assistant" : "user";
    const roleLabel = role === "assistant" ? "ASSISTANT" : "USER";
    const contentHtml = markdownToSafeHtml(entry.content || "");
    return `<div class="history-entry ${role}"><div class="history-meta">#${index + 1} [${roleLabel}]</div><div class="history-content">${contentHtml}</div></div>`;
  });
  sessionHistory.innerHTML = entryHtml.join("");
}

function buildPlaceholderFlowTabs(expectedTabs) {
  return (expectedTabs || []).map((tab) => ({
    agent_id: tab.label,
    stage: "PENDING",
    event_type: "pending",
    content: "_Waiting for output..._",
    key: tab.key,
  }));
}

function applyStageUpdates(records, updates, finalOutputText) {
  const byKey = new Map();
  records.forEach((item) => byKey.set(item.key || item.agent_id, item));
  (updates || []).forEach((entry) => {
    const key = entry.key || entry.agent_id;
    byKey.set(key, { ...entry, key });
  });
  if (finalOutputText) {
    byKey.set("final_output", {
      key: "final_output",
      agent_id: "final_output",
      stage: "FINAL_OUTPUT",
      event_type: "workflow_output",
      content: finalOutputText,
    });
  }
  return records.map((item) => byKey.get(item.key || item.agent_id) || item);
}

function isCompletedRecord(record) {
  const isPending = record.event_type === "pending";
  const content = String(record.content || "").trim();
  return !isPending && content.length > 0 && content !== "_Waiting for output..._";
}

function selectProgressKey(records) {
  let furthestKey = null;
  records.forEach((record) => {
    if (isCompletedRecord(record)) {
      furthestKey = record.key || record.agent_id || furthestKey;
    }
  });
  return furthestKey;
}

async function loadSessionMeta() {
  const response = await fetch("/api/sessions");
  const data = await response.json();
  sessions = data.sessions || ["default"];
  currentSession = data.current_session || sessions[0] || "default";
  renderSessionSelector();
  renderSessionHistory(data.history || []);
}

async function switchSession(sessionName) {
  const response = await fetch(`/api/sessions/${encodeURIComponent(sessionName)}`);
  const data = await response.json();
  currentSession = data.current_session;
  if (!sessions.includes(currentSession)) sessions.push(currentSession);
  renderSessionSelector();
  renderSessionHistory(data.history || []);
}

async function createSession() {
  const proposed = newSessionNameInput.value.trim();
  if (!proposed) return;
  const response = await fetch("/api/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session: proposed }),
  });
  const data = await response.json();
  currentSession = data.current_session;
  sessions = data.sessions || sessions;
  renderSessionSelector();
  renderSessionHistory(data.history || []);
  newSessionNameInput.value = "";
}

async function runWorkflow() {
  runBtn.disabled = true;
  runBtn.textContent = "Running...";
  try {
    const payload = {
      message: messageInput.value.trim(),
      mode: document.getElementById("mode").value,
      agent: document.getElementById("agent").value.trim() || "auto",
      review: document.getElementById("review").checked,
      verbose: document.getElementById("verbose").checked,
      session: currentSession,
    };
    if (!payload.message) throw new Error("Please enter a prompt.");

    const response = await fetch("/api/run/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Request failed.");

    decision.textContent = JSON.stringify(data.decision, null, 2);
    currentJobId = data.job_id;
    stageData = buildPlaceholderFlowTabs(data.expected_tabs || []);
    activeFlowKey = stageData.length ? (stageData[0].key || stageData[0].agent_id) : null;
    renderTabs(stageData);
    setUiStatus("running");
    messageInput.value = "";

    if (pollingTimer) clearInterval(pollingTimer);
    pollingTimer = setInterval(async () => {
      if (!currentJobId) return;
      const statusResponse = await fetch(`/api/run/status/${encodeURIComponent(currentJobId)}`);
      const statusData = await statusResponse.json();
      if (!statusResponse.ok) throw new Error(statusData.detail || "Status polling failed.");

      const updates = (statusData.stage_outputs || []).map((entry) => ({ ...entry, key: entry.key || entry.agent_id }));
      stageData = applyStageUpdates(stageData, updates, statusData.final_output || "");
      const progressedKey = selectProgressKey(stageData);
      if (progressedKey) activeFlowKey = progressedKey;
      if (statusData.final_output) activeFlowKey = "final_output";
      renderTabs(stageData);

      if (statusData.status === "completed") {
        clearInterval(pollingTimer);
        pollingTimer = null;
        currentJobId = null;
        renderSessionHistory(statusData.history || []);
        setUiStatus("ready");
      } else if (statusData.status === "failed") {
        clearInterval(pollingTimer);
        pollingTimer = null;
        currentJobId = null;
        throw new Error(statusData.error || "Run failed.");
      }
    }, 1000);
  } catch (error) {
    handleUiError(error);
  } finally {
    runBtn.disabled = false;
    runBtn.textContent = "Run";
  }
}

function initUiBindings() {
  if (!runBtn || !createSessionBtn || !sessionSelect || !tabContent) {
    setUiStatus("missing required elements");
    return;
  }
  runBtn.addEventListener("click", () => { runWorkflow().catch(handleUiError); });
  createSessionBtn.addEventListener("click", () => { createSession().catch(handleUiError); });
  sessionSelect.addEventListener("change", (event) => {
    const selected = event && event.target ? event.target.value : currentSession;
    switchSession(selected).catch(handleUiError);
  });
  setUiStatus("ready");
}

window.addEventListener("error", (event) => handleUiError(event.error || event.message || "Unknown UI error"));

initUiBindings();
if (tabContent) loadSessionMeta().catch(handleUiError);

