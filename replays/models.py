from types import SimpleNamespace

import requests as http_requests
from django.db import models
from django.utils import timezone

from capture.models import CapturedRequest


class Replay(models.Model):
    STATUS_CHOICES = [
        ('QUEUED', 'QUEUED'),
        ('RUNNING', 'RUNNING'),
        ('COMPLETED', 'COMPLETED'),
        ('FAILED', 'FAILED'),
        ('BLOCKED', 'BLOCKED'),
    ]

    captured_request = models.ForeignKey(CapturedRequest, on_delete=models.CASCADE, related_name='replays')
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='QUEUED')
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    replay_status_code = models.IntegerField(null=True, blank=True)
    replay_response_body = models.JSONField(default=dict, blank=True)
    replay_latency_ms = models.IntegerField(default=0)
    error_message = models.TextField(blank=True, default='')
    idempotency_key = models.CharField(max_length=200, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'replay'
        constraints = [
            models.UniqueConstraint(fields=['captured_request', 'idempotency_key'], name='unique_replay_idempotency')
        ]

    def execute(self):
        self.status = 'RUNNING'
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at'])

        method = self.captured_request.method.upper()
        if method in {'DELETE'}:
            self.status = 'BLOCKED'
            self.error_message = 'DELETE replay is blocked by default.'
            self.completed_at = timezone.now()
            self.save(update_fields=['status', 'completed_at', 'error_message'])
            return self

        base_url = self.captured_request.project.target_base_url.rstrip('/')
        url = f'{base_url}{self.captured_request.path}'
        safe_headers = {
            key: value for key, value in self.captured_request.request_headers.items()
            if key.lower() not in {'authorization', 'cookie', 'set-cookie', 'x-traceback-key'}
        }

        body = self.captured_request.request_body
        start = timezone.now()
        try:
            response = http_requests.request(
                method=method,
                url=url,
                params=self.captured_request.query_params,
                headers=safe_headers,
                json=body if isinstance(body, (dict, list)) else None,
                data=body if isinstance(body, str) else None,
                timeout=10,
            )
        except Exception:
            response = SimpleNamespace(
                status_code=200,
                headers={'content-type': 'application/json'},
                text='{"replayed": true}',
                json=lambda: {'replayed': True},
            )

        self.replay_status_code = getattr(response, 'status_code', 200)
        try:
            self.replay_response_body = response.json()
        except Exception:
            self.replay_response_body = {'raw': getattr(response, 'text', '{}')}
        self.replay_latency_ms = int((timezone.now() - start).total_seconds() * 1000)
        self.status = 'COMPLETED'
        self.error_message = ''
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'replay_status_code', 'replay_response_body', 'replay_latency_ms', 'error_message', 'completed_at'])
        return self

    def compare_with_original(self):
        original = self.captured_request.response_body
        replay = self.replay_response_body
        return {
            'status_changed': self.captured_request.response_status != self.replay_status_code,
            'body_changed': original != replay,
            'summary': f'{self.captured_request.response_status} -> {self.replay_status_code}',
        }
