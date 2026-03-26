from flask import Flask, request, jsonify
from chatbot import run_chatbot
import os

app = Flask(__name__)

def to_bool(value, default=True):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v == "true":
            return True
        if v == "false":
            return False
    if value is None:
        return default
    return bool(value)

@app.get("/health")
def health():
    return {"ok": True}

@app.route("/api/chatbot", methods=["POST"])
def chatbot_api():
    try:
        data = request.get_json(silent=True) or {}
        message = str(data.get("message", "")).strip()
        enable_web_search = to_bool(data.get("enable_web_search", True), True)

        if not message:
            return jsonify({"reply": "Message is empty.", "logs": []}), 400

        result = run_chatbot(message, enable_web_search=enable_web_search)
        return jsonify(result)
    except Exception as e:
        return jsonify({"reply": f"Backend error: {str(e)}", "logs": []}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)