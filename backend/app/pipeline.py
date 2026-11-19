"""Job extraction and analysis with Claude, shared by the API routes (pasted text, browser extension).

These functions build the database objects but never commit: the caller decides.
Claude errors (LLMOutputError, anthropic errors) propagate to the caller.
"""

import json
from datetime import date

from app.analysis import KIND_LABEL, build_analysis, numbered_requirements
from app.llm.client import LLMClient
from app.llm.prompts import load_prompt
from app.llm.schemas import JobAnalysis, JobData, JobExtraction
from app.models import Analysis, Application, ApplicationStatus, Job, Profile

# Job.extracted = {"tracks": [JobData, ...], "selected_track": int | None}
# A posting with a single track is selected automatically; with several, the user picks one.


def apply_track(job: Job, index: int | None) -> None:
    tracks = [JobData.model_validate(t) for t in job.extracted["tracks"]]
    job.extracted = {**job.extracted, "selected_track": index}
    if index is not None:
        job.company = tracks[index].company or ""
        job.title = tracks[index].title
    else:
        job.company = next((t.company for t in tracks if t.company), "") or ""
        job.title = " | ".join(t.title for t in tracks)


def extract_job(
    llm: LLMClient, text: str, url: str | None, status: ApplicationStatus = ApplicationStatus.SAVED
) -> Job:
    """Extracts the posting with Claude. Returns a new Job with its Application (not added to a session)."""
    extraction = llm.create_structured(
        "extract_job",
        JobExtraction,
        system=load_prompt("extract_job"),
        messages=[{"role": "user", "content": f"<vaga>\n{text}\n</vaga>"}],
    )
    job = Job(
        raw_text=text,
        url=url,
        extracted={"tracks": [t.model_dump() for t in extraction.tracks], "selected_track": None},
    )
    apply_track(job, 0 if len(extraction.tracks) == 1 else None)
    application = Application(job=job)
    application.set_status(status)
    return job


def selected_track(job: Job) -> JobData | None:
    index = job.extracted.get("selected_track")
    if index is None:
        return None
    return JobData.model_validate(job.extracted["tracks"][index])


def can_analyze(job: Job) -> bool:
    """A track is chosen and it has requirements."""
    track = selected_track(job)
    return track is not None and bool(numbered_requirements(track))


def analyze_job(llm: LLMClient, job: Job, profile: Profile) -> Analysis:
    """Compares the profile with the chosen track. Evidence and score are checked in code.
    Requires can_analyze(job)."""
    track_index = job.extracted["selected_track"]
    track = JobData.model_validate(job.extracted["tracks"][track_index])
    requirement_lines = "\n".join(f"{r.id} ({KIND_LABEL[r.kind]}): {r.text}" for r in numbered_requirements(track))
    content = (
        f"<data_de_hoje>{date.today().isoformat()}</data_de_hoje>\n\n"
        f"<perfil>\n{json.dumps(profile.data, ensure_ascii=False, indent=1)}\n</perfil>\n\n"
        f"<vaga>\nCargo: {track.title}\n\nRequisitos:\n{requirement_lines}\n</vaga>"
    )
    output = llm.create_structured(
        "analyze_job",
        JobAnalysis,
        system=load_prompt("analyze_job"),
        messages=[{"role": "user", "content": content}],
    )
    result = build_analysis(output, track_index, track, profile.data)
    return Analysis(job=job, profile_version=profile.version, result=result.model_dump())
