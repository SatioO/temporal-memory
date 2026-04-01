from schema import CompressedObservation
from schema.domain import SessionSummary


def score_compression(obs: CompressedObservation) -> float:
    score = 0

    if obs.facts:
        score += 25
        if len(obs.facts) >= 3:
            score += 10

    if obs.narrative:
        if len(obs.narrative) >= 20:
            score += 20
        if len(obs.narrative) >= 50:
            score += 5

    if obs.title and 5 <= len(obs.title) <= 120:
        score += 15

    if obs.concepts:
        score += 15

    if obs.importance and 1 <= obs.importance <= 10:
        score += 10

    return min(100, score)


def score_summary(summary: SessionSummary) -> float:
    score = 0

    if summary.title and len(summary.title) >= 5:
        score += 20

    if summary.narrative:
        n = len(summary.narrative)
        if n >= 20:
            score += 25
        if n >= 100:
            score += 5

    if summary.key_decisions:
        score += 20

    if summary.files_modified:
        score += 15

    if summary.concepts:
        score += 15

    return min(100, score)
