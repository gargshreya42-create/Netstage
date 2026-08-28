"""
Unit tests for the AI diagnosis engine using a mocked AIProvider, so these
run without any real API key or network access. Covers Section 21's
'invalid JSON from LLM' and 'LLM API failure' error-handling requirements
directly, plus the hard requires_human_review safety invariant.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ai import engine as engine_module  # noqa: E402
from app.ai.engine import AIEngineError, DiagnosisRequest, run_ai_diagnosis  # noqa: E402
from app.ai.provider import AIProvider, AIProviderError  # noqa: E402
from app.schemas.diagnosis_schemas import RuleCheckResult  # noqa: E402


class _FakeProvider(AIProvider):
    def __init__(self, response_text=None, raise_error=False):
        self._response_text = response_text
        self._raise_error = raise_error

    def complete(self, system_prompt, user_prompt):
        if self._raise_error:
            raise AIProviderError("Simulated provider failure (e.g. network/auth/rate limit).")
        return self._response_text


def _sample_request():
    return DiagnosisRequest(
        case_id="NET-001",
        symptom="Test symptom",
        topology_note="Test topology",
        show_outputs="R1# show interfaces Gi0/0.30\nadministratively down",
        rule_check_result=RuleCheckResult(status="ERRORS_DETECTED", errors=[]),
    )


def _patch_provider(monkeypatch, fake_provider):
    monkeypatch.setattr(engine_module, "get_ai_provider", lambda api_key, model: fake_provider)
    monkeypatch.setattr(
        engine_module,
        "get_settings",
        lambda: type("S", (), {"ai_enabled": True, "openai_api_key": "fake-key", "ai_model": "fake-model"})(),
    )


def test_valid_json_response_parses_successfully(monkeypatch):
    valid_json = (
        '{"root_cause": "Interface down", "osi_layer": "Layer 3", "confidence": "High", '
        '"severity": "High", "evidence": ["line 1"], "next_command": null, '
        '"fix_steps": ["no shutdown"], "reasoning": "clear evidence", "requires_human_review": true}'
    )
    _patch_provider(monkeypatch, _FakeProvider(response_text=valid_json))
    result = run_ai_diagnosis(_sample_request())
    assert result.root_cause == "Interface down"
    assert result.requires_human_review is True


def test_code_fenced_json_response_parses_successfully(monkeypatch):
    fenced = (
        "```json\n"
        '{"root_cause": "x", "osi_layer": "Layer 3", "confidence": "Low", '
        '"severity": "Low", "evidence": [], "next_command": "show run", '
        '"fix_steps": [], "reasoning": "insufficient", "requires_human_review": true}\n'
        "```"
    )
    _patch_provider(monkeypatch, _FakeProvider(response_text=fenced))
    result = run_ai_diagnosis(_sample_request())
    assert result.root_cause == "x"


def test_invalid_json_raises_ai_engine_error(monkeypatch):
    """Section 21: invalid JSON from the LLM must be handled, not crash the app."""
    _patch_provider(monkeypatch, _FakeProvider(response_text="this is not json at all { broken"))
    with pytest.raises(AIEngineError):
        run_ai_diagnosis(_sample_request())


def test_json_missing_required_fields_raises_ai_engine_error(monkeypatch):
    incomplete_json = '{"root_cause": "x"}'  # missing required fields
    _patch_provider(monkeypatch, _FakeProvider(response_text=incomplete_json))
    with pytest.raises(AIEngineError):
        run_ai_diagnosis(_sample_request())


def test_empty_response_raises_ai_engine_error(monkeypatch):
    _patch_provider(monkeypatch, _FakeProvider(response_text=""))
    with pytest.raises(AIEngineError):
        run_ai_diagnosis(_sample_request())


def test_provider_failure_raises_ai_engine_error(monkeypatch):
    """Section 21: LLM API failure (network, auth, rate limit) must be handled cleanly."""
    _patch_provider(monkeypatch, _FakeProvider(raise_error=True))
    with pytest.raises(AIEngineError):
        run_ai_diagnosis(_sample_request())


def test_requires_human_review_cannot_be_overridden_by_model(monkeypatch):
    """
    Hard safety invariant: even if the LLM (hypothetically) returned
    requires_human_review=false, our schema must force it back to true.
    """
    sneaky_json = (
        '{"root_cause": "x", "osi_layer": "Layer 3", "confidence": "High", '
        '"severity": "Low", "evidence": [], "next_command": null, '
        '"fix_steps": [], "reasoning": "y", "requires_human_review": false}'
    )
    _patch_provider(monkeypatch, _FakeProvider(response_text=sneaky_json))
    result = run_ai_diagnosis(_sample_request())
    assert result.requires_human_review is True


def test_missing_api_key_raises_before_calling_provider(monkeypatch):
    monkeypatch.setattr(
        engine_module,
        "get_settings",
        lambda: type("S", (), {"ai_enabled": False, "openai_api_key": "", "ai_model": "x"})(),
    )
    with pytest.raises(AIEngineError, match="OPENAI_API_KEY"):
        run_ai_diagnosis(_sample_request())
