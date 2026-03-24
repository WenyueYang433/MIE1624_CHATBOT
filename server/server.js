require("dotenv").config();
const path = require("path");
const fs = require("fs");
const express = require("express");

const app = express();
const PORT = process.env.PORT || 3000;
const PYTHON_CHAT_API =
  process.env.PYTHON_CHAT_API || "http://127.0.0.1:8080/api/chatbot";
const ENABLE_TTS = process.env.ENABLE_TTS === "true";

const candidateDirs = [
  path.resolve(__dirname, "../frontend"),
  path.resolve(__dirname, "frontend"),
  path.resolve(__dirname, "../../frontend")
];

function pickFrontendDir() {
  for (const dir of candidateDirs) {
    if (fs.existsSync(path.join(dir, "index.html"))) return dir;
  }
  return candidateDirs[0];
}

function toBoolean(value, defaultValue = false) {
  if (typeof value === "boolean") return value;
  if (typeof value === "string") {
    const v = value.trim().toLowerCase();
    if (v === "true") return true;
    if (v === "false") return false;
  }
  if (value === undefined || value === null) return defaultValue;
  return Boolean(value);
}

const FRONTEND_DIR = pickFrontendDir();
const INDEX_HTML = path.join(FRONTEND_DIR, "index.html");

app.use(express.json({ limit: "1mb" }));
app.use(express.static(FRONTEND_DIR));

async function callPythonChatbot(message, useRetrieval = true) {
  console.log("PYTHON_CHAT_API =", PYTHON_CHAT_API);
  try {
    const resp = await fetch(PYTHON_CHAT_API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        use_retrieval: useRetrieval
      })
    });

    const text = await resp.text();

    if (!resp.ok) {
      throw new Error(`Python HTTP ${resp.status}: ${text}`);
    }

    return JSON.parse(text);
  } catch (err) {
    console.error("callPythonChatbot failed:", err);
    throw err;
  }
}

async function textToSpeech(text) {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) throw new Error("Missing OPENAI_API_KEY");

  const resp = await fetch("https://api.openai.com/v1/audio/speech", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      model: process.env.TTS_MODEL || "tts-1",
      input: text,
      voice: process.env.TTS_VOICE || "shimmer",
      format: "mp3"
    })
  });

  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    throw new Error(`TTS HTTP ${resp.status}: ${text}`);
  }

  const arrayBuffer = await resp.arrayBuffer();
  return `data:audio/mp3;base64,${Buffer.from(arrayBuffer).toString("base64")}`;
}

app.post("/api/chat", async (req, res) => {
  try {
    const message = String(req.body?.message || "").trim();
    const useRetrieval = toBoolean(req.body?.use_retrieval, true);
    const enableTTS = toBoolean(req.body?.enable_tts, ENABLE_TTS);

    console.log("Incoming /api/chat:", {
      message,
      use_retrieval: useRetrieval,
      enable_tts: enableTTS
    });

    if (!message) {
      return res.status(400).json({
        reply: "Message is empty.",
        audio: null,
        logs: []
      });
    }

    const result = await callPythonChatbot(message, useRetrieval);
    const reply = result.reply;
    const logs = result.logs;

    let audio = null;
    if (enableTTS && reply) {
      try {
        audio = await textToSpeech(reply);
      } catch (e) {
        console.error("TTS Error:", e.message);
        logs.push({
          agent: "System",
          message: `TTS failed: ${e.message}`
        });
      }
    }

    return res.json({ reply, audio, logs });
  } catch (e) {
    console.error("API Error:", e.message);
    return res.status(500).json({
      reply: `Server Error: ${e.message}`,
      audio: null,
      logs: []
    });
  }
});

app.get("*", (req, res) => res.sendFile(INDEX_HTML));

app.listen(PORT, "0.0.0.0", () => {
  console.log(`Web server running on http://127.0.0.1:${PORT}`);
});