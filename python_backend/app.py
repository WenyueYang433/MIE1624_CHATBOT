from flask import Flask, request, jsonify
from chatbot import run_chatbot

app = Flask(__name__)

@app.route("/api/chatbot", methods=["POST"])
def chatbot_api():
    try:
        data = request.get_json()
        message = str(data.get("message", "")).strip()
        use_retrieval = bool(data.get("use_retrieval", True))

        if not message:
            return jsonify({"reply": "Message is empty.", "logs": []}), 400

        result = run_chatbot(message, use_retrieval=use_retrieval)
        return jsonify(result)
    except Exception as e:
        return jsonify({"reply": f"Backend error: {str(e)}", "logs": []}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)