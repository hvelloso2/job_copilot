from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.database import get_db
from app.dependencies import get_llm_client, llm_errors_as_http
from app.llm.client import LLMClient
from app.llm.prompts import load_prompt
from app.llm.schemas import JobData, JobExtraction
from app.models import Application, ApplicationStatus, Job
from app.queries import get_job_or_404
from app.schemas import ApplicationUpdate, JobCreate, JobOut, JobSummary, TrackChoice

router = APIRouter(prefix="/jobs", tags=["jobs"])

# Job.extracted = {"tracks": [JobData, ...], "selected_track": int | None}
# A posting with a single track is selected automatically; with several, the user picks one.


def _apply_track(job: Job, index: int | None) -> None:
    tracks = [JobData.model_validate(t) for t in job.extracted["tracks"]]
    job.extracted = {**job.extracted, "selected_track": index}
    if index is not None:
        job.company = tracks[index].company or ""
        job.title = tracks[index].title
    else:
        job.company = next((t.company for t in tracks if t.company), "") or ""
        job.title = " | ".join(t.title for t in tracks)


def _latest_score(job: Job) -> int | None:
    if not job.analyses:
        return None
    return max(job.analyses, key=lambda a: a.id).result.get("score")


def _summary_fields(job: Job) -> dict:
    return {
        "id": job.id,
        "company": job.company,
        "title": job.title,
        "status": job.application.status,
        "needs_track_choice": job.extracted.get("selected_track") is None,
        "score": _latest_score(job),
        "created_at": job.created_at,
        "updated_at": job.application.updated_at,
    }


def _to_out(job: Job) -> JobOut:
    return JobOut(
        **_summary_fields(job),
        url=job.url,
        raw_text=job.raw_text,
        tracks=job.extracted["tracks"],
        selected_track=job.extracted.get("selected_track"),
        status_history=job.application.status_history or [],
        notes=job.application.notes or "",
    )


@router.post("", response_model=JobOut, status_code=201)
def create_job(
    payload: JobCreate, db: Session = Depends(get_db), llm: LLMClient = Depends(get_llm_client)
) -> JobOut:
    """Extracts the posting with Claude and saves it, with an Application in status "saved"."""
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Cole o texto da vaga.")

    with llm_errors_as_http():
        extraction = llm.create_structured(
            "extract_job",
            JobExtraction,
            system=load_prompt("extract_job"),
            messages=[{"role": "user", "content": f"<vaga>\n{text}\n</vaga>"}],
        )

    job = Job(
        raw_text=text,
        url=(payload.url or "").strip() or None,
        extracted={"tracks": [t.model_dump() for t in extraction.tracks], "selected_track": None},
    )
    _apply_track(job, 0 if len(extraction.tracks) == 1 else None)
    application = Application(job=job)
    application.set_status(ApplicationStatus.SAVED)
    db.add(job)
    db.commit()
    db.refresh(job)
    return _to_out(job)


@router.get("", response_model=list[JobSummary])
def list_jobs(status: ApplicationStatus | None = None, db: Session = Depends(get_db)) -> list[JobSummary]:
    """Lists jobs, most recent first. `status` filters by the application status."""
    query = select(Job).join(Job.application).options(joinedload(Job.application), selectinload(Job.analyses))
    if status is not None:
        query = query.where(Application.status == status)
    jobs = db.scalars(query.order_by(Job.created_at.desc(), Job.id.desc())).all()
    return [JobSummary(**_summary_fields(job)) for job in jobs]


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db)) -> JobOut:
    return _to_out(get_job_or_404(db, job_id))


@router.put("/{job_id}/track", response_model=JobOut)
def choose_track(job_id: int, payload: TrackChoice, db: Session = Depends(get_db)) -> JobOut:
    """Chooses which track of a multi-track posting to follow (used by the analysis and texts)."""
    job = get_job_or_404(db, job_id)
    if payload.track >= len(job.extracted["tracks"]):
        raise HTTPException(status_code=422, detail="Essa trilha não existe nesta vaga.")
    _apply_track(job, payload.track)
    db.commit()
    db.refresh(job)
    return _to_out(job)


@router.patch("/{job_id}/application", response_model=JobOut)
def update_application(job_id: int, payload: ApplicationUpdate, db: Session = Depends(get_db)) -> JobOut:
    """Moves the application to another status (kanban) and/or saves the notes."""
    job = get_job_or_404(db, job_id)
    application = job.application
    if payload.status is not None and payload.status != application.status:
        application.set_status(payload.status)
    if payload.notes is not None:
        application.notes = payload.notes
    db.commit()
    db.refresh(job)
    return _to_out(job)


@router.delete("/{job_id}", status_code=204)
def delete_job(job_id: int, db: Session = Depends(get_db)) -> Response:
    """Deletes the job with its application, analyses and texts (e.g. a wrong extraction)."""
    db.delete(get_job_or_404(db, job_id))
    db.commit()
    return Response(status_code=204)
