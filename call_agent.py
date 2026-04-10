import json
import os
import anthropic
from dotenv import load_dotenv

# Agent modules split across separate files for readability
from agent.prompts import select_persona, build_system_prompt
from agent.tts import speak as ava_speak
from agent.stt import record_until_enter
from agent import improvement

# Load environment variables from .env
load_dotenv()

SCRIPT_PATH  = "scripts/current_script.json"
CLAUDE_MODEL = "claude-sonnet-4-6"

# Initialize the Anthropic client using the API key from .env
client = anthropic.Anthropic(api_key=os.getenv("CLAUDE_API_KEY"))


def load_script() -> dict:
    # Reads the latest script version from disk.
    # This file gets updated automatically after every call by the improvement loop.
    with open(SCRIPT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return json.loads(data[0]["clean_script"])


def ava_respond(system_prompt: str, history: list) -> str:
    # Sends the full conversation history to Claude and returns Ava's next line.
    # History grows each turn so Claude always has full context of what was said.
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=300,
        system=system_prompt,
        messages=history
    )
    return response.content[0].text.strip()


if __name__ == "__main__":
    # Load the current script and let the user pick a persona
    script = load_script()
    persona = select_persona()
    system_prompt = build_system_prompt(script)

    print(f"\nScript version: {script['script_version']}")
    print(f"Persona: {persona['name']} - {persona['role']}")
    print("\n--- Call starting ---\n")

    # Conversation history passed to Claude on every turn
    history = []

    # Start the call, Ava delivers the opener
    history.append({"role": "user", "content": "[ Call connected ]"})
    opener = ava_respond(system_prompt, history)
    history.append({"role": "assistant", "content": opener})
    print(f"AVA: {opener}\n")
    ava_speak(opener)

    # Main call loop, runs until Ava signals an outcome
    while True:
        # Capture the lead's voice input via mic
        user_input = record_until_enter()
        if not user_input:
            continue

        # Add lead input to history, get Ava's response
        history.append({"role": "user", "content": user_input})
        response = ava_respond(system_prompt, history)
        history.append({"role": "assistant", "content": response})

        # Strip the outcome tag before passing to TTS so Ava doesn't speak it
        speakable = response.split("[OUTCOME:")[0].strip()
        print(f"\nAVA: {response}\n")
        ava_speak(speakable)

        # Ava appends [OUTCOME: ...] on the final turn to signal the call is done
        if "[OUTCOME:" in response:
            outcome = "success" if "success" in response else "failed" if "failed" in response else "neutral"
            print(f"\n[ Call ended - outcome: {outcome} ]")

            # Trigger the improvement loop to analyze the call and update the script
            improvement.run(history, outcome, script, client)
            break
