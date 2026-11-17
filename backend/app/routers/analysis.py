import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis import KIND_LABEL, build_analysis, numbered_requirements
from app.database import get_db
from app.dependencies import get_llm_client, llm_errors_as_http
from app.llm.client import LLMClient
from app.llm.prompts import load_prompt
from app.llm.schemas import JobAnalysis, JobData
from app.models import Analysis
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
    track_index = job.extracted.get("selected_track")
    if track_index is None:
        raise HTTPException(status_code=409, detail="Escolha a trilha da vaga antes de analisar.")
    profile = current_profile(db)
    if profile is None:
        raise HTTPException(status_code=409, detail="Salve o seu perfil antes de analisar uma vaga.")

    track = JobData.model_validate(job.extracted["tracks"][track_index])
    requirements = numbered_requirements(track)
    if not requirements:
        raise HTTPException(status_code=422, detail="A vaga não tem requisitos extraídos para analisar.")

    requirement_lines = "\n".join(f"{r.id} ({KIND_LABEL[r.kind]}): {r.text}" for r in requirements)
    content = (
        f"<data_de_hoje>{date.today().isoformat()}</data_de_hoje>\n\n"
        f"<perfil>\n{json.dumps(profile.data, ensure_ascii=False, indent=1)}\n</perfil>\n\n"
        f"<vaga>\nCargo: {track.title}\n\nRequisitos:\n{requirement_lines}\n</vaga>"
    )
    with llm_errors_as_http():
        output = llm.create_structured(
            "analyze_job",
            JobAnalysis,
            system=load_prompt("analyze_job"),
            messages=[{"role": "user", "content": content}],
        )

    result = build_analysis(output, track_index, track, profile.data)
    analysis = Analysis(job=job, profile_version=profile.version, result=result.model_dump())
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
