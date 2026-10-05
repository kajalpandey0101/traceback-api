import json


def _is_sensitive_key(key):
    normalized = str(key).lower().replace('-', '_')
    return any(
        part in normalized
        for part in ['password', 'token', 'secret', 'authorization', 'cookie', 'api_key', 'apikey', 'traceback_key']
    )


def redact_value(value):
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            if _is_sensitive_key(key):
                redacted[key] = '[REDACTED]'
            else:
                redacted[key] = redact_value(item)
        return redacted
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    return value


def redact_headers(headers):
    redacted = {}
    for key, value in headers.items():
        if _is_sensitive_key(key):
            redacted[key] = '[REDACTED]'
        else:
            redacted[key] = value
    return redacted


def truncate_body(value, max_size=1048576):
    if value is None:
        return None
    text = value if isinstance(value, str) else json.dumps(
        value,
        ensure_ascii=False,
        separators=(',', ':'),
        default=str,
    )
    marker = '...[TRUNCATED]'

    def fits(candidate):
        return len(json.dumps(candidate, ensure_ascii=False).encode('utf-8')) <= max_size

    if not fits(marker):
        marker = ''

    low, high = 0, len(text)
    while low < high:
        middle = (low + high + 1) // 2
        if fits(text[:middle] + marker):
            low = middle
        else:
            high = middle - 1
    return text[:low] + marker
