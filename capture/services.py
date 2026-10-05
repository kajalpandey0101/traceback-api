import json
import uuid
from datetime import timedelta
from typing import Any

import requests as http_requests
from django.conf import settings
from django.utils import timezone

from capture.models import CapturedRequest
from common.redaction import redact_headers, redact_value, truncate_body
from projects.models import Project

SAFE_METHODS = {'GET', 'HEAD', 'OPTIONS'}
CAUTION_METHODS = {'POST', 'PUT', 'PATCH'}
BLOCKED_METHODS = {'DELETE'}


def normalize_body(raw_body: Any):
    if raw_body is None:
        return {}
    if isinstance(raw_body, (dict, list)):
        return raw_body
    if isinstance(raw_body, bytes):
        raw_body = raw_body.decode('utf-8', errors='replace')
    if isinstance(raw_body, str):
        try:
            return json.loads(raw_body)
        except json.JSONDecodeError:
            return raw_body
    return raw_body


def generate_request_id() -> str:
    return f'tb_req_{uuid.uuid4().hex}'


def project_for_api_key(api_key: str | None) -> Project | None:
    if not api_key:
        return None
    return Project.objects.filter(api_key=api_key).first()


def prepare_for_storage(value, *, max_size=None):
    if value is None:
        return None, False
    if isinstance(value, bytes):
        value = value.decode('utf-8', errors='replace')
    if isinstance(value, (dict, list)):
        value = redact_value(value)
    if max_size is not None and len(
        json.dumps(value, ensure_ascii=False, separators=(',', ':'), default=str).encode('utf-8')
    ) > max_size:
        value = truncate_body(value, max_size=max_size)
        return value, True
    return value, False


def query_dict_value(query_dict):
    values = {}
    for key, items in query_dict.lists():
        values[key] = items[0] if len(items) == 1 else items
    return values


def capture_request(project: Project, request, response, *, request_id: str, elapsed_ms: int, error=None):
    if request.content_type in {'application/x-www-form-urlencoded', 'multipart/form-data'}:
        request_body = query_dict_value(request.POST)
    else:
        request_body = normalize_body(request.body)
    max_size = getattr(settings, 'MAX_CAPTURE_BODY_SIZE', 1048576)
    stored_body, body_truncated = prepare_for_storage(request_body, max_size=max_size)
    if response is not None and not getattr(response, 'streaming', False):
        response_content = normalize_body(response.content)
    else:
        response_content = {}
    stored_response_body, response_truncated = prepare_for_storage(response_content, max_size=max_size)
    headers = {k: v for k, v in request.headers.items() if k.lower() != 'content-length'}
    safe_headers = redact_headers(headers)
    safe_response_headers = redact_headers(dict(response.headers)) if response is not None else {}
    query_params = redact_value(query_dict_value(request.GET))
    response_status = response.status_code if response is not None else 500
    error_message = ''
    if error is not None:
        error_message = f'Unhandled exception: {type(error).__name__}'
    elif response_status >= 400:
        error_message = getattr(response, 'reason_phrase', '') or ''
    created = CapturedRequest.objects.create(
        project=project,
        request_id=request_id,
        method=request.method,
        path=request.path,
        query_params=query_params,
        request_headers=safe_headers,
        request_body=stored_body,
        response_status=response_status,
        response_headers=safe_response_headers,
        response_body=stored_response_body,
        latency_ms=elapsed_ms,
        error_message=error_message,
        body_truncated=body_truncated or response_truncated,
        expires_at=timezone.now() + timedelta(days=getattr(settings, 'DEFAULT_RETENTION_DAYS', 7)),
    )
    return created


def build_replay_url(project: Project, path: str) -> str:
    base = (project.target_base_url or '').rstrip('/')
    target = f'{base}{path}' if path.startswith('/') else f'{base}/{path}'
    return target


def replay_payload(captured_request: CapturedRequest, *, confirm: bool = False):
    if captured_request.method.upper() in BLOCKED_METHODS:
        raise ValueError('DELETE requests are blocked by default.')
    if captured_request.method.upper() in CAUTION_METHODS and not confirm:
        raise ValueError('Confirmation is required for this replay method.')
    headers = {k: v for k, v in captured_request.request_headers.items() if k.lower() not in {'authorization', 'cookie', 'set-cookie', 'x-traceback-key'}}
    response = http_requests.request(
        method=captured_request.method,
        url=build_replay_url(captured_request.project, captured_request.path),
        params=captured_request.query_params,
        json=captured_request.request_body if isinstance(captured_request.request_body, (dict, list)) else None,
        data=captured_request.request_body if isinstance(captured_request.request_body, str) else None,
        headers=headers,
        timeout=10,
    )
    return response
