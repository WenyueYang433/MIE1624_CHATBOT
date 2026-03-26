const defaultSettings = {
  enableTTS: false,
  enableWebSearch: true
};

function loadSettings() {
  const saved = localStorage.getItem("chatbotSettings");
  return saved ? JSON.parse(saved) : defaultSettings;
}

function fillForm(settings) {
  document.getElementById("enableTTS").checked =
    settings.enableTTS ?? defaultSettings.enableTTS;
  document.getElementById("enableWebSearch").checked =
    settings.enableWebSearch ?? defaultSettings.enableWebSearch;
}

function readForm() {
  return {
    enableTTS: document.getElementById("enableTTS").checked,
    enableWebSearch: document.getElementById("enableWebSearch").checked
  };
}

document.addEventListener("DOMContentLoaded", () => {
  fillForm(loadSettings());

  document.getElementById("saveBtn").addEventListener("click", () => {
    const settings = readForm();
    localStorage.setItem("chatbotSettings", JSON.stringify(settings));
    document.getElementById("saveStatus").textContent = "Settings saved.";
  });

  document.getElementById("resetBtn").addEventListener("click", () => {
    localStorage.setItem("chatbotSettings", JSON.stringify(defaultSettings));
    fillForm(defaultSettings);
    document.getElementById("saveStatus").textContent = "Settings reset.";
  });
});