import json
import os
import sys
import asyncio
import tempfile
import subprocess
from datetime import datetime
from flask import Flask, render_template, request, jsonify, Response
import anthropic
import edge_tts
from dotenv import load_dotenv

# Add parent directory to path so we can import agent modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from faster_whisper import WhisperModel
from agent.prompts import load_personas, build_system_prompt
from agent import improvement

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

app = Flask(__name__)

SCRIPT_PATH  = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts/current_script.json")
CLAUDE_MODEL = "claude-sonnet-4-6"

client    = anthropic.Anthropic(api_key=os.getenv("CLAUDE_API_KEY"))
stt_model = WhisperModel("base", device="cpu", compute_type="int8")

# In-memory call state — one call at a time
call_state = {
    "active":        False,
    "history":       [],
    "script":        None,
    "system_prompt": None,
    "persona":       None,
    "transcript":    []
}


def load_script() -> dict:
    with open(SCRIPT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return json.loads(data[0]["clean_script"])


def ava_respond(system_prompt: str, history: list) -> str:
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=300,
        system=system_prompt,
        messages=history
    )
    return response.content[0].text.strip()


async def tts_to_file(text: str, path: str):
    # Generate Ava's voice and save to a file path instead of playing via ffplay
    communicate = edge_tts.Communicate(text, voice="en-US-JennyNeural")
    await communicate.save(path)


def generate_speech(text: str) -> str:
    # Returns path to generated mp3 file
    path = os.path.join(os.path.dirname(__file__), "static", "ava_response.mp3")
    asyncio.run(tts_to_file(text, path))
    return "/static/ava_response.mp3"


@app.route("/")
def index():
    personas = load_personas()
    script   = load_script()
    return render_template("index.html", personas=personas, script_version=script.get("script_version"))


@app.route("/start", methods=["POST"])
def start_call():
    # Initialize a new call with the selected persona
    data    = request.json
    persona = data.get("persona")
    script  = load_script()

    call_state["active"]        = True
    call_state["history"]       = []
    call_state["script"]        = script
    call_state["system_prompt"] = build_system_prompt(script)
    call_state["persona"]       = persona
    call_state["transcript"]    = []

    # Ava opens the call
    call_state["history"].append({"role": "user", "content": "[ Call connected ]"})
    opener = ava_respond(call_state["system_prompt"], call_state["history"])
    call_state["history"].append({"role": "assistant", "content": opener})
    call_state["transcript"].append({"speaker": "AVA", "text": opener})

    audio_url = generate_speech(opener)

    return jsonify({
        "text":      opener,
        "audio_url": audio_url,
        "version":   script.get("script_version")
    })


@app.route("/respond", methods=["POST"])
def respond():
    if not call_state["active"]:
        return jsonify({"error": "No active call"}), 400

    # Receive audio from browser, convert to WAV, transcribe with Whisper
    audio_file = request.files.get("audio")
    if not audio_file:
        return jsonify({"error": "No audio received"}), 400

    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp_webm:
        audio_file.save(tmp_webm.name)
        webm_path = tmp_webm.name

    wav_path = webm_path.replace(".webm", ".wav")
    subprocess.run(
        ["ffmpeg", "-y", "-i", webm_path, "-ar", "16000", "-ac", "1", wav_path],
        capture_output=True
    )

    segments, _ = stt_model.transcribe(wav_path)
    user_text = " ".join(s.text for s in segments).strip()

    os.unlink(webm_path)
    os.unlink(wav_path)

    if not user_text:
        return jsonify({"error": "Could not transcribe audio"}), 400

    call_state["transcript"].append({"speaker": "LEAD", "text": user_text})

    # Get Ava's response
    call_state["history"].append({"role": "user", "content": user_text})
    response = ava_respond(call_state["system_prompt"], call_state["history"])
    call_state["history"].append({"role": "assistant", "content": response})

    speakable = response.split("[OUTCOME:")[0].strip()
    call_state["transcript"].append({"speaker": "AVA", "text": speakable})

    audio_url = generate_speech(speakable)

    # Check if call ended
    outcome = None
    if "[OUTCOME:" in response:
        outcome = "success" if "success" in response else "failed" if "failed" in response else "neutral"
        call_state["active"] = False
        improvement.run(call_state["history"], outcome, call_state["script"], client)

    return jsonify({
        "lead_text": user_text,
        "ava_text":  speakable,
        "audio_url": audio_url,
        "outcome":   outcome
    })


@app.route("/transcript")
def get_transcript():
    return jsonify(call_state["transcript"])


@app.route("/personas")
def get_personas():
    return jsonify(load_personas())


if __name__ == "__main__":
    app.run(debug=True, port=5000)
