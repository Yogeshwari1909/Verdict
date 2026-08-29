import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Common sensitive field name patterns in metadata keys
SENSITIVE_KEY_PATTERN = re.compile(
    r"^(.*_)?(password|secret|token|api_?key|auth|authorization|private_?key|access_?token|refresh_?token|pwd|credential|cvv|credit_?card)(_.*)?$",
    re.IGNORECASE,
)

# Sensitive patterns in arbitrary text / logs / stack traces
BEARER_TOKEN_PATTERN = re.compile(r"(?i)\b(Bearer\s+)[A-Za-z0-9\-\._~\+\/]+=*")
BASIC_AUTH_PATTERN = re.compile(r"(?i)\b(Basic\s+)[A-Za-z0-9\+\/]+=*")
KEY_VALUE_SECRET_PATTERN = re.compile(
    r"(?i)\b(api[_-]?key|token|access[_-]?token|refresh[_-]?token|secret|client[_-]?secret|password|passwd|pwd|auth[_-]?token|private[_-]?key)\s*([:=]|=>)\s*([\"']?)([^\"'\s,;]+)\3"
)
KNOWN_TOKEN_PREFIX_PATTERN = re.compile(
    r"\b(sk_live_[0-9a-zA-Z]+|sk_test_[0-9a-zA-Z]+|ghp_[0-9a-zA-Z]+|gho_[0-9a-zA-Z]+|AIzaSy[0-9A-Za-z-_]{33})\b"
)


def redact_text(text: Optional[str]) -> Optional[str]:
    """
    Redact sensitive information (tokens, keys, passwords) within string text.
    Replaces sensitive data with [REDACTED].
    """
    if text is None:
        return None
    if not isinstance(text, str):
        return text

    # Redact Bearer tokens: Bearer <token> -> Bearer [REDACTED]
    text = BEARER_TOKEN_PATTERN.sub(r"\1[REDACTED]", text)

    # Redact Basic auth: Basic <token> -> Basic [REDACTED]
    text = BASIC_AUTH_PATTERN.sub(r"\1[REDACTED]", text)

    # Redact key-value pairs: password=secret123 -> password=[REDACTED]
    text = KEY_VALUE_SECRET_PATTERN.sub(r"\1\2\3[REDACTED]\3", text)

    # Redact well-known token prefix formats
    text = KNOWN_TOKEN_PREFIX_PATTERN.sub(r"[REDACTED]", text)

    return text


def redact_metadata(data: Any) -> Any:
    """
    Recursively redact sensitive key-value pairs and strings in metadata.
    """
    if isinstance(data, dict):
        redacted_dict = {}
        for k, v in data.items():
            str_key = str(k)
            if SENSITIVE_KEY_PATTERN.match(str_key):
                redacted_dict[k] = "[REDACTED]"
            else:
                redacted_dict[k] = redact_metadata(v)
        return redacted_dict
    elif isinstance(data, list):
        return [redact_metadata(item) for item in data]
    elif isinstance(data, str):
        return redact_text(data)
    else:
        return data


def normalize_endpoint(endpoint: str) -> str:
    """
    Normalize endpoint path: trim whitespace and ensure it begins with '/'
    """
    cleaned = endpoint.strip()
    if cleaned and not cleaned.startswith("/") and not cleaned.startswith("http://") and not cleaned.startswith("https://"):
        cleaned = "/" + cleaned
    return cleaned


def normalize_and_redact_incident(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize and redact incoming incident payload.
    Ensures:
    - Whitespace is stripped across string fields.
    - HTTP method is normalized to uppercase.
    - Endpoint is properly formatted.
    - Sensitive values in stack trace, message, and metadata are replaced with [REDACTED].
    - Timestamp is normalized (falls back to current UTC ISO timestamp if missing/empty).
    """
    service = data["service"].strip()
    environment = data["environment"].strip()
    endpoint = normalize_endpoint(data["endpoint"])
    http_method = data["http_method"].strip().upper()
    status_code = int(data["status_code"])
    exception_type = data["exception_type"].strip()

    # Redact text fields
    exception_message = redact_text(data["exception_message"].strip())
    stack_trace = redact_text(data["stack_trace"].strip())

    request_id = data.get("request_id")
    if request_id is not None:
        request_id = redact_text(str(request_id).strip())

    timestamp = data.get("timestamp")
    if timestamp and isinstance(timestamp, str) and timestamp.strip():
        timestamp = timestamp.strip()
    else:
        timestamp = datetime.now(timezone.utc).isoformat()

    metadata = data.get("metadata")
    if metadata is not None:
        metadata = redact_metadata(metadata)

    return {
        "service": service,
        "environment": environment,
        "endpoint": endpoint,
        "http_method": http_method,
        "status_code": status_code,
        "exception_type": exception_type,
        "exception_message": exception_message,
        "stack_trace": stack_trace,
        "request_id": request_id,
        "timestamp": timestamp,
        "metadata": metadata,
    }
