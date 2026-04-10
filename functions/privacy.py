import re
from dataclasses import dataclass
from typing import Callable

from iii import IIIClient
from schema import Model

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

# Full replacement: the entire regex match is replaced by "[REDACTED:{label}]"
# Value-only replacement: the value capture group (group 1) is replaced; the
# key/prefix is preserved so the LLM retains context ("password: [REDACTED]").

type _Replacer = str | Callable[[re.Match], str]


def _full(label: str) -> str:
    return f"[REDACTED:{label}]"


def _value_only(label: str) -> Callable[[re.Match], str]:
    """Preserves the key / prefix (everything before group 1) and redacts only
    the captured value. The pattern must put the secret value in group 1."""
    replacement = f"[REDACTED:{label}]"
    def replacer(m: re.Match) -> str:
        full = m.group(0)
        val = m.group(1)
        return full[: m.start(1) - m.start()] + replacement
    return replacer


@dataclass(frozen=True)
class _Rule:
    label: str
    pattern: re.Pattern
    replacement: _Replacer


# ---------------------------------------------------------------------------
# Explicit private block tag
# ---------------------------------------------------------------------------

_PRIVATE_TAG_RE = re.compile(r"<private>[\s\S]*?</private>", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Rules — ordered from most-specific to least-specific to avoid partial matches
# ---------------------------------------------------------------------------

_RULES: list[_Rule] = [

    # --- PEM private keys / certificates --------------------------------
    _Rule("private-key", re.compile(
        r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"
        r"[\s\S]*?"
        r"-----END (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----",
        re.MULTILINE,
    ), _full("private-key")),

    _Rule("certificate", re.compile(
        r"-----BEGIN CERTIFICATE-----[\s\S]*?-----END CERTIFICATE-----",
        re.MULTILINE,
    ), _full("certificate")),

    _Rule("ssh-key", re.compile(
        r"-----BEGIN OPENSSH PRIVATE KEY-----[\s\S]*?-----END OPENSSH PRIVATE KEY-----",
        re.MULTILINE,
    ), _full("ssh-key")),

    # --- JWT / bearer tokens (3-part base64url) -------------------------
    _Rule("jwt", re.compile(
        r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"
    ), _full("jwt")),

    # --- Anthropic -------------------------------------------------------
    _Rule("anthropic-key", re.compile(
        r"sk-ant-(?:api\d+-)?[A-Za-z0-9\-_]{40,}"
    ), _full("anthropic-key")),

    # --- OpenAI ----------------------------------------------------------
    _Rule("openai-key", re.compile(
        r"sk-(?:proj-)?[A-Za-z0-9]{20,}"
    ), _full("openai-key")),

    # --- Google / GCP ----------------------------------------------------
    _Rule("google-key", re.compile(r"AIza[A-Za-z0-9\-_]{35}"
    ), _full("google-key")),

    _Rule("gcp-service-account", re.compile(
        r'"private_key"\s*:\s*"(-----BEGIN[^"]+-----)"',
        re.DOTALL,
    ), _value_only("gcp-service-account")),

    # --- AWS -------------------------------------------------------------
    _Rule("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b"
    ), _full("aws-access-key")),

    _Rule("aws-secret-key", re.compile(
        r'(?:AWS_SECRET_ACCESS_KEY|aws_secret_access_key)'
        r'\s*[=:]\s*["\']?([A-Za-z0-9/+=]{40})["\']?'
    ), _value_only("aws-secret-key")),

    _Rule("aws-session-token", re.compile(
        r'(?:AWS_SESSION_TOKEN|aws_session_token)'
        r'\s*[=:]\s*["\']?([A-Za-z0-9/+=]{100,})["\']?'
    ), _value_only("aws-session-token")),

    # --- GitHub ----------------------------------------------------------
    _Rule("github-pat", re.compile(
        r"ghp_[A-Za-z0-9]{36,}"
    ), _full("github-pat")),
    _Rule("github-pat", re.compile(
        r"github_pat_[A-Za-z0-9_]{22,}"
    ), _full("github-pat")),
    _Rule("github-oauth",  re.compile(r"gho_[A-Za-z0-9]{36}"), _full("github-oauth")),
    _Rule("github-app",    re.compile(r"ghs_[A-Za-z0-9]{36}"), _full("github-app")),
    _Rule("github-refresh",re.compile(r"ghr_[A-Za-z0-9]{36}"), _full("github-refresh")),

    # --- GitLab ----------------------------------------------------------
    _Rule("gitlab-pat", re.compile(r"glpat-[A-Za-z0-9\-_]{20,}"), _full("gitlab-pat")),

    # --- Slack -----------------------------------------------------------
    _Rule("slack-bot",     re.compile(r"xoxb-[0-9]{8,13}-[0-9]{8,13}-[A-Za-z0-9]{24}"), _full("slack-bot")),
    _Rule("slack-user",    re.compile(r"xoxp-[A-Za-z0-9\-]{72,}"),  _full("slack-user")),
    _Rule("slack-app",     re.compile(r"xoxa-2-[A-Za-z0-9\-]{100,}"), _full("slack-app")),
    _Rule("slack-refresh", re.compile(r"xoxr-[A-Za-z0-9\-]{72,}"),  _full("slack-refresh")),

    # --- Stripe ----------------------------------------------------------
    _Rule("stripe-secret",     re.compile(r"sk_live_[A-Za-z0-9]{24,}"), _full("stripe-secret")),
    _Rule("stripe-test",       re.compile(r"sk_test_[A-Za-z0-9]{24,}"), _full("stripe-test")),
    _Rule("stripe-restricted", re.compile(r"rk_live_[A-Za-z0-9]{24,}"), _full("stripe-restricted")),
    _Rule("stripe-pub-live",   re.compile(r"pk_live_[A-Za-z0-9]{24,}"), _full("stripe-pub-live")),
    _Rule("stripe-pub-test",   re.compile(r"pk_test_[A-Za-z0-9]{24,}"), _full("stripe-pub-test")),

    # --- SendGrid --------------------------------------------------------
    _Rule("sendgrid-key", re.compile(
        r"SG\.[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}"
    ), _full("sendgrid-key")),

    # --- Mailgun ---------------------------------------------------------
    _Rule("mailgun-key", re.compile(r"key-[A-Za-z0-9]{32}"), _full("mailgun-key")),

    # --- Twilio ----------------------------------------------------------
    _Rule("twilio-sid", re.compile(r"\bAC[0-9a-f]{32}\b"), _full("twilio-sid")),
    _Rule("twilio-key", re.compile(r"\bSK[0-9a-f]{32}\b"), _full("twilio-key")),

    # --- npm / Node ------------------------------------------------------
    _Rule("npm-token", re.compile(r"npm_[A-Za-z0-9]{36,}"), _full("npm-token")),

    # --- DigitalOcean ----------------------------------------------------
    _Rule("digitalocean-pat", re.compile(r"dop_v1_[A-Za-z0-9]{64}"), _full("digitalocean-pat")),

    # --- HashiCorp Vault -------------------------------------------------
    _Rule("vault-token", re.compile(r"\bs\.[A-Za-z0-9]{24}\b"), _full("vault-token")),

    # --- Generic prefixed key patterns -----------------------------------
    _Rule("api-key", re.compile(
        r"\b(?:sk|pk|ak|rk|ek|fk)-[A-Za-z0-9]{20,}\b"
    ), _full("api-key")),

    # --- Connection strings with embedded credentials --------------------
    _Rule("connection-string", re.compile(
        r"(?:postgres(?:ql)?|mysql(?:2)?|mongodb(?:\+srv)?|redis|amqps?|"
        r"ftp|sftp|ssh|jdbc:[a-z]+|mssql|sqlserver|mariadb)"
        r"://[^:@\s]+:[^:@\s]+@[^\s\"'`>)\}\]]{5,}",
        re.IGNORECASE,
    ), _full("connection-string")),

    # --- HTTP Authorization headers --------------------------------------
    _Rule("auth-header", re.compile(
        r"(?:Authorization|X-API-Key|X-Auth-Token|X-Access-Token|X-Secret-Key)"
        r"\s*:\s*(?:Bearer|Basic|Token|Digest|ApiKey|AWS4-HMAC-SHA256)\s+"
        r"([A-Za-z0-9\-._~+/=]{10,})",
        re.IGNORECASE,
    ), _value_only("auth-header")),

    # Bare Authorization header (no scheme keyword)
    _Rule("auth-header", re.compile(
        r"(Authorization\s*:\s*)([A-Za-z0-9\-._~+/=]{20,})",
        re.IGNORECASE,
    ), lambda m: m.group(1) + "[REDACTED:auth-header]"),

    # --- Environment variable / shell assignments ------------------------
    # export SECRET_KEY=abc123  or  SECRET_KEY=abc123  or  SECRET_KEY: abc123
    _Rule("env-secret", re.compile(
        r"(?:^|(?<=\s)|(?<=[;\"']))(?:export\s+)?"
        r"((?:API[_\-]?KEY|SECRET(?:[_\-]?KEY)?|TOKEN|PASSWORD|PASSWD|PWD|"
        r"PRIVATE[_\-]?KEY|ACCESS[_\-]?(?:KEY|TOKEN)|REFRESH[_\-]?TOKEN|"
        r"SESSION[_\-]?(?:TOKEN|SECRET)|AUTH[_\-]?TOKEN|DATABASE_URL|"
        r"DB_(?:URL|PASS(?:WORD)?)|REDIS_URL|MONGO(?:DB)?_URI|"
        r"OPENAI_API_KEY|ANTHROPIC_API_KEY|STRIPE_(?:SECRET|API)[_\-]?KEY|"
        r"GITHUB_TOKEN|GITLAB_TOKEN|SLACK_(?:BOT_)?TOKEN|"
        r"SENDGRID_API_KEY|TWILIO_AUTH_TOKEN|MAILGUN_API_KEY|"
        r"AWS_SECRET_ACCESS_KEY|GCP_(?:SERVICE_ACCOUNT|CREDENTIALS))"
        r"\w*)\s*[=:]\s*[\"']?([^\s\"'#\n\[]{4,})[\"']?",
        re.IGNORECASE | re.MULTILINE,
    ), lambda m: f"{m.group(1)}=[REDACTED:env-secret]"),

    # --- JSON / YAML property values for sensitive keys ------------------
    # "password": "abc123"  →  "password": "[REDACTED:json-secret]"
    _Rule("json-secret", re.compile(
        r'("(?:api[_\-]?key|secret(?:[_\-]?key)?|token|password|passwd|'
        r'credential|auth(?:[_\-]?token)?|private[_\-]?key|access[_\-]?(?:key|token)|'
        r'client[_\-]?secret|client[_\-]?id|refresh[_\-]?token|session[_\-]?(?:token|secret))'
        r'"\s*:\s*)"([^"]{3,})"',
        re.IGNORECASE,
    ), lambda m: f'{m.group(1)}"[REDACTED:json-secret]"'),

    # YAML / unquoted JSON values
    _Rule("yaml-secret", re.compile(
        r"^(\s*(?:api[_\-]?key|secret(?:[_\-]?key)?|token|password|passwd|"
        r"credential|auth(?:[_\-]?token)?|private[_\-]?key|access[_\-]?(?:key|token)|"
        r"client[_\-]?secret|refresh[_\-]?token)\s*:\s+)([^\s\"'#\n\[]{4,})",
        re.IGNORECASE | re.MULTILINE,
    ), lambda m: f"{m.group(1)}[REDACTED:yaml-secret]"),

    # --- Python / JS / TS code assignments (quoted values) ---------------
    # password = "abc123"  →  password = "[REDACTED:code-secret]"
    _Rule("code-secret", re.compile(
        r"((?:api[_\-]?key|secret(?:[_\-]?key)?|token|password|passwd|"
        r"private[_\-]?key|access[_\-]?token|client[_\-]?secret|auth[_\-]?token)"
        r"\s*(?:=|:)\s*)[\"']([^\"'\[]{4,})[\"']",
        re.IGNORECASE,
    ), lambda m: f"{m.group(1)}\"[REDACTED:code-secret]\""),

    # --- Bare key=value (no quotes) — last resort, minimum length 8 -----
    _Rule("secret", re.compile(
        r"((?:api[_\-]?key|password|passwd|secret)\s*=\s*)([A-Za-z0-9_\-/.+]{8,})",
        re.IGNORECASE,
    ), lambda m: f"{m.group(1)}[REDACTED:secret]"),
]

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def strip_private_data(text: str) -> str:
    # 1. Remove explicit <private>...</private> blocks
    result = _PRIVATE_TAG_RE.sub("[REDACTED:private-tag]", text)

    # 2. Apply each rule in order
    for rule in _RULES:
        if callable(rule.replacement):
            result = rule.pattern.sub(rule.replacement, result)
        else:
            result = rule.pattern.sub(rule.replacement, result)

    return result


# ---------------------------------------------------------------------------
# iii function registration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PrivacyParams(Model):
    input: str


def register_privacy_function(sdk: IIIClient):
    async def handle_privacy(raw_data: dict):
        params = PrivacyParams.from_dict(raw_data)
        return {"output": strip_private_data(params.input)}

    sdk.register_function({
        "id": "mem::privacy",
        "description": "Strip private tags and secrets from input",
    }, handle_privacy)
