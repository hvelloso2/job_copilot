from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_llm_client, llm_errors_as_http
from app.llm.client import LLMClient
from app.models import Analysis
from app.pipeline import analyze_job as run_analysis
from app.pipeline import can_analyze
from app.queries import current_profile, get_job_or_404
from app.schemas import AnalysisOut, AnalysisResult

router = APIRouter(prefix="/jobs/{job_id}/analysis", tags=["analysis"])


def _to_out(analysis: Analysis, current_version: int | None) -> AnalysisOut:
    return AnalysisOut(
        **AnalysisResult.model_validate(analysis.result).model_dump(),
        id=analysis.id,
        job_id=analysis.job_id,
        profile_version=analysis.profile_version,
        outdated=current_version is not None and current_version != analysis.profile_version,
        created_at=analysis.created_at,
    )


@router.post("", response_model=AnalysisOut, status_code=201)
def analyze_job(
    job_id: int, db: Session = Depends(get_db), llm: LLMClient = Depends(get_llm_client)
) -> AnalysisOut:
    """Compares the saved profile with the chosen track of the job. Evidence and score are checked in code."""
    job = get_job_or_404(db, job_id)
    if job.extracted.get("selected_track") is None:
        raise HTTPException(status_code=409, detail="Escolha a trilha da vaga antes de analisar.")
    profile = current_profile(db)
    if profile is None:
        raise HTTPException(status_code=409, detail="Salve o seu perfil antes de analisar uma vaga.")
    if not can_analyze(job):
        raise HTTPException(status_code=422, detail="A vaga não tem requisitos extraídos para analisar.")

    with llm_errors_as_http():
        analysis = run_analysis(llm, job, profile)
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return _to_out(analysis, profile.version)


@router.get("", response_model=AnalysisOut)
def latest_analysis(job_id: int, db: Session = Depends(get_db)) -> AnalysisOut:
    """The most recent analysis of the job. `outdated` is true if the profile changed since then."""
    get_job_or_404(db, job_id)
    analysis = db.scalars(
        select(Analysis).where(Analysis.job_id == job_id).order_by(Analysis.id.desc()).limit(1)
    ).first()
    if analysis is None:
        raise HTTPException(status_code=404, detail="Esta vaga ainda não foi analisada.")
    profile = current_profile(db)
    return _to_out(analysis, profile.version if profile else None)
