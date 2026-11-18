from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.database import get_db
from app.insights import build_insights
from app.models import Job
from app.queries import current_profile
from app.schemas import Insights

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("", response_model=Insights)
def get_insights(db: Session = Depends(get_db)) -> Insights:
    """Most requested skills vs. the profile, funnel and average score per status."""
    jobs = db.scalars(
        select(Job).join(Job.application).options(joinedload(Job.application), selectinload(Job.analyses))
    ).all()
    profile = current_profile(db)
    return build_insights(list(jobs), profile.data if profile else None)
