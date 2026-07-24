from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.app import repository
from src.config import settings
from src.risk.data_access import AuthorizedDataBatch, validate_authorized_batch

app = FastAPI(title="AdShield AI API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


class FeedbackInput(BaseModel):
    case_id: str
    decision: str
    notes: str = ""


class StrategyAssumptionsInput(BaseModel):
    review_minutes_per_case: float = Field(3.0, ge=0)
    reviewer_hourly_cost: float = Field(35.0, ge=0)
    model_cost_per_case: float = Field(0.002, ge=0)
    revenue_value_per_allowed_case: float = Field(4.0, ge=0)
    harm_cost_per_missed_case: float = Field(50.0, ge=0)


class CandidateStrategyInput(BaseModel):
    risk_threshold: float = Field(ge=0, le=1)
    escalation_threshold: float = Field(ge=0, le=1)
    reviewer_capacity: int = Field(ge=1)


class MultimodalTextInput(BaseModel):
    creative_text: str = Field(min_length=1)
    ocr_text: str | None = None
    asr_text: str | None = None


@app.get("/api/health")
def health() -> dict[str, object]:
    database = repository.database_health()
    return {
        "status": "ok",
        "database_ready": database["ready"],
        "missing_tables": database["missing_tables"],
        "real_data_only": True,
        "deployment_mode": "public_read_only_snapshot" if settings.public_demo else "local_writable_mart",
        "feedback_writable": settings.feedback_writable,
    }


@app.get("/api/overview")
def get_overview() -> dict[str, object]:
    return repository.overview()


@app.get("/api/cases")
def get_cases(search: str = "", category: str = "", severity: str = "", language: str = "", source: str = "", action: str = "", limit: int = Query(200, ge=1, le=1000), offset: int = Query(0, ge=0)) -> list[dict[str, object]]:
    return repository.cases(search, category, severity, language, source, action, limit, offset)


@app.get("/api/cases/count")
def get_case_count(search: str = "", category: str = "", severity: str = "", language: str = "", source: str = "", action: str = "") -> dict[str, int]:
    return {"total": repository.case_count(search, category, severity, language, source, action)}


@app.get("/api/cases/{case_id}")
def get_case(case_id: str) -> dict[str, object]:
    result = repository.case_detail(case_id)
    if not result:
        raise HTTPException(404, "Case not found")
    return result


@app.get("/api/metrics")
def get_metrics() -> dict[str, object]:
    return repository.metrics()


@app.get("/api/policies")
def get_policies() -> list[dict[str, object]]:
    return repository.policies()


@app.get("/api/mandarin")
def get_mandarin() -> dict[str, object]:
    return repository.mandarin_lab()


@app.get("/api/policy-studio")
def get_policy_studio() -> dict[str, object]:
    return repository.policy_studio()


@app.get("/api/strategies")
def get_strategies() -> dict[str, object]:
    return repository.strategy_catalog()


@app.get("/api/strategy-evaluation")
def get_strategy_evaluation() -> dict[str, object]:
    return repository.evaluate_strategies()


@app.post("/api/strategy-preview")
def post_strategy_preview(payload: CandidateStrategyInput) -> dict[str, object]:
    try:
        return repository.preview_strategy(payload.risk_threshold, payload.escalation_threshold, payload.reviewer_capacity)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/strategy-evaluation")
def post_strategy_evaluation(payload: StrategyAssumptionsInput) -> dict[str, object]:
    return repository.evaluate_strategies(payload.model_dump())


@app.get("/api/benchmark-lab")
def get_benchmark_lab(include_results: bool = False) -> dict[str, object]:
    return repository.benchmark_lab(include_results=include_results)


@app.get("/api/holdout-benchmark")
def get_holdout_benchmark() -> dict[str, object]:
    return repository.holdout_benchmark()


@app.get("/api/launch-readiness")
def get_launch_readiness() -> dict[str, object]:
    return repository.launch_readiness()


@app.get("/api/public-evidence")
def get_public_evidence() -> dict[str, object]:
    return repository.public_evidence()


@app.post("/api/authorized-data/validate")
def post_authorized_data_validate(payload: AuthorizedDataBatch) -> dict[str, object]:
    return validate_authorized_batch(payload)


@app.post("/api/multimodal-text/evaluate")
def post_multimodal_text_evaluate(payload: MultimodalTextInput) -> dict[str, object]:
    return repository.multimodal_text_evaluation(payload.creative_text, payload.ocr_text, payload.asr_text)


@app.get("/api/advertiser-integrity")
def get_advertiser_integrity() -> dict[str, object]:
    return repository.advertiser_integrity()


@app.get("/api/emerging-risks")
def get_emerging_risks() -> dict[str, object]:
    return repository.emerging_risks()


@app.get("/api/operational-performance")
def get_operational_performance(sample_size: int = Query(40, ge=1, le=100)) -> dict[str, object]:
    return repository.operational_performance(sample_size)


@app.get("/api/system-provenance")
def get_system_provenance() -> dict[str, object]:
    return repository.system_provenance()


@app.get("/api/llm-comparison")
def get_llm_comparison(limit: int = Query(5, ge=1, le=20)) -> dict[str, object]:
    try:
        return repository.llm_comparison(limit, run_llm=False)
    except FileNotFoundError as exc:
        return {"status": "unavailable", "reason": str(exc), "llm_available": False, "sample_size": 0, "cases": []}


@app.post("/api/llm-comparison/run")
def run_llm_comparison(limit: int = Query(5, ge=1, le=20)) -> dict[str, object]:
    try:
        return repository.llm_comparison(limit, run_llm=True)
    except FileNotFoundError as exc:
        return {"status": "unavailable", "reason": str(exc), "llm_available": False, "sample_size": 0, "cases": []}


@app.post("/api/feedback")
def post_feedback(
    payload: FeedbackInput,
    x_reviewer_id: str = Header(min_length=1),
    x_reviewer_role: str = Header(default="reviewer"),
) -> dict[str, object]:
    try:
        return repository.save_feedback(payload.case_id, payload.decision, payload.notes, reviewer_id=x_reviewer_id, reviewer_role=x_reviewer_role)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc


dist = settings.root / "dist"
if dist.exists():
    assets = dist / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    dist_root = dist.resolve()

    @app.get("/{path:path}")
    def spa(path: str) -> FileResponse:
        candidate = (dist / path).resolve()
        if candidate.is_file() and candidate.is_relative_to(dist_root):
            return FileResponse(candidate)
        return FileResponse(dist_root / "index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.app.api:app", host="127.0.0.1", port=8501, reload=False)
