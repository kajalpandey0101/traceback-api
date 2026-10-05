import json
from unittest.mock import patch

import pytest
from django.http import JsonResponse
from django.test import RequestFactory, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from capture.middleware import TracebackMiddleware
from capture.models import CapturedRequest
from capture.services import capture_request, generate_request_id, prepare_for_storage
from common.redaction import redact_value
from projects.models import Project


@pytest.mark.django_db
class TestTracebackCore:
    def test_root_health_endpoint_returns_json(self):
        client = APIClient()

        response = client.get('/')

        assert response.status_code == 200
        assert response.json()['project'] == 'Traceback'
        assert response.json()['status'] == 'ok'

    def test_redact_nested_values(self):
        payload = {
            "username": "kajal",
            "password": "secret123",
            "user": {
                "name": "Kajal",
                "credentials": {"token": "abc123"},
            },
            "items": [{"password": "x"}, {"safe": "ok"}],
        }
        result = redact_value(payload)
        assert result["username"] == "kajal"
        assert result["password"] == "[REDACTED]"
        assert result["user"]["credentials"]["token"] == "[REDACTED]"
        assert result["items"][0]["password"] == "[REDACTED]"
        assert result["items"][1]["safe"] == "ok"

    def test_capture_request_and_response_metadata(self):
        project = Project.objects.create(name="Demo", target_base_url="http://localhost:9001")
        project.set_api_key("tb_live_test_key")

        client = APIClient()
        response = client.post(
            "/api/test/echo/",
            data=json.dumps({"username": "kajal", "password": "secret123"}),
            content_type="application/json",
            HTTP_X_TRACEBACK_KEY=project.api_key,
        )

        assert response.status_code == 200
        assert response.headers.get("X-Traceback-Request-ID")
        captured = CapturedRequest.objects.latest("created_at")
        assert captured.project == project
        assert captured.request_id == response.headers["X-Traceback-Request-ID"]
        assert captured.response_status == 200
        assert captured.method == "POST"
        assert captured.request_body["password"] == "[REDACTED]"

    def test_capture_redacts_nested_response_and_query_data(self):
        project = Project.objects.create(name="Demo", target_base_url="http://localhost:9001")
        request = RequestFactory().post(
            "/capture/?tag=one&tag=two&access_token=query-secret",
            data=json.dumps({"users": [{"password": "body-secret"}]}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer request-secret",
            HTTP_COOKIE="sessionid=cookie-secret",
            HTTP_X_TRACEBACK_KEY="tb_live_platform-secret",
        )
        response = JsonResponse({
            "items": [{"refresh_token": "response-secret", "safe": "value"}],
        })
        response["Set-Cookie"] = "sessionid=response-cookie-secret"

        captured = capture_request(
            project,
            request,
            response,
            request_id=generate_request_id(),
            elapsed_ms=12,
        )

        assert captured.query_params == {
            "tag": ["one", "two"],
            "access_token": "[REDACTED]",
        }
        assert captured.request_body["users"][0]["password"] == "[REDACTED]"
        assert captured.request_headers["Authorization"] == "[REDACTED]"
        assert captured.request_headers["Cookie"] == "[REDACTED]"
        assert captured.request_headers["X-Traceback-Key"] == "[REDACTED]"
        assert captured.response_body["items"][0] == {
            "refresh_token": "[REDACTED]",
            "safe": "value",
        }
        assert captured.response_headers["Set-Cookie"] == "[REDACTED]"

    @override_settings(MAX_CAPTURE_BODY_SIZE=96)
    def test_capture_body_truncation_stays_valid_and_within_limit(self):
        body, truncated = prepare_for_storage(
            {"password": "do-not-store", "data": "x" * 500},
            max_size=96,
        )

        assert truncated
        assert len(json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) <= 96
        assert "do-not-store" not in json.dumps(body)

    def test_capture_storage_failure_does_not_break_response(self):
        project = Project.objects.create(name="Demo", target_base_url="http://localhost:9001")
        project.set_api_key("tb_live_storage_failure")
        request = RequestFactory().get("/", HTTP_X_TRACEBACK_KEY=project.api_key)
        response = JsonResponse({"ok": True})
        middleware = TracebackMiddleware(lambda _request: response)

        with patch("capture.middleware.project_for_api_key", return_value=project), patch(
            "capture.middleware.capture_request",
            side_effect=RuntimeError("database unavailable"),
        ):
            result = middleware(request)

        assert result is response
        assert result.status_code == 200
        assert result["X-Traceback-Request-ID"] == request.META["TRACEBACK_REQUEST_ID"]

    def test_unhandled_exception_is_captured_and_re_raised(self):
        project = Project.objects.create(name="Demo", target_base_url="http://localhost:9001")
        project.set_api_key("tb_live_unhandled_exception")
        request = RequestFactory().get("/failure/", HTTP_X_TRACEBACK_KEY=project.api_key)

        def raise_error(_request):
            raise ValueError("exception may contain a secret")

        middleware = TracebackMiddleware(raise_error)

        with pytest.raises(ValueError):
            middleware(request)

        captured = CapturedRequest.objects.get(request_id=request.META["TRACEBACK_REQUEST_ID"])
        assert captured.response_status == 500
        assert captured.error_message == "Unhandled exception: ValueError"
        assert "secret" not in captured.error_message

    def test_capture_redacts_sensitive_form_fields(self):
        project = Project.objects.create(name="Demo", target_base_url="http://localhost:9001")
        request = RequestFactory().post(
            "/form/",
            data="password=form-secret&username=kajal",
            content_type="application/x-www-form-urlencoded",
        )

        captured = capture_request(
            project,
            request,
            JsonResponse({"ok": True}),
            request_id=generate_request_id(),
            elapsed_ms=3,
        )

        assert captured.request_body == {"password": "[REDACTED]", "username": "kajal"}

    def test_replay_requires_confirmation_for_caution_methods(self):
        project = Project.objects.create(name="Demo", target_base_url="http://localhost:9001")
        project.set_api_key("tb_live_replay")
        request = CapturedRequest.objects.create(
            project=project,
            request_id="tb_req_replay_01",
            method="POST",
            path="/api/orders",
            query_params={},
            request_headers={},
            request_body={"status": "pending"},
            response_status=500,
            response_headers={},
            response_body={"detail": "error"},
            latency_ms=100,
            body_truncated=False,
            expires_at=None,
        )

        client = APIClient()
        response = client.post(reverse("request-replay", kwargs={"pk": request.pk}), {"confirm": False}, format="json")
        assert response.status_code == 400

    def test_replay_idempotency_prevents_duplicates(self):
        project = Project.objects.create(name="Demo", target_base_url="http://localhost:9001")
        project.set_api_key("tb_live_replay2")
        request = CapturedRequest.objects.create(
            project=project,
            request_id="tb_req_replay_02",
            method="GET",
            path="/api/orders",
            query_params={},
            request_headers={},
            request_body={},
            response_status=500,
            response_headers={},
            response_body={"detail": "error"},
            latency_ms=100,
            body_truncated=False,
            expires_at=None,
        )

        client = APIClient()
        first = client.post(
            reverse("request-replay", kwargs={"pk": request.pk}),
            {"confirm": True, "idempotency_key": "replay-123"},
            format="json",
        )
        second = client.post(
            reverse("request-replay", kwargs={"pk": request.pk}),
            {"confirm": True, "idempotency_key": "replay-123"},
            format="json",
        )

        assert first.status_code == 200
        assert second.status_code == 409
