const chatList = document.getElementById("chatList");
const agentLog = document.getElementById("agentLog");
const userText = document.getElementById("userText");
const sendBtn = document.getElementById("sendBtn");
const stopBtn = document.getElementById("stopBtn");
const clearBtn = document.getElementById("clearBtn");
const micBtn = document.getElementById("micBtn");
const statusEl = document.getElementById("status");

let currentAudio = null;
let logRenderToken = 0;

function getSettings() {
  const defaults = {
    enableTTS: false,
    enableRetrieval: true
  };
  try {
    const saved = JSON.parse(localStorage.getItem("chatbotSettings") || "{}");
    return {
      enableTTS: saved.enableTTS ?? defaults.enableTTS,
      enableRetrieval: saved.enableRetrieval ?? defaults.enableRetrieval
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
  return marked.parse(text, {
    breaks: true,
    gfm: true
  });
}

function addMessage(text, role) {
  if (!chatList) return null;
  const div = document.createElement("div");
  div.className = `message ${role}`;
  if (role === "bot") {
    div.innerHTML = renderMarkdown(text);
  } else {
    div.textContent = text;
  }
  chatList.appendChild(div);
  chatList.scrollTop = chatList.scrollHeight;
  return div;
}

function showChatLoading(message = "Assistant is thinking...") {
  if (!chatList) return null;
  const div = document.createElement("div");
  div.className = "message bot loading-bubble";
  div.innerHTML = `
    <div class="bubble-loading">
      <span class="spinner"></span>
      <span>${message}</span>
    </div>
  `;
  chatList.appendChild(div);
  chatList.scrollTop = chatList.scrollHeight;
  return div;
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
  agentLog.appendChild(item);
  const msgEl = item.querySelector(".log-message");
  msgEl.textContent = message;
  agentLog.scrollTop = agentLog.scrollHeight;
  return item;
}

async function typeAgentLog(agent, message, speed = 20) {
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
  item.className = "log-item loading-item";
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

async function renderLogsSequentially(logs, speed = 20, token = 0) {
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

async function sendMessage() {
  const question = userText ? userText.value.trim() : "";
  if (!question) return;

  const settings = getSettings();
  const enableTTS = settings.enableTTS;
  const useRetrieval = settings.enableRetrieval;

  addMessage(question, "user");
  userText.value = "";
  statusEl.textContent = "Running...";

  logRenderToken += 1;
  const currentToken = logRenderToken;

  clearAgentLog();
  if (useRetrieval) {
    addAgentLog("System", "Retrieval mode enabled.");
    addAgentLog("Researcher", "Knowledge base search initialized.");
  } else {
    addAgentLog("System", "Retrieval mode disabled.");
    addAgentLog("Assistant", "Using direct chat mode.");
  }

  addAgentLog("System", `TTS setting: ${enableTTS ? "ON" : "OFF"}.`);

  const loadingEl = showAgentLoading(
    useRetrieval
      ? "Agents are analyzing and retrieving evidence..."
      : "Agents are analyzing the question..."
  );
  const chatLoadingEl = showChatLoading("Assistant is thinking...");

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        message: question,
        enable_tts: enableTTS,
        use_retrieval: useRetrieval
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
    statusEl.textContent = "Done";

    clearAgentLog();
    renderLogsSequentially(data.logs, 20, currentToken);

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
    await typeAgentLog("System", "Backend request failed: " + err.message, 20);
    statusEl.textContent = "Error";
  }
}

if (sendBtn) {
  sendBtn.addEventListener("click", sendMessage);
}

if (userText) {
  userText.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
}

if (clearBtn) {
  clearBtn.addEventListener("click", () => {
    logRenderToken += 1;
    stopCurrentAudio();
    if (chatList) chatList.innerHTML = "";
    clearAgentLog();
    addAgentLog("System", "Waiting for a question...");
    statusEl.textContent = "Idle";
  });
}

if (stopBtn) {
  stopBtn.addEventListener("click", () => {
    stopCurrentAudio();
    addAgentLog("System", "Current audio stopped.");
    statusEl.textContent = "Idle";
  });
}

if (micBtn) {
  micBtn.addEventListener("click", () => {
    addAgentLog("System", "Microphone input is not configured.");
  });
}

clearAgentLog();
addAgentLog("System", "Waiting for a question...");