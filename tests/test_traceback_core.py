import json

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from capture.models import CapturedRequest
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
