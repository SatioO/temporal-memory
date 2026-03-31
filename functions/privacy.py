import re


PRIVATE_TAG_RE = re.compile(
    r'/<private>[\s\S]*?<\/private>/gi')

SECRET_PATTERN_SOURCES = [
    re.compile(
        r'(?:api[_-]?key|secret|token|password|credential|auth)[\s]*[=:]\s*["\']?[A-Za-z0-9_\-/.+]{20,}["\']?', re.IGNORECASE),
    re.compile(r'(?:sk|pk|rk|ak)-[A-Za-z0-9]{20,}'),
    re.compile(r'sk-ant-[A-Za-z0-9\-_]{20,}'),
    re.compile(r'ghp_[A-Za-z0-9]{36}'),
    re.compile(r'github_pat_[A-Za-z0-9_]{22,}'),
    re.compile(r'xoxb-[A-Za-z0-9\-]+'),
    re.compile(r'AKIA[0-9A-Z]{16}'),
    re.compile(r'AIza[A-Za-z0-9\-_]{35}'),
    re.compile(
        r'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}'),
    re.compile(r'npm_[A-Za-z0-9]{36}'),
    re.compile(r'glpat-[A-Za-z0-9\-_]{20,}'),
    re.compile(r'dop_v1_[A-Za-z0-9]{64}'),
]


def strip_private_data(input: str) -> str:
    result = re.sub(PRIVATE_TAG_RE, "[REDACTED]", input)
    for pattern in SECRET_PATTERN_SOURCES:
        result = pattern.sub("[REDACTED]", result)

    return result


def register_privacy_function(sdk):
    pass
