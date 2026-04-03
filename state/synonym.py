from typing import List, Dict, Set
from state.stemmer import stem

SYNONYM_GROUPS: List[List[str]] = [
    ["auth", "authentication", "authn", "authenticating"],
    ["authz", "authorization", "authorizing"],
    ["db", "database", "datastore"],
    ["perf", "performance", "latency", "throughput", "slow", "bottleneck"],
    ["optim", "optimization", "optimizing", "optimise", "query-optimization"],
    ["k8s", "kubernetes", "kube"],
    ["config", "configuration", "configuring", "setup"],
    ["deps", "dependencies", "dependency"],
    ["env", "environment"],
    ["fn", "function"],
    ["impl", "implementation", "implementing"],
    ["msg", "message", "messaging"],
    ["repo", "repository"],
    ["req", "request"],
    ["res", "response"],
    ["ts", "typescript"],
    ["js", "javascript"],
    ["pg", "postgres", "postgresql"],
    ["err", "error", "errors"],
    ["api", "endpoint", "endpoints"],
    ["ci", "continuous-integration"],
    ["cd", "continuous-deployment"],
    ["test", "testing", "tests"],
    ["doc", "documentation", "docs"],
    ["infra", "infrastructure"],
    ["deploy", "deployment", "deploying"],
    ["cache", "caching", "cached"],
    ["log", "logging", "logs"],
    ["monitor", "monitoring"],
    ["observe", "observability"],
    ["sec", "security", "secure"],
    ["validate", "validation", "validating"],
    ["migrate", "migration", "migrations"],
    ["debug", "debugging"],
    ["container", "containerization", "docker"],
    ["crash", "crashloop", "crashloopbackoff"],
    ["webhook", "webhooks", "callback"],
    ["middleware", "mw"],
    ["paginate", "pagination"],
    ["serialize", "serialization"],
    ["encrypt", "encryption"],
    ["hash", "hashing"],
]

# term -> set of synonyms
synonym_map: Dict[str, Set[str]] = {}

for group in SYNONYM_GROUPS:
    stemmed = [stem(t.lower()) for t in group]

    for s in stemmed:
        if s not in synonym_map:
            synonym_map[s] = set()

        for other in stemmed:
            if other != s:
                synonym_map[s].add(other)


def get_synonyms(stemmed_term: str) -> List[str]:
    return list(synonym_map.get(stemmed_term, []))
