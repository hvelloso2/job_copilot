from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_llm_client, llm_errors_as_http
from app.llm.client import LLMClient
from app.llm.prompts import load_prompt
from app.llm.schemas import ProfileData
from app.models import Profile
from app.pdf import PdfError, extract_pdf_text
from app.queries import current_profile
from app.schemas import ProfileDraft, ProfileOut, ProfileSave

router = APIRouter(prefix="/profile", tags=["profile"])

MAX_UPLOAD_BYTES = 5 * 1024 * 1024


@router.post("/upload", response_model=ProfileDraft)
async def upload_profile(file: UploadFile, llm: LLMClient = Depends(get_llm_client)) -> ProfileDraft:
    """Extracts a structured profile from a PDF résumé. Does NOT save: the user reviews first."""
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="O PDF passa de 5 MB.")
    if not content.startswith(b"%PDF"):
        raise HTTPException(status_code=415, detail="Envie um arquivo PDF.")

    try:
        raw_text = extract_pdf_text(content)
    except PdfError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    with llm_errors_as_http():
        data = llm.create_structured(
            "extract_profile",
            ProfileData,
            system=load_prompt("extract_profile"),
            messages=[{"role": "user", "content": f"<curriculo>\n{raw_text}\n</curriculo>"}],
        )

    return ProfileDraft(data=data, raw_text=raw_text)


@router.put("", response_model=ProfileOut)
def save_profile(payload: ProfileSave, db: Session = Depends(get_db)) -> ProfileOut:
    """Saves the reviewed profile. Each save creates a new version (analyses record which one they used)."""
    profile = current_profile(db)
    if profile is None:
        profile = Profile(version=1)
        db.add(profile)
    else:
        profile.version += 1
    profile.data = payload.data.model_dump()
    profile.raw_text = payload.raw_text
    db.commit()
    db.refresh(profile)
    return ProfileOut(data=profile.data, raw_text=profile.raw_text,
                      version=profile.version, updated_at=profile.updated_at)


@router.get("", response_model=ProfileOut)
def get_profile(db: Session = Depends(get_db)) -> ProfileOut:
    profile = current_profile(db)
    if profile is None:
        raise HTTPException(status_code=404, detail="Nenhum perfil salvo ainda.")
    return ProfileOut(data=profile.data, raw_text=profile.raw_text,
                      version=profile.version, updated_at=profile.updated_at)
