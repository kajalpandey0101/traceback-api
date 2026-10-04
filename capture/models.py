import uuid

from django.db import models

from projects.models import Project


class CapturedRequest(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='captured_requests')
    request_id = models.CharField(max_length=64, unique=True, db_index=True)
    method = models.CharField(max_length=12)
    path = models.CharField(max_length=500)
    query_params = models.JSONField(default=dict, blank=True)
    request_headers = models.JSONField(default=dict, blank=True)
    request_body = models.JSONField(default=dict, blank=True)
    response_status = models.IntegerField(default=0)
    response_headers = models.JSONField(default=dict, blank=True)
    response_body = models.JSONField(default=dict, blank=True)
    latency_ms = models.IntegerField(default=0)
    error_message = models.TextField(blank=True, default='')
    body_truncated = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'captured_request'
        indexes = [
            models.Index(fields=['project', 'created_at']),
            models.Index(fields=['project', 'response_status']),
            models.Index(fields=['project', 'method']),
            models.Index(fields=['request_id']),
        ]

    def __str__(self):
        return f'{self.method} {self.path} ({self.request_id})'

    @property
    def status(self):
        return self.response_status
