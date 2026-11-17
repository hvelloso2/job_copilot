"""Second verification of generated texts (Etapa 5), done in code.

The model lists the statements about the candidate it finds in a text (with evidence), and
this module decides which ones are supported, using the same rules as the job analysis:
- the evidence must be an excerpt that really exists in the saved profile;
- skills/technologies and numbers inside the statement must exist in the profile.
A whole-text scan also catches skills and numbers in sentences the model did not list.
"""

import re

from app.analysis import ProfileIndex, mentions_word, normalize, unsupported_terms
from app.llm.schemas import ClaimList, JobData
from app.schemas import ClaimResult

PLACEHOLDER_RE = re.compile(r"\[PREENCHER:\s*([^\]]*)\]", re.IGNORECASE)

REASON_NO_EVIDENCE = "Sem evidência no perfil."
REASON_EVIDENCE_NOT_FOUND = "Evidência não encontrada no perfil."
REASON_TERMS = "Não está no perfil: {}."


def find_placeholders(text: str) -> list[str]:
    return [m.group(1).strip() for m in PLACEHOLDER_RE.finditer(text)]


def _locate(text: str, excerpt: str) -> tuple[int, int] | None:
    start = text.find(excerpt)
    if start < 0 and len(text.lower()) == len(text):  # case-insensitive fallback keeps offsets valid
        start = text.lower().find(excerpt.lower())
    return (start, start + len(excerpt)) if start >= 0 else None


def verify_claims(text: str, claims: ClaimList, track: JobData, index: ProfileIndex) -> list[ClaimResult]:
    placeholder_spans = [m.span() for m in PLACEHOLDER_RE.finditer(text)]
    results, seen = [], set()
    for item in claims.claims:
        claim = item.claim.strip()
        key = normalize(claim)
        if not claim or key in seen:
            continue
        seen.add(key)
        span = _locate(text, claim)
        if span and any(s <= span[0] and span[1] <= e for s, e in placeholder_spans):
            continue  # placeholders are the opposite of a claim

        evidence = (item.evidence or "").strip() or None
        reasons = []
        if evidence is None:
            reasons.append(REASON_NO_EVIDENCE)
        elif not index.contains_excerpt(evidence):
            reasons.append(REASON_EVIDENCE_NOT_FOUND)
        terms = unsupported_terms(claim, [], track.technologies, index)
        if terms:
            reasons.append(REASON_TERMS.format(", ".join(terms)))

        results.append(ClaimResult(
            claim=claim,
            evidence=evidence,
            supported=not reasons,
            reason=" ".join(reasons) or None,
            start=span[0] if span else None,
            end=span[1] if span else None,
        ))
    return results


def highlight(text: str, claims: list[ClaimResult]) -> str:
    """Wraps the unsupported claims found in the text as [[SEM SUPORTE: ...]]."""
    spans = sorted((c.start, c.end) for c in claims if not c.supported and c.start is not None)
    out, cursor = [], 0
    for start, end in spans:
        if start < cursor:  # overlaps a span already marked
            continue
        out += [text[cursor:start], f"[[SEM SUPORTE: {text[start:end]}]]"]
        cursor = end
    out.append(text[cursor:])
    return "".join(out)


def text_warnings(text: str, track: JobData, index: ProfileIndex, claims: list[ClaimResult]) -> list[str]:
    """Skills and numbers anywhere in the text (outside placeholders) that the profile does not have.

    Safety net for statements the model did not list as claims. Terms already reported in an
    unsupported claim are not repeated.
    """
    terms = unsupported_terms(PLACEHOLDER_RE.sub(" ", text), [], track.technologies, index)
    flagged = " ".join(normalize(c.claim) for c in claims if not c.supported)
    return [t for t in terms if not mentions_word(flagged, t)]
