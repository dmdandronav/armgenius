"""
ArmGenius — Flask backend
--------------------------
Natural language commands are translated by an LLM into named arm actions,
then forwarded to an ESP32 servo controller over HTTP.

This is the "DUM-E" pattern: LLM decides WHAT to do, Flask translates that
into a simple HTTP call, and the microcontroller executes it. Splitting it
this way means you can swap in a different "brain" without touching firmware.

Endpoints:
  POST /api/chat        -> send a message, get a reply + arm action result
  POST /api/documents    -> upload .txt/.md files for lightweight RAG context
  GET  /api/health       -> sanity check
"""

import os
import json
import math
from pathlib import Path

import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

app = Flask(__name__)
CORS(app)  # allow the Vite dev server (localhost:5173) to call this API

# ---------------------------------------------------------------------------
# Client setup — works with OpenAI, Groq, or any OpenAI-compatible API
# ---------------------------------------------------------------------------
_client = None


def get_client():
    """Lazily construct the OpenAI client.

    Building it at import time raises when OPENAI_API_KEY is unset, which would
    prevent the whole app from booting. Deferring construction lets the server
    start and only surfaces the missing-key error on the first request that
    actually needs the LLM.
    """
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
            base_url=os.environ.get("OPENAI_BASE_URL") or None,
        )
    return _client


MODEL = os.environ.get("MODEL_NAME", "gpt-4o-mini")
EMBED_MODEL = os.environ.get("EMBED_MODEL_NAME", "text-embedding-3-small")

# ---------------------------------------------------------------------------
# ArmGenius system prompt — instructs the LLM to append ACTION:{...} lines
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = os.environ.get(
    "SYSTEM_PROMPT",
    "You are ArmGenius, a robotic arm assistant. When the user asks you to do "
    "something physical, respond naturally AND include a JSON action on the last "
    'line of your response in the format: ACTION:{"action":"point_left"} where '
    "action is one of: point_left, point_right, center, wave, grab, release, bow, "
    "none. Choose \"none\" if the user is just talking. Always execute the most "
    "fitting action.",
)

# ---------------------------------------------------------------------------
# Arm connection — set ARM_URL in .env to your ESP32's IP, e.g.
#   ARM_URL=http://192.168.1.55
# Leave blank to run without hardware (simulation mode).
# ---------------------------------------------------------------------------
ARM_URL = os.environ.get("ARM_URL")  # e.g. http://192.168.1.55

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
INDEX_PATH = DATA_DIR / "_embeddings.json"


# ---------------------------------------------------------------------------
# Arm action executor — fires a GET to /action?name=<action_name>
# ---------------------------------------------------------------------------
def execute_arm_action(action_name: str):
    """Forward a named action to the ESP32 arm controller.

    Returns the JSON response from the arm, or None if ARM_URL is not set
    or the action is "none". Catches network errors gracefully so a missing
    or offline arm never crashes the chat endpoint.
    """
    if not ARM_URL or action_name == "none":
        return None
    try:
        r = requests.get(
            f"{ARM_URL}/action",
            params={"name": action_name},
            timeout=3,
        )
        return r.json()
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Lightweight RAG — chunk local docs, embed them, retrieve by cosine similarity
# ---------------------------------------------------------------------------
def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return [c.strip() for c in chunks if c.strip()]


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def build_index():
    """Re-embeds every .txt/.md file in ./data and saves to _embeddings.json."""
    records = []
    for path in DATA_DIR.glob("*.*"):
        if path.suffix.lower() not in (".txt", ".md"):
            continue
        text = path.read_text(errors="ignore")
        for chunk in chunk_text(text):
            records.append({"source": path.name, "text": chunk})

    if not records:
        INDEX_PATH.write_text(json.dumps([]))
        return []

    resp = get_client().embeddings.create(model=EMBED_MODEL, input=[r["text"] for r in records])
    for r, e in zip(records, resp.data):
        r["embedding"] = e.embedding

    INDEX_PATH.write_text(json.dumps(records))
    return records


def load_index():
    if INDEX_PATH.exists():
        return json.loads(INDEX_PATH.read_text())
    return []


def retrieve(query: str, top_k: int = 3):
    """Return the top_k most relevant chunks for `query`. Empty list if no docs."""
    records = load_index()
    if not records:
        return []
    q_emb = get_client().embeddings.create(model=EMBED_MODEL, input=[query]).data[0].embedding
    scored = sorted(records, key=lambda r: cosine(q_emb, r["embedding"]), reverse=True)
    return scored[:top_k]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "model": MODEL, "arm_url": ARM_URL or "not configured"})


@app.route("/api/documents", methods=["POST"])
def add_document():
    """Upload a text/markdown file to add it to the RAG knowledge base.

    Send as multipart/form-data with field name 'file'.
    """
    if "file" not in request.files:
        return jsonify({"error": "no file provided"}), 400

    f = request.files["file"]
    save_path = DATA_DIR / f.filename
    f.save(save_path)

    records = build_index()
    return jsonify({"status": "indexed", "chunks": len(records)})


@app.route("/api/chat", methods=["POST"])
def chat():
    """
    Body: { "messages": [{"role": "user"|"assistant", "content": "..."}, ...] }
    Returns: { "reply": "...", "sources": [...], "arm_action": {...}|null }

    The LLM is instructed to append ACTION:{...} on its last line. This route
    strips that line, fires the action at the arm, and returns the arm's
    response as arm_action in the JSON body.
    """
    body = request.get_json(force=True)
    messages = body.get("messages", [])
    if not messages:
        return jsonify({"error": "messages required"}), 400

    last_user_msg = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")

    # Pull in relevant context from uploaded docs, if any exist.
    context_chunks = retrieve(last_user_msg)
    sources = sorted({c["source"] for c in context_chunks})

    chat_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if context_chunks:
        context_text = "\n\n---\n\n".join(c["text"] for c in context_chunks)
        chat_messages.append({
            "role": "system",
            "content": f"Relevant context from uploaded documents:\n\n{context_text}",
        })
    chat_messages.extend(messages)

    completion = get_client().chat.completions.create(
        model=MODEL,
        messages=chat_messages,
        temperature=0.7,
    )
    reply = completion.choices[0].message.content

    # Parse ACTION:{...} from the last line and execute it on the arm.
    arm_result = None
    arm_action_name = None
    lines = reply.strip().split("\n")
    if lines and lines[-1].startswith("ACTION:"):
        try:
            action_data = json.loads(lines[-1][7:])
            arm_action_name = action_data.get("action", "none")
            arm_result = execute_arm_action(arm_action_name)
            # Strip the ACTION line from the displayed reply
            reply = "\n".join(lines[:-1]).strip()
        except Exception:
            pass

    return jsonify({
        "reply": reply,
        "sources": sources,
        "arm_action": arm_action_name,
        "arm_result": arm_result,
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
