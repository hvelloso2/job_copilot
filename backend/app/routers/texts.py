import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis import KIND_LABEL, STATUS_LABEL, ProfileIndex
from app.database import get_db
from app.dependencies import get_llm_client, llm_errors_as_http
from app.llm.client import LLMClient
from app.llm.prompts import load_prompt
from app.llm.schemas import ClaimList, JobData, TextDraft
from app.models import Analysis, GeneratedText, TextFormat
from app.queries import current_profile, get_job_or_404
from app.schemas import AnalysisResult, TextCreate, TextOut, TextVerification
from app.texts import find_placeholders, highlight, text_warnings, verify_claims

router = APIRouter(prefix="/jobs/{job_id}/texts", tags=["texts"])


def _job_context(track: JobData) -> str:
    lines = [f"Cargo: {track.title}"]
    if track.company:
        lines.append(f"Empresa: {track.company}")
    if track.seniority:
        lines.append(f"Senioridade: {track.seniority}")
    if track.responsibilities:
        lines += ["Responsabilidades:", *(f"- {r}" for r in track.responsibilities)]
    return "\n".join(lines)


def _analysis_context(result: AnalysisResult) -> str:
    """Only the verified parts of the analysis go to the model."""
    lines = ["Requisitos:"]
    for r in result.requirements:
        line = f"- ({KIND_LABEL[r.kind]}) {r.requirement}: {STATUS_LABEL[r.status]}"
        if r.status != "missing" and r.evidence_verified:
            line += f' (evidência no perfil: "{r.evidence}")'
        lines.append(line)
    strengths = [f'- {s.point} (evidência no perfil: "{s.evidence}")' for s in result.strengths if s.evidence_verified]
    if strengths:
        lines += ["", "Pontos fortes:", *strengths]
    if result.gaps:
        lines += ["", "Lacunas:", *(f"- {g}" for g in result.gaps)]
    return "\n".join(lines)


def _to_out(item: GeneratedText) -> TextOut:
    return TextOut(
        **TextVerification.model_validate(item.details).model_dump(),
        id=item.id,
        job_id=item.job_id,
        type=item.type,
        format=item.format or TextFormat.WRITTEN,
        question=item.question,
        text=item.text,
        created_at=item.created_at,
    )


@router.post("", response_model=TextOut, status_code=201)
def generate_text(
    job_id: int, payload: TextCreate, db: Session = Depends(get_db), llm: LLMClient = Depends(get_llm_client)
) -> TextOut:
    """Generates a text from the profile and the job analysis, then checks every claim against the profile."""
    job = get_job_or_404(db, job_id)
    track_index = job.extracted.get("selected_track")
    if track_index is None:
        raise HTTPException(status_code=409, detail="Escolha a trilha da vaga antes de gerar textos.")
    profile = current_profile(db)
    if profile is None:
        raise HTTPException(status_code=409, detail="Salve o seu perfil antes de gerar textos.")
    analysis = db.scalars(
        select(Analysis).where(Analysis.job_id == job_id).order_by(Analysis.id.desc()).limit(1)
    ).first()
    if analysis is None:
        raise HTTPException(status_code=409, detail="Analise a vaga antes de gerar textos.")
    result = AnalysisResult.model_validate(analysis.result)
    if result.track != track_index:
        raise HTTPException(status_code=409, detail="A trilha mudou desde a última análise. Analise a vaga de novo.")

    track = JobData.model_validate(job.extracted["tracks"][track_index])
    profile_json = json.dumps(profile.data, ensure_ascii=False, indent=1)
    request_lines = [f"Tipo: {payload.type.value}", f"Formato: {payload.format.value}"]
    if payload.question:
        request_lines.append(f"Pergunta: {payload.question}")

    with llm_errors_as_http():
        draft = llm.create_structured(
            "generate_text",
            TextDraft,
            system=load_prompt("generate_text"),
            messages=[{"role": "user", "content": (
                f"<perfil>\n{profile_json}\n</perfil>\n\n"
                f"<vaga>\n{_job_context(track)}\n</vaga>\n\n"
                f"<analise>\n{_analysis_context(result)}\n</analise>\n\n"
                f"<pedido>\n{chr(10).join(request_lines)}\n</pedido>"
            )}],
        )
        text = draft.text.strip()
        if not text:
            raise HTTPException(status_code=502, detail="O modelo devolveu um texto vazio.")
        claims = llm.create_structured(
            "extract_claims",
            ClaimList,
            system=load_prompt("extract_claims"),
            messages=[{"role": "user", "content": f"<perfil>\n{profile_json}\n</perfil>\n\n<texto>\n{text}\n</texto>"}],
        )

    index = ProfileIndex(profile.data)
    checked = verify_claims(text, claims, track, index)
    verification = TextVerification(
        highlighted_text=highlight(text, checked),
        placeholders=find_placeholders(text),
        claims=checked,
        unsupported_claims=sum(not c.supported for c in checked),
        warnings=text_warnings(text, track, index, checked),
        profile_version=profile.version,
        analysis_id=analysis.id,
    )
    item = GeneratedText(
        job=job, type=payload.type, format=payload.format, question=payload.question,
        text=text, details=verification.model_dump(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _to_out(item)


@router.get("", response_model=list[TextOut])
def list_texts(job_id: int, db: Session = Depends(get_db)) -> list[TextOut]:
    """History of texts generated for the job, most recent first."""
    get_job_or_404(db, job_id)
    items = db.scalars(
        select(GeneratedText)
        .where(GeneratedText.job_id == job_id, GeneratedText.details.is_not(None))
        .order_by(GeneratedText.id.desc())
    ).all()
    return [_to_out(item) for item in items]
