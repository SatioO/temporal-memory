from dataclasses import dataclass
import re

from iii import IIIClient

from schema import Model


PRIVATE_TAG_RE = re.compile(
    r'<private>[\s\S]*?<\/private>', re.IGNORECASE)

SECRET_PATTERN_SOURCES = [
    re.compile(
        r'(?:api[_-]?key|secret|token|password|credential|auth)\w*\s*[=:]\s*["\']?[A-Za-z0-9_\-/.+]{3,}', re.IGNORECASE),
    re.compile(r'\b(?:sk|pk|rk|ak)-[A-Za-z0-9]{20,}'),
    re.compile(r'sk-ant-[A-Za-z0-9\-_]{20,}'),
    re.compile(r'ghp_[A-Za-z0-9]{20,}'),
    re.compile(r'github_pat_[A-Za-z0-9_]{22,}'),
    re.compile(r'xoxb-[A-Za-z0-9-]+'),
    re.compile(r'AKIA[0-9A-Z]{16}'),
    re.compile(r'AIza[A-Za-z0-9\-_]{35}'),
    re.compile(
        r'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}'),
    re.compile(r'npm_[A-Za-z0-9]{20,}'),
    re.compile(r'glpat-[A-Za-z0-9\-_]{20,}'),
    re.compile(r'dop_v1_[A-Za-z0-9]{64}'),
]


def strip_private_data(input: str) -> str:
    result = re.sub(PRIVATE_TAG_RE, "[REDACTED]", input)
    for pattern in SECRET_PATTERN_SOURCES:
        result = pattern.sub("[REDACTED]", result)

    return result


@dataclass(frozen=True)
class PrivacyParams(Model):
    input: str


def register_privacy_function(sdk: IIIClient):
    def handle_privacy(params: PrivacyParams):
        return {"output": strip_private_data(params.input)}

    sdk.register_function({
        "id": "mem::privacy",
        "description": "Strip private tags and secrets from input",
    }, handle_privacy)
