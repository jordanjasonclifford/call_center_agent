import json
import os
from datetime import datetime
import anthropic

# Improvement loop - runs after every call to analyze the transcript and update the script.
# Two Claude calls are made: one to analyze what went wrong, one to rewrite only the problem section.

_ROOT        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_PATH  = os.path.join(_ROOT, "scripts/current_script.json")
CLAUDE_MODEL = "claude-sonnet-4-6"


def run(history: list, outcome: str, script: dict, client: anthropic.Anthropic):
    # Build a clean transcript from the conversation history
    transcript = "\n".join(
        f"{'AVA' if m['role'] == 'assistant' else 'LEAD'}: {m['content']}"
        for m in history
        if m["content"] != "[ Call connected ]"
    )

    # Step 1 - Analyst: identify what failed and where
    print("[ Analyzing call... ]")
    analysis_response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": f"""You are a sales call analyst. Here is a transcript of a sales call:

{transcript}

Outcome: {outcome}

Return ONLY valid JSON with this exact structure - no explanation, no markdown:

{{
  "outcome": "{outcome}",
  "primary_objection": "too_expensive" or "already_have_crm" or "not_the_right_time" or "send_info" or "none",
  "failure_point": "opener" or "discovery" or "value_pitch" or "objection_handler" or "close" or "none",
  "reached_close": true,
  "recommendation": "one sentence on what to change"
}}"""
        }]
    )
    analysis = analysis_response.content[0].text.strip()
    print(f"[ Analysis: {analysis} ]")

    # Step 2 - Optimizer: rewrite only the section that failed, increment version
    print("[ Optimizing script... ]")
    optimizer_response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": f"""You are a sales script optimizer. Here is the current script:

{json.dumps(script, indent=2)}

Here is the analysis of the last call:
{analysis}

Rules:
- ONLY edit the section identified in failure_point
- If failure_point is "objection_handler", only edit the handler for primary_objection
- Do NOT rewrite sections that are working
- Keep the same JSON structure
- Increment script_version by 1
- If failure_point is none and outcome is success, return the script unchanged

Return ONLY the updated script JSON. No explanation, no markdown."""
        }]
    )
    new_script_raw = optimizer_response.content[0].text.strip()

    # Strip markdown fences if Claude wrapped the output in them
    new_script_clean = new_script_raw.replace("```json", "").replace("```", "").strip()

    # Write the updated script back to disk in the same format the system expects
    with open(SCRIPT_PATH, "w", encoding="utf-8") as f:
        json.dump([{"clean_script": new_script_clean}], f)

    new_script = json.loads(new_script_clean)
    version = new_script.get("script_version")
    print(f"[ Script updated - version {version} ]")

    # Save a versioned snapshot of the script after each optimization
    version_path = os.path.join(_ROOT, f"scripts/versions/script_v{version}.json")
    with open(version_path, "w", encoding="utf-8") as f:
        json.dump(new_script, f, indent=2)

    # Save the full transcript with timestamp for this call
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    transcript_path = os.path.join(_ROOT, f"logs/transcripts/call_{timestamp}.txt")
    with open(transcript_path, "w", encoding="utf-8") as f:
        f.write(f"Outcome: {outcome}\n")
        f.write(f"Script version used: {script.get('script_version')}\n")
        f.write(f"Analysis: {analysis}\n\n")
        f.write(transcript)

    print(f"[ Transcript saved - {transcript_path} ]")
