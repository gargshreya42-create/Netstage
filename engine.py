"""
AI diagnosis engine.

Combines:
1. User-provided evidence (symptom, topology, show output)
2. Deterministic rule checker results
3. The system prompt template (prompts/diagnose_prompt.md)
4. The LLM response

The engine NEVER lets malformed AI output reach the rest of the app: any
response that isn't strictly valid JSON matching AIDiagnosisPayload raises
an AIEngineError, which the API layer turns into a clean error response
instead of a crash.
"""
import json
import os
from dataclasses import dataclass
from typing import Optional

from pydantic import ValidationError

from app.ai.provider import AIProviderError, get_ai_provider
from app.config import get_settings
from app.schemas.diagnosis_schemas import AIDiagnosisPayload, RuleCheckResult

PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "prompts", "diagnose_prompt.md")


class AIEngineError(Exception):
    """Raised for any failure in the AI diagnosis path (config, provider, or parsing)."""


@dataclass
class DiagnosisRequest:
    case_id: str
    symptom: str
    topology_note: str
    show_outputs: str
    rule_check_result: RuleCheckResult


def _load_system_prompt() -> str:
    path = os.path.abspath(PROMPT_PATH)
    if not os.path.exists(path):
        raise AIEngineError(f"Diagnosis prompt file not found at {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _build_user_prompt(req: DiagnosisRequest) -> str:
    rule_summary = req.rule_check_result.model_dump()
    return (
        f"## Case: {req.case_id}\n\n"
        f"### Symptom\n{req.symptom}\n\n"
        f"### Topology Notes\n{req.topology_note or '(none provided)'}\n\n"
        f"### Evidence (raw show-command output)\n```\n{req.show_outputs}\n```\n\n"
        f"### Deterministic Rule Checker Result\n```json\n{json.dumps(rule_summary, indent=2)}\n```\n\n"
        "Analyze the above and return your diagnosis as a single JSON object "
        "matching the required schema. Return ONLY the JSON object."
    )


def _extract_json(raw_text: str) -> dict:
    """
    Best-effort extraction of a JSON object from the model's raw response.
    Handles the common case of accidental markdown code fences even though
    the prompt explicitly forbids them.
    """
    text = raw_text.strip()
    if text.startswith("```"):
        # Strip ```json ... ``` or ``` ... ``` fences
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise AIEngineError(f"AI response was not valid JSON: {e}") from e


def run_ai_diagnosis(req: DiagnosisRequest) -> AIDiagnosisPayload:
    """
    Run the full AI diagnosis pipeline for a single case.
    Raises AIEngineError for any failure (missing key, provider failure,
    invalid JSON, schema validation failure) — callers must handle this
    and surface a clean error rather than letting it propagate raw.
    """
    settings = get_settings()
    if not settings.ai_enabled:
        raise AIEngineError(
            "AI diagnosis is unavailable: no OPENAI_API_KEY is configured. "
            "Rule-checker results are still available."
        )

    system_prompt = _load_system_prompt()
    user_prompt = _build_user_prompt(req)

    try:
        provider = get_ai_provider(settings.openai_api_key, settings.ai_model)
        raw_response = provider.complete(system_prompt, user_prompt)
    except AIProviderError as e:
        raise AIEngineError(str(e)) from e

    if not raw_response or not raw_response.strip():
        raise AIEngineError("AI provider returned an empty response.")

    parsed_dict = _extract_json(raw_response)

    try:
        payload = AIDiagnosisPayload(**parsed_dict)
    except ValidationError as e:
        raise AIEngineError(f"AI response failed schema validation: {e}") from e

    return payload
