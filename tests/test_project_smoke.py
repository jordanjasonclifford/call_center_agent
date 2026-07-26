import json
from pathlib import Path

from agent.prompts import build_system_prompt, load_personas


ROOT = Path(__file__).resolve().parents[1]


def load_current_script() -> dict:
    data = json.loads((ROOT / "scripts" / "current_script.json").read_text(encoding="utf-8"))
    return json.loads(data[0]["clean_script"])


def test_personas_load_with_required_fields():
    personas = load_personas()

    assert personas
    assert {"name", "role", "primary_objection", "description"}.issubset(personas[0])


def test_current_script_loads_salesnest_fields():
    script = load_current_script()

    assert script["product"] == "SalesNest"
    assert isinstance(script["script_version"], int)
    assert "opener" in script
    assert "objection_handlers" in script


def test_system_prompt_includes_script_and_outcome_tags():
    script = load_current_script()
    prompt = build_system_prompt(script)

    assert "You are Ava" in prompt
    assert "SalesNest" in prompt
    assert "[OUTCOME: success]" in prompt
    assert "[OUTCOME: failed]" in prompt
    assert "[OUTCOME: neutral]" in prompt
