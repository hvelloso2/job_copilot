"""Dashboard numbers (Etapa 7): most requested skills vs. the profile, funnel and scores.

Everything here is computed in code from saved data. No LLM call.
"""

from collections import Counter, defaultdict
from statistics import mean
from typing import Any

from app.analysis import ProfileIndex, normalize
from app.llm.schemas import JobData
from app.models import ApplicationStatus, Job
from app.schemas import FunnelStep, Insights, SkillDemand, StatusScore

# Equivalent names: canonical name shown in the dashboard -> other spellings.
# Matching is case-insensitive (see `skill_key`), so only list real variations.
SYNONYMS: dict[str, list[str]] = {
    "PostgreSQL": ["Postgres", "Postgre", "PSQL"],
    "JavaScript": ["JS", "ECMAScript", "ES6"],
    "TypeScript": ["TS"],
    "React": ["React.js", "ReactJS", "React JS"],
    "React Native": ["React-Native"],
    "Node.js": ["Node", "NodeJS", "Node JS"],
    "Next.js": ["NextJS"],
    "Vue.js": ["Vue", "VueJS"],
    "Angular": ["AngularJS", "Angular.js"],
    "Express": ["Express.js", "ExpressJS"],
    "NestJS": ["Nest.js"],
    "Python": ["Python 3", "Python3"],
    "C#": ["CSharp", "C Sharp"],
    ".NET": ["dotnet", ".NET Core", "ASP.NET", "ASP.NET Core"],
    "Golang": ["Go"],
    "Kubernetes": ["K8s"],
    "Docker": ["Docker Compose", "Containers Docker"],
    "AWS": ["Amazon Web Services"],
    "GCP": ["Google Cloud", "Google Cloud Platform"],
    "Azure": ["Microsoft Azure"],
    "MongoDB": ["Mongo"],
    "SQL Server": ["MSSQL", "Microsoft SQL Server"],
    "MySQL": ["My SQL"],
    "CI/CD": ["CI CD", "CICD", "Continuous Integration"],
    "Git": ["Git/GitHub", "Versionamento com Git"],
    "REST": ["REST API", "REST APIs", "RESTful", "APIs REST", "API REST", "APIs RESTful"],
    "Tailwind CSS": ["Tailwind", "TailwindCSS"],
    "Machine Learning": ["ML", "Aprendizado de Máquina"],
    "LLM": ["LLMs", "Large Language Models"],
    "Power BI": ["PowerBI"],
    "scikit-learn": ["sklearn", "scikit learn"],
    "FastAPI": ["Fast API"],
    "Spring Boot": ["Spring", "SpringBoot"],
}

_ALIAS_TO_CANONICAL: dict[str, str] = {
    normalize(name): canonical for canonical, aliases in SYNONYMS.items() for name in [canonical, *aliases]
}

FUNNEL_STAGES = [
    ApplicationStatus.SAVED,
    ApplicationStatus.APPLIED,
    ApplicationStatus.TEST,
    ApplicationStatus.INTERVIEW,
    ApplicationStatus.OFFER,
]
_STAGE_ORDER = {status.value: i for i, status in enumerate(FUNNEL_STAGES)}


def skill_key(name: str) -> str:
    """Key that groups equivalent names: the canonical name if listed, else the normalized name."""
    normalized = normalize(name).strip(" .,;:")
    return _ALIAS_TO_CANONICAL.get(normalized, normalized)


def _job_technologies(job: Job) -> list[str]:
    """Technologies of the chosen track; while no track is chosen, of all tracks."""
    tracks = [JobData.model_validate(t) for t in job.extracted.get("tracks", [])]
    selected = job.extracted.get("selected_track")
    if selected is not None and selected < len(tracks):
        tracks = [tracks[selected]]
    return [tech for track in tracks for tech in track.technologies]


def _in_profile(key: str, index: ProfileIndex | None) -> bool:
    if index is None:
        return False
    names = [key, *SYNONYMS.get(key, [])]
    return any(index.mentions(name) for name in names)


def skill_demand(jobs: list[Job], profile_data: dict[str, Any] | None) -> list[SkillDemand]:
    """How many saved jobs ask for each skill (each job counts once), most requested first."""
    counts: Counter[str] = Counter()
    spellings: dict[str, Counter[str]] = defaultdict(Counter)
    for job in jobs:
        keys_in_job = set()
        for tech in _job_technologies(job):
            key = skill_key(tech)
            if not key:
                continue
            spellings[key][tech.strip()] += 1
            keys_in_job.add(key)
        counts.update(keys_in_job)

    index = ProfileIndex(profile_data) if profile_data is not None else None
    total = len(jobs)
    result = [
        SkillDemand(
            name=key if key in SYNONYMS else spellings[key].most_common(1)[0][0],
            count=count,
            share=round(100 * count / total) if total else 0,
            in_profile=_in_profile(key, index),
        )
        for key, count in counts.items()
    ]
    result.sort(key=lambda s: (-s.count, s.name.casefold()))
    return result


def _furthest_stage(job: Job) -> int:
    """Furthest funnel stage the application reached (history included, so 'closed' keeps its past)."""
    application = job.application
    statuses = [entry.get("status") for entry in application.status_history or []]
    statuses.append(application.status.value)
    return max((_STAGE_ORDER[s] for s in statuses if s in _STAGE_ORDER), default=0)


def funnel(jobs: list[Job]) -> list[FunnelStep]:
    """Applications per current status and how many reached each stage.

    A stage counts as reached when the application was there or went further
    (an interview without a test still passed the "test" step). The rate is
    reached(this stage) / reached(previous stage).
    """
    current = Counter(job.application.status for job in jobs)
    furthest = [_furthest_stage(job) for job in jobs]
    steps = []
    previous_reached = None
    for order, status in enumerate(FUNNEL_STAGES):
        reached = sum(1 for f in furthest if f >= order)
        rate = None
        if previous_reached:
            rate = round(100 * reached / previous_reached)
        steps.append(FunnelStep(status=status, current=current[status], reached=reached, rate_from_previous=rate))
        previous_reached = reached
    steps.append(
        FunnelStep(
            status=ApplicationStatus.CLOSED,
            current=current[ApplicationStatus.CLOSED],
            reached=current[ApplicationStatus.CLOSED],
            rate_from_previous=None,
        )
    )
    return steps


def _latest_score(job: Job) -> int | None:
    if not job.analyses:
        return None
    return max(job.analyses, key=lambda a: a.id).result.get("score")


def scores_by_status(jobs: list[Job]) -> list[StatusScore]:
    """Average compatibility score (latest analysis of each job) per current status."""
    scores: dict[ApplicationStatus, list[int]] = defaultdict(list)
    totals = Counter(job.application.status for job in jobs)
    for job in jobs:
        score = _latest_score(job)
        if score is not None:
            scores[job.application.status].append(score)
    return [
        StatusScore(
            status=status,
            average=round(mean(scores[status])) if scores[status] else None,
            analyzed=len(scores[status]),
            total=totals[status],
        )
        for status in ApplicationStatus
    ]


def build_insights(jobs: list[Job], profile_data: dict[str, Any] | None) -> Insights:
    skills = skill_demand(jobs, profile_data)
    return Insights(
        total_jobs=len(jobs),
        has_profile=profile_data is not None,
        skills=skills,
        top_gaps=[s for s in skills if not s.in_profile][:10],
        funnel=funnel(jobs),
        scores_by_status=scores_by_status(jobs),
    )
