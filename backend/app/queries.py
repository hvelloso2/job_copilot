"""Small DB lookups shared by the routers."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Job, Profile


def current_profile(db: Session) -> Profile | None:
    return db.scalars(select(Profile).order_by(Profile.id).limit(1)).first()


def get_job_or_404(db: Session, job_id: int) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Vaga não encontrada.")
    return job
