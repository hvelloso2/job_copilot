"""Runs the AI evaluation against the REAL Claude API (costs money) and writes the report.

Usage, from backend/ with the virtual environment active:
    python -m evals.run_evals                          # models from ANTHROPIC_MODEL / ANTHROPIC_MODELS
    python -m evals.run_evals --model claude-haiku-5-5 --label "haiku"
    python -m evals.run_evals --jobs 01,09 --no-texts  # quick, cheaper run

It goes through the same API routes the app uses (FastAPI TestClient), with a temporary
in-memory database and the fictional profile in evals/fixtures/. Your real database is never used.
Each run is saved in evals/runs/ and evals/results.md is rebuilt with all runs.
"""

import argparse
import json
import os
import sys
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

os.environ["DATABASE_URL"] = "sqlite:///:memory:"  # before importing the app: never touch data/

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.config import Settings, get_settings  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.dependencies import get_llm_client  # noqa: E402
from app.llm.client import LLMClient, LLMOutputError  # noqa: E402
from app.llm.schemas import JobData  # noqa: E402
from app.main import app  # noqa: E402
from app.texts import audit_text  # noqa: E402
from evals import scoring  # noqa: E402

EVALS_DIR = Path(__file__).parent
FIXTURES = EVALS_DIR / "fixtures"
RUNS_DIR = EVALS_DIR / "runs"
RESULTS = EVALS_DIR / "results.md"


def pct(value: float | None) -> str:
    return "—" if value is None else f"{100 * value:.0f}%"


def ratio(num: int, den: int) -> float | None:
    return num / den if den else None


def usd(value: float | None) -> str:
    return "—" if value is None else f"US$ {value:.4f}"


def load_fixtures(only: set[str] | None) -> tuple[dict, list[dict], dict]:
    profile = json.loads((FIXTURES / "profile.json").read_text(encoding="utf-8"))
    jobs = []
    for posting in sorted((FIXTURES / "jobs").glob("*.txt")):
        job_id = posting.stem
        if only and job_id.split("-")[0] not in only:
            continue
        expected = json.loads(posting.with_suffix(".expected.json").read_text(encoding="utf-8"))
        jobs.append({"id": job_id, "text": posting.read_text(encoding="utf-8"), "expected": expected})
    planted = json.loads((FIXTURES / "planted_texts.json").read_text(encoding="utf-8"))
    return profile, jobs, planted


def make_client(model: str, fallbacks: str, models: str = "") -> LLMClient:
    base = get_settings()
    settings = Settings(
        anthropic_api_key=base.anthropic_api_key, anthropic_model=model, anthropic_models=models,
        anthropic_fallbacks=fallbacks, database_url="sqlite:///:memory:",
    )
    return LLMClient(settings=settings)


def describe_models(llm: LLMClient) -> str:
    """'default' or 'default (op1, op2: model; op3: model)'."""
    by_model: dict[str, list[str]] = {}
    for operation, model in llm.operation_models.items():
        if model != llm.model:
            by_model.setdefault(model, []).append(operation)
    if not by_model:
        return llm.model
    parts = "; ".join(f"{', '.join(ops)}: {model}" for model, ops in by_model.items())
    return f"{llm.model} ({parts})"


def run_job(api: TestClient, job: dict, with_texts: bool) -> dict[str, Any]:
    out: dict[str, Any] = {"id": job["id"], "errors": []}
    expected = job["expected"]

    response = api.post("/jobs", json={"text": job["text"]})
    if response.status_code != 201:
        out["errors"].append(f"extração: {response.status_code} {response.json().get('detail')}")
        return out
    created = response.json()
    tracks = created["tracks"]
    index = scoring.pick_track(tracks, expected.get("track"))
    if index is None:
        out["errors"].append(f"trilha '{expected.get('track')}' não encontrada entre {[t['title'] for t in tracks]}")
        index = 0
    if created["selected_track"] != index:
        api.put(f"/jobs/{created['id']}/track", json={"track": index})

    extraction = scoring.score_extraction(tracks[index], expected, len(tracks))
    out["extraction"] = asdict(extraction) | {"coverage": extraction.coverage, "precision": extraction.precision}

    response = api.post(f"/jobs/{created['id']}/analysis")
    if response.status_code != 201:
        out["errors"].append(f"análise: {response.status_code} {response.json().get('detail')}")
        return out
    analysis = response.json()
    out["score"] = analysis["score"]
    out["evidence_rejected"] = analysis["verification"]["evidence_rejected"]
    out["analysis_cases"] = [asdict(c) | {"correct": c.correct} for c in scoring.score_analysis(
        analysis["requirements"], expected.get("analysis", []))]

    if with_texts:
        response = api.post(f"/jobs/{created['id']}/texts", json={"type": "cover_letter"})
        if response.status_code != 201:
            out["errors"].append(f"texto: {response.status_code} {response.json().get('detail')}")
        else:
            text = response.json()
            out["text"] = {
                "claims": len(text["claims"]),
                "unsupported": text["unsupported_claims"],
                "warnings": text["warnings"],
                "placeholders": len(text["placeholders"]),
                "highlighted": text["highlighted_text"],
            }
    return out


def run_planted(llm: LLMClient, profile: dict, planted: dict) -> list[dict[str, Any]]:
    results = []
    for i, case in enumerate(planted["texts"], start=1):
        track = JobData(title="Vaga de teste", technologies=case["job_technologies"])
        try:
            claims, warnings = audit_text(llm, case["text"], track, profile)
        except LLMOutputError as exc:
            results.append({"case": i, "error": str(exc)})
            continue
        score = scoring.score_planted(case, [c.model_dump() for c in claims], warnings)
        results.append({"case": i, **asdict(score)})
    return results


def summarize(jobs: list[dict], planted: list[dict], costs: list[dict]) -> dict[str, Any]:
    ext = [j["extraction"] for j in jobs if "extraction" in j]
    cases = [c for j in jobs for c in j.get("analysis_cases", [])]
    texts = [j["text"] for j in jobs if "text" in j]
    ok_planted = [p for p in planted if "error" not in p]
    cost_by_op = {row["operation"]: row["cost_usd"] for row in costs}
    per_job = [cost_by_op.get(op) for op in ("extract_job", "analyze_job")]
    per_text = [cost_by_op.get(op) for op in ("generate_text", "extract_claims")]
    return {
        "coverage": ratio(sum(e["found"] for e in ext), sum(e["expected"] for e in ext)),
        "precision": ratio(sum(e["extracted_valid"] for e in ext), sum(e["extracted"] for e in ext)),
        "kind_accuracy": ratio(sum(e["kind_correct"] for e in ext), sum(e["kind_checked"] for e in ext)),
        "tracks_ok": f"{sum(e['tracks_ok'] for e in ext)}/{len(ext)}",
        "analysis_accuracy": ratio(sum(c["correct"] for c in cases), len(cases)),
        "analysis_cases": len(cases),
        "planted_caught": ratio(sum(p["caught"] for p in ok_planted), sum(p["fabricated"] for p in ok_planted)),
        "planted_false_alarms": ratio(sum(p["false_alarms"] for p in ok_planted), sum(p["true_statements"] for p in ok_planted)),
        "texts": len(texts),
        "text_claims": sum(t["claims"] for t in texts),
        "text_unsupported": sum(t["unsupported"] for t in texts),
        "text_warnings": sum(len(t["warnings"]) for t in texts),
        "cost_per_job": sum(per_job) if all(c is not None for c in per_job) else None,
        "cost_per_text": sum(per_text) if all(c is not None for c in per_text) else None,
        "errors": sum(len(j["errors"]) for j in jobs) + sum("error" in p for p in planted),
    }


def render_run(run: dict[str, Any]) -> str:
    s = run["summary"]
    lines = [
        f"# Avaliação — {run['model']} — {run['started']}",
        "",
        f"Rótulo: {run['label'] or '—'} · Vagas: {len(run['jobs'])} · Tempo total: {run['seconds']:.0f}s · "
        f"Custo estimado: {usd(run['total_cost'])}",
    ]
    if not run["fixtures_reviewed"]:
        lines += ["", "> **Atenção:** o gabarito ainda não foi revisado à mão (`reviewed: false`). Os números são provisórios."]
    lines += [
        "",
        "## Resumo",
        "",
        "| Medida | Resultado |",
        "|---|---|",
        f"| Extração: cobertura (requisitos esperados encontrados) | {pct(s['coverage'])} |",
        f"| Extração: precisão (extraídos que existem na vaga) | {pct(s['precision'])} |",
        f"| Extração: obrigatório/desejável correto | {pct(s['kind_accuracy'])} |",
        f"| Extração: número de trilhas correto | {s['tracks_ok']} |",
        f"| Análise: casos claros acertados | {pct(s['analysis_accuracy'])} de {s['analysis_cases']} |",
        f"| Verificação: invenções plantadas pegas | {pct(s['planted_caught'])} |",
        f"| Verificação: afirmações verdadeiras marcadas por engano | {pct(s['planted_false_alarms'])} |",
        f"| Textos gerados: afirmações sem suporte marcadas | {s['text_unsupported']} de {s['text_claims']} (em {s['texts']} textos) |",
        f"| Textos gerados: avisos de skill/número fora do perfil | {s['text_warnings']} |",
        f"| Custo por vaga (extração + análise) | {usd(s['cost_per_job'])} |",
        f"| Custo por texto (geração + verificação) | {usd(s['cost_per_text'])} |",
        f"| Erros | {s['errors']} |",
        "",
        "## Por vaga",
        "",
        "| Vaga | Cobertura | Precisão | Análise | Nota | Não encontrados | Extraídos sem gabarito |",
        "|---|---|---|---|---|---|---|",
    ]
    for job in run["jobs"]:
        e = job.get("extraction")
        cases = job.get("analysis_cases", [])
        lines.append(
            f"| {job['id']} | {pct(e and e['coverage'])} | {pct(e and e['precision'])} | "
            f"{sum(c['correct'] for c in cases)}/{len(cases)} | {job.get('score', '—')} | "
            f"{', '.join(e['missed']) if e else '—'} | {', '.join(e['invented']) if e else '—'} |"
        )
    wrong = [(job["id"], c) for job in run["jobs"] for c in job.get("analysis_cases", []) if not c["correct"]]
    if wrong:
        lines += ["", "## Análise: casos errados", ""]
        lines += [f"- {jid}: “{c['requirement'] or 'requisito não encontrado'}” — esperado {c['expected']}, veio {c['got']}"
                  for jid, c in wrong]
    lines += ["", "## Verificação: textos com invenções plantadas", ""]
    for p in run["planted"]:
        if "error" in p:
            lines.append(f"- Texto {p['case']}: erro — {p['error']}")
        else:
            lines.append(f"- Texto {p['case']}: {p['caught']}/{p['fabricated']} pegas"
                         + (f"; escaparam: {', '.join(p['missed'])}" if p["missed"] else "")
                         + (f"; verdadeiras marcadas: {', '.join(p['flagged_true'])}" if p["flagged_true"] else ""))
    lines += ["", "## Custo por operação (média por chamada)", "",
              "| Operação | Chamadas | Tokens entrada | Tokens saída | Tempo | Custo |", "|---|---|---|---|---|---|"]
    lines += [f"| {r['operation']} | {r['calls']} | {r['input_tokens']} | {r['output_tokens']} | {r['seconds']}s | {usd(r['cost_usd'])} |"
              for r in run["costs"]]
    errors = [f"- {job['id']}: {err}" for job in run["jobs"] for err in job["errors"]]
    if errors:
        lines += ["", "## Erros", "", *errors]
    lines += ["", "Custos estimados com a tabela de preços em `evals/scoring.py` (US$ por milhão de tokens)."]
    return "\n".join(lines) + "\n"


def rebuild_results() -> None:
    runs = sorted((json.loads(p.read_text(encoding="utf-8")) for p in RUNS_DIR.glob("*.json")),
                  key=lambda r: r["started"])
    lines = [
        "# Resultados da avaliação da IA",
        "",
        "Gerado por `python -m evals.run_evals`. Cada linha é uma rodada; o relatório completo está em `evals/runs/`.",
        "Perfil fictício e vagas em `evals/fixtures/`. Custos são estimativas.",
        "",
        "| Data | Modelo | Rótulo | Vagas | Cobertura | Precisão | Análise | Invenções pegas | Falsos alarmes | Custo/vaga | Custo/texto |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in runs:
        s = r["summary"]
        flag = "" if r["fixtures_reviewed"] else " *"
        lines.append(
            f"| {r['started']}{flag} | {r['model']} | {r['label'] or '—'} | {len(r['jobs'])} | {pct(s['coverage'])} | "
            f"{pct(s['precision'])} | {pct(s['analysis_accuracy'])} | {pct(s['planted_caught'])} | "
            f"{pct(s['planted_false_alarms'])} | {usd(s['cost_per_job'])} | {usd(s['cost_per_text'])} |"
        )
    if any(not r["fixtures_reviewed"] for r in runs):
        lines += ["", "\\* gabarito ainda não revisado à mão: números provisórios."]
    RESULTS.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # Windows terminals default to cp1252
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Avaliação da IA do job-copilot (usa a API real).")
    parser.add_argument("--model", default=None,
                        help="um modelo para todas as operações (ignora ANTHROPIC_MODELS)")
    parser.add_argument("--models", default=None,
                        help="modelo por operação, ex.: extract_job=claude-haiku-5-5 (padrão: ANTHROPIC_MODELS)")
    parser.add_argument("--fallbacks", default=None, help="padrão: ANTHROPIC_FALLBACKS; desligado no Haiku")
    parser.add_argument("--label", default="", help="rótulo da rodada, ex.: 'prompt v2'")
    parser.add_argument("--jobs", default="", help="só estas vagas, ex.: 01,09")
    parser.add_argument("--no-texts", action="store_true", help="não gera textos (mais barato)")
    parser.add_argument("--no-planted", action="store_true", help="pula os textos com invenções plantadas")
    parser.add_argument("--yes", action="store_true", help="não pede confirmação")
    args = parser.parse_args()

    model = args.model or settings.anthropic_model
    if not model:
        print("Defina ANTHROPIC_MODEL no .env ou use --model.")
        return 1
    # --model alone compares a single model; otherwise the per-operation mix of the .env applies.
    models = args.models if args.models is not None else ("" if args.model else settings.anthropic_models)
    fallbacks = args.fallbacks if args.fallbacks is not None else settings.anthropic_fallbacks
    try:
        llm = make_client(model, fallbacks, models)
    except ValueError as exc:
        print(exc)
        return 1
    description = describe_models(llm)

    only = {j.strip().zfill(2) for j in args.jobs.split(",") if j.strip()} or None
    profile, jobs, planted = load_fixtures(only)
    calls = len(jobs) * (2 + (0 if args.no_texts else 2)) + (0 if args.no_planted else len(planted["texts"]))
    reviewed = all(j["expected"].get("reviewed") for j in jobs) and planted.get("reviewed", False)
    print(f"Modelo: {description} · {len(jobs)} vagas · cerca de {calls} chamadas à API (custa dinheiro).")
    if not reviewed:
        print("Aviso: o gabarito ainda não foi revisado (reviewed: false). Os números serão provisórios.")
    if not args.yes and input("Continuar? [s/N] ").strip().lower() not in ("s", "sim", "y"):
        return 1

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_llm_client] = lambda: llm

    started = datetime.now()
    t0 = time.perf_counter()
    with TestClient(app) as api:
        response = api.put("/profile", json={"data": profile, "raw_text": ""})
        response.raise_for_status()
        job_results = []
        for job in jobs:
            print(f"  {job['id']}…", flush=True)
            job_results.append(run_job(api, job, with_texts=not args.no_texts))
    planted_results = [] if args.no_planted else run_planted(llm, profile, planted)
    app.dependency_overrides.clear()

    costs = scoring.cost_summary(llm.calls)
    call_costs = [scoring.call_cost(c) for c in llm.calls]
    total_cost = None if None in call_costs else sum(call_costs)
    run = {
        "model": description,
        "label": args.label,
        "started": started.strftime("%Y-%m-%d %H:%M"),
        "seconds": time.perf_counter() - t0,
        "fixtures_reviewed": reviewed,
        "jobs": job_results,
        "planted": planted_results,
        "costs": costs,
        "total_cost": total_cost,
        "summary": summarize(job_results, planted_results, costs),
    }

    RUNS_DIR.mkdir(exist_ok=True)
    stem = f"{started.strftime('%Y%m%d-%H%M%S')}_{model}{'_mix' if description != model else ''}"
    (RUNS_DIR / f"{stem}.json").write_text(json.dumps(run, ensure_ascii=False, indent=1), encoding="utf-8")
    (RUNS_DIR / f"{stem}.md").write_text(render_run(run), encoding="utf-8")
    rebuild_results()
    print(render_run(run))
    print(f"Salvo em evals/runs/{stem}.md e evals/results.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
