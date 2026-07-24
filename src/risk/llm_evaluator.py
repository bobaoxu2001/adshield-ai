from __future__ import annotations

import json

from pydantic import BaseModel, Field

from src.config import settings


class LLMRiskAssessment(BaseModel):
    risk_category: str
    risk_score: float = Field(ge=0, le=1)
    evidence: list[str]
    policy_rationale: str
    recommended_action: str
    confidence: float = Field(ge=0, le=1)
    needs_human_review: bool


def llm_available() -> bool:
    return bool(settings.openai_api_key)


def evaluate_with_openai(case_payload: dict[str, object]) -> dict[str, object] | None:
    """Optional comparison path; deterministic decisions remain authoritative by default."""
    if not settings.openai_api_key:
        return None
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.responses.parse(
        model=settings.openai_model,
        instructions=(
            "You are a non-binding second-opinion reviewer for public-source commercial-ads risk research. "
            "Do not infer identity or private facts. CFPB complaints are risk priors, not ads or confirmed violations; "
            "for those records, recommend analyst research rather than approve/reject enforcement."
        ),
        input=json.dumps(case_payload, ensure_ascii=False),
        text_format=LLMRiskAssessment,
        max_output_tokens=800,
        store=False,
        timeout=30,
    )
    return response.output_parsed.model_dump() if response.output_parsed else None
