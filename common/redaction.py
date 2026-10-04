import json

SENSITIVE_KEYS = {
    'authorization',
    'cookie',
    'set-cookie',
    'password',
    'token',
    'access_token',
    'refresh_token',
    'client_secret',
    'api_key',
    'secret',
}


def _is_sensitive_key(key):
    normalized = str(key).lower().replace('-', '_')
    return any(part in normalized for part in ['password', 'token', 'secret', 'authorization', 'cookie', 'api_key'])


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
    if isinstance(value, (str, bytes)):
        text = value.decode('utf-8', errors='replace') if isinstance(value, bytes) else value
        if len(text) <= max_size:
            return value
        return (text[:max_size] + '...[TRUNCATED]') if isinstance(value, str) else (text[:max_size] + '...[TRUNCATED]').encode('utf-8')
    payload = json.dumps(value, default=str)
    if len(payload) <= max_size:
        return value
    return json.loads((payload[:max_size] + '...[TRUNCATED]')[:max_size])
