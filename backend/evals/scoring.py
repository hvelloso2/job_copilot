"""Scoring of the AI evaluation (Etapa 8). Pure functions: no API calls, unit tested.

Matching rule used everywhere: texts are compared without accents and case, and an item
matches an expected entry when it contains any of the entry's `match` excerpts.
"""

import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

# US$ per million tokens (input, output). Estimate only: check the current prices.
PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}


def fold(text: str) -> str:
    """Lower case, no accents, single spaces."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return " ".join("".join(c for c in decomposed if not unicodedata.combining(c)).split())


def matches(text: str, patterns: list[str]) -> bool:
    folded = fold(text)
    return any(fold(p) in folded for p in patterns)


# --- Extraction ---


@dataclass
class ExtractionScore:
    expected: int = 0
    found: int = 0               # expected requirements matched by some extracted item
    extracted: int = 0
    extracted_valid: int = 0     # extracted items that match some expected requirement
    kind_checked: int = 0
    kind_correct: int = 0        # found with the right kind (required/preferred)
    tracks_ok: bool = True
    missed: list[str] = field(default_factory=list)
    invented: list[str] = field(default_factory=list)
    wrong_kind: list[str] = field(default_factory=list)

    @property
    def coverage(self) -> float | None:
        return self.found / self.expected if self.expected else None

    @property
    def precision(self) -> float | None:
        return self.extracted_valid / self.extracted if self.extracted else None


def score_extraction(track: dict[str, Any], expected: dict[str, Any], n_tracks: int) -> ExtractionScore:
    """Compares the requirements of the chosen track with the hand-written expected ones."""
    extracted = [(r, "required") for r in track.get("required_requirements", [])]
    extracted += [(r, "preferred") for r in track.get("preferred_requirements", [])]
    wanted = [(e, "required") for e in expected.get("required", [])]
    wanted += [(e, "preferred") for e in expected.get("preferred", [])]

    score = ExtractionScore(expected=len(wanted), extracted=len(extracted))
    score.tracks_ok = n_tracks == expected.get("tracks", 1)

    for entry, kind in wanted:
        hits = [(text, k) for text, k in extracted if matches(text, entry["match"])]
        if not hits:
            score.missed.append(entry["text"])
            continue
        score.found += 1
        score.kind_checked += 1
        if any(k == kind for _, k in hits):
            score.kind_correct += 1
        else:
            score.wrong_kind.append(entry["text"])

    all_patterns = [p for entry, _ in wanted for p in entry["match"]]
    for text, _ in extracted:
        if matches(text, all_patterns):
            score.extracted_valid += 1
        else:
            score.invented.append(text)
    return score


def pick_track(tracks: list[dict[str, Any]], hint: str | None) -> int | None:
    """Index of the track whose title contains `hint` (the expected track of multi-track postings)."""
    if len(tracks) == 1:
        return 0
    if not hint:
        return None
    for i, track in enumerate(tracks):
        if matches(track.get("title", ""), [hint]):
            return i
    return None


# --- Analysis ---


@dataclass
class AnalysisCase:
    requirement: str | None   # requirement text found in the analysis (None if not found)
    expected: str
    got: str | None

    @property
    def correct(self) -> bool:
        return self.got == self.expected


def score_analysis(requirements: list[dict[str, Any]], cases: list[dict[str, Any]]) -> list[AnalysisCase]:
    """Clear cases: the profile obviously meets (or obviously lacks) a requirement."""
    results = []
    for case in cases:
        hit = next((r for r in requirements if matches(r["requirement"], case["match"])), None)
        results.append(AnalysisCase(
            requirement=hit["requirement"] if hit else None,
            expected=case["expected"],
            got=hit["status"] if hit else None,
        ))
    return results


# --- Verification (planted fabrications) ---


def _overlaps(a: str, b: str) -> bool:
    fa, fb = fold(a), fold(b)
    return bool(fa) and bool(fb) and (fa in fb or fb in fa)


@dataclass
class PlantedScore:
    fabricated: int = 0
    caught: int = 0
    true_statements: int = 0
    false_alarms: int = 0
    missed: list[str] = field(default_factory=list)
    flagged_true: list[str] = field(default_factory=list)


def score_planted(case: dict[str, Any], claims: list[dict[str, Any]], warnings: list[str]) -> PlantedScore:
    """A fabrication is caught when an unsupported claim overlaps it or a warning term is inside it.
    A true statement is a false alarm when an unsupported claim overlaps it."""
    unsupported = [c["claim"] for c in claims if not c["supported"]]
    score = PlantedScore(fabricated=len(case["fabricated"]), true_statements=len(case["true"]))
    for snippet in case["fabricated"]:
        if any(_overlaps(snippet, c) for c in unsupported) or any(fold(w) in fold(snippet) for w in warnings):
            score.caught += 1
        else:
            score.missed.append(snippet)
    for snippet in case["true"]:
        if any(_overlaps(snippet, c) for c in unsupported):
            score.false_alarms += 1
            score.flagged_true.append(snippet)
    return score


# --- Cost ---


def call_cost(call: Any) -> float | None:
    """Estimated US$ of one call, from its model's price (None if the model is unknown)."""
    price = PRICES_PER_MTOK.get(call.model) or PRICES_PER_MTOK.get(_base_model(call.model))
    if not price:
        return None
    return (call.input_tokens * price[0] + call.output_tokens * price[1]) / 1_000_000


def cost_summary(calls: list[Any]) -> list[dict[str, Any]]:
    """Average tokens, time and estimated cost per operation, from LLMClient.calls."""
    by_op: dict[str, list[Any]] = defaultdict(list)
    for call in calls:
        by_op[call.operation].append(call)
    rows = []
    for op, items in by_op.items():
        n = len(items)
        tokens_in = sum(c.input_tokens for c in items) / n
        tokens_out = sum(c.output_tokens for c in items) / n
        price = PRICES_PER_MTOK.get(items[0].model) or PRICES_PER_MTOK.get(_base_model(items[0].model))
        cost = (tokens_in * price[0] + tokens_out * price[1]) / 1_000_000 if price else None
        rows.append({
            "operation": op,
            "calls": n,
            "input_tokens": round(tokens_in),
            "output_tokens": round(tokens_out),
            "seconds": round(sum(c.duration_s for c in items) / n, 1),
            "cost_usd": cost,
        })
    return rows


def _base_model(model: str) -> str:
    return next((m for m in PRICES_PER_MTOK if model.startswith(m)), model)
