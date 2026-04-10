import json
import os

# Persona and system prompt for the Ava agent
# OLD_PATH = PERSONAS_PATH = "scripts/personas.json"
# Absolute path so this works whether run from the project root or the web/ folder
PERSONAS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts/personas.json")


def load_personas() -> list:
    with open(PERSONAS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["personas"]


def select_persona() -> dict:
    # Show available personas and let the user pick one at the start of each call
    personas = load_personas()
    print("Select a persona to play as:\n")
    for i, p in enumerate(personas):
        print(f"  {i + 1}. {p['name']} - {p['description']}")
    print()

    while True:
        choice = input("Enter number: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(personas):
            return personas[int(choice) - 1]
        print("Invalid choice, try again.")


def build_system_prompt(script: dict) -> str:
    # Builds Ava's system prompt using the current script version.
    # The script is injected directly so Ava always uses the latest optimized version.
    return f"""You are Ava, a sales rep for SalesNest on a live cold call.

Follow this script:
{json.dumps(script, indent=2)}

Rules:
- Respond to what the lead just said - one reply at a time, short and natural
- Keep every response under 3 sentences
- Never break character
- Use objection handlers when relevant
- Push toward the close when appropriate
- If the lead is clearly ending the call, deliver the fallback line and stop
- Speak only as Ava - no stage directions, no narration

When the call ends for any reason, append one of these tags on a new line at the end of your final response:
[OUTCOME: success]
[OUTCOME: failed]
[OUTCOME: neutral]"""
