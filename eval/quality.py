from schema import CompressedObservation


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
