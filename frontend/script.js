const chatList = document.getElementById("chatList");
const agentLog = document.getElementById("agentLog");
const userText = document.getElementById("userText");
const sendBtn = document.getElementById("sendBtn");
const stopBtn = document.getElementById("stopBtn");
const clearBtn = document.getElementById("clearBtn");
const statusEl = document.getElementById("status");
const agentPanel = document.getElementById("agentPanel");
const toggleAgentPanelBtn = document.getElementById("toggleAgentPanel");
const closeAgentPanelBtn = document.getElementById("closeAgentPanel");

let currentAudio = null;
let logRenderToken = 0;

const overlay = document.createElement("div");
overlay.className = "agent-panel-overlay";
document.body.appendChild(overlay);

function getSettings() {
  const defaults = { enableTTS: false, enableWebSearch: true };
  try {
    const saved = JSON.parse(localStorage.getItem("chatbotSettings") || "{}");
    return {
      enableTTS: saved.enableTTS ?? defaults.enableTTS,
      enableWebSearch: saved.enableWebSearch ?? defaults.enableWebSearch
    };
  } catch (err) {
    return defaults;
  }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function renderMarkdown(text) {
  if (!window.marked) return text;
  return marked.parse(text, { breaks: true, gfm: true });
}

function removeWelcomeBlock() {
  const welcome = chatList.querySelector(".welcome-block");
  if (welcome) welcome.remove();
}

function scrollChatToBottom() {
  chatList.scrollTop = chatList.scrollHeight;
}

function autoResizeTextarea() {
  if (!userText) return;
  userText.style.height = "auto";
  userText.style.height = Math.min(userText.scrollHeight, 220) + "px";
}

function createMessageRow(role) {
  const row = document.createElement("div");
  row.className = `message-row ${role === "user" ? "user-row" : "bot-row"}`;
  return row;
}

function addMessage(text, role) {
  if (!chatList) return null;
  removeWelcomeBlock();
  const row = createMessageRow(role);
  const div = document.createElement("div");
  div.className = `message ${role}`;
  if (role === "bot") {
    div.innerHTML = renderMarkdown(text);
  } else {
    div.textContent = text;
  }
  row.appendChild(div);
  chatList.appendChild(row);
  scrollChatToBottom();
  return div;
}

function showChatLoading(message = "Assistant is thinking...") {
  removeWelcomeBlock();
  const row = createMessageRow("bot");
  const div = document.createElement("div");
  div.className = "message bot loading-bubble";
  div.innerHTML = `
    <div class="bubble-loading">
      <span class="spinner"></span>
      <span>${message}</span>
    </div>
  `;
  row.appendChild(div);
  chatList.appendChild(row);
  scrollChatToBottom();
  return row;
}

function removeChatLoading(loadingEl) {
  if (loadingEl && loadingEl.parentNode) {
    loadingEl.parentNode.removeChild(loadingEl);
  }
}

function addAgentLog(agent, message) {
  if (!agentLog) return null;
  const item = document.createElement("div");
  item.className = "log-item";
  const now = new Date().toLocaleTimeString();
  item.innerHTML = `
    <div class="log-agent">${agent}</div>
    <div class="log-message"></div>
    <div class="log-time">${now}</div>
  `;
  item.querySelector(".log-message").textContent = message;
  agentLog.appendChild(item);
  agentLog.scrollTop = agentLog.scrollHeight;
  return item;
}

async function typeAgentLog(agent, message, speed = 14) {
  if (!agentLog) return null;
  const item = document.createElement("div");
  item.className = "log-item";
  const now = new Date().toLocaleTimeString();
  item.innerHTML = `
    <div class="log-agent">${agent}</div>
    <div class="log-message"></div>
    <div class="log-time">${now}</div>
  `;
  agentLog.appendChild(item);
  const msgEl = item.querySelector(".log-message");
  for (let i = 0; i < message.length; i++) {
    msgEl.textContent += message[i];
    agentLog.scrollTop = agentLog.scrollHeight;
    await sleep(speed);
  }
  return item;
}

function showAgentLoading(message = "Agents are analyzing...") {
  if (!agentLog) return null;
  const item = document.createElement("div");
  item.className = "log-item";
  const now = new Date().toLocaleTimeString();
  item.innerHTML = `
    <div class="log-agent">System</div>
    <div class="log-message loading-message">
      <span class="spinner"></span>
      <span>${message}</span>
    </div>
    <div class="log-time">${now}</div>
  `;
  agentLog.appendChild(item);
  agentLog.scrollTop = agentLog.scrollHeight;
  return item;
}

function removeAgentLoading(loadingEl) {
  if (loadingEl && loadingEl.parentNode) {
    loadingEl.parentNode.removeChild(loadingEl);
  }
}

function clearAgentLog() {
  if (!agentLog) return;
  agentLog.innerHTML = "";
}

async function renderLogsSequentially(logs, speed = 14, token = 0) {
  if (!Array.isArray(logs) || !logs.length) {
    if (token !== logRenderToken) return;
    await typeAgentLog("System", "No detailed agent logs were returned.", speed);
    return;
  }
  for (const log of logs) {
    if (token !== logRenderToken) return;
    await typeAgentLog(log.agent || "System", log.message || "", speed);
  }
}

function stopCurrentAudio() {
  if (currentAudio) {
    currentAudio.pause();
    currentAudio.currentTime = 0;
    currentAudio = null;
  }
}

function setStatus(text) {
  if (statusEl) statusEl.textContent = text;
}

function setSendingState(isSending) {
  if (!sendBtn || !userText) return;
  sendBtn.disabled = isSending;
  userText.disabled = isSending;
}

function isMobileLayout() {
  return window.innerWidth <= 1100;
}

function openAgentPanel() {
  if (!agentPanel) return;
  if (isMobileLayout()) {
    agentPanel.classList.add("open");
    overlay.classList.add("show");
  } else {
    agentPanel.classList.remove("collapsed");
  }
}

function closeAgentPanel() {
  if (!agentPanel) return;
  if (isMobileLayout()) {
    agentPanel.classList.remove("open");
    overlay.classList.remove("show");
  } else {
    agentPanel.classList.add("collapsed");
  }
}

function toggleAgentPanel() {
  if (!agentPanel) return;
  if (isMobileLayout()) {
    const isOpen = agentPanel.classList.contains("open");
    if (isOpen) closeAgentPanel();
    else openAgentPanel();
  } else {
    agentPanel.classList.toggle("collapsed");
  }
}

async function sendMessage() {
  const question = userText ? userText.value.trim() : "";
  if (!question) return;

  const settings = getSettings();
  const enableTTS = settings.enableTTS;
  const enableWebSearch = settings.enableWebSearch;

  addMessage(question, "user");
  userText.value = "";
  autoResizeTextarea();
  setStatus("Running...");
  setSendingState(true);

  logRenderToken += 1;
  const currentToken = logRenderToken;

  clearAgentLog();
  addAgentLog("System", `Web search: ${enableWebSearch ? "ON" : "OFF"}.`);
  addAgentLog("System", "Local file retrieval: ON.");
  addAgentLog("System", `TTS setting: ${enableTTS ? "ON" : "OFF"}.`);

  const loadingEl = showAgentLoading(
    enableWebSearch
      ? "Agents are analyzing, retrieving local files, and searching the web..."
      : "Agents are analyzing and retrieving only local files..."
  );
  const chatLoadingEl = showChatLoading("Assistant is thinking...");

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: question,
        enable_tts: enableTTS,
        enable_web_search: enableWebSearch
      })
    });

    const data = await res.json();

    removeAgentLoading(loadingEl);
    removeChatLoading(chatLoadingEl);

    if (!res.ok) {
      throw new Error(data.reply || "Server returned an error");
    }

    const replyText = data.reply || "No response received.";
    addMessage(replyText, "bot");
    setStatus("Done");

    clearAgentLog();
    renderLogsSequentially(data.logs, 14, currentToken);

    if (enableTTS && data.audio) {
      stopCurrentAudio();
      currentAudio = new Audio(data.audio);
      addAgentLog("System", "TTS audio generated successfully.");
      currentAudio.play().catch(err => {
        console.error("Audio play failed:", err);
        addAgentLog("System", "TTS audio playback failed.");
      });
      currentAudio.onended = () => {
        currentAudio = null;
      };
    } else if (enableTTS && !data.audio) {
      addAgentLog("System", "TTS was requested, but no audio was returned.");
    }
  } catch (err) {
    removeAgentLoading(loadingEl);
    removeChatLoading(chatLoadingEl);
    console.error(err);
    addMessage("Error: failed to connect to backend.", "bot");
    clearAgentLog();
    await typeAgentLog("System", "Backend request failed: " + err.message, 14);
    setStatus("Error");
  } finally {
    setSendingState(false);
    if (userText) userText.focus();
  }
}

if (sendBtn) {
  sendBtn.addEventListener("click", sendMessage);
}

if (userText) {
  userText.addEventListener("input", autoResizeTextarea);
  userText.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
  autoResizeTextarea();
}

if (clearBtn) {
  clearBtn.addEventListener("click", () => {
    logRenderToken += 1;
    stopCurrentAudio();
    if (chatList) {
      chatList.innerHTML = `
        <div class="welcome-block">
          <h1>Ask about Canada’s AI Strategy</h1>
          <p>Ask something about Canada’s AI strategy, policy, market, or related research.</p>
        </div>
      `;
    }
    clearAgentLog();
    addAgentLog("System", "Waiting for a question...");
    setStatus("Idle");
  });
}

if (stopBtn) {
  stopBtn.addEventListener("click", () => {
    stopCurrentAudio();
    addAgentLog("System", "Current audio stopped.");
    setStatus("Idle");
  });
}

if (toggleAgentPanelBtn) {
  toggleAgentPanelBtn.addEventListener("click", toggleAgentPanel);
}

if (closeAgentPanelBtn) {
  closeAgentPanelBtn.addEventListener("click", closeAgentPanel);
}

overlay.addEventListener("click", closeAgentPanel);

window.addEventListener("resize", () => {
  if (!isMobileLayout()) {
    overlay.classList.remove("show");
    agentPanel.classList.remove("open");
  } else {
    if (!agentPanel.classList.contains("open")) {
      overlay.classList.remove("show");
    }
  }
});

clearAgentLog();
addAgentLog("System", "Waiting for a question...");
setStatus("Idle");