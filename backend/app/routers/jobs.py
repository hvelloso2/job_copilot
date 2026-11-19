from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session, joinedload, selectinload

from app.database import get_db
from app.dependencies import get_llm_client, llm_errors_as_http
from app.llm.client import LLMClient
from app.job_urls import canonical_job_url
from app.models import Application, ApplicationStatus, Job, JobLead, LeadStatus
from app.pipeline import apply_track, extract_job
from app.queries import get_job_or_404
from app.schemas import ApplicationUpdate, JobCreate, JobOut, JobSummary, PageImport, PageImportOut, TrackChoice

router = APIRouter(prefix="/jobs", tags=["jobs"])

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
        job = extract_job(llm, text, (payload.url or "").strip() or None)
    db.add(job)
    db.commit()
    db.refresh(job)
    return _to_out(job)


@router.post("/import", response_model=PageImportOut, status_code=201)
def import_page(
    payload: PageImport, response: Response, db: Session = Depends(get_db), llm: LLMClient = Depends(get_llm_client)
) -> PageImportOut:
    """Saves the job page sent by the browser extension (what the user is seeing; no scraping).
    The same posting is never extracted twice: if it is already on the board, that job is returned (200)."""
    url = canonical_job_url(payload.url)
    job_id = db.scalar(select(Job.id).where(Job.url.in_({url, payload.url.strip()})))
    created = job_id is None
    if created:
        text = f"Título da página: {payload.title.strip()}\nEndereço: {url}\n\n{payload.text.strip()}"
        with llm_errors_as_http():
            job = extract_job(llm, text, url)
        db.add(job)
        db.flush()
        job_id = job.id
    else:
        response.status_code = 200
    # The posting may have come from a job alert email: it is no longer "new" there.
    db.execute(update(JobLead).where(JobLead.url == url).values(status=LeadStatus.IMPORTED, job_id=job_id))
    db.commit()
    return PageImportOut(job_id=job_id, created=created)


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
    apply_track(job, payload.track)
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
